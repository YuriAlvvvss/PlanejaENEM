# PlanejaENEM 5.0 📚

**PlanejaENEM** é uma aplicação web para organização de estudos direcionada aos candidatos do ENEM. A versão 5.0 adiciona **observabilidade de IA, controle de custos e segurança avançada** — monitorando uso de IA, controlando orçamentos e protegendo contra prompt injection.

1. **O que estudar?**
2. **Qual assunto?**
3. **Qual tipo de estudo?**
4. **Quanto tempo?**
5. **Quando estudar?**
6. **Quando revisar?**
7. **Por que isso foi recomendado?**
8. **Qual deve ser a próxima ação depois do estudo?**

## 🎯 Visão Geral

A aplicação foi desenvolvida com **Flask** seguindo a arquitetura de **Application Factory** com **Blueprints**, separando as responsabilidades em autenticação, dashboard, gestão de matérias, tarefas, planejamento, **análise de desempenho** e **motor de decisão**. O sistema é multiusuário (cada usuário possui seus próprios dados), com armazenamento em **SQLite** por padrão e fácil migração para PostgreSQL.

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
- ✅ **Sistema de Questões**: CRUD completo de questões com enunciado, alternativas (A-E), resposta correta, dificuldade, ano e fonte
- ✅ **Assuntos (Topics)**: Organização de questões por assunto dentro de cada matéria
- ✅ **Registro de Tentativas**: Responder questões com registro de acerto/erro e tempo opcional
- ✅ **Estatísticas de Desempenho**: Aproveitamento por matéria, assunto, dificuldade e área do ENEM
- ✅ **Dashboard de Desempenho**: Página dedicada com gráficos Chart.js, melhor/pior matéria e histórico
- ✅ **PlanejaENEM 3.0**: Sistema de análise de desempenho, domínio por tópico, recomendações e revisão adaptativa
- ✅ **PlanejaENEM 4.0**: Motor de decisão determinístico com recomendações explicáveis

### 🆕 Novidades do 4.0

