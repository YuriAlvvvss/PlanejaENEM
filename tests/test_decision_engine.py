"""
Testes Determinísticos - Decision Engine PlanejaENEM 4.0.

Testa 14 cenários específicos para garantir que o algoritmo
é determinístico e reproduzível.

Com os mesmos dados de entrada, o sistema deve produzir
a mesma recomendação.
"""

import pytest
from datetime import date, timedelta

from app.decision_engine.types import (
    MasteryLevel,
    ReasonCode,
    StudyAction,
    StudyPhase,
    TopicContext,
    WeeklyAvailability,
)
from app.decision_engine.ranking import (
    calculate_final_score,
    calculate_need_score,
    calculate_weakness_score,
    calculate_recency_score,
    calculate_exam_urgency_score,
    calculate_review_urgency_score,
    calculate_historical_importance_score,
    calculate_study_consistency_score,
    determine_reason_codes,
    determine_action,
    estimate_duration,
)
from app.decision_engine.explanations import (
    build_explanation,
    build_short_explanation,
    get_action_text,
    get_mastery_level_text,
)
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


class TestDeterministicRanking:
    """Testes de determinismo do ranking."""

    def test_same_input_same_output(self):
        """Mesmos dados devem produzir mesmo resultado."""
        context = _make_context()
        result1 = calculate_final_score(context)
        result2 = calculate_final_score(context)
        assert result1["final_score"] == result2["final_score"]
        assert result1["reason_codes"] == result2["reason_codes"]
        assert result1["recommended_action"] == result2["recommended_action"]

    def test_deterministic_across_calls(self):
        """Múltiplas chamadas devem produzir mesmo resultado."""
        context = _make_context(mastery_score=35.0)
        scores = [calculate_final_score(context)["final_score"] for _ in range(10)]
        assert len(set(scores)) == 1


class TestScenario1LowMastery:
    """Cenário 1: Domínio muito baixo."""

    def test_low_mastery(self):
        context = _make_context(
            mastery_score=20.0,
            confidence_score=30.0,
            questions_answered=5,
        )
        result = calculate_final_score(context)
        assert result["final_score"] > 50
        assert ReasonCode.LOW_MASTERY in result["reason_codes"]
        assert result["recommended_action"] == StudyAction.LEARN


class TestScenario2HighMastery:
    """Cenário 2: Domínio alto."""

    def test_high_mastery(self):
        context = _make_context(
            mastery_score=85.0,
            confidence_score=80.0,
            questions_answered=25,
        )
        result = calculate_final_score(context)
        assert result["final_score"] < 60
        assert result["recommended_action"] in [
            StudyAction.DIFFICULT_QUESTIONS,
            StudyAction.ENEM_QUESTIONS,
        ]


class TestScenario3RecentDrop:
    """Cenário 3: Queda recente."""

    def test_recent_drop(self):
        context = _make_context(
            mastery_score=60.0,
            recent_accuracy=35.0,
            historical_accuracy=70.0,
        )
        result = calculate_final_score(context)
        assert ReasonCode.PERFORMANCE_DECLINING in result["reason_codes"]
        assert ReasonCode.RECENT_POOR_PERFORMANCE in result["reason_codes"]


class TestScenario4OverdueReview:
    """Cenário 4: Revisão atrasada."""

    def test_overdue_review(self):
        context = _make_context(
            mastery_score=65.0,
            last_review_at=date.today() - timedelta(days=21),
            overdue_reviews=1,
        )
        result = calculate_final_score(context)
        assert ReasonCode.OVERDUE_REVIEW in result["reason_codes"]
        assert result["components"]["review_urgency"] >= 50


class TestScenario5ExamApproaching:
    """Cenário 5: ENEM próximo."""

    def test_exam_approaching(self):
        context = _make_context(
            mastery_score=50.0,
            days_until_exam=15,
        )
        result = calculate_final_score(context)
        assert ReasonCode.EXAM_URGENCY in result["reason_codes"]
        assert result["components"]["exam_urgency"] >= 80


class TestScenario6Tie:
    """Cenário 6: Empate entre assuntos."""

    def test_tie_breaking(self):
        context_a = _make_context(
            topic_id=1,
            subject_id=1,
            mastery_score=50.0,
            confidence_score=50.0,
        )
        context_b = _make_context(
            topic_id=2,
            subject_id=2,
            mastery_score=50.0,
            confidence_score=50.0,
        )
        result_a = calculate_final_score(context_a)
        result_b = calculate_final_score(context_b)
        assert result_a["final_score"] == result_b["final_score"]


class TestScenario7LittleEvidence:
    """Cenário 7: Pouca evidência."""

    def test_little_evidence(self):
        context = _make_context(
            mastery_score=50.0,
            confidence_score=20.0,
            questions_answered=2,
        )
        result = calculate_final_score(context)
        assert ReasonCode.LOW_CONFIDENCE in result["reason_codes"]
        assert ReasonCode.NO_DATA in result["reason_codes"]


