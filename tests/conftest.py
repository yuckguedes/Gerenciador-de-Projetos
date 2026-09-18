from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from testcontainers.community.postgres import PostgresContainer

from alembic import command
from app.api.dependencies import get_db
from app.database import Base
from app.main import app

ROOT_DIR = Path(__file__).resolve().parent.parent

# Sobe um Postgres efêmero em container Docker automaticamente, só para esta
# sessão de testes. Não depende de nenhum serviço externo (como um `db_test`
# do docker-compose) já estar de pé — o próprio testcontainers gerencia o
# ciclo de vida do container (start aqui, stop no fixture de sessão abaixo).
postgres_container = PostgresContainer("postgres:16")
postgres_container.start()

TEST_DATABASE_URL = postgres_container.get_connection_url()

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def _stop_postgres_container():
    yield
    postgres_container.stop()


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations():
    # o schema dos testes vem das migrations reais do Alembic (as mesmas do `docker compose up`),
    # não de Base.metadata.create_all — assim uma migration quebrada ou faltando derruba os testes.
    alembic_config = Config(str(ROOT_DIR / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(ROOT_DIR / "alembic"))
    with engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, "head")


@pytest.fixture(scope="function", autouse=True)
def clean_database(_apply_migrations):
    yield
    table_names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_client(client):
    client.post(
        "/auth/register",
        json={
            "name": "Usuario Teste",
            "email": "usuario@teste.com",
            "password": "senha12345",
        },
    )
    resp = client.post(
        "/auth/login",
        json={
            "email": "usuario@teste.com",
            "password": "senha12345",
        },
    )
    token = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest.fixture
def second_auth_client(client):
    # cliente separado simulando um segundo usuário, pra testar isolamento entre usuários
    from fastapi.testclient import TestClient as TC

    second_client = TC(app)
    second_client.post(
        "/auth/register",
        json={
            "name": "Outro Usuario",
            "email": "outro@teste.com",
            "password": "senha12345",
        },
    )
    resp = second_client.post(
        "/auth/login",
        json={
            "email": "outro@teste.com",
            "password": "senha12345",
        },
    )
    token = resp.json()["access_token"]
    second_client.headers.update({"Authorization": f"Bearer {token}"})
    return second_client