- ✅ **Decision Engine**: Motor central de decisão que gera recomendações de estudo
- ✅ **Recomendações Explicáveis**: Toda recomendação possui reason codes e explicação
- ✅ **Ranking Determinístico**: Score final baseado em 7 componentes ponderados
- ✅ **Detecção de Conflitos**: Sistema identifica e resolve conflitos automaticamente
- ✅ **Simulação de Planos**: Comparar diferentes cenários de estudo
- ✅ **Modo Debug**: Visualizar scores, pesos e reason codes detalhados
- ✅ **Dashboard 4.0**: Seção "O que estudar agora?" com recomendações
- ✅ **Mapa de Domínio**: Visualização por níveis (crítico, baixo, médio, bom, excelente)
- ✅ **Feedback Loop**: Recálculo automático após cada sessão
- ✅ **Planos Arquivados**: Histórico preservado ao regenerar planos

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
│   ├── models.py                 # Modelos (User, Subject, Task, StudyPlan, StudySession, PasswordResetToken, Topic, Question, QuestionAttempt)
│   ├── auth/                     # Blueprint de autenticação
│   │   ├── forms.py              # RegistrationForm, LoginForm, ProfileForm, ChangePasswordForm, ForgotPasswordForm, ResetPasswordForm
│   │   └── routes.py             # /register, /login, /logout, /profile, /forgot-password, /reset-password, /privacy, /export-data, /delete-account
│   ├── main/                     # Blueprint principal (dashboard)
│   │   ├── routes.py            # /, /weekly-goal, /sessions/<id>/toggle, /health
│   │   └── stats.py             # Cálculo de métricas do dashboard (streak, áreas, gráficos, mastery map)
│   ├── planner/                  # Blueprint de planejamento adaptativo
│   │   ├── __init__.py          # Blueprint registration
│   │   ├── routes.py            # /planner, /planner/<id>/regenerate, /planner/<id>/manual, /planner/replan, /planner/diagnostics
│   │   ├── scoring.py           # Score inteligente por matéria (7 componentes)
│   │   ├── spaced_repetition.py # Revisão espaçada adaptativa (1-30 dias)
│   │   ├── scheduler.py         # Distribuição, balanceamento e tipos de estudo
│   │   ├── services.py          # Orquestração e integração com modelos
│   │   └── validators.py        # Validações e tratamento de casos extremos
│   ├── decision_engine/          # 🆕 Motor de decisão do PlanejaENEM 4.0
│   │   ├── __init__.py          # Exportações públicas
│   │   ├── types.py             # Enums, dataclasses, reason codes
│   │   ├── ranking.py           # Pesos centralizados, FinalScore (7 componentes)
│   │   ├── policies.py          # Detecção e resolução de conflitos
│   │   ├── explanations.py      # Reason codes → texto amigável
│   │   ├── engine.py            # Ciclo completo de decisão
│   │   ├── simulator.py         # Simulação e comparação de planos
│   │   └── routes.py            # Endpoints da API
│   ├── subjects/                 # Blueprint de matérias
│   │   ├── forms.py             # SubjectForm (com área do ENEM e cor)
│   │   └── routes.py            # CRUD de matérias
│   ├── tasks/                    # Blueprint de tarefas
│   │   ├── forms.py             # TaskForm
│   │   └── routes.py            # CRUD de tarefas, filtros e toggle de status
│   ├── questions/                # Blueprint de questões
│   │   ├── __init__.py          # Blueprint registration
│   │   ├── forms.py             # TopicForm, QuestionForm, AnswerForm
│   │   ├── routes.py            # CRUD de assuntos e questões, resposta de questões
│   │   └── services.py          # Lógica de negócio para questões e tentativas
│   ├── performance/             # Blueprint de desempenho
│   │   ├── __init__.py          # Blueprint registration + KnowledgeState import
│   │   ├── routes.py            # Dashboard de desempenho + recomendações
│   │   ├── statistics.py        # Cálculo de estatísticas por matéria/assunto/dificuldade/área
│   │   ├── models.py            # KnowledgeState (estado de conhecimento por tópico)
│   │   ├── mastery.py           # Cálculo de mastery score (0-100) e componentes
│   │   ├── recommendations.py   # Recommendation engine (need score, reason codes)
│   │   └── services.py          # Orquestrador: atualização de KnowledgeState, recomendações
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
│       ├── tasks/
│       │   ├── list.html
│       │   ├── form.html
│       │   └── confirm_delete.html
│       ├── questions/             # Templates de questões
│       │   ├── topics.html       # Lista de assuntos
│       │   ├── topic_form.html   # Formulário de assunto
│       │   ├── confirm_delete_topic.html
│       │   ├── list.html         # Lista de questões
│       │   ├── question_form.html # Formulário de questão
│       │   ├── view.html         # Visualizar e responder questão
│       │   └── confirm_delete_question.html
│       ├── performance/          # Templates de desempenho
│       │   └── overview.html     # Dashboard de desempenho com gráficos
│       └── decision_engine/      # 🆕 Templates do motor de decisão
│           ├── recommendations.html  # "O que estudar agora?"
│           ├── debug.html            # Modo debug com scores detalhados
│           ├── simulate.html         # Simulação e comparação de planos
│           ├── simulation_result.html # Resultado da simulação
│           └── history.html          # Histórico de recomendações
├── docs/                          # 🆕 Documentação do PlanejaENEM 4.0
│   ├── architecture.md           # Arquitetura do sistema
│   ├── scoring.md                # Documentação de scoring e fórmulas
│   ├── recommendation-engine.md  # Motor de recomendação
│   ├── adaptive-planner.md       # Planner adaptativo
│   └── security.md               # Documentação de segurança
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
│   ├── test_phase2_quality.py    # Testes de qualidade
│   ├── test_questions.py         # Testes do módulo de questões
│   ├── test_performance_v3.py    # Testes do PlanejaENEM 3.0 (mastery, recommendations, knowledge state)
│   ├── test_decision_engine.py   # 🆕 Testes determinísticos do motor de decisão (36 testes)
│   └── test_invariants.py        # 🆕 Testes de invariantes (20 testes)
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
python -m pytest tests/test_questions.py -v
python -m pytest tests/test_performance_v3.py -v
python -m pytest tests/test_decision_engine.py -v   # 🆕 Decision Engine
python -m pytest tests/test_invariants.py -v        # 🆕 Invariantes
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
- `GET      /` - Dashboard principal (protegida) - 🆕 Inclui "O que estudar agora?" e Mapa de Domínio
- `POST     /weekly-goal` - Atualizar meta semanal de estudo (horas)
- `POST     /sessions/<id>/toggle` - Marcar/desmarcar conclusão de uma sessão (🆕 atualiza status)
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
- `POST     /planner/<id>/regenerate` - 🆕 Arquiva plano anterior (preserva histórico)
- `POST     /planner/<id>/manual` - Ajuste manual de uma sessão (matéria/anotações)
- `POST     /planner/replan` - Replanejar sessões perdidas
- `GET      /planner/diagnostics` - Diagnóstico de desempenho por área

