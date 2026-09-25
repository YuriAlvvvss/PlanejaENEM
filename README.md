# PlanejaENEM 5.x 📚

**PlanejaENEM** é uma aplicação web para organização de estudos direcionada aos candidatos do ENEM. Responde, de forma determinística e explicável:

1. **O que estudar?**
2. **Qual assunto?**
3. **Qual tipo de estudo?**
4. **Quanto tempo?**
5. **Quando estudar?**
6. **Quando revisar?**
7. **Por que isso foi recomendado?**
8. **Qual deve ser a próxima ação depois do estudo?**

> **Regra de ouro (5.x):** a IA generativa **NUNCA é a fonte da verdade**. Banco de dados, estatísticas, regras determinísticas, `KnowledgeState` e `Decision Engine` continuam sendo a fonte da verdade. A IA apenas **gera, explica, resume e personaliza** — sempre com fallback determinístico quando desligada ou indisponível.

Estado atual: **setembro/2026 (branch `main` + working tree)** — núcleo 3.0/4.0 preservado + **AI Gateway (OpenRouter)**, **questões via IA**, **avaliação adaptativa REST + HTML**, **2FA TOTP (opt-in)**, **busca global**, **filtros/paginação em Tarefas/Questões/Desempenho/Avaliação**, **badges no dashboard**, **preferências de aparência/notificação** e **CRUD de Matérias reabilitado**.

## 🎯 Visão Geral

Aplicação **Flask** com **Application Factory** + **Blueprints**, multiusuário (isolamento por `user_id`), **SQLite** por padrão (migração fácil para PostgreSQL), CSRF, rate limiting, headers de segurança e LGPD.

### ✨ Funcionalidades Principais

**Conta e segurança**
- ✅ Cadastro/login com força de senha, lockout anti brute-force (5 tentativas/5 min), regeneração de sessão, `session_protection="strong"`, sessão de 30 min
- ✅ Recuperação de senha com token seguro (hash, 1h, uso único)
- ✅ Perfil (nome/e-mail/senha com reautenticação), centro de privacidade, exportação JSON ampliada, exclusão de conta em ordem filha→pai com rollback (LGPD)
- ✅ **2FA TOTP opt-in** (`app/auth/two_factor.py`, `pyotp`): atrás da flag `TWOFA_ENABLED` (default `false`, 404 quando desligado)
  - `GET/POST /auth/two-factor/setup` → gera `secret` + 10 backup codes (sessão) → `POST /auth/two-factor/setup/confirm` ativa com senha + código
  - `GET/POST /auth/two-factor/verify` (sessão pendente de 10 min, lockout, aceita backup code de uso único)
  - `POST /auth/two-factor/disable` (exige senha + código; invalida backups restantes)
- ✅ **Preferências no perfil** (`POST /auth/appearance`, `POST /auth/notification-preference`): `theme` (light/dark), `density` (comfortable/compact), `default_task_status` (all/pending/done), `email_opt_in` (digest on-site; e-mail real futuro)
- ✅ Toggle de tema no topbar via `POST /auth/appearance` (`app/static/app.js`)

**Matérias (catálogo oficial + CRUD reabilitado)**
- ✅ **12 matérias oficiais auto-provisionadas** no primeiro acesso (`app/subjects/catalog.py`): Português, Literatura, Inglês, História, Geografia, Filosofia, Sociologia, Biologia, Química, Física, Matemática, Redação
- ✅ **CRUD reabilitado** (`GET/POST /subjects/new`, `/<id>/edit`, `/<id>/delete`): validação de nome duplicado por usuário + bloqueio de exclusão com tarefas/assuntos/questões/sessões vinculadas
- ✅ Área do ENEM + inferência automática (`app/areas.py`), cor, prioridade/dificuldade

**Tarefas**
- ✅ CRUD, toggle com `next_review_date` (+7 dias)
- ✅ Lista com `?status=all|pending|done` (**explícito vence**; sem ele usa `default_task_status` do perfil), `?subject=<id>`, `?q=` (título+descrição, LIKE com escape), `?periodo=all|hoje|atrasadas|7d|14d|sem_data`, paginação `?page=&per_page=` (5–50, default 20) + contadores `pending/done/total`
- ✅ **Recomendação por IA em 2 passos** (sem persistência automática):
  - `POST /tasks/recommend` → sugere título/descrição/matéria/duração/motivo
  - `POST /tasks/recommend/confirm` → persiste só após confirmação explícita
  - Fallback determinístico quando IA desligada; validação `available_minutes` 15–720

