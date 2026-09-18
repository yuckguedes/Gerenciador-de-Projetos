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