### 🆕 Decision Engine (`/decision-engine`)
- `GET      /decision-engine/recommendations` - Recomendações atuais com reason codes
- `GET      /decision-engine/api/recommendations` - API JSON das recomendações
- `GET      /decision-engine/debug` - Modo debug com scores, pesos e componentes
- `GET/POST /decision-engine/simulate` - Simular e comparar planos A vs B
- `GET      /decision-engine/history` - Histórico de recomendações e sessões

### Questões (`/questions`)
- `GET      /questions` - Listar questões (filtros: `?subject=<id>`, `?topic=<id>`)
- `GET/POST /questions/new` - Criar questão
- `GET      /questions/<id>` - Visualizar questão
- `GET/POST /questions/<id>/edit` - Editar questão
- `GET/POST /questions/<id>/delete` - Excluir questão (remove tentativas associadas)
- `POST     /questions/<id>/answer` - Responder questão (registra tentativa)
- `GET      /questions/topics` - Listar assuntos
- `GET/POST /questions/topics/new` - Criar assunto
- `GET/POST /questions/topics/<id>/edit` - Editar assunto
- `GET/POST /questions/topics/<id>/delete` - Excluir assunto

### Desempenho (`/performance`)
- `GET      /performance` - Dashboard de desempenho (estatísticas por matéria, assunto, dificuldade, área)

## 📖 Fluxo de Uso

