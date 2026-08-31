"""
Políticas de seleção e diversidade - PlanejaENEM 5.0.

Controla a seleção de questões para avaliações adaptativas,
garantindo diversidade e evitando repetições.

Regras:
  - Evitar questões repetidas (mesmo question_id)
  - Evitar mesmo tópico em excesso (>40% das questões)
  - Evitar mesma dificuldade em sequência sem necessidade
  - Promover diversidade de assuntos e dificuldades
  - Reutilizar questões válidas já armazenadas
"""

from __future__ import annotations

from typing import Optional


# =============================================================================
# LIMITES DE DIVERSIDADE
# =============================================================================
MAX_SAME_TOPIC_RATIO = 0.4  # Máximo 40% de questões do mesmo tópico
MAX_CONSECUTIVE_SAME_DIFFICULTY = 3  # Máx 3 questões seguidas mesma dificuldade
MIN_DIFFICULTY_VARIANCE = 0.5  # Variação mínima entre dificuldades consecutivas


def should_avoid_question(
    question_id: int,
    used_question_ids: set[int],
) -> bool:
    """
    Verifica se uma questão deve ser evitada (já foi usada).
    
    Args:
        question_id: ID da questão candidata.
        used_question_ids: IDs das questões já utilizadas na avaliação.
        
    Returns:
        True se a questão deve ser evitada.
    """
    return question_id in used_question_ids


def check_topic_diversity(
    topic_id: int,
    total_questions: int,
    topic_counts: dict[int, int],
) -> bool:
    """
    Verifica se o tópico respeita o limite de diversidade.
    
    Args:
        topic_id: ID do tópico candidato.
        total_questions: Total de questões já feitas.
        topic_counts: Contagem de questões por tópico.
        
    Returns:
        True se o tópico pode ser usado (dentro do limite).
    """
    if total_questions < 3:
        return True

    current_count = topic_counts.get(topic_id, 0)
    projected_ratio = (current_count + 1) / (total_questions + 1)

    return projected_ratio <= MAX_SAME_TOPIC_RATIO


def check_difficulty_sequence(
    new_difficulty: float,
    recent_difficulties: list[float],
) -> float:
    """
    Verifica e ajusta a sequência de dificuldades.
    
    Evita 3+ questões seguidas com mesma dificuldade.
    Ajusta a dificuldade se necessário para manter diversidade.
    
    Args:
        new_difficulty: Dificuldade proposta.
        recent_difficulties: Últimas 5 dificuldades usadas.
        
    Returns:
        Dificuldade ajustada (pode ser a mesma se OK).
    """
    if len(recent_difficulties) < MAX_CONSECUTIVE_SAME_DIFFICULTY:
        return new_difficulty

    # Verificar se últimas N são iguais
    last_n = recent_difficulties[-MAX_CONSECUTIVE_SAME_DIFFICULTY:]
    all_same = all(
        abs(d - last_n[0]) < MIN_DIFFICULTY_VARIANCE for d in last_n
    )

    if not all_same:
        return new_difficulty

    # Se todas iguais, forçar variação
    last_diff = recent_difficulties[-1]
    if new_difficulty >= last_diff:
        # Subiu ou manteve: descer um pouco
        adjusted = max(1.0, last_diff - MIN_DIFFICULTY_VARIANCE)
    else:
        # Desceu: subir um pouco
        adjusted = min(5.0, last_diff + MIN_DIFFICULTY_VARIANCE)

    return round(adjusted, 2)


def select_best_question_from_candidates(
    candidates: list[dict],
    used_question_ids: set[int],
    topic_counts: dict[int, int],
    total_questions: int,
    recent_difficulties: list[float],
    target_difficulty: float,
) -> Optional[dict]:
    """
    Seleciona a melhor questão de uma lista de candidatas.
    
    Aplica todas as políticas de diversidade e retorna a questão
    mais adequada.
    
    Args:
        candidates: Lista de questões candidatas (dicts com id, topic_id, dificuldade).
        used_question_ids: IDs já utilizados.
        topic_counts: Contagem por tópico.
        total_questions: Total de questões na avaliação.
        recent_difficulties: Últimas dificuldades usadas.
        target_difficulty: Dificuldade alvo do Decision Engine.
        
    Returns:
        Questão selecionada ou None.
    """
    if not candidates:
        return None

    scored = []
    for q in candidates:
        q_id = q.get("id")
        q_topic = q.get("topic_id")
        q_diff = q.get("dificuldade", 3)

        # Penalizar questões já usadas
        if should_avoid_question(q_id, used_question_ids):
            continue

        # Penalizar tópicos em excesso
        if not check_topic_diversity(q_topic, total_questions, topic_counts):
            continue

        # Score de proximidade com dificuldade alvo
        diff_distance = abs(q_diff - target_difficulty)
        score = 100.0 - (diff_distance * 20)

        scored.append((score, q))

    if not scored:
        return None

    # Ordenar por score (maior primeiro)
    scored.sort(key=lambda x: x[0], reverse=True)

    # Top 3 candidatos, escolher aleatoriamente para diversidade
    top = scored[:min(3, len(scored))]
    import random
    _, selected = random.choice(top)
    return selected


def build_assessment_result(
    correct_count: int,
    wrong_count: int,
    total_time_seconds: int,
    question_difficulties: list[float],
    question_correctness: list[bool],
) -> dict:
    """
    Calcula métricas finais da avaliação.
    
    Args:
        correct_count: Total de acertos.
        wrong_count: Total de erros.
        total_time_seconds: Tempo total em segundos.
        question_difficulties: Lista de dificuldades das questões.
        question_correctness: Lista de True/False por questão.
        
    Returns:
        Dict com métricas calculadas.
    """
    total = correct_count + wrong_count
    accuracy = (correct_count / total * 100) if total > 0 else 0.0
    avg_time = (total_time_seconds / total) if total > 0 else 0.0
    avg_difficulty = (
        sum(question_difficulties) / len(question_difficulties)
        if question_difficulties
        else 3.0
    )

    # Desempenho por faixa de dificuldade
    by_difficulty = {}
    for diff, correct in zip(question_difficulties, question_correctness):
        bucket = int(diff)
        if bucket not in by_difficulty:
            by_difficulty[bucket] = {"total": 0, "correct": 0}
        by_difficulty[bucket]["total"] += 1
        if correct:
            by_difficulty[bucket]["correct"] += 1

    difficulty_performance = {}
    for bucket, data in sorted(by_difficulty.items()):
        acc = (data["correct"] / data["total"] * 100) if data["total"] > 0 else 0.0
        difficulty_performance[bucket] = {
            "total": data["total"],
            "correct": data["correct"],
            "accuracy": round(acc, 2),
        }

    return {
        "accuracy": round(accuracy, 2),
        "total_questions": total,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "average_time_seconds": round(avg_time, 1),
        "average_difficulty": round(avg_difficulty, 2),
        "difficulty_performance": difficulty_performance,
    }
