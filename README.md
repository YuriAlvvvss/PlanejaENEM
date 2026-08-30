# PlanejaENEM 📚

**PlanejaENEM** é uma aplicação web para organização de estudos direcionada aos candidatos do ENEM. A plataforma permite registrar matérias (organizadas por área do ENEM), gerenciar tarefas com repetição espaçada, acompanhar o progresso em tempo real por meio de métricas e gráficos, e gerar um cronograma personalizado de estudos com base na disponibilidade semanal, tempo diário e data da prova.

## 🎯 Visão Geral

A aplicação foi desenvolvida com **Flask** seguindo a arquitetura de **Application Factory** com **Blueprints**, separando as responsabilidades em autenticação, dashboard, gestão de matérias, tarefas e planejamento. O sistema é multiusuário (cada usuário possui seus próprios dados), com armazenamento em **SQLite** por padrão e fácil migração para PostgreSQL.

### ✨ Funcionalidades Principais

- ✅ **Autenticação segura**: Cadastro e login com validação de força de senha e bloqueio temporário após tentativas falhas (brute-force protection)
- ✅ **Recuperação de senha**: Solicitação via email com tokens seguros (1h de validade)
- ✅ **Perfil do usuário**: Atualização de nome/e-mail e troca de senha (exige senha atual)
- ✅ **Gestão de Matérias**: CRUD completo com cor, prioridade (1-5), dificuldade (1-5) e **área do ENEM** (Linguagens, Humanas, Natureza, Matemática, Redação)
- ✅ **Inferência automática de área**: A área é deduzida a partir do nome da matéria quando não informada
- ✅ **Gestão de Tarefas**: CRUD com prioridade (baixa/média/alta), data prevista, filtros por status/matéria/busca e alternância de conclusão
- ✅ **Repetição espaçada adaptativa**: Intervalos de revisão baseados no desempenho (1, 3, 7, 14 ou 30 dias)
- ✅ **Dashboard**: Métricas de progresso, gráficos (Chart.js), sequência de estudos (streak), cobertura por área e revisões pendentes
- ✅ **Meta semanal**: Definição de objetivo de horas de estudo por semana
- ✅ **Planejamento Adaptativo**: Geração automática de cronograma com score inteligente, balanceamento e tipos de estudo
- ✅ **Replanejamento**: Detecção automática de sessões perdidas e reagendamento inteligente
- ✅ **Diagnóstico**: Análise de desempenho por área do ENEM
- ✅ **Edição Manual**: Ajuste de sessões do cronograma (matéria e anotações) com flag de override
- ✅ **Regeneração**: Refazer o plano de estudos conforme necessário
- ✅ **Conclusão de sessões**: Marcar sessões como concluídas diretamente no dashboard/planner
- ✅ **Health Check**: Monitoramento via rota `/health`
- ✅ **Logging**: Logs em `instance/logs/planejaenem.log` com rotação
- ✅ **Segurança**: Cabeçalhos de segurança (CSP, HSTS em produção), proteção CSRF, cookies seguros, session protection "strong", rate limiting e proteção IDOR
- ✅ **LGPD**: Centro de privacidade, exportação de dados e exclusão de conta
- ✅ **Interface Premium**: Animações, glassmorphism e tema moderno (veja [PREMIUM_UPGRADES.md](PREMIUM_UPGRADES.md))

## 🛠 Stack Tecnológico

