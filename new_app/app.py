
import os
import hashlib
import datetime as dt
import zipfile
from functools import wraps
from io import BytesIO

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import inspect, text, or_, and_
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
BLANK_TEMPLATE_DIR = os.path.join(STATIC_DIR, "templates")
FOLDER_MAX_DEPTH = 3

CREATE_KINDS = {
    "word": {"ext": ".docx", "template": "blank.docx", "file_type": "word"},
    "excel": {"ext": ".xlsx", "template": "blank.xlsx", "file_type": "excel"},
    "txt": {"ext": ".txt", "template": "blank.txt", "file_type": "txt"},
}

ALLOWED_FILE_TYPES = ("word", "excel", "txt", "zip", "other")
EXT_TO_FILE_TYPE = {
    ".docx": "word",
    ".xlsx": "excel",
    ".txt": "txt",
    ".zip": "zip",
}
EXT_TO_MIME = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain",
    ".zip": "application/zip",
}
ALLOWED_UPLOAD_EXTENSIONS = frozenset(EXT_TO_FILE_TYPE.keys())
FILE_TYPE_LABELS = {
    "word": "Word",
    "excel": "Excel",
    "txt": "文本",
    "zip": "Zip",
    "other": "其他",
}

REGION_LABELS = {
    "China": "China · NMPA",
    "EU": "EU · MDR",
    "FDA": "US · FDA",
    "UK": "UK · MHRA",
}

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR, static_url_path="/static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
_db_uri = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}")
if _db_uri.startswith("sqlite:///") and not _db_uri.startswith("sqlite:////"):
    _rest = _db_uri[len("sqlite:///"):]
    if _rest and not os.path.isabs(_rest):
        _db_uri = "sqlite:///" + os.path.join(BASE_DIR, _rest)
