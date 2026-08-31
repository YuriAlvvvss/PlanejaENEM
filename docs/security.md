# Segurança - PlanejaENEM 4.0

## Visão Geral

O PlanejaENEM 4.0 mantém todos os padrões de segurança do 3.0 e adiciona novas garantias para o motor de decisão.

## Princípios de Segurança

### 1. Isolamento de Usuários
- Cada usuário só acessa seus próprios dados
- Nunca mistura dados entre usuários
- Queries sempre filtram por `user_id`

### 2. Não Regressão
- Novas funcionalidades não quebram segurança existente
- Testes de segurança contínuos
- Validação em todas as camadas

### 3. Defense in Depth
- Múltiplas camadas de proteção
- Validação no frontend e backend
- Rate limiting em endpoints sensíveis

## Controles de Acesso

### Autenticação
- Flask-Login com sessões seguras
- Senhas hasheadas com Werkzeug (scrypt/pbkdf2)
- Regeneração de sessão após login

### Autorização
- `authz.py`: Helpers de proteção contra IDOR
- `get_user_session()`: Garante que sessão pertence ao usuário
- `get_user_plan()`: Garante que plano pertence ao usuário
- `user_owns_subject()`: Garante que matéria pertence ao usuário

### Rate Limiting
- Flask-Limiter com armazenamento em memória
- Limite de 10 requisições/minuto em endpoints do planner
- Proteção contra brute-force em login

## Segurança do Decision Engine

### Isolamento de Dados

```python
# CORRETO: Filtrar por user_id
knowledge_states = KnowledgeState.query.filter_by(user_id=user_id).all()

# INCORRETO: Carregar todos os estados
knowledge_states = KnowledgeState.query.all()
```

### Validação de Entrada

```python
# Validar disponibilidade
if not availability.days:
    return {"error": "Dias não especificados"}

if availability.daily_minutes <= 0:
    return {"error": "Minutos diários inválidos"}

if availability.weekly_goal_minutes <= 0:
    return {"error": "Meta semanal inválida"}
```

### Proteção contra Manipulação

```python
# Nunca confiar em dados do cliente para cálculos
# Usar sempre dados do banco de dados

# CORRETO:
subject = db.session.get(Subject, subject_id)
if subject.user_id != current_user.id:
    abort(403)

# INCORRETO:
subject_id = request.form.get("subject_id")  # Pode ser manipulado
```

## Endpoints Seguros

### GET /decision-engine/recommendations
- Requer autenticação
- Filtra por `user_id`
- Não expõe dados de outros usuários

### GET /decision-engine/debug
- Requer autenticação
- Mostra apenas dados do usuário atual
- Pode ser desativado em produção

### POST /decision-engine/simulate
- Requer autenticação
- Valida todos os parâmetros
- Rate limiting aplicado

### GET /decision-engine/history
- Requer autenticação
- Filtra por `user_id`
- Limite de resultados configurável

## Proteção contra IDOR

### Exemplo de Vulnerabilidade
```python
# VULNERÁVEL: IDOR
@app.route("/session/<int:id>")
def get_session(id):
    session = StudySession.query.get(id)  # Pode ser de outro usuário!
    return jsonify(session.to_dict())
```

### Correção
```python
# SEGURO: Com verificação de ownership
@app.route("/session/<int:id>")
@login_required
def get_session(id):
    session = get_user_session(id)  # Verifica user_id
    return jsonify(session.to_dict())
```

## Validação de Dados

### Tipos de Validação

1. **Tipo**: Verificar se é integer, string, etc.
2. **Faixa**: Verificar se está dentro de limites
3. **Formato**: Verificar formato (email, data, etc.)
4. **Existência**: Verificar se registro existe
5. **Ownership**: Verificar se pertence ao usuário

### Exemplo

```python
def validate_weekly_goal(hours):
    if hours is None:
        return False, "Informe a meta semanal"
    
    if not isinstance(hours, (int, float)):
        return False, "Meta deve ser um número"
    
    if hours < 1 or hours > 80:
        return False, "Meta deve estar entre 1 e 80 horas"
    
    return True, None
```

## Criptografia

### Senhas
- Hashing com Werkzeug (scrypt ou pbdkf2)
- Nunca armazenar senhas em texto plano
- Salt gerado automaticamente

### Tokens
- Tokens de redefinição de senha: `secrets.token_urlsafe(32)`
- Hash com SHA-256 para armazenamento
- Expiração configurável

### Dados Sensíveis
- `.env` excluído do git
- Chaves secrets nunca no código
- HTTPS em produção

## Logs e Auditoria

### O que Logar
- Tentativas de login (sucesso e falha)
- Ações sensíveis (criar, editar, excluir)
- Erros do sistema
- Acesso não autorizado

### O que NÃO Logar
- Senhas
- Tokens
- Dados pessoais sensíveis
- Conteúdo de formulários

### Configuração

```python
# Logs rotativos
file_handler = RotatingFileHandler(
    "planejaenem.log",
    maxBytes=10485760,  # 10MB
    backupCount=10,
)
```

## Headers de Segurança

```python
response.headers["X-Content-Type-Options"] = "nosniff"
response.headers["X-Frame-Options"] = "SAMEORIGIN"
response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
response.headers["Content-Security-Policy"] = "default-src 'self'; ..."
response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
```

## Testes de Segurança

### Testes Incluídos

1. **IDOR**: Verificar que usuário não acessa dados de outro
2. **CSRF**: Verificar proteção em formulários
3. **Rate Limiting**: Verificar limites de requisição
4. **Session Fixation**: Verificar regeneração de sessão
5. **Input Validation**: Verificar sanitização de entrada

### Executar Testes

```bash
pytest tests/test_security.py -v
```

## Checklist de Segurança

- [x] Isolamento de usuários por `user_id`
- [x] Validação de entrada em todos os endpoints
- [x] Rate limiting em endpoints sensíveis
- [x] CSRF protection em formulários
- [x] Headers de segurança configurados
- [x] Senhas hasheadas com Werkzeug
- [x] Tokens de redefinição seguros
- [x] Logs sem dados sensíveis
- [x] `.env` excluído do git
- [x] HTTPS em produção
- [x] Testes de segurança executados

## Incidentes

### Em Caso de Vulnerabilidade

1. **Identificar**: Coletar detalhes da vulnerabilidade
2. **Conter**: Desativar funcionalidade afetada se necessário
3. **Corrigir**: Implementar correção
4. **Testar**: Verificar correção com testes
5. **Documentar**: Registrar incidente e lições aprendidas

### Contato

Para reportar vulnerabilidades de segurança:
- Email: [CONFIGURAR]
- GitHub: Issues com label "security"