1. **Registrar/Login** em `http://localhost:5000`.
2. **Configurar Matérias** em `/subjects`: nome, cor, prioridade, dificuldade e área do ENEM.
3. **Criar Assuntos** em `/questions/topics`: organize questões por tema dentro de cada matéria.
4. **Cadastrar Questões** em `/questions`: enunciado, alternativas, resposta correta, dificuldade e assunto.
5. **Responder Questões** em `/questions/<id>`: selecione a alternativa e registre o tempo opcional.
6. **Gerenciar Tarefas** em `/tasks`: vincule a uma matéria, defina data prevista e prioridade; marque como concluídas (gera data de revisão).
7. **Definir Meta Semanal** no dashboard (campo "Meta semanal").
8. **Gerar Cronograma** em `/planner`: informe dias disponíveis, faixas horárias, tempo diário e data da prova; ajuste manualmente se necessário e regenere quando quiser.
9. **Acompanhar "O que estudar agora?"** no dashboard: recomendação principal, domínio, tendência, tempo e motivo.
10. **Acompanhar Desempenho** em `/performance`: aproveitamento por matéria, assunto, dificuldade e área do ENEM.
11. **Ver Recomendações Detalhadas** em `/decision-engine/recommendations`: todas as recomendações ordenadas.
12. **Usar Modo Debug** em `/decision-engine/debug`: analise scores, pesos e reason codes.
13. **Simular Planos** em `/decision-engine/simulate`: compare diferentes cenários de estudo.

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
- is_active             # 🆕 Boolean (True = plano atual, False = arquivado)
- generated_at
- last_regenerated_at
```

### StudySession
```python
- id
- plan_id
- user_id
- subject_id            # (não há task_id; a sessão referencia a matéria)
- topic_id              # FK -> Topic (opcional, v3.0)
- session_date          # Date
- start_time            # Time
- end_time              # Time
- duration_minutes
- completed             # Boolean
- completed_at
- priority_score
- session_type          # "teoria" | "exercicios" | "questoes_enem" | "revisao" | "simulado"
- status                # 🆕 "scheduled" | "completed" | "missed" | "rescheduled" | "cancelled"
- manual_override       # ajuste manual
- notes
- reason_codes          # 🆕 reason codes da recomendação
- explanation           # 🆕 explicação legível
- created_at / updated_at
```

### Topic (Assunto)
```python
- id
- nome                    # nome do assunto
- subject_id              # FK -> Subject
- user_id                 # FK -> User (isolamento multiusuário)
- created_at
```

### Question (Questão)
```python
- id
- enunciado               # texto da questão (Text)
- alternativa_a           # alternativa A (String 500)
- alternativa_b           # alternativa B
- alternativa_c           # alternativa C
- alternativa_d           # alternativa D
- alternativa_e           # alternativa E
- resposta_correta        # "A" | "B" | "C" | "D" | "E"
- subject_id              # FK -> Subject
- topic_id                # FK -> Topic (opcional)
- user_id                 # FK -> User (isolamento multiusuário)
- dificuldade             # 1-5
- ano                     # ano da questão (opcional, 2000-2030)
- fonte                   # fonte da questão (opcional, ex: "ENEM 2023")
- created_at
```

### QuestionAttempt (Tentativa)
```python
- id
- user_id                 # FK -> User
- question_id             # FK -> Question
- resposta                # "A" | "B" | "C" | "D" | "E"
- correta                 # Boolean (calculada automaticamente)
- tempo_segundos          # tempo gasto em segundos (opcional)
- attempted_at            # DateTime da tentativa
```

### KnowledgeState (Estado de Conhecimento - v3.0)
```python
- id
- user_id                 # FK -> User (isolamento multiusuário)
- subject_id              # FK -> Subject
- topic_id                # FK -> Topic
- mastery_score           # 0-100 (score de domínio)
- confidence_score        # 0-100 (confiança estatística)
- questions_answered      # total de questões respondidas
- questions_correct       # questões corretas
- questions_wrong         # questões incorretas
- recent_accuracy         # acurácia das últimas 10 tentativas
- historical_accuracy     # acurácia geral
- last_attempt_at         # DateTime da última tentativa
- last_review_at          # DateTime da última revisão
- consecutive_correct     # acertos consecutivos
- consecutive_wrong       # erros consecutivos
- average_response_time   # tempo médio de resposta (segundos)
- trend                   # "improving" | "stable" | "declining"
- updated_at              # DateTime da última atualização
```

## 🧠 PlanejaENEM 4.0 - Motor de Decisão

A versão 4.0 introduz um **motor de decisão determinístico** que transforma dados de desempenho em recomendações de estudo acionáveis e explicáveis.

### Fluxo de Decisão

```
┌─────────────────────────────────────────────────────────────┐
│                    CICLO DE DECISÃO                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. COLETAR DADOS                                          │
│     ├── KnowledgeState (domínio, confiança)                │
│     ├── Subject (dificuldade, prioridade)                  │
│     ├── Topic (nome)                                       │
│     ├── QuestionAttempt (histórico)                        │
│     └── StudySession (sessões perdidas)                    │
│                          ↓                                  │
│  2. CALCULAR SCORES                                        │
│     ├── NeedScore                                          │
│     ├── Weakness                                           │
│     ├── Recency                                            │
│     ├── ExamUrgency                                        │
│     ├── ReviewUrgency                                      │
│     ├── HistoricalImportance                               │
│     └── StudyConsistency                                   │
│                          ↓                                  │
│  3. RANKEAR                                                │
│     └── FinalScore = Σ(componente × peso)                  │
│                          ↓                                  │
│  4. DETECTAR CONFLITOS                                     │
│     ├── Meta semanal impossível                            │
│     ├── Excesso de sessões                                 │
│     ├── Limite diário excedido                             │
│     └── Sem disponibilidade                                │
│                          ↓                                  │
│  5. RESOLVER CONFLITOS                                     │
│     ├── Priorizar revisões atrasadas                       │
│     ├── Reduzir duração                                    │
│     └── Selecionar prioridades mais altas                  │
│                          ↓                                  │
│  6. ALOCAR TEMPO                                           │
│     ├── Respeitar meta semanal                             │
│     ├── Respeitar limite diário                            │
│     └── Distribuir entre assuntos                          │
│                          ↓                                  │
│  7. GERAR RECOMENDAÇÕES                                    │
│     ├── Reason codes                                       │
│     ├── Explicação                                         │
│     ├── Data recomendada                                   │
│     └── Duração                                            │
│                          ↓                                  │
│  8. RETORNAR LISTA ORDENADA                                │
│     └── Ordenada por FinalScore (maior = mais urgente)     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Score Final (FinalScore)

