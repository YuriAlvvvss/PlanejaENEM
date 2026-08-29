import pytest
from app import create_app, db
from app.models import User, Subject, Task


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


def login(client, email="ana@example.com", password="Senha123"):
    return client.post(
        "/auth/login",
        data={"email": email, "senha": password},
        follow_redirects=True,
    )


def test_register_success(client):
    response = client.post(
        "/auth/register",
        data={
            "nome": "Ana",
            "email": "ana@example.com",
            "senha": "Senha123",
            "confirmar_senha": "Senha123",
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
            "senha": "Senha123",
            "confirmar_senha": "Senha123",
        },
        follow_redirects=True,
    )

    response = client.post(
        "/auth/register",
        data={
            "nome": "Outra",
            "email": "ana@example.com",
            "senha": "OutraSenha123",
            "confirmar_senha": "OutraSenha123",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert User.query.filter_by(email="ana@example.com").count() == 1


def test_login_success(client):
    user = User(nome="Ana", email="ana@example.com")
    user.set_senha("Senha123")
    db.session.add(user)
    db.session.commit()

    response = client.post(
        "/auth/login",
        data={
            "email": "ana@example.com",
            "senha": "Senha123",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Bem-vindo de volta!" in response.data


def test_login_invalid_credentials(client):
    user = User(nome="Ana", email="ana@example.com")
    user.set_senha("Senha123")
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
    user.set_senha("Senha123")
    db.session.add(user)
    db.session.commit()

    client.post(
        "/auth/login",
        data={
            "email": "ana@example.com",
            "senha": "Senha123",
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


def test_create_subject_and_dashboard_summary(client):
    user = User(nome="Ana", email="ana@example.com")
    user.set_senha("Senha123")
    db.session.add(user)
    db.session.commit()

    login(client)

    response = client.post(
        "/subjects/new",
        data={"nome": "Matemática", "cor": "#ff0000"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert Subject.query.filter_by(nome="Matemática", user_id=user.id).count() == 1

    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert b"Matem\xc3\xa1tica" in dashboard.data


def test_create_task_filter_and_toggle(client):
    user = User(nome="Ana", email="ana@example.com")
    user.set_senha("Senha123")
    db.session.add(user)
    db.session.commit()

    subject = Subject(nome="História", cor="#00ff00", user_id=user.id)
    db.session.add(subject)
    db.session.commit()

    login(client)

    response = client.post(
        "/tasks/new",
        data={
            "titulo": "Estudar Brasil",
            "descricao": "Revisar capítulos 1 e 2",
            "subject_id": subject.id,
            "data_prevista": "2026-08-31",
            "prioridade": "alta",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    task = Task.query.filter_by(titulo="Estudar Brasil", user_id=user.id).first()
    assert task is not None
    assert task.concluida is False

    filtered = client.get("/tasks/?status=pending")
    assert filtered.status_code == 200
    assert b"Estudar Brasil" in filtered.data

    toggle_response = client.post(f"/tasks/{task.id}/toggle", follow_redirects=True)
    assert toggle_response.status_code == 200
    db.session.refresh(task)
    assert task.concluida is True
