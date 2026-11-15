from app import (
    PROJECT_KIND_PRODUCT,
    PROJECT_KIND_QMS,
    QMS_PROJECT_NAME,
    QMS_REGION_NAME,
    QMS_ROOT_FOLDERS,
    Folder,
    Project,
    Region,
)
from tests.conftest import unique_name


def test_product_projects_exclude_qms(login, client):
    login("viewer")
    r = client.get("/api/projects")
    assert r.status_code == 200
    names = [p["name"] for p in r.get_json()["projects"]]
    kinds = {p["kind"] for p in r.get_json()["projects"]}
    assert QMS_PROJECT_NAME not in names
    assert kinds <= {PROJECT_KIND_PRODUCT}


def test_qms_root_is_company_library(login, client, app_ctx):
    login("viewer")
    r = client.get("/api/qms")
    assert r.status_code == 200
    body = r.get_json()
    assert body["project"]["kind"] == PROJECT_KIND_QMS
    assert body["project"]["name"] == QMS_PROJECT_NAME
    assert body["region"]["name"] == QMS_REGION_NAME
    folder_names = [f["name"] for f in body["folders"]]
    for name in QMS_ROOT_FOLDERS:
        assert name in folder_names
    assert "设计文档" not in folder_names
    assert "质量记录" not in folder_names


def test_qms_not_inside_product_china(login, client, app_ctx):
    login("viewer")
    product = Project.query.filter_by(kind=PROJECT_KIND_PRODUCT, name="项目 1").first()
    china = Region.query.filter_by(project_id=product.id, name="China").first()
    qms = Project.query.filter_by(kind=PROJECT_KIND_QMS).first()
    qms_region = Region.query.filter_by(project_id=qms.id).first()
    assert china.id != qms_region.id
    china_roots = [
        f.name for f in Folder.query.filter_by(region_id=china.id, parent_id=None).all()
    ]
    assert "程序文件" not in china_roots
    assert "质量记录" in china_roots


def test_qms_create_file_uses_same_control(login, client, app_ctx):
    login("editor")
    qms = client.get("/api/qms").get_json()
    sop_folder = next(f for f in qms["folders"] if f["name"] == "程序文件")
    name = unique_name("sop")
    r = client.post(
        "/api/files/create",
        json={"folder_id": sop_folder["id"], "type": "txt", "name": name, "comment": ""},
    )
    assert r.status_code == 200
    file_id = r.get_json()["file"]["id"]
    listed = client.get(f"/api/files?folder_id={sop_folder['id']}").get_json()["files"]
    assert any(f["id"] == file_id for f in listed)
    product_files = client.get("/api/search?q=" + name + "&kind=product").get_json()["files"]
    qms_files = client.get("/api/search?q=" + name + "&kind=qms").get_json()["files"]
    assert product_files == []
    assert any(name in f["name"] for f in qms_files)