**Questões (criação só via IA; manual continua 404)**
- ✅ Lista com `?subject=&topic=&status=all|pending|done&dificuldade=1-5&q=&page=&per_page=` (filtros inválidos ignorados, nunca 500), separação **Pendentes / Concluídas** via `get_attempts_map` (sem N+1) + contadores
- ✅ **Tentativa única** por questão (`uq_attempt_user_question`); segunda tentativa bloqueada com aviso
- ✅ Timer de resposta (`session["question_started:<id>"]` + campo hidden `tempo_segundos` como fallback)
- ✅ Resposta gera **explicação personalizada por IA** (`ExplanationGenerator` com mastery/trend do `KnowledgeState`) e atualiza `KnowledgeState` em commit único (`commit=False` + 1 `commit`)
- ✅ **Geração por IA via modal** (`Gerar com IA` → `POST /questions/generate` com `subject_id`, `topic_id` opcional, `quantidade` 1/3/5) — `questions.js`
- ✅ `GET/POST /questions/new` e `/<id>/edit` → **404 intencional**; exclusão mantida
- ✅ Assuntos (Topics) com CRUD completo por matéria; `services.py` com validação de posse (matéria do usuário, assunto da matéria) e flag `commit` para transações atômicas

**Desempenho (3.0 + filtros)**
- ✅ `KnowledgeState` por tópico, mastery 0–100 (6 componentes), confiança, tendência, revisão adaptativa 1/3/7/14/30 dias
- ✅ `GET /performance` com filtros compartilháveis `?subject=<id>&area=<chave|all>&periodo=all|7d|30d|90d` (inválidos ignorados), drill-down mastery/trend via `ks_map` (1 query), tempo médio + evolução cumulativa p/ gráfico
- ✅ Feedback textual por IA (`FeedbackGenerator`)
- ✅ `POST /performance/refresh` (era GET) recalcula `KnowledgeState` + flash

**Dashboard / UX**
- ✅ Métricas, streak, cobertura por área, gráficos Chart.js, “O que estudar agora?”, mapa de domínio, glassmorphism/animações (`premium.css`), JS dedicado (`app.js`, `questions.js`, `question-answer.js`, `dashboard-charts.js`)
- ✅ **Conquistas derivadas** (`compute_badges` em `app/main/stats.py`, puras sem DB): streak 3/7/14, 10/50 questões, mira afiada 80% (mín. 10 tentativas), explorador (5 assuntos), expert (≥90% em 1 assunto) — conta nova começa tudo bloqueado
- ✅ Cards de rotina linkam filtros (`periodo=hoje|atrasadas|14d`, `status=done`); `build_dashboard_stats` com queries escopadas por usuário + log de exceção real

**Busca global (nova)**
- ✅ `GET /search?q=&type=all|subject|topic|task|question` (`app/main/routes.py` + `app/templates/search.html` + busca no topbar em `base.html`)
- ✅ LIKE com escape (`%_\\`), limite 25 por grupo, isolamento total por `user_id`, empty-state (“Encontre algo…”) e no-result (“Nenhum resultado encontrado”)

**Planner adaptativo + Cronograma**
- ✅ Score de necessidade, fases (longo/médio/reta final), tipos (`teoria`, `exercicios`, `questoes_enem`, `revisao`, `simulado`), balanceamento, replanejamento de perdidas, diagnósticos por área
- ✅ **Orientação de tipo de estudo por IA** (`PlannerRecommender`, com fallback) — IA nunca cria datas/horários
- ✅ **Revisão personalizada por IA**: `POST /planner/review` (`topic_id`, `duration_minutes`) via `ReviewGenerator`
- ✅ Melhorias recentes de UX no template `planner/planner.html` + CSS premium (ver últimos commits `melhorias na aba "Cronograma"`)

**Decision Engine (4.0, mantido)**
- ✅ Recomendações explicáveis com reason codes, ranking de 7 componentes, detecção/resolução de 6 conflitos, simulação A vs B, modo debug, mapa de domínio, feedback loop, planos arquivados
- ✅ `GET /decision-engine/history` agora **paginado** (`?page=&per_page=`, compat com `?limit=` antigo); redirects corrigidos para `planner.planner`

**Avaliação adaptativa (5.x, REST + HTML)**
- ✅ REST JSON (login + rate limit + anti-IDOR): `POST /assessment/start` (5–30, `subject_id` validado por posse), `GET /assessment/<id>/next`, `POST /assessment/<id>/answer` (`{assessment_question_id, resposta A-E, tempo_segundos?}`), `POST /assessment/<id>/complete`, `GET /assessment/<id>/status`, `GET /assessment/list?status=&limit=&offset=` (status whitelist, limit 1–100)
- ✅ Hardening em `services.py`: `target_questions` coagido a int/clamp, resposta validada A–E, `tempo_segundos` clamp 0–3600 + teto pelo tempo real desde `presented_at` (+30s tolerância), espelho em `QuestionAttempt` sem violar tentativa única (reutiliza existente), `update_knowledge_state` tolerante a `ValueError`
- ✅ **Camada HTML P2.1** (`app/assessment/web.py`, mesmo blueprint `/assessment`, sem colidir com REST):
  - `GET /assessment/` — hub com filtro `?status=all|active|completed|abandoned`, paginação `?page=&per_page=` (5–20), card “Em andamento”, `ks_count` com empty-state CTA, digest on-site (atrasadas+revisões) só se `email_opt_in`
  - `POST /assessment/new` — inicia via form (5–30 + matéria opcional)
  - `GET /assessment/<id>` — jogador 1 questão/vez com timer em sessão; fallback `pending_generation.html` sem 500
  - `POST /assessment/<id>/respond` — PRG com validação A–E
  - `GET /assessment/<id>/result` — idempotente via `complete_assessment`
  - `POST /assessment/<id>/abandon` — active → abandoned
