import pytest
from datetime import date, datetime, time, timedelta, timezone

from app import create_app, db
from app.areas import infer_area
from app.main.stats import build_dashboard_stats, compute_streak, format_hours
from app.models import StudySession, Subject, Task, User


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


def test_infer_area_from_subject_name():
    assert infer_area("Matemática") == "matematica"
    assert infer_area("História do Brasil") == "humanas"
    assert infer_area("Redação ENEM") == "redacao"


def test_format_hours_and_streak():
    assert format_hours(90) == "1h 30min"
    assert format_hours(120) == "2h"
    today = date(2026, 8, 29)
    assert compute_streak({today, today - timedelta(days=1)}, today) == 2
    assert compute_streak({today - timedelta(days=1)}, today) == 1
    assert compute_streak(set(), today) == 0


def test_dashboard_hours_streak_reviews_and_goal(client):
    app = client.application
    with app.app_context():
        user = User(nome="Ana", email="ana@example.com", weekly_goal_minutes=300)
        user.set_senha("Senha123")
        db.session.add(user)
        db.session.commit()

        subject = Subject(nome="Matemática", cor="#ff0000", user_id=user.id, area="matematica")
        db.session.add(subject)
        db.session.commit()

        today = date.today()
        overdue = Task(
            titulo="Lista atrasada",
            subject_id=subject.id,
            user_id=user.id,
            data_prevista=today - timedelta(days=2),
            prioridade="alta",
            concluida=False,
        )
        today_task = Task(
            titulo="Simulado de hoje",
            subject_id=subject.id,
            user_id=user.id,
            data_prevista=today,
            prioridade="media",
            concluida=False,
        )
        review = Task(
            titulo="Revisar funções",
            subject_id=subject.id,
            user_id=user.id,
            data_prevista=today - timedelta(days=7),
            prioridade="baixa",
            concluida=True,
            completed_at=datetime.now(timezone.utc) - timedelta(days=7),
            next_review_date=today,
        )
        db.session.add_all([overdue, today_task, review])

        session = StudySession(
            plan_id=1,
            user_id=user.id,
            subject_id=subject.id,
            session_date=today,
            start_time=time(8, 0),
            end_time=time(10, 0),
            duration_minutes=120,
            completed=True,
            completed_at=datetime.now(timezone.utc),
        )
        # plan_id FK will fail without plan - create plan
        from app.models import StudyPlan

        plan = StudyPlan(
            user_id=user.id,
            exam_date=today + timedelta(days=30),
            daily_minutes=90,
            available_days="seg,qua,sex",
            available_hours="08:00-10:00",
        )
        db.session.add(plan)
        db.session.flush()
        session.plan_id = plan.id
        db.session.add(session)
        db.session.commit()
        user_id = user.id

    login = client.post(
        "/auth/login",
        data={"email": "ana@example.com", "senha": "Senha123"},
        follow_redirects=True,
    )
    assert login.status_code == 200

    response = client.get("/")
    assert response.status_code == 200
    assert b"2h" in response.data
    assert b"Simulado de hoje" in response.data
    assert b"Lista atrasada" in response.data
    assert b"Revisar fun" in response.data
    assert b"cal-grid" not in response.data

    with app.app_context():
        user = db.session.get(User, user_id)
        stats = build_dashboard_stats(user)
        assert stats["completed_minutes"] == 120
        assert stats["planned_minutes"] == 120
        assert stats["streak"] >= 1
        assert stats["weekly_progress"] > 0
        assert any(item["key"] == "matematica" for item in stats["area_stats"])

    goal = client.post(
        "/weekly-goal",
        data={"weekly_goal_hours": "8"},
        follow_redirects=True,
    )
    assert goal.status_code == 200
    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.weekly_goal_minutes == 480
