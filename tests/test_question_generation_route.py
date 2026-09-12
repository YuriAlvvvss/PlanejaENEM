"""Integration tests for the AI question generation endpoint."""

from types import SimpleNamespace

import pytest

from app import create_app, db
from app.ai import GeneratedQuestion
from app.ai.exceptions import AIConfigurationError, AIProviderError
from app.models import Question, Subject, Topic, User


@pytest.fixture
def app():
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _logged_user(client, email="generation@test.com"):
    user = User(nome="Generator", email=email)
    user.set_senha("Senha123")
    db.session.add(user)
    db.session.commit()
    response = client.post(
        "/auth/login",
        data={"email": email, "senha": "Senha123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    return user


def _valid_generated_question():
    return GeneratedQuestion(
        statement="Quanto e 2 + 2?",
        alternative_a="3",
        alternative_b="4",
        alternative_c="5",
        alternative_d="6",
        alternative_e="7",
        correct_answer="B",
        explanation="A soma resulta em 4.",
        difficulty=3,
        topic="Aritmetica",
        model="test-model",
    )


def _subject(user_id, name):
    subject = Subject(
        nome=name,
        cor="#007bff",
        prioridade=3,
        dificuldade=3,
        area="matematica",
        user_id=user_id,
    )
    db.session.add(subject)
    db.session.flush()
    return subject


def test_generate_question_success(client, app):
    user = _logged_user(client)
    subject = _subject(user.id, "Matematica")
    topic = Topic(nome="Aritmetica", subject_id=subject.id, user_id=user.id)
    db.session.add(topic)
    db.session.commit()

    generator = SimpleNamespace(
        enabled=True,
        generate=lambda **kwargs: [_valid_generated_question()],
    )
    app.question_generator = generator

    response = client.post(
        "/questions/generate",
        json={"subject_id": subject.id, "topic_id": topic.id, "quantidade": 1},
    )

    assert response.status_code == 201
    assert response.json["success"] is True
    assert response.json["count"] == 1
    assert Question.query.filter_by(user_id=user.id).count() == 1


def test_generate_question_rejects_topic_from_another_subject(client, app):
    user = _logged_user(client)
    first_subject = _subject(user.id, "Matematica")
    second_subject = _subject(user.id, "Historia")
    topic = Topic(nome="Brasil", subject_id=second_subject.id, user_id=user.id)
    db.session.add(topic)
    db.session.commit()
    app.question_generator = SimpleNamespace(enabled=True, generate=lambda **kwargs: [])

    response = client.post(
        "/questions/generate",
        json={"subject_id": first_subject.id, "topic_id": topic.id, "quantidade": 1},
    )

    assert response.status_code == 404
    assert response.json["success"] is False
    assert Question.query.filter_by(user_id=user.id).count() == 0


def test_generate_question_returns_controlled_provider_error(client, app):
    user = _logged_user(client)
    subject = _subject(user.id, "Matematica")
    db.session.commit()

    def generate(**kwargs):
        raise AIProviderError("provider secret")

    app.question_generator = SimpleNamespace(enabled=True, generate=generate)

    response = client.post(
        "/questions/generate",
        json={"subject_id": subject.id, "quantidade": 1},
    )

    assert response.status_code == 502
    assert response.json["error"] != "provider secret"
    assert Question.query.filter_by(user_id=user.id).count() == 0


def test_generate_question_rejects_invalid_quantity(client, app):
    user = _logged_user(client)
    subject = _subject(user.id, "Matematica")
    db.session.commit()
    app.question_generator = SimpleNamespace(enabled=True, generate=lambda **kwargs: [])

    response = client.post(
        "/questions/generate",
        json={"subject_id": subject.id, "quantidade": 2},
    )

    assert response.status_code == 400
    assert "1, 3 ou 5" in response.json["error"]


def test_generate_question_reports_disabled_ai(client, app):
    user = _logged_user(client)
    subject = _subject(user.id, "Matematica")
    db.session.commit()
    app.question_generator = SimpleNamespace(enabled=False, generate=lambda **kwargs: [])

    response = client.post(
        "/questions/generate",
        json={"subject_id": subject.id, "quantidade": 1},
    )

    assert response.status_code == 503
    assert response.json["error"] == "IA não está disponível"


def test_generate_question_reports_empty_validated_response(client, app):
    user = _logged_user(client)
    subject = _subject(user.id, "Matematica")
    db.session.commit()
    app.question_generator = SimpleNamespace(enabled=True, generate=lambda **kwargs: [])

    response = client.post(
        "/questions/generate",
        json={"subject_id": subject.id, "quantidade": 1},
    )

    assert response.status_code == 422
    assert response.json["success"] is False
    assert Question.query.filter_by(user_id=user.id).count() == 0


def test_generate_question_reports_incomplete_ai_configuration(client, app):
    user = _logged_user(client)
    subject = _subject(user.id, "Matematica")
    db.session.commit()

    def generate(**kwargs):
        raise AIConfigurationError("missing api key")

    app.question_generator = SimpleNamespace(enabled=True, generate=generate)

    response = client.post(
        "/questions/generate",
        json={"subject_id": subject.id, "quantidade": 1},
    )

    assert response.status_code == 503
    assert "configuração" in response.json["error"]


def test_questions_page_uses_csp_compatible_static_script(client, app):
    user = _logged_user(client)
    _subject(user.id, "Matematica")
    db.session.commit()

    response = client.get("/questions/")
    page = response.data.decode()

    assert response.status_code == 200
    assert "/static/questions.js" in page
    assert "onclick=\"generateWithAI()\"" not in page
    assert "<script>" not in page