- ✅ Dificuldade inicial por mastery médio + ajuste ±0,5/1,0 por acerto/erro, sem saltos bruscos

**AI Observability / Custos / Segurança**
- ✅ `AIClient` central (httpx síncrono), `chat` + `chat_structured` (JSON robusto, remove markdown), retry exponencial com jitter, tratamento 429/5xx/timeout, timeouts separados por feature
- ✅ Modelos separados: `OPENROUTER_MODEL` (chat) e `OPENROUTER_STRUCTURED_MODEL` (JSON)
- ✅ `CostEstimator`, `UsageTracker` → tabela `ai_usage`, `AIRateLimiter` por feature/hora, enforcement de budget diário/mensal (essenciais nunca bloqueiam)
- ✅ `sanitizer` (~25 padrões de prompt injection) + `build_safe_prompt`, `output_validator` por tipo (text/question/explanation/feedback/review); output bruto nunca vai direto ao banco
- ✅ Cache do `QuestionGenerator` (TTL 1h, 20/hora por usuário), validação e sanitização de lote

## 🆕 O que mudou desde o README anterior (working tree atual)

- CRUD de Matérias **reabilitado** (antes 404 intencional) com anti-duplicada + guard de vinculados
- Questões/Tarefas/Desempenho/Avaliação/History com **filtros + paginação** compartilháveis
- **Busca global** `GET /search` + topbar + `tests/test_search.py`
- **2FA TOTP** completo atrás de `TWOFA_ENABLED` + `TwoFactorBackupCode` + `pyotp==2.9.0`
- **Perfil**: aparência (tema/densidade/filtro inicial) + preferência de notificação (digest on-site)
- **Dashboard**: 8 badges + queries escopadas + links de filtro
- **Assessment HTML** (`web.py` + 4 templates) sobre os mesmos services do REST
- `POST /performance/refresh` (breaking: era GET), blueprint único `assessment_bp`, `conftest.py` ignorando `scripts/*` manuais
- Suite: **844 testes coletados** (era 838); `test_questions.py` reescrito para o comportamento vigente

## 🛠 Stack Tecnológico

| Componente | Tecnologia |
|-----------|-----------|
| **Backend** | Python 3.12 |
| **Framework Web** | Flask 3.1.1 |
| **ORM & Banco** | Flask-SQLAlchemy 3.1.1 + SQLite (compatível com PostgreSQL) |
| **Autenticação** | Flask-Login 0.6.3 |
| **2FA** | pyotp 2.9.0 (TOTP + backup codes) |
| **Rate Limiting HTTP** | Flask-Limiter 4.1.1 |
| **Formulários** | Flask-WTF 1.2.2 + WTForms 3.2.1 |
| **Validação de Email** | email-validator 2.2.0 |
| **Env** | python-dotenv 1.1.0 |
| **Servidor** | Werkzeug 3.1.3 |
| **Cliente IA** | httpx 0.28.1 (OpenRouter `/chat/completions`) |
| **Frontend** | Bootstrap 5 + Chart.js + JS próprio |
| **Container** | Docker / Docker Compose (não-root `appuser`) |
| **Testes** | pytest 8.3.3 |

## 📁 Estrutura do Projeto (estado atual)

