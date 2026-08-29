from flask import Blueprint

planner_bp = Blueprint("planner", __name__, url_prefix="/planner")

from app.planner import routes  # noqa: E402, F401
