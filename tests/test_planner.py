from datetime import date

import pytest

from app import create_app, db
from app.models import StudyPlan, StudySession, Subject, User


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


def test_planner_generates_sessions_for_user(client):
    user = User(nome="Ana", email="ana@example.com")
    user.set_senha("Senha123")
    db.session.add(user)
    db.session.commit()

    matematica = Subject(nome="Matemática", cor="#ff0000", user_id=user.id)
    historia = Subject(nome="História", cor="#00ff00", user_id=user.id)
    db.session.add_all([matematica, historia])
    db.session.commit()

    login = client.post(
        "/auth/login",
        data={"email": "ana@example.com", "senha": "Senha123"},
        follow_redirects=True,
    )
    assert login.status_code == 200

    response = client.post(
        "/planner/",
        data={
            "available_days": ["seg", "qua", "sex"],
            "available_hours": "08:00-10:00, 15:00-17:00",
            "daily_minutes": "120",
            "exam_date": "2026-09-15",
            f"priority_{matematica.id}": "alta",
            f"difficulty_{matematica.id}": "5",
            f"priority_{historia.id}": "media",
            f"difficulty_{historia.id}": "3",
            "generate_plan": "1",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert StudyPlan.query.filter_by(user_id=user.id).count() == 1
    assert StudySession.query.filter_by(user_id=user.id).count() > 0

    plan = StudyPlan.query.filter_by(user_id=user.id).first()
    assert plan.exam_date == date(2026, 9, 15)
    assert plan.daily_minutes == 120

    session = StudySession.query.filter_by(user_id=user.id).first()
    assert session is not None
    assert session.subject_id in {matematica.id, historia.id}
