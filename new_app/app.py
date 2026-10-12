
import os
import hashlib
import datetime as dt
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

# ---------------- Config ----------------
BASE_DIR = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "new_web", "templates"))
STATIC_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "static"))
DEFAULT_VERSION_FILE = "versions/history.pdf"
UPLOAD_ROOT = os.path.join(STATIC_DIR, "versions", "uploads")

REGION_LABELS = {
    "China": "China · NMPA",
    "EU": "EU · MDR",
    "FDA": "US · FDA",
    "UK": "UK · MHRA",
}

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR, static_url_path="/static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# ---------------- Models ----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    pwd_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="approver")  # viewer/editor/approver/admin
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
    name = db.Column(db.String(80), nullable=False)  # China / EU / FDA / UK
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
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    group = db.relationship(Group, backref=db.backref("files", lazy=True))
    status = db.Column(db.String(32), default="草稿")
    checked_out_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    checked_out_at = db.Column(db.DateTime)
    doc_code = db.Column(db.String(32))
    current_version_id = db.Column(db.Integer)


class FileVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey("file.id"), nullable=False)
    file = db.relationship(File, backref=db.backref("versions", lazy=True))
    label = db.Column(db.String(32), nullable=False)
    date = db.Column(db.DateTime, default=dt.datetime.utcnow)
    author = db.Column(db.String(64))
    rel_path = db.Column(db.String(255), default=DEFAULT_VERSION_FILE)
    original_filename = db.Column(db.String(255))
    size_bytes = db.Column(db.Integer, default=0)
    sha256 = db.Column(db.String(64))
    comment = db.Column(db.Text)
    parent_version_id = db.Column(db.Integer)


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


