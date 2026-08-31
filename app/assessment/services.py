"""
Services de avaliação adaptativa - PlanejaENEM 5.0.

Orquestra o fluxo completo de avaliação adaptativa:
  1. Iniciar avaliação (criar Assessment, difficulty inicial)
  2. Buscar próxima questão (Decision Engine → banco/IA → retorno)
  3. Registrar resposta (atualizar assessment, KnowledgeState)
  4. Finalizar avaliação (gerar resultado completo)

REGRA DE OURO: A IA apenas gera a questão.
O backend controla resultado, acerto, dificuldade, mastery, confiança.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.extensions import db
from app.models import Question, Subject, Topic
from app.performance.models import KnowledgeState
from app.performance.services import update_knowledge_state

from app.assessment.engine import (
    AssessmentDecision,
    AssessmentState,
    build_result_summary,
    decide_next_question,
    get_initial_difficulty,
    is_assessment_complete,
)
from app.assessment.models import Assessment, AssessmentQuestion
from app.assessment.policies import (
    build_assessment_result,
    check_difficulty_sequence,
)

logger = logging.getLogger(__name__)


def _get_knowledge_states_as_dicts(user_id: int) -> list[dict]:
    """
    Busca KnowledgeStates do usuário como lista de dicts.
    
    Inclui campos necessários para o Decision Engine:
    topic_id, subject_id, mastery_score, area, subject_name, topic_name.
    """
    states = (
        db.session.query(KnowledgeState, Subject, Topic)
        .join(Subject, KnowledgeState.subject_id == Subject.id)
        .join(Topic, KnowledgeState.topic_id == Topic.id)
        .filter(KnowledgeState.user_id == user_id)
        .all()
    )

    return [
        {
            "topic_id": ks.topic_id,
            "subject_id": ks.subject_id,
            "mastery_score": ks.mastery_score,
            "confidence_score": ks.confidence_score,
            "area": subject.area,
            "subject_name": subject.nome,
            "topic_name": topic.nome,
        }
        for ks, subject, topic in states
    ]


def _find_question_in_bank(
    user_id: int,
    subject_id: int,
    topic_id: Optional[int],
    difficulty: float,
    used_question_ids: set[int],
) -> Optional[Question]:
    """
    Busca questão válida no banco de dados.
    
    Prioriza:
    1. Questão do tópico com dificuldade próxima
    2. Questão da matéria com dificuldade próxima
    3. Qualquer questão com dificuldade próxima
    """
    # Faixa de dificuldade aceitável (±1.0)
    min_diff = max(1, int(difficulty) - 1)
    max_diff = min(5, int(difficulty) + 1)

    # Buscar por tópico específico
    if topic_id:
        question = (
            Question.query.filter(
                Question.user_id == user_id,
                Question.topic_id == topic_id,
                Question.dificuldade.between(min_diff, max_diff),
                ~Question.id.in_(used_question_ids) if used_question_ids else True,
            )
            .order_by(db.func.abs(Question.dificuldade - difficulty))
            .first()
        )
        if question:
            return question

    # Buscar por matéria
    question = (
        Question.query.filter(
            Question.user_id == user_id,
            Question.subject_id == subject_id,
            Question.dificuldade.between(min_diff, max_diff),
            ~Question.id.in_(used_question_ids) if used_question_ids else True,
        )
        .order_by(db.func.abs(Question.dificuldade - difficulty))
        .first()
    )
    if question:
        return question

    # Buscar qualquer questão disponível
    question = (
        Question.query.filter(
            Question.user_id == user_id,
            Question.dificuldade.between(min_diff, max_diff),
            ~Question.id.in_(used_question_ids) if used_question_ids else True,
        )
        .order_by(db.func.abs(Question.dificuldade - difficulty))
        .first()
    )
    return question


def start_assessment(
    user_id: int,
    target_questions: int = 10,
    subject_id: Optional[int] = None,
) -> Assessment:
    """
    Inicia uma nova avaliação adaptativa.
    
    Args:
        user_id: ID do usuário.
        target_questions: Número de questões desejado (5-30).
        subject_id: Matéria específica (opcional).
        
    Returns:
        Assessment criado e salvo no banco.
        
    Raises:
        ValueError: Se parâmetros são inválidos.
    """
    # Validar parâmetros
    target_questions = max(5, min(30, target_questions))

    # Verificar se háKnowledgeStates suficientes
    knowledge_states = _get_knowledge_states_as_dicts(user_id)
    if not knowledge_states:
        raise ValueError(
            "Nenhum tópico com dados de conhecimento encontrado. "
            "Responda algumas questões primeiro."
        )

    # Calcular difficulty inicial baseada no mastery médio
    avg_mastery = sum(ks["mastery_score"] for ks in knowledge_states) / len(knowledge_states)
    initial_difficulty = get_initial_difficulty(avg_mastery)

    # Criar Assessment
    assessment = Assessment(
        user_id=user_id,
        target_questions=target_questions,
        subject_id=subject_id,
        status="active",
        current_difficulty=initial_difficulty,
    )
    db.session.add(assessment)
    db.session.commit()

    logger.info(
        "Avaliação #%d iniciada: user=%d, target=%d, difficulty=%.1f",
        assessment.id, user_id, target_questions, initial_difficulty,
    )

    return assessment


def get_next_question(assessment_id: int, user_id: int) -> dict:
    """
    Busca a próxima questão para a avaliação.
    
    Fluxo:
    1. Verificar se avaliação está ativa
    2. Decision Engine decide assunto + dificuldade
    3. Buscar questão no banco (ou gerar via IA)
    4. Criar AssessmentQuestion
    5. Retornar questão para o aluno
    
    Args:
        assessment_id: ID da avaliação.
        user_id: ID do usuário (anti-IDOR).
        
    Returns:
        Dict com questão, assessment_question_id, decision.
        
    Raises:
        ValueError: Se avaliação não existe, não está ativa, ou completa.
    """
    # Buscar assessment (com filtro por user_id para anti-IDOR)
    assessment = Assessment.query.filter_by(
        id=assessment_id, user_id=user_id
    ).first()
    if assessment is None:
        raise ValueError("Avaliação não encontrada")
    if not assessment.is_active:
        raise ValueError("Avaliação não está ativa")
    if is_assessment_complete(
        AssessmentState(
            questions_answered=assessment.current_question_number,
            correct_count=assessment.correct_count,
            wrong_count=assessment.wrong_count,
            current_difficulty=assessment.current_difficulty,
        ),
        assessment.target_questions,
    ):
        raise ValueError("Avaliação já está completa")

    # Buscar KnowledgeStates
    knowledge_states = _get_knowledge_states_as_dicts(user_id)
    if not knowledge_states:
        raise ValueError("Nenhum tópico com dados encontrado")

    # Montar estado atual
    state = _build_state_from_assessment(assessment)

    # Decision Engine decide
    decision = decide_next_question(state, knowledge_states)
    if decision is None:
        raise ValueError("Nenhum tópico disponível para avaliação")

    # Ajustar dificuldade sequencial
    recent_diffs = _get_recent_difficulties(assessment.id)
    adjusted_difficulty = check_difficulty_sequence(
        decision.difficulty, recent_diffs
    )

    # Buscar questão no banco
    used_ids = _get_used_question_ids(assessment.id)
    question = _find_question_in_bank(
        user_id=user_id,
        subject_id=decision.subject_id,
        topic_id=decision.topic_id,
        difficulty=adjusted_difficulty,
        used_question_ids=used_ids,
    )

    # Criar AssessmentQuestion
    aq = AssessmentQuestion(
        assessment_id=assessment.id,
        user_id=user_id,
        order=assessment.current_question_number + 1,
        target_difficulty=adjusted_difficulty,
        subject_id=decision.subject_id,
        topic_id=decision.topic_id,
        decision_reason=decision.reason,
    )

    if question:
        aq.question_id = question.id
    else:
        # Sem questão no banco: marcar para geração via IA
        aq.generated_question_data = json.dumps({
            "area": decision.area,
            "subject_name": decision.subject_name,
            "topic_name": decision.topic_name,
            "difficulty": adjusted_difficulty,
        })

    db.session.add(aq)
    db.session.commit()

    logger.info(
        "Questão %d/%d para avaliação #%d: topic=%s, diff=%.1f",
        aq.order, assessment.target_questions, assessment.id,
        decision.topic_name, adjusted_difficulty,
    )

    # Montar resposta
    result = {
        "assessment_question_id": aq.id,
        "order": aq.order,
        "target_difficulty": adjusted_difficulty,
        "subject_name": decision.subject_name,
        "topic_name": decision.topic_name,
        "reason": decision.reason,
        "needs_ai_generation": question is None,
    }

    if question:
        result["question"] = {
            "id": question.id,
            "enunciado": question.enunciado,
            "alternativa_a": question.alternativa_a,
            "alternativa_b": question.alternativa_b,
            "alternativa_c": question.alternativa_c,
            "alternativa_d": question.alternativa_d,
            "alternativa_e": question.alternativa_e,
            "dificuldade": question.dificuldade,
        }
    else:
        # Dados para geração via IA
        result["generation_params"] = {
            "area": decision.area,
            "materia": decision.subject_name,
            "assunto": decision.topic_name,
            "dificuldade": int(round(adjusted_difficulty)),
        }

    return result


def submit_answer(
    assessment_id: int,
    assessment_question_id: int,
    user_id: int,
    resposta: str,
    tempo_segundos: Optional[int] = None,
) -> dict:
    """
    Registra a resposta do aluno e prepara a próxima questão.
    
    Fluxo:
    1. Validar assessment e questão
    2. Verificar correção (banco ou IA)
    3. Atualizar AssessmentQuestion
    4. Atualizar Assessment (contadores, difficulty)
    5. Atualizar KnowledgeState
    6. Retornar resultado parcial + próxima questão (se houver)
    
    Args:
        assessment_id: ID da avaliação.
        assessment_question_id: ID da questão da avaliação.
        user_id: ID do usuário.
        resposta: Resposta do aluno (A-E).
        tempo_segundos: Tempo de resposta em segundos.
        
    Returns:
        Dict com resultado parcial e próxima questão (se disponível).
    """
    # Validar assessment
    assessment = Assessment.query.filter_by(
        id=assessment_id, user_id=user_id
    ).first()
    if assessment is None:
        raise ValueError("Avaliação não encontrada")
    if not assessment.is_active:
        raise ValueError("Avaliação não está ativa")

    # Validar questão
    aq = AssessmentQuestion.query.filter_by(
        id=assessment_question_id,
        assessment_id=assessment_id,
        user_id=user_id,
    ).first()
    if aq is None:
        raise ValueError("Questão da avaliação não encontrada")
    if aq.resposta is not None:
        raise ValueError("Questão já foi respondida")

    # Verificar correção
    correta = _check_answer(aq, resposta.upper())

    # Atualizar AssessmentQuestion
    aq.resposta = resposta.upper()
    aq.correta = correta
    aq.tempo_segundos = tempo_segundos
    aq.answered_at = datetime.now(timezone.utc)

    # Atualizar Assessment
    assessment.current_question_number += 1
    if correta:
        assessment.correct_count += 1
    else:
        assessment.wrong_count += 1
    if tempo_segundos:
        assessment.total_time_seconds += tempo_segundos

    # Atualizar difficulty
    state = _build_state_from_assessment(assessment)
    assessment.current_difficulty = state.current_difficulty

    # Verificar se completa
    if is_assessment_complete(state, assessment.target_questions):
        assessment.status = "completed"
        assessment.completed_at = datetime.now(timezone.utc)

    # Atualizar KnowledgeState do tópico (antes do commit principal)
    ks_updated = False
    if aq.topic_id and aq.question_id:
        from app.models import QuestionAttempt
        attempt = QuestionAttempt(
            user_id=user_id,
            question_id=aq.question_id,
            resposta=resposta.upper(),
            correta=correta,
            tempo_segundos=tempo_segundos,
        )
        db.session.add(attempt)
        ks_updated = True

    db.session.commit()

    if ks_updated:
        update_knowledge_state(user_id, aq.topic_id)

    # Montar resultado
    result = {
        "assessment_question_id": aq.id,
        "order": aq.order,
        "resposta": resposta.upper(),
        "correta": correta,
        "tempo_segundos": tempo_segundos,
        "assessment_progress": {
            "current": assessment.current_question_number,
            "target": assessment.target_questions,
            "correct_count": assessment.correct_count,
            "wrong_count": assessment.wrong_count,
            "accuracy": assessment.accuracy,
            "current_difficulty": assessment.current_difficulty,
        },
        "is_complete": assessment.status == "completed",
    }

    # Se não completa, incluir próxima questão
    if assessment.status == "active":
        try:
            next_q = get_next_question(assessment.id, user_id)
            result["next_question"] = next_q
        except ValueError:
            # Sem próxima questão disponível
            assessment.status = "completed"
            assessment.completed_at = datetime.now(timezone.utc)
            db.session.commit()
            result["is_complete"] = True

    return result


def complete_assessment(assessment_id: int, user_id: int) -> dict:
    """
    Finaliza uma avaliação e gera o resultado completo.
    
    Args:
        assessment_id: ID da avaliação.
        user_id: ID do usuário.
        
    Returns:
        Dict com resultado completo da avaliação.
    """
    assessment = Assessment.query.filter_by(
        id=assessment_id, user_id=user_id
    ).first()
    if assessment is None:
        raise ValueError("Avaliação não encontrada")

    # Marcar como completa se ainda estiver ativa
    if assessment.is_active:
        assessment.status = "completed"
        assessment.completed_at = datetime.now(timezone.utc)
        db.session.commit()

    # Buscar todas as questões da avaliação
    questions = AssessmentQuestion.query.filter_by(
        assessment_id=assessment_id
    ).order_by(AssessmentQuestion.order).all()

    # Calcular métricas
    difficulties = [aq.target_difficulty for aq in questions]
    correctness = [aq.correta for aq in questions if aq.correta is not None]

    result_metrics = build_assessment_result(
        correct_count=assessment.correct_count,
        wrong_count=assessment.wrong_count,
        total_time_seconds=assessment.total_time_seconds,
        question_difficulties=difficulties,
        question_correctness=correctness,
    )

    # Desempenho por tópico
    topic_stats = {}
    for aq in questions:
        if aq.topic_id and aq.correta is not None:
            if aq.topic_id not in topic_stats:
                topic_stats[aq.topic_id] = {"total": 0, "correct": 0, "topic_name": ""}
            topic_stats[aq.topic_id]["total"] += 1
            if aq.correta:
                topic_stats[aq.topic_id]["correct"] += 1

            # Buscar nome do tópico
            topic = db.session.get(Topic, aq.topic_id)
            if topic:
                topic_stats[aq.topic_id]["topic_name"] = topic.nome

    topic_performance = {}
    for tid, data in topic_stats.items():
        acc = (data["correct"] / data["total"] * 100) if data["total"] > 0 else 0.0
        topic_performance[tid] = {
            "topic_name": data["topic_name"],
            "total": data["total"],
            "correct": data["correct"],
            "accuracy": round(acc, 2),
        }

    # Desempenho por matéria
    subject_stats = {}
    for aq in questions:
        if aq.subject_id and aq.correta is not None:
            if aq.subject_id not in subject_stats:
                subject_stats[aq.subject_id] = {"total": 0, "correct": 0, "subject_name": ""}
            subject_stats[aq.subject_id]["total"] += 1
            if aq.correta:
                subject_stats[aq.subject_id]["correct"] += 1

            subject = db.session.get(Subject, aq.subject_id)
            if subject:
                subject_stats[aq.subject_id]["subject_name"] = subject.nome

    subject_performance = {}
    for sid, data in subject_stats.items():
        acc = (data["correct"] / data["total"] * 100) if data["total"] > 0 else 0.0
        subject_performance[sid] = {
            "subject_name": data["subject_name"],
            "total": data["total"],
            "correct": data["correct"],
            "accuracy": round(acc, 2),
        }

    return {
        "assessment_id": assessment.id,
        "status": assessment.status,
        "started_at": assessment.started_at.isoformat() if assessment.started_at else None,
        "completed_at": assessment.completed_at.isoformat() if assessment.completed_at else None,
        **result_metrics,
        "topic_performance": topic_performance,
        "subject_performance": subject_performance,
    }


def get_assessment_status(assessment_id: int, user_id: int) -> dict:
    """Retorna o status atual de uma avaliação."""
    assessment = Assessment.query.filter_by(
        id=assessment_id, user_id=user_id
    ).first()
    if assessment is None:
        raise ValueError("Avaliação não encontrada")

    return assessment.to_dict()


def list_user_assessments(
    user_id: int,
    status: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Lista avaliações do usuário."""
    query = Assessment.query.filter_by(user_id=user_id)
    if status:
        query = query.filter_by(status=status)
    assessments = query.order_by(Assessment.created_at.desc()).limit(limit).all()
    return [a.to_dict() for a in assessments]


