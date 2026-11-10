from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import main
from app.main import app

client = TestClient(app)


def test_liveness() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_when_database_is_available(monkeypatch) -> None:
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _statement):
            return 1

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            pass

    monkeypatch.setattr(main, "create_database_engine", Engine)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_when_database_is_unavailable(monkeypatch) -> None:
    class Connection:
        def __enter__(self):
            raise OperationalError("connect", {}, RuntimeError("unavailable"))

        def __exit__(self, *_args):
            return False

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            pass

    monkeypatch.setattr(main, "create_database_engine", Engine)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
