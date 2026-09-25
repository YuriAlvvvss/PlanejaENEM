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

from flask import jsonify, request, session
from flask_login import login_required, current_user

from app.assessment import assessment_bp
from app.extensions import limiter
from app.assessment.services import (
    complete_assessment,
    get_assessment_status,
    get_next_question,
    list_user_assessments,
    start_assessment,
    submit_answer,
)


@assessment_bp.route("/start", methods=["POST"])
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

    idempotency_key = request.headers.get("Idempotency-Key") or data.get("idempotency_key")
    if isinstance(idempotency_key, str):
        idempotency_key = idempotency_key.strip()[:64]
    else:
        idempotency_key = None
    if idempotency_key:
        seen = session.get("_assessment_idempotency", {})
        if idempotency_key in seen:
            from app.assessment.models import Assessment as AssessmentModel

            existing = AssessmentModel.query.filter_by(
                id=seen[idempotency_key], user_id=current_user.id
            ).first()
            if existing is not None:
                return jsonify({
                    "success": True,
                    "assessment": existing.to_dict(),
                    "deduplicated": True,
                }), 200

    try:
        assessment = start_assessment(
            user_id=current_user.id,
            target_questions=target_questions,
            subject_id=subject_id,
        )
        if idempotency_key:
            seen = session.get("_assessment_idempotency", {})
            seen[idempotency_key] = assessment.id
            session["_assessment_idempotency"] = dict(list(seen.items())[-20:])
        return jsonify({
            "success": True,
            "assessment": assessment.to_dict(),
        }), 201
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@assessment_bp.route("/<int:assessment_id>/next", methods=["GET"])
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


@assessment_bp.route("/<int:assessment_id>/answer", methods=["POST"])
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


@assessment_bp.route("/<int:assessment_id>/complete", methods=["POST"])
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


@assessment_bp.route("/<int:assessment_id>/status", methods=["GET"])
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


@assessment_bp.route("/list", methods=["GET"])
@login_required
@limiter.limit("20/minute")
def api_list_assessments():
    """
    Lista avaliações do usuário.
    
    Query params:
        status: str (active/completed/abandoned, opcional)
        limit: int (default 20)
    """
    status = (request.args.get("status") or "").strip().lower() or None
    if status is not None and status not in {"active", "completed", "abandoned"}:
        status = None
    try:
        limit = int(request.args.get("limit", 20))
    except (TypeError, ValueError):
        limit = 20
    limit = max(1, min(100, limit))

    assessments = list_user_assessments(
        user_id=current_user.id,
        status=status,
        limit=limit,
    )
    return jsonify({"success": True, "assessments": assessments}), 200