# =============================================================================
# FUNÇÕES AUXILIARES PRIVADAS
# =============================================================================

def _build_state_from_assessment(assessment: Assessment) -> AssessmentState:
    """Constrói AssessmentState a partir do Assessment no banco."""
    # Buscar resultados das questões já respondidas
    answered = (
        AssessmentQuestion.query.filter_by(assessment_id=assessment.id)
        .filter(AssessmentQuestion.resposta.isnot(None))
        .order_by(AssessmentQuestion.order)
        .all()
    )

    recent_results = [aq.correta for aq in answered if aq.correta is not None]
    used_ids = {aq.question_id for aq in answered if aq.question_id}
    used_topics = [aq.topic_id for aq in answered if aq.topic_id]

    return AssessmentState(
        questions_answered=assessment.current_question_number,
        correct_count=assessment.correct_count,
        wrong_count=assessment.wrong_count,
        current_difficulty=assessment.current_difficulty,
        recent_results=recent_results,
        used_question_ids=used_ids,
        used_topic_ids=used_topics,
        subject_id=assessment.subject_id,
    )


def _get_used_question_ids(assessment_id: int) -> set[int]:
    """Retorna IDs das questões já usadas na avaliação."""
    result = (
        db.session.query(AssessmentQuestion.question_id)
        .filter(
            AssessmentQuestion.assessment_id == assessment_id,
            AssessmentQuestion.question_id.isnot(None),
        )
        .all()
    )
    return {row[0] for row in result if row[0] is not None}


def _get_recent_difficulties(assessment_id: int) -> list[float]:
    """Retorna as últimas 5 dificuldades usadas na avaliação."""
    result = (
        db.session.query(AssessmentQuestion.target_difficulty)
        .filter(AssessmentQuestion.assessment_id == assessment_id)
        .order_by(AssessmentQuestion.order.desc())
        .limit(5)
        .all()
    )
    return [row[0] for row in result]


def _check_answer(aq: AssessmentQuestion, resposta: str) -> bool:
    """
    Verifica se a resposta está correta.
    
    Se a questão veio do banco, compara com resposta_correta.
    Se foi gerada por IA, a validação é feita no backend.
    """
    if aq.question_id:
        question = db.session.get(Question, aq.question_id)
        if question:
            return resposta.upper() == question.resposta_correta.upper()

    # Questão gerada por IA: não deveria chegar aqui sem resposta no banco
    # Mas por segurança, registrar como não verificada
    logger.warning(
        "Questão %d sem resposta_correta no banco. "
        "Verificação pendente de validação IA.",
        aq.id,
    )
    return False
