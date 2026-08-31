# Scoring - PlanejaENEM 4.0

## Visão Geral

O sistema de scoring do PlanejaENEM 4.0 calcula prioridades de estudo usando múltiplos fatores ponderados. Todos os pesos são **heurísticas determinísticas** e podem ser ajustados com base em validação empírica.

**IMPORTANTE**: O sistema NÃO utiliza IA generativa, LLM ou machine learning. Toda a inteligência vem de estatísticas, regras determinísticas e histórico de desempenho.

## Score Final (FinalScore)

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

### Pesos Centralizados

Os pesos estão definidos em `app/decision_engine/ranking.py`:

```python
WEIGHTS = {
    "need_score": 0.25,
    "weakness": 0.20,
    "recency": 0.15,
    "exam_urgency": 0.15,
    "review_urgency": 0.10,
    "historical_importance": 0.10,
    "study_consistency": 0.05,
}
```

**Regra**: A soma dos pesos deve ser sempre 1.0 (100%).

## Componentes do Score

### 1. NeedScore (0.25)

Calcula a necessidade de estudo baseada em:

| Fator | Peso Interno | Descrição |
|-------|--------------|-----------|
| low_mastery | 0.30 | Inverso do domínio atual |
| recent_poor | 0.20 | Desempenho recente ruim |
| subject_difficulty | 0.15 | Dificuldade da matéria |
| exam_proximity | 0.15 | Proximidade do ENEM |
| overdue_review | 0.10 | Revisões atrasadas |
| confidence | 0.10 | Inverso da confiança |

**Fórmula**:
```python
need = (low_mastery * 0.30
      + recent_poor * 0.20
      + subject_diff * 0.15
      + exam_prox * 0.15
      + overdue_rev * 0.10
      + confidence * 0.10)
```

### 2. Weakness (0.20)

Calcula a fraqueza no assunto:

- **Base**: Inverso do domínio (100 - mastery_score)
- **Penalidade por tendência de queda**: +15 pontos se queda > 10%
- **Penalidade por erros consecutivos**: +20 pontos se >= 3 erros consecutivos

```python
weakness = 100.0 - mastery_score
if recent_accuracy < historical_accuracy - 10:
    weakness = min(100.0, weakness + 15.0)
if consecutive_wrong >= 3:
    weakness = min(100.0, weakness + 20.0)
```

### 3. Recency (0.15)

Calcula baseado no tempo desde a última atividade:

| Dias Inativo | Score |
|--------------|-------|
| 0-1 | 10 |
| 2-3 | 25 |
| 4-7 | 45 |
| 8-14 | 65 |
| 15-30 | 80 |
| 31+ | 100 |

### 4. ExamUrgency (0.15)

Calcula baseado na proximidade do ENEM:

| Dias até ENEM | Score |
|---------------|-------|
| 0 | 100 |
| 1-7 | 95 |
| 8-14 | 90 |
| 15-30 | 80 |
| 31-60 | 65 |
| 61-120 | 45 |
| 121-180 | 30 |
| 181+ | 15 |

### 5. ReviewUrgency (0.10)

Calcula baseado em revisões atrasadas:

- **Sem revisões atrasadas**: Score baseado no tempo desde última revisão
- **1 revisão atrasada**: 50
- **2 revisões atrasadas**: 75
- **3+ revisões atrasadas**: 100

### 6. HistoricalImportance (0.10)

Calcula baseado em prioridade e dificuldade:

```python
importance = (priority_factor * 0.6) + (difficulty_factor * 0.4)
```

Onde:
- `priority_factor = (subject_priority / 5.0) * 100.0`
- `difficulty_factor = (subject_difficulty / 5.0) * 100.0`

### 7. StudyConsistency (0.05)

Calcula baseado em sessões perdidas:

| Sessões Perdidas | Score |
|------------------|-------|
| 0 | 50 |
| 1-2 | 40 |
| 3-4 | 25 |
| 5+ | 10 |

