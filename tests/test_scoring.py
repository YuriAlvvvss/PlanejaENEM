"""
Testes do módulo de scoring - PlanejaENEM Adaptive Planner v2.
"""

from datetime import date, timedelta

import pytest

from app.planner.scoring import (
    calculate_subject_need_score,
    difficulty_score,
    exam_proximity_score,
    normalize,
    overdue_reviews_score,
    pending_tasks_score,
    performance_score,
    priority_score,
    revision_score,
)


class TestNormalize:
    def test_normalize_default_range(self):
        assert normalize(50, 0, 100) == 50.0

    def test_normalize_min_value(self):
        assert normalize(0, 0, 100) == 0.0

    def test_normalize_max_value(self):
        assert normalize(100, 0, 100) == 100.0

    def test_normalize_custom_range(self):
        assert normalize(3, 1, 5) == 50.0

    def test_normalize_equal_min_max(self):
        assert normalize(50, 50, 50) == 50.0

    def test_normalize_below_min(self):
        assert normalize(-10, 0, 100) == 0.0

    def test_normalize_above_max(self):
        assert normalize(200, 0, 100) == 100.0


class TestPriorityScore:
    def test_priority_1(self):
        result = priority_score(1)
        assert result == 0.0

    def test_priority_5(self):
        result = priority_score(5)
        assert result == 100.0

    def test_priority_3(self):
        result = priority_score(3)
        assert result == 50.0

    def test_priority_monotonic(self):
        scores = [priority_score(i) for i in range(1, 6)]
        assert scores == sorted(scores)


class TestDifficultyScore:
    def test_difficulty_1(self):
        assert difficulty_score(1) == 0.0

    def test_difficulty_5(self):
        assert difficulty_score(5) == 100.0

    def test_difficulty_3(self):
        result = difficulty_score(3)
        assert 40 <= result <= 60

    def test_difficulty_monotonic(self):
        scores = [difficulty_score(i) for i in range(1, 6)]
        assert scores == sorted(scores)


class TestPerformanceScore:
    def test_no_data_returns_neutral(self):
        assert performance_score(None, 0) == 50.0

    def test_few_questions_returns_neutral(self):
        assert performance_score(80.0, 2) == 50.0

    def test_high_performance_low_score(self):
        result = performance_score(90.0, 10)
        assert result < 50.0

    def test_low_performance_high_score(self):
        result = performance_score(20.0, 10)
        assert result > 50.0

    def test_zero_questions(self):
        assert performance_score(None, 0) == 50.0

    def test_exactly_3_questions(self):
        result = performance_score(50.0, 3)
        assert result == 50.0

    def test_inverse_relationship(self):
        high = performance_score(90.0, 10)
        low = performance_score(10.0, 10)
        assert high < low


class TestExamProximityScore:
    def test_exam_today(self):
        assert exam_proximity_score(0) == 100.0

    def test_exam_tomorrow(self):
        assert exam_proximity_score(1) == 100.0

    def test_exam_1_week(self):
        result = exam_proximity_score(7)
        assert result >= 90.0

    def test_exam_2_weeks(self):
        result = exam_proximity_score(14)
        assert result >= 80.0

    def test_exam_1_month(self):
        result = exam_proximity_score(30)
        assert result >= 70.0

    def test_exam_3_months(self):
        result = exam_proximity_score(90)
        assert 40 <= result <= 70

    def test_exam_6_months(self):
        result = exam_proximity_score(180)
        assert 25 <= result <= 45

    def test_exam_1_year(self):
        result = exam_proximity_score(365)
        assert result <= 35

    def test_exam_past(self):
        assert exam_proximity_score(-10) == 100.0