```
PlanejaENEM/
├── app/
│   ├── __init__.py            # Factory, config, headers, migração legada, registra AI + blueprints
│   ├── extensions.py          # db, login_manager, csrf, limiter
│   ├── authz.py               # Autorização centralizada anti-IDOR
│   ├── areas.py               # Áreas ENEM + inferência
│   ├── models.py              # User (+theme/density/default_task_status/email_opt_in/totp_*), TwoFactorBackupCode, PasswordResetToken, Subject, Task, StudyPlan, StudySession, Topic, Question, QuestionAttempt (única por user/question)
│   ├── ai/                    # 5.x AI Gateway
│   │   ├── client.py          # AIClient (chat, chat_structured, retry, 429, timeouts por feature)
│   │   ├── config.py          # AIConfig + load_ai_config()
│   │   ├── schemas.py         # ChatRequest/Response, StructuredChatResponse, UsageInfo
│   │   ├── prompts.py         # PROMPT_VERSION + builders (questões enxutas p/ economizar tokens)
│   │   ├── question_generator.py  # Lote 1-5, cache TTL 1h, 20/h, validação
│   │   ├── explanation_generator.py # Explicação pós-resposta (summary, concept, steps, mistake, tip)
│   │   ├── feedback_generator.py    # Feedback de desempenho (/performance)
│   │   ├── review_generator.py      # Revisão personalizada (/planner/review)
│   │   ├── task_recommender.py      # 1 tarefa executável + fallback + confirmação
│   │   ├── planner_recommender.py   # Só study_type por matéria + fallback
│   │   ├── sanitizer.py       # sanitize_user_content, has_injection_attempt, build_safe_prompt
│   │   ├── output_validator.py# validate_*_output + sanitize_output
│   │   ├── validators.py      # validate_question / batch / sanitize_question
│   │   ├── rate_limiter.py    # AIRateLimiter por feature+usuário
│   │   ├── cost_estimator.py  # estimate_cost / monthly
│   │   ├── usage.py           # UsageTracker (record, budget, cost_summary)
│   │   ├── models.py          # AIUsage
│   │   └── exceptions.py      # AIDisabled, AIConfiguration, AIProvider, AIRateLimit, AIValidation, AITimeout
│   ├── assessment/            # Avaliação adaptativa (REST + HTML)
│   │   ├── __init__.py        # Blueprint único assessment_bp (/assessment)
│   │   ├── engine.py          # Dificuldade inicial + ajuste determinístico
│   │   ├── services.py        # start/next/answer/complete + validações + espelho QuestionAttempt
│   │   ├── policies.py        # Resultado, sequência de dificuldade
│   │   ├── models.py          # Assessment, AssessmentQuestion
│   │   ├── routes.py          # REST JSON /assessment/* (login + rate limit + anti-IDOR)
│   │   └── web.py             # 🆕 HTML: / (hub), /new, /<id> (play), /<id>/respond, /<id>/result, /<id>/abandon
│   ├── decision_engine/       # 4.0 ranking, policies, explanations, engine, simulator, routes (history paginado)
│   ├── performance/           # 3.0 statistics (since/subject), mastery, recommendations, services, KnowledgeState, routes com filtros
│   ├── planner/               # scoring, spaced_repetition, scheduler, services (com PlannerRecommender), validators
│   ├── questions/             # routes (generate/answer IA-only + filtros/paginação), services (filtros + commit flag + posse), forms
│   ├── subjects/              # routes CRUD reabilitado + catalog.py (12 oficiais)
│   ├── tasks/                 # routes (CRUD + filtros/periodo/paginação + recommend/confirm) + forms
│   ├── auth/                  # login, perfil, reset, 2FA (two_factor.py + forms + routes), appearance, notification-preference
│   ├── main/                  # dashboard/stats (badges)/health + busca global /search
│   ├── static/                # app.js (tema/sidebar), questions.js (modal IA), question-answer.js (timer), dashboard-charts.js, style.css (density-compact), premium.css
│   └── templates/             # base (sidebar + top-search + theme-toggle), dashboard (badges), auth (profile + two_factor_*), planner, subjects, tasks, questions (filtros/paginação), performance (filtros), decision_engine, assessment/ (index/play/result/pending_generation), search.html
├── docs/                      # architecture, scoring, recommendation-engine, adaptive-planner, security, ai-observability
├── scripts/                   # Manuais (fora da suite via conftest.py): benchmark_ai.py, test_ai_connection.py, test_structured_output.py
├── tests/                     # 844 coletados: auth (+2FA/prefs), search, dashboard/badges, planner/scoring/scheduler/validators/adaptive, questions (answer_flow, generation_route), AI (gateway, usage, explanation, feedback, review, question_generator), assessment (REST+regras), decision_engine, invariants, performance_v3 (filtros), security…
├── instance/                  # Runtime (ignorado): planejaenem.db + logs/planejaenem.log
├── Dockerfile / docker-compose.yml / requirements.txt (inclui pyotp) / run.py / run.sh / run.bat
├── conftest.py / .env.example (inclui TWOFA_ENABLED) / SECURITY.md / PREMIUM_UPGRADES.md / README.md
```

## 📋 Pré-requisitos

- Python 3.12+, pip, Git
- Docker + Compose (opcional)
- Conta OpenRouter + créditos **somente se for usar IA** (sem IA o app roda com fallbacks)
- Navegador moderno (Bootstrap 5 + Chart.js)

## 🚀 Instalação e Execução

### Localmente

```bash
git clone <url-do-repositorio>
cd PlanejaENEM
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
python run.py
# http://localhost:5000
```

### Com Docker

```bash
docker-compose up --build
# http://localhost:5000 — volume ./instance persiste banco + logs
docker-compose down
```

### Configurar variáveis (`.env`)

Mínimo sem IA (funciona com fallbacks):

```env
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=uma-chave-secreta-bem-longa
DATABASE_URL=sqlite:///instance/planejaenem.db
PORT=5000
FLASK_DEBUG=0
AI_ENABLED=false
TWOFA_ENABLED=false
```

Com IA (OpenRouter):

