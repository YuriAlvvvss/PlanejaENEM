from flask import Blueprint

performance_bp = Blueprint("performance", __name__, url_prefix="/performance")

from app.performance import routes  # noqa: E402, F401
from app.performance.models import KnowledgeState  # noqa: E402, F401
