
import hashlib
import os
import uuid
import datetime as dt
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session,
    jsonify, send_from_directory, abort,
)
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# ---------------- Config ----------------
BASE_DIR = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "new_web", "templates"))
STATIC_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "static"))
DEFAULT_UPLOAD_DIR = os.path.abspath(os.path.join(BASE_DIR, "uploads"))

ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".md", ".csv", ".png", ".jpg", ".jpeg", ".zip",
}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
EDIT_ROLES = {"editor", "approver", "admin"}

db = SQLAlchemy()
migrate = Migrate()


def create_app(test_config=None):
    if load_dotenv:
        load_dotenv(os.path.join(BASE_DIR, ".env"))

    app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR, static_url_path="/static")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    app.config["UPLOAD_DIR"] = DEFAULT_UPLOAD_DIR
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    db.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        db.create_all()
        ensure_columns()
        if not app.config.get("TESTING"):
            seed_if_needed()

    register_routes(app)
    return app


# ---------------- Models ----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    pwd_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="approver")
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)

    def set_password(self, pw):
        self.pwd_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.pwd_hash, pw)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)


class Region(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    project = db.relationship(Project, backref=db.backref("regions", lazy=True))


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    region_id = db.Column(db.Integer, db.ForeignKey("region.id"), nullable=False)
    region = db.relationship(Region, backref=db.backref("groups", lazy=True))


class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    doc_code = db.Column(db.String(32), unique=True)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    group = db.relationship(Group, backref=db.backref("files", lazy=True))
    status = db.Column(db.String(32), default="草稿")
    checked_out_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    checked_out_at = db.Column(db.DateTime)
    current_version_id = db.Column(db.Integer)


class FileVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey("file.id"), nullable=False)
    file = db.relationship(File, backref=db.backref("versions", lazy=True))
    label = db.Column(db.String(32), nullable=False)
    date = db.Column(db.DateTime, default=dt.datetime.utcnow)
    author = db.Column(db.String(64))
    rel_path = db.Column(db.String(255), default="")
    original_filename = db.Column(db.String(255))
    size_bytes = db.Column(db.Integer, default=0)
    sha256 = db.Column(db.String(64))
    comment = db.Column(db.Text)
    parent_version_id = db.Column(db.Integer, db.ForeignKey("file_version.id"))


class AcceptanceTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey("file.id"), nullable=False)
    file = db.relationship(File, backref=db.backref("accept_tasks", lazy=True))
    owner = db.Column(db.String(64))
    status = db.Column(db.String(32), default="待验收")
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(64))
    action = db.Column(db.String(64))
    target = db.Column(db.String(128))
    detail = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)


def ensure_columns():
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    wanted = {
        "file": {
            "doc_code": "VARCHAR(32)",
            "current_version_id": "INTEGER",
        },
        "file_version": {
            "original_filename": "VARCHAR(255)",
            "size_bytes": "INTEGER DEFAULT 0",
            "sha256": "VARCHAR(64)",
            "comment": "TEXT",
            "parent_version_id": "INTEGER",
        },
    }
    for table, cols in wanted.items():
        if table not in existing_tables:
            continue
        have = {c["name"] for c in inspector.get_columns(table)}
        for name, spec in cols.items():
            if name not in have:
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {spec}"))
        db.session.commit()


def seed_if_needed():
    if not User.query.first():
        admin = User(username="admin", email="admin@example.com", role="admin")
        admin.set_password("admin123")
        editor = User(username="editor", email="editor@example.com", role="editor")
        editor.set_password("editor123")
        viewer = User(username="viewer", email="viewer@example.com", role="viewer")
        viewer.set_password("viewer123")
        db.session.add_all([admin, editor, viewer])
        db.session.commit()
    if not Project.query.first():
        p1 = Project(name="项目 1")
        p2 = Project(name="项目 2")
        db.session.add_all([p1, p2])
        db.session.flush()
        regions = []
        for pname, project in (("China", p1), ("EU", p1), ("FDA", p1), ("UK", p1), ("China", p2)):
            regions.append(Region(name=pname, project=project))
        db.session.add_all(regions)
        db.session.flush()
        groups = []
        for r in regions:
            groups.append(Group(name="占位条目 1", region=r))
            groups.append(Group(name="占位条目 2", region=r))
        db.session.add_all(groups)
        db.session.commit()


def current_user():
    name = session.get("username")
    if not name:
        return None
    return User.query.filter_by(username=name).first()


def require_login():
    if "username" not in session:
        abort(401)