| Componente | Tecnologia |
|-----------|-----------|
| **Backend** | Python 3.12 |
| **Framework Web** | Flask 3.1.1 |
| **ORM & Banco de Dados** | Flask-SQLAlchemy 3.1.1 + SQLite (compatível com PostgreSQL) |
| **Autenticação** | Flask-Login 0.6.3 |
| **Rate Limiting** | Flask-Limiter 4.1.1 |
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
│   ├── __init__.py               # Factory da aplicação, config e segurança (headers, CSP, HSTS, rate limiting)
│   ├── extensions.py             # Extensões (db, login_manager, csrf, limiter)
│   ├── authz.py                  # Autorização centralizada (get_user_subject, user_owns_*, etc.)
│   ├── areas.py                  # Áreas do ENEM e inferência automática de área
│   ├── models.py                 # Modelos (User, Subject, Task, StudyPlan, StudySession, PasswordResetToken)
│   ├── auth/                     # Blueprint de autenticação
│   │   ├── forms.py              # RegistrationForm, LoginForm, ProfileForm, ChangePasswordForm, ForgotPasswordForm, ResetPasswordForm
│   │   └── routes.py             # /register, /login, /logout, /profile, /forgot-password, /reset-password, /privacy, /export-data, /delete-account
│   ├── main/                     # Blueprint principal (dashboard)
│   │   ├── routes.py            # /, /weekly-goal, /sessions/<id>/toggle, /health
│   │   └── stats.py             # Cálculo de métricas do dashboard (streak, áreas, gráficos)
│   ├── planner/                  # Blueprint de planejamento adaptativo
│   │   ├── __init__.py          # Blueprint registration
│   │   ├── routes.py            # /planner, /planner/<id>/regenerate, /planner/<id>/manual, /planner/replan, /planner/diagnostics
│   │   ├── scoring.py           # Score inteligente por matéria (7 componentes)
│   │   ├── spaced_repetition.py # Revisão espaçada adaptativa (1-30 dias)
│   │   ├── scheduler.py         # Distribuição, balanceamento e tipos de estudo
│   │   ├── services.py          # Orquestração e integração com modelos
│   │   └── validators.py        # Validações e tratamento de casos extremos
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
│       │   ├── profile.html
│       │   ├── forgot_password.html
│       │   ├── reset_password.html
│       │   ├── privacy.html
│       │   └── delete_account.html
│       ├── includes/
│       │   └── flashes.html      # Mensagens flash
│       ├── planner/
│       │   ├── planner.html      # Configuração + cronograma adaptativo
│       │   └── diagnostics.html  # Diagnóstico de desempenho por área
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
│   ├── test_security.py          # Testes de segurança e autorização (IDOR, session fixation, CSRF)
│   ├── test_dashboard.py         # Testes do dashboard
│   ├── test_planner.py           # Testes de planejamento original
│   ├── test_scoring.py           # Testes do módulo de scoring
│   ├── test_spaced_repetition.py # Testes de revisão espaçada
│   ├── test_scheduler.py         # Testes do scheduler
│   ├── test_validators.py        # Testes de validadores
│   ├── test_adaptive_planner.py  # Testes de integração do planner adaptativo
│   └── test_phase2_quality.py    # Testes de qualidade
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── run.py                        # Entrypoint
├── SECURITY.md                   # Documentação de segurança
├── README.md
├── PREMIUM_UPGRADES.md
├── .env.example                  # Exemplo de variáveis de ambiente
├── .env                          # Variáveis de ambiente (ignorado no git)
└── .gitignore
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
- `RATELIMIT_STORAGE_URI`: URI do armazenamento de rate limiting (padrão: `memory://`; produção: `redis://host:6379`)
- `USE_HSTS`: `1` para habilitar HSTS (recomendado atrás de reverse proxy com HTTPS)

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
python -m pytest tests/test_security.py -v
python -m pytest tests/test_dashboard.py -v
python -m pytest tests/test_planner.py -v
python -m pytest tests/test_scoring.py -v
python -m pytest tests/test_spaced_repetition.py -v
python -m pytest tests/test_scheduler.py -v
python -m pytest tests/test_validators.py -v
python -m pytest tests/test_adaptive_planner.py -v
python -m pytest tests/test_phase2_quality.py -v
```

## 🔗 Rotas Principais

### Autenticação (`/auth`)
- `GET/POST /auth/register` - Cadastro (com validação de força de senha)
- `GET/POST /auth/login` - Login (com bloqueio após 5 falhas em 5 min)
- `GET     /auth/logout` - Logout
- `GET/POST /auth/profile` - Perfil (atualizar dados e trocar senha; exige senha atual)
- `GET/POST /auth/forgot-password` - Solicitação de redefinição de senha
- `GET/POST /auth/reset-password/<token>` - Redefinição de senha via token
- `GET     /auth/privacy` - Centro de privacidade e dados
- `GET     /auth/export-data` - Exportar todos os dados do usuário (JSON)
- `GET/POST /auth/delete-account` - Excluir conta e todos os dados

### Dashboard (`/`)
- `GET      /` - Dashboard principal (protegida)
- `POST     /weekly-goal` - Atualizar meta semanal de estudo (horas)
- `POST     /sessions/<id>/toggle` - Marcar/desmarcar conclusão de uma sessão
- `GET      /health` - Status da aplicação (público)

### Matérias (`/subjects`)
- `GET      /subjects` - Listar
- `GET/POST /subjects/new` - Criar
- `GET/POST /subjects/<id>/edit` - Editar
- `GET      /subjects/<id>/delete` - Confirmar exclusão (página de confirmação)
- `POST     /subjects/<id>/delete` - Excluir (bloqueia se houver tarefas vinculadas)

### Tarefas (`/tasks`)
- `GET      /tasks` - Listar (filtros: `?status=pending|done`, `?subject=<id>`, `?q=<busca>`)
- `GET/POST /tasks/new` - Criar
- `GET/POST /tasks/<id>/edit` - Editar
- `GET/POST /tasks/<id>/delete` - Excluir
- `POST     /tasks/<id>/toggle` - Alternar conclusão (define `next_review_date`)

### Planejamento (`/planner`)
- `GET/POST /planner` - Visualizar e gerar cronograma adaptativo (POST gera o plano)
- `POST     /planner/<id>/regenerate` - Regenerar plano existente
- `POST     /planner/<id>/manual` - Ajuste manual de uma sessão (matéria/anotações)
- `POST     /planner/replan` - Replanejar sessões perdidas
- `GET      /planner/diagnostics` - Diagnóstico de desempenho por área

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
- session_type          # "teoria" | "exercicios" | "questoes_enem" | "revisao" | "simulado"
- manual_override       # ajuste manual
- notes
- created_at / updated_at
```

