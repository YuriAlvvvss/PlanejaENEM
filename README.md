# PlanejaENEM 📚

**PlanejaENEM** é uma aplicação web para organização de estudos direcionada aos candidatos do ENEM. A plataforma permite registrar matérias (organizadas por área do ENEM), gerenciar tarefas com repetição espaçada, acompanhar o progresso em tempo real por meio de métricas e gráficos, e gerar um cronograma personalizado de estudos com base na disponibilidade semanal, tempo diário e data da prova.

## 🎯 Visão Geral

A aplicação foi desenvolvida com **Flask** seguindo a arquitetura de **Application Factory** com **Blueprints**, separando as responsabilidades em autenticação, dashboard, gestão de matérias, tarefas e planejamento. O sistema é multiusuário (cada usuário possui seus próprios dados), com armazenamento em **SQLite** por padrão e fácil migração para PostgreSQL.

### ✨ Funcionalidades Principais

- ✅ **Autenticação segura**: Cadastro e login com validação de força de senha e bloqueio temporário após tentativas falhas (brute-force protection)
- ✅ **Perfil do usuário**: Atualização de nome/e-mail e troca de senha
- ✅ **Gestão de Matérias**: CRUD completo com cor, prioridade (1-5), dificuldade (1-5) e **área do ENEM** (Linguagens, Humanas, Natureza, Matemática, Redação)
- ✅ **Inferência automática de área**: A área é deduzida a partir do nome da matéria quando não informada
- ✅ **Gestão de Tarefas**: CRUD com prioridade (baixa/média/alta), data prevista, filtros por status/matéria/busca e alternância de conclusão
- ✅ **Repetição espaçada**: Ao concluir uma tarefa, calcula-se automaticamente a próxima data de revisão (7 dias)
- ✅ **Dashboard**: Métricas de progresso, gráficos (Chart.js), sequência de estudos (streak), cobertura por área e revisões pendentes
- ✅ **Meta semanal**: Definição de objetivo de horas de estudo por semana
- ✅ **Planejamento Inteligente**: Geração automática de sessões de estudo por dia e faixa horária, priorizando matérias mais importantes/difíceis
- ✅ **Edição Manual**: Ajuste de sessões do cronograma (matéria e anotações) com flag de override
- ✅ **Regeneração**: Refazer o plano de estudos conforme necessário
- ✅ **Conclusão de sessões**: Marcar sessões como concluídas diretamente no dashboard/planner
- ✅ **Health Check**: Monitoramento via rota `/health`
- ✅ **Logging**: Logs em `instance/logs/planejaenem.log` com rotação
- ✅ **Segurança**: Cabeçalhos de segurança (CSP, HSTS em produção), proteção CSRF, cookies seguros e session protection "strong"
- ✅ **Interface Premium**: Animações, glassmorphism e tema moderno (veja [PREMIUM_UPGRADES.md](PREMIUM_UPGRADES.md))

## 🛠 Stack Tecnológico

| Componente | Tecnologia |
|-----------|-----------|
| **Backend** | Python 3.12 |
| **Framework Web** | Flask 3.1.1 |
| **ORM & Banco de Dados** | Flask-SQLAlchemy 3.1.1 + SQLite (compatível com PostgreSQL) |
| **Autenticação** | Flask-Login 0.6.3 |
| **Formulários** | Flask-WTF 1.2.2 + WTForms 3.2.1 |
| **Validação de Email** | email-validator 2.2.0 |
| **Variáveis de Ambiente** | python-dotenv 1.1.0 |
| **Web Server** | Werkzeug 3.1.3 |
| **Frontend** | Bootstrap 5 + Chart.js + HTML/CSS/JavaScript |
| **Containerização** | Docker / Docker Compose |
| **Testes** | pytest 8.3.3 |

## 📁 Estrutura do Projeto

