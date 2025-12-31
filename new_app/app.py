
import os, datetime as dt
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------- Config ----------------
BASE_DIR   = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "new_web", "templates"))
STATIC_DIR   = os.path.abspath(os.path.join(BASE_DIR, "..", "static"))

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR, static_url_path="/static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR,'app.db')}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# ---------------- Models ----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email    = db.Column(db.String(120), unique=True, nullable=False)
    pwd_hash = db.Column(db.String(255), nullable=False)
    role     = db.Column(db.String(20), default="approver")  # viewer/editor/approver/admin
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)

    def set_password(self, pw): self.pwd_hash = generate_password_hash(pw)
    def check_password(self, pw): return check_password_hash(self.pwd_hash, pw)

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
    name = db.Column(db.String(120), nullable=False)  # 占位条目 1...
    region_id = db.Column(db.Integer, db.ForeignKey("region.id"), nullable=False)
    region = db.relationship(Region, backref=db.backref("groups", lazy=True))

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)     # 文件 A/B/C...
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    group = db.relationship(Group, backref=db.backref("files", lazy=True))
    status = db.Column(db.String(32), default="草稿")     # 草稿/已借出/已验收/已拒绝...
    checked_out_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    checked_out_at = db.Column(db.DateTime)

class FileVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey("file.id"), nullable=False)
    file = db.relationship(File, backref=db.backref("versions", lazy=True))
    label = db.Column(db.String(32), nullable=False)     # V1 / V2 / V2.1...
    date  = db.Column(db.DateTime, default=dt.datetime.utcnow)
    author = db.Column(db.String(64))
    # 真实文件相对路径（位于 new_web/static/versions 下）
    rel_path = db.Column(db.String(255), default="versions/sample.pdf")

class AcceptanceTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey("file.id"), nullable=False)
    file = db.relationship(File, backref=db.backref("accept_tasks", lazy=True))
    owner = db.Column(db.String(64))
    status = db.Column(db.String(32), default="待验收")  # 待验收/已验收/已拒绝
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(64))
    action = db.Column(db.String(64))      # checkout/checkin/accept/reject/rollback/diff
    target = db.Column(db.String(128))     # 作用对象，如 文件A 或 版本V2
    detail = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
# ---- 初始化数据库 & 种子数据（放在模型定义之后）----
with app.app_context():
    db.create_all()
    if not User.query.first():
        admin = User(
            username="admin",
            email="admin@example.com",   # 必填：模型要求非空且唯一
            role="admin"
        )
        admin.set_password("admin123")   # 正确：写入 pwd_hash
        db.session.add(admin)
        db.session.commit()

# ---------------- Seed (first run) ----------------
# @app.before_first_request
# def seed():
#     db.create_all()
#     if not User.query.first():
#         u1 = User(username="admin", email="admin@example.com", role="admin"); u1.set_password("admin123")
#         u2 = User(username="approver", email="a@example.com", role="approver"); u2.set_password("pass12345!")
#         db.session.add_all([u1,u2])
#         p = Project(name="项目 1"); db.session.add(p)
#         r_cn = Region(name="China", project=p); r_eu = Region(name="EU", project=p); db.session.add_all([r_cn,r_eu])
#         g1 = Group(name="占位条目 1", region=r_cn); g2 = Group(name="占位条目 2", region=r_cn); db.session.add_all([g1,g2])
#         fA = File(name="文件 A", group=g1); fB = File(name="文件 B", group=g1); db.session.add_all([fA,fB])
#         v1 = FileVersion(file=fA, label="V1", author="User1"); v2 = FileVersion(file=fA, label="V2", author="User2")
#         db.session.add_all([v1,v2])
#         t1 = AcceptanceTask(file=fA, owner="owner1"); t2 = AcceptanceTask(file=fB, owner="owner2")
#         db.session.add_all([t1,t2])
#         db.session.commit()

