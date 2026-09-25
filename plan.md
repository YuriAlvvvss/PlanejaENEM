# Plano de Execução — PlanejaENEM (Segurança → Visual → A11y)

> Origem: avaliação geral + verificação contra o código em `main` + working tree (set/2026).
> Ordem recomendada: P0 → P1 → P2 → P3. Não pular P0.

## Status (atualizado set/2026 — suíte 844 passed)

- [x] P0 — Segurança crítica (6/6 concluídos, 844 passed)
- [x] P1 — Hardening segurança + IA + ops (4/4 concluídos, 844 passed)
- [x] P2 — Redesign base + a11y base (tokens, hero, crumbs, skip-link, aria-live, scope — 844 passed)
- [ ] P3 — Auditoria WCAG 2.2 AA completa + validação visual (detalhado abaixo)

## 0. Verificação prévia (base factual)

| Alegação | Veredito | Evidência |
|---|---|---|
| Exclusões aceitam GET mutante | Falso-positivo parcial. GET só renderiza confirmação; mutação só em POST | `app/subjects/routes.py:79-95`, `app/tasks/routes.py:287-298`, `app/questions/routes.py:83-92`, `app/questions/routes.py:394-403` + templates `confirm_delete*.html` já com CSRF |
| Revisão vaza exceção interna | Procede | `app/planner/routes.py:279-281` retorna `str(exc)` 500 |
| Simulate POST sem CSRF | Procede | `app/templates/decision_engine/simulate.html:21` sem `csrf_token`; 41 outros forms têm |
| Simulate sem validação/rate limit | Procede | `app/decision_engine/routes.py:156-168` sem clamp/limiter |
| Rate limit IA só memória | Procede | `app/ai/rate_limiter.py:59-68`, `check_budget` sempre True |
| `AI_BASE_URL` arbitrária (SSRF) | Procede | `app/ai/config.py:102` + `app/ai/client.py:182` sem allowlist |
| Matérias “só catálogo” vs CRUD | Desatualizado. CRUD reabilitado é intencional | `README.md:35-38`, `app/subjects/routes.py:22-76` |
| `premium.css:512` com `\n` literais | Procede | `app/static/premium.css:511-512` linha única colada |
| Headers/CSRF global/IDOR | Maioria OK | `app/__init__.py:283-353`, `app/extensions.py:1-17`, `app/authz.py`, `app/assessment/routes.py` com limiter |

---

## P0 — Segurança crítica ✅ CONCLUÍDO (844 passed)

### P0-1. CSRF `simulate.html` ✅
- Feito: hidden `csrf_token` em `app/templates/decision_engine/simulate.html:21-22`.

### P0-2. Não vazar exceção em `/planner/review` ✅
- Feito em `app/planner/routes.py:217-311`: body dict-check → 400, `topic_id` int>0, `duration_minutes` 5–120, `@limiter 20/min`, `ValueError→400/429`, `AIRateLimit→429`, `AIDisabled/AIConfiguration→503`, `AIProvider/AIValidation/AITimeout→502` genérico, genérico → 500 genérico + `logger.exception`. Sem `str(exc)` em resposta.

### P0-3. Validar + rate-limit Decision Engine ✅
- Feito em `app/decision_engine/routes.py:12,156-174`: import `limiter`, `_clamp()` daily 15–480 / weekly 60–3000, `@limiter 20/min` em `simulate`.

### P0-4. SSRF em `AI_BASE_URL` ✅
- Feito: `sanitize_ai_base_url()` + `_allowed_ai_hosts()` em `app/ai/config.py:1-60,102` (só `https` + `openrouter.ai` + `AI_ALLOWED_HOSTS` opt-in; inválido → fallback + warning); defesa em profundidade em `app/ai/client.py:112-145` (`AIConfigurationError` se bypass). Verificado: `169.254.169.254/localhost/evil.com` → fallback, `openrouter.ai` mantido.

### P0-5. Corrigir `premium.css:512` ✅
- Feito: 79 `\n` literais → quebras reais (`app/static/premium.css:511-591`, 591 linhas, count 0).

### P0-6. CSRF em endpoints JSON (padronizar) ✅
- Feito: `<meta name="csrf-token">` em `app/templates/base.html:6` (só autenticado); fallback `dataset || meta` em `app/static/questions.js:57-62` e `app/static/app.js:124-172`. Mantido CSRF ligado em prod; testes com CSRF desligado continuam verdes.

## P1 — Hardening segurança + IA + ops ✅ CONCLUÍDO (844 passed)