## Determinação de Ação

A ação recomendada é determinada pelo domínio atual:

| Domínio | Ação Recomendada |
|---------|------------------|
| 0-39% | LEARN (teoria) |
| 40-59% | PRACTICE (exercícios) |
| 60-74% | ENEM_QUESTIONS (questões ENEM) |
| 75-89% | DIFFICULT_QUESTIONS (questões difíceis) |
| 90-100% | REVIEW (revisão) ou DIFFICULT_QUESTIONS |

**Exceção**: Na fase FINAL_STRETCH (< 30 dias para ENEM), prioriza questões ENEM.

## Estimativa de Duração

A duração é estimada baseada na ação e domínio:

| Ação | Duração Base |
|------|--------------|
| LEARN | 45 min |
| PRACTICE | 40 min |
| ENEM_QUESTIONS | 35 min |
| REVIEW | 25 min |
| DIFFICULT_QUESTIONS | 40 min |
| MOCK_EXAM | 60 min |

**Ajustes**:
- Domínio < 30%: +30% na duração
- Domínio > 80%: -20% na duração
- Fase FINAL_STRETCH: -10% na duração

## Reason Codes

Cada recomendação possui uma lista de reason codes explicando por que foi recomendada:

| Reason Code | Significado |
|-------------|-------------|
| LOW_MASTERY | Domínio abaixo de 40% |
| MODERATE_MASTERY | Domínio entre 40-70% |
| RECENT_ACCURACY_DROP | Queda recente de desempenho |
| RECENT_POOR_PERFORMANCE | Desempenho recente < 50% |
| PERFORMANCE_DECLINING | Queda > 10% em relação ao histórico |
| OVERDUE_REVIEW | Revisão atrasada |
| EXAM_URGENCY | ENEM em < 30 dias |
| HIGH_DIFFICULTY | Matéria com dificuldade >= 4 |
| LOW_CONFIDENCE | Confiança < 40% |
| MISSED_SESSION | Sessões perdidas |
| NO_DATA | Poucos dados (< 3 questões) |

## Exemplo de Cálculo

### Contexto
- Matemática: Funções
- Domínio: 35%
- Confiança: 45%
- Última atividade: 10 dias atrás
- ENEM: 25 dias
- Revisão atrasada: 1
- Dificuldade: 4
- Prioridade: 4

### Cálculo

```
NeedScore:
  low_mastery = 100 - 35 = 65
  recent_poor = 50 (neutro)
  subject_diff = ((4-1)/4) * 100 = 75
  exam_prox = 80 (25 dias)
  overdue_rev = 50 (1 revisão)
  confidence = 100 - 45 = 55
  
  need = 65*0.30 + 50*0.20 + 75*0.15 + 80*0.15 + 50*0.10 + 55*0.10
       = 19.5 + 10 + 11.25 + 12 + 5 + 5.5 = 63.25

Weakness:
  weakness = 100 - 35 = 65

Recency:
  10 dias → 65

ExamUrgency:
  25 dias → 80

ReviewUrgency:
  1 revisão atrasada → 50

HistoricalImportance:
  priority = (4/5)*100 = 80
  difficulty = (4/5)*100 = 80
  importance = 80*0.6 + 80*0.4 = 80

StudyConsistency:
  0 sessões perdidas → 50

FinalScore:
  = 63.25*0.25 + 65*0.20 + 65*0.15 + 80*0.15 + 50*0.10 + 80*0.10 + 50*0.05
  = 15.81 + 13 + 9.75 + 12 + 5 + 8 + 2.5
  = 66.06
```

### Resultado
- **Score Final**: 66.06
- **Ação**: PRACTICE (domínio 35%)
- **Duração**: 40 min
- **Reason Codes**: LOW_MASTERY, OVERDUE_REVIEW, EXAM_URGENCY, HIGH_DIFFICULTY