# ---------------- Auth pages ----------------
@app.route("/")
def home():
    if "username" in session:
        return redirect(url_for("main"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        u = User.query.filter((User.username==username)|(User.email==username)).first()
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
    # 你的 v6 页面改名为 main.html，若仍用旧文件名可改这里
    return render_template("main.html", username=session["username"])

# ---------------- APIs for frontend ----------------
def require_login():
    if "username" not in session: abort(401)

@app.get("/api/me")
def api_me():
    if "username" not in session:
        return jsonify({"ok": False, "user": None})
    return jsonify({"ok": True, "user": {"username": session["username"], "role": session.get("role","viewer")}})

@app.get("/api/projects")
def api_projects():
    require_login()
    data = []
    for p in Project.query.all():
        data.append({"id": p.id, "name": p.name})
    return jsonify({"ok": True, "projects": data})

@app.get("/api/regions")
def api_regions():
    require_login()
    pid = request.args.get("project_id", type=int)
    q = Region.query
    if pid: q = q.filter_by(project_id=pid)
    return jsonify({"ok": True, "regions": [{"id":r.id,"name":r.name,"project_id":r.project_id} for r in q.all()]})

@app.get("/api/groups")
def api_groups():
    require_login()
    rid = request.args.get("region_id", type=int)
    q = Group.query.filter_by(region_id=rid) if rid else Group.query
    return jsonify({"ok": True, "groups": [{"id":g.id,"name":g.name} for g in q.all()]})

@app.get("/api/files")
def api_files():
    require_login()
    gid = request.args.get("group_id", type=int)
    q = File.query.filter_by(group_id=gid) if gid else File.query
    res=[]
    for f in q.all():
        res.append({
            "id": f.id, "name": f.name, "status": f.status,
            "checked_out_by": f.checked_out_by, "checked_out_at": f.checked_out_at.isoformat() if f.checked_out_at else None
        })
    return jsonify({"ok": True, "files": res})

@app.post("/api/files/checkout")
def api_checkout():
    require_login()
    data = request.get_json() or {}
    fid = data.get("file_id")
    user = session["username"]
    f = File.query.get_or_404(fid)
    if f.checked_out_by:
        return jsonify({"ok": False, "error": "文件已被借出"})
    f.checked_out_by = User.query.filter_by(username=user).first().id
    f.checked_out_at = dt.datetime.utcnow()
    f.status = "已借出"
    db.session.add(AuditLog(user=user, action="checkout", target=f.name, detail=""))
    db.session.commit()
    return jsonify({"ok": True})

@app.post("/api/files/checkin")
def api_checkin():
    require_login()
    data = request.get_json() or {}
    fid = data.get("file_id")
    user = session["username"]
    f = File.query.get_or_404(fid)
    f.checked_out_by = None
    f.checked_out_at = None
    f.status = "草稿"
    db.session.add(AuditLog(user=user, action="checkin", target=f.name, detail=""))
    db.session.commit()
    return jsonify({"ok": True})

@app.get("/api/files/versions")
def api_versions():
    require_login()
    fid = request.args.get("file_id", type=int)
    q = FileVersion.query.filter_by(file_id=fid).order_by(FileVersion.date.desc())
    return jsonify({"ok": True, "versions": [
        {"id":v.id,"label":v.label,"date":v.date.strftime("%Y-%m-%d"),"author":v.author,"rel_path":v.rel_path} for v in q.all()
    ]})

@app.get("/versions/download")
def versions_download():
    # file version download, fallback to sample.pdf
    vid = request.args.get("version_id", type=int)
    v = FileVersion.query.get(vid) if vid else None
    rel = v.rel_path if v else "versions/sample.pdf"
    path = os.path.join(STATIC_DIR, rel)
    directory, filename = os.path.split(path)
    if not os.path.exists(path):
        directory, filename = os.path.join(STATIC_DIR, "versions"), "sample.pdf"
    return send_from_directory(directory, filename, as_attachment=False)

@app.get("/api/acceptance")
def api_acceptance_list():
    require_login()
    tasks = AcceptanceTask.query.filter_by(status="待验收").all()
    out=[]
    for t in tasks:
        out.append({
            "id": t.id,
            "file_id": t.file_id,
            "name": t.file.name,
            "owner": t.owner,
            "date": t.created_at.strftime("%Y-%m-%d %H:%M")
        })
    return jsonify({"ok": True, "items": out})

@app.post("/api/acceptance/approve")
def api_accept_approve():
    require_login()
    data = request.get_json() or {}
    tid = data.get("task_id")
    user = session["username"]
    t = AcceptanceTask.query.get_or_404(tid)
    t.status = "已验收"
    t.file.status = "已验收"
    db.session.add(AuditLog(user=user, action="accept", target=t.file.name, detail=f"task={tid}"))
    db.session.commit()
    return jsonify({"ok": True})

@app.post("/api/acceptance/reject")
def api_accept_reject():
    require_login()
    data = request.get_json() or {}
    tid = data.get("task_id"); reason = data.get("reason","")
    user = session["username"]
    t = AcceptanceTask.query.get_or_404(tid)
    t.status = "已拒绝"
    t.file.status = "已拒绝"
    db.session.add(AuditLog(user=user, action="reject", target=t.file.name, detail=reason))
    db.session.commit()
    return jsonify({"ok": True})

# -------------- run --------------
if __name__ == "__main__":
    app.run(debug=True)
