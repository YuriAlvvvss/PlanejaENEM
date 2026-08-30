"""
Testes de integração do planner adaptativo - PlanejaENEM Adaptive Planner v2.
"""

from datetime import date, timedelta

import pytest

from app import create_app, db
from app.models import StudyPlan, StudySession, Subject, Task, User
from app.planner.services import (
    generate_adaptive_plan,
    get_diagnostics,
    get_subject_need_data,
    get_subject_performance,
    process_planner_request,
    replan_after_missed_sessions,
)
from app.planner.spaced_repetition import get_review_status


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_user(app):
    user = User(nome="Test User", email="test@example.com")
    user.set_senha("Senha123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def sample_subjects(sample_user):
    mat = Subject(nome="Matematica", cor="#ff0000", user_id=sample_user.id, prioridade=5, dificuldade=4)
    hist = Subject(nome="Historia", cor="#00ff00", user_id=sample_user.id, prioridade=3, dificuldade=2)
    fis = Subject(nome="Fisica", cor="#0000ff", user_id=sample_user.id, prioridade=4, dificuldade=5)
    db.session.add_all([mat, hist, fis])
    db.session.commit()
    return [mat, hist, fis]


@pytest.fixture
def sample_tasks(sample_user, sample_subjects):
    tasks = []
    for subject in sample_subjects:
        for i in range(3):
            task = Task(
                titulo=f"Task {subject.nome} {i}",
                subject_id=subject.id,
                user_id=sample_user.id,
                concluida=True,
                prioridade="media",
            )
            tasks.append(task)
    db.session.add_all(tasks)
    db.session.commit()
    return tasks


class TestSubjectPerformance:
    def test_no_tasks(self, app, sample_user, sample_subjects):
        perf = get_subject_performance(sample_subjects[0].id, sample_user.id)
        assert perf["total_tasks"] == 0
        assert perf["correct_pct"] is None
        assert perf["performance_level"] == "medium"

    def test_with_tasks(self, app, sample_user, sample_subjects, sample_tasks):
        perf = get_subject_performance(sample_subjects[0].id, sample_user.id)
        assert perf["total_tasks"] == 3


class TestSubjectNeedData:
    def test_basic(self, app, sample_user, sample_subjects, sample_tasks):
        exam_date = date.today() + timedelta(days=90)
        data = get_subject_need_data(sample_subjects[0], sample_user.id, exam_date)
        assert "score" in data
        assert "components" in data
        assert 0 <= data["score"] <= 100

    def test_high_priority_high_score(self, app, sample_user, sample_subjects):
        exam_date = date.today() + timedelta(days=14)
        data = get_subject_need_data(sample_subjects[0], sample_user.id, exam_date)
        assert data["score"] >= 50


class TestAdaptivePlan:
    def test_generates_sessions(self, app, sample_user, sample_subjects, sample_tasks):
        exam_date = date.today() + timedelta(days=30)
        result = generate_adaptive_plan(
            user_id=sample_user.id,
            days=["seg", "qua", "sex"],
            hours=["08:00-10:00"],
            daily_minutes=120,
            exam_date=exam_date,
            subject_settings={
                sample_subjects[0].id: {"priority": 5, "difficulty": 4},
                sample_subjects[1].id: {"priority": 3, "difficulty": 2},
                sample_subjects[2].id: {"priority": 4, "difficulty": 5},
            },
        )
        assert len(result["sessions"]) > 0
        assert "explanations" in result
        assert "summary" in result

    def test_summary_has_correct_fields(self, app, sample_user, sample_subjects):
        exam_date = date.today() + timedelta(days=90)
        result = generate_adaptive_plan(
            user_id=sample_user.id,
            days=["seg", "qua"],
            hours=["08:00-10:00"],
            daily_minutes=60,
            exam_date=exam_date,
            subject_settings={s.id: {"priority": 3, "difficulty": 3} for s in sample_subjects},
        )
        summary = result["summary"]
        assert "total_sessions" in summary
        assert "total_minutes" in summary
        assert "phase" in summary
        assert "days_until_exam" in summary

    def test_no_subjects(self, app, sample_user):
        exam_date = date.today() + timedelta(days=30)
        result = generate_adaptive_plan(
            user_id=sample_user.id,
            days=["seg"],
            hours=["08:00-10:00"],
            daily_minutes=60,
            exam_date=exam_date,
            subject_settings={},
        )
        assert result["sessions"] == []


class TestProcessPlannerRequest:
    def test_valid_request(self, app, client, sample_user, sample_subjects):
        with client.session_transaction():
            pass
        client.post("/auth/login", data={"email": "test@example.com", "senha": "Senha123"})

        form_data = {
            "available_days": ["seg", "qua"],
            "available_hours": "08:00-10:00",
            "daily_minutes": "120",
            "exam_date": (date.today() + timedelta(days=30)).isoformat(),
        }
        for s in sample_subjects:
            form_data[f"priority_{s.id}"] = "3"
            form_data[f"difficulty_{s.id}"] = "3"

        class MockForm:
            def __init__(self, data):
                self._data = data
            def getlist(self, key):
                val = self._data.get(key, [])
                if isinstance(val, list):
                    return val
                return [val]
            def get(self, key, default=None):
                return self._data.get(key, default)

        result, errors = process_planner_request(
            user_id=sample_user.id,
            form_data=MockForm(form_data),
            subjects=sample_subjects,
        )
        assert errors == []
        assert len(result["sessions"]) > 0

    def test_missing_exam_date(self, app, sample_user, sample_subjects):
        class MockForm:
            def __init__(self, data):
                self._data = data
            def getlist(self, key):
                val = self._data.get(key, [])
                if isinstance(val, list):
                    return val
                return [val]
            def get(self, key, default=None):
                return self._data.get(key, default)

        form_data = {
            "available_days": ["seg"],
            "available_hours": "08:00-10:00",
            "daily_minutes": "60",
            "exam_date": "",
        }
        result, errors = process_planner_request(
            user_id=sample_user.id,
            form_data=MockForm(form_data),
            subjects=sample_subjects,
        )
        assert len(errors) > 0

    def test_no_days_selected(self, app, sample_user, sample_subjects):
        class MockForm:
            def __init__(self, data):
                self._data = data
            def getlist(self, key):
                val = self._data.get(key, [])
                if isinstance(val, list):
                    return val
                return [val]
            def get(self, key, default=None):
                return self._data.get(key, default)

        form_data = {
            "available_days": [],
            "available_hours": "08:00-10:00",
            "daily_minutes": "60",
            "exam_date": (date.today() + timedelta(days=30)).isoformat(),
        }
        result, errors = process_planner_request(
            user_id=sample_user.id,
            form_data=MockForm(form_data),
            subjects=sample_subjects,
        )
        assert len(errors) > 0


class TestDiagnostics:
    def test_no_data(self, app, sample_user):
        diag = get_diagnostics(sample_user.id)
        assert diag["has_data"] is False
        assert diag["overall"] == 0

    def test_with_data(self, app, sample_user, sample_subjects, sample_tasks):
        diag = get_diagnostics(sample_user.id)
        assert len(diag["areas"]) > 0


class TestReplanMissedSessions:
    def test_no_missed(self, app, sample_user, sample_subjects):
        result = replan_after_missed_sessions(sample_user.id)
        assert result["missed_count"] == 0

    def test_with_missed_sessions(self, app, sample_user, sample_subjects):
        exam_date = date.today() + timedelta(days=30)
        plan = StudyPlan(
            user_id=sample_user.id,
            exam_date=exam_date,
            daily_minutes=120,
            available_days="seg,qua,sex",
            available_hours="08:00-10:00",
        )
        db.session.add(plan)
        db.session.flush()

        yesterday = date.today() - timedelta(days=1)
        missed = StudySession(
            plan_id=plan.id,
            user_id=sample_user.id,
            subject_id=sample_subjects[0].id,
            session_date=yesterday,
            start_time=__import__("datetime").time(8, 0),
            end_time=__import__("datetime").time(10, 0),
            duration_minutes=120,
            completed=False,
            manual_override=False,
        )
        db.session.add(missed)
        db.session.commit()

        result = replan_after_missed_sessions(sample_user.id)
        assert result["missed_count"] == 1


class TestPlannerRoutes:
    def test_planner_get(self, client, sample_user, sample_subjects):
        client.post("/auth/login", data={"email": "test@example.com", "senha": "Senha123"})
        response = client.get("/planner/")
        assert response.status_code == 200

    def test_planner_post_creates_plan(self, client, sample_user, sample_subjects):
        client.post("/auth/login", data={"email": "test@example.com", "senha": "Senha123"})
        response = client.post(
            "/planner/",
            data={
                "available_days": ["seg", "qua", "sex"],
                "available_hours": "08:00-10:00, 15:00-17:00",
                "daily_minutes": "120",
                "exam_date": (date.today() + timedelta(days=30)).isoformat(),
                f"priority_{sample_subjects[0].id}": "5",
                f"difficulty_{sample_subjects[0].id}": "4",
                f"priority_{sample_subjects[1].id}": "3",
                f"difficulty_{sample_subjects[1].id}": "2",
                f"priority_{sample_subjects[2].id}": "4",
                f"difficulty_{sample_subjects[2].id}": "5",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert StudyPlan.query.filter_by(user_id=sample_user.id).count() >= 1

    def test_replan_route(self, client, sample_user, sample_subjects):
        client.post("/auth/login", data={"email": "test@example.com", "senha": "Senha123"})
        response = client.post("/planner/replan", follow_redirects=True)
        assert response.status_code == 200

    def test_diagnostics_route(self, client, sample_user, sample_subjects):
        client.post("/auth/login", data={"email": "test@example.com", "senha": "Senha123"})
        response = client.get("/planner/diagnostics")
        assert response.status_code == 200


class TestUserIsolation:
    def test_users_cannot_access_each_others_plans(self, app, client):
        user1 = User(nome="User 1", email="user1@test.com")
        user1.set_senha("Senha123")
        user2 = User(nome="User 2", email="user2@test.com")
        user2.set_senha("Senha123")
        db.session.add_all([user1, user2])
        db.session.commit()

        sub1 = Subject(nome="Mat", cor="#ff0000", user_id=user1.id)
        sub2 = Subject(nome="Hist", cor="#00ff00", user_id=user2.id)
        db.session.add_all([sub1, sub2])
        db.session.commit()

        client.post("/auth/login", data={"email": "user1@test.com", "senha": "Senha123"})
        client.post(
            "/planner/",
            data={
                "available_days": ["seg"],
                "available_hours": "08:00-10:00",
                "daily_minutes": "60",
                "exam_date": (date.today() + timedelta(days=30)).isoformat(),
                f"priority_{sub1.id}": "3",
                f"difficulty_{sub1.id}": "3",
            },
            follow_redirects=True,
        )

        plan_user1 = StudyPlan.query.filter_by(user_id=user1.id).first()
        assert plan_user1 is not None

        client.get("/auth/logout", follow_redirects=True)
        client.post("/auth/login", data={"email": "user2@test.com", "senha": "Senha123"})

        plan_user2 = StudyPlan.query.filter_by(user_id=user2.id).first()
        assert plan_user2 is None

        response = client.post(f"/planner/{plan_user1.id}/regenerate", follow_redirects=True)
        assert response.status_code in (200, 404)

        plan_user1_still = StudyPlan.query.filter_by(user_id=user1.id, id=plan_user1.id).first()
        assert plan_user1_still is not None


class TestEdgeCases:
    def test_single_subject(self, app, sample_user):
        sub = Subject(nome="Unica", cor="#ff0000", user_id=sample_user.id)
        db.session.add(sub)
        db.session.commit()

        exam_date = date.today() + timedelta(days=30)
        result = generate_adaptive_plan(
            user_id=sample_user.id,
            days=["seg"],
            hours=["08:00-10:00"],
            daily_minutes=60,
            exam_date=exam_date,
            subject_settings={sub.id: {"priority": 3, "difficulty": 3}},
        )
        assert result["summary"]["subjects_count"] == 1

    def test_very_short_time_until_exam(self, app, sample_user, sample_subjects):
        exam_date = date.today() + timedelta(days=1)
        result = generate_adaptive_plan(
            user_id=sample_user.id,
            days=["seg", "ter", "qua"],
            hours=["08:00-10:00"],
            daily_minutes=120,
            exam_date=exam_date,
            subject_settings={s.id: {"priority": 3, "difficulty": 3} for s in sample_subjects},
        )
        assert result["summary"]["phase"] == "final_stretch"

    def test_long_time_until_exam(self, app, sample_user, sample_subjects):
        exam_date = date.today() + timedelta(days=365)
        result = generate_adaptive_plan(
            user_id=sample_user.id,
            days=["seg"],
            hours=["08:00-10:00"],
            daily_minutes=60,
            exam_date=exam_date,
            subject_settings={s.id: {"priority": 3, "difficulty": 3} for s in sample_subjects},
        )
        assert result["summary"]["phase"] == "long_term"
