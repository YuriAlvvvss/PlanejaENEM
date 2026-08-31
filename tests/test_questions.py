"""
Tests for the questions module.

Covers topic CRUD, question CRUD, answering questions,
statistics computation, IDOR protection, and multi-user isolation.
"""

import pytest
from datetime import datetime, timezone

from app import create_app, db
from app.models import User, Subject, Topic, Question, QuestionAttempt


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


def _logout(client):
    client.get("/auth/logout", follow_redirects=True)


def _create_subject(client, nome="Matematica"):
    client.post(
        "/subjects/new",
        data={"nome": nome, "cor": "#007bff", "prioridade": "3", "dificuldade": "3", "area": "matematica"},
        follow_redirects=True,
    )
    return Subject.query.filter_by(nome=nome).first()


def _create_topic(client, subject_id, nome="Funcoes"):
    client.post(
        "/questions/topics/new",
        data={"nome": nome, "subject_id": str(subject_id)},
        follow_redirects=True,
    )
    return Topic.query.filter_by(nome=nome).first()


def _create_question(client, subject_id, topic_id=None, resposta_correta="A"):
    data = {
        "enunciado": "Quanto e 2 + 2?",
        "alternativa_a": "4",
        "alternativa_b": "3",
        "alternativa_c": "5",
        "alternativa_d": "6",
        "alternativa_e": "7",
        "resposta_correta": resposta_correta,
        "subject_id": str(subject_id),
        "dificuldade": "3",
        "topic_id": "0",
    }
    if topic_id:
        data["topic_id"] = str(topic_id)
    client.post("/questions/new", data=data, follow_redirects=True)
    return Question.query.filter_by(enunciado="Quanto e 2 + 2?").first()