```env
AI_ENABLED=true
OPENROUTER_API_KEY=sua-chave
OPENROUTER_MODEL=nvidia/nemotron-3-ultra:free
OPENROUTER_STRUCTURED_MODEL=nvidia/nemotron-3-ultra:free
AI_BASE_URL=https://openrouter.ai/api/v1
AI_TIMEOUT=30
AI_STRUCTURED_TIMEOUT=12
AI_STRUCTURED_MAX_RETRIES=0
AI_TASK_TIMEOUT=8
AI_MAX_RETRIES=2
AI_MAX_TOKENS=2048
AI_MAX_QUESTIONS_PER_REQUEST=5
AI_MAX_QUESTIONS_PER_HOUR=20
AI_COST_PER_1K_INPUT_TOKENS=0.00015
AI_COST_PER_1K_OUTPUT_TOKENS=0.0006
AI_MAX_EXPLANATIONS_PER_HOUR=30
AI_MAX_REVIEWS_PER_HOUR=20
AI_MAX_FEEDBACK_PER_HOUR=20
AI_DAILY_BUDGET_USD=5.00
AI_MONTHLY_BUDGET_USD=100.00
```

2FA (opt-in, default off):

```env
TWOFA_ENABLED=false
# true → ativa /auth/two-factor/* (requer pyotp instalado)
```

Outras: `SESSION_COOKIE_SECURE=1`, `RATELIMIT_STORAGE_URI=memory://` (prod: `redis://…`), `USE_HSTS=1` (HTTPS/prod). Em `production`, `SECRET_KEY` é obrigatória.

Diagnóstico manual da IA (fora do pytest):

```bash
python scripts/test_ai_connection.py
python scripts/test_structured_output.py
python scripts/benchmark_ai.py
```

## 🧪 Testes

```bash
python -m pytest -q
python -m pytest --collect-only -q   # conta atual: 844 coletados
python -m pytest --cov=app --cov-report=html
```

Exemplos:

```bash
python -m pytest tests/test_auth.py tests/test_security.py -v
python -m pytest tests/test_search.py -v
python -m pytest tests/test_question_answer_flow.py tests/test_question_generation_route.py -v
python -m pytest tests/test_ai_gateway.py tests/test_ai_usage.py -v
python -m pytest tests/test_explanation_generator.py tests/test_feedback_generator.py tests/test_review_generator.py -v
python -m pytest tests/test_assessment.py tests/test_decision_engine.py tests/test_invariants.py -v
python -m pytest tests/test_performance_v3.py tests/test_adaptive_planner.py -v
```

> `conftest.py` na raiz ignora `scripts/test_ai_connection.py`, `scripts/test_structured_output.py` e `scripts/benchmark_ai.py` (diagnósticos manuais, rode com `python scripts/…`).

## 🔗 Rotas Principais (estado atual)

### Autenticação (`/auth`)
- `GET/POST /auth/register`, `GET/POST /auth/login` (lockout), `GET /auth/logout`
- `GET/POST /auth/profile`, `POST /auth/appearance` (tema/densidade/filtro tarefas), `POST /auth/notification-preference` (digest on-site)
- `GET/POST /auth/two-factor/setup`, `POST /auth/two-factor/setup/confirm`, `GET/POST /auth/two-factor/verify`, `POST /auth/two-factor/disable` (404 se `TWOFA_ENABLED=false`)
- `GET/POST /auth/forgot-password`, `GET/POST /auth/reset-password/<token>`
- `GET /auth/privacy`, `GET /auth/export-data` (ampliado), `GET/POST /auth/delete-account` (ordem FK + rollback)

### Dashboard / Busca (`/`)
- `GET /` — métricas, streak, badges, áreas, gráficos, “O que estudar agora?”, mapa de domínio
- `GET /search?q=&type=all|subject|topic|task|question` — busca global escopada (25/grupo)
- `POST /weekly-goal`, `POST /sessions/<id>/toggle`, `GET /health` → `{"status":"ok"}`

### Matérias (`/subjects`) — catálogo + CRUD
- `GET /subjects` — lista (auto-provisiona as 12 oficiais na primeira visita)
- `GET/POST /subjects/new`, `/<id>/edit` — com anti-duplicada por usuário
- `GET/POST /<id>/delete` — bloqueia se houver tarefas/assuntos/questões/sessões

### Tarefas (`/tasks`)
- `GET /tasks` (`?status=pending|done|all`, `?subject=<id>`, `?periodo=all|hoje|atrasadas|7d|14d|sem_data`, `?q=<busca>`, `?page=&per_page=`), `GET/POST /tasks/new`, `/<id>/edit`, `/<id>/delete`, `POST /<id>/toggle`
- `POST /tasks/recommend` (`{available_minutes}`) → sugestão sem persistir
- `POST /tasks/recommend/confirm` (`{title, description, subject_id, duration_minutes}`) → persiste

### Questões (`/questions`) — criação só via IA
- `GET /questions` (`?subject=<id>`, `?topic=<id>`, `?status=all|pending|done`, `?dificuldade=1-5`, `?q=<busca>`, `?page=&per_page=`) — Pendentes + Concluídas
- `GET /questions/<id>` — ver/responder (timer + aviso de tentativa única)
- `POST /questions/<id>/answer` — tentativa única; gera explicação IA e atualiza `KnowledgeState`
- `POST /questions/generate` (JSON `{subject_id, topic_id?, quantidade: 1|3|5}`) — 201 com questões, 400 validação, 404 matéria/assunto, 429 limite, 503 IA desligada, 502/422 falha IA
- `GET/POST /questions/new`, `/<id>/edit` → **404 intencional** (use Gerar com IA)
- `GET/POST /<id>/delete`, assuntos: `GET /questions/topics`, `/topics/new`, `/topics/<id>/edit`, `/topics/<id>/delete`