### P1-1. Rate limit IA distribuído ✅
- Feito: `app/ai/rate_limiter.py:59-170` — in-memory + `_db_count_recent()` (`ai_usage`, user+feature, última hora); bloqueio se qualquer camada estourar; nunca levanta. Mesmo padrão em `app/ai/question_generator.py:137-165` + `remaining_hourly()`. HTTP Redis via `RATELIMIT_STORAGE_URI` + warning prod `memory://` em `app/__init__.py`.

### P1-2. Endurecer AI Gateway ✅
- Feito em `app/ai/sanitizer.py:20-60,190-222`: +18 regex PT-BR + ofuscação (`i.g.n.o.r.e`, `[SYSTEM]`, `<<sys>>`), NFKC + strip zero-width, remove controles C0/C1, teto efetivo (sys 4k, ctx 8k, total 15k). Verificado: 5 ataques → True, conteúdo legítimo → False, prompt gigante → 15000. `usage.py` segue sem logar prompt/resposta.

### P1-3. HTTP/Docker/Secrets/LGPD ✅
- Feito: `ProxyFix` opt-in `TRUST_PROXY=1` + `errorhandler` 404/500 genéricos (JSON p/ APIs, HTML sem stack) em `app/__init__.py:322-360`; `HEALTHCHECK → /health` no `Dockerfile:24`; bloco `redis` comentado no `docker-compose.yml`; `TRUST_PROXY` + `AI_ALLOWED_HOSTS` no `.env.example`. LGPD restante (retenção/documentação) movido p/ P3-docs.

### P1-4. IDOR/dupla submissão ✅
- Feito: `app/assessment/web.py:40-44` delega a `get_user_assessment()` (`app/authz.py` cobre todos recursos); `Idempotency-Key` opt-in (header ou JSON, sessão, últimas 20) em `app/tasks/routes.py:194-250` e `app/assessment/routes.py:31-90` (sem chave = comportamento antigo; repetida → `200 + deduplicated:true`); `crypto.randomUUID()` + trava anti-duplo-submit em `app/static/app.js`.

## P2 — Redesign base + a11y base ✅ CONCLUÍDO (844 passed)

Amarração de testes respeitada: dashboard mantém `2h`, `Simulado de hoje`, `Lista atrasada`, `Revisar fun`, sem `cal-grid` (`tests/test_dashboard.py:117-123`); `Matemática` (`test_auth.py:227-229`); badges/questões (`test_questions.py:636-646`, `test_phase2_quality.py:570-584`).

### P2-1. Tokens aditivos ✅
- `app/static/style.css:1580+`: `--font-display`, `clamp()`, `--space-*`, `.skip-link`, `.hero-next`, `.skeleton` + `prefers-reduced-motion`, `.crumb-nav`. Nenhum token removido; `premium.css` segue como camada.

### P2-2. Dashboard hero ✅
- `app/templates/dashboard.html:23-46,99-106`: hero com resumo + CTA `#next-action`; card virou `.hero-next#next-action` (“Próxima ação recomendada”). Métricas/KPIs/badges/rotina/sessões preservados; charts com `role=img` + `aria-labelledby` + `<details>` textual (planned/completed/progress + link `/performance`); `scope="col"` nas tabelas.

### P2-3. Unificação + estados ✅
- `decision_engine/recommendations.html`, `simulate.html`, `history.html`: `crumb-nav` + `eyebrow Decision Engine` (mesma linguagem de `questions/list.html`).
- `questions/list.html:51-58`: `#aiError role=alert aria-live=assertive`, `#aiLoading/#aiResult role=status aria-live=polite`; `questions.js` move foco ao erro, mantém disabled/retry.

### P2-4. A11y base ✅
- `base.html`: skip-link, `#main-content role=main`, `aria-expanded/controls` no toggle; flashes já `role=alert`; modal Bootstrap com focus trap; `app.js` gerencia `aria-expanded`/`aria-selected`.

## P3 — Auditoria WCAG 2.2 AA + validação (PARCIAL — auditoria local feita, axe/Lighthouse-full pendente de navegador)

### P3-1. Auditoria real
- [x] Auditoria estática local (stdlib, 15 rotas via test-client): skip-link ✅, main/nav ✅, imgs sem alt 0, botões sem nome 0, `tabindex>0` 0, canvas todos com `aria-label`, tabelas dashboard com `scope`.
- [x] Achado 1 CORRIGIDO: `#aiSubject/#aiTopic/#aiQuantity` sem `<label for>` em `questions/list.html` (3 → 0).
- [x] Achado 2 CORRIGIDO: contraste light `--primary #2f80ed` 3.60 e `--danger #d14b5d` 4.01 (falham AA) → `--primary #1f6fd6` (4.55 texto / 4.88 botão branco) e `--danger #b23a4b` (5.43 / 5.83), `--primary-strong #1d5fc2`. Dark todos ≥7.3; light muted 4.62 ✅.
- [ ] axe-core full + Lighthouse (SEM NAVEGADOR NESTE AMBIENTE — sem chrome/node): rodar em CI/dev com Chrome:
  `npx @axe-core/cli http://localhost:5000/ --exit` e `npx lighthouse --only-categories=accessibility --view` (meta ≥90) nas 11 rotas do P3-1 original. Script local salvo em `Temp/opencode/a11y_audit.py` (relatórios `a11y_report*.txt`).