O score final é calculado como uma combinação ponderada de 7 componentes:

```
FinalScore = 0.25 × NeedScore
           + 0.20 × Weakness
           + 0.15 × Recency
           + 0.15 × ExamUrgency
           + 0.10 × ReviewUrgency
           + 0.10 × HistoricalImportance
           + 0.05 × StudyConsistency
```

> **Nota**: Estes pesos são heurísticas determinísticas centralizadas em `app/decision_engine/ranking.py` e podem ser ajustados posteriormente com base em validação empírica. Não utilizam IA generativa, LLM ou machine learning.

### Componentes do Score

| Componente | Peso | Descrição |
|-----------|------|-----------|
| NeedScore | 25% | Necessidade de estudo (domínio inverso + desempenho + dificuldade + ENEM + revisão + confiança) |
| Weakness | 20% | Fraqueza no assunto (inverso do domínio + tendência + erros consecutivos) |
| Recency | 15% | Tempo desde última atividade |
| ExamUrgency | 15% | Proximidade do ENEM |
| ReviewUrgency | 10% | Urgência de revisão |
| HistoricalImportance | 10% | Prioridade e dificuldade definidas pelo usuário |
| StudyConsistency | 5% | Sessões perdidas |

### Reason Codes

O sistema gera códigos de motivo para explicar cada recomendação:

| Código | Significado |
|--------|-------------|
| `low_mastery` | Domínio abaixo de 40% |
| `moderate_mastery` | Domínio entre 40-70% |
| `recent_accuracy_drop` | Queda recente de desempenho |
| `recent_poor_performance` | Desempenho recente abaixo de 50% |
| `performance_declining` | Queda significativa em relação ao histórico |
| `overdue_review` | Revisão atrasada |
| `exam_urgency` | ENEM em menos de 30 dias |
| `high_difficulty` | Matéria com dificuldade >= 4 |
| `low_confidence` | Confiança estatística abaixo de 40% |
| `missed_session` | Sessões perdidas |
| `no_data` | Poucos dados (< 3 questões) |

### Tipos de Ação