class TestTopicCRUD:
    def test_list_topics_empty(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        resp = client.get("/questions/topics")
        assert resp.status_code == 200
        assert "Nenhum assunto cadastrado" in resp.data.decode()

    def test_create_topic(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client)
        resp = _create_topic(client, subject.id)
        assert resp is not None
        assert resp.nome == "Funcoes"
        assert resp.subject_id == subject.id

    def test_create_topic_no_subject_redirects(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        resp = client.get("/questions/topics/new", follow_redirects=True)
        assert b"Crie uma mat" in resp.data

    def test_edit_topic(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client)
        topic = _create_topic(client, subject.id)
        resp = client.post(
            f"/questions/topics/{topic.id}/edit",
            data={"nome": "Equacoes", "subject_id": str(subject.id)},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        updated = db.session.get(Topic, topic.id)
        assert updated.nome == "Equacoes"

    def test_delete_topic(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client)
        topic = _create_topic(client, subject.id)
        resp = client.post(f"/questions/topics/{topic.id}/delete", follow_redirects=True)
        assert resp.status_code == 200
        assert db.session.get(Topic, topic.id) is None


class TestQuestionCRUD:
    def test_list_questions_empty(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        resp = client.get("/questions/")
        assert resp.status_code == 200
        assert "Nenhuma" in resp.data.decode()

    def test_create_question(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client)
        q = _create_question(client, subject.id)
        assert q is not None
        assert q.enunciado == "Quanto e 2 + 2?"
        assert q.resposta_correta == "A"
        assert q.user_id == User.query.filter_by(email="a@test.com").first().id

    def test_create_question_with_topic(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client)
        topic = _create_topic(client, subject.id, nome="Algebra")
        q = _create_question(client, subject.id, topic_id=topic.id)
        assert q is not None
        assert q.topic_id == topic.id

    def test_view_question(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client)
        q = _create_question(client, subject.id)
        resp = client.get(f"/questions/{q.id}")
        assert resp.status_code == 200
        assert "Quanto e 2 + 2?" in resp.data.decode()

    def test_edit_question(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client)
        q = _create_question(client, subject.id)
        resp = client.post(
            f"/questions/{q.id}/edit",
            data={
                "enunciado": "Quanto e 3 + 3?",
                "alternativa_a": "6",
                "alternativa_b": "5",
                "alternativa_c": "7",
                "alternativa_d": "8",
                "alternativa_e": "9",
                "resposta_correta": "A",
                "subject_id": str(subject.id),
                "topic_id": "0",
                "dificuldade": "2",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        updated = db.session.get(Question, q.id)
        assert updated.enunciado == "Quanto e 3 + 3?"

    def test_delete_question(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client)
        q = _create_question(client, subject.id)
        resp = client.post(f"/questions/{q.id}/delete", follow_redirects=True)
        assert resp.status_code == 200
        assert db.session.get(Question, q.id) is None


class TestAnswerQuestion:
    def test_answer_correct(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client)
        q = _create_question(client, subject.id, resposta_correta="A")
        resp = client.post(
            f"/questions/{q.id}/answer",
            data={"resposta": "A", "tempo_segundos": "30"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Resposta correta" in resp.data.decode()
        attempt = QuestionAttempt.query.filter_by(
            user_id=User.query.filter_by(email="a@test.com").first().id, question_id=q.id
        ).first()
        assert attempt is not None
        assert attempt.correta is True
        assert attempt.resposta == "A"
        assert attempt.tempo_segundos == 30

    def test_answer_incorrect(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client)
        q = _create_question(client, subject.id, resposta_correta="A")
        resp = client.post(
            f"/questions/{q.id}/answer",
            data={"resposta": "B"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "incorreta" in resp.data.decode()
        attempt = QuestionAttempt.query.filter_by(
            user_id=User.query.filter_by(email="a@test.com").first().id, question_id=q.id
        ).first()
        assert attempt.correta is False
        assert attempt.resposta == "B"

    def test_answer_without_time(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client)
        q = _create_question(client, subject.id)
        resp = client.post(
            f"/questions/{q.id}/answer",
            data={"resposta": "A"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        attempt = QuestionAttempt.query.filter_by(
            user_id=User.query.filter_by(email="a@test.com").first().id, question_id=q.id
        ).first()
        assert attempt.tempo_segundos is None

    def test_multiple_attempts_allowed(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client)
        q = _create_question(client, subject.id, resposta_correta="A")
        client.post(f"/questions/{q.id}/answer", data={"resposta": "A"}, follow_redirects=True)
        client.post(f"/questions/{q.id}/answer", data={"resposta": "B"}, follow_redirects=True)
        client.post(f"/questions/{q.id}/answer", data={"resposta": "A"}, follow_redirects=True)
        user = User.query.filter_by(email="a@test.com").first()
        count = QuestionAttempt.query.filter_by(user_id=user.id, question_id=q.id).count()
        assert count == 3


class TestIDORProtection:
    def test_cannot_view_other_users_question(self, client):
        user_a = _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject_a = _create_subject(client, "MatA")
        q = _create_question(client, subject_a.id)

        _logout(client)
        _create_user(client, "b@test.com")
        _login(client, "b@test.com")
        resp = client.get(f"/questions/{q.id}")
        assert resp.status_code == 404

    def test_cannot_answer_other_users_question(self, client):
        user_a = _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject_a = _create_subject(client, "MatA")
        q = _create_question(client, subject_a.id)

        _logout(client)
        _create_user(client, "b@test.com")
        _login(client, "b@test.com")
        resp = client.post(f"/questions/{q.id}/answer", data={"resposta": "A"}, follow_redirects=True)
        assert resp.status_code == 404

    def test_cannot_edit_other_users_question(self, client):
        user_a = _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject_a = _create_subject(client, "MatA")
        q = _create_question(client, subject_a.id)

        _logout(client)
        _create_user(client, "b@test.com")
        _login(client, "b@test.com")
        resp = client.get(f"/questions/{q.id}/edit")
        assert resp.status_code == 404

    def test_cannot_delete_other_users_question(self, client):
        user_a = _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject_a = _create_subject(client, "MatA")
        q = _create_question(client, subject_a.id)

        _logout(client)
        _create_user(client, "b@test.com")
        _login(client, "b@test.com")
        resp = client.post(f"/questions/{q.id}/delete", follow_redirects=True)
        assert resp.status_code == 404
        assert db.session.get(Question, q.id) is not None

    def test_cannot_view_other_users_topic(self, client):
        user_a = _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject_a = _create_subject(client, "MatA")
        topic = _create_topic(client, subject_a.id)

        _logout(client)
        _create_user(client, "b@test.com")
        _login(client, "b@test.com")
        resp = client.get(f"/questions/topics/{topic.id}/edit")
        assert resp.status_code == 404

    def test_cannot_delete_other_users_topic(self, client):
        user_a = _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject_a = _create_subject(client, "MatA")
        topic = _create_topic(client, subject_a.id)

        _logout(client)
        _create_user(client, "b@test.com")
        _login(client, "b@test.com")
        resp = client.post(f"/questions/topics/{topic.id}/delete", follow_redirects=True)
        assert db.session.get(Topic, topic.id) is not None

    def test_user_isolation_list_questions(self, client):
        user_a = _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject_a = _create_subject(client, "MatA")
        _create_question(client, subject_a.id)

        _logout(client)
        _create_user(client, "b@test.com")
        _login(client, "b@test.com")
        resp = client.get("/questions/")
        assert b"Quanto e 2 + 2?" not in resp.data

    def test_user_isolation_list_topics(self, client):
        user_a = _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject_a = _create_subject(client, "MatA")
        _create_topic(client, subject_a.id)

        _logout(client)
        _create_user(client, "b@test.com")
        _login(client, "b@test.com")
        resp = client.get("/questions/topics")
        assert b"Funcoes" not in resp.data


class TestStatistics:
    def test_overall_stats_empty(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        from app.performance.statistics import get_overall_stats
        stats = get_overall_stats(User.query.filter_by(email="a@test.com").first().id)
        assert stats["total"] == 0
        assert stats["accuracy"] == 0

    def test_overall_stats_with_attempts(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client, "MatA")
        q1 = _create_question(client, subject.id, resposta_correta="A")
        q2_enunciado = "Quanto e 3 + 3?"
        client.post(
            "/questions/new",
            data={
                "enunciado": q2_enunciado,
                "alternativa_a": "5",
                "alternativa_b": "6",
                "alternativa_c": "7",
                "alternativa_d": "8",
                "alternativa_e": "9",
                "resposta_correta": "B",
                "subject_id": str(subject.id),
                "topic_id": "0",
                "dificuldade": "3",
            },
            follow_redirects=True,
        )
        q2 = Question.query.filter_by(enunciado=q2_enunciado).first()
        client.post(f"/questions/{q1.id}/answer", data={"resposta": "A"}, follow_redirects=True)
        client.post(f"/questions/{q2.id}/answer", data={"resposta": "A"}, follow_redirects=True)

        from app.performance.statistics import get_overall_stats
        user = User.query.filter_by(email="a@test.com").first()
        stats = get_overall_stats(user.id)
        assert stats["total"] == 2
        assert stats["correct"] == 1
        assert stats["wrong"] == 1
        assert stats["accuracy"] == 50

    def test_subject_stats(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client, "MatStats")
        q = _create_question(client, subject.id, resposta_correta="A")
        client.post(f"/questions/{q.id}/answer", data={"resposta": "A"}, follow_redirects=True)

        from app.performance.statistics import get_subject_stats
        user = User.query.filter_by(email="a@test.com").first()
        stats = get_subject_stats(user.id)
        assert len(stats) == 1
        assert stats[0]["accuracy"] == 100
        assert stats[0]["subject_nome"] == "MatStats"

    def test_difficulty_stats(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client, "MatDiff")
        q = _create_question(client, subject.id, resposta_correta="A")
        client.post(f"/questions/{q.id}/answer", data={"resposta": "A"}, follow_redirects=True)

        from app.performance.statistics import get_difficulty_stats
        user = User.query.filter_by(email="a@test.com").first()
        stats = get_difficulty_stats(user.id)
        assert len(stats) == 1
        assert stats[0]["dificuldade"] == 3
        assert stats[0]["accuracy"] == 100

    def test_topic_stats(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client, "MatTopic")
        topic = _create_topic(client, subject.id, nome="Algebra")
        q = _create_question(client, subject.id, topic_id=topic.id, resposta_correta="A")
        client.post(f"/questions/{q.id}/answer", data={"resposta": "A"}, follow_redirects=True)

        from app.performance.statistics import get_topic_stats
        user = User.query.filter_by(email="a@test.com").first()
        stats = get_topic_stats(user.id)
        assert len(stats) == 1
        assert stats[0]["accuracy"] == 100

    def test_recent_performance(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client, "MatRecent")
        q = _create_question(client, subject.id, resposta_correta="A")
        client.post(f"/questions/{q.id}/answer", data={"resposta": "A"}, follow_redirects=True)

        from app.performance.statistics import get_recent_performance
        user = User.query.filter_by(email="a@test.com").first()
        perf = get_recent_performance(user.id)
        assert perf["recent_total"] == 1
        assert perf["recent_correct"] == 1
        assert perf["recent_accuracy"] == 100

    def test_best_worst_subject(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client, "MatBest")
        q = _create_question(client, subject.id, resposta_correta="A")
        client.post(f"/questions/{q.id}/answer", data={"resposta": "A"}, follow_redirects=True)

        from app.performance.statistics import get_best_worst_subject
        user = User.query.filter_by(email="a@test.com").first()
        best, worst = get_best_worst_subject(user.id)
        assert best is not None
        assert worst is not None
        assert best["accuracy"] == 100

    def test_area_stats(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client, "MatArea")
        q = _create_question(client, subject.id, resposta_correta="A")
        client.post(f"/questions/{q.id}/answer", data={"resposta": "A"}, follow_redirects=True)

        from app.performance.statistics import get_area_stats
        user = User.query.filter_by(email="a@test.com").first()
        stats = get_area_stats(user.id)
        assert len(stats) >= 1

    def test_user_isolation_stats(self, client):
        user_a = _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject_a = _create_subject(client, "MatIso")
        q = _create_question(client, subject_a.id, resposta_correta="A")
        client.post(f"/questions/{q.id}/answer", data={"resposta": "A"}, follow_redirects=True)

        _logout(client)
        _create_user(client, "b@test.com")
        _login(client, "b@test.com")

        from app.performance.statistics import get_overall_stats, get_subject_stats
        user_b = User.query.filter_by(email="b@test.com").first()
        stats_b = get_overall_stats(user_b.id)
        assert stats_b["total"] == 0
        subject_stats_b = get_subject_stats(user_b.id)
        assert len(subject_stats_b) == 0


class TestPerformanceRoutes:
    def test_overview_requires_login(self, client):
        resp = client.get("/performance/")
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]

    def test_overview_empty(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        resp = client.get("/performance/")
        assert resp.status_code == 200
        assert "Nenhum dado" in resp.data.decode()

    def test_overview_with_data(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client, "MatPerf")
        q = _create_question(client, subject.id, resposta_correta="A")
        client.post(f"/questions/{q.id}/answer", data={"resposta": "A"}, follow_redirects=True)
        resp = client.get("/performance/")
        assert resp.status_code == 200
        assert "100%" in resp.data.decode()


class TestFormValidation:
    def test_question_requires_enunciado(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client, "MatVal")
        resp = client.post(
            "/questions/new",
            data={
                "enunciado": "",
                "alternativa_a": "A",
                "alternativa_b": "B",
                "alternativa_c": "C",
                "alternativa_d": "D",
                "alternativa_e": "E",
                "resposta_correta": "A",
                "subject_id": str(subject.id),
                "topic_id": "0",
                "dificuldade": "3",
            },
            follow_redirects=True,
        )
        user = User.query.filter_by(email="a@test.com").first()
        assert Question.query.filter_by(user_id=user.id).count() == 0

    def test_answer_requires_selection(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client, "MatVal2")
        q = _create_question(client, subject.id)
        resp = client.post(f"/questions/{q.id}/answer", data={}, follow_redirects=True)
        user = User.query.filter_by(email="a@test.com").first()
        assert QuestionAttempt.query.filter_by(user_id=user.id).count() == 0

    def test_topic_requires_nome(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client, "MatVal3")
        resp = client.post(
            "/questions/topics/new",
            data={"nome": "", "subject_id": str(subject.id)},
            follow_redirects=True,
        )
        user = User.query.filter_by(email="a@test.com").first()
        assert Topic.query.filter_by(user_id=user.id).count() == 0

    def test_question_with_invalid_resposta_correta(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client, "MatVal4")
        resp = client.post(
            "/questions/new",
            data={
                "enunciado": "Teste",
                "alternativa_a": "A",
                "alternativa_b": "B",
                "alternativa_c": "C",
                "alternativa_d": "D",
                "alternativa_e": "E",
                "resposta_correta": "X",
                "subject_id": str(subject.id),
                "topic_id": "0",
                "dificuldade": "3",
            },
            follow_redirects=True,
        )
        user = User.query.filter_by(email="a@test.com").first()
        assert Question.query.filter_by(user_id=user.id).count() == 0


class TestDashboardIntegration:
    def test_dashboard_shows_question_stats(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        subject = _create_subject(client, "MatDash")
        q = _create_question(client, subject.id, resposta_correta="A")
        client.post(f"/questions/{q.id}/answer", data={"resposta": "A"}, follow_redirects=True)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "100%" in resp.data.decode()

    def test_dashboard_no_questions_shows_no_section(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        resp = client.get("/")
        assert resp.status_code == 200


class TestSidebarLinks:
    def test_sidebar_has_questions_link(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        resp = client.get("/")
        assert "/questions/" in resp.data.decode()

    def test_sidebar_has_performance_link(self, client):
        _create_user(client, "a@test.com")
        _login(client, "a@test.com")
        resp = client.get("/")
        assert "/performance/" in resp.data.decode()
