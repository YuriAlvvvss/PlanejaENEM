# AI Observability - PlanejaENEM 5.0

## Visão Geral

O PlanejaENEM 5.0 introduz monitoramento completo do uso de IA generativa: custo, performance, segurança e conformidade. A IA é uma **ferramenta de suporte** — nunca a fonte da verdade.

## Regra de Ouro

> A IA generativa NUNCA é a fonte da verdade. Banco de dados, estatísticas, regras determinísticas, KnowledgeState e Decision Engine continuam sendo a fonte da verdade. A IA apenas gera, explica, resume e personaliza.

## Arquitetura

```
┌──────────────────────────────────────────────────────────┐
│                    AI GATEWAY (5.0)                       │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Usuário                                                │
│    ↓                                                    │
│  Sanitize Input ──→ Rate Limiter ──→ Cost Estimator     │
│    ↓ (prompt injection)   ↓ (limite/hora)  ↓ (custo)    │
│  Build Safe Prompt     Check Budget    Track Usage       │
│    ↓                       ↓              ↓              │
│  AIClient ──→ AI Provider ──→ Response                  │
│    ↓                              ↓                     │
│  Output Validator ──→ Validate   Persist to DB          │
│    ↓ (perigos)           ↓         ↓                    │
│  Reject/Sanitize    Show/Block   ai_usage table         │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

## Módulos

### 1. Cost Estimator (`app/ai/cost_estimator.py`)

Estima custo por chamada e projeção mensal.

```python
from app.ai import estimate_cost, estimate_monthly_cost, AIConfig

config = AIConfig()
cost = estimate_cost(input_tokens=500, output_tokens=200, config=config)
# ~$0.000195 por chamada

monthly = estimate_monthly_cost(
    avg_daily_calls=10,
    avg_input_tokens=500,
    avg_output_tokens=200,
    config=config,
    days=30,
)
```

**Variáveis de ambiente:**
- `AI_COST_PER_1K_INPUT_TOKENS` (padrão: 0.00015)
- `AI_COST_PER_1K_OUTPUT_TOKENS` (padrão: 0.0006)

### 2. Rate Limiter (`app/ai/rate_limiter.py`)

Rate limit in-memory por feature + usuário. Features essenciais (planner, dashboard, estatísticas) nunca são bloqueadas.

```python
from app.ai import AIRateLimiter, AIConfig

config = AIConfig(max_explanations_per_hour=30)
limiter = AIRateLimiter(config)

# Verificar se pode prosseguir
if limiter.check_rate_limit(user_id, "explanation"):
    # Chamar IA
    limiter.record_usage(user_id, "explanation")

# Consultar restante
remaining = limiter.get_remaining(user_id, "explanation")
```

**Features com limite:**
| Feature | Limite padrão/hora | Essencial? |
|---------|-------------------|------------|
| explanation | 30 | Não |
| review | 20 | Não |
| feedback | 20 | Não |
| question_generation | 10 | Não |
| planner | ∞ | Sim |
| dashboard | ∞ | Sim |
| statistics | ∞ | Sim |

**Variáveis de ambiente:**
- `AI_MAX_EXPLANATIONS_PER_HOUR` (padrão: 30)
- `AI_MAX_REVIEWS_PER_HOUR` (padrão: 20)
- `AI_MAX_FEEDBACK_PER_HOUR` (padrão: 20)

### 3. Budget Enforcement (`app/ai/usage.py`)

Bloqueio de features não-essenciais quando orçamento é excedido.

```python
from app.ai import UsageTracker

tracker = UsageTracker()
tracker.record("explanation", "m1", 100, 50, 150, 200.0, "success", 0.001)

# Verificar orçamento
budget = tracker.is_budget_exceeded(
    daily_budget=5.00,
    monthly_budget=100.00,
)
# {'daily_exceeded': False, 'monthly_exceeded': False}

# Resumo de custo
summary = tracker.cost_summary("daily")
# {'total_cost_usd': 0.001, 'total_calls': 1, ...}
```

**Variáveis de ambiente:**
- `AI_DAILY_BUDGET_USD` (padrão: 5.00)
- `AI_MONTHLY_BUDGET_USD` (padrão: 100.00)

### 4. Prompt Injection Protection (`app/ai/sanitizer.py`)

Proteção contra ataques de prompt injection.

```python
from app.ai import sanitize_user_content, has_injection_attempt, build_safe_prompt

# Sanitizar input do usuário
clean = sanitize_user_content(user_input)
# Remove HTML, JS, null bytes, decodifica entidades

# Detectar injection
if has_injection_attempt(user_input):
    # Log de segurança + rejeitar ou sanitizar

# Construir prompt seguro (separa conteúdo do usuário)
messages = build_safe_prompt(
    system_instructions="Você é um tutor.",
    domain_context="Matéria: Matemática",
    user_content=clean,
)
# Conteúdo do usuário fica isolado em bloco delimitado
```

**Padrões detectados (~25):**
- `ignore previous instructions`
- `disregard instructions`
- `you are now`
- `pretend you are`
- `system:` injection
- `<|im_start|>` injection
- `jailbreak`
- `override instructions`
- E mais...

### 5. Output Validator (`app/ai/output_validator.py`)

Validação de output da IA antes de salvar no banco ou mostrar ao usuário.

```python
from app.ai import validate_text_output, validate_question_output, sanitize_output