| Ação | Quando Recomendada |
|------|-------------------|
| `learn` | Domínio < 40% (teoria urgente) |
| `practice` | Domínio 40-59% (exercícios) |
| `enem_questions` | Domínio 60-74% (questões ENEM) |
| `difficult_questions` | Domínio 75-89% (questões avançadas) |
| `review` | Domínio >= 90% (manutenção) |
| `mock_exam` | Simulados completos |

### Progressão de Aprendizagem

O sistema implementa uma progressão lógica:

```
Domínio < 40% → Teoria + Exercícios Básicos
      ↓
Domínio 40-60% → Exercícios Práticos
      ↓
Domínio 60-75% → Questões ENEM
      ↓
Domínio 75-90% → Questões Difíceis
      ↓
Domínio > 90% → Revisão Espaçada + Manutenção
```

### Detecção e Resolução de Conflitos

O sistema detecta automaticamente:

| Conflito | Severidade | Resolução |
|----------|-----------|-----------|
| Meta semanal impossível | Alta | Reduzir duração das sessões |
| Excesso de sessões por assunto | Média | Manter apenas as N com maior score |
| Limite diário excedido | Alta | Reduzir para caber no limite |
| Sem disponibilidade | Crítica | Alertar o usuário |
| Revisão atrasada + conteúdo novo | Média | Priorizar revisão |
| Desbalanceamento entre assuntos | Baixa | Equilibrar distribuição |

### Dashboard 4.0

O dashboard principal agora inclui:

```
┌─────────────────────────────────────────────────┐
│  🎯 O que estudar agora?                       │
├─────────────────────────────────────────────────┤
│                                                 │
│  Geometria Analítica → Triângulos                │
│                                                 │
│  Domínio: 42%  |  Tendência: ↓  |  Confiança: 65%  │
│                                                 │
│  Recomendação: 50 min de questões ENEM          │
│                                                 │
│  Por quê?                                       │
│  • domínio baixo                                │
│  • desempenho recente caiu                      │
│  • revisão atrasada                             │
│  • ENEM se aproxima                             │
│                                                 │
│  Próximo: Probabilidade — 35 min                │
│  Depois: Funções — 30 min                       │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Mapa de Domínio

Visualização por níveis:

| Faixa | Nível | Cor | Ação |
|-------|-------|-----|------|
| 0-39% | Crítico | Vermelho | Teoria urgente |
| 40-59% | Baixo | Laranja | Exercícios |
| 60-74% | Médio | Amarelo | Questões ENEM |
| 75-89% | Bom | Verde Claro | Questões difíceis |
| 90-100% | Excelente | Verde Escuro | Manutenção |

### Feedback Loop

Após cada sessão de estudo:

```
Sessão Concluída
      ↓
Atualizar KnowledgeState
      ↓
Recalcular MasteryScore
      ↓
Atualizar Tendência
      ↓
Recalcular Necessidade
      ↓
Gerar Novas Recomendações
```

### Modo Debug

O modo debug fornece informações detalhadas sobre o cálculo:

```
======================================================================
PLANEJAENEM 4.0 - MODO DEBUG
======================================================================

Total de tópicos analisados: 15
Total de recomendações: 8
Tempo total recomendado: 480min
Fase de estudo: medium_term
Dias até o ENEM: 45

----------------------------------------------------------------------
RECOMENDAÇÕES ORDENADAS:
----------------------------------------------------------------------

#1 - Matemática → Funções
    Score: 72.50
    Domínio: 35%
    Confiança: 45%
    Ação: practice
    Duração: 40min
    Motivos: Domínio baixo | ENEM próximo

#2 - Português → Interpretação de Texto
    Score: 65.20
    ...
```

### Simulação de Planos

O simulador permite comparar diferentes cenários:

```python
# Plano A: 60min/dia, 300min/semana
# Plano B: 90min/dia, 630min/semana

