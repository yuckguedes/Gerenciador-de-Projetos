import pytest


@pytest.fixture
def project_id(auth_client):
    resp = auth_client.post("/projects", json={"name": "Projeto com tarefas"})
    return resp.json()["id"]


def test_create_task_valid(auth_client, project_id):
    resp = auth_client.post(
        f"/projects/{project_id}/tasks",
        json={
            "title": "Tarefa válida",
            "priority": "high",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"  # valor default


def test_create_task_invalid(auth_client, project_id):
    resp = auth_client.post(
        f"/projects/{project_id}/tasks",
        json={
            "title": "ab",  # menor que o mínimo de 3 caracteres
            "priority": "high",
        },
    )
    assert resp.status_code == 422


def test_partial_update_task(auth_client, project_id):
    create_resp = auth_client.post(
        f"/projects/{project_id}/tasks",
        json={
            "title": "Tarefa original",
            "priority": "low",
        },
    )
    task_id = create_resp.json()["id"]
    version = create_resp.json()["version"]

    update_resp = auth_client.patch(f"/tasks/{task_id}", json={"status": "in_progress", "version": version})
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "in_progress"
    assert update_resp.json()["title"] == "Tarefa original"  # não deve ter mudado
    assert update_resp.json()["version"] == version + 1


def test_update_task_with_stale_version_returns_409(auth_client, project_id):
    create_resp = auth_client.post(
        f"/projects/{project_id}/tasks",
        json={
            "title": "Tarefa concorrente",
            "priority": "low",
        },
    )
    task_id = create_resp.json()["id"]
    version = create_resp.json()["version"]

    first_update = auth_client.patch(f"/tasks/{task_id}", json={"status": "in_progress", "version": version})
    assert first_update.status_code == 200

    stale_update = auth_client.patch(f"/tasks/{task_id}", json={"status": "completed", "version": version})
    assert stale_update.status_code == 409
    assert stale_update.json()["detail"]["code"] == "VERSION_CONFLICT"


def test_pagination_and_filters(auth_client, project_id):
    for i in range(15):
        auth_client.post(
            f"/projects/{project_id}/tasks",
            json={
                "title": f"Tarefa {i}",
                "priority": "high" if i % 2 == 0 else "low",
            },
        )

    resp = auth_client.get(f"/projects/{project_id}/tasks?priority=high&page=1&page_size=5")
    data = resp.json()
    assert resp.status_code == 200
    assert data["total"] == 8  # índices 0,2,4,6,8,10,12,14
    assert len(data["items"]) == 5
    assert data["page"] == 1


def test_cursor_pagination_covers_all_items_without_overlap(auth_client, project_id):
    created_ids = []
    for i in range(12):
        resp = auth_client.post(
            f"/projects/{project_id}/tasks",
            json={
                "title": f"Tarefa cursor {i}",
                "priority": "low",
            },
        )
        created_ids.append(resp.json()["id"])

    seen_ids = []
    cursor = None
    pages = 0
    while True:
        url = f"/projects/{project_id}/tasks/cursor?limit=5"
        if cursor:
            url += f"&cursor={cursor}"
        resp = auth_client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        seen_ids.extend(item["id"] for item in data["items"])
        pages += 1
        if not data["has_more"]:
            assert data["next_cursor"] is None
            break
        cursor = data["next_cursor"]
        assert pages < 10  # guarda contra loop infinito em caso de bug

    assert pages == 3  # 12 itens, limit 5 -> 5 + 5 + 2
    assert sorted(seen_ids) == sorted(created_ids)  # sem repetição, sem lacuna
    assert len(seen_ids) == len(set(seen_ids))  # nenhum id duplicado


def test_cursor_pagination_invalid_cursor(auth_client, project_id):
    resp = auth_client.get(f"/projects/{project_id}/tasks/cursor?cursor=isto-nao-e-um-cursor-valido")
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "INVALID_CURSOR"


def test_delete_project_cascades_tasks(auth_client, project_id):
    create_resp = auth_client.post(
        f"/projects/{project_id}/tasks",
        json={
            "title": "Tarefa que vai sumir",
            "priority": "medium",
        },
    )
    task_id = create_resp.json()["id"]

    delete_resp = auth_client.delete(f"/projects/{project_id}")
    assert delete_resp.status_code == 204

    get_task_resp = auth_client.get(f"/tasks/{task_id}")
    assert get_task_resp.status_code == 404


def test_partial_update_task_without_version_still_works(auth_client, project_id):
    create_resp = auth_client.post(
        f"/projects/{project_id}/tasks",
        json={"title": "Tarefa sem versão", "priority": "low"},
    )
    task_id = create_resp.json()["id"]

    update_resp = auth_client.patch(f"/tasks/{task_id}", json={"status": "in_progress"})
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "in_progress"
    assert update_resp.json()["title"] == "Tarefa sem versão"
