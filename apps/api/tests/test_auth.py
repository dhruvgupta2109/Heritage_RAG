from fastapi.testclient import TestClient

from app.main import APP_SESSION_COOKIE, app


def test_app_password_protects_api_and_creates_one_shared_session() -> None:
    with TestClient(app) as client:
        protected = client.get("/api/chats")
        assert protected.status_code == 401

        rejected = client.post("/api/auth/login", json={"password": "incorrect"})
        assert rejected.status_code == 401
        assert APP_SESSION_COOKIE not in rejected.cookies

        accepted = client.post("/api/auth/login", json={"password": "Password"})
        assert accepted.status_code == 200
        assert accepted.json()["authenticated"] is True
        assert accepted.cookies.get(APP_SESSION_COOKIE)

        session = client.get("/api/auth/session")
        assert session.status_code == 200
        assert session.json()["authenticated"] is True

        chats = client.get("/api/chats")
        assert chats.status_code == 200

        uploads = client.get("/api/uploads/session")
        assert uploads.status_code == 200
        assert uploads.json()["unlocked"] is True

        logout = client.post("/api/auth/logout")
        assert logout.status_code == 204
        assert client.get("/api/chats").status_code == 401
