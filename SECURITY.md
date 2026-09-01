# Security - PlanejaENEM

## Autenticação

- Senhas hasheadas com Werkzeug (scrypt/pbkdf2)
- Validação de força de senha: 8+ caracteres, maiúscula, minúscula, número
- Rate limiting em login (10/min por IP)
- Rate limiting em registro (5/min por IP)
- Regeneração de sessão após login, logout e troca de senha
- `session_protection="strong"` via Flask-Login
- Sessão expira após 30 minutos de inatividade

## Autorização

- Todas as rotas autenticadas usam `@login_required`
- Consultas sempre filtram por `user_id=current_user.id`
- Funções centralizadas em `app/authz.py`:
  - `get_user_subject()`, `get_user_task()`, `get_user_session()`, `get_user_plan()`
  - `user_owns_subject()`, `user_owns_task()`, `user_owns_session()`
- Validação de `subject_id` em operações que associam objetos

## Proteção contra IDOR

- Nenhuma rota usa `Model.query.get(id)` sem filtro de `user_id`
- Operações de edição/exclusão usam `first_or_404()` com filtro de usuário
- Testes automatizados verificam isolamento entre usuários

## CSRF

- Flask-WTF com `CSRFProtect` global
- Todos os formulários usam `{{ form.hidden_tag() }}`
- Operações POST exigem token CSRF válido

## Sessão e Cookies

- `SESSION_COOKIE_HTTPONLY=True`
- `SESSION_COOKIE_SAMESITE="Lax"`
- `SESSION_COOKIE_SECURE=True` em produção
- `REMEMBER_COOKIE_HTTPONLY=True`
- `PERMANENT_SESSION_LIFETIME=30 minutos`
- Regeneração de sessão em eventos sensíveis

## Rate Limiting

- Flask-Limiter com `memory://` (configurável para Redis via `RATELIMIT_STORAGE_URI`)
- Login: 10/min por IP
- Registro: 5/min por IP
- Planner: 10/min por usuário
- Password reset: 3/min por IP

## Headers de Segurança

- `Content-Security-Policy`: `default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; ...`
- `Strict-Transport-Security`: habilitado em produção/HTTPS
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- `Cross-Origin-Opener-Policy: same-origin`
- `Cross-Origin-Resource-Policy: same-origin`
- `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`
- `base-uri 'self'`
- `form-action 'self'`

## Secrets

- `SECRET_KEY` obrigatória em produção (app falha se ausente)
- Fallback `"dev-fallback-key"` apenas em desenvolvimento
- Variáveis de ambiente para todas as configurações sensíveis
- `.env` no `.gitignore`
- `docker-compose.yml` não contém secrets hardcoded

## Logs

- Logs em `instance/logs/planejaenem.log` com rotação (10MB x 10 backups)
- Emails nunca aparecem em logs em texto claro
- Senhas nunca aparecem em logs ou respostas HTTP
- Tokens nunca são logados

## Docker

- Container roda como usuário não-root (`appuser`)
- Permissões adequadas em diretórios de escrita
- `HEALTHCHECK` recomendado para produção

## Validação de Entrada

- WTForms com validadores em todos os campos
- `MAX_CONTENT_LENGTH`: 2MB
- `MAX_FORM_MEMORY_SIZE`: 512KB
- `MAX_FORM_PARTS`: 50
- Descrição de tarefas: máximo 2000 caracteres
- Nome de matérias: máximo 100 caracteres
- Título de tarefas: máximo 200 caracteres

## Open Redirects

- Função `_safe_next_url()` valida redirecionamentos
- Apenas caminhos relativos são permitidos
- URLs absolutas e `//` são bloqueadas

## AI Security (PlanejaENEM 5.0)

### Prompt Injection Protection

- ~25 padrões de ataque detectados via regex
- `sanitize_user_content()` remove HTML, JS, null bytes, decodifica entidades
- `has_injection_attempt()` detecta: "ignore instructions", "you are now", "pretend", "jailbreak", "system:" injection, "<|im_start|>" injection
- `build_safe_prompt()` isola conteúdo do usuário em bloco delimitado
- Conteúdo sanitizado nunca é tratado como instrução

### Output Validation

- `validate_text_output()` detecta HTML perigoso, XSS, scripts
- `validate_question_output()` valida campos obrigatórios, range de resposta, range de dificuldade
- `validate_explanation_output()`, `validate_feedback_output()`, `validate_review_output()` validam campos obrigatórios
- `sanitize_output()` remove conteúdo perigoso antes de salvar/mostrar
- Output bruto da IA NUNCA é salvo diretamente no banco

### Rate Limiting por Feature

- Limite por feature + usuário (explicações, revisões, feedbacks)
- Features essenciais (planner, dashboard, statistics) nunca são bloqueadas
- Limite configurável via variáveis de ambiente
- Reset por usuário ou global

### Budget Enforcement

- Orçamento diário e mensal configurável
- Bloqueio de features não-essenciais quando orçamento excedido
- Features essenciais continuam funcionando
- Alertas de orçamento via logs
- Tracking completo: tokens, custo, latência, status

### Usage Persistence

- Tabela `ai_usage` com tracking completo
- Índices para queries de análise
- Dados: user_id, feature, model, tokens, latency, cost, status
- Retenção configurável

## Recuperação de Senha

- Token criptograficamente seguro (`secrets.token_urlsafe`)
- Hash do token armazenado (não o token em plaintext)
- Expiração de 1 hora
- Uso único (invalidado após uso)
- Tokens antigos são invalidados ao solicitar novo reset
- Não revela se o email existe

## Reautenticação

- Troca de senha exige senha atual
- Alteração de email exige senha atual

## Dependências

- Versões fixadas com `==` no `requirements.txt`
- Flask-Limiter para rate limiting

## Reporte de Vulnerabilidades

Se você encontrar uma vulnerabilidade de segurança, por favor não a reporte publicamente.
Envie um email para o maintainer do projeto com:
- Descrição da vulnerabilidade
- Passos para reproduzir
- Impacto potencial
- Sugestão de correção (se aplicável)