Resultado:
- Plano A: 65% de cobertura de prioridades
- Plano B: 82% de cobertura de prioridades
- Recomendação: Plano B é mais adequado
```

> **IMPORTANTE**: O sistema NÃO prevê nota do ENEM. Usa linguagem de "cobertura de prioridades" e "adequação ao perfil".

## 🧠 PlanejaENEM 3.0 - Sistema de Análise de Desempenho

A versão 3.0 introduz uma camada completa de análise de desempenho que transforma dados brutos de tentativas em **estado de conhecimento**, **recomendações** e **revisão adaptativa**.

### Fluxo de Dados

```
Questões → Tentativas → Estatísticas → KnowledgeState → Recommendation Engine → Planner
```

### Mastery Score

O score de domínio (0-100) é calculado combinando 6 fatores ponderados:

| Componente | Peso | Descrição |
|-----------|------|-----------|
| Acurácia Geral | 35% | Percentual histórico de acertos |
| Desempenho Recente | 20% | Comparação últimas 10 tentativas vs histórico |
| Dificuldade | 15% | Dificuldade média das questões respondidas |
| Consistência | 10% | Padrão de acertos/erros consecutivos |
| Recência | 10% | Tempo desde última atividade |
| Confiança Estatística | 10% | Quantidade de evidências disponíveis |

> **Nota**: Estes pesos são heurísticas determinísticas e podem ser ajustados posteriormente com base em validação empírica. Não utilizam IA generativa, LLM ou machine learning.

**Fórmula:**
```
mastery = (accuracy × 0.35) + (recent × 0.20) + (difficulty × 0.15) + 
          (consistency × 0.10) + (recency × 0.10) + (confidence × 0.10)
