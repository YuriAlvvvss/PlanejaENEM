"""
Rotas de avaliação adaptativa - PlanejaENEM 5.0.

Endpoints REST para o fluxo de avaliação adaptativa:
  POST /assessment/start       - Iniciar avaliação
  GET  /assessment/<id>/next   - Buscar próxima questão
  POST /assessment/<id>/answer - Registrar resposta
  POST /assessment/<id>/complete - Finalizar avaliação
  GET  /assessment/<id>/status - Status atual
  GET  /assessment/list        - Listar avaliações do usuário

Todos os endpoints exigem login.
IDs são validados contra o usuário logado (anti-IDOR).
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.extensions import limiter
from app.assessment.services import (
    complete_assessment,
    get_assessment_status,
    get_next_question,
    list_user_assessments,
    start_assessment,
    submit_answer,
)

assessment_routes = Blueprint(
    "assessment_routes", __name__
)


@assessment_routes.route("/start", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def api_start_assessment():
    """
    Inicia uma nova avaliação adaptativa.
    
    Body JSON:
        target_questions: int (5-30, default 10)
        subject_id: int (opcional, filtrar por matéria)
    """
    data = request.get_json(silent=True) or {}

    target_questions = data.get("target_questions", 10)
    subject_id = data.get("subject_id")

    try:
        assessment = start_assessment(
            user_id=current_user.id,
            target_questions=target_questions,
            subject_id=subject_id,
        )
        return jsonify({
            "success": True,
            "assessment": assessment.to_dict(),
        }), 201
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@assessment_routes.route("/<int:assessment_id>/next", methods=["GET"])
@login_required
@limiter.limit("30/minute")
def api_get_next_question(assessment_id: int):
    """Busca a próxima questão da avaliação."""
    try:
        result = get_next_question(
            assessment_id=assessment_id,
            user_id=current_user.id,
        )
        return jsonify({"success": True, **result}), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@assessment_routes.route("/<int:assessment_id>/answer", methods=["POST"])
@login_required
@limiter.limit("60/minute")
def api_submit_answer(assessment_id: int):
    """
    Registra a resposta de uma questão.
    
    Body JSON:
        assessment_question_id: int (obrigatório)
        resposta: str (A-E, obrigatório)
        tempo_segundos: int (opcional)
    """
    data = request.get_json(silent=True) or {}

    assessment_question_id = data.get("assessment_question_id")
    resposta = data.get("resposta")
    tempo_segundos = data.get("tempo_segundos")

    if not assessment_question_id or not resposta:
        return jsonify({
            "success": False,
            "error": "assessment_question_id e resposta são obrigatórios",
        }), 400

    try:
        result = submit_answer(
            assessment_id=assessment_id,
            assessment_question_id=assessment_question_id,
            user_id=current_user.id,
            resposta=resposta,
            tempo_segundos=tempo_segundos,
        )
        return jsonify({"success": True, **result}), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@assessment_routes.route("/<int:assessment_id>/complete", methods=["POST"])
@login_required
@limiter.limit("5/minute")
def api_complete_assessment(assessment_id: int):
    """Finaliza a avaliação e retorna o resultado completo."""
    try:
        result = complete_assessment(
            assessment_id=assessment_id,
            user_id=current_user.id,
        )
        return jsonify({"success": True, "result": result}), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@assessment_routes.route("/<int:assessment_id>/status", methods=["GET"])
@login_required
@limiter.limit("30/minute")
def api_get_status(assessment_id: int):
    """Retorna o status atual da avaliação."""
    try:
        result = get_assessment_status(
            assessment_id=assessment_id,
            user_id=current_user.id,
        )
        return jsonify({"success": True, "assessment": result}), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@assessment_routes.route("/list", methods=["GET"])
@login_required
@limiter.limit("20/minute")
def api_list_assessments():
    """
    Lista avaliações do usuário.
    
    Query params:
        status: str (active/completed/abandoned, opcional)
        limit: int (default 20)
    """
    status = request.args.get("status")
    limit = request.args.get("limit", 20, type=int)

    assessments = list_user_assessments(
        user_id=current_user.id,
        status=status,
        limit=limit,
    )
    return jsonify({"success": True, "assessments": assessments}), 200
