"""
Explicabilidade - PlanejaENEM 4.0.

Transforma reason codes em textos amigáveis para o usuário.
Cada reason code possui uma explicação clara e objetiva.
"""

from typing import Optional

from app.decision_engine.types import ReasonCode, TopicContext


# =============================================================================
# MAPA DE EXPLICAÇÕES - TEXTOS AMIGÁVEIS
# =============================================================================
# Cada reason code possui uma explicação em português que descreve
# por que aquela recomendação foi feita.
# =============================================================================

REASON_TEXTS = {
    ReasonCode.LOW_MASTERY: (
        "Seu domínio estimado neste assunto ainda é baixo. "
        "Estudar este tópico ajudará a aumentar sua compreensão."
    ),
    ReasonCode.MODERATE_MASTERY: (
        "Seu domínio é intermediário. "
        "Com mais prática, você pode atingir um nível mais alto."
    ),
    ReasonCode.RECENT_ACCURACY_DROP: (
        "Seu desempenho caiu nas questões mais recentes. "
        "Revisar este assunto pode ajudar a reverter a tendência."
    ),
    ReasonCode.RECENT_POOR_PERFORMANCE: (
        "Suas respostas recentes neste assunto estão com baixa taxa de acerto. "
        "Foque em exercícios para melhorar."
    ),
    ReasonCode.PERFORMANCE_DECLINING: (
        "Você apresenta queda de desempenho em relação ao histórico. "
        "Este assunto precisa de atenção."
    ),
    ReasonCode.OVERDUE_REVIEW: (
        "Você tem revisões atrasadas neste assunto. "
        "Revisar o conteúdo estudado é essencial para a fixação."
    ),
    ReasonCode.EXAM_URGENCY: (
        "A data do ENEM está próxima. "
        "Priorize assuntos com maior impacto na prova."
    ),
    ReasonCode.HIGH_DIFFICULTY: (
        "Este assunto é considerado de alta dificuldade. "
        "Requer mais tempo e atenção."
    ),
    ReasonCode.LOW_CONFIDENCE: (
        "Ainda há poucos dados para avaliar seu domínio com precisão. "
        "Mais questões ajudarão a refletir seu real conhecimento."
    ),
    ReasonCode.STRONG_PERFORMANCE: (
        "Você tem um bom desempenho neste assunto. "
        "Mantenha com revisões periódicas."
    ),
    ReasonCode.BALANCE_AREA: (
        "É importante balancear estudos entre todas as áreas do ENEM. "
        "Este assunto contribui para o equilíbrio."
    ),
    ReasonCode.MISSED_SESSION: (
        "Você perdeu sessões anteriores neste assunto. "
        "Recuperar o tempo perdido é importante."
    ),
    ReasonCode.NO_DATA: (
        "Este assunto ainda não possui dados suficientes. "
        "Comece com questões para avaliar seu nível."
    ),
    ReasonCode.NEEDS_INITIAL_ASSESSMENT: (
        "Recomendamos começar com questões para avaliar seu domínio atual."
    ),
    ReasonCode.TIME_CONSTRAINT: (
        "O tempo disponível é limitado. "
        "Priorizamos os assuntos mais impactantes."
    ),
    ReasonCode.WEEKLY_GOAL_EXCEEDED: (
        "A meta semanal excedeu o tempo disponível. "
        "Ajustamos para caber na sua rotina."
    ),
    ReasonCode.CONSECUTIVE_LIMIT: (
        "Evitamos muitas sessões seguidas do mesmo assunto. "
        "Alternar melhora a absorção do conteúdo."
    ),
}


# =============================================================================
# TEXTOS POR TIPO DE AÇÃO
# =============================================================================

ACTION_TEXTS = {
    "learn": "Estudar teoria e conceitos",
    "practice": "Resolver exercícios práticos",
    "enem_questions": "Responder questões de provas anteriores do ENEM",
    "review": "Revisar conteúdo estudado",
    "difficult_questions": "Resolver questões difíceis avançadas",
    "mock_exam": "Realizar simulado completo",
}


# =============================================================================
# TEXTOS POR NÍVEL DE DOMÍNIO
# =============================================================================