class TestScenario8MuchEvidence:
    """Cenário 8: Muita evidência."""

    def test_much_evidence(self):
        context = _make_context(
            mastery_score=70.0,
            confidence_score=85.0,
            questions_answered=30,
        )
        result = calculate_final_score(context)
        assert ReasonCode.LOW_CONFIDENCE not in result["reason_codes"]
        assert ReasonCode.NO_DATA not in result["reason_codes"]


class TestScenario9TimeConstraint:
    """Cenário 9: Falta de tempo."""

    def test_time_constraint(self):
        availability = _make_availability(
            daily_minutes=30,
            weekly_goal_minutes=150,
        )
        from app.decision_engine.policies import detect_weekly_goal_impossible
        from app.decision_engine.types import StudyRecommendation

        recs = [
            StudyRecommendation(
                priority=i,
                subject_id=i,
                topic_id=i,
                action=StudyAction.LEARN,
                duration_minutes=60,
                recommended_date=date.today(),
                score=70.0,
                mastery_score=30.0,
                confidence_score=40.0,
                reason_codes=[ReasonCode.LOW_MASTERY],
                explanation="Teste",
                study_phase=StudyPhase.MEDIUM_TERM,
            )
            for i in range(1, 4)
        ]
        conflict = detect_weekly_goal_impossible(recs, availability)
        assert conflict is not None


class TestScenario10MultipleSubjects:
    """Cenário 10: Várias matérias."""

    def test_multiple_subjects(self):
        contexts = [
            _make_context(subject_id=i, topic_id=i, mastery_score=30 + i * 10)
            for i in range(1, 6)
        ]
        results = [calculate_final_score(ctx) for ctx in contexts]
        scores = [r["final_score"] for r in results]
        assert len(scores) == 5
        assert all(0 <= s <= 100 for s in scores)


class TestScenario11FewTopics:
    """Cenário 11: Poucos assuntos."""

    def test_few_topics(self):
        contexts = [
            _make_context(subject_id=1, topic_id=1, mastery_score=40.0),
            _make_context(subject_id=2, topic_id=2, mastery_score=60.0),
        ]
        results = [calculate_final_score(ctx) for ctx in contexts]
        assert len(results) == 2
        assert results[0]["final_score"] > results[1]["final_score"]


class TestScenario12MissedSession:
    """Cenário 12: Sessão perdida."""

    def test_missed_session(self):
        context = _make_context(
            mastery_score=50.0,
            missed_sessions=3,
        )
        result = calculate_final_score(context)
        assert ReasonCode.MISSED_SESSION in result["reason_codes"]
        assert result["components"]["study_consistency"] < 50


class TestScenario13ExcessSessions:
    """Cenário 13: Excesso de sessões."""

    def test_excess_sessions(self):
        from app.decision_engine.policies import detect_excess_sessions
        from app.decision_engine.types import StudyRecommendation

        recs = [
            StudyRecommendation(
                priority=i,
                subject_id=1,
                topic_id=i,
                action=StudyAction.PRACTICE,
                duration_minutes=30,
                recommended_date=date.today(),
                score=50.0,
                mastery_score=50.0,
                confidence_score=50.0,
                reason_codes=[],
                explanation="Teste",
                study_phase=StudyPhase.MEDIUM_TERM,
            )
            for i in range(5)
        ]
        conflict = detect_excess_sessions(recs, max_per_subject=3)
        assert conflict is not None


class TestScenario14TimeSlotConflict:
    """Cenário 14: Conflito de horário."""

    def test_time_slot_conflict(self):
        from app.decision_engine.policies import detect_daily_limit_exceeded
        from app.decision_engine.types import StudyRecommendation

        today = date.today()
        recs = [
            StudyRecommendation(
                priority=1,
                subject_id=1,
                topic_id=1,
                action=StudyAction.LEARN,
                duration_minutes=90,
                recommended_date=today,
                score=70.0,
                mastery_score=30.0,
                confidence_score=40.0,
                reason_codes=[],
                explanation="Teste",
                study_phase=StudyPhase.MEDIUM_TERM,
            ),
            StudyRecommendation(
                priority=2,
                subject_id=2,
                topic_id=2,
                action=StudyAction.PRACTICE,
                duration_minutes=90,
                recommended_date=today,
                score=60.0,
                mastery_score=40.0,
                confidence_score=50.0,
                reason_codes=[],
                explanation="Teste",
                study_phase=StudyPhase.MEDIUM_TERM,
            ),
        ]
        availability = _make_availability(daily_minutes=120)
        conflict = detect_daily_limit_exceeded(recs, availability)
        assert conflict is not None


