from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_check_reports_local_service_status() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "cipherstego-local",
        "processing": "sender_receiver_available",
    }


def test_existing_frontend_is_served_with_local_assets() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "CipherStego" in response.text
    assert "/styles.css" in response.text
    assert "/app.js" in response.text
    assert client.get("/styles.css").status_code == 200
    assert client.get("/app.js").status_code == 200


def test_legacy_python_source_is_not_served() -> None:
    assert client.get("/app.py").status_code == 404
    assert client.get("/crypto_engine.py").status_code == 404


def test_sender_and_receiver_require_valid_request_models() -> None:
    for path in ("/api/sender", "/api/embed", "/api/receiver", "/api/extract"):
        response = client.post(path, json={})
        assert response.status_code == 422, path
        assert response.json() == {"detail": "Format request tidak valid."}, path


def test_unimplemented_routes_remain_explicit_placeholders() -> None:
    paths = ["/api/inspect", "/api/tamper"]

    for path in paths:
        response = client.post(path)
        assert response.status_code == 501, path
        assert "belum tersedia" in response.json()["detail"].lower(), path