```
PlanejaENEM/
├── app/                           # Pacote principal da aplicação
│   ├── __init__.py               # Factory da aplicação, config e segurança (headers, CSP, HSTS)
│   ├── extensions.py             # Extensões (db, login_manager, csrf)
│   ├── areas.py                  # Áreas do ENEM e inferência automática de área
│   ├── models.py                 # Modelos (User, Subject, Task, StudyPlan, StudySession)
│   ├── auth/                     # Blueprint de autenticação
│   │   ├── forms.py              # RegistrationForm, LoginForm, ProfileForm, ChangePasswordForm
│   │   └── routes.py             # /register, /login, /logout, /profile (com lockout de login)
│   ├── main/                     # Blueprint principal (dashboard)
│   │   ├── routes.py            # /, /weekly-goal, /sessions/<id>/toggle, /health
│   │   └── stats.py             # Cálculo de métricas do dashboard (streak, áreas, gráficos)
│   ├── planner/                  # Blueprint de planejamento
│   │   └── routes.py            # /planner, /planner/<id>/regenerate, /planner/<id>/manual
│   ├── subjects/                 # Blueprint de matérias
│   │   ├── forms.py             # SubjectForm (com área do ENEM e cor)
│   │   └── routes.py            # CRUD de matérias
│   ├── tasks/                    # Blueprint de tarefas
│   │   ├── forms.py             # TaskForm
│   │   └── routes.py            # CRUD de tarefas, filtros e toggle de status
│   ├── static/                   # Arquivos estáticos
│   │   ├── app.js                # JavaScript da aplicação
│   │   ├── dashboard-charts.js   # Gráficos do dashboard (Chart.js)
│   │   ├── style.css             # Estilos padrão
│   │   └── premium.css           # Estilos premium (animações, glassmorphism)
│   └── templates/                # Templates HTML
│       ├── base.html             # Template base (sidebar, topbar, tema)
│       ├── dashboard.html        # Dashboard principal com métricas e gráficos
│       ├── auth/
│       │   ├── login.html
│       │   ├── register.html
│       │   └── profile.html
│       ├── includes/
│       │   └── flashes.html      # Mensagens flash
│       ├── planner/
│       │   └── planner.html
│       ├── subjects/
│       │   ├── list.html
│       │   ├── form.html
│       │   └── confirm_delete.html
│       └── tasks/
│           ├── list.html
│           ├── form.html
│           └── confirm_delete.html
├── instance/                      # Runtime (ignorado no git)
│   ├── logs/                     # Logs da aplicação
│   └── planejaenem.db            # Banco SQLite (criado automaticamente)
├── tests/                        # Suite de testes
│   ├── test_auth.py              # Testes de autenticação
│   ├── test_dashboard.py         # Testes do dashboard
│   ├── test_planner.py           # Testes de planejamento
│   └── test_phase2_quality.py    # Testes de qualidade
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── run.py                        # Entrypoint
├── run.sh / run.bat              # Scripts de execução
├── README.md
├── PREMIUM_UPGRADES.md
└── .env                          # Variáveis de ambiente (ignorado no git)
```

## 📋 Pré-requisitos

- **Python** 3.12 ou superior
- **pip**
- **Git**
- **Docker e Docker Compose** (opcional)
- Navegador moderno com suporte a Bootstrap 5 e Chart.js

## 🚀 Instalação e Execução

### Localmente

#### 1️⃣ Clonar e preparar ambiente

```bash
git clone <url-do-repositorio>
cd PlanejaENEM
python -m venv venv
```

Ativar o ambiente virtual:
- **Windows:** `venv\Scripts\activate`
- **Linux/macOS:** `source venv/bin/activate`

#### 2️⃣ Instalar dependências

```bash
pip install -r requirements.txt
```

#### 3️⃣ Configurar variáveis de ambiente (opcional)

O projeto usa valores padrão caso `.env` não exista. Crie um `.env` na raiz para personalizar:

```env
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=uma-chave-secreta-bem-longa
DATABASE_URL=sqlite:///instance/planejaenem.db
PORT=5000
FLASK_DEBUG=0
```

**Variáveis disponíveis:**
- `FLASK_APP`: Entrypoint da aplicação (`run.py`)
- `FLASK_ENV`: `development` (padrão) ou `production`
- `SECRET_KEY`: Assinatura de sessões. **Obrigatória em produção** (a app encerra se ausente em `production`)
- `DATABASE_URL`: URL do banco (padrão: SQLite local)
- `PORT`: Porta da aplicação (padrão: 5000)
- `FLASK_DEBUG`: Modo debug (0 ou 1)
- `SESSION_COOKIE_SECURE`: `1` para cookies seguros em produção (também ativado automaticamente quando `FLASK_ENV=production`)

