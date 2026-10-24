from fastapi.testclient import TestClient

from backend.main import app


def test_the_backend_says_it_is_up():
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"healthy": True}