app.config["SQLALCHEMY_DATABASE_URI"] = _db_uri
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
    """Legacy placeholder groups; migrated to Folder. Kept for old DB rows."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    region_id = db.Column(db.Integer, db.ForeignKey("region.id"), nullable=False)
    region = db.relationship(Region, backref=db.backref("groups", lazy=True))


class Folder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("folder.id"), nullable=True)
    region_id = db.Column(db.Integer, db.ForeignKey("region.id"), nullable=False)
    created_by = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
    region = db.relationship(Region, backref=db.backref("folders", lazy=True))
    parent = db.relationship("Folder", remote_side=[id], backref=db.backref("children", lazy=True))


class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(200))
    file_type = db.Column(db.String(20), default="other")
    mime = db.Column(db.String(128))
    folder_id = db.Column(db.Integer, db.ForeignKey("folder.id"), nullable=True)
    folder = db.relationship(Folder, backref=db.backref("files", lazy=True))
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=True)
    group = db.relationship(Group, backref=db.backref("files_legacy", lazy=True))
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
    target_type = db.Column(db.String(32))  # folder | file
    target_id = db.Column(db.Integer)
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


def infer_file_type(filename):
    if not filename:
        return "other", None
    ext = os.path.splitext(filename.lower())[1]
    ftype = EXT_TO_FILE_TYPE.get(ext, "other")
    mime = EXT_TO_MIME.get(ext)
    return ftype, mime


def validate_upload_filename(filename):
    ext = os.path.splitext((filename or "").lower())[1]
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return False, "仅支持 Word（.docx）、Excel（.xlsx）、文本（.txt）、压缩包（.zip）"
    return True, None


def log_audit(user, action, target_type, target_id, target_name, detail=""):
    db.session.add(AuditLog(
        user=user,
        action=action,
        target=target_name,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    ))


def _table_columns(table_name):
    rows = db.session.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def ensure_schema():
    db.create_all()
    file_cols = _table_columns("file")
    al_cols = _table_columns("audit_log")
    alters = []
    if "folder_id" not in file_cols:
        alters.append("ALTER TABLE file ADD COLUMN folder_id INTEGER REFERENCES folder(id)")
    if "title" not in file_cols:
        alters.append("ALTER TABLE file ADD COLUMN title VARCHAR(200)")
    if "file_type" not in file_cols:
        alters.append("ALTER TABLE file ADD COLUMN file_type VARCHAR(20)")
    if "mime" not in file_cols:
        alters.append("ALTER TABLE file ADD COLUMN mime VARCHAR(128)")
    if "target_type" not in al_cols:
        alters.append("ALTER TABLE audit_log ADD COLUMN target_type VARCHAR(32)")
    if "target_id" not in al_cols:
        alters.append("ALTER TABLE audit_log ADD COLUMN target_id INTEGER")
    for stmt in alters:
        db.session.execute(text(stmt))
    if alters:
        db.session.commit()


def migrate_groups_to_folders():
    """One-time: each legacy Group becomes a root Folder; files get folder_id."""
    insp = inspect(db.engine)
    if not insp.has_table("file") or not insp.has_table("folder"):
        return
    if File.query.filter(File.folder_id.is_(None)).count() == 0:
        return
    group_map = {}
    for g in Group.query.order_by(Group.id.asc()).all():
        folder = Folder.query.filter_by(
            name=g.name, region_id=g.region_id, parent_id=None
        ).first()
        if not folder:
            folder = Folder(name=g.name, region_id=g.region_id, parent_id=None, created_by="system")
            db.session.add(folder)
            db.session.flush()
        group_map[g.id] = folder.id
    for f in File.query.filter(File.folder_id.is_(None)).all():
        if f.group_id and f.group_id in group_map:
            f.folder_id = group_map[f.group_id]
        if not f.title:
            f.title = f.name
        if not f.file_type or f.file_type == "other":
            ver = FileVersion.query.filter_by(file_id=f.id).order_by(FileVersion.date.desc()).first()
            fname = ver.original_filename if ver and ver.original_filename else f.name
            ftype, mime = infer_file_type(fname)
            f.file_type = ftype
            f.mime = mime
    db.session.commit()


def region_stats(region):
    files = File.query.join(Folder).filter(Folder.region_id == region.id).all()
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
        "title": f.title or f.name,
        "file_type": f.file_type or "other",
        "mime": f.mime,
        "status": f.status,
        "folder_id": f.folder_id,
        "group_id": f.folder_id,
        "checked_out_by": f.checked_out_by,
        "checked_out_by_name": file_owner_name(f),
        "checked_out_at": f.checked_out_at.isoformat() if f.checked_out_at else None,
        "latest_version": latest.label if latest else None,
        "doc_code": f.doc_code,
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


def save_bytes(file_id, original_filename, raw):
    os.makedirs(os.path.join(UPLOAD_ROOT, str(file_id)), exist_ok=True)
    sha = hashlib.sha256(raw).hexdigest()
    fname = secure_filename(original_filename or "file.bin") or "file.bin"
    stored = f"{sha[:12]}_{fname}"
    path = os.path.join(UPLOAD_ROOT, str(file_id), stored)
    with open(path, "wb") as fh:
        fh.write(raw)
    rel = os.path.relpath(path, STATIC_DIR).replace("\\", "/")
    return rel, fname, len(raw), sha


def _write_minimal_docx(path):
    content_types = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    document = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t></w:t></w:r></w:p></w:body>
</w:document>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document)


def _write_minimal_xlsx(path):
    content_types = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""
    rels = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
    workbook = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
    wb_rels = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""
    sheet = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData/>
</worksheet>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet)


def ensure_blank_templates():
    os.makedirs(BLANK_TEMPLATE_DIR, exist_ok=True)
    txt_path = os.path.join(BLANK_TEMPLATE_DIR, "blank.txt")
    if not os.path.exists(txt_path):
        with open(txt_path, "w", encoding="utf-8") as fh:
            fh.write("")
    docx_path = os.path.join(BLANK_TEMPLATE_DIR, "blank.docx")
    if not os.path.exists(docx_path):
        _write_minimal_docx(docx_path)
    xlsx_path = os.path.join(BLANK_TEMPLATE_DIR, "blank.xlsx")
    if not os.path.exists(xlsx_path):
        _write_minimal_xlsx(xlsx_path)


def normalize_create_filename(name, kind):
    spec = CREATE_KINDS.get(kind)
    if not spec:
        return None, "不支持的文档类型"
    ext = spec["ext"]
    raw = (name or "").strip() or "未命名文档"
    base, cur_ext = os.path.splitext(raw)
    if not cur_ext:
        raw = raw + ext
    elif cur_ext.lower() != ext:
        raw = base + ext
    display = raw
    stored_name = secure_filename(raw) or f"doc{ext}"
    return display, stored_name


def template_bytes_for_kind(kind, comment=""):
    ensure_blank_templates()
    spec = CREATE_KINDS[kind]
    path = os.path.join(BLANK_TEMPLATE_DIR, spec["template"])
    if kind == "txt":
        text = (comment or "").strip()
        if not text:
            with open(path, "rb") as fh:
                return fh.read()
        return text.encode("utf-8")
    with open(path, "rb") as fh:
        return fh.read()


def serialize_folder(folder):
    files = File.query.filter_by(folder_id=folder.id).all()
    child_count = Folder.query.filter_by(parent_id=folder.id).count()
    return {
        "id": folder.id,
        "name": folder.name,
        "parent_id": folder.parent_id,
        "region_id": folder.region_id,
        "depth": folder_level(folder),
        "file_count": len(files),
        "child_count": child_count,
        "accepted": sum(1 for f in files if f.status == "已验收"),
        "created_at": folder.created_at.isoformat() if folder.created_at else None,
        "created_by": folder.created_by,
    }


def folder_level(folder):
    level = 1
    current = folder
    while current.parent_id:
        level += 1
        current = db.session.get(Folder, current.parent_id)
        if not current:
            break
    return level


def folder_name_taken(name, region_id, parent_id):
    q = Folder.query.filter_by(name=name, region_id=region_id)
    if parent_id is None:
        q = q.filter(Folder.parent_id.is_(None))
    else:
        q = q.filter_by(parent_id=parent_id)
    return q.first() is not None


def folder_is_empty(folder_id):
    if File.query.filter_by(folder_id=folder_id).count():
        return False
    if Folder.query.filter_by(parent_id=folder_id).count():
        return False
    return True


def folder_ancestors(folder):
    chain = []
    current = folder
    while current:
        chain.append(current)
        current = db.session.get(Folder, current.parent_id) if current.parent_id else None
    chain.reverse()
    return chain


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
            for fname in ("设计文档", "质量记录"):
                if not Folder.query.filter_by(name=fname, region_id=r.id, parent_id=None).first():
                    db.session.add(Folder(
                        name=fname, region_id=r.id, parent_id=None, created_by="admin"
                    ))
    db.session.flush()

    if not File.query.first():
        folders = Folder.query.order_by(Folder.id.asc()).all()
        for idx, folder in enumerate(folders):
            created = []
            for n, doc_name in enumerate(("文件 A", "文件 B"), start=1):
                ftype, mime = infer_file_type("history.pdf")
                f = File(
                    name=doc_name,
                    title=doc_name,
                    file_type=ftype,
                    mime=mime,
                    folder=folder,
                    status="草稿",
                    doc_code=f"DOC-{folder.id:02d}{n}",
                )
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
    ensure_schema()
    ensure_blank_templates()
    migrate_groups_to_folders()
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
    """Deprecated: use /api/folders. Returns root-level folders as legacy «groups»."""
    rid = request.args.get("region_id", type=int)
    q = Folder.query.filter(Folder.parent_id.is_(None))
    if rid:
        q = q.filter_by(region_id=rid)
    groups = []
    for folder in q.order_by(Folder.id.asc()).all():
        s = serialize_folder(folder)
        groups.append({
            "id": s["id"],
            "name": s["name"],
            "region_id": s["region_id"],
            "file_count": s["file_count"],
            "accepted": s["accepted"],
        })
    return jsonify({"ok": True, "groups": groups, "deprecated": "use /api/folders"})


@app.get("/api/folders")
@login_required
def api_folders():
    rid = request.args.get("region_id", type=int)
    parent_raw = request.args.get("parent_id")
    q = Folder.query
    if rid:
        q = q.filter_by(region_id=rid)
    if parent_raw is None:
        q = q.filter(Folder.parent_id.is_(None))
    elif parent_raw in ("", "null", "none"):
        q = q.filter(Folder.parent_id.is_(None))
    else:
        q = q.filter_by(parent_id=int(parent_raw))
    folders = [serialize_folder(f) for f in q.order_by(Folder.id.asc()).all()]
    return jsonify({"ok": True, "folders": folders})


@app.get("/api/folders/<int:folder_id>")
@login_required
def api_folder_detail(folder_id):
    folder = db.session.get(Folder, folder_id)
    if not folder:
        return jsonify({"ok": False, "error": "文件夹不存在"}), 404
    path = [serialize_folder(f) for f in folder_ancestors(folder)]
    return jsonify({"ok": True, "folder": serialize_folder(folder), "path": path})


@app.post("/api/folders")
@role_required("editor", "approver", "admin")
def api_folders_create():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    region_id = data.get("region_id")
    parent_id = data.get("parent_id")
    if parent_id in ("", "null", "none"):
        parent_id = None
    if not name:
        return jsonify({"ok": False, "error": "名称不能为空"}), 400
    if not region_id:
        return jsonify({"ok": False, "error": "缺少地区"}), 400
    region = db.session.get(Region, region_id)
    if not region:
        return jsonify({"ok": False, "error": "地区不存在"}), 404
    parent = None
    if parent_id is not None:
        parent_id = int(parent_id)
        parent = db.session.get(Folder, parent_id)
        if not parent:
            return jsonify({"ok": False, "error": "父文件夹不存在"}), 404
        if parent.region_id != region_id:
            return jsonify({"ok": False, "error": "父文件夹不在同一地区"}), 400
        if folder_level(parent) >= FOLDER_MAX_DEPTH:
            return jsonify({"ok": False, "error": f"文件夹层级不能超过 {FOLDER_MAX_DEPTH} 层"}), 400
    if folder_name_taken(name, region_id, parent_id):
        return jsonify({"ok": False, "error": "同级目录下已有同名文件夹"}), 400
    user = current_user()
    folder = Folder(
        name=name,
        region_id=region_id,
        parent_id=parent_id,
        created_by=user.username if user else None,
    )
    db.session.add(folder)
    db.session.flush()
    log_audit(user.username, "folder_create", "folder", folder.id, folder.name, "")
    db.session.commit()
    return jsonify({"ok": True, "folder": serialize_folder(folder)})


@app.patch("/api/folders/<int:folder_id>")
@role_required("editor", "approver", "admin")
def api_folders_rename(folder_id):
    folder = db.session.get(Folder, folder_id)
    if not folder:
        return jsonify({"ok": False, "error": "文件夹不存在"}), 404
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "名称不能为空"}), 400
    if name != folder.name and folder_name_taken(name, folder.region_id, folder.parent_id):
        return jsonify({"ok": False, "error": "同级目录下已有同名文件夹"}), 400
    old = folder.name
    folder.name = name
    user = current_user()
    log_audit(user.username, "folder_rename", "folder", folder.id, folder.name, old)
    db.session.commit()
    return jsonify({"ok": True, "folder": serialize_folder(folder)})


@app.delete("/api/folders/<int:folder_id>")
@role_required("editor", "approver", "admin")
def api_folders_delete(folder_id):
    folder = db.session.get(Folder, folder_id)
    if not folder:
        return jsonify({"ok": False, "error": "文件夹不存在"}), 404
    if not folder_is_empty(folder_id):
        return jsonify({"ok": False, "error": "文件夹非空，无法删除"}), 400
    user = current_user()
    name = folder.name
    db.session.delete(folder)
    log_audit(user.username, "folder_delete", "folder", folder_id, name, "")
    db.session.commit()
    return jsonify({"ok": True})


@app.get("/api/files")
@login_required
def api_files():
    folder_id = request.args.get("folder_id", type=int)
    gid = request.args.get("group_id", type=int)
    fid = folder_id or gid
    q = File.query
    if fid:
        folder = db.session.get(Folder, fid)
        if not folder:
            return jsonify({"ok": False, "error": "文件夹不存在"}), 404
        q = q.filter_by(folder_id=fid)
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
    log_audit(user.username, "checkout", "file", f.id, f.name, "")
    db.session.commit()
    return jsonify({"ok": True, "file": serialize_file(f)})


@app.post("/api/files/upload")
@role_required("editor", "approver", "admin")
def api_upload():
    gid = request.form.get("folder_id", type=int) or request.form.get("group_id", type=int)
    storage = request.files.get("file")
    if not gid:
        return jsonify({"ok": False, "error": "缺少文件夹"}), 400
    if not storage or not storage.filename:
        return jsonify({"ok": False, "error": "请选择文件"}), 400
    ok, err = validate_upload_filename(storage.filename)
    if not ok:
        return jsonify({"ok": False, "error": err}), 400
    folder = db.session.get(Folder, gid)
    if not folder:
        return jsonify({"ok": False, "error": "文件夹不存在"}), 404
    user = current_user()
    name = (request.form.get("name") or "").strip() or storage.filename
    comment = request.form.get("comment") or "首次上传"
    ftype, mime = infer_file_type(storage.filename)
    f = File(
        name=name,
        title=name,
        file_type=ftype,
        mime=mime,
        folder=folder,
        group_id=folder.id,
        status="草稿",
    )
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
    log_audit(user.username, "upload", "file", f.id, f.name, fname)
    db.session.commit()
    return jsonify({"ok": True, "file": serialize_file(f)})


@app.post("/api/files/create")
@role_required("editor", "approver", "admin")
def api_files_create():
    data = request.get_json() or {}
    folder_id = data.get("folder_id")
    kind = (data.get("type") or "").strip().lower()
    name = data.get("name")
    comment = (data.get("comment") or "").strip()
    if kind not in CREATE_KINDS:
        return jsonify({"ok": False, "error": "类型须为 word、excel 或 txt"}), 400
    if not folder_id:
        return jsonify({"ok": False, "error": "缺少文件夹"}), 400
    folder = db.session.get(Folder, folder_id)
    if not folder:
        return jsonify({"ok": False, "error": "文件夹不存在"}), 404
    display_name, stored_fname = normalize_create_filename(name, kind)
    if display_name is None:
        return jsonify({"ok": False, "error": stored_fname}), 400
    user = current_user()
    ftype, mime = infer_file_type(stored_fname)
    f = File(
        name=display_name,
        title=display_name,
        file_type=ftype,
        mime=mime,
        folder=folder,
        group_id=folder.id,
        status="草稿",
    )
    db.session.add(f)
    db.session.flush()
    raw = template_bytes_for_kind(kind, comment)
    rel, fname, size, sha = save_bytes(f.id, stored_fname, raw)
    v = FileVersion(
        file=f,
        label="V1",
        author=user.username,
        rel_path=rel,
        original_filename=fname,
        size_bytes=size,
        sha256=sha,
        comment=comment or "新建文档",
    )
    db.session.add(v)
    db.session.flush()
    f.current_version_id = v.id
    log_audit(user.username, "create", "file", f.id, f.name, kind)
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
        if not storage or not storage.filename:
            return jsonify({"ok": False, "error": "请上传新版本文件"}), 400
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
        ok, err = validate_upload_filename(storage.filename)
        if not ok:
            return jsonify({"ok": False, "error": err}), 400
        rel, fname, size, sha = save_upload(storage, f.id)
        ftype, mime = infer_file_type(fname)
        f.file_type = ftype
        f.mime = mime
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
    log_audit(user.username, "checkin", "file", f.id, f.name, v.label)
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
    logs = (
        AuditLog.query.filter(
            or_(
                and_(AuditLog.target_type == "file", AuditLog.target_id == fid),
                and_(AuditLog.target_type.is_(None), AuditLog.target == f.name),
            )
        )
        .order_by(AuditLog.created_at.desc())
        .all()
    )
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
    log_audit(user.username, "accept", "file", t.file_id, t.file.name, detail)
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
    log_audit(user.username, "reject", "file", t.file_id, t.file.name, reason)
    db.session.commit()
    return jsonify({"ok": True})


# -------------- run --------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=True)