## 🧠 Adaptive Planner v2

O PlanejaENEM possui um sistema de planejamento adaptativo determinístico (sem dependência de LLM) que gera cronogramas inteligentes baseados em múltiplos fatores.

### Score Inteligente por Matéria

Cada matéria recebe um **score de necessidade** (0-100) calculado por 7 componentes ponderados:

| Componente | Peso | Descrição |
|-----------|------|-----------|
| Prioridade | 15% | Prioridade definida pelo usuário (1-5) |
| Dificuldade | 15% | Dificuldade da matéria (1-5) |
| Desempenho | 20% | Aproveitamento em tarefas concluídas (inverso) |
| Proximidade ENEM | 15% | Dias até a prova (quanto mais perto, maior o score) |
| Revisão | 10% | Tempo desde a última revisão |
| Revisões atrasadas | 10% | Quantidade de revisões atrasadas |
| Tarefas pendentes | 15% | Proporção de tarefas pendentes |

**Fórmula:**
```
score = (priority × 0.15) + (difficulty × 0.15) + (performance × 0.20) + 
        (exam_proximity × 0.15) + (revision × 0.10) + (overdue × 0.10) + 
        (pending × 0.15)
```

O algoritmo é **determinístico**: o mesmo conjunto de dados sempre produz o mesmo resultado.

### Revisão Espaçada Adaptativa

O intervalo entre revisões é ajustado automaticamente baseado no desempenho:

| Desempenho | Intervalo |
|-----------|-----------|
| Excelente (≥85%) | 30 dias |
| Bom (≥70%) | 14 dias |
| Médio (≥50%) | 7 dias |
| Baixo (≥30%) | 3 dias |
| Muito Baixo (<30%) | 1 dia |

O sistema identifica automaticamente:
- **Revisão futura**: data agendada para depois de hoje
- **Revisão para hoje**: data é hoje
- **Revisão atrasada**: data já passou (aumenta a prioridade da matéria)

### Fases de Estudo

O algoritmo adapta o foco baseado na proximidade da prova:

| Fase | Dias até o ENEM | Foco Principal |
|------|----------------|----------------|
| Longo Prazo | >120 dias | Teoria e construção de base |
| Médio Prazo | 30-120 dias | Teoria + exercícios + questões |
| Reta Final | <30 dias | Questões, revisão e simulados |

### Tipos de Sessão

Cada sessão de estudo é classificada em um tipo:

| Tipo | Descrição |
|------|-----------|
| `teoria` | Estudo de conceitos e conteúdo novo |
| `exercicios` | Prática com exercícios variados |
| `questoes_enem` | Foco em questões do ENEM |
| `revisao` | Revisão de conteúdo já estudado |
| `simulado` | Simulado completo |

O tipo é selecionado automaticamente baseado na fase e desempenho do aluno.