# ---------------- Helpers ----------------
def current_user():
    name = session.get("username")
    if not name:
        return None
    return User.query.filter_by(username=name).first()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return jsonify({"ok": False, "error": "未登录"}), 401
        return fn(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "username" not in session:
                return jsonify({"ok": False, "error": "未登录"}), 401
            u = current_user()
            if not u or u.role not in roles:
                return jsonify({"ok": False, "error": "权限不足"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return deco


def region_label(name):
    return REGION_LABELS.get(name, name)


def region_stats(region):
    files = File.query.join(Group).filter(Group.region_id == region.id).all()
    if not files:
        return {"progress": 0, "status": "Todo", "file_count": 0}
    accepted = sum(1 for f in files if f.status == "已验收")
    progress = int(100 * accepted / len(files))
    if accepted == len(files):
        status = "Done"
    elif any(f.status in ("已借出", "待验收", "已验收") for f in files):
        status = "In progress"
    else:
        status = "Todo"
    return {"progress": progress, "status": status, "file_count": len(files)}


def file_owner_name(file_obj):
    if not file_obj.checked_out_by:
        return None
    u = db.session.get(User, file_obj.checked_out_by)
    return u.username if u else None


def serialize_file(f):
    latest = (
        FileVersion.query.filter_by(file_id=f.id)
        .order_by(FileVersion.date.desc())
        .first()
    )
    return {
        "id": f.id,
        "name": f.name,
        "status": f.status,
        "group_id": f.group_id,
        "checked_out_by": f.checked_out_by,
        "checked_out_by_name": file_owner_name(f),
        "checked_out_at": f.checked_out_at.isoformat() if f.checked_out_at else None,
        "latest_version": latest.label if latest else None,
    }


def next_version_label(file_id):
    count = FileVersion.query.filter_by(file_id=file_id).count()
    return f"V{count + 1}"


def save_upload(storage, file_id):
    os.makedirs(os.path.join(UPLOAD_ROOT, str(file_id)), exist_ok=True)
    raw = storage.read()
    sha = hashlib.sha256(raw).hexdigest()
    fname = secure_filename(storage.filename or "upload.bin") or "upload.bin"
    stored = f"{sha[:12]}_{fname}"
    path = os.path.join(UPLOAD_ROOT, str(file_id), stored)
    with open(path, "wb") as fh:
        fh.write(raw)
    rel = os.path.relpath(path, STATIC_DIR).replace("\\", "/")
    return rel, fname, len(raw), sha


def seed_if_needed():
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", email="admin@example.com", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)

    extras = [
        ("approver", "approver@example.com", "approver", "approver123"),
        ("editor", "editor@example.com", "editor", "editor123"),
        ("viewer", "viewer@example.com", "viewer", "viewer123"),
    ]
    for username, email, role, password in extras:
        if not User.query.filter_by(username=username).first():
            u = User(username=username, email=email, role=role)
            u.set_password(password)
            db.session.add(u)

    project_specs = [
        ("项目 1", ["China", "EU", "FDA", "UK"]),
        ("项目 2", ["China", "EU"]),
        ("项目 3", ["China", "FDA"]),
    ]
    for pname, region_names in project_specs:
        p = Project.query.filter_by(name=pname).first()
        if not p:
            p = Project(name=pname)
            db.session.add(p)
            db.session.flush()
        for rname in region_names:
            r = Region.query.filter_by(name=rname, project_id=p.id).first()
            if not r:
                r = Region(name=rname, project=p)
                db.session.add(r)
                db.session.flush()
            for gname in ("占位条目 1", "占位条目 2"):
                if not Group.query.filter_by(name=gname, region_id=r.id).first():
                    db.session.add(Group(name=gname, region=r))
    db.session.flush()

    if not File.query.first():
        groups = Group.query.order_by(Group.id.asc()).all()
        for idx, g in enumerate(groups):
            created = []
            for n, fname in enumerate(("文件 A", "文件 B"), start=1):
                f = File(name=fname, group=g, status="草稿", doc_code=f"DOC-{g.id:02d}{n}")
                db.session.add(f)
                db.session.flush()
                v1 = FileVersion(
                    file=f,
                    label="V1",
                    author="admin",
                    rel_path=DEFAULT_VERSION_FILE,
                    original_filename="history.pdf",
                    comment="初始版本",
                )
                db.session.add(v1)
                db.session.flush()
                f.current_version_id = v1.id
                created.append(f)
            if idx == 0:
                fA = created[0]
                v2 = FileVersion(
                    file=fA,
                    label="V2",
                    author="editor",
                    rel_path=DEFAULT_VERSION_FILE,
                    original_filename="history.pdf",
                    comment="提交验收",
                    parent_version_id=fA.current_version_id,
                )
                db.session.add(v2)
                db.session.flush()
                fA.current_version_id = v2.id
                fA.status = "待验收"
                created[1].status = "待验收"
                db.session.add(AcceptanceTask(file=fA, owner="editor", status="待验收"))
                db.session.add(AcceptanceTask(file=created[1], owner="editor", status="待验收"))

    db.session.commit()


with app.app_context():
    db.create_all()
    seed_if_needed()


# ---------------- Auth pages ----------------
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


# ---------------- APIs ----------------
@app.get("/api/me")
def api_me():
    if "username" not in session:
        return jsonify({"ok": False, "user": None})
    u = current_user()
    role = u.role if u else session.get("role", "viewer")
    return jsonify({"ok": True, "user": {"username": session["username"], "role": role}})


@app.get("/api/projects")
@login_required
def api_projects():
    data = [{"id": p.id, "name": p.name} for p in Project.query.order_by(Project.id.asc()).all()]
    return jsonify({"ok": True, "projects": data})


@app.get("/api/regions")
@login_required
def api_regions():
    pid = request.args.get("project_id", type=int)
    q = Region.query
    if pid:
        q = q.filter_by(project_id=pid)
    regions = []
    for r in q.order_by(Region.id.asc()).all():
        stats = region_stats(r)
        regions.append({
            "id": r.id,
            "name": r.name,
            "label": region_label(r.name),
            "project_id": r.project_id,
            **stats,
        })
    return jsonify({"ok": True, "regions": regions})


@app.get("/api/groups")
@login_required
def api_groups():
    rid = request.args.get("region_id", type=int)
    q = Group.query.filter_by(region_id=rid) if rid else Group.query
    groups = []
    for g in q.order_by(Group.id.asc()).all():
        files = File.query.filter_by(group_id=g.id).all()
        groups.append({
            "id": g.id,
            "name": g.name,
            "region_id": g.region_id,
            "file_count": len(files),
            "accepted": sum(1 for f in files if f.status == "已验收"),
        })
    return jsonify({"ok": True, "groups": groups})


@app.get("/api/files")
@login_required
def api_files():
    gid = request.args.get("group_id", type=int)
    q = File.query.filter_by(group_id=gid) if gid else File.query
    return jsonify({"ok": True, "files": [serialize_file(f) for f in q.order_by(File.id.asc()).all()]})


@app.post("/api/files/checkout")
@role_required("editor", "approver", "admin")
def api_checkout():
    data = request.get_json() or {}
    fid = data.get("file_id")
    user = current_user()
    f = db.session.get(File, fid)
    if not f:
        return jsonify({"ok": False, "error": "文件不存在"}), 404
    if f.checked_out_by:
        return jsonify({"ok": False, "error": "文件已被借出"}), 400
    f.checked_out_by = user.id
    f.checked_out_at = dt.datetime.utcnow()
    f.status = "已借出"
    db.session.add(AuditLog(user=user.username, action="checkout", target=f.name, detail=""))
    db.session.commit()
    return jsonify({"ok": True, "file": serialize_file(f)})


@app.post("/api/files/upload")
@role_required("editor", "approver", "admin")
def api_upload():
    gid = request.form.get("group_id", type=int)
    storage = request.files.get("file")
    if not gid:
        return jsonify({"ok": False, "error": "缺少分组"}), 400
    if not storage or not storage.filename:
        return jsonify({"ok": False, "error": "请选择文件"}), 400
    group = db.session.get(Group, gid)
    if not group:
        return jsonify({"ok": False, "error": "分组不存在"}), 404
    user = current_user()
    name = (request.form.get("name") or "").strip() or storage.filename
    comment = request.form.get("comment") or "首次上传"
    f = File(name=name, group=group, status="草稿")
    db.session.add(f)
    db.session.flush()
    rel, fname, size, sha = save_upload(storage, f.id)
    v = FileVersion(
        file=f,
        label="V1",
        author=user.username,
        rel_path=rel,
        original_filename=fname,
        size_bytes=size,
        sha256=sha,
        comment=comment,
    )
    db.session.add(v)
    db.session.flush()
    f.current_version_id = v.id
    db.session.add(AuditLog(user=user.username, action="upload", target=f.name, detail=fname))
    db.session.commit()
    return jsonify({"ok": True, "file": serialize_file(f)})


@app.post("/api/files/checkin")
@role_required("editor", "approver", "admin")
def api_checkin():
    is_multipart = request.content_type and "multipart" in request.content_type
    if is_multipart:
        fid = request.form.get("file_id", type=int)
        comment = request.form.get("comment") or "Check in"
        label = request.form.get("label")
        storage = request.files.get("file")
    else:
        data = request.get_json() or {}
        fid = data.get("file_id")
        comment = data.get("comment") or "Check in"
        label = data.get("label")
        storage = None
    user = current_user()
    f = db.session.get(File, fid)
    if not f:
        return jsonify({"ok": False, "error": "文件不存在"}), 404
    if f.checked_out_by and f.checked_out_by != user.id and user.role != "admin":
        return jsonify({"ok": False, "error": "只能由借出人或管理员归还"}), 403

    parent_id = f.current_version_id
    if storage and storage.filename:
        rel, fname, size, sha = save_upload(storage, f.id)
    else:
        rel, fname, size, sha = DEFAULT_VERSION_FILE, "history.pdf", 0, None
    v = FileVersion(
        file=f,
        label=label or next_version_label(f.id),
        author=user.username,
        rel_path=rel,
        comment=comment,
        parent_version_id=parent_id,
        original_filename=fname,
        size_bytes=size,
        sha256=sha,
    )
    db.session.add(v)
    db.session.flush()
    f.current_version_id = v.id
    f.checked_out_by = None
    f.checked_out_at = None
    f.status = "待验收"
    existing = AcceptanceTask.query.filter_by(file_id=f.id, status="待验收").first()
    if not existing:
        db.session.add(AcceptanceTask(file=f, owner=user.username, status="待验收"))
    db.session.add(AuditLog(user=user.username, action="checkin", target=f.name, detail=v.label))
    db.session.commit()
    return jsonify({"ok": True, "file": serialize_file(f)})


@app.get("/api/files/trace")
@login_required
def api_trace():
    fid = request.args.get("file_id", type=int)
    f = db.session.get(File, fid)
    if not f:
        return jsonify({"ok": False, "error": "文件不存在"}), 404
    versions = FileVersion.query.filter_by(file_id=fid).order_by(FileVersion.date.asc()).all()
    logs = AuditLog.query.filter_by(target=f.name).order_by(AuditLog.created_at.desc()).all()
    return jsonify({
        "ok": True,
        "file": serialize_file(f),
        "versions": [
            {
                "id": v.id,
                "label": v.label,
                "date": v.date.strftime("%Y-%m-%d %H:%M") if v.date else "",
                "author": v.author,
                "comment": v.comment,
                "sha256": v.sha256,
                "original_filename": v.original_filename,
            }
            for v in versions
        ],
        "audit": [
            {
                "id": a.id,
                "user": a.user,
                "action": a.action,
                "detail": a.detail,
                "created_at": a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "",
            }
            for a in logs
        ],
    })


@app.get("/api/files/versions")
@login_required
def api_versions():
    fid = request.args.get("file_id", type=int)
    q = FileVersion.query.filter_by(file_id=fid).order_by(FileVersion.date.desc())
    return jsonify({"ok": True, "versions": [
        {
            "id": v.id,
            "label": v.label,
            "date": v.date.strftime("%Y-%m-%d") if v.date else "",
            "author": v.author,
            "rel_path": v.rel_path,
            "comment": v.comment,
        }
        for v in q.all()
    ]})


@app.get("/versions/download")
def versions_download():
    if "username" not in session:
        return redirect(url_for("login"))
    vid = request.args.get("version_id", type=int)
    fid = request.args.get("file_id", type=int)
    v = None
    if vid:
        v = db.session.get(FileVersion, vid)
    elif fid:
        v = FileVersion.query.filter_by(file_id=fid).order_by(FileVersion.date.desc()).first()
    rel = v.rel_path if v and v.rel_path else DEFAULT_VERSION_FILE
    path = os.path.join(STATIC_DIR, rel)
    if not os.path.exists(path):
        path = os.path.join(STATIC_DIR, DEFAULT_VERSION_FILE)
    directory, filename = os.path.split(path)
    if not os.path.exists(path):
        return jsonify({"ok": False, "error": "文件不存在"}), 404
    return send_from_directory(directory, filename, as_attachment=False)


@app.get("/api/acceptance")
@login_required
def api_acceptance_list():
    tasks = AcceptanceTask.query.filter_by(status="待验收").order_by(AcceptanceTask.created_at.desc()).all()
    out = []
    for t in tasks:
        out.append({
            "id": t.id,
            "file_id": t.file_id,
            "name": t.file.name,
            "owner": t.owner,
            "date": t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
            "status": t.status,
        })
    return jsonify({"ok": True, "items": out})


@app.post("/api/acceptance/approve")
@role_required("approver", "admin")
def api_accept_approve():
    data = request.get_json() or {}
    tid = data.get("task_id")
    user = current_user()
    t = db.session.get(AcceptanceTask, tid)
    if not t:
        return jsonify({"ok": False, "error": "任务不存在"}), 404
    t.status = "已验收"
    t.file.status = "已验收"
    detail = data.get("role") or data.get("comment") or f"task={tid}"
    db.session.add(AuditLog(user=user.username, action="accept", target=t.file.name, detail=detail))
    db.session.commit()
    return jsonify({"ok": True})


@app.post("/api/acceptance/reject")
@role_required("approver", "admin")
def api_accept_reject():
    data = request.get_json() or {}
    tid = data.get("task_id")
    reason = data.get("reason", "")
    user = current_user()
    t = db.session.get(AcceptanceTask, tid)
    if not t:
        return jsonify({"ok": False, "error": "任务不存在"}), 404
    t.status = "已拒绝"
    t.file.status = "已拒绝"
    db.session.add(AuditLog(user=user.username, action="reject", target=t.file.name, detail=reason))
    db.session.commit()
    return jsonify({"ok": True})


# -------------- run --------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=True)
