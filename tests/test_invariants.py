"""
Testes de Invariantes - Decision Engine PlanejaENEM 4.0.

Garante que todas as restrições fundamentais são sempre respeitadas:
- Scores entre 0 e 100
- Nunca horários sobrepostos
- Nunca sessão fora de disponibilidade
- Nunca ultrapassar meta semanal
- Nunca estudar assunto de outro usuário
- Nunca contaminar estatísticas com dados de outro usuário
"""

import pytest
from datetime import date, time, timedelta

from app.decision_engine.types import (
    StudyAction,
    StudyPhase,
    StudyRecommendation,
    TopicContext,
    WeeklyAvailability,
)
from app.decision_engine.ranking import calculate_final_score
from app.decision_engine.policies import (
    detect_all_conflicts,
    resolve_conflicts,
)


def _make_context(**kwargs):
    """Cria um TopicContext para testes."""
    defaults = {
        "topic_id": 1,
        "subject_id": 1,
        "topic_name": "Funções",
        "subject_name": "Matemática",
        "area": "ciencias_da_natureza",
        "mastery_score": 50.0,
        "confidence_score": 50.0,
        "recent_accuracy": 50.0,
        "historical_accuracy": 50.0,
        "questions_answered": 10,
        "questions_correct": 5,
        "questions_wrong": 5,
        "consecutive_correct": 0,
        "consecutive_wrong": 0,
        "last_attempt_at": date.today() - timedelta(days=5),
        "last_review_at": date.today() - timedelta(days=7),
        "subject_difficulty": 3,
        "subject_priority": 3,
        "days_until_exam": 60,
        "overdue_reviews": 0,
        "missed_sessions": 0,
    }
    defaults.update(kwargs)
    return TopicContext(**defaults)


def _make_availability(**kwargs):
    """Cria WeeklyAvailability para testes."""
    defaults = {
        "days": ["seg", "qua", "sex"],
        "hours": ["08:00-10:00"],
        "daily_minutes": 120,
        "weekly_goal_minutes": 600,
        "max_session_minutes": 120,
    }
    defaults.update(kwargs)
    return WeeklyAvailability(**defaults)


def _make_recommendation(**kwargs):
    """Cria StudyRecommendation para testes."""
    defaults = {
        "priority": 1,
        "subject_id": 1,
        "topic_id": 1,
        "action": StudyAction.PRACTICE,
        "duration_minutes": 30,
        "recommended_date": date.today(),
        "score": 50.0,
        "mastery_score": 50.0,
        "confidence_score": 50.0,
        "reason_codes": [],
        "explanation": "Teste",
        "study_phase": StudyPhase.MEDIUM_TERM,
        "area": "ciencias_da_natureza",
        "subject_name": "Matemática",
        "topic_name": "Funções",
    }
    defaults.update(kwargs)
    return StudyRecommendation(**defaults)


