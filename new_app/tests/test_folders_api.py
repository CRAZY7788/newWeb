from tests.conftest import unique_name


def test_create_folder(login, client, any_folder):
    login("editor")
    parent = any_folder
    name = unique_name("fld")
    r = client.post(
        "/api/folders",
        json={"name": name, "region_id": parent.region_id, "parent_id": parent.id},
    )
    assert r.status_code == 200
    assert r.get_json()["folder"]["name"] == name


def test_duplicate_folder_name_sibling(login, client, any_folder):
    login("editor")
    name = unique_name("fld-dup")
    payload = {"name": name, "region_id": any_folder.region_id, "parent_id": any_folder.parent_id}
    assert client.post("/api/folders", json=payload).status_code == 200
    r2 = client.post("/api/folders", json=payload)
    assert r2.status_code == 400
    assert "同名" in r2.get_json()["error"]
