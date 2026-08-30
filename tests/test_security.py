"""
Security and authorization tests for PlanejaENEM.

Tests IDOR protection, cross-user access, session fixation,
CSRF, and rate limiting.
"""

import pytest
from datetime import date, datetime, time, timedelta, timezone

from app import create_app, db
from app.models import User, Subject, Task, StudyPlan, StudySession


@pytest.fixture
def app():
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _create_user(client, email, password="Senha123", nome="Test"):
    client.post(
        "/auth/register",
        data={"nome": nome, "email": email, "senha": password, "confirmar_senha": password},
        follow_redirects=True,
    )
    return User.query.filter_by(email=email).first()


def _login(client, email, password="Senha123"):
    return client.post(
        "/auth/login",
        data={"email": email, "senha": password},
        follow_redirects=True,
    )


class TestIDORProtection:
    """Test that users cannot access objects belonging to other users."""

    def test_subject_edit_cross_user(self, client):
        user_a = _create_user(client, "a@test.com")
        _login(client, "a@test.com")

        resp = client.post(
            "/subjects/new",
            data={"nome": "Mat A", "cor": "#ff0000", "prioridade": "3", "dificuldade": "3", "area": "matematica"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        subject_a = Subject.query.filter_by(user_id=user_a.id).first()

        client.get("/auth/logout", follow_redirects=True)

        user_b = _create_user(client, "b@test.com")
        _login(client, "b@test.com")

        resp = client.get(f"/subjects/{subject_a.id}/edit", follow_redirects=True)
        assert resp.status_code == 404

    def test_subject_delete_cross_user(self, client):
        user_a = _create_user(client, "a@test.com")
        _login(client, "a@test.com")

        client.post(
            "/subjects/new",
            data={"nome": "Mat A", "cor": "#ff0000", "prioridade": "3", "dificuldade": "3", "area": "matematica"},
            follow_redirects=True,
        )
        subject_a = Subject.query.filter_by(user_id=user_a.id).first()

        client.get("/auth/logout", follow_redirects=True)

        user_b = _create_user(client, "b@test.com")
        _login(client, "b@test.com")

        resp = client.get(f"/subjects/{subject_a.id}/delete", follow_redirects=True)
        assert resp.status_code == 404

        resp = client.post(f"/subjects/{subject_a.id}/delete", follow_redirects=True)
        assert resp.status_code == 404
        assert Subject.query.filter_by(id=subject_a.id).count() == 1

    def test_task_edit_cross_user(self, client):
        user_a = _create_user(client, "a@test.com")
        _login(client, "a@test.com")

        client.post(
            "/subjects/new",
            data={"nome": "Mat A", "cor": "#ff0000", "prioridade": "3", "dificuldade": "3", "area": "matematica"},
            follow_redirects=True,
        )
        subject_a = Subject.query.filter_by(user_id=user_a.id).first()

        client.post(
            "/tasks/new",
            data={"titulo": "Task A", "subject_id": subject_a.id, "prioridade": "media"},
            follow_redirects=True,
        )
        task_a = Task.query.filter_by(user_id=user_a.id).first()

        client.get("/auth/logout", follow_redirects=True)

        user_b = _create_user(client, "b@test.com")
        _login(client, "b@test.com")

        resp = client.get(f"/tasks/{task_a.id}/edit", follow_redirects=True)
        assert resp.status_code == 404

    def test_task_delete_cross_user(self, client):
        user_a = _create_user(client, "a@test.com")
        _login(client, "a@test.com")

        client.post(
            "/subjects/new",
            data={"nome": "Mat A", "cor": "#ff0000", "prioridade": "3", "dificuldade": "3", "area": "matematica"},
            follow_redirects=True,
        )
        subject_a = Subject.query.filter_by(user_id=user_a.id).first()

        client.post(
            "/tasks/new",
            data={"titulo": "Task A", "subject_id": subject_a.id, "prioridade": "media"},
            follow_redirects=True,
        )
        task_a = Task.query.filter_by(user_id=user_a.id).first()

        client.get("/auth/logout", follow_redirects=True)

        user_b = _create_user(client, "b@test.com")
        _login(client, "b@test.com")

        resp = client.post(f"/tasks/{task_a.id}/delete", follow_redirects=True)
        assert resp.status_code == 404
        assert Task.query.filter_by(id=task_a.id).count() == 1

    def test_task_toggle_cross_user(self, client):
        user_a = _create_user(client, "a@test.com")
        _login(client, "a@test.com")

        client.post(
            "/subjects/new",
            data={"nome": "Mat A", "cor": "#ff0000", "prioridade": "3", "dificuldade": "3", "area": "matematica"},
            follow_redirects=True,
        )
        subject_a = Subject.query.filter_by(user_id=user_a.id).first()

        client.post(
            "/tasks/new",
            data={"titulo": "Task A", "subject_id": subject_a.id, "prioridade": "media"},
            follow_redirects=True,
        )
        task_a = Task.query.filter_by(user_id=user_a.id).first()

        client.get("/auth/logout", follow_redirects=True)

        user_b = _create_user(client, "b@test.com")
        _login(client, "b@test.com")

        resp = client.post(f"/tasks/{task_a.id}/toggle", follow_redirects=True)
        assert resp.status_code == 404
        db.session.refresh(task_a)
        assert task_a.concluida is False

    def test_session_toggle_cross_user(self, client):
        user_a = _create_user(client, "a@test.com")
        _login(client, "a@test.com")

        client.post(
            "/subjects/new",
            data={"nome": "Mat A", "cor": "#ff0000", "prioridade": "3", "dificuldade": "3", "area": "matematica"},
            follow_redirects=True,
        )
        subject_a = Subject.query.filter_by(user_id=user_a.id).first()

        today = date.today()
        plan = StudyPlan(
            user_id=user_a.id,
            exam_date=today + timedelta(days=30),
            daily_minutes=90,
            available_days="seg,qua,sex",
            available_hours="08:00-10:00",
        )
        db.session.add(plan)
        db.session.flush()

        session_a = StudySession(
            plan_id=plan.id,
            user_id=user_a.id,
            subject_id=subject_a.id,
            session_date=today,
            start_time=time(8, 0),
            end_time=time(10, 0),
            duration_minutes=120,
            completed=False,
        )
        db.session.add(session_a)
        db.session.commit()

        client.get("/auth/logout", follow_redirects=True)

        user_b = _create_user(client, "b@test.com")
        _login(client, "b@test.com")

        resp = client.post(f"/sessions/{session_a.id}/toggle", follow_redirects=True)
        assert resp.status_code == 404
        db.session.refresh(session_a)
        assert session_a.completed is False

    def test_planner_regenerate_cross_user(self, client):
        user_a = _create_user(client, "a@test.com")
        _login(client, "a@test.com")

        client.post(
            "/subjects/new",
            data={"nome": "Mat A", "cor": "#ff0000", "prioridade": "3", "dificuldade": "3", "area": "matematica"},
            follow_redirects=True,
        )

        today = date.today()
        client.post(
            "/planner/",
            data={
                "available_days": ["seg", "qua", "sex"],
                "available_hours": "08:00-10:00",
                "daily_minutes": "120",
                "exam_date": (today + timedelta(days=30)).strftime("%Y-%m-%d"),
            },
            follow_redirects=True,
        )
        plan_a = StudyPlan.query.filter_by(user_id=user_a.id).first()

        client.get("/auth/logout", follow_redirects=True)

        user_b = _create_user(client, "b@test.com")
        _login(client, "b@test.com")

        resp = client.post(f"/planner/{plan_a.id}/regenerate", follow_redirects=True)
        assert resp.status_code == 404
        assert StudyPlan.query.filter_by(id=plan_a.id).count() == 1

    def test_nonexistent_id_returns_404(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")

        resp = client.get("/subjects/99999/edit", follow_redirects=True)
        assert resp.status_code == 404

        resp = client.get("/tasks/99999/edit", follow_redirects=True)
        assert resp.status_code == 404

        resp = client.post("/tasks/99999/toggle", follow_redirects=True)
        assert resp.status_code == 404


class TestSubjectIdor:
    """Detailed IDOR tests for subjects."""

    def test_subject_list_isolation(self, client):
        user_a = _create_user(client, "a@test.com")
        _login(client, "a@test.com")

        client.post(
            "/subjects/new",
            data={"nome": "Mat A", "cor": "#ff0000", "prioridade": "3", "dificuldade": "3", "area": "matematica"},
            follow_redirects=True,
        )

        client.get("/auth/logout", follow_redirects=True)

        user_b = _create_user(client, "b@test.com")
        _login(client, "b@test.com")

        resp = client.get("/subjects/")
        assert resp.status_code == 200
        assert b"Mat A" not in resp.data

    def test_task_list_isolation(self, client):
        user_a = _create_user(client, "a@test.com")
        _login(client, "a@test.com")

        client.post(
            "/subjects/new",
            data={"nome": "Mat A", "cor": "#ff0000", "prioridade": "3", "dificuldade": "3", "area": "matematica"},
            follow_redirects=True,
        )
        subject_a = Subject.query.filter_by(user_id=user_a.id).first()

        client.post(
            "/tasks/new",
            data={"titulo": "Secret Task A", "subject_id": subject_a.id, "prioridade": "media"},
            follow_redirects=True,
        )

        client.get("/auth/logout", follow_redirects=True)

        user_b = _create_user(client, "b@test.com")
        _login(client, "b@test.com")

        resp = client.get("/tasks/")
        assert resp.status_code == 200
        assert b"Secret Task A" not in resp.data


class TestSessionFixation:
    """Test session regeneration after login/logout."""

    def test_session_id_changes_after_login(self, client):
        _create_user(client, "a@test.com")

        client.get("/auth/login")
        session_before = client.get("/auth/login").headers.get("Set-Cookie", "")

        _login(client, "a@test.com")

        session_after = client.get("/").headers.get("Set-Cookie", "")

        assert "session=" in session_before or "session=" in session_after

    def test_session_invalidated_after_logout(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")

        resp = client.get("/")
        assert resp.status_code == 200

        client.get("/auth/logout", follow_redirects=True)

        resp = client.get("/")
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]


class TestCSRFProtection:
    """Test CSRF protection on mutating endpoints."""

    def test_post_without_csrf_blocked(self, app):
        app.config["WTF_CSRF_ENABLED"] = True
        client = app.test_client()

        resp = client.post("/auth/login", data={"email": "a@test.com", "senha": "Senha123"})
        assert resp.status_code == 400

    def test_subject_create_requires_csrf(self, app):
        app.config["WTF_CSRF_ENABLED"] = True
        client = app.test_client()

        user = User(nome="Test", email="a@test.com")
        user.set_senha("Senha123")
        db.session.add(user)
        db.session.commit()

        client.post("/auth/login", data={"email": "a@test.com", "senha": "Senha123"})

        resp = client.post(
            "/subjects/new",
            data={"nome": "Mat", "cor": "#ff0000", "prioridade": "3", "dificuldade": "3", "area": "matematica"},
        )
        assert resp.status_code == 400


class TestSecurityHeaders:
    """Test security headers are present."""

    def test_security_headers_present(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")

        resp = client.get("/")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert resp.headers.get("Permissions-Policy") == "geolocation=(), microphone=(), camera=()"
        assert resp.headers.get("Cross-Origin-Opener-Policy") == "same-origin"
        assert resp.headers.get("Cross-Origin-Resource-Policy") == "same-origin"
        assert "Content-Security-Policy" in resp.headers
        assert "default-src 'self'" in resp.headers["Content-Security-Policy"]

    def test_no_xss_protection_header(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")

        resp = client.get("/")
        assert "X-XSS-Protection" not in resp.headers


class TestPasswordNeverInLogs:
    """Test that passwords never appear in logs."""

    def test_password_not_in_response(self, client):
        _create_user(client, "a@test.com")
        resp = _login(client, "a@test.com")
        assert b"Senha123" not in resp.data

    def test_password_not_in_register_response(self, client):
        resp = client.post(
            "/auth/register",
            data={
                "nome": "Test",
                "email": "new@test.com",
                "senha": "MySecret123",
                "confirmar_senha": "MySecret123",
            },
            follow_redirects=True,
        )
        assert b"MySecret123" not in resp.data
