def test_create_project(auth_client):
    resp = auth_client.post("/projects", json={"name": "Projeto Teste", "description": "desc"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Projeto Teste"


def test_access_other_user_project_forbidden(auth_client, second_auth_client):
    resp = auth_client.post("/projects", json={"name": "Projeto Privado"})
    project_id = resp.json()["id"]

    resp2 = second_auth_client.get(f"/projects/{project_id}")
    assert resp2.status_code == 403


def test_update_project_increments_version(auth_client):
    create_resp = auth_client.post("/projects", json={"name": "Projeto Original"})
    project_id = create_resp.json()["id"]
    version = create_resp.json()["version"]
    assert version == 1

    update_resp = auth_client.put(
        f"/projects/{project_id}", json={"name": "Projeto Renomeado", "version": version}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Projeto Renomeado"
    assert update_resp.json()["version"] == version + 1


def test_update_project_with_stale_version_returns_409(auth_client):
    create_resp = auth_client.post("/projects", json={"name": "Projeto Concorrente"})
    project_id = create_resp.json()["id"]
    version = create_resp.json()["version"]

    first_update = auth_client.put(
        f"/projects/{project_id}", json={"name": "Primeira edição", "version": version}
    )
    assert first_update.status_code == 200

    stale_update = auth_client.put(
        f"/projects/{project_id}", json={"name": "Edição desatualizada", "version": version}
    )
    assert stale_update.status_code == 409
    assert stale_update.json()["detail"]["code"] == "VERSION_CONFLICT"


def test_update_project_without_version_still_works(auth_client):
    create_resp = auth_client.post("/projects", json={"name": "Projeto sem versão"})
    project_id = create_resp.json()["id"]

    update_resp = auth_client.put(f"/projects/{project_id}", json={"name": "Renomeado sem versão"})
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Renomeado sem versão"
    assert update_resp.json()["version"] == 2
