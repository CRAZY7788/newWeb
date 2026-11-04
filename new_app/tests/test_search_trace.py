from tests.conftest import unique_name


def test_search_by_name(login, client, any_folder):
    login("admin")
    name = unique_name("searchme")
    client.post(
        "/api/files/create",
        json={"folder_id": any_folder.id, "type": "txt", "name": name, "comment": ""},
    )
    r = client.get(f"/api/search?q={name}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert any(name in f["name"] for f in body["files"])


def test_trace_by_file_id(login, client, any_folder):
    login("admin")
    name = unique_name("trace")
    created = client.post(
        "/api/files/create",
        json={"folder_id": any_folder.id, "type": "txt", "name": name, "comment": "body"},
    ).get_json()["file"]
    r = client.get(f"/api/files/trace?file_id={created['id']}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["file"]["id"] == created["id"]
    assert body["location"]["folder_id"] == any_folder.id
    assert len(body["versions"]) >= 1
    assert body["versions"][-1]["is_current"] is True
    assert any(a["action"] == "create" for a in body["audit"])


def test_trace_requires_file_id(login, client):
    login("viewer")
    r = client.get("/api/files/trace")
    assert r.status_code == 400