MASTERY_LEVEL_TEXTS = {
    "critical": "Domínio crítico - precisa de atenção urgente",
    "low": "Domínio baixo - pratique mais",
    "medium": "Domínio médio - continue evoluindo",
    "good": "Domínio bom - mantenha com revisões",
    "excellent": "Domínio excelente - foco em manutenção",
}


def build_explanation(
    reason_codes: list[ReasonCode],
    context: Optional[TopicContext] = None,
) -> str:
    """
    Gera texto explicativo baseado nos reason codes.
    
    Args:
        reason_codes: Lista de códigos de motivo
        context: Contexto opcional do tópico para enriquecer a explicação
    
    Returns:
        Texto explicativo formatado
    """
    if not reason_codes:
        return "Recomendação baseada na análise geral de desempenho."

    explanations = []

    for code in reason_codes:
        text = REASON_TEXTS.get(code, "")
        if text:
            explanations.append(f"• {text}")

    if context:
        mastery_text = MASTERY_LEVEL_TEXTS.get(
            context.mastery_level.value, ""
        )
        if mastery_text:
            explanations.append(f"• {mastery_text}")

    return "\n".join(explanations)


def build_short_explanation(
    reason_codes: list[ReasonCode],
) -> str:
    """
    Gera explicação curta para uso em interfaces compactas.
    """
    if not reason_codes:
        return "Análise de desempenho"

    short_texts = {
        ReasonCode.LOW_MASTERY: "Domínio baixo",
        ReasonCode.MODERATE_MASTERY: "Domínio intermediário",
        ReasonCode.RECENT_ACCURACY_DROP: "Queda recente",
        ReasonCode.RECENT_POOR_PERFORMANCE: "Desempenho baixo",
        ReasonCode.PERFORMANCE_DECLINING: "Tendência de queda",
        ReasonCode.OVERDUE_REVIEW: "Revisão atrasada",
        ReasonCode.EXAM_URGENCY: "ENEM próximo",
        ReasonCode.HIGH_DIFFICULTY: "Alta dificuldade",
        ReasonCode.LOW_CONFIDENCE: "Poucos dados",
        ReasonCode.STRONG_PERFORMANCE: "Bom desempenho",
        ReasonCode.BALANCE_AREA: "Equilíbrio de áreas",
        ReasonCode.MISSED_SESSION: "Sessão perdida",
        ReasonCode.NO_DATA: "Sem dados",
        ReasonCode.NEEDS_INITIAL_ASSESSMENT: "Avaliação inicial",
        ReasonCode.TIME_CONSTRAINT: "Tempo limitado",
        ReasonCode.WEEKLY_GOAL_EXCEEDED: "Meta excedida",
        ReasonCode.CONSECUTIVE_LIMIT: "Limite de sessões",
    }

    texts = []
    for code in reason_codes[:3]:
        text = short_texts.get(code, "")
        if text:
            texts.append(text)

    return " | ".join(texts) if texts else "Análise de desempenho"


def build_debug_explanation(
    reason_codes: list[ReasonCode],
    components: dict,
    weights: dict,
    final_score: float,
) -> str:
    """
    Gera explicação detalhada para modo debug.
    
    Inclui scores individuais, pesos e reason codes.
    """
    lines = [
        "=" * 60,
        "MODO DEBUG - EXPlicação Detalhada",
        "=" * 60,
        f"\nScore Final: {final_score:.2f}",
        "\nComponentes:",
    ]

    for key, value in components.items():
        weight = weights.get(key, 0)
        weighted = value * weight
        lines.append(f"  {key}: {value:.2f} (peso: {weight}) = {weighted:.2f}")

    lines.append(f"\nSoma ponderada: {final_score:.2f}")

    lines.append("\nReason Codes:")
    for code in reason_codes:
        text = REASON_TEXTS.get(code, "Código desconhecido")
        lines.append(f"  - {code.value}: {text[:80]}...")

    lines.append("\n" + "=" * 60)

    return "\n".join(lines)


def get_action_text(action: str) -> str:
    """Retorna texto descritivo para uma ação de estudo."""
    return ACTION_TEXTS.get(action, "Estudar")


def get_mastery_level_text(mastery_level: str) -> str:
    """Retorna texto descritivo para um nível de domínio."""
    return MASTERY_LEVEL_TEXTS.get(mastery_level, "Domínio não avaliado")
