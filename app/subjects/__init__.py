from flask import Blueprint

subjects_bp = Blueprint("subjects", __name__)

from app.subjects import routes  # noqa: E402, F401
