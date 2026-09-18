import pytest


@pytest.fixture
def project_id(auth_client):
    resp = auth_client.post("/projects", json={"name": "Projeto com tarefas"})
    return resp.json()["id"]


def test_create_task_valid(auth_client, project_id):
    resp = auth_client.post(f"/projects/{project_id}/tasks", json={
        "title": "Tarefa válida",
        "priority": "high",
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"  # valor default


def test_create_task_invalid(auth_client, project_id):
    resp = auth_client.post(f"/projects/{project_id}/tasks", json={
        "title": "ab",  # menor que o mínimo de 3 caracteres
        "priority": "high",
    })
    assert resp.status_code == 422


def test_partial_update_task(auth_client, project_id):
    create_resp = auth_client.post(f"/projects/{project_id}/tasks", json={
        "title": "Tarefa original",
        "priority": "low",
    })
    task_id = create_resp.json()["id"]

    update_resp = auth_client.patch(f"/tasks/{task_id}", json={"status": "in_progress"})
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "in_progress"
    assert update_resp.json()["title"] == "Tarefa original"  # não deve ter mudado


def test_pagination_and_filters(auth_client, project_id):
    for i in range(15):
        auth_client.post(f"/projects/{project_id}/tasks", json={
            "title": f"Tarefa {i}",
            "priority": "high" if i % 2 == 0 else "low",
        })

    resp = auth_client.get(f"/projects/{project_id}/tasks?priority=high&page=1&page_size=5")
    data = resp.json()
    assert resp.status_code == 200
    assert data["total"] == 8  # índices 0,2,4,6,8,10,12,14
    assert len(data["items"]) == 5
    assert data["page"] == 1


def test_delete_project_cascades_tasks(auth_client, project_id):
    create_resp = auth_client.post(f"/projects/{project_id}/tasks", json={
        "title": "Tarefa que vai sumir",
        "priority": "medium",
    })
    task_id = create_resp.json()["id"]

    delete_resp = auth_client.delete(f"/projects/{project_id}")
    assert delete_resp.status_code == 204

    get_task_resp = auth_client.get(f"/tasks/{task_id}")
    assert get_task_resp.status_code == 404
