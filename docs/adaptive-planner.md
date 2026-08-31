# Planner Adaptativo - PlanejaENEM 4.0

## Visão Geral

O Planner Adaptativo do PlanejaENEM 4.0 combina o planner existente com o novo Decision Engine para criar um sistema de estudo inteligente e personalizado.

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    PLANNER ADAPTATIVO                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Planner    │    │   Decision   │    │   Dashboard  │  │
│  │   (Base)     │ ←→ │   Engine     │ ←→ │   4.0        │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                   │                   │          │
│         ▼                   ▼                   ▼          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Sessões    │    │ Recomendações│    │  "O que      │  │
│  │   de Estudo  │    │   Com        │    │  estudar     │  │
│  │              │    │   Reason     │    │  agora?"     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Componentes

### 1. Planner Base (Existente)

Responsável por:
- Gerar sessões de estudo
- Distribuir tempo disponível
- Respeitar disponibilidade do aluno
- Reagendar sessões perdidas

### 2. Decision Engine (Novo)

Responsável por:
- Recomendar qual assunto estudar
- Determinar tipo de estudo
- Explicar por que foi recomendado
- Detectar e resolver conflitos

### 3. Dashboard 4.0 (Novo)

Responsável por:
- Mostrar "O que estudar agora?"
- Exibir mapa de domínio
- Mostrar progressão
- Exibir histórico de recomendações

## Fluxo de Trabalho

### 1. Configuração Inicial

```
Aluno configura:
├── Data da prova (ENEM)
├── Dias disponíveis
├── Horários disponíveis
├── Meta semanal
└── Matérias e prioridades
```

### 2. Geração do Plano

```
Planner Base:
├── Calcula disponibilidade
├── Gera grade de horários
├── Distribui tempo entre matérias
└── Cria sessões de estudo

Decision Engine:
├── Analisa domínio de cada tópico
├── Calcula scores de prioridade
├── Gera recomendações ordenadas
└── Adiciona reason codes
```

### 3. Execução

```
Aluno estuda:
├── Segue recomendações do Dashboard
├── Marca sessões como concluídas
├── Responde questões
└── Atualiza desempenho
```

### 4. Feedback Loop

```
Após cada sessão:
├── Atualiza KnowledgeState
├── Recalcula mastery_score
├── Atualiza tendência
├── Recalcula necessidade
└── Gera novas recomendações
```

## Integração com Planner Existente

### Modificações nos Modelos

#### StudyPlan
```python
# Novo campo
is_active = db.Column(db.Boolean, nullable=False, default=True)
```

- `True`: Plano atual (ativo)
- `False`: Plano antigo (arquivado)

#### StudySession
```python
# Novos campos
status = db.Column(db.String(20), nullable=False, default="scheduled")
reason_codes = db.Column(db.Text, nullable=True)
explanation = db.Column(db.Text, nullable=True)
```

Status possíveis:
- `scheduled`: Agendada
- `completed`: Concluída
- `missed`: Perdida
- `rescheduled`: Reagendada
- `cancelled`: Cancelada

### Comportamento de Regeneração

Quando o aluno regenera um plano:

1. **Plano anterior** → `is_active = False` (arquivado)
2. **Novo plano** → `is_active = True`
3. **Histórico** → Permanece intacto

### Comportamento de Sessão Perdida

Quando uma sessão é marcada como perdida:

1. **Status** → `missed`
2. **Não contamina** horas estudadas
3. **Recalcula** prioridade
4. **Reagenda** se houver disponibilidade
5. **Registra** que foi reagendada

## Dashboard 4.0

### Seção "O que estudar agora?"

```html
<div class="card border-primary">
    <div class="card-header bg-primary text-white">
        <h4>O que estudar agora?</h4>
    </div>
    <div class="card-body">
        <h3>Matemática → Funções</h3>
        <p>Domínio: 35% | Confiança: 45%</p>
        <p>Recomendação: 40min de exercícios</p>
        <div class="alert alert-info">
            <strong>Por quê?</strong>
            <ul>
                <li>Domínio baixo</li>
                <li>ENEM próximo</li>
                <li>Revisão atrasada</li>
            </ul>
        </div>
    </div>
</div>
```

### Mapa de Domínio

```html
<table class="table">
    <thead>
        <tr>
            <th>Matéria</th>
            <th>Tópico</th>
            <th>Domínio</th>
            <th>Nível</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>Matemática</td>
            <td>Funções</td>
            <td>
                <div class="progress">
                    <div class="progress-bar bg-danger" style="width: 35%">
                        35%
                    </div>
                </div>
            </td>
            <td>Crítico</td>
        </tr>
    </tbody>
</table>
```

### Níveis de Domínio

| Faixa | Nível | Cor | Ação |
|-------|-------|-----|------|
| 0-39% | Crítico | Vermelho | Teoria urgente |
| 40-59% | Baixo | Laranja | Exercícios |
| 60-74% | Médio | Amarelo | Questões ENEM |
| 75-89% | Bom | Verde Claro | Questões difíceis |
| 90-100% | Excelente | Verde Escuro | Manutenção |

## Endpoints

### GET /planner/
- Exibe formulário do planner
- Mostra plano ativo existente

### POST /planner/
- Gera novo plano de estudo
- Arquiva plano anterior automaticamente

### POST /planner/<id>/regenerate
- Arquiva plano específico
- Permite gerar novo plano

### POST /planner/replan
- Detecta sessões perdidas
- Reagenda automaticamente

### GET /planner/diagnostics
- Exibe diagnóstico de desempenho

### GET /decision-engine/recommendations
- Exibe recomendações do Decision Engine

### GET /decision-engine/debug
- Exibe modo debug com scores detalhados

### GET/POST /decision-engine/simulate
- Permite simular e comparar planos

### GET /decision-engine/history
- Exibe histórico de recomendações

## Uso

### Criar Plano

1. Acesse `/planner/`
2. Configure disponibilidade
3. Defina prioridades das matérias
4. Clique em "Gerar Cronograma"

### Ver Recomendações

1. Acesse `/decision-engine/recommendations`
2. Veja a recomendação principal
3. Siga as sugestões de estudo

### Simular Planos

1. Acesse `/decision-engine/simulate`
2. Configure dois cenários
3. Compare cobertura de prioridades

### Modo Debug

1. Acesse `/decision-engine/debug`
2. Veja scores detalhados
3. Analise reason codes

## Garantias

### Determinismo
- Mesmos dados → mesmo plano
- Sem aleatoriedade
- Totalmente reproduzível

### Não-Invasivo
- Não substitui planner existente
- Funciona em paralelo
- Pode ser desativado

### Explicável
- Toda recomendação tem motivo
- Modo debug disponível
- Pesos documentados

### Offline
- Funciona 100% offline
- Sem dependências externas
- Todos os cálculos locais