### Desempenho (`/performance`)
- `GET /performance` (`?subject=<id>&area=<chave|all>&periodo=all|7d|30d|90d`) — stats + KnowledgeState + recomendações + feedback IA + mastery/trend + tempo médio/evolução
- `POST /performance/refresh` — recalcula `KnowledgeState` (GET agora 405)

### Planejamento (`/planner`)
- `GET/POST /planner`, `POST /planner/<id>/regenerate` (arquiva), `POST /planner/<id>/manual`, `POST /planner/replan`, `GET /planner/diagnostics`
- `POST /planner/review` (JSON `{topic_id, duration_minutes}`) — revisão via IA

### Avaliação adaptativa (`/assessment`, login)
- HTML: `GET /assessment/` (`?status=&page=&per_page=`), `POST /assessment/new`, `GET /assessment/<id>`, `POST /assessment/<id>/respond`, `GET /assessment/<id>/result`, `POST /assessment/<id>/abandon`
- REST JSON: `POST /assessment/start` (`{target_questions 5-30, subject_id?}`), `GET /assessment/<id>/next`, `POST /assessment/<id>/answer` (`{assessment_question_id, resposta A-E, tempo_segundos?}`), `POST /assessment/<id>/complete`, `GET /assessment/<id>/status`, `GET /assessment/list?status=&limit=&offset=`

### Decision Engine (`/decision-engine`)
- `GET /decision-engine/recommendations`, `GET /decision-engine/api/recommendations`, `GET /decision-engine/debug`, `GET/POST /decision-engine/simulate`, `GET /decision-engine/history?page=&per_page=` (compat `?limit=`)

## 📖 Fluxo de Uso (atual)

1. Registro/login → catálogo de 12 matérias já aparece em `/subjects` (crie/edite extras se quiser).
2. Ajuste tema/densidade/filtro inicial e notificações em `/auth/profile`; ative 2FA se `TWOFA_ENABLED=true`.
3. Crie Assuntos em `/questions/topics`.
4. Em `/questions`, filtre por status/dificuldade/busca e clique **Gerar com IA** (matéria + assunto opcional + 1/3/5) — requer `AI_ENABLED=true`.
5. Responda em `/questions/<id>` (1 tentativa, timer). Veja explicação IA e gabarito.
6. Gerencie `/tasks` (use `periodo`, busca e paginação) ou peça `Recomendação IA` (confirme para salvar).
7. Use a busca global no topbar (`/search`) para pular entre matérias/assuntos/tarefas/questões.
8. Defina meta semanal no dashboard; acompanhe badges, “O que estudar agora?”, `/performance` (filtre por área/período) e `/decision-engine/recommendations`.
9. Gere cronograma em `/planner` (tipo de estudo pode vir da IA, datas continuam determinísticas).
10. (Opcional) Rode avaliação pelo hub `/assessment/` → `play` → `respond` → `result` (ou via REST).
11. Replaneje perdidas em `/planner/replan`; regenere/arquive quando precisar.

## 📊 Modelos de Dados (resumo)

- **User**: `id, nome, email (único), senha_hash, weekly_goal_minutes (600), email_opt_in, theme (dark), density (comfortable), default_task_status (all), totp_secret?, totp_enabled, data_criacao`
- **TwoFactorBackupCode**: `id, user_id, code_hash, used, created_at` (10 por ativação, uso único)
- **Subject**: `id, nome (único por user), cor, prioridade 1-5, dificuldade 1-5, area, user_id` (+ `progress_percent`, `area_label`)
- **Task**: `id, titulo, descricao, subject_id, user_id, data_prevista, concluida, prioridade, completed_at, next_review_date`
- **StudyPlan**: `id, user_id, exam_date, daily_minutes, available_days, available_hours, is_active, generated_at, last_regenerated_at`
- **StudySession**: `id, plan_id, user_id, subject_id, topic_id?, session_date, start/end_time, duration_minutes, completed, completed_at, priority_score, session_type, status (scheduled|completed|missed|rescheduled|cancelled), manual_override, notes, reason_codes?, explanation?`
- **Topic**: `id, nome, subject_id, user_id`
- **Question**: `id, enunciado, alternativa_a–e, resposta_correta A-E, subject_id, topic_id?, user_id, dificuldade 1-5, ano?, fonte?` (`fonte=ai:<model>:<versão>` quando gerada)
- **QuestionAttempt**: `id, user_id, question_id (único por par — tentativa única), resposta, correta, tempo_segundos, attempted_at`
- **KnowledgeState**: `id, user_id, subject_id, topic_id, mastery_score, confidence_score, questions_answered/correct/wrong, recent/historical_accuracy, last_attempt/review_at, consecutive_correct/wrong, average_response_time, trend (improving|stable|declining)`
- **Assessment**: `id, user_id, target_questions (5-30), subject_id?, status (active|completed|abandoned), current_question_number, current_difficulty, correct/wrong_count, total_time_seconds, started/completed_at`
- **AssessmentQuestion**: `id, assessment_id, user_id, order, target_difficulty, subject_id?, topic_id?, question_id?, generated_question_data?, resposta?, correta?, tempo_segundos?, decision_reason?, presented/answered_at`
- **AIUsage**: `id, user_id?, feature, model, prompt_version, input/output/total_tokens, latency_ms, estimated_cost, status (success|error|timeout|rate_limit), error_type?, created_at`
- **PasswordResetToken**: `id, user_id, token_hash, expires_at (1h), used`