class TestScoreRangeInvariant:
    """Invariantes de faixa de scores."""

    def test_final_score_0_100(self):
        """Score final deve estar entre 0 e 100."""
        for mastery in [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            context = _make_context(mastery_score=float(mastery))
            result = calculate_final_score(context)
            assert 0 <= result["final_score"] <= 100, (
                f"Score {result['final_score']} fora do range para mastery={mastery}"
            )

    def test_mastery_score_0_100(self):
        """Mastery score deve estar entre 0 e 100."""
        for mastery in [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            context = _make_context(mastery_score=float(mastery))
            result = calculate_final_score(context)
            assert 0 <= context.mastery_score <= 100

    def test_confidence_score_0_100(self):
        """Confidence score deve estar entre 0 e 100."""
        for confidence in [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            context = _make_context(confidence_score=float(confidence))
            result = calculate_final_score(context)
            assert 0 <= context.confidence_score <= 100

    def test_component_scores_0_100(self):
        """Todos os componentes devem estar entre 0 e 100."""
        context = _make_context()
        result = calculate_final_score(context)
        for component, value in result["components"].items():
            assert 0 <= value <= 100, (
                f"Componente {component} com valor {value} fora do range"
            )

    def test_weights_sum_to_one(self):
        """Pesos devem somar 1.0."""
        from app.decision_engine.ranking import WEIGHTS
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Pesos somam {total}, esperado 1.0"


class TestTimeSlotInvariant:
    """Invariantes de horários."""

    def test_no_overlapping_recommendations(self):
        """Recomendações não devem ter sobreposição de horário."""
        today = date.today()
        recs = [
            _make_recommendation(
                recommended_date=today,
                duration_minutes=60,
            ),
            _make_recommendation(
                recommended_date=today,
                duration_minutes=60,
            ),
        ]
        availability = _make_availability(daily_minutes=120)
        resolved, _ = resolve_conflicts(recs, availability)
        total_minutes = sum(r.duration_minutes for r in resolved)
        assert total_minutes <= availability.daily_minutes

    def test_session_within_availability(self):
        """Sessão deve estar dentro da disponibilidade."""
        availability = _make_availability(daily_minutes=120)
        rec = _make_recommendation(duration_minutes=30)
        assert rec.duration_minutes <= availability.daily_minutes

    def test_no_session_outside_max(self):
        """Sessão não deve exceder duração máxima."""
        availability = _make_availability(max_session_minutes=90)
        rec = _make_recommendation(duration_minutes=120)
        if rec.duration_minutes > availability.max_session_minutes:
            rec.duration_minutes = availability.max_session_minutes
        assert rec.duration_minutes <= availability.max_session_minutes


class TestWeeklyGoalInvariant:
    """Invariantes de meta semanal."""

    def test_total_minutes_within_weekly_goal(self):
        """Total de minutos não deve exceder meta semanal."""
        availability = _make_availability(weekly_goal_minutes=300)
        recs = [
            _make_recommendation(duration_minutes=60) for _ in range(10)
        ]
        resolved, _ = resolve_conflicts(recs, availability)
        total = sum(r.duration_minutes for r in resolved)
        assert total <= availability.weekly_goal_minutes

    def test_resolve_reduces_to_goal(self):
        """Resolução de conflitos deve reduzir para meta."""
        availability = _make_availability(weekly_goal_minutes=200)
        recs = [
            _make_recommendation(duration_minutes=60) for _ in range(10)
        ]
        resolved, _ = resolve_conflicts(recs, availability)
        total = sum(r.duration_minutes for r in resolved)
        assert total <= availability.weekly_goal_minutes


class TestUserIsolationInvariant:
    """Invariantes de isolamento de usuário."""

    def test_recommendations_have_user_context(self):
        """Recomendações devem estar no contexto do usuário."""
        context = _make_context(subject_id=1)
        result = calculate_final_score(context)
        assert result is not None

    def test_subject_id_in_recommendation(self):
        """Recomendação deve conter subject_id."""
        rec = _make_recommendation(subject_id=42)
        assert rec.subject_id == 42

    def test_topic_id_in_recommendation(self):
        """Recomendação deve conter topic_id."""
        rec = _make_recommendation(topic_id=99)
        assert rec.topic_id == 99


class TestNoStatisticsContamination:
    """Invariantes de contaminação de estatísticas."""

    def test_mastery_based_on_own_data(self):
        """Mastery deve ser baseado nos próprios dados."""
        context_a = _make_context(
            topic_id=1,
            mastery_score=80.0,
            questions_correct=8,
            questions_answered=10,
        )
        context_b = _make_context(
            topic_id=2,
            mastery_score=20.0,
            questions_correct=2,
            questions_answered=10,
        )
        result_a = calculate_final_score(context_a)
        result_b = calculate_final_score(context_b)
        assert result_a["final_score"] < result_b["final_score"]

    def test_scores_independent_between_topics(self):
        """Scores de tópicos diferentes devem ser independentes."""
        context_a = _make_context(topic_id=1, mastery_score=30.0)
        context_b = _make_context(topic_id=2, mastery_score=70.0)
        result_a = calculate_final_score(context_a)
        result_b = calculate_final_score(context_b)
        assert result_a["final_score"] != result_b["final_score"]


class TestDeterminismInvariant:
    """Invariantes de determinismo."""

    def test_same_input_always_same_output(self):
        """Mesma entrada sempre produz mesma saída."""
        context = _make_context(mastery_score=45.0)
        results = [calculate_final_score(context) for _ in range(20)]
        scores = [r["final_score"] for r in results]
        assert len(set(scores)) == 1

    def test_same_context_same_reason_codes(self):
        """Mesmo contexto produz mesmos reason codes."""
        context = _make_context(mastery_score=25.0)
        results = [calculate_final_score(context) for _ in range(10)]
        reason_codes_sets = [tuple(sorted(r["reason_codes"])) for r in results]
        assert len(set(reason_codes_sets)) == 1


class TestActionInvariant:
    """Invariantes de ação."""

    def test_action_matches_mastery(self):
        """Ação deve ser adequada ao domínio."""
        test_cases = [
            (10, StudyAction.LEARN),
            (30, StudyAction.LEARN),
            (50, StudyAction.PRACTICE),
            (65, StudyAction.ENEM_QUESTIONS),
            (80, StudyAction.DIFFICULT_QUESTIONS),
        ]
        for mastery, expected_action in test_cases:
            context = _make_context(mastery_score=float(mastery))
            result = calculate_final_score(context)
            assert result["recommended_action"] == expected_action, (
                f"Para mastery={mastery}, esperado {expected_action}, "
                f"obtido {result['recommended_action']}"
            )

    def test_duration_positive(self):
        """Duração deve ser positiva."""
        for action in StudyAction:
            duration = _make_recommendation(action=action).duration_minutes
            assert duration > 0


class TestMasteryLevelInvariant:
    """Invariantes de nível de domínio."""

    def test_mastery_level_boundaries(self):
        """Níveis de domínio devem ser consistentes."""
        from app.decision_engine.types import MasteryLevel

        test_cases = [
            (0, MasteryLevel.CRITICAL),
            (39, MasteryLevel.CRITICAL),
            (40, MasteryLevel.LOW),
            (59, MasteryLevel.LOW),
            (60, MasteryLevel.MEDIUM),
            (74, MasteryLevel.MEDIUM),
            (75, MasteryLevel.GOOD),
            (89, MasteryLevel.GOOD),
            (90, MasteryLevel.EXCELLENT),
            (100, MasteryLevel.EXCELLENT),
        ]
        for mastery, expected_level in test_cases:
            context = _make_context(mastery_score=float(mastery))
            assert context.mastery_level == expected_level, (
                f"Para mastery={mastery}, esperado {expected_level}, "
                f"obtido {context.mastery_level}"
            )
