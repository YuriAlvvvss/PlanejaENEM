"""
Módulo de avaliação adaptativa - PlanejaENEM 5.0.

Fornece avaliações adaptativas em que o sistema escolhe assunto e
dificuldade com base no desempenho atual do aluno.

Fluxo:
  KnowledgeState → Decision Engine → assunto + dificuldade
  → QuestionGenerator → AIClient → questão → aluno responde
  → backend registra → KnowledgeState atualiza → próxima questão

REGRA DE OURO: A IA generativa nunca é a fonte da verdade.
O backend controla resultado, acerto, dificuldade, mastery, confiança, tendência.
"""

from flask import Blueprint

assessment_bp = Blueprint("assessment", __name__, url_prefix="/assessment")

from app.assessment import routes  # noqa: E402, F401
