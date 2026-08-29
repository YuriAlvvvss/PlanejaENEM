import pytest
from app import create_app, db
from app.models import User


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


def test_register_success(client):
    response = client.post(
        "/auth/register",
        data={
            "nome": "Ana",
            "email": "ana@example.com",
            "senha": "senha123",
            "confirmar_senha": "senha123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert User.query.filter_by(email="ana@example.com").count() == 1


def test_register_duplicate_email(client):
    client.post(
        "/auth/register",
        data={
            "nome": "Ana",
            "email": "ana@example.com",
            "senha": "senha123",
            "confirmar_senha": "senha123",
        },
        follow_redirects=True,
    )

    response = client.post(
        "/auth/register",
        data={
            "nome": "Outra",
            "email": "ana@example.com",
            "senha": "outrasenha",
            "confirmar_senha": "outrasenha",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert User.query.filter_by(email="ana@example.com").count() == 1


def test_login_success(client):
    user = User(nome="Ana", email="ana@example.com")
    user.set_senha("senha123")
    db.session.add(user)
    db.session.commit()

    response = client.post(
        "/auth/login",
        data={
            "email": "ana@example.com",
            "senha": "senha123",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Bem-vindo de volta!" in response.data


def test_login_invalid_credentials(client):
    user = User(nome="Ana", email="ana@example.com")
    user.set_senha("senha123")
    db.session.add(user)
    db.session.commit()

    response = client.post(
        "/auth/login",
        data={
            "email": "ana@example.com",
            "senha": "senhaerrada",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Email ou senha inv\xc3\xa1lidos." in response.data


def test_logout(client):
    user = User(nome="Ana", email="ana@example.com")
    user.set_senha("senha123")
    db.session.add(user)
    db.session.commit()

    client.post(
        "/auth/login",
        data={
            "email": "ana@example.com",
            "senha": "senha123",
        },
        follow_redirects=True,
    )

    response = client.get("/auth/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"Entrar" in response.data


def test_protected_route_requires_login(client):
    response = client.get("/subjects/", follow_redirects=True)
    assert response.status_code == 200
    assert b"Entrar" in response.data
