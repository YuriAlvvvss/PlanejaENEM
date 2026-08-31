# Arquitetura - PlanejaENEM 4.0

## Visão Geral

O PlanejaENEM 4.0 transforma o planner existente em um **motor de decisão determinístico** que responde:

1. **O que estudar?** → Ação recomendada (teoria, exercícios, questões ENEM, etc.)
2. **Qual assunto?** → Matéria e tópico específicos
3. **Qual tipo de estudo?** → Baseado no domínio atual
4. **Quanto tempo?** → Duração estimada da sessão
5. **Quando estudar?** → Data recomendada
6. **Quando revisar?** → Próxima data de revisão
7. **Por que isso foi recomendado?** → Reason codes explicativos
8. **Qual deve ser a próxima ação?** → Progressão de aprendizagem

## Princípios Fundamentais

### Determinismo
- Com os mesmos dados de entrada, o sistema sempre produz a mesma recomendação
- Não há aleatoriedade ou elementos não determinísticos
- Todas as decisões são reproduzíveis

### Transparência
- Toda recomendação possui reason codes explicativos
- Modo debug disponível para análise do algoritmo
- Pesos e fórmulas documentados e centralizados

### Offline
- Sistema funciona 100% offline após instalação
- Não depende de APIs externas, LLM ou serviços de IA
- Todos os cálculos são locais

### Não-Invasivo
- Não substitui o projeto existente
- Funciona em paralelo com o planner atual
- Pode ser ativado/desativado conforme necessidade

## Componentes

### Decision Engine (`app/decision_engine/`)

```
app/decision_engine/
├── __init__.py          # Exportações públicas
├── types.py             # Enums, dataclasses, reason codes
├── ranking.py           # Pesos centralizados, FinalScore
├── policies.py          # Detecção/resolução de conflitos
├── explanations.py      # reason_codes → texto amigável
├── engine.py            # Ciclo completo de decisão
├── simulator.py         # Simulação e comparação de planos
└── routes.py            # Endpoints da API
```

### Tipos de Dados (`types.py`)

- **StudyAction**: Ações de estudo (learn, practice, enem_questions, review, difficult_questions, mock_exam)
- **SessionStatus**: Status de sessões (scheduled, completed, missed, rescheduled, cancelled)
- **ReasonCode**: Códigos de motivo para recomendações
- **MasteryLevel**: Níveis de domínio (critical, low, medium, good, excellent)
- **StudyPhase**: Fases de estudo (long_term, medium_term, final_stretch)
- **ConflictType**: Tipos de conflitos detectados
- **StudyRecommendation**: Recomendação completa de estudo
- **TopicContext**: Contexto completo de um tópico
- **WeeklyAvailability**: Disponibilidade semanal do aluno

### Ranking (`ranking.py`)

Calcula o score final de prioridade (0-100) combinando:

| Componente | Peso | Descrição |
|------------|------|-----------|
| need_score | 0.25 | Necessidade de estudo |
| weakness | 0.20 | Fraqueza no assunto |
| recency | 0.15 | Tempo desde última atividade |
| exam_urgency | 0.15 | Proximidade do ENEM |
| review_urgency | 0.10 | Urgência de revisão |
| historical_importance | 0.10 | Importância histórica |
| study_consistency | 0.05 | Consistência de estudo |

### Políticas (`policies.py`)

Detecta e resolve conflitos:

- **WEEKLY_GOAL_IMPOSSIBLE**: Tempo recomendado > meta semanal
- **EXCESS_SESSIONS**: Mais de 3 sessões por assunto
- **OVERDUE_REVIEW_CONFLICT**: Revisões atrasadas + conteúdo novo
- **DAILY_LIMIT_EXCEEDED**: Limite diário excedido
- **NO_AVAILABILITY**: Sem disponibilidade configurada
- **SUBJECT_IMBALANCE**: Desbalanceamento entre assuntos

### Explicabilidade (`explanations.py`)

Transforma reason codes em textos amigáveis:

- LOW_MASTERY → "Seu domínio estimado neste assunto ainda é baixo."
- RECENT_ACCURACY_DROP → "Seu desempenho caiu nas questões mais recentes."
- OVERDUE_REVIEW → "Você tem revisões atrasadas neste assunto."
- EXAM_URGENCY → "A data do ENEM está próxima."

### Engine (`engine.py`)

Executa o ciclo completo:

1. Coletar estado de conhecimento
2. Calcular scores para cada tópico
3. Rankear por FinalScore
4. Detectar conflitos
5. Resolver conflitos
6. Alocar tempo disponível
7. Gerar recomendações com reason codes
8. Retornar lista ordenada

### Simulador (`simulator.py`)

Permite comparar planos:

- `simulate_plan()`: Simula um plano e calcula métricas
- `compare_plans()`: Compara dois planos
- `simulate_scenario()`: Simula cenários com parâmetros modificados

## Fluxo de Dados

```
┌─────────────────────────────────────────────────────────────┐
│                    DECISION ENGINE                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Knowledge   │    │   Subject    │    │    Study     │  │
│  │   State      │    │   Data       │    │   Sessions   │  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘  │
│         │                   │                   │          │
│         └───────────────────┼───────────────────┘          │
│                             ▼                              │
│                    ┌────────────────┐                      │
│                    │ TopicContext   │                      │
│                    │ Collection     │                      │
│                    └────────┬───────┘                      │
│                             ▼                              │
│                    ┌────────────────┐                      │
│                    │    Ranking     │                      │
│                    │   (FinalScore) │                      │
│                    └────────┬───────┘                      │
│                             ▼                              │
│                    ┌────────────────┐                      │
│                    │   Policies     │                      │
│                    │  (Conflict     │                      │
│                    │   Detection)   │                      │
│                    └────────┬───────┘                      │
│                             ▼                              │
│                    ┌────────────────┐                      │
│                    │  Explanations  │                      │
│                    │  (ReasonCodes) │                      │
│                    └────────┬───────┘                      │
│                             ▼                              │
│                    ┌────────────────┐                      │
│                    │ Recommendations│                      │
│                    │   (Ordered)    │                      │
│                    └────────────────┘                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Integração com Planner Existente

O Decision Engine funciona em paralelo com o planner:

1. **Planner**: Gera sessões de estudo com base em disponibilidade
2. **Decision Engine**: Recomenda qual assunto estudar e por quê
3. **Dashboard**: Mostra "O que estudar agora?" usando o Decision Engine

### Modificação nos Modelos

- **StudyPlan**: Adicionado campo `is_active` para suportar planos arquivados
- **StudySession**: Adicionado campo `status` (scheduled, completed, missed, rescheduled, cancelled)

### Endpoints Novos

- `GET /decision-engine/recommendations`: Recomendações atuais
- `GET /decision-engine/debug`: Modo debug com scores detalhados
- `GET/POST /decision-engine/simulate`: Simulação e comparação de planos
- `GET /decision-engine/history`: Histórico de recomendações

## Segurança

- Todos os dados são isolados por usuário
- Nunca mistura dados de usuários diferentes
- Rate limiting em endpoints sensíveis
- CSRF protection em formulários
- Validação de entrada em todas as rotas

## Performance

- Queries otimizadas com índices adequados
- Uso de agregações SQL quando possível
- Cache de cálculos quando apropriado
- Evita N+1 queries
- Carrega apenas dados necessários

## Testes

- **Testes Determinísticos**: 14 cenários específicos
- **Testes de Invariantes**: Garante restrições fundamentais
- **Testes de Integração**: Verifica fluxo completo
- **Testes de Segurança**: Valida isolamento de usuários