class TestRevisionScore:
    def test_never_reviewed(self):
        result = revision_score(None)
        assert result == 80.0

    def test_reviewed_today(self):
        today = date.today()
        result = revision_score(today, today)
        assert result <= 15.0

    def test_reviewed_recently(self):
        today = date.today()
        result = revision_score(today - timedelta(days=2), today)
        assert result <= 40.0

    def test_reviewed_1_week_ago(self):
        today = date.today()
        result = revision_score(today - timedelta(days=7), today)
        assert 40 <= result <= 60

    def test_reviewed_2_weeks_ago(self):
        today = date.today()
        result = revision_score(today - timedelta(days=14), today)
        assert 60 <= result <= 80

    def test_reviewed_1_month_ago(self):
        today = date.today()
        result = revision_score(today - timedelta(days=30), today)
        assert result >= 80

    def test_reviewed_long_ago(self):
        today = date.today()
        result = revision_score(today - timedelta(days=60), today)
        assert result == 100.0


class TestOverdueReviewsScore:
    def test_no_overdue(self):
        assert overdue_reviews_score(0) == 0.0

    def test_one_overdue(self):
        assert overdue_reviews_score(1) == 40.0

    def test_two_overdue(self):
        assert overdue_reviews_score(2) == 60.0

    def test_five_overdue(self):
        assert overdue_reviews_score(5) == 80.0

    def test_many_overdue(self):
        assert overdue_reviews_score(10) == 100.0


class TestPendingTasksScore:
    def test_no_tasks(self):
        assert pending_tasks_score(0, 0) == 50.0

    def test_all_pending(self):
        assert pending_tasks_score(10, 10) == 100.0

    def test_none_pending(self):
        assert pending_tasks_score(0, 10) == 0.0

    def test_half_pending(self):
        result = pending_tasks_score(5, 10)
        assert 45 <= result <= 55

    def test_monotonic(self):
        scores = [pending_tasks_score(i, 10) for i in range(11)]
        assert scores == sorted(scores)


class TestCalculateSubjectNeedScore:
    def test_basic_calculation(self):
        result = calculate_subject_need_score(
            priority=3,
            difficulty=3,
            correct_pct=50.0,
            total_questions=10,
            days_until_exam=90,
            last_review_date=date.today() - timedelta(days=7),
            overdue_reviews=0,
            pending_tasks=2,
            total_tasks=5,
        )
        assert "total" in result
        assert "components" in result
        assert "weights" in result
        assert 0 <= result["total"] <= 100

    def test_high_need_scenario(self):
        result = calculate_subject_need_score(
            priority=5,
            difficulty=5,
            correct_pct=20.0,
            total_questions=10,
            days_until_exam=14,
            last_review_date=date.today() - timedelta(days=30),
            overdue_reviews=3,
            pending_tasks=8,
            total_tasks=10,
        )
        assert result["total"] >= 70

    def test_low_need_scenario(self):
        result = calculate_subject_need_score(
            priority=1,
            difficulty=1,
            correct_pct=95.0,
            total_questions=50,
            days_until_exam=365,
            last_review_date=date.today(),
            overdue_reviews=0,
            pending_tasks=0,
            total_tasks=10,
        )
        assert result["total"] <= 40

    def test_weights_sum_to_one(self):
        result = calculate_subject_need_score(
            priority=3, difficulty=3, correct_pct=50.0,
            total_questions=10, days_until_exam=90,
            last_review_date=None, overdue_reviews=0,
            pending_tasks=2, total_tasks=5,
        )
        weights = result["weights"]
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_components_are_0_100(self):
        result = calculate_subject_need_score(
            priority=3, difficulty=3, correct_pct=50.0,
            total_questions=10, days_until_exam=90,
            last_review_date=None, overdue_reviews=0,
            pending_tasks=2, total_tasks=5,
        )
        for component, value in result["components"].items():
            assert 0 <= value <= 100, f"Component {component} out of range: {value}"

    def test_score_bounded(self):
        for priority in [1, 3, 5]:
            for difficulty in [1, 3, 5]:
                for days in [0, 30, 90, 365]:
                    result = calculate_subject_need_score(
                        priority=priority, difficulty=difficulty,
                        correct_pct=50.0, total_questions=10,
                        days_until_exam=days, last_review_date=None,
                        overdue_reviews=0, pending_tasks=2, total_tasks=5,
                    )
                    assert 0 <= result["total"] <= 100
