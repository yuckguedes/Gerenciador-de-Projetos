from sqlalchemy.exc import OperationalError
from app.main import app
from app.api.dependencies import get_db


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_database_unreachable(client):
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    def broken_get_db():
        yield BrokenSession()

    original_override = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = broken_get_db
    try:
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json() == {"status": "error", "database": "unreachable"}
    finally:
        app.dependency_overrides[get_db] = original_override
