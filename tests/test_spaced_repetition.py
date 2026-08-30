"""
Testes do módulo de revisão espaçada - PlanejaENEM Adaptive Planner v2.
"""

from datetime import date, timedelta

import pytest

from app.planner.spaced_repetition import (
    adaptive_interval_adjustment,
    calculate_next_review_date,
    calculate_next_review_from_task,
    calculate_overdue_days,
    classify_performance,
    get_review_interval,
    get_review_status,
)


class TestClassifyPerformance:
    def test_no_data_returns_medium(self):
        assert classify_performance(None, 0) == "medium"

    def test_few_questions_returns_medium(self):
        assert classify_performance(80.0, 2) == "medium"

    def test_excellent(self):
        assert classify_performance(90.0, 10) == "excellent"

    def test_good(self):
        assert classify_performance(75.0, 10) == "good"

    def test_medium(self):
        assert classify_performance(55.0, 10) == "medium"

    def test_low(self):
        assert classify_performance(35.0, 10) == "low"

    def test_very_low(self):
        assert classify_performance(10.0, 10) == "very_low"

    def test_boundary_85(self):
        assert classify_performance(85.0, 10) == "excellent"

    def test_boundary_70(self):
        assert classify_performance(70.0, 10) == "good"

    def test_boundary_50(self):
        assert classify_performance(50.0, 10) == "medium"

    def test_boundary_30(self):
        assert classify_performance(30.0, 10) == "low"


class TestGetReviewInterval:
    def test_excellent(self):
        assert get_review_interval("excellent") == 30

    def test_good(self):
        assert get_review_interval("good") == 14

    def test_medium(self):
        assert get_review_interval("medium") == 7

    def test_low(self):
        assert get_review_interval("low") == 3

    def test_very_low(self):
        assert get_review_interval("very_low") == 1

    def test_unknown_defaults_to_7(self):
        assert get_review_interval("unknown") == 7


class TestCalculateNextReviewDate:
    def test_high_performance_long_interval(self):
        today = date.today()
        result = calculate_next_review_date(
            correct_pct=90.0, total_questions=10, today=today
        )
        expected = today + timedelta(days=30)
        assert result == expected

    def test_medium_performance_short_interval(self):
        today = date.today()
        result = calculate_next_review_date(
            correct_pct=55.0, total_questions=10, today=today
        )
        expected = today + timedelta(days=7)
        assert result == expected

    def test_low_performance_very_short(self):
        today = date.today()
        result = calculate_next_review_date(
            correct_pct=20.0, total_questions=10, today=today
        )
        expected = today + timedelta(days=1)
        assert result == expected

    def test_no_data_defaults_to_medium(self):
        today = date.today()
        result = calculate_next_review_date(
            correct_pct=None, total_questions=0, today=today
        )
        expected = today + timedelta(days=7)
        assert result == expected

    def test_review_count_extends_interval_for_good(self):
        today = date.today()
        result_no_review = calculate_next_review_date(
            correct_pct=90.0, total_questions=10,
            today=today, review_count=0,
        )
        result_with_review = calculate_next_review_date(
            correct_pct=90.0, total_questions=10,
            today=today, review_count=3,
        )
        assert result_with_review >= result_no_review

    def test_review_count_no_effect_on_low(self):
        today = date.today()
        result_no_review = calculate_next_review_date(
            correct_pct=20.0, total_questions=10,
            today=today, review_count=0,
        )
        result_with_review = calculate_next_review_date(
            correct_pct=20.0, total_questions=10,
            today=today, review_count=3,
        )
        assert result_no_review == result_with_review


class TestCalculateNextReviewFromTask:
    def test_completed_task(self):
        today = date.today()
        result = calculate_next_review_from_task(
            task_completed=True,
            correct_pct=80.0,
            total_questions=10,
            today=today,
        )
        assert result is not None
        assert result > today

    def test_uncompleted_task(self):
        result = calculate_next_review_from_task(
            task_completed=False,
            correct_pct=80.0,
            total_questions=10,
        )
        assert result is None


class TestGetReviewStatus:
    def test_overdue(self):
        today = date.today()
        review_date = today - timedelta(days=3)
        assert get_review_status(review_date, today) == "overdue"

    def test_today(self):
        today = date.today()
        assert get_review_status(today, today) == "today"

    def test_upcoming(self):
        today = date.today()
        review_date = today + timedelta(days=5)
        assert get_review_status(review_date, today) == "upcoming"

    def test_none(self):
        assert get_review_status(None) == "none"


class TestCalculateOverdueDays:
    def test_not_overdue(self):
        today = date.today()
        assert calculate_overdue_days(today, today) == 0

    def test_overdue(self):
        today = date.today()
        review_date = today - timedelta(days=5)
        assert calculate_overdue_days(review_date, today) == 5

    def test_none_review(self):
        assert calculate_overdue_days(None) == 0

    def test_future_review(self):
        today = date.today()
        review_date = today + timedelta(days=5)
        assert calculate_overdue_days(review_date, today) == 0


class TestAdaptiveIntervalAdjustment:
    def test_base_case(self):
        assert adaptive_interval_adjustment(7, 0, 0) == 7

    def test_consecutive_good(self):
        result = adaptive_interval_adjustment(7, 5, 0)
        assert result > 7

    def test_consecutive_bad(self):
        result = adaptive_interval_adjustment(7, 0, 3)
        assert result < 7

    def test_minimum_interval(self):
        result = adaptive_interval_adjustment(1, 0, 10)
        assert result >= 1

    def test_very_good_extends_a_lot(self):
        base = adaptive_interval_adjustment(7, 10, 0)
        few = adaptive_interval_adjustment(7, 2, 0)
        assert base >= few