> ⚠️ Em produção, `SECRET_KEY` é obrigatória e cookies/sessões passam a ser `Secure`; o cabeçalho HSTS (`Strict-Transport-Security`) é emitido quando a requisição é HTTPS.

#### 4️⃣ Executar

```bash
python run.py
```

Acesse `http://localhost:5000`.

### Com Docker

```bash
docker-compose up --build
```

Acesse `http://localhost:5000`. O volume `./instance` persiste o banco. Para parar: `docker-compose down`.

## 🧪 Testes

```bash
python -m pytest -q
```

Com cobertura:

```bash
python -m pytest --cov=app --cov-report=html
```

Testes específicos:

```bash
python -m pytest tests/test_auth.py -v
python -m pytest tests/test_dashboard.py -v
python -m pytest tests/test_planner.py -v
python -m pytest tests/test_phase2_quality.py -v
```

## 🔗 Rotas Principais

### Autenticação (`/auth`)
- `GET/POST /auth/register` - Cadastro (com validação de força de senha)
- `GET/POST /auth/login` - Login (com bloqueio após 5 falhas em 5 min)
- `GET     /auth/logout` - Logout
- `GET/POST /auth/profile` - Perfil (atualizar dados e trocar senha)

### Dashboard (`/`)
- `GET      /` - Dashboard principal (protegida)
- `POST     /weekly-goal` - Atualizar meta semanal de estudo (horas)
- `POST     /sessions/<id>/toggle` - Marcar/desmarcar conclusão de uma sessão
- `GET      /health` - Status da aplicação (público)

### Matérias (`/subjects`)
- `GET      /subjects` - Listar
- `GET/POST /subjects/new` - Criar
- `GET/POST /subjects/<id>/edit` - Editar
- `GET/POST /subjects/<id>/delete` - Excluir (bloqueia se houver tarefas vinculadas)

### Tarefas (`/tasks`)
- `GET      /tasks` - Listar (filtros: `?status=pending|done`, `?subject=<id>`, `?q=<busca>`)
- `GET/POST /tasks/new` - Criar
- `GET/POST /tasks/<id>/edit` - Editar
- `GET/POST /tasks/<id>/delete` - Excluir
- `POST     /tasks/<id>/toggle` - Alternar conclusão (define `next_review_date`)

### Planejamento (`/planner`)
- `GET/POST /planner` - Visualizar e gerar cronograma (POST gera o plano)
- `POST     /planner/<id>/regenerate` - Regenerar plano existente
- `POST     /planner/<id>/manual` - Ajuste manual de uma sessão (matéria/anotações)

## 📖 Fluxo de Uso

1. **Registrar/Login** em `http://localhost:5000`.
2. **Configurar Matérias** em `/subjects`: nome, cor, prioridade, dificuldade e área do ENEM.
3. **Gerenciar Tarefas** em `/tasks`: vincule a uma matéria, defina data prevista e prioridade; marque como concluídas (gera data de revisão).
4. **Definir Meta Semanal** no dashboard (campo "Meta semanal").
5. **Gerar Cronograma** em `/planner`: informe dias disponíveis, faixas horárias, tempo diário e data da prova; ajuste manualmente se necessário e regenere quando quiser.
6. **Acompanhar Progresso** no dashboard: taxa de conclusão, streak, cobertura por área, sessões do dia, revisões pendentes e gráficos de horas estudadas.

## 📊 Modelos de Dados

### User
```python
- id
- nome                  # nome do usuário
- email                 # único
- senha_hash            # hash bcrypt (Werkzeug)
- weekly_goal_minutes   # meta semanal (padrão 600 min)
- data_criacao
```

### Subject (Matéria)
```python
- id
- nome
- cor                   # cor hexadecimal (ex: #3B82F6)
- prioridade            # 1-5
- dificuldade           # 1-5
- area                  # área do ENEM (linguagens, humanas, natureza, matematica, redacao, outro)
- user_id
- data_criacao
```
Propriedades úteis: `progress_percent`, `priority_score`, `area_label`, `total_tasks`, `completed_tasks`.

### Task (Tarefa)
```python
- id
- titulo
- descricao
- subject_id
- user_id
- data_prevista         # Date (opcional)
- concluida             # Boolean
- prioridade            # "baixa" | "media" | "alta"
- completed_at         # DateTime (quando concluída)
- next_review_date      # Date (revisão espaçada, +7 dias)
- data_criacao
```

