from fastapi.testclient import TestClient

from app.main import app


def test_health():
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unexpected_error_hides_stack_trace(caplog):
    from fastapi import FastAPI

    from app.core.errors import register_error_handlers

    broken = FastAPI()
    register_error_handlers(broken)

    @broken.get("/boom")
    def boom():
        raise RuntimeError("segredo interno")

    response = TestClient(broken, raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "segredo interno" not in response.text
    assert "segredo interno" in caplog.text
