# PlanejaENEM

PlanejaENEM é uma aplicação web para organização de estudos para o ENEM. O projeto ajuda o aluno a registrar matérias, gerenciar tarefas, acompanhar um dashboard de progresso e gerar um cronograma de estudos com base em disponibilidade semanal, tempo diário e data da prova.

## Visão geral

A aplicação foi construída com Flask e segue a arquitetura de Application Factory com Blueprints para separar autenticação, dashboard, matérias, tarefas e planejamento. O sistema foi pensado para uso individual por usuário, com armazenamento local em SQLite por padrão.

### Funcionalidades principais

- cadastro e autenticação de usuários
- login/logout com proteção de rotas autenticadas
- CRUD de matérias
- CRUD de tarefas com prioridade, data prevista e status de conclusão
- dashboard com indicadores de progresso e tarefas pendentes
- geração de cronograma de estudos por dia e faixa horária
- edição manual de sessões do cronograma
- regeneração do plano de estudos
- monitoramento de saúde da aplicação via rota `/health`
- logging em `instance/logs`
- cabeçalhos de segurança básicos e proteção CSRF

## Stack

- Python 3.12
- Flask 3.1.1
- Flask-SQLAlchemy 3.1.1
- Flask-Login 0.6.3
- Flask-WTF 1.2.2
- WTForms 3.2.1
- SQLite
- Bootstrap 5 (via templates)
- Docker / Docker Compose
- pytest 8

## Estrutura do projeto

```text
PlanejaENEM/
├── app/
│   ├── __init__.py            # Factory da aplicação e configuração
│   ├── extensions.py          # db, login_manager e csrf
│   ├── models.py              # User, Subject, Task, StudyPlan e StudySession
│   ├── auth/
│   │   ├── __init__.py        # Blueprint de autenticação
│   │   ├── forms.py           # Formulários de registro, login e perfil
│   │   └── routes.py          # login, logout, cadastro e perfil
│   ├── main/
│   │   ├── __init__.py        # Blueprint principal
│   │   └── routes.py          # dashboard e health check
│   ├── planner/
│   │   ├── __init__.py        # Blueprint do planejamento
│   │   └── routes.py          # geração e regeneração do cronograma
│   ├── subjects/
│   │   ├── __init__.py        # Blueprint de matérias
│   │   ├── forms.py           # Formulário de matéria
│   │   └── routes.py          # CRUD de matérias
│   ├── tasks/
│   │   ├── __init__.py        # Blueprint de tarefas
│   │   ├── forms.py           # Formulário de tarefa
│   │   └── routes.py          # CRUD e toggle de tarefas
│   ├── static/
│   │   └── style.css          # Estilos da interface
│   └── templates/
│       ├── base.html
│       ├── dashboard.html
│       ├── auth/
│       ├── planner/
│       ├── subjects/
│       └── tasks/
├── instance/
│   ├── logs/                  # arquivos de log em execução
│   └── planejaenem.db         # banco SQLite padrão
├── tests/
│   ├── test_auth.py
│   ├── test_planner.py
│   └── test_phase2_quality.py
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── README.md
├── requirements.txt
├── run.py                     # entrypoint da aplicação
└── .env                       # opcional para variáveis locais
```

## Requisitos

- Python 3.12
- pip
- Docker e Docker Compose (opcional)

## Configuração local

### 1) Clonar o repositório

```bash
git clone <url-do-repositorio>
cd PlanejaENEM
```

### 2) Criar ambiente virtual

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

Linux/macOS:

```bash
source venv/bin/activate
```

### 3) Instalar dependências

```bash
pip install -r requirements.txt
```

### 4) Configurar variáveis de ambiente

O projeto usa valores padrão caso `.env` não exista, mas você pode criar uma variável local opcional:

```env
SECRET_KEY=sua-chave-secreta
FLASK_ENV=development
DATABASE_URL=sqlite:////caminho/para/instance/planejaenem.db
```

### 5) Executar a aplicação

```bash
python run.py
```

A aplicação ficará disponível em:

```text
http://localhost:5000
```

## Execução com Docker

```bash
docker-compose up --build
```

Acesse:

```text
http://localhost:5000
```

## Testes

Para executar a suíte de testes:

```bash
python -m pytest -q
```

## Fluxo principal da aplicação

1. O usuário cria uma conta e faz login.
2. Adiciona matérias e prioridades/dificuldades para cada disciplina.
3. Cria tarefas de estudo com data prevista e nível de prioridade.
4. Acesse o módulo de planejamento e configure:
   - dias disponíveis
   - horários disponíveis
   - tempo diário de estudo
   - data da prova
5. O sistema gera sessões de estudo distribuídas ao longo do período.
6. O dashboard exibe métricas de progresso, tarefas pendentes e próximas entregas.

## Observações importantes

- O banco usa SQLite por padrão em `instance/planejaenem.db`.
- Os logs da aplicação são gravados em `instance/logs/planejaenem.log`.
- A rota `/health` responde com status `ok` para verificação simples de disponibilidade.
- A aplicação foi validada com testes automatizados e a suíte atual está passando.

## Status

Aplicação funcional, com autenticação, gestão de estudos, dashboard e planejamento de cronograma implementados e validados por testes.