def require_login_json(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return jsonify({"ok": False, "error": "未登录"}), 401
        return fn(*args, **kwargs)
    return wrapper


def audit(user, action, target, detail=""):
    db.session.add(AuditLog(user=user, action=action, target=target, detail=detail or ""))


def next_doc_code():
    last = File.query.order_by(File.id.desc()).first()
    n = (last.id + 1) if last else 1
    return f"DOC-{n:04d}"


def next_version_label(file_id):
    count = FileVersion.query.filter_by(file_id=file_id).count()
    return f"V{count + 1}"


def file_ext(filename):
    return os.path.splitext(filename or "")[1].lower()


def validate_upload(storage):
    if not storage or not storage.filename:
        return "请选择要上传的文件"
    ext = file_ext(storage.filename)
    if ext not in ALLOWED_EXTENSIONS:
        return f"不支持的文件类型：{ext or '无扩展名'}"
    return None


def save_version_bytes(upload_dir, file_id, label, original_name, data):
    ext = file_ext(original_name) or ".bin"
    safe = secure_filename(original_name) or f"document{ext}"
    stored = f"{uuid.uuid4().hex}_{safe}"
    rel = os.path.join("file", str(file_id), stored)
    dest_dir = os.path.join(upload_dir, "file", str(file_id))
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(upload_dir, rel)
    with open(path, "wb") as f:
        f.write(data)
    return rel.replace("\\", "/"), hashlib.sha256(data).hexdigest(), len(data)


def user_can_edit(user):
    return bool(user) and user.role in EDIT_ROLES


def locker(file_row):
    if not file_row.checked_out_by:
        return None
    return db.session.get(User, file_row.checked_out_by)


def serialize_file(f):
    holder = locker(f)
    current = db.session.get(FileVersion, f.current_version_id) if f.current_version_id else None
    if not current:
        current = (
            FileVersion.query.filter_by(file_id=f.id)
            .order_by(FileVersion.date.desc(), FileVersion.id.desc())
            .first()
        )
    return {
        "id": f.id,
        "name": f.name,
        "doc_code": f.doc_code,
        "status": f.status,
        "group_id": f.group_id,
        "checked_out_by": f.checked_out_by,
        "checked_out_by_name": holder.username if holder else None,
        "checked_out_at": f.checked_out_at.isoformat() if f.checked_out_at else None,
        "current_version": current.label if current else None,
        "current_version_id": current.id if current else None,
        "sha256": current.sha256 if current else None,
    }


def serialize_version(v):
    return {
        "id": v.id,
        "file_id": v.file_id,
        "label": v.label,
        "date": v.date.strftime("%Y-%m-%d %H:%M") if v.date else None,
        "author": v.author,
        "rel_path": v.rel_path,
        "original_filename": v.original_filename,
        "size_bytes": v.size_bytes or 0,
        "sha256": v.sha256,
        "comment": v.comment or "",
        "parent_version_id": v.parent_version_id,
        "download_url": f"/versions/download?version_id={v.id}",
    }


def register_routes(app):
    @app.route("/")
    def home():
        if "username" in session:
            return redirect(url_for("main"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            u = User.query.filter((User.username == username) | (User.email == username)).first()
            if not u or not u.check_password(password):
                return render_template("auth.html", error="用户名或密码错误")
            session["username"] = u.username
            session["role"] = u.role
            return redirect(url_for("main"))
        return render_template("auth.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return render_template("logout.html")

    @app.route("/main")
    def main():
        if "username" not in session:
            return redirect(url_for("login"))
        return render_template("main.html", username=session["username"])

    @app.get("/api/me")
    def api_me():
        if "username" not in session:
            return jsonify({"ok": False, "user": None})
        u = current_user()
        if not u:
            session.clear()
            return jsonify({"ok": False, "user": None})
        return jsonify({"ok": True, "user": {"id": u.id, "username": u.username, "role": u.role}})

    @app.get("/api/projects")
    @require_login_json
    def api_projects():
        data = [{"id": p.id, "name": p.name} for p in Project.query.order_by(Project.id).all()]
        return jsonify({"ok": True, "projects": data})

    @app.get("/api/regions")
    @require_login_json
    def api_regions():
        pid = request.args.get("project_id", type=int)
        q = Region.query
        if pid:
            q = q.filter_by(project_id=pid)
        return jsonify({
            "ok": True,
            "regions": [{"id": r.id, "name": r.name, "project_id": r.project_id} for r in q.all()],
        })

    @app.get("/api/groups")
    @require_login_json
    def api_groups():
        rid = request.args.get("region_id", type=int)
        q = Group.query.filter_by(region_id=rid) if rid else Group.query
        return jsonify({"ok": True, "groups": [{"id": g.id, "name": g.name, "region_id": g.region_id} for g in q.all()]})

    @app.get("/api/files")
    @require_login_json
    def api_files():
        gid = request.args.get("group_id", type=int)
        q = File.query.filter_by(group_id=gid) if gid else File.query
        return jsonify({"ok": True, "files": [serialize_file(f) for f in q.order_by(File.id).all()]})

    @app.post("/api/files/upload")
    @require_login_json
    def api_upload():
        user = current_user()
        if not user_can_edit(user):
            return jsonify({"ok": False, "error": "当前角色不能上传文件"}), 403
        group_id = request.form.get("group_id", type=int)
        group = db.session.get(Group, group_id) if group_id else None
        if not group:
            return jsonify({"ok": False, "error": "缺少有效的分组"}), 400
        storage = request.files.get("file")
        err = validate_upload(storage)
        if err:
            return jsonify({"ok": False, "error": err}), 400
        data = storage.read()
        if not data:
            return jsonify({"ok": False, "error": "文件内容为空"}), 400
        if len(data) > MAX_UPLOAD_BYTES:
            return jsonify({"ok": False, "error": "文件超过 50MB 限制"}), 400
        name = (request.form.get("name") or "").strip() or os.path.splitext(storage.filename)[0]
        comment = (request.form.get("comment") or "").strip()
        row = File(name=name, group_id=group.id, status="草稿", doc_code=next_doc_code())
        db.session.add(row)
        db.session.flush()
        label = "V1"
        rel, digest, size = save_version_bytes(app.config["UPLOAD_DIR"], row.id, label, storage.filename, data)
        ver = FileVersion(
            file_id=row.id,
            label=label,
            author=user.username,
            rel_path=rel,
            original_filename=storage.filename,
            size_bytes=size,
            sha256=digest,
            comment=comment or "首次上传",
            parent_version_id=None,
        )
        db.session.add(ver)
        db.session.flush()
        row.current_version_id = ver.id
        audit(user.username, "upload", row.doc_code, f"{row.name} {label} sha256={digest}")
        db.session.commit()
        return jsonify({"ok": True, "file": serialize_file(row), "version": serialize_version(ver)})

    @app.post("/api/files/checkout")
    @require_login_json
    def api_checkout():
        user = current_user()
        if not user_can_edit(user):
            return jsonify({"ok": False, "error": "当前角色不能借出文件"}), 403
        data = request.get_json() or {}
        f = db.session.get(File, data.get("file_id"))
        if not f:
            return jsonify({"ok": False, "error": "文件不存在"}), 404
        if f.checked_out_by:
            holder = locker(f)
            who = holder.username if holder else str(f.checked_out_by)
            if f.checked_out_by == user.id:
                return jsonify({"ok": False, "error": "你已经借出了该文件"}), 409
            return jsonify({"ok": False, "error": f"文件已被 {who} 借出"}), 409
        f.checked_out_by = user.id
        f.checked_out_at = dt.datetime.utcnow()
        f.status = "已借出"
        audit(user.username, "checkout", f.doc_code or f.name, "")
        db.session.commit()
        return jsonify({"ok": True, "file": serialize_file(f)})

    @app.post("/api/files/checkin")
    @require_login_json
    def api_checkin():
        user = current_user()
        if not user_can_edit(user):
            return jsonify({"ok": False, "error": "当前角色不能归还文件"}), 403
        file_id = request.form.get("file_id", type=int) or (request.get_json() or {}).get("file_id")
        f = db.session.get(File, file_id)
        if not f:
            return jsonify({"ok": False, "error": "文件不存在"}), 404
        if not f.checked_out_by:
            return jsonify({"ok": False, "error": "文件未借出"}), 409
        if f.checked_out_by != user.id and user.role != "admin":
            holder = locker(f)
            return jsonify({"ok": False, "error": f"只有借出人 {holder.username if holder else ''} 可以归还"}), 403
        storage = request.files.get("file")
        err = validate_upload(storage)
        if err:
            return jsonify({"ok": False, "error": err}), 400
        data = storage.read()
        if not data:
            return jsonify({"ok": False, "error": "文件内容为空"}), 400
        digest = hashlib.sha256(data).hexdigest()
        current = db.session.get(FileVersion, f.current_version_id) if f.current_version_id else None
        comment = (request.form.get("comment") or "").strip()
        unchanged = bool(current and current.sha256 == digest)
        if unchanged:
            f.checked_out_by = None
            f.checked_out_at = None
            f.status = "草稿"
            audit(user.username, "checkin", f.doc_code or f.name, "内容未变化，未创建新版本")
            db.session.commit()
            return jsonify({"ok": True, "unchanged": True, "file": serialize_file(f)})

        label = next_version_label(f.id)
        rel, digest, size = save_version_bytes(app.config["UPLOAD_DIR"], f.id, label, storage.filename, data)
        ver = FileVersion(
            file_id=f.id,
            label=label,
            author=user.username,
            rel_path=rel,
            original_filename=storage.filename,
            size_bytes=size,
            sha256=digest,
            comment=comment or f"由 {current.label if current else '无'} 签入",
            parent_version_id=current.id if current else None,
        )
        db.session.add(ver)
        db.session.flush()
        f.current_version_id = ver.id
        f.checked_out_by = None
        f.checked_out_at = None
        f.status = "草稿"
        parent = current.label if current else "无"
        audit(user.username, "checkin", f.doc_code or f.name, f"{parent} -> {label} sha256={digest}")
        db.session.commit()
        return jsonify({"ok": True, "unchanged": False, "file": serialize_file(f), "version": serialize_version(ver)})

    @app.post("/api/files/unlock")
    @require_login_json
    def api_unlock():
        user = current_user()
        data = request.get_json() or {}
        f = db.session.get(File, data.get("file_id"))
        if not f:
            return jsonify({"ok": False, "error": "文件不存在"}), 404
        if not f.checked_out_by:
            return jsonify({"ok": False, "error": "文件未借出"}), 409
        if f.checked_out_by != user.id and user.role != "admin":
            return jsonify({"ok": False, "error": "无权取消借出"}), 403
        holder = locker(f)
        f.checked_out_by = None
        f.checked_out_at = None
        f.status = "草稿"
        audit(user.username, "unlock", f.doc_code or f.name, f"取消 {holder.username if holder else ''} 的借出，未生成新版本")
        db.session.commit()
        return jsonify({"ok": True, "file": serialize_file(f)})

    @app.get("/api/files/versions")
    @require_login_json
    def api_versions():
        fid = request.args.get("file_id", type=int)
        if not fid:
            return jsonify({"ok": False, "error": "缺少 file_id"}), 400
        q = FileVersion.query.filter_by(file_id=fid).order_by(FileVersion.date.desc(), FileVersion.id.desc())
        return jsonify({"ok": True, "versions": [serialize_version(v) for v in q.all()]})

    @app.get("/api/files/<int:file_id>/trace")
    @require_login_json
    def api_trace(file_id):
        f = db.session.get(File, file_id)
        if not f:
            return jsonify({"ok": False, "error": "文件不存在"}), 404
        versions = (
            FileVersion.query.filter_by(file_id=f.id)
            .order_by(FileVersion.date.asc(), FileVersion.id.asc())
            .all()
        )
        codes = [f.doc_code, f.name]
        logs = (
            AuditLog.query.filter(AuditLog.target.in_([c for c in codes if c]))
            .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
            .all()
        )
        chain = []
        for v in versions:
            parent = db.session.get(FileVersion, v.parent_version_id) if v.parent_version_id else None
            chain.append({
                **serialize_version(v),
                "parent_label": parent.label if parent else None,
            })
        return jsonify({
            "ok": True,
            "file": serialize_file(f),
            "versions": chain,
            "audit": [{
                "id": a.id,
                "user": a.user,
                "action": a.action,
                "target": a.target,
                "detail": a.detail,
                "created_at": a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else None,
            } for a in logs],
        })

    @app.get("/versions/download")
    def versions_download():
        require_login()
        vid = request.args.get("version_id", type=int)
        v = db.session.get(FileVersion, vid) if vid else None
        if not v or not v.rel_path:
            abort(404)
        path = os.path.join(app.config["UPLOAD_DIR"], v.rel_path)
        if not os.path.isfile(path):
            abort(404)
        directory, filename = os.path.split(path)
        user = current_user()
        audit(user.username if user else "?", "download", v.file.doc_code if v.file else str(v.file_id), v.label)
        db.session.commit()
        download_name = v.original_filename or filename
        return send_from_directory(directory, filename, as_attachment=True, download_name=download_name)

    @app.get("/api/acceptance")
    @require_login_json
    def api_acceptance_list():
        tasks = AcceptanceTask.query.filter_by(status="待验收").all()
        out = []
        for t in tasks:
            out.append({
                "id": t.id,
                "file_id": t.file_id,
                "name": t.file.name,
                "owner": t.owner,
                "date": t.created_at.strftime("%Y-%m-%d %H:%M"),
            })
        return jsonify({"ok": True, "items": out})

    @app.post("/api/acceptance/approve")
    @require_login_json
    def api_accept_approve():
        data = request.get_json() or {}
        user = session["username"]
        t = db.session.get(AcceptanceTask, data.get("task_id"))
        if not t:
            abort(404)
        t.status = "已验收"
        t.file.status = "已验收"
        audit(user, "accept", t.file.doc_code or t.file.name, f"task={t.id}")
        db.session.commit()
        return jsonify({"ok": True})

    @app.post("/api/acceptance/reject")
    @require_login_json
    def api_accept_reject():
        data = request.get_json() or {}
        user = session["username"]
        t = db.session.get(AcceptanceTask, data.get("task_id"))
        if not t:
            abort(404)
        t.status = "已拒绝"
        t.file.status = "已拒绝"
        audit(user, "reject", t.file.doc_code or t.file.name, data.get("reason", ""))
        db.session.commit()
        return jsonify({"ok": True})


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