# Validar texto livre
result = validate_text_output(ai_response)
if result.is_safe:
    display(result.sanitized_text)

# Validar questão gerada
result = validate_question_output(question_data)
if not result.is_safe:
    log_security_event(result.errors)

# Sanitizar output genérico
clean = sanitize_output(ai_output)
```

**Validações por tipo:**
| Tipo | Campos obrigatórios | Validações extras |
|------|---------------------|-------------------|
| text | (nenhum) | HTML, XSS, length |
| question | statement, alternatives A-E, correct_answer, difficulty, topic | answer range 1-5, difficulty 1-5, duplicates |
| explanation | summary, concept, steps, common_mistake, study_tip | all required |
| feedback | summary, strengths, weaknesses, advice, next_step | all required |
| review | title, summary, key_concepts, worked_example, common_mistakes, quick_check | all required |

### 6. Usage Persistence (`app/ai/models.py` + `app/ai/usage.py`)

Todas as chamadas de IA são persistidas na tabela `ai_usage`.

```python
# Modelo AIUsage
class AIUsage(db.Model):
    id, user_id, feature, model, prompt_version,
    input_tokens, output_tokens, total_tokens,
    latency_ms, estimated_cost, status, error_type, created_at
```

**Queries de exemplo:**
```sql
-- Custo diário por feature
SELECT feature, SUM(estimated_cost) as cost, COUNT(*) as calls
FROM ai_usage
WHERE created_at >= date('now', '-1 day')
GROUP BY feature;

-- Usuários com mais custo
SELECT user_id, SUM(estimated_cost) as total_cost
FROM ai_usage
WHERE created_at >= date('now', '-30 day')
GROUP BY user_id
ORDER BY total_cost DESC;
```

## Configuração Completa

### Variáveis de Ambiente

```env
# AI Gateway
AI_ENABLED=false
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
AI_BASE_URL=https://openrouter.ai/api/v1
AI_TIMEOUT=30
AI_MAX_RETRIES=2
AI_MAX_TOKENS=2048

# Cost & Limits
AI_COST_PER_1K_INPUT_TOKENS=0.00015
AI_COST_PER_1K_OUTPUT_TOKENS=0.0006
AI_MAX_EXPLANATIONS_PER_HOUR=30
AI_MAX_REVIEWS_PER_HOUR=20
AI_MAX_FEEDBACK_PER_HOUR=20
AI_DAILY_BUDGET_USD=5.00
AI_MONTHLY_BUDGET_USD=100.00
```

### Defaults do AIConfig

| Campo | Default | Descrição |
|-------|---------|-----------|
| cost_per_1k_input_tokens | 0.00015 | Custo por 1k tokens de entrada |
| cost_per_1k_output_tokens | 0.0006 | Custo por 1k tokens de saída |
| max_explanations_per_hour | 30 | Limite de explicações/hora por usuário |
| max_reviews_per_hour | 20 | Limite de revisões/hora por usuário |
| max_feedback_per_hour | 20 | Limite de feedbacks/hora por usuário |
| daily_budget_usd | 5.00 | Orçamento diário em USD |
| monthly_budget_usd | 100.00 | Orçamento mensal em USD |

## Fluxo de Segurança

```
1. Input do Usuário
   ↓
2. sanitize_user_content() ──→ Remove HTML, JS, null bytes
   ↓
3. has_injection_attempt() ──→ Detecta padrões maliciosos
   ↓ (se detectado)
4. Log de segurança + build_safe_prompt() ──→ Isola conteúdo
   ↓
5. AIClient.chat() ──→ Envia para IA
   ↓
6. validate_*_output() ──→ Valida resposta da IA
   ↓ (se inseguro)
7. sanitize_output() ou fallback determinístico
   ↓
8. Salvar no banco (NUNCA output bruto da IA)
```

## Testes

Suite completa: `tests/test_ai_usage.py` (80 testes)

```bash
python -m pytest tests/test_ai_usage.py -v
```

**Cobertura:**
- Cost Estimator: 6 testes
- Sanitizer (injection): 19 testes
- Build Safe Prompt: 3 testes
- Output Validator: 18 testes
- Rate Limiter: 10 testes
- Usage Persistence: 6 testes
- AIUsage Model: 3 testes
- AIConfig: 5 testes
- Load Config: 5 testes
- Integração: 4 testes

## Verificação de Orçamento

O `UsageTracker.is_budget_exceeded()` é chamado antes de cada chamada de IA não-essencial:

```python
if tracker.is_budget_exceeded(daily_budget=5.0):
    # Bloquear feature não-essencial
    # Log de alerta
    # Continuar funcionando sem IA
```

**Comportamento quando orçamento é excedido:**
- Features essenciais (planner, dashboard, statistics): sempre funcionam
- Features não-essenciais (explanation, review, feedback): bloqueadas com log
- Usuário vê mensagem amigável + fallback determinístico