```

### Confiança Estatística

O sistema evita considerar poucas evidências como domínio consolidado:

| Questões Respondidas | Confiança |
|---------------------|-----------|
| 0 | 0% |
| 1 | ~7% |
| 3 | ~21% |
| 10 | ~55% |
| 30 | ~91% |
| 50+ | ~98% |

### Tendência

Compara desempenho recente com histórico:
- **melhorando**: diferença ≥ +5%
- **estável**: diferença entre -5% e +5%
- **piorando**: diferença ≤ -5%

### Revisão Espaçada com Domínio

A revisão agora considera o mastery score real:

| Domínio | Intervalo |
|---------|-----------|
| ≥ 90% | 30 dias |
| 75-89% | 14 dias |
| 60-74% | 7 dias |
| 40-59% | 3 dias |
| < 40% | 1 dia |

O intervalo é ajustado por acertos/erros consecutivos.

## 🧠 Adaptive Planner

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
2. Marca como perdidas (status `missed`)
3. Recalcula a prioridade
4. Reagenda se houver disponibilidade
5. Registra que foi reagendada
6. Não contamina horas estudadas

### Metas Semanais Adaptativas

A meta semanal de minutos é distribuída proporcionalmente entre as matérias:
- Matéria com maior score recebe mais tempo
- Mínimo de 30 min por matéria para garantir cobertura
- Total não excede a meta semanal definida

> Quando o tempo disponível não é suficiente: "Seu tempo disponível não é suficiente para cobrir todas as prioridades." O sistema seleciona apenas as prioridades mais importantes.

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
- **Migração de bancos legados**: `migrate_legacy_database()` em `app/__init__.py` adiciona colunas ausentes (prioridade, dificuldade, area, weekly_goal_minutes, completed_at, next_review_date, status, is_active, etc.) em bancos SQLite existentes.

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

### PlanejaENEM 4.0 (Atual)
- ✅ **Decision Engine**: Motor central de decisão determinístico
- ✅ **Recomendações Explicáveis**: Reason codes e explicações em texto
- ✅ **Ranking Determinístico**: Score final com 7 componentes ponderados
- ✅ **Detecção de Conflitos**: 6 tipos de conflito detectados e resolvidos
- ✅ **Simulação de Planos**: Comparação A vs B com métricas
- ✅ **Modo Debug**: Scores, pesos e componentes detalhados
- ✅ **Dashboard 4.0**: "O que estudar agora?" e Mapa de Domínio
- ✅ **Feedback Loop**: Recálculo automático pós-sessão
- ✅ **Planos Arquivados**: Histórico preservado
- ✅ **Status de Sessões**: scheduled, completed, missed, rescheduled, cancelled

### PlanejaENEM 3.0
- ✅ **KnowledgeState**: Estado de conhecimento por tópico
- ✅ **Mastery Score**: Score de domínio (0-100) com 6 componentes
- ✅ **Confiança Estatística**: Evita conclusões com poucos dados
- ✅ **Tendência**: improving, stable, declining
- ✅ **Recomendação de Próximo Tópico**: Need score com reason codes
- ✅ **Revisão Espaçada**: Intervalos adaptativos baseados em domínio

### Funcionalidades Gerais
- ✅ Autenticação segura (força de senha + lockout)
- ✅ CRUD de matérias (com áreas do ENEM) e tarefas
- ✅ Repetição espaçada adaptativa (1-30 dias baseado em desempenho)
- ✅ Dashboard com métricas, streak e gráficos (Chart.js)
- ✅ **Adaptive Planner**: Score inteligente, balanceamento, tipos de estudo
- ✅ **Replanejamento**: Detecção e reagendamento de sessões perdidas
- ✅ **Diagnóstico**: Análise de desempenho por área do ENEM
- ✅ **Explicabilidade**: Algoritmo pode justificar prioridades
- ✅ Suite de testes automatizados (426 testes)
- ✅ Interface premium (animações, glassmorphism)
- ✅ Pronto para produção com Docker (exige `SECRET_KEY`)
- ✅ **LGPD**: exportação de dados e exclusão de conta
- ✅ **Rate limiting** distribuído (Flask-Limiter)
- ✅ **Password reset** com tokens seguros
- ✅ **Segurança**: nota 8.5/10 (auditoria completa)
- ✅ **Sistema de Questões**: CRUD de questões, assuntos, tentativas e estatísticas
- ✅ **Dashboard de Desempenho**: Gráficos por matéria, assunto, dificuldade e área
- ✅ **Proteção IDOR estendida**: Questões e tentativas protegidas contra acesso cross-user
- ✅ **PlanejaENEM 3.0**: KnowledgeState, mastery score, recomendações, reason codes e revisão adaptativa
- ✅ **PlanejaENEM 4.0**: Decision Engine determinístico com recomendações explicáveis
- ✅ **PlanejaENEM 5.0**: AI Observability, Cost Management e Security (80 testes)

## 📚 Documentação Adicional

- **[SECURITY.md](SECURITY.md)** - Documentação completa de segurança
- **[PREMIUM_UPGRADES.md](PREMIUM_UPGRADES.md)** - Recursos premium, animações e melhorias visuais
- **[docs/architecture.md](docs/architecture.md)** - 🆕 Arquitetura do PlanejaENEM 4.0
- **[docs/scoring.md](docs/scoring.md)** - 🆕 Documentação de scoring e fórmulas
- **[docs/recommendation-engine.md](docs/recommendation-engine.md)** - 🆕 Motor de recomendação
- **[docs/adaptive-planner.md](docs/adaptive-planner.md)** - 🆕 Planner adaptativo
- **[docs/security.md](docs/security.md)** - 🆕 Documentação de segurança detalhada
- **[docs/ai-observability.md](docs/ai-observability.md)** - 🆕 AI Observability, Cost Management e Security
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
- Documente pesos e fórmulas em `docs/scoring.md`

## 📝 Licença

Este projeto é fornecido como está, livre para uso e modificação.

## 👤 Autor

Ferramenta de preparação para o ENEM.

---

**Última atualização**: Agosto 2026 - PlanejaENEM 4.0 (motor de decisão determinístico, recomendações explicáveis, simulação de planos)