### Balanceamento entre Matérias

O algoritmo evita concentração excessiva:
- **Limite de sessões consecutivas**: máx. 2 sessões da mesma matéria seguidas
- **Diversidade de áreas**: prioriza alternar entre áreas do ENEM
- **Proporcionalidade**: tempo distribuído conforme necessidade calculada

### Replanejamento

Quando sessões são perdidas (data passada e não concluída):
1. Detecta automaticamente as sessões perdidas
2. Marca como concluídas com anotação de reagendamento
3. Cria novas sessões com bônus de prioridade
4. Redistribui respeitando a disponibilidade do usuário

### Metas Semanais Adaptativas

A meta semanal de minutos é distribuída proporcionalmente entre as matérias:
- Matéria com maior score recebe mais tempo
- Mínimo de 30 min por matéria para garantir cobertura
- Total não excede a meta semanal definida

### Diagnóstico

O sistema gera um diagnóstico de desempenho por área do ENEM:
- Média de aproveitamento por área
- Detalhamento por matéria
- Classificação: Excelente (≥85%), Bom (≥70%), Médio (≥50%), Baixo (≥30%), Muito Baixo (<30%)

### Explicabilidade

O algoritmo pode explicar por que uma matéria recebeu determinada prioridade:
```
Por que Matemática recebeu mais tempo?
• Desempenho: 54%
• Dificuldade: alta
• Prioridade: alta
• 2 revisões atrasadas
• 8 tarefas pendentes
• ENEM se aproxima
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
- ✅ **Rate Limiting**: Flask-Limiter com limites configuráveis (login 10/min, registro 5/min, planner 10/min). Configurável via `RATELIMIT_STORAGE_URI`.
- ✅ **Recuperação de senha**: token seguro com expiração de 1h, uso único, hash armazenado.
- ✅ **Reautenticação**: troca de senha e alteração de email exigem confirmação da senha atual.
- ✅ **Regeneração de sessão**: sessão regenerada em login, logout e troca de senha.
- ✅ **Cookies/Sessões**: HTTP-only, SameSite=Lax; Secure em produção; `session_protection="strong"`; sessão permanente de 30 min.
- ✅ **Cabeçalhos**: CSP (com `base-uri 'self'` e `form-action 'self'`), X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, COOP/COEP; HSTS em HTTPS/produção (configurável via `USE_HSTS`).
- ✅ **Rotas**: todas as rotas autenticadas usam `@login_required`; consultas sempre filtram por `user_id`.
- ✅ **IDOR**: proteção via funções centralizadas em `app/authz.py` com testes automatizados.
- ✅ **LGPD**: exportação de dados (JSON) e exclusão de conta com confirmação de senha.
- ✅ **Logs seguros**: emails e dados sensíveis mascarados; senhas e tokens nunca logados.
- ✅ **Docker não-root**: container roda como `appuser`.
- ✅ **Input validation**: `MAX_CONTENT_LENGTH=2MB`, `MAX_FORM_MEMORY_SIZE=512KB`, `MAX_FORM_PARTS=50`.
- ✅ **Open redirect protection**: função `_safe_next_url()` valida redirecionamentos.

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
- ✅ Repetição espaçada adaptativa (1-30 dias baseado em desempenho)
- ✅ Dashboard com métricas, streak e gráficos (Chart.js)
- ✅ **Adaptive Planner v2**: Score inteligente, balanceamento, tipos de estudo
- ✅ **Replanejamento**: Detecção e reagendamento de sessões perdidas
- ✅ **Diagnóstico**: Análise de desempenho por área do ENEM
- ✅ **Explicabilidade**: Algoritmo pode justificar prioridades
- ✅ Suite de testes automatizados (252 testes)
- ✅ Interface premium (animações, glassmorphism)
- ✅ Pronto para produção com Docker (exige `SECRET_KEY`)
- ✅ **LGPD**: exportação de dados e exclusão de conta
- ✅ **Rate limiting** distribuído (Flask-Limiter)
- ✅ **Password reset** com tokens seguros
- ✅ **Segurança**: nota 8.5/10 (auditoria completa)

## 📚 Documentação Adicional

- **[SECURITY.md](SECURITY.md)** - Documentação completa de segurança
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

**Última atualização**: Agosto 2026 - Segurança e LGPD implementadas
