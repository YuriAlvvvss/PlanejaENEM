"""
Authorization helpers for PlanejaENEM.

Provides centralized queries that always scope by user_id,
preventing IDOR vulnerabilities across all routes.
"""

from flask import abort
from flask_login import current_user

from app.extensions import db
from app.models import StudyPlan, StudySession, Subject, Task


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
