# PlanejaENEM

PlanejaENEM é uma aplicação web de organização de estudos para o ENEM, pensada para ajudar estudantes a gerenciar matérias, tarefas de revisão e acompanhamento de progresso.

## Visão geral

O projeto foi estruturado com Flask, utilizando Blueprints para separar as áreas da aplicação e facilitar manutenção, escalabilidade e clareza no código. A aplicação permite:

- cadastro e autenticação de usuários
- gestão de matérias por usuário
- criação, edição, exclusão e conclusão de tarefas
- acompanhamento do progresso no dashboard
- monitoramento básico de saúde da aplicação via rota `/health`

## Stack

- Python 3.12
- Flask 3.x
- SQLAlchemy
- Flask-Login
- Flask-WTF
- SQLite (ambiente local/dev)
- Bootstrap 5
- Docker
- pytest

## Funcionalidades

- Registro de conta com validação de senha
- Login e logout com proteção de rotas autenticadas
- CRUD de matérias
- CRUD de tarefas com prioridade, data prevista e status
- Dashboard com indicadores de progresso
- Filtros de tarefas por status e matéria
- Proteção CSRF e cabeçalhos de segurança básicos
- Logs em arquivo dentro de `instance/logs`

## Estrutura do projeto

```text
PlanejaENEM/
├── app/
│   ├── __init__.py          # Factory da aplicação e configuração geral
│   ├── extensions.py        # Extensões do Flask (db, login_manager, csrf)
│   ├── models.py            # Modelos: User, Subject e Task
│   ├── auth/
│   │   ├── __init__.py      # Blueprint de autenticação
│   │   ├── forms.py         # Formulários de autenticação e perfil
│   │   └── routes.py        # Rotas de login, registro, logout e perfil
│   ├── main/
│   │   ├── __init__.py      # Blueprint principal
│   │   └── routes.py        # Dashboard e health check
│   ├── subjects/
│   │   ├── __init__.py      # Blueprint de matérias
│   │   ├── forms.py         # Formulário de matéria
│   │   └── routes.py        # CRUD de matérias
│   ├── tasks/
│   │   ├── __init__.py      # Blueprint de tarefas
│   │   ├── forms.py         # Formulário de tarefa
│   │   └── routes.py        # CRUD e toggle de tarefas
│   ├── static/
│   │   └── style.css        # Estilos do projeto
│   └── templates/
│       ├── base.html
│       ├── dashboard.html
│       ├── auth/
│       ├── subjects/
│       └── tasks/
├── instance/
│   └── logs/                # Logs gerados em execução
├── tests/
│   ├── test_auth.py
│   └── test_phase2_quality.py
├── .env                     # Variáveis de ambiente locais
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── README.md
├── requirements.txt
├── run.py                   # Ponto de entrada da aplicação
└── venv/                    # Ambiente virtual local
```

## Pré-requisitos

- Python 3.12
- pip
- Docker e Docker Compose (opcional, para execução em container)

## Configuração local

1. Clone o repositório
2. Crie um ambiente virtual
3. Instale as dependências
4. Configure as variáveis de ambiente
5. Execute a aplicação

### 1) Criar ambiente virtual

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

### 2) Instalar dependências

```bash
pip install -r requirements.txt
```

### 3) Configurar variáveis de ambiente

Crie um arquivo `.env` na raiz com pelo menos:

```env
SECRET_KEY=sua-chave-secreta
FLASK_ENV=development
```

> Em ambiente de desenvolvimento, a aplicação usa valores padrão quando a variável não for informada.

### 4) Executar a aplicação

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

Para rodar a suíte de testes:

```bash
python -m pytest -q
```

Ou, se estiver usando o ambiente virtual:

```bash
venv\Scripts\python -m pytest -q
```

## Boas práticas aplicadas

- uso de Application Factory
- separação por Blueprints
- organização de extensões em módulo próprio
- logging configurado fora da raiz do projeto
- proteção de rotas com login obrigatório
- validações de formulários com WTForms
- uso de diretórios dedicados para logs e instância
- configuração de segurança básica via headers HTTP

## Observações

- O banco local é gerado automaticamente pela aplicação no contexto do Flask.
- O diretório `instance/logs` é usado para armazenar arquivos de log em execução.
- O projeto foi pensado para evoluir com padrões mais organizados e fáceis de manter.

## Status

Aplicação funcional e validada por testes automatizados em ambiente local.
