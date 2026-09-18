def test_create_project(auth_client):
    resp = auth_client.post("/projects", json={"name": "Projeto Teste", "description": "desc"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Projeto Teste"


def test_access_other_user_project_forbidden(auth_client, second_auth_client):
    resp = auth_client.post("/projects", json={"name": "Projeto Privado"})
    project_id = resp.json()["id"]

    resp2 = second_auth_client.get(f"/projects/{project_id}")
    assert resp2.status_code == 403
