import pytest


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


def test_project_accepts_long_description(auth_client):
    long_description = "y" * 2000
    resp = auth_client.post(
        "/projects", json={"name": "Projeto descricao longa", "description": long_description}
    )
    assert resp.status_code == 201
    assert resp.json()["description"] == long_description


def _create_projects(client, count):
    return [client.post("/projects", json={"name": f"Projeto {i:02d}"}).json()["id"] for i in range(count)]


def test_list_projects_pagination_format_and_totals(auth_client):
    _create_projects(auth_client, 25)

    first_page = auth_client.get("/projects?page=1&page_size=10").json()
    assert set(first_page) == {"items", "page", "page_size", "total", "total_pages"}
    assert first_page["page"] == 1
    assert first_page["page_size"] == 10
    assert first_page["total"] == 25
    assert first_page["total_pages"] == 3
    assert len(first_page["items"]) == 10

    last_page = auth_client.get("/projects?page=3&page_size=10").json()
    assert len(last_page["items"]) == 5

    beyond_last_page = auth_client.get("/projects?page=4&page_size=10").json()
    assert beyond_last_page["items"] == []
    assert beyond_last_page["total"] == 25


def test_list_projects_empty(auth_client):
    data = auth_client.get("/projects").json()
    assert data == {"items": [], "page": 1, "page_size": 20, "total": 0, "total_pages": 0}


def test_list_projects_only_returns_own_projects(auth_client, second_auth_client):
    _create_projects(auth_client, 3)
    second_auth_client.post("/projects", json={"name": "Projeto do outro usuario"})

    data = auth_client.get("/projects").json()
    assert data["total"] == 3
    assert all(project["name"].startswith("Projeto ") for project in data["items"])
    assert "Projeto do outro usuario" not in [project["name"] for project in data["items"]]


def test_list_projects_pages_do_not_overlap_or_skip(auth_client):
    created_ids = _create_projects(auth_client, 7)

    seen_ids = []
    for page in range(1, 5):  # 7 projetos, 2 por página -> 4 páginas
        data = auth_client.get(f"/projects?page_size=2&page={page}").json()
        seen_ids.extend(project["id"] for project in data["items"])

    assert len(seen_ids) == 7
    assert set(seen_ids) == set(created_ids)


@pytest.mark.parametrize("query", ["page=0", "page=-1", "page=abc", "page_size=0", "page_size=101"])
def test_list_projects_rejects_invalid_pagination_params(auth_client, query):
    resp = auth_client.get(f"/projects?{query}")
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"


def test_list_projects_accepts_page_size_boundaries(auth_client):
    _create_projects(auth_client, 3)

    assert auth_client.get("/projects?page_size=1").json()["total_pages"] == 3
    assert auth_client.get("/projects?page_size=100").json()["total_pages"] == 1
