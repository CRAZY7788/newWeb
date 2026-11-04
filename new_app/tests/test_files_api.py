import io

from app import FILE_STATUS_DRAFT, FILE_STATUS_PENDING
from tests.conftest import unique_name


def test_create_txt_file(login, client, any_folder):
    login("editor")
    name = unique_name("create")
    r = client.post(
        "/api/files/create",
        json={"folder_id": any_folder.id, "type": "txt", "name": name, "comment": "hello"},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["file"]["status"] == FILE_STATUS_DRAFT
    assert body["file"]["name"] == f"{name}.txt"


def test_create_rejects_duplicate_name(login, client, any_folder):
    login("admin")
    base = unique_name("dup")
    payload = {"folder_id": any_folder.id, "type": "txt", "name": base, "comment": ""}
    assert client.post("/api/files/create", json=payload).status_code == 200
    r2 = client.post("/api/files/create", json=payload)
    assert r2.status_code == 400
    assert "同名" in r2.get_json()["error"]


def test_patch_rename(login, client, any_folder):
    login("editor")
    name = unique_name("ren")
    created = client.post(
        "/api/files/create",
        json={"folder_id": any_folder.id, "type": "txt", "name": name, "comment": ""},
    ).get_json()["file"]
    new_title = unique_name("renamed")
    r = client.patch(
        f"/api/files/{created['id']}",
        json={"name": new_title},
    )
    assert r.status_code == 200
    assert r.get_json()["file"]["name"] == f"{new_title}.txt"


def test_checkin_requires_checkout(login, client, any_folder):
    login("editor")
    name = unique_name("ci")
    fid = client.post(
        "/api/files/create",
        json={"folder_id": any_folder.id, "type": "txt", "name": name, "comment": ""},
    ).get_json()["file"]["id"]
    r = client.post(
        "/api/files/checkin",
        data={
            "file_id": str(fid),
            "comment": "skip checkout",
            "file": (io.BytesIO(b"x"), f"{name}.txt"),
        },
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert "Check out" in r.get_json()["error"]
