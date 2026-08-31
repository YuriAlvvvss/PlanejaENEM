"""
Decision Engine de avaliação adaptativa - PlanejaENEM 5.0.

Decide assunto e dificuldade da próxima questão com base no
desempenho atual do aluno. Totalmente determinístico (sem IA).

Dificuldade inicial (baseada no mastery):
  mastery < 40  → 1-2
  40-59         → 2-3
  60-74         → 3
  75-89         → 3-4
  90+           → 4-5

Ajuste durante a avaliação:
  Acertou → mantém ou sobe 0.5
  Errou   → mantém ou desce 0.5-1.0
  Evitar grandes saltos (máx ±1.0 por questão)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional


# =============================================================================
# LIMITES E CONSTANTES
# =============================================================================
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5
MAX_DIFFICULTY_STEP = 1.0
SMALL_DIFFICULTY_STEP = 0.5

# Faixas de mastery -> dificuldade inicial
MASTERY_RANGES = [
    (90, 4.5),   # mastery >= 90 → 4-5 (início em 4.5)
    (75, 3.5),   # mastery >= 75 → 3-4
    (60, 3.0),   # mastery >= 60 → 3
    (40, 2.5),   # mastery >= 40 → 2-3
    (0,  1.5),   # mastery < 40  → 1-2
]


@dataclass(frozen=True)
class AssessmentDecision:
    """Decisão do engine para a próxima questão."""
    subject_id: int
    topic_id: Optional[int]
    difficulty: float
    area: str
    subject_name: str
    topic_name: str
    reason: str


@dataclass
class AssessmentState:
    """
    Estado acumulado da avaliação.
    
    Usado pelo engine para tomar decisões baseadas no histórico
    de respostas da sessão atual.
    """
    questions_answered: int = 0
    correct_count: int = 0
    wrong_count: int = 0
    current_difficulty: float = 3.0
    recent_results: list[bool] = field(default_factory=list)
    used_question_ids: set[int] = field(default_factory=set)
    used_topic_ids: list[int] = field(default_factory=list)
    subject_id: Optional[int] = None

    @property
    def accuracy(self) -> float:
        """Acurácia da avaliação (0-100)."""
        if self.questions_answered <= 0:
            return 0.0
        return (self.correct_count / self.questions_answered) * 100.0

    @property
    def recent_accuracy(self) -> float:
        """Acurácia das últimas 5 questões."""
        if not self.recent_results:
            return 0.0
        window = self.recent_results[-5:]
        return (sum(window) / len(window)) * 100.0

    @property
    def streak(self) -> int:
        """
        Streak atual: positivo = acertos, negativo = erros.
        Exemplo: +3 = 3 acertos seguidos, -2 = 2 erros seguidos.
        """
        if not self.recent_results:
            return 0
        streak = 0
        last_result = self.recent_results[-1]
        for result in reversed(self.recent_results):
            if result == last_result:
                streak += 1 if last_result else -1
            else:
                break
        return streak


def get_initial_difficulty(mastery_score: float) -> float:
    """
    Calcula a dificuldade inicial baseada no mastery do tópico.
    
    Args:
        mastery_score: Score de domínio (0-100).
        
    Returns:
        Dificuldade inicial (1.0-5.0).
    """
    for threshold, difficulty in MASTERY_RANGES:
        if mastery_score >= threshold:
            return difficulty
    return 1.5


def adjust_difficulty(
    current_difficulty: float,
    correct: bool,
    streak: int,
) -> float:
    """
    Ajusta a dificuldade baseado no resultado mais recente.
    
    Args:
        current_difficulty: Dificuldade atual (1.0-5.0).
        correct: Se a resposta foi correta.
        streak: Streak atual (positivo=acertos, negativo=erros).
        
    Returns:
        Nova dificuldade (1.0-5.0), com saltos limitados.
    """
    if correct:
        # Acertou: subir dificuldade
        if streak >= 3:
            step = MAX_DIFFICULTY_STEP
        elif streak >= 1:
            step = SMALL_DIFFICULTY_STEP
        else:
            step = SMALL_DIFFICULTY_STEP
        new_difficulty = current_difficulty + step
    else:
        # Errou: reduzir dificuldade
        if streak <= -3:
            step = MAX_DIFFICULTY_STEP
        elif streak <= -1:
            step = SMALL_DIFFICULTY_STEP + 0.25
        else:
            step = SMALL_DIFFICULTY_STEP
        new_difficulty = current_difficulty - step

    # Limitar faixa
    new_difficulty = max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, new_difficulty))
    return round(new_difficulty, 2)


def select_topic_for_question(
    knowledge_states: list[dict],
    used_topic_ids: list[int],
    subject_id: Optional[int] = None,
) -> Optional[dict]:
    """
    Seleciona o tópico mais adequado para a próxima questão.
    
    Prioriza:
    1. Tópicos com mastery mais baixo (áreas fracas)
    2. Tópicos não utilizados recentemente na avaliação
    3. Tópicos da matéria especificada (se houver)
    
    Args:
        knowledge_states: Lista de KnowledgeState dicts do usuário.
        used_topic_ids: IDs dos tópicos já usados nesta avaliação.
        subject_id: Matéria específica (opcional).
        
    Returns:
        Dict do KnowledgeState selecionado ou None.
    """
    if not knowledge_states:
        return None

    candidates = knowledge_states

    # Filtrar por matéria se especificada
    if subject_id is not None:
        filtered = [ks for ks in candidates if ks.get("subject_id") == subject_id]
        if filtered:
            candidates = filtered

    # Dar preferência a tópicos não usados recentemente
    unused = [ks for ks in candidates if ks.get("topic_id") not in used_topic_ids]
    if unused:
        candidates = unused

    # Ordenar por mastery crescente (áreas fracas primeiro)
    candidates.sort(key=lambda ks: ks.get("mastery_score", 50.0))

    # Top 3 com menor mastery, escolher aleatoriamente para diversidade
    top_candidates = candidates[:min(3, len(candidates))]
    return random.choice(top_candidates)


def decide_next_question(
    state: AssessmentState,
    knowledge_states: list[dict],
) -> Optional[AssessmentDecision]:
    """
    Decide os parâmetros da próxima questão.
    
    O Decision Engine é 100% determinísticoexceto pela seleção
    entre top candidatos (para diversidade controlada).
    
    Args:
        state: Estado atual da avaliação.
        knowledge_states: KnowledgeStates do usuário.
        
    Returns:
        AssessmentDecision com subject_id, topic_id, difficulty, etc.
        ou None se não houver tópicos disponíveis.
    """
    # Selecionar tópico
    selected = select_topic_for_question(
        knowledge_states=knowledge_states,
        used_topic_ids=state.used_topic_ids,
        subject_id=state.subject_id,
    )

    if selected is None:
        return None

    # Ajustar dificuldade
    if state.questions_answered > 0:
        new_difficulty = adjust_difficulty(
            current_difficulty=state.current_difficulty,
            correct=state.recent_results[-1] if state.recent_results else True,
            streak=state.streak,
        )
    else:
        new_difficulty = state.current_difficulty

    # Montar decisão
    topic_id = selected.get("topic_id")
    subject_id = selected.get("subject_id")
    area = selected.get("area", "outro")
    subject_name = selected.get("subject_name", "")
    topic_name = selected.get("topic_name", "")

    # Construir reason
    mastery = selected.get("mastery_score", 0.0)
    if mastery < 40:
        reason = f"Domínio baixo ({mastery:.0f}%) — foco em fundamentos"
    elif mastery < 60:
        reason = f"Domínio intermediário ({mastery:.0f}%) — praticar exercícios"
    elif mastery < 75:
        reason = f"Domínio em desenvolvimento ({mastery:.0f}%) — questões ENEM"
    elif mastery < 90:
        reason = f"Bom domínio ({mastery:.0f}%) — questões desafiadoras"
    else:
        reason = f"Domínio excelente ({mastery:.0f}%) — manutenção"

    if state.questions_answered > 0:
        last_correct = state.recent_results[-1] if state.recent_results else None
        if last_correct is True:
            reason += " | Acertou última → subindo dificuldade"
        elif last_correct is False:
            reason += " | Errou última → reduzindo dificuldade"

    return AssessmentDecision(
        subject_id=subject_id,
        topic_id=topic_id,
        difficulty=round(new_difficulty, 1),
        area=area,
        subject_name=subject_name,
        topic_name=topic_name,
        reason=reason,
    )


def is_assessment_complete(state: AssessmentState, target: int) -> bool:
    """Verifica se a avaliação atingiu o número alvo de questões."""
    return state.questions_answered >= target


def build_result_summary(state: AssessmentState) -> dict:
    """
    Gera o resumo final da avaliação.
    
    Retorna accuracy, desempenho por dificuldade, tempo médio, etc.
    """
    return {
        "total_questions": state.questions_answered,
        "correct_count": state.correct_count,
        "wrong_count": state.wrong_count,
        "accuracy": round(state.accuracy, 2),
        "final_difficulty": state.current_difficulty,
        "difficulty_range": {
            "min": MIN_DIFFICULTY,
            "max": MAX_DIFFICULTY,
        },
    }
