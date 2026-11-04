from tests.conftest import unique_name


def test_viewer_cannot_create(login, client, any_folder):
    login("viewer")
    r = client.post(
        "/api/files/create",
        json={"folder_id": any_folder.id, "type": "txt", "name": unique_name("v"), "comment": ""},
    )
    assert r.status_code == 403


def test_viewer_can_list_files(login, client, any_folder):
    login("viewer")
    r = client.get(f"/api/files?folder_id={any_folder.id}")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_editor_cannot_void(login, client, any_folder):
    login("admin")
    name = unique_name("voidperm")
    fid = client.post(
        "/api/files/create",
        json={"folder_id": any_folder.id, "type": "txt", "name": name, "comment": ""},
    ).get_json()["file"]["id"]
    login("editor")
    r = client.post(f"/api/files/{fid}/void", json={})
    assert r.status_code == 403


def test_admin_can_delete(login, client, any_folder):
    login("admin")
    name = unique_name("del")
    fid = client.post(
        "/api/files/create",
        json={"folder_id": any_folder.id, "type": "txt", "name": name, "comment": ""},
    ).get_json()["file"]["id"]
    r = client.delete(f"/api/files/{fid}")
    assert r.status_code == 200
    assert client.get(f"/api/files/trace?file_id={fid}").status_code == 404
