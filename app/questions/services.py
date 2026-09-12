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


def get_user_questions(user_id: int, subject_id: Optional[int] = None, topic_id: Optional[int] = None):
    query = Question.query.filter_by(user_id=user_id)
    if subject_id is not None:
        query = query.filter_by(subject_id=subject_id)
    if topic_id is not None:
        query = query.filter_by(topic_id=topic_id)
    return query.order_by(Question.created_at.desc()).all()


def create_topic(nome: str, subject_id: int, user_id: int) -> Topic:
    topic = Topic(nome=nome, subject_id=subject_id, user_id=user_id)
    db.session.add(topic)
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
) -> Question:
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
    db.session.commit()
    return question


def record_attempt(
    user_id: int,
    question_id: int,
    resposta: str,
    tempo_segundos: Optional[int] = None,
) -> QuestionAttempt:
    question = Question.query.filter_by(id=question_id, user_id=user_id).first()
    if question is None:
        raise ValueError("Questão não encontrada.")

    correta = resposta.upper() == question.resposta_correta.upper()

    attempt = QuestionAttempt(
        user_id=user_id,
        question_id=question_id,
        resposta=resposta.upper(),
        correta=correta,
        tempo_segundos=tempo_segundos,
    )
    db.session.add(attempt)
    db.session.commit()
    return attempt


def get_user_attempt_count(user_id: int, question_id: int) -> int:
    return QuestionAttempt.query.filter_by(user_id=user_id, question_id=question_id).count()


def get_recent_attempts(user_id: int, limit: int = 10):
    return (
        QuestionAttempt.query.filter_by(user_id=user_id)
        .order_by(QuestionAttempt.attempted_at.desc())
        .limit(limit)
        .all()
    )