- [ ] h1 ausente na maioria das páginas (h2 como título) — avaliar trocar título da página p/ h1 sem quebrar testes (só strings amarradas, não tags).
- [ ] Inventário teclado manual (tab order, traps, `aria-expanded`, foco pós-AJAX) — pendente de navegador.

### P3-2. Correções por lote (1 PR por lote, 844 sempre verde)
1. **Foco/teclado**: `focus-visible` já existe (`premium.css`) — validar espessura/contraste; foco retorna ao gatilho ao fechar modal (`questions.js`); `Escape` fecha sidebar (já faz em `app.js:86-90`) + fechar modal confirmação destrutiva.
2. **Live regions**: flashes `role=alert` OK; adicionar `aria-live=polite` em `#dashboard-charts-data` updates, `data-task-recommendation` panel, timer `data-answer-timer` (`assessment/play.html:46`, `questions/view.html:63` usam `aria-live=off` — trocar timer p/ `aria-hidden` + texto alternativo sob demanda).
3. **Gráficos/tabelas**: todo `<canvas>` com `role=img` + descrição + `<details>`/tabela oculta (padrão já aplicado no dashboard — replicar em `performance/overview.html`); toda `<table>` com `<caption>` ou `aria-label` + `scope`.
4. **Modais**: `Gerar com IA` (`questions/list.html:17-78`) — `aria-modal`, foco inicial no `#aiSubject`, `focus-trap` nativo Bootstrap validado, `aria-describedby` p/ erro/loading.
5. **Formulários destrutivos**: `confirm_delete*.html` — heading hierárquico, botão perigo com `aria-describedby` da consequência, contraste `#ffb1bb` sobre fundo validado.
6. **Contraste temas**: ajustar `--warning: #f3c76d` sobre claro (atual `#d49a2c` OK, validar dark) e `.alert-warning color:#f3c76d` (`premium.css:536-540`).

### P3-3. Validação multissensorial (evidência p/ PR)
- [ ] `prefers-reduced-motion`: skeleton/animações desligadas (já em `style.css`) — validar com emulação.
- [ ] Zoom 200% + 360px: hero, `routine-grid`, `chart-grid`, `table-responsive` sem scroll horizontal quebrado; `btn-group` empilha (já em `premium.css`).
- [ ] Rede lenta (throttle 3G): skeleton visível, retry funciona, IA 502/429/503 mostra mensagem amigável + fallback determinístico (planner/questions).
- [ ] Screenshots antes/depois desktop + mobile anexados.

### P3-4. Docs/dívida
- [ ] Atualizar `SECURITY.md`, `docs/security.md`, `docs/ai-observability.md` (SSRF allowlist, rate-limit DB, erro genérico, `Idempotency-Key`, `TRUST_PROXY`, `HEALTHCHECK`).
- [ ] Atualizar `README.md` (contagem testes se mudar, `AI_ALLOWED_HOSTS`, `TRUST_PROXY`, `redis`).
- [ ] `PREMIUM_UPGRADES.md` + `docs/`: marcar o que foi unificado em P2.
- [ ] LGPD: documentar retenção `ai_usage`, exportação, exclusão; `git status` limpo (hoje `?? plan.md` + working tree à frente — commitar por fatia).

---

## Ordem executada

- [x] P0-1 → P0-5 (CSRF, CSS, clamp, review, SSRF).
- [x] P0-6 + P1-4 (CSRF JSON + IDOR/idempotência).
- [x] P1-1 + P1-2 (IA distribuída + injection).
- [x] P1-3 (ops/LGPD base).
- [x] P2 incremental (tokens → hero → crumbs/estados → a11y base).
- [ ] P3 (auditoria + lotes + evidências).

## Definition of Done (aplicado)

- [x] `python -m pytest -q` verde (844 em P0, P1 e P2).
- [x] Sem `str(exc)` em resposta HTTP; sem `\n` literal em CSS; CSRF em todo POST form.
- [x] `SECRET_KEY` ausente em `production` falha; nenhum secret/key em log (`__repr__` mascara).
- [ ] `README.md`/`SECURITY.md` atualizados (pendente — P3-4).
- [ ] Screenshots antes/depois para P2/P3 (pendente — P3-3).
