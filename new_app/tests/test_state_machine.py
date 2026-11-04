import io

from app import (
    FILE_STATUS_CHECKED_OUT,
    FILE_STATUS_PENDING,
    AcceptanceTask,
)
from tests.conftest import unique_name


def _create_txt(login, client, folder_id, name=None):
    login("editor")
    name = name or unique_name("flow")
    r = client.post(
        "/api/files/create",
        json={"folder_id": folder_id, "type": "txt", "name": name, "comment": "v1"},
    )
    assert r.status_code == 200
    return r.get_json()["file"]


def test_checkout_checkin_acceptance(login, client, any_folder):
    created = _create_txt(login, client, any_folder.id)
    fid = created["id"]
    login("editor")
    r = client.post("/api/files/checkout", json={"file_id": fid})
    assert r.status_code == 200
    assert r.get_json()["file"]["status"] == FILE_STATUS_CHECKED_OUT

    r = client.post(
        "/api/files/checkin",
        data={
            "file_id": str(fid),
            "comment": "v2",
            "file": (io.BytesIO(b"version two"), f"{created['name']}"),
        },
        content_type="multipart/form-data",
    )
    assert r.status_code == 200
    assert r.get_json()["file"]["status"] == FILE_STATUS_PENDING

    login("editor")
    r = client.post("/api/files/checkout", json={"file_id": fid})
    assert r.status_code == 400

    login("approver")
    tasks = client.get("/api/acceptance").get_json()["items"]
    task = next(t for t in tasks if t["file_id"] == fid)
    r = client.post("/api/acceptance/approve", json={"task_id": task["id"]})
    assert r.status_code == 200

    login("editor")
    r = client.post("/api/files/checkout", json={"file_id": fid})
    assert r.status_code == 200
    assert r.get_json()["file"]["status"] == FILE_STATUS_CHECKED_OUT


def test_void_hides_from_folder_list(login, client, any_folder, app_ctx):
    created = _create_txt(login, client, any_folder.id)
    fid = created["id"]
    login("approver")
    assert client.post(f"/api/files/{fid}/void", json={}).status_code == 200

    login("admin")
    listed = client.get(f"/api/files?folder_id={any_folder.id}").get_json()["files"]
    assert all(f["id"] != fid for f in listed)


def test_void_clears_pending_task(login, client, any_folder, app_ctx):
    created = _create_txt(login, client, any_folder.id)
    fid = created["id"]
    login("editor")
    client.post("/api/files/checkout", json={"file_id": fid})
    client.post(
        "/api/files/checkin",
        data={
            "file_id": str(fid),
            "comment": "pending",
            "file": (io.BytesIO(b"v2"), "x.txt"),
        },
        content_type="multipart/form-data",
    )
    login("approver")
    client.post(f"/api/files/{fid}/void", json={})
    pending = AcceptanceTask.query.filter_by(file_id=fid, status=FILE_STATUS_PENDING).count()
    assert pending == 0