Migração legada (`migrate_legacy_database`) cria colunas/tabelas ausentes (`ai_usage`, `knowledge_states`, `users.email_opt_in/theme/density/default_task_status/totp_*`, `status`, `is_active`, etc.) e o índice único de tentativa quando não há duplicadas.

## 🧠 Decision Engine 4.0 (resumo mantido)

```
Coletar (KnowledgeState/Subject/Topic/Attempt/Session) → 7 scores → FinalScore=Σ(peso×comp)
→ detectar conflitos → resolver → alocar tempo → recomendações ordenadas (reason codes + explicação)
```

`FinalScore = 0.25×Need + 0.20×Weakness + 0.15×Recency + 0.15×ExamUrgency + 0.10×ReviewUrgency + 0.10×HistImportance + 0.05×Consistency`

Reason codes: `low_mastery`, `moderate_mastery`, `recent_accuracy_drop`, `recent_poor_performance`, `performance_declining`, `overdue_review`, `exam_urgency`, `exam_far`, `high_difficulty`, `low_confidence`, `missed_session`, `no_data`. Ações: `learn (<40)`, `practice (40-59)`, `enem_questions (60-74)`, `difficult_questions (75-89)`, `review (≥90)`, `mock_exam`. Detalhes e fórmulas: `docs/scoring.md`, `docs/recommendation-engine.md`, `docs/architecture.md`.

## 🧠 Desempenho 3.0 / Planner (resumo mantido)

- Mastery: `0.35×accuracy + 0.20×recent + 0.15×difficulty + 0.10×consistency + 0.10×recency + 0.10×confidence`; confiança por nº de evidências; tendência ±5%; revisão 1/3/7/14/30 dias por faixa de domínio.
- Planner: score 7 componentes, fases `>120 / 30-120 / <30` dias, limite 2 sessões consecutivas da mesma matéria, metas semanais proporcionais (mín. 30 min), replanejamento sem contaminar horas, diagnósticos por área. Detalhes: `docs/adaptive-planner.md`.
- Dashboard badges (leitura pura): streak 3/7/14, 10/50 questões, 80% com mín. 10 tentativas, 5 assuntos explorados, 1 assunto ≥90%.

## 🤖 AI Gateway 5.x (detalhe do estado atual)

```
Usuário → sanitize → injection-check → rate-limit → budget-check → prompt seguro (PROMPT_VERSION)
→ AIClient (OpenRouter) → validate output → sanitizar → persistir (nunca o bruto) → ai_usage
```

- **Client**: `AIClient(config, tracker)`; `chat()` livre + `chat_structured()` com `expected_keys` e parse tolerante a markdown; retry só p/ 5xx/timeout/429, backoff exponencial + jitter; `structured_max_retries=0` por padrão (falha rápido em JSON); `task_recommendation_timeout=8s`.
- **Geradores**: `QuestionGenerator` (quantidade 1/3/5, dificuldade 1-5, `to_db_dict()`), `ExplanationGenerator` (pós-resposta), `FeedbackGenerator` (`PerformanceData`), `ReviewGenerator` (`ReviewInput/Output`), `TaskRecommender` e `PlannerRecommender` (só sugerem; planner nunca delega datas ao LLM).
- **Limites**: `AIRateLimiter` em memória por `(user, feature)`; geração 20/h; explicações 30/h; reviews/feedbacks 20/h; planner/dashboard/statistics essenciais nunca bloqueiam.
- **Custos**: `estimate_cost(input, output)` + `estimate_monthly_cost()`; `UsageTracker.record()` por chamada; `is_budget_exceeded(daily, monthly)` bloqueia só não-essenciais.
- **Segurança IA**: `sanitize_user_content` (HTML/JS/null bytes/entidades), `has_injection_attempt` (~25 regex), `build_safe_prompt` (bloco delimitado), `validate_*_output` + `sanitize_output`; ver `docs/ai-observability.md` e `SECURITY.md`.
- **Sem IA**: tudo continua funcionando via fallbacks (recomendação de revisão, tipo de estudo por performance/fase, geração retorna 503 com mensagem amigável).

## ⚙️ Configuração & Pontos Importantes