class TestScoreComponents:
    """Testes dos componentes individuais do score."""

    def test_need_score_range(self):
        context = _make_context()
        score = calculate_need_score(context)
        assert 0 <= score <= 100

    def test_weakness_score_range(self):
        context = _make_context()
        score = calculate_weakness_score(context)
        assert 0 <= score <= 100

    def test_recency_score_range(self):
        context = _make_context()
        score = calculate_recency_score(context)
        assert 0 <= score <= 100

    def test_exam_urgency_score_range(self):
        context = _make_context()
        score = calculate_exam_urgency_score(context)
        assert 0 <= score <= 100

    def test_review_urgency_score_range(self):
        context = _make_context()
        score = calculate_review_urgency_score(context)
        assert 0 <= score <= 100

    def test_historical_importance_score_range(self):
        context = _make_context()
        score = calculate_historical_importance_score(context)
        assert 0 <= score <= 100

    def test_study_consistency_score_range(self):
        context = _make_context()
        score = calculate_study_consistency_score(context)
        assert 0 <= score <= 100


class TestActionDetermination:
    """Testes de determinação de ação."""

    def test_learn_for_critical_mastery(self):
        context = _make_context(mastery_score=20.0)
        action = determine_action(context, StudyPhase.MEDIUM_TERM)
        assert action == StudyAction.LEARN

    def test_practice_for_low_mastery(self):
        context = _make_context(mastery_score=50.0)
        action = determine_action(context, StudyPhase.MEDIUM_TERM)
        assert action == StudyAction.PRACTICE

    def test_enem_for_medium_mastery(self):
        context = _make_context(mastery_score=65.0)
        action = determine_action(context, StudyPhase.MEDIUM_TERM)
        assert action == StudyAction.ENEM_QUESTIONS

    def test_difficult_for_high_mastery(self):
        context = _make_context(mastery_score=80.0)
        action = determine_action(context, StudyPhase.MEDIUM_TERM)
        assert action == StudyAction.DIFFICULT_QUESTIONS

    def test_review_for_final_stretch(self):
        context = _make_context(mastery_score=95.0)
        action = determine_action(context, StudyPhase.FINAL_STRETCH)
        assert action == StudyAction.REVIEW


class TestDurationEstimation:
    """Testes de estimativa de duração."""

    def test_duration_in_range(self):
        for mastery in [10, 30, 50, 70, 90]:
            duration = estimate_duration(
                StudyAction.LEARN, mastery, StudyPhase.MEDIUM_TERM
            )
            assert 20 <= duration <= 120

    def test_low_mastery_longer_duration(self):
        short = estimate_duration(StudyAction.LEARN, 80, StudyPhase.MEDIUM_TERM)
        long = estimate_duration(StudyAction.LEARN, 20, StudyPhase.MEDIUM_TERM)
        assert long >= short


class TestExplanations:
    """Testes de explicabilidade."""

    def test_build_explanation(self):
        codes = [ReasonCode.LOW_MASTERY, ReasonCode.EXAM_URGENCY]
        explanation = build_explanation(codes)
        assert "LOW_MASTERY" in explanation or "domínio" in explanation.lower()
        assert "EXAM_URGENCY" in explanation or "ENEM" in explanation

    def test_build_short_explanation(self):
        codes = [ReasonCode.LOW_MASTERY]
        explanation = build_short_explanation(codes)
        assert len(explanation) > 0

    def test_action_text(self):
        text = get_action_text("learn")
        assert "teoria" in text.lower() or "estudar" in text.lower()

    def test_mastery_level_text(self):
        text = get_mastery_level_text("critical")
        assert "crítico" in text.lower()


class TestConflictDetection:
    """Testes de detecção de conflitos."""

    def test_no_conflicts(self):
        availability = _make_availability()
        from app.decision_engine.types import StudyRecommendation

        recs = [
            StudyRecommendation(
                priority=1,
                subject_id=1,
                topic_id=1,
                action=StudyAction.PRACTICE,
                duration_minutes=30,
                recommended_date=date.today(),
                score=50.0,
                mastery_score=50.0,
                confidence_score=50.0,
                reason_codes=[],
                explanation="Teste",
                study_phase=StudyPhase.MEDIUM_TERM,
            )
        ]
        conflicts = detect_all_conflicts(recs, availability)
        assert len(conflicts) == 0

    def test_weekly_goal_impossible(self):
        availability = _make_availability(weekly_goal_minutes=100)
        from app.decision_engine.types import StudyRecommendation

        recs = [
            StudyRecommendation(
                priority=1,
                subject_id=1,
                topic_id=1,
                action=StudyAction.LEARN,
                duration_minutes=60,
                recommended_date=date.today(),
                score=70.0,
                mastery_score=30.0,
                confidence_score=40.0,
                reason_codes=[],
                explanation="Teste",
                study_phase=StudyPhase.MEDIUM_TERM,
            ),
            StudyRecommendation(
                priority=2,
                subject_id=2,
                topic_id=2,
                action=StudyAction.PRACTICE,
                duration_minutes=60,
                recommended_date=date.today(),
                score=60.0,
                mastery_score=40.0,
                confidence_score=50.0,
                reason_codes=[],
                explanation="Teste",
                study_phase=StudyPhase.MEDIUM_TERM,
            ),
        ]
        conflicts = detect_all_conflicts(recs, availability)
        assert any(c.conflict_type.value == "weekly_goal_impossible" for c in conflicts)
