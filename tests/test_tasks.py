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


def test_combined_filters_ordering_and_pagination(auth_client, project_id):
    tasks = [
        ("Relatorio mensal", "high", "pending"),
        ("Relatorio anual", "high", "in_progress"),
        ("Relatorio semanal", "high", "in_progress"),
        ("Relatorio diario", "low", "in_progress"),
        ("Reuniao de equipe", "high", "in_progress"),
    ]
    for title, priority, task_status in tasks:
        created = auth_client.post(
            f"/projects/{project_id}/tasks", json={"title": title, "priority": priority}
        ).json()
        if task_status != "pending":
            auth_client.patch(f"/tasks/{created['id']}", json={"status": task_status})

    base_url = (
        f"/projects/{project_id}/tasks"
        "?status=in_progress&priority=high&search=RELATORIO&order_by=title&direction=asc&page_size=1"
    )

    first_page = auth_client.get(f"{base_url}&page=1").json()
    assert first_page["total"] == 2  # só "anual" e "semanal" atendem aos três filtros ao mesmo tempo
    assert first_page["total_pages"] == 2
    assert [task["title"] for task in first_page["items"]] == ["Relatorio anual"]

    second_page = auth_client.get(f"{base_url}&page=2").json()
    assert [task["title"] for task in second_page["items"]] == ["Relatorio semanal"]

    descending = auth_client.get(base_url.replace("direction=asc", "direction=desc") + "&page=1").json()
    assert [task["title"] for task in descending["items"]] == ["Relatorio semanal"]


def test_partial_update_task_accepts_past_due_date(auth_client, project_id):
    # o enunciado só proíbe due_date no passado "no momento do cadastro", não em atualizações
    create_resp = auth_client.post(
        f"/projects/{project_id}/tasks", json={"title": "Tarefa com prazo", "priority": "low"}
    )
    task_id = create_resp.json()["id"]

    update_resp = auth_client.patch(f"/tasks/{task_id}", json={"due_date": "2020-01-01T00:00:00"})
    assert update_resp.status_code == 200
    assert update_resp.json()["due_date"].startswith("2020-01-01")


def test_create_task_with_past_due_date_is_rejected(auth_client, project_id):
    resp = auth_client.post(
        f"/projects/{project_id}/tasks",
        json={"title": "Tarefa atrasada", "priority": "low", "due_date": "2020-01-01T00:00:00"},
    )
    assert resp.status_code == 422


def test_task_accepts_long_description(auth_client, project_id):
    long_description = "x" * 2000
    resp = auth_client.post(
        f"/projects/{project_id}/tasks",
        json={"title": "Descricao longa", "priority": "low", "description": long_description},
    )
    assert resp.status_code == 201
    assert resp.json()["description"] == long_description


def test_search_treats_like_wildcards_literally(auth_client, project_id):
    for title in ["Meta 100% concluida", "Meta_interna", "Outra tarefa"]:
        auth_client.post(f"/projects/{project_id}/tasks", json={"title": title, "priority": "low"})

    percent = auth_client.get(f"/projects/{project_id}/tasks?search=%25").json()
    assert [task["title"] for task in percent["items"]] == ["Meta 100% concluida"]

    underscore = auth_client.get(f"/projects/{project_id}/tasks?search=_").json()
    assert [task["title"] for task in underscore["items"]] == ["Meta_interna"]


def test_offset_pagination_is_stable_when_sort_values_tie(auth_client, project_id):
    created_ids = set()
    for i in range(7):
        resp = auth_client.post(
            f"/projects/{project_id}/tasks", json={"title": f"Empate {i}", "priority": "medium"}
        )
        created_ids.add(resp.json()["id"])

    seen_ids = []
    for page in range(1, 5):  # 7 itens com a mesma prioridade, 2 por página -> 4 páginas
        data = auth_client.get(
            f"/projects/{project_id}/tasks?order_by=priority&page_size=2&page={page}"
        ).json()
        seen_ids.extend(task["id"] for task in data["items"])

    assert len(seen_ids) == 7
    assert set(seen_ids) == created_ids  # sem repetição e sem lacuna entre as páginas


@pytest.mark.parametrize("query", ["page=0", "page=-1", "page=abc", "page_size=0", "page_size=101"])
def test_list_tasks_rejects_invalid_pagination_params(auth_client, project_id, query):
    resp = auth_client.get(f"/projects/{project_id}/tasks?{query}")
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"


def test_list_tasks_accepts_page_size_boundaries_and_empty_list(auth_client, project_id):
    empty = auth_client.get(f"/projects/{project_id}/tasks").json()
    assert empty == {"items": [], "page": 1, "page_size": 20, "total": 0, "total_pages": 0}

    for i in range(3):
        auth_client.post(f"/projects/{project_id}/tasks", json={"title": f"Tarefa {i}", "priority": "low"})

    assert auth_client.get(f"/projects/{project_id}/tasks?page_size=1").json()["total_pages"] == 3
    assert auth_client.get(f"/projects/{project_id}/tasks?page_size=100").json()["total_pages"] == 1