### StudyPlan
```python
- id
- user_id
- exam_date             # Date (data da prova)
- daily_minutes         # tempo diário de estudo
- available_days        # String (ex: "seg,qua,sex")
- available_hours       # String (ex: "08:00-10:00,14:00-16:00")
- generated_at
- last_regenerated_at
```

### StudySession
```python
- id
- plan_id
- user_id
- subject_id            # (não há task_id; a sessão referencia a matéria)
- session_date          # Date
- start_time            # Time
- end_time              # Time
- duration_minutes
- completed             # Boolean
- completed_at
- priority_score
- manual_override       # ajuste manual
- notes
- created_at / updated_at
```

## ⚙️ Configuração & Pontos Importantes

### Banco de Dados
- Padrão: SQLite em `instance/planejaenem.db` (criado automaticamente na primeira execução).
- Compatível com PostgreSQL: basta ajustar `DATABASE_URL` (ex: `postgresql://usuario:senha@host:5432/planejaenem`).
- **Migração de bancos legados**: `migrate_legacy_database()` em `app/__init__.py` adiciona colunas ausentes (prioridade, dificuldade, area, weekly_goal_minutes, completed_at, next_review_date, etc.) em bancos SQLite existentes.

### Logging
- Gravado em `instance/logs/planejaenem.log` com `RotatingFileHandler` (10 MB × 10 backups).
- Nível configurável em `setup_logging()` (`app/__init__.py`).

### Segurança
- ✅ **CSRF**: ativado em todos os formulários (Flask-WTF).
- ✅ **Senhas**: hash via Werkzeug; cadastro exige força mínima (8+ caracteres, maiúscula, minúscula e número).
- ✅ **Proteção de login**: bloqueio após 5 tentativas falhas em 5 minutos (por IP e por e-mail).
- ✅ **Cookies/Sessões**: HTTP-only, SameSite=Lax; Secure em produção; `session_protection="strong"`; sessão permanente de 30 min.
- ✅ **Cabeçalhos**: CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, COOP/COEP; HSTS apenas em HTTPS/produção.
- ✅ **Rotas**: todas as rotas autenticadas usam `@login_required`.

### Health Check
- `GET /health` retorna `{"status": "ok"}` para monitoramento (sem autenticação).

## 🐛 Troubleshooting

- **ModuleNotFoundError: 'flask'**: ative o venv e rode `pip install -r requirements.txt`.
- **Porta em uso**: `run.py` lê a porta da variável `PORT` (padrão 5000). Defina `PORT=5001` no `.env` ou no ambiente antes de `python run.py`.
- **Banco não criado / colunas faltando**: o banco e as colunas são criados/migrados automaticamente. Para resetar: remova `instance/planejaenem.db` e reinicie.
- **Testes falhando**: garanta o venv ativado e nenhuma instância rodando; use `python -m pytest -v`.

## 🚦 Status do Projeto

- ✅ Autenticação segura (força de senha + lockout)
- ✅ CRUD de matérias (com áreas do ENEM) e tarefas
- ✅ Repetição espaçada e revisões
- ✅ Dashboard com métricas, streak e gráficos (Chart.js)
- ✅ Planejamento inteligente + ajuste manual
- ✅ Suite de testes automatizados
- ✅ Interface premium (animações, glassmorphism)
- ✅ Pronto para produção com Docker (exige `SECRET_KEY`)

## 📚 Documentação Adicional

- **[PREMIUM_UPGRADES.md](PREMIUM_UPGRADES.md)** - Recursos premium, animações e melhorias visuais
- Docstrings em português e modelo normalizado
- Scripts de inicialização: `run.py`, `run.sh`, `run.bat`

## 🤝 Contribuindo

1. Fork do repositório
2. Branch de feature (`git checkout -b feature/nova-funcionalidade`)
3. Commit (`git commit -m 'Adiciona nova funcionalidade'`)
4. Push (`git push origin feature/nova-funcionalidade`)
5. Pull Request

### Diretrizes
- Mantenha a arquitetura de Blueprints por módulo
- Escreva testes para novas funcionalidades
- Campos, rotas e mensagens em português
- Atualize o README quando necessário

## 📝 Licença

Este projeto é fornecido como está, livre para uso e modificação.

## 👤 Autor

Ferramenta de preparação para o ENEM.

---

**Última atualização**: Agosto 2026
