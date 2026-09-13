import pytest

from app import create_app, db
from app.models import Subject, Task, User


@pytest.fixture
def app():
    application = create_app("testing")
    application.config["WTF_CSRF_ENABLED"] = False
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def create_user(client, email, name):
    client.post(
        "/auth/register",
        data={
            "nome": name,
            "email": email,
            "senha": "Senha123",
            "confirmar_senha": "Senha123",
        },
    )
    client.post(
        "/auth/login",
        data={"email": email, "senha": "Senha123"},
    )
    return User.query.filter_by(email=email).first()


def test_global_search_returns_only_current_user_results(client):
    user_a = create_user(client, "a@example.com", "Ana")
    subject_a = Subject(
        nome="Algebra personalizada",
        cor="#123456",
        area="matematica",
        user_id=user_a.id,
    )
    db.session.add(subject_a)
    db.session.commit()

    client.get("/auth/logout")
    user_b = create_user(client, "b@example.com", "Bia")
    subject_b = Subject(
        nome="Algebra privada",
        cor="#654321",
        area="matematica",
        user_id=user_b.id,
    )
    db.session.add(subject_b)
    db.session.commit()

    response = client.get("/search?q=Algebra")

    assert response.status_code == 200
    assert b"Algebra privada" in response.data
    assert b"Algebra personalizada" not in response.data


def test_global_search_empty_and_missing_states(client):
    create_user(client, "a@example.com", "Ana")

    empty = client.get("/search")
    missing = client.get("/search?q=nao-existe")

    assert empty.status_code == 200
    assert b"Encontre algo" in empty.data
    assert missing.status_code == 200
    assert b"Nenhum resultado encontrado" in missing.data
