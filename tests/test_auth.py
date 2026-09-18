def test_register_user(client):
    resp = client.post("/auth/register", json={
        "name": "Fulano",
        "email": "fulano@teste.com",
        "password": "senha12345",
    })
    assert resp.status_code == 201
    assert "password_hash" not in resp.json()
    assert resp.json()["email"] == "fulano@teste.com"


def test_register_duplicate_email(client):
    payload = {"name": "Fulano", "email": "dup@teste.com", "password": "senha12345"}
    client.post("/auth/register", json=payload)
    resp = client.post("/auth/register", json=payload)
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "EMAIL_ALREADY_REGISTERED"


def test_login_valid_credentials(client):
    client.post("/auth/register", json={
        "name": "Fulano", "email": "login@teste.com", "password": "senha12345",
    })
    resp = client.post("/auth/login", json={
        "email": "login@teste.com", "password": "senha12345",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert resp.json()["token_type"] == "bearer"


def test_login_invalid_credentials(client):
    resp = client.post("/auth/login", json={
        "email": "naoexiste@teste.com", "password": "errada",
    })
    assert resp.status_code == 401


def test_protected_route_without_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401  # ou 403, dependendo de como o HTTPBearer se comporta sem header


def test_login_returns_refresh_token(client):
    client.post("/auth/register", json={
        "name": "Fulano", "email": "refresh1@teste.com", "password": "senha12345",
    })
    resp = client.post("/auth/login", json={
        "email": "refresh1@teste.com", "password": "senha12345",
    })
    assert resp.status_code == 200
    assert "refresh_token" in resp.json()


def test_refresh_rotates_token(client):
    client.post("/auth/register", json={
        "name": "Fulano", "email": "refresh2@teste.com", "password": "senha12345",
    })
    login_resp = client.post("/auth/login", json={
        "email": "refresh2@teste.com", "password": "senha12345",
    })
    old_refresh_token = login_resp.json()["refresh_token"]

    refresh_resp = client.post("/auth/refresh", json={"refresh_token": old_refresh_token})
    assert refresh_resp.status_code == 200
    new_refresh_token = refresh_resp.json()["refresh_token"]
    assert new_refresh_token != old_refresh_token


def test_refresh_reuse_detection_revokes_chain(client):
    client.post("/auth/register", json={
        "name": "Fulano", "email": "refresh3@teste.com", "password": "senha12345",
    })
    login_resp = client.post("/auth/login", json={
        "email": "refresh3@teste.com", "password": "senha12345",
    })
    old_refresh_token = login_resp.json()["refresh_token"]

    refresh_resp = client.post("/auth/refresh", json={"refresh_token": old_refresh_token})
    new_refresh_token = refresh_resp.json()["refresh_token"]

    # reusar o token antigo (já rotacionado) deve falhar...
    reuse_resp = client.post("/auth/refresh", json={"refresh_token": old_refresh_token})
    assert reuse_resp.status_code == 401
    assert reuse_resp.json()["detail"]["code"] == "INVALID_REFRESH_TOKEN"

    # ...e revogar em cascata o token novo, mesmo sendo legítimo (contenção de roubo)
    legit_reuse_resp = client.post("/auth/refresh", json={"refresh_token": new_refresh_token})
    assert legit_reuse_resp.status_code == 401


def test_logout_revokes_refresh_token(client):
    client.post("/auth/register", json={
        "name": "Fulano", "email": "refresh4@teste.com", "password": "senha12345",
    })
    login_resp = client.post("/auth/login", json={
        "email": "refresh4@teste.com", "password": "senha12345",
    })
    refresh_token = login_resp.json()["refresh_token"]

    logout_resp = client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert logout_resp.status_code == 204

    refresh_resp = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 401