- **Banco**: SQLite `instance/planejaenem.db` (auto-cria + migra); PostgreSQL via `DATABASE_URL`.
- **Logs**: `instance/logs/planejaenem.log` (`RotatingFileHandler` 10 MB × 10), sem PII/senhas/tokens (e-mail mascarado).
- **Segurança HTTP**: CSP (`base-uri/form-action 'self'`, scripts só `self` + jsdelivr), `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, COOP/COEP, `Cache-Control: no-store`, HSTS em HTTPS/prod; CSRF global; `MAX_CONTENT_LENGTH=2MB`; `_safe_next_url()` anti open-redirect; IDOR via `app/authz.py` + posse validada em services + testes (inclui `test_search.py`).
- **Rate limiting HTTP**: login 10/min, registro 5/min, planner 10/min, reset 3/min, 2FA 10/min por endpoint, assessment 5–60/min por endpoint (ver `app/assessment/routes.py` + `web.py` herda login).
- **Health**: `GET /health` público.

## 🐛 Troubleshooting (atual)

- `ModuleNotFoundError: flask` ou `pyotp` → ative venv + `pip install -r requirements.txt`.
- Porta em uso → `PORT=5001 python run.py`.
- Banco/colunas → auto-migrado; reset: apague `instance/planejaenem.db` e reinicie.
- `IA não está disponível (503)` → `AI_ENABLED=true` + `OPENROUTER_API_KEY` + `OPENROUTER_MODEL`; teste com `scripts/test_ai_connection.py`.
- `Limite do provedor (429)` / `422 sem questão válida` → aguarde / tente de novo / reduza quantidade.
- `404 em /questions/new` → **intencional** (geração só-via-IA). `404 em /auth/two-factor/*` → ative `TWOFA_ENABLED=true`.
- `405 em /performance/refresh` → use `POST` (GET foi removido).
- `Você já possui uma matéria com esse nome` → renomeie (unicidade por usuário).
- `Esta questão já foi respondida` → tentativa única por design (constraint `uq_attempt_user_question`; avaliação reutiliza a tentativa existente).
- `Tempo zerado na avaliação` → servidor recalcula pelo `presented_at` (teto +30s); client é só hint.
- Testes legados falhando → rode a referência atual: `test_search`, `test_question_answer_flow`, `test_question_generation_route`, `test_assessment`, `test_ai_*`, `test_performance_v3`.

## 🚦 Status do Projeto

- ✅ Núcleo 3.0/4.0 preservado (mastery, planner, decision engine, simulador, debug, arquivamento)
- ✅ Gateway IA + observabilidade/custos/segurança + 6 geradores/recomendadores
- ✅ Avaliação adaptativa REST + HTML (`web.py`) + Questões IA-only + tentativa única + timer + explicação
- ✅ Catálogo oficial + CRUD de Matérias + `questions.js`/`question-answer.js` + `attempt_map` sem N+1
- ✅ Busca global + filtros/paginação + badges + aparência/notificações + 2FA opt-in
- ✅ 844 testes coletados; `conftest.py` isolando scripts manuais; Docker não-root; LGPD; docs em `docs/`
- ⚠️ **Working tree à frente do HEAD**: `git status` mostra ~36 arquivos modificados + 8 novos (`web.py`, `two_factor.py`, `search.html`, `assessment/`, `two_factor_*.html`, `conftest.py`, `test_search.py`) ainda não commitados — commite antes de deploy
- ⚠️ **Débito conhecido**: `docs/` e `PREMIUM_UPGRADES.md` parcialmente datados frente a filtros/2FA/busca/badges; parte antiga da suite assume comportamentos pré-5.x — os testes novos documentam o vigente

## 📚 Documentação Adicional

- `SECURITY.md` — segurança completa (inclui IA + 2FA)
- `PREMIUM_UPGRADES.md` — histórico visual 3.0/4.0 (parcialmente datado; UX atual inclui `questions.js`, badges, busca, assessment HTML)
- `docs/architecture.md`, `docs/scoring.md`, `docs/recommendation-engine.md`, `docs/adaptive-planner.md`, `docs/security.md`, `docs/ai-observability.md`
- Scripts manuais: `scripts/benchmark_ai.py`, `scripts/test_ai_connection.py`, `scripts/test_structured_output.py`
- Inicialização: `run.py`, `run.sh`, `run.bat`

## 🤝 Contribuindo

1. Fork → branch `feature/...` → commit → push → PR.
2. Mantenha Blueprints por módulo; camada web fina sobre services (como `assessment/web.py`); nunca delegue decisão determinística ao LLM.
3. Escreva testes para o **comportamento atual** (CRUD matérias, IA-only questões, tentativa única, confirmação em 2 passos, 2FA atrás de flag, isolamento de busca).
4. Português em campos/rotas/mensagens; documente pesos/fórmulas em `docs/scoring.md`; atualize este README.
5. Rode `python -m pytest -q` + `python -m pytest --collect-only -q` antes do PR; não inclua `scripts/*` na suite.

## 📝 Licença

Fornecido como está, livre para uso e modificação.

## 👤 Autor

Ferramenta de preparação para o ENEM.

---

**Última atualização**: Setembro/2026 — 5.x + working tree (CRUD matérias, busca global `/search`, 2FA TOTP opt-in, perfis aparência/notificação, filtros/paginação, badges, assessment HTML, `POST /performance/refresh`; 844 testes coletados).
