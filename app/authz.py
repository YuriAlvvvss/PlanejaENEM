"""
Authorization helpers for PlanejaENEM.

Provides centralized queries that always scope by user_id,
preventing IDOR vulnerabilities across all routes.
"""

from flask import abort
from flask_login import current_user

from app.extensions import db
from app.models import StudyPlan, StudySession, Subject, Task, Topic, Question, QuestionAttempt
from app.assessment.models import Assessment, AssessmentQuestion


def get_user_subject(subject_id, user_id=None):
    uid = user_id or current_user.id
    subject = Subject.query.filter_by(id=subject_id, user_id=uid).first()
    if subject is None:
        abort(404)
    return subject


def get_user_task(task_id, user_id=None):
    uid = user_id or current_user.id
    task = Task.query.filter_by(id=task_id, user_id=uid).first()
    if task is None:
        abort(404)
    return task


def get_user_session(session_id, user_id=None):
    uid = user_id or current_user.id
    session = StudySession.query.filter_by(id=session_id, user_id=uid).first()
    if session is None:
        abort(404)
    return session


def get_user_plan(plan_id, user_id=None):
    uid = user_id or current_user.id
    plan = StudyPlan.query.filter_by(id=plan_id, user_id=uid).first()
    if plan is None:
        abort(404)
    return plan


def user_owns_subject(subject_id, user_id=None):
    uid = user_id or current_user.id
    return Subject.query.filter_by(id=subject_id, user_id=uid).first() is not None


def user_owns_task(task_id, user_id=None):
    uid = user_id or current_user.id
    return Task.query.filter_by(id=task_id, user_id=uid).first() is not None


def user_owns_session(session_id, user_id=None):
    uid = user_id or current_user.id
    return StudySession.query.filter_by(id=session_id, user_id=uid).first() is not None


def get_user_topic(topic_id, user_id=None):
    uid = user_id or current_user.id
    topic = Topic.query.filter_by(id=topic_id, user_id=uid).first()
    if topic is None:
        abort(404)
    return topic


def get_user_question(question_id, user_id=None):
    uid = user_id or current_user.id
    question = Question.query.filter_by(id=question_id, user_id=uid).first()
    if question is None:
        abort(404)
    return question


def get_user_attempt(attempt_id, user_id=None):
    uid = user_id or current_user.id
    attempt = QuestionAttempt.query.filter_by(id=attempt_id, user_id=uid).first()
    if attempt is None:
        abort(404)
    return attempt


def user_owns_topic(topic_id, user_id=None):
    uid = user_id or current_user.id
    return Topic.query.filter_by(id=topic_id, user_id=uid).first() is not None


def user_owns_question(question_id, user_id=None):
    uid = user_id or current_user.id
    return Question.query.filter_by(id=question_id, user_id=uid).first() is not None


def get_user_assessment(assessment_id, user_id=None):
    uid = user_id or current_user.id
    assessment = Assessment.query.filter_by(id=assessment_id, user_id=uid).first()
    if assessment is None:
        abort(404)
    return assessment


def get_user_assessment_question(assessment_question_id, user_id=None):
    uid = user_id or current_user.id
    aq = AssessmentQuestion.query.filter_by(
        id=assessment_question_id, user_id=uid
    ).first()
    if aq is None:
        abort(404)
    return aq


def user_owns_assessment(assessment_id, user_id=None):
    uid = user_id or current_user.id
    return Assessment.query.filter_by(id=assessment_id, user_id=uid).first() is not None
