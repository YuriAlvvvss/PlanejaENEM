"""Integration tests for the single-attempt question answering flow."""

import re

import pytest

from app import create_app, db
from app.models import Question, Subject, User


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


def _user_and_question(client):
    user = User(nome="Student", email="student@test.com")
    user.set_senha("Senha123")
    db.session.add(user)
    db.session.flush()
    subject = Subject(
        nome="Matematica",
        cor="#007bff",
        prioridade=3,
        dificuldade=3,
        area="matematica",
        user_id=user.id,
    )
    db.session.add(subject)
    db.session.flush()
    question = Question(
        enunciado="Qual alternativa esta correta?",
        alternativa_a="Resposta correta",
        alternativa_b="Distrator B",
        alternativa_c="Distrator C",
        alternativa_d="Distrator D",
        alternativa_e="Distrator E",
        resposta_correta="A",
        subject_id=subject.id,
        user_id=user.id,
        dificuldade=3,
        fonte="ai:test",
    )
    db.session.add(question)
    db.session.commit()
    client.post(
        "/auth/login",
        data={"email": user.email, "senha": "Senha123"},
        follow_redirects=True,
    )
    return user, question


def test_question_get_hides_answer_and_shows_one_attempt_warning(client):
    _, question = _user_and_question(client)

    response = client.get(f"/questions/{question.id}")
    page = response.data.decode()

    assert response.status_code == 200
    assert "Leia com atenção" in page
    assert "você tem apenas uma tentativa" in page
    assert "Gabarito:" not in page
    assert 'name="resposta"' in page
    assert page.count('name="resposta"') == 5
    assert "question-answer.js" in page


def test_answer_records_only_one_attempt_and_shows_result(client):
    user, question = _user_and_question(client)
    client.get(f"/questions/{question.id}")

    response = client.post(
        f"/questions/{question.id}/answer",
        data={"resposta": "A"},
    )

    assert response.status_code == 200
    page = response.data.decode()
    assert "Você acertou!" in page
    assert "Gabarito: A" in page
    assert "data-question-answer-form" not in page
    attempt = question.attempts[0]
    assert attempt.user_id == user.id
    assert attempt.tempo_segundos is not None
    assert attempt.tempo_segundos >= 0

    duplicate = client.post(
        f"/questions/{question.id}/answer",
        data={"resposta": "B"},
    )

    assert duplicate.status_code == 200
    assert "Você acertou!" in duplicate.data.decode()
    assert len(question.attempts) == 1


def test_wrong_answer_reveals_result_only_after_submission(client):
    _, question = _user_and_question(client)
    initial = client.get(f"/questions/{question.id}")
    assert "Gabarito:" not in initial.data.decode()

    response = client.post(
        f"/questions/{question.id}/answer",
        data={"resposta": "B"},
    )

    assert response.status_code == 200
    page = response.data.decode()
    assert "Você errou." in page
    assert "Gabarito: A" in page


def test_question_remains_available_when_user_abandons(client):
    _, question = _user_and_question(client)

    response = client.get(f"/questions/{question.id}")

    assert response.status_code == 200
    assert len(question.attempts) == 0
    listing = client.get("/questions/")
    assert "Qual alternativa esta correta?" in listing.data.decode()
    assert "Resposta correta" not in listing.data.decode()


def test_answer_submission_preserves_csrf_token(client, app):
    _, question = _user_and_question(client)
    app.config["WTF_CSRF_ENABLED"] = True

    page = client.get(f"/questions/{question.id}")
    match = re.search(r'name="csrf_token"[^>]+value="([^"]+)"', page.data.decode())
    assert match is not None

    response = client.post(
        f"/questions/{question.id}/answer",
        data={"csrf_token": match.group(1), "resposta": "A"},
    )

    assert response.status_code == 200
    assert "Você acertou!" in response.data.decode()
