# PlanejaENEM

Organizador de estudos para o ENEM. Cadastre materias, crie tarefas de estudo e acompanhe seu progresso.

## Stack

- Python 3.12 + Flask
- SQLAlchemy + SQLite
- Flask-Login (autenticacao)
- Flask-WTF (formularios com CSRF)
- Bootstrap 5 (frontend via CDN)
- Docker

## Funcionalidades do MVP

- Registro e login de usuario
- CRUD de materias (nome + cor)
- CRUD de tarefas (titulo, descricao, data prevista, prioridade, status)
- Dashboard com progresso por materia e tarefas pendentes
- Rota `/health` retornando status 200

## Como rodar local

```bash
# Criar e ativar virtualenv
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt

# Criar arquivo .env (ja incluido no repo com valores de dev)
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
│   ├── auth/                # Blueprint de autenticacao
│   ├── main/                # Blueprint do dashboard
│   ├── subjects/            # Blueprint de materias
│   └── tasks/               # Blueprint de tarefas
├── templates/               # Templates Jinja2
├── static/                  # CSS estatico
├── .env                     # Variaveis de ambiente
├── .gitignore
├── requirements.txt
├── run.py                   # Entry point
├── Dockerfile
└── docker-compose.yml
```
