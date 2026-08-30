"""
Testes do módulo scheduler - PlanejaENEM Adaptive Planner v2.
"""

from datetime import date, time, timedelta

import pytest

from app.planner.scheduler import (
    calculate_time_allocation,
    distribute_sessions,
    exam_date_from_schedule,
    generate_session_schedule,
    get_study_phase,
    pick_next_subject,
    recommend_study_type,
    reschedule_missed_sessions,
    should_limit_consecutive,
)


class TestGetStudyPhase:
    def test_long_term(self):
        assert get_study_phase(200) == "long_term"

    def test_medium_term(self):
        assert get_study_phase(90) == "medium_term"

    def test_final_stretch(self):
        assert get_study_phase(15) == "final_stretch"

    def test_boundary_120(self):
        assert get_study_phase(121) == "long_term"
        assert get_study_phase(120) == "medium_term"

    def test_boundary_30(self):
        assert get_study_phase(31) == "medium_term"
        assert get_study_phase(30) == "final_stretch"

    def test_zero_days(self):
        assert get_study_phase(0) == "final_stretch"


class TestRecommendStudyType:
    def test_long_term_low_performance(self):
        assert recommend_study_type("long_term", "low", 200) == "teoria"

    def test_long_term_medium_performance(self):
        assert recommend_study_type("long_term", "medium", 200) == "exercicios"

    def test_long_term_high_performance(self):
        assert recommend_study_type("long_term", "excellent", 200) == "exercicios"

    def test_medium_term_low_performance(self):
        assert recommend_study_type("medium_term", "low", 90) == "teoria"

    def test_medium_term_high_performance(self):
        assert recommend_study_type("medium_term", "excellent", 90) == "revisao"

    def test_final_stretch_low_performance(self):
        assert recommend_study_type("final_stretch", "low", 15) == "exercicios"

    def test_final_stretch_high_performance(self):
        assert recommend_study_type("final_stretch", "excellent", 15) == "questoes_enem"


class TestCalculateTimeAllocation:
    def test_basic_allocation(self):
        scores = [
            {"subject_id": 1, "score": 80, "area": "matematica"},
            {"subject_id": 2, "score": 40, "area": "humanas"},
        ]
        result = calculate_time_allocation(scores, 600, 5)
        assert "allocations" in result
        assert len(result["allocations"]) == 2

    def test_higher_score_gets_more_time(self):
        scores = [
            {"subject_id": 1, "score": 80, "area": "matematica"},
            {"subject_id": 2, "score": 20, "area": "humanas"},
        ]
        result = calculate_time_allocation(scores, 600, 5)
        alloc_1 = result["allocations"][1]["minutes"]
        alloc_2 = result["allocations"][2]["minutes"]
        assert alloc_1 > alloc_2

    def test_empty_scores(self):
        result = calculate_time_allocation([], 600, 5)
        assert result["allocations"] == {}

    def test_zero_goal(self):
        scores = [{"subject_id": 1, "score": 80, "area": "matematica"}]
        result = calculate_time_allocation(scores, 0, 5)
        assert result["total_minutes"] == 0

    def test_equal_scores_equal_allocation(self):
        scores = [
            {"subject_id": 1, "score": 50, "area": "matematica"},
            {"subject_id": 2, "score": 50, "area": "humanas"},
        ]
        result = calculate_time_allocation(scores, 600, 5)
        alloc_1 = result["allocations"][1]["minutes"]
        alloc_2 = result["allocations"][2]["minutes"]
        assert abs(alloc_1 - alloc_2) <= 10

    def test_total_does_not_exceed_goal(self):
        scores = [
            {"subject_id": 1, "score": 90, "area": "matematica"},
            {"subject_id": 2, "score": 30, "area": "humanas"},
            {"subject_id": 3, "score": 60, "area": "natureza"},
        ]
        result = calculate_time_allocation(scores, 600, 5)
        assert result["total_minutes"] <= 600


class TestShouldLimitConsecutive:
    def test_no_limit_needed(self):
        assert should_limit_consecutive([1, 2, 3], 2) is False

    def test_limit_needed(self):
        assert should_limit_consecutive([1, 1, 1], 2) is True

    def test_empty_list(self):
        assert should_limit_consecutive([], 2) is False

    def test_exact_limit(self):
        assert should_limit_consecutive([1, 1], 2) is True

    def test_one_below_limit(self):
        assert should_limit_consecutive([1], 2) is False


class TestPickNextSubject:
    def test_picks_highest_score(self):
        subjects = [
            {"subject_id": 1, "score": 30, "area": "matematica"},
            {"subject_id": 2, "score": 80, "area": "humanas"},
        ]
        result = pick_next_subject(subjects, [], {})
        assert result["subject_id"] == 2

    def test_avoids_consecutive(self):
        subjects = [
            {"subject_id": 1, "score": 90, "area": "matematica"},
            {"subject_id": 2, "score": 60, "area": "humanas"},
        ]
        result = pick_next_subject(subjects, [1, 1, 1], {})
        assert result["subject_id"] == 2

    def test_empty_subjects(self):
        assert pick_next_subject([], [], {}) is None

    def test_single_subject(self):
        subjects = [{"subject_id": 1, "score": 50, "area": "matematica"}]
        result = pick_next_subject(subjects, [], {})
        assert result["subject_id"] == 1


class TestGenerateSessionSchedule:
    def test_basic_schedule(self):
        schedule = generate_session_schedule(
            available_days=["seg", "qua"],
            available_hours=["08:00-10:00"],
            daily_minutes=120,
            exam_date=date.today() + timedelta(days=14),
            today=date.today(),
        )
        assert len(schedule) > 0

    def test_no_days_selected(self):
        schedule = generate_session_schedule(
            available_days=[],
            available_hours=["08:00-10:00"],
            daily_minutes=120,
            exam_date=date.today() + timedelta(days=14),
            today=date.today(),
        )
        assert schedule == []

    def test_no_hours(self):
        schedule = generate_session_schedule(
            available_days=["seg"],
            available_hours=[],
            daily_minutes=120,
            exam_date=date.today() + timedelta(days=14),
            today=date.today(),
        )
        assert schedule == []

    def test_invalid_hours(self):
        schedule = generate_session_schedule(
            available_days=["seg"],
            available_hours=["invalid"],
            daily_minutes=120,
            exam_date=date.today() + timedelta(days=14),
            today=date.today(),
        )
        assert schedule == []

    def test_exam_in_past(self):
        schedule = generate_session_schedule(
            available_days=["seg"],
            available_hours=["08:00-10:00"],
            daily_minutes=120,
            exam_date=date.today() - timedelta(days=1),
            today=date.today(),
        )
        assert schedule == []


class TestDistributeSessions:
    def test_basic_distribution(self):
        today = date.today()
        schedule = [
            {
                "date": today + timedelta(days=(0 - today.weekday()) % 7),
                "day_of_week": "seg",
                "slots": [(time(8, 0), time(10, 0))],
            }
        ]
        allocations = {
            1: {"minutes": 300},
            2: {"minutes": 300},
        }
        subject_data = {
            1: {"score": 80, "area": "matematica", "performance": "medium"},
            2: {"score": 50, "area": "humanas", "performance": "medium"},
        }
        sessions = distribute_sessions(schedule, allocations, subject_data, 120)
        assert len(sessions) > 0

    def test_empty_schedule(self):
        sessions = distribute_sessions([], {}, {}, 120)
        assert sessions == []

    def test_empty_allocations(self):
        today = date.today()
        schedule = [{"date": today, "day_of_week": "seg", "slots": [(time(8, 0), time(10, 0))]}]
        sessions = distribute_sessions(schedule, {}, {}, 120)
        assert sessions == []

    def test_sessions_have_required_fields(self):
        today = date.today()
        schedule = [
            {
                "date": today + timedelta(days=(0 - today.weekday()) % 7),
                "day_of_week": "seg",
                "slots": [(time(8, 0), time(10, 0))],
            }
        ]
        allocations = {1: {"minutes": 300}}
        subject_data = {1: {"score": 80, "area": "matematica", "performance": "medium"}}
        sessions = distribute_sessions(schedule, allocations, subject_data, 120)
        for session in sessions:
            assert "subject_id" in session
            assert "session_date" in session
            assert "start_time" in session
            assert "end_time" in session
            assert "duration_minutes" in session


class TestExamDateFromSchedule:
    def test_basic(self):
        d1 = date(2026, 1, 1)
        d2 = date(2026, 1, 15)
        schedule = [{"date": d1}, {"date": d2}]
        assert exam_date_from_schedule(schedule) == d2

    def test_empty(self):
        assert exam_date_from_schedule([]) == date.today()


class TestRescheduleMissedSessions:
    def test_no_missed(self):
        result = reschedule_missed_sessions([], [], ["seg"], ["08:00-10:00"], 120, date.today() + timedelta(days=30))
        assert result == []

    def test_with_missed(self):
        today = date.today()
        missed = [
            {
                "subject_id": 1,
                "session_date": today - timedelta(days=1),
                "start_time": time(8, 0),
                "end_time": time(10, 0),
                "duration_minutes": 120,
                "priority_score": 50,
            }
        ]
        existing = []
        result = reschedule_missed_sessions(
            missed, existing, ["seg", "ter"], ["08:00-10:00"],
            120, today + timedelta(days=30), today
        )
        assert len(result) > 0
        assert result[0].get("rescheduled") is True
