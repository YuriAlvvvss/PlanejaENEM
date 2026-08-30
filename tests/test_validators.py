"""
Testes do módulo de validadores - PlanejaENEM Adaptive Planner v2.
"""

from datetime import date, timedelta

import pytest

from app.planner.validators import (
    check_availability_conflict,
    safe_divide,
    validate_available_days,
    validate_available_hours,
    validate_daily_minutes,
    validate_exam_date,
    validate_subject_settings,
    validate_total_sessions_per_day,
)


class TestValidateAvailableDays:
    def test_valid_days(self):
        days, errors = validate_available_days(["seg", "qua", "sex"])
        assert days == ["seg", "qua", "sex"]
        assert errors == []

    def test_empty_days(self):
        days, errors = validate_available_days([])
        assert days == []
        assert len(errors) > 0

    def test_none_days(self):
        days, errors = validate_available_days(None)
        assert days == []
        assert len(errors) > 0

    def test_invalid_days_filtered(self):
        days, errors = validate_available_days(["seg", "xyz", "qua"])
        assert "seg" in days
        assert "qua" in days
        assert "xyz" not in days

    def test_duplicates_removed(self):
        days, errors = validate_available_days(["seg", "seg", "qua"])
        assert days.count("seg") == 1

    def test_case_insensitive(self):
        days, errors = validate_available_days(["SEG", "Qua"])
        assert "seg" in days
        assert "qua" in days

    def test_aliases(self):
        days, errors = validate_available_days(["mon", "tue"])
        assert "seg" in days
        assert "ter" in days


class TestValidateAvailableHours:
    def test_valid_hours(self):
        hours, errors = validate_available_hours("08:00-10:00, 15:00-17:00")
        assert len(hours) == 2
        assert errors == []

    def test_single_slot(self):
        hours, errors = validate_available_hours("08:00-10:00")
        assert len(hours) == 1

    def test_empty_string(self):
        hours, errors = validate_available_hours("")
        assert hours == []
        assert len(errors) > 0

    def test_invalid_format(self):
        hours, errors = validate_available_hours("08:00")
        assert len(errors) > 0

    def test_end_before_start(self):
        hours, errors = validate_available_hours("10:00-08:00")
        assert len(errors) > 0

    def test_too_short_slot(self):
        hours, errors = validate_available_hours("08:00-08:15")
        assert len(errors) > 0

    def test_invalid_time(self):
        hours, errors = validate_available_hours("abc-def")
        assert len(errors) > 0


class TestValidateDailyMinutes:
    def test_valid_minutes(self):
        minutes, errors = validate_daily_minutes(120)
        assert minutes == 120
        assert errors == []

    def test_string_minutes(self):
        minutes, errors = validate_daily_minutes("120")
        assert minutes == 120

    def test_below_minimum(self):
        minutes, errors = validate_daily_minutes(10)
        assert minutes == 30
        assert len(errors) > 0

    def test_above_maximum(self):
        minutes, errors = validate_daily_minutes(700)
        assert minutes == 600
        assert len(errors) > 0

    def test_invalid_string(self):
        minutes, errors = validate_daily_minutes("abc")
        assert minutes == 30
        assert len(errors) > 0

    def test_none_value(self):
        minutes, errors = validate_daily_minutes(None)
        assert minutes == 30
        assert len(errors) > 0


class TestValidateExamDate:
    def test_valid_future_date(self):
        future = date.today() + timedelta(days=30)
        date_result, errors = validate_exam_date(future.isoformat())
        assert date_result == future
        assert errors == []

    def test_empty_date(self):
        date_result, errors = validate_exam_date("")
        assert date_result is None
        assert len(errors) > 0

    def test_invalid_format(self):
        date_result, errors = validate_exam_date("15/09/2026")
        assert date_result is None
        assert len(errors) > 0

    def test_past_date(self):
        past = date.today() - timedelta(days=10)
        date_result, errors = validate_exam_date(past.isoformat())
        assert len(errors) > 0

    def test_today(self):
        today = date.today()
        date_result, errors = validate_exam_date(today.isoformat())
        assert date_result == today


class TestValidateSubjectSettings:
    def test_valid_settings(self):
        class MockSubject:
            def __init__(self, id):
                self.id = id

        subjects = [MockSubject(1), MockSubject(2)]
        form_data = {"priority_1": "5", "difficulty_1": "4", "priority_2": "3", "difficulty_2": "2"}
        settings, errors = validate_subject_settings(subjects, form_data)
        assert settings[1]["priority"] == 5
        assert settings[1]["difficulty"] == 4
        assert settings[2]["priority"] == 3
        assert settings[2]["difficulty"] == 2

    def test_invalid_priority_defaults(self):
        class MockSubject:
            def __init__(self, id):
                self.id = id

        subjects = [MockSubject(1)]
        form_data = {"priority_1": "invalid", "difficulty_1": "invalid"}
        settings, errors = validate_subject_settings(subjects, form_data)
        assert settings[1]["priority"] == 3
        assert settings[1]["difficulty"] == 3


class TestCheckAvailabilityConflict:
    def test_no_conflict(self):
        existing = [
            {"session_date": date(2026, 1, 1), "start_time": "08:00", "end_time": "10:00"}
        ]
        assert check_availability_conflict("10:00", "12:00", existing, date(2026, 1, 1)) is False

    def test_conflict(self):
        existing = [
            {"session_date": date(2026, 1, 1), "start_time": "08:00", "end_time": "10:00"}
        ]
        assert check_availability_conflict("09:00", "11:00", existing, date(2026, 1, 1)) is True

    def test_different_date(self):
        existing = [
            {"session_date": date(2026, 1, 1), "start_time": "08:00", "end_time": "10:00"}
        ]
        assert check_availability_conflict("09:00", "11:00", existing, date(2026, 1, 2)) is False

    def test_empty_existing(self):
        assert check_availability_conflict("08:00", "10:00", [], date(2026, 1, 1)) is False


class TestValidateTotalSessionsPerDay:
    def test_within_limit(self):
        assert validate_total_sessions_per_day(3) == []

    def test_exceeds_limit(self):
        errors = validate_total_sessions_per_day(10)
        assert len(errors) > 0


class TestSafeDivide:
    def test_normal_division(self):
        assert safe_divide(10, 2) == 5.0

    def test_division_by_zero(self):
        assert safe_divide(10, 0) == 0.0

    def test_custom_default(self):
        assert safe_divide(10, 0, default=-1) == -1.0

    def test_zero_numerator(self):
        assert safe_divide(0, 5) == 0.0
