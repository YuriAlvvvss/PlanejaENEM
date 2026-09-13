"""
Services for the questions module.

Handles question CRUD business logic and attempt recording.
"""

from typing import Optional

from app.extensions import db
from app.models import Question, QuestionAttempt, Topic, Subject


def get_user_topics(user_id: int, subject_id: Optional[int] = None):
    query = Topic.query.filter_by(user_id=user_id)
    if subject_id is not None:
        query = query.filter_by(subject_id=subject_id)
    return query.order_by(Topic.nome).all()


def _escape_like(value: str) -> str:
    """Escapa caracteres especiais para uso seguro em LIKE/ilike."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_user_questions(
    user_id: int,
    subject_id: Optional[int] = None,
    topic_id: Optional[int] = None,
    dificuldade: Optional[int] = None,
    search: Optional[str] = None,
):
    """Lista questões do usuário com filtros opcionais (contrato preservado: retorna lista).

    Filtros inválidos são ignorados (nunca levantam 500):
    - dificuldade fora de 1-5 é ignorada
    - search vazio é ignorado
    """
    query = Question.query.filter_by(user_id=user_id)
    if subject_id is not None:
        query = query.filter_by(subject_id=subject_id)
    if topic_id is not None:
        query = query.filter_by(topic_id=topic_id)
    if dificuldade is not None:
        try:
            dificuldade_int = int(dificuldade)
        except (TypeError, ValueError):
            dificuldade_int = None
        if dificuldade_int is not None and 1 <= dificuldade_int <= 5:
            query = query.filter_by(dificuldade=dificuldade_int)
    if search:
        cleaned = search.strip()
        if cleaned:
            like = f"%{_escape_like(cleaned)}%"
            query = query.filter(Question.enunciado.ilike(like, escape="\\"))
    return query.order_by(Question.created_at.desc()).all()


def create_topic(nome: str, subject_id: int, user_id: int, commit: bool = True) -> Topic:
    subject = Subject.query.filter_by(id=subject_id, user_id=user_id).first()
    if subject is None:
        raise ValueError("Matéria não encontrada para este usuário.")
    topic = Topic(nome=nome, subject_id=subject_id, user_id=user_id)
    db.session.add(topic)
    if commit:
        db.session.commit()
    return topic


def create_question(
    enunciado: str,
    alternativa_a: str,
    alternativa_b: str,
    alternativa_c: str,
    alternativa_d: str,
    alternativa_e: str,
    resposta_correta: str,
    subject_id: int,
    user_id: int,
    topic_id: Optional[int] = None,
    dificuldade: int = 3,
    ano: Optional[int] = None,
    fonte: Optional[str] = None,
    commit: bool = True,
) -> Question:
    subject = Subject.query.filter_by(id=subject_id, user_id=user_id).first()
    if subject is None:
        raise ValueError("Matéria não encontrada para este usuário.")
    if topic_id is not None:
        topic = Topic.query.filter_by(
            id=topic_id,
            subject_id=subject_id,
            user_id=user_id,
        ).first()
        if topic is None:
            raise ValueError("Assunto não encontrado para esta matéria.")
    question = Question(
        enunciado=enunciado,
        alternativa_a=alternativa_a,
        alternativa_b=alternativa_b,
        alternativa_c=alternativa_c,
        alternativa_d=alternativa_d,
        alternativa_e=alternativa_e,
        resposta_correta=resposta_correta,
        subject_id=subject_id,
        topic_id=topic_id,
        user_id=user_id,
        dificuldade=dificuldade,
        ano=ano,
        fonte=fonte,
    )
    db.session.add(question)
    if commit:
        db.session.commit()
    return question


def record_attempt(
    user_id: int,
    question_id: int,
    resposta: str,
    tempo_segundos: Optional[int] = None,
    commit: bool = True,
) -> QuestionAttempt:
    question = Question.query.filter_by(id=question_id, user_id=user_id).first()
    if question is None:
        raise ValueError("Questão não encontrada.")

    existing_attempt = QuestionAttempt.query.filter_by(
        user_id=user_id, question_id=question_id
    ).first()
    if existing_attempt is not None:
        raise ValueError("Esta questão já foi respondida.")

    correta = resposta.upper() == question.resposta_correta.upper()

    attempt = QuestionAttempt(
        user_id=user_id,
        question_id=question_id,
        resposta=resposta.upper(),
        correta=correta,
        tempo_segundos=tempo_segundos,
    )
    db.session.add(attempt)
    if commit:
        db.session.commit()
    return attempt


def get_user_attempt_count(user_id: int, question_id: int) -> int:
    return QuestionAttempt.query.filter_by(user_id=user_id, question_id=question_id).count()


def get_user_attempt(user_id: int, question_id: int) -> Optional[QuestionAttempt]:
    return QuestionAttempt.query.filter_by(
        user_id=user_id, question_id=question_id
    ).first()


def get_attempts_map(user_id: int, question_ids: list) -> dict:
    """Mapa question_id -> attempt do usuário em 1 query (evita N+1 na lista)."""
    if not question_ids:
        return {}
    attempts = QuestionAttempt.query.filter_by(user_id=user_id).filter(
        QuestionAttempt.question_id.in_(question_ids)
    ).all()
    return {a.question_id: a for a in attempts}


def get_recent_attempts(user_id: int, limit: int = 10):
    return (
        QuestionAttempt.query.filter_by(user_id=user_id)
        .order_by(QuestionAttempt.attempted_at.desc())
        .limit(limit)
        .all()
    )
