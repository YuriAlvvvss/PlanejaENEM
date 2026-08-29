# PlanejaENEM

Organizador de estudos para o ENEM. Cadastre matérias, crie tarefas de estudo e acompanhe seu progresso.

## Stack

- Python 3.12 + Flask
- SQLAlchemy + SQLite
- Flask-Login (autenticação)
- Flask-WTF (formulários com CSRF)
- Bootstrap 5 (frontend via CDN)
- Docker

## Funcionalidades do MVP

- Registro e login de usuário
- CRUD de matérias (nome + cor)
- CRUD de tarefas (título, descrição, data prevista, prioridade, status)
- Dashboard com progresso por matéria e tarefas pendentes
- Rota `/health` retornando status 200

## Como rodar local

```bash
# Criar e ativar virtualenv
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# Instalar dependências
pip install -r requirements.txt

# Criar arquivo .env (já incluso no repo com valores de dev)
# SECRET_KEY=change-me-in-production

# Rodar
python run.py
```

Acesse: http://localhost:5000

## Como rodar via Docker

```bash
docker-compose up --build
```

Acesse: http://localhost:5000

## Estrutura do projeto

```
PlanejaENEM/
├── app/
│   ├── __init__.py          # Application Factory
│   ├── models.py            # User, Subject, Task
│   ├── auth/                # Blueprint de autenticação
│   ├── main/                # Blueprint do dashboard
│   ├── subjects/            # Blueprint de matérias
│   └── tasks/               # Blueprint de tarefas
├── templates/               # Templates Jinja2
├── static/                  # CSS estático
├── .env                     # Variáveis de ambiente
├── .gitignore
├── requirements.txt
├── run.py                   # Entry point
├── Dockerfile
└── docker-compose.yml