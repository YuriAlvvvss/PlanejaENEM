# Recommendation Engine - PlanejaENEM 4.0

## Visão Geral

O motor de recomendação do PlanejaENEM 4.0 é o componente central que gera sugestões de estudo personalizadas. Ele executa um ciclo completo de decisão que transforma dados de desempenho em ações concretas.

## Ciclo de Decisão

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

## Entradas do Sistema

### KnowledgeState
- `mastery_score`: Domínio atual (0-100)
- `confidence_score`: Confiança estatística (0-100)
- `recent_accuracy`: Acurácia recente
- `historical_accuracy`: Acurácia histórica
- `questions_answered`: Total de questões respondidas
- `questions_correct`: Questões corretas
- `questions_wrong`: Questões erradas
- `consecutive_correct`: Acertos consecutivos
- `consecutive_wrong`: Erros consecutivos
- `last_attempt_at`: Última tentativa
- `last_review_at`: Última revisão
- `trend`: Tendência (improving/stable/declining)

### Subject
- `nome`: Nome da matéria
- `dificuldade`: Dificuldade (1-5)
- `prioridade`: Prioridade (1-5)
- `area`: Área do ENEM

### Topic
- `nome`: Nome do tópico

### StudySession
- `session_date`: Data da sessão
- `completed`: Se foi concluída
- `status`: Status (scheduled/completed/missed)

### User Settings
- `exam_date`: Data da prova
- `weekly_goal_minutes`: Meta semanal
- `available_days`: Dias disponíveis
- `available_hours`: Horários disponíveis
- `daily_minutes`: Minutos por dia

## Saídas do Sistema

### StudyRecommendation
```python
@dataclass
class StudyRecommendation:
    priority: int                    # Posição no ranking
    subject_id: int                  # ID da matéria
    topic_id: Optional[int]         # ID do tópico
    action: StudyAction              # Ação recomendada
    duration_minutes: int            # Duração em minutos
    recommended_date: date           # Data recomendada
    score: float                     # Score final (0-100)
    mastery_score: float             # Domínio atual
    confidence_score: float          # Confiança atual
    reason_codes: list[ReasonCode]   # Códigos de motivo
    explanation: str                 # Explicação legível
    study_phase: StudyPhase          # Fase de estudo
    area: str                        # Área do ENEM
    subject_name: str                # Nome da matéria
    topic_name: str                  # Nome do tópico
```

### ReasonCodes

| Código | Significado | Ação Sugerida |
|--------|-------------|---------------|
| LOW_MASTERY | Domínio < 40% | Focar em teoria e exercícios básicos |
| MODERATE_MASTERY | Domínio 40-70% | Praticar mais questões |
| RECENT_ACCURACY_DROP | Queda recente | Revisar conceitos |
| RECENT_POOR_PERFORMANCE | Desempenho < 50% | Reforçar base |
| PERFORMANCE_DECLINING | Queda > 10% | Investigar causas |
| OVERDUE_REVIEW | Revisão atrasada | Priorizar revisão |
| EXAM_URGENCY | ENEM < 30 dias | Focar em questões ENEM |
| HIGH_DIFFICULTY | Dificuldade >= 4 | Deducar mais tempo |
| LOW_CONFIDENCE | Confiança < 40% | Coletar mais dados |
| MISSED_SESSION | Sessões perdidas | Recuperar tempo |
| NO_DATA | < 3 questões | Fazer avaliação inicial |

## Progressão de Aprendizagem

O sistema implementa uma progressão lógica:

```
Domínio < 40%
    ↓
Teoria + Exercícios Básicos
    ↓
Domínio 40-60%
    ↓
Exercícios Práticos
    ↓
Domínio 60-75%
    ↓
Questões ENEM
    ↓
Domínio 75-90%
    ↓
Questões Difíceis
    ↓
Domínio > 90%
    ↓
Revisão Espaçada + Manutenção
```

## Exemplo de Uso

### Python

```python
from datetime import date
from app.decision_engine import generate_recommendations, WeeklyAvailability

# Configurar disponibilidade
availability = WeeklyAvailability(
    days=["seg", "qua", "sex"],
    hours=["08:00-10:00", "14:00-16:00"],
    daily_minutes=180,
    weekly_goal_minutes=600,
)

# Gerar recomendações
result = process_planner_request(
    user_id=1,
    exam_date=date(2025, 11, 10),
    availability=availability,
)

# Acessar resultados
for rec in result["recommendations"]:
    print(f"{rec.subject_name} → {rec.topic_name}")
    print(f"  Ação: {rec.action.value}")
    print(f"  Duração: {rec.duration_minutes}min")
    print(f"  Score: {rec.score:.1f}")
    print(f"  Motivos: {rec.reason_codes}")
    print()
```

### API

```bash
# GET /decision-engine/api/recommendations
curl -H "Authorization: Bearer <token>" \
     http://localhost:5000/decision-engine/api/recommendations

# Response
{
  "recommendations": [
    {
      "priority": 1,
      "subject_id": 1,
      "topic_id": 3,
      "action": "practice",
      "duration_minutes": 40,
      "recommended_date": "2025-08-15",
      "score": 72.5,
      "mastery_score": 35.0,
      "confidence_score": 45.0,
      "reason_codes": ["low_mastery", "exam_urgency"],
      "explanation": "Domínio baixo | ENEM próximo"
    }
  ],
  "summary": {
    "total_recommendations": 8,
    "total_minutes": 480,
    "topics_analyzed": 15,
    "conflicts_detected": 0
  }
}
```

## Modo Debug

O modo debug fornece informações detalhadas sobre o cálculo:

```python
from app.decision_engine import generate_recommendations, build_debug_output

result = process_planner_request(user_id=1, ...)
debug = build_debug_output(result)
print(debug)
```

Saída:
```
======================================================================
PLANEJAENEM 4.0 - MODO DEBUG
======================================================================

Total de tópicos analisados: 15
Total de recomendações: 8
Tempo total recomendado: 480min
Fase de estudo: medium_term
Dias até o ENEM: 45
Conflitos detectados: 0
Conflitos resolvidos: 0

----------------------------------------------------------------------
RECOMENDAÇÕES ORDENADAS:
----------------------------------------------------------------------

#1 - Matemática → Funções
    Score: 72.50
    Domínio: 35%
    Confiança: 45%
    Ação: practice
    Duração: 40min
    Data: 2025-08-15
    Motivos: Domínio baixo | ENEM próximo

#2 - Português → Interpretação de Texto
    Score: 65.20
    ...
```

## Simulação

O simulador permite comparar planos:

```python
from app.decision_engine import simulate_plan, compare_plans, WeeklyAvailability

availability_a = WeeklyAvailability(
    days=["seg", "qua", "sex"],
    hours=["08:00-10:00"],
    daily_minutes=60,
    weekly_goal_minutes=300,
)

availability_b = WeeklyAvailability(
    days=["seg", "ter", "qua", "qui", "sex"],
    hours=["08:00-10:00"],
    daily_minutes=90,
    weekly_goal_minutes=630,
)

sim_a = simulate_plan(user_id=1, exam_date=exam_date, availability=availability_a)
sim_b = simulate_plan(user_id=1, exam_date=exam_date, availability=availability_b)

comparison = compare_plans(sim_a, sim_b)
print(comparison["analysis"]["recommendation"])
```

## Garantias

### Determinismo
- Mesmos dados → mesma recomendação
- Sem aleatoriedade
- Totalmente reproduzível

### Explicabilidade
- Todo reason code tem explicação
- Modo debug disponível
- Pesos documentados

### Segurança
- Isolamento por usuário
- Sem contaminação de dados
- Validação de entrada

### Performance
- Queries otimizadas
- Sem N+1 queries
- Agregações SQL
