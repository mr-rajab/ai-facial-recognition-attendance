import sys

import pytest

pytest.importorskip("httpx")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import init_db

    monkeypatch.setattr(init_db, "DB_PATH", str(tmp_path / "portal_test.sqlite"))
    monkeypatch.setenv("SECRET_KEY", "test-secret-for-web-tests-twenty-chars")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@test.edu")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "demo-admin-pass")
    sys.modules.pop("web_app", None)
    import web_app
    from fastapi.testclient import TestClient

    with TestClient(web_app.app) as c:
        yield c


def test_login_page_ok(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert "Attendance Portal" in r.text


def test_quick_attendance_page_public(client):
    r = client.get("/quick-attendance")
    assert r.status_code == 200
    assert "Quick attendance" in r.text


def test_login_redirects_admin_to_dashboard(client):
    r = client.post(
        "/login",
        data={"email": "admin@test.edu", "password": "demo-admin-pass"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers.get("location") == "/admin"


def test_root_requires_login(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers.get("location") == "/login"


def test_login_rejects_bad_password(client):
    r = client.post(
        "/login",
        data={"email": "admin@test.edu", "password": "wrong"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers.get("location") == "/login?error=1"
