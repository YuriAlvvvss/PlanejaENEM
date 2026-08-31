"""
Testes para PlanejaENEM 3.0 - Performance Layer.

Testa:
- Mastery score (calculate_mastery)
- Confidence score
- Trend detection
- Recommendation engine (recommend_next_topic)
- Reason codes
- Study type recommendation
- Knowledge state updates
- Integration planner + performance
- Multi-user isolation
- Edge cases
"""

import math
from datetime import date, datetime, timedelta, timezone

import pytest

from app import create_app
from app.extensions import db
from app.models import (
    Question,
    QuestionAttempt,
    Subject,
    Topic,
    User,
)
from app.performance.models import KnowledgeState
from app.performance.mastery import (
    calculate_accuracy_score,
    calculate_confidence_score,
    calculate_consistency_score,
    calculate_difficulty_score,
    calculate_mastery,
    calculate_recent_performance_score,
    calculate_recency_score,
    get_mastery_level,
    get_trend,
    recommend_study_type,
)
from app.performance.recommendations import (
    build_reason_messages,
    calculate_need_score,
    recommend_next_topic,
)
from app.performance.services import (
    get_subject_attempt_stats,
    get_topic_attempt_stats,
    get_user_knowledge_summary,
    update_knowledge_state,
)
from app.planner.spaced_repetition import (
    classify_mastery_for_review,
    calculate_next_review_from_mastery,
)


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user(app):
    with app.app_context():
        user = User(nome="Test User", email="test@example.com")
        user.set_senha("password123")
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture
def subject(app, user):
    with app.app_context():
        subject = Subject(
            nome="Matematica",
            cor="#007bff",
            prioridade=3,
            dificuldade=4,
            area="exatas",
            user_id=user,
        )
        db.session.add(subject)
        db.session.commit()
        return subject.id


@pytest.fixture
def topic(app, user, subject):
    with app.app_context():
        topic = Topic(
            nome="Geometria Analitica",
            subject_id=subject,
            user_id=user,
        )
        db.session.add(topic)
        db.session.commit()
        return topic.id


@pytest.fixture
def questions(app, user, subject, topic):
    with app.app_context():
        questions = []
        for i in range(10):
            q = Question(
                enunciado=f"Questao {i}",
                alternativa_a="A",
                alternativa_b="B",
                alternativa_c="C",
                alternativa_d="D",
                alternativa_e="E",
                resposta_correta="A",
                subject_id=subject,
                topic_id=topic,
                user_id=user,
                dificuldade=3 + (i % 3),
            )
            db.session.add(q)
            questions.append(q)
        db.session.commit()
        return [q.id for q in questions]


# =============================================================================
# TESTES DE MASTERY SCORE
# =============================================================================


class TestMasteryScore:
    """Testes para calculate_mastery."""

    def test_mastery_zero_questions(self):
        result = calculate_mastery(
            questions_correct=0,
            questions_wrong=0,
            questions_answered=0,
            recent_correct=0,
            recent_total=0,
        )
        assert result["mastery_score"] == 0.0
        assert result["confidence_score"] == 0.0

    def test_mastery_all_correct(self):
        result = calculate_mastery(
            questions_correct=30,
            questions_wrong=0,
            questions_answered=30,
            recent_correct=10,
            recent_total=10,
            average_difficulty=4.0,
            consecutive_correct=10,
            consecutive_wrong=0,
        )
        assert result["mastery_score"] >= 80.0
        assert result["confidence_score"] >= 80.0

    def test_mastery_all_wrong(self):
        result = calculate_mastery(
            questions_correct=0,
            questions_wrong=30,
            questions_answered=30,
            recent_correct=0,
            recent_total=10,
        )
        assert result["mastery_score"] <= 20.0

    def test_mastery_score_between_0_and_100(self):
        for correct in range(0, 31):
            result = calculate_mastery(
                questions_correct=correct,
                questions_wrong=30 - correct,
                questions_answered=30,
                recent_correct=min(correct, 10),
                recent_total=10,
            )
            assert 0 <= result["mastery_score"] <= 100, (
                f"mastery_score {result['mastery_score']} out of range for {correct} correct"
            )

    def test_mastery_weights_sum_to_one(self):
        result = calculate_mastery(
            questions_correct=15,
            questions_wrong=15,
            questions_answered=30,
            recent_correct=5,
            recent_total=10,
        )
        weights = result["weights"]
        total_weight = sum(weights.values())
        assert abs(total_weight - 1.0) < 0.001

    def test_recent_drop_penalizes(self):
        good_recent = calculate_mastery(
            questions_correct=25,
            questions_wrong=5,
            questions_answered=30,
            recent_correct=9,
            recent_total=10,
            consecutive_correct=5,
        )
        bad_recent = calculate_mastery(
            questions_correct=25,
            questions_wrong=5,
            questions_answered=30,
            recent_correct=3,
            recent_total=10,
            consecutive_wrong=3,
        )
        assert good_recent["mastery_score"] > bad_recent["mastery_score"]

    def test_consistency_matters(self):
        consistent = calculate_mastery(
            questions_correct=15,
            questions_wrong=15,
            questions_answered=30,
            recent_correct=5,
            recent_total=10,
            consecutive_correct=5,
            consecutive_wrong=0,
        )
        inconsistent = calculate_mastery(
            questions_correct=15,
            questions_wrong=15,
            questions_answered=30,
            recent_correct=5,
            recent_total=10,
            consecutive_correct=0,
            consecutive_wrong=3,
        )
        assert consistent["mastery_score"] > inconsistent["mastery_score"]


# =============================================================================
# TESTES DE CONFIDENCE SCORE
# =============================================================================


class TestConfidenceScore:
    """Testes para calculate_confidence_score."""

    def test_zero_questions(self):
        assert calculate_confidence_score(0) == 0.0

    def test_one_question(self):
        score = calculate_confidence_score(1)
        assert 0 < score < 30

    def test_three_questions(self):
        score = calculate_confidence_score(3)
        assert 20 < score < 50

    def test_ten_questions(self):
        score = calculate_confidence_score(10)
        assert 50 < score < 80

    def test_thirty_questions(self):
        score = calculate_confidence_score(30)
        assert score >= 80

    def test_confidence_increases_monotonically(self):
        prev = 0
        for n in [1, 3, 5, 10, 20, 30, 50]:
            current = calculate_confidence_score(n)
            assert current > prev
            prev = current

    def test_confidence_between_0_and_100(self):
        for n in range(0, 101):
            score = calculate_confidence_score(n)
            assert 0 <= score <= 100


# =============================================================================
# TESTES DE TREND
# =============================================================================


class TestTrend:
    """Testes para get_trend."""

    def test_improving(self):
        assert get_trend(80.0, 60.0) == "improving"

    def test_declining(self):
        assert get_trend(40.0, 70.0) == "declining"

    def test_stable(self):
        assert get_trend(70.0, 72.0) == "stable"

    def test_none_values(self):
        assert get_trend(None, 70.0) == "stable"
        assert get_trend(70.0, None) == "stable"
        assert get_trend(None, None) == "stable"

    def test_exactly_5_percent(self):
        assert get_trend(75.0, 70.0) == "improving"
        assert get_trend(65.0, 70.0) == "declining"


# =============================================================================
# TESTES DE MASTERY LEVEL
# =============================================================================


class TestMasteryLevel:
    """Testes para get_mastery_level."""

    def test_beginner(self):
        assert get_mastery_level(0) == "beginner"
        assert get_mastery_level(39) == "beginner"

    def test_intermediate(self):
        assert get_mastery_level(40) == "intermediate"
        assert get_mastery_level(59) == "intermediate"

    def test_advanced(self):
        assert get_mastery_level(60) == "advanced"
        assert get_mastery_level(74) == "advanced"

    def test_proficient(self):
        assert get_mastery_level(75) == "proficient"
        assert get_mastery_level(89) == "proficient"

    def test_expert(self):
        assert get_mastery_level(90) == "expert"
        assert get_mastery_level(100) == "expert"


# =============================================================================
# TESTES DE STUDY TYPE RECOMMENDATION
# =============================================================================


class TestStudyTypeRecommendation:
    """Testes para recommend_study_type."""

    def test_beginner_study_type(self):
        assert recommend_study_type(20) == "teoria_exercicios"
        assert recommend_study_type(39) == "teoria_exercicios"

    def test_intermediate_study_type(self):
        assert recommend_study_type(40) == "exercicios"
        assert recommend_study_type(59) == "exercicios"

    def test_advanced_study_type(self):
        assert recommend_study_type(60) == "questoes_enem"
        assert recommend_study_type(74) == "questoes_enem"

    def test_proficient_study_type(self):
        assert recommend_study_type(75) == "questoes_enem_revisao"
        assert recommend_study_type(89) == "questoes_enem_revisao"

    def test_expert_study_type(self):
        assert recommend_study_type(90) == "questoes_dificeis_revisao"
        assert recommend_study_type(100) == "questoes_dificeis_revisao"


# =============================================================================
# TESTES DE COMPONENTES INDIVIDUAIS
# =============================================================================


class TestAccuracyScore:
    def test_zero_questions(self):
        assert calculate_accuracy_score(0, 0) == 0.0

    def test_all_correct(self):
        assert calculate_accuracy_score(10, 10) == 100.0

    def test_all_wrong(self):
        assert calculate_accuracy_score(0, 10) == 0.0

    def test_half(self):
        assert calculate_accuracy_score(5, 10) == 50.0


class TestDifficultyScore:
    def test_zero_questions(self):
        assert calculate_difficulty_score(0, 0, 3.0) == 0.0

    def test_high_difficulty_bonus(self):
        easy = calculate_difficulty_score(10, 8, 2.0)
        hard = calculate_difficulty_score(10, 8, 5.0)
        assert hard > easy


class TestConsistencyScore:
    def test_zero_questions(self):
        assert calculate_consistency_score(0, 0, 0) == 0.0

    def test_consecutive_correct_bonus(self):
        good = calculate_consistency_score(5, 0, 10)
        bad = calculate_consistency_score(0, 3, 10)
        assert good > bad


class TestRecencyScore:
    def test_no_activity(self):
        assert calculate_recency_score(None, None) == 0.0

    def test_recent_activity(self):
        now = datetime.now(timezone.utc)
        score = calculate_recency_score(now, None, now)
        assert score == 100.0

    def test_old_activity(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=60)
        score = calculate_recency_score(old, None, now)
        assert score <= 30.0


# =============================================================================
# TESTES DE NEED SCORE
# =============================================================================


class TestNeedScore:
    """Testes para calculate_need_score."""

    def test_low_mastery_high_need(self):
        result = calculate_need_score(
            mastery_score=20.0,
            recent_accuracy=30.0,
            historical_accuracy=50.0,
            subject_difficulty=4,
            days_until_exam=30,
            last_review_at=None,
            confidence_score=30.0,
        )
        assert result["need_score"] >= 70.0

    def test_high_mastery_low_need(self):
        now = datetime.now(timezone.utc)
        result = calculate_need_score(
            mastery_score=90.0,
            recent_accuracy=85.0,
            historical_accuracy=80.0,
            subject_difficulty=3,
            days_until_exam=120,
            last_review_at=now - timedelta(days=2),
            confidence_score=90.0,
        )
        assert result["need_score"] <= 40.0

    def test_need_score_between_0_and_100(self):
        result = calculate_need_score(
            mastery_score=50.0,
            recent_accuracy=60.0,
            historical_accuracy=55.0,
            subject_difficulty=3,
            days_until_exam=60,
            last_review_at=datetime.now(timezone.utc) - timedelta(days=7),
            confidence_score=50.0,
        )
        assert 0 <= result["need_score"] <= 100

    def test_reason_codes_generated(self):
        result = calculate_need_score(
            mastery_score=25.0,
            recent_accuracy=30.0,
            historical_accuracy=70.0,
            subject_difficulty=4,
            days_until_exam=14,
            last_review_at=None,
            confidence_score=20.0,
        )
        codes = result["reason_codes"]
        assert "low_mastery" in codes
        assert "recent_poor_performance" in codes
        assert "overdue_review" in codes
        assert "low_confidence" in codes
        assert "exam_approaching" in codes

    def test_overdue_review_detected(self):
        result = calculate_need_score(
            mastery_score=60.0,
            recent_accuracy=70.0,
            historical_accuracy=65.0,
            subject_difficulty=3,
            days_until_exam=60,
            last_review_at=datetime.now(timezone.utc) - timedelta(days=20),
            confidence_score=60.0,
        )
        assert "overdue_review" in result["reason_codes"]

    def test_weights_sum_to_one(self):
        result = calculate_need_score(
            mastery_score=50.0,
            recent_accuracy=60.0,
            historical_accuracy=55.0,
            subject_difficulty=3,
            days_until_exam=60,
            last_review_at=datetime.now(timezone.utc) - timedelta(days=7),
            confidence_score=50.0,
        )
        total = sum(result["weights"].values())
        assert abs(total - 1.0) < 0.001


# =============================================================================
# TESTES DE REASON MESSAGES
# =============================================================================


class TestReasonMessages:
    def test_low_mastery_message(self):
        messages = build_reason_messages(
            ["low_mastery"], {"mastery_score": 35.0}
        )
        assert any("35%" in m for m in messages)

    def test_recent_poor_message(self):
        messages = build_reason_messages(
            ["recent_poor_performance"],
            {"recent_accuracy": 40.0, "recent_total": 10, "recent_correct": 4},
        )
        assert any("4 de 10" in m for m in messages)

    def test_overdue_review_message(self):
        messages = build_reason_messages(
            ["overdue_review"], {"days_since_review": 12}
        )
        assert any("12 dias" in m for m in messages)

    def test_exam_approaching_message(self):
        messages = build_reason_messages(
            ["exam_approaching"], {"days_until_exam": 15}
        )
        assert any("15 dias" in m for m in messages)


# =============================================================================
# TESTES DE SPACED REPETITION COM MASTERY
# =============================================================================


class TestSpacedRepetitionWithMastery:
    def test_classify_mastery_for_review(self):
        assert classify_mastery_for_review(95) == "high"
        assert classify_mastery_for_review(80) == "medium_high"
        assert classify_mastery_for_review(65) == "medium"
        assert classify_mastery_for_review(45) == "low"
        assert classify_mastery_for_review(20) == "very_low"

    def test_calculate_next_review_from_mastery_high(self):
        today = date.today()
        result = calculate_next_review_from_mastery(95.0)
        delta = (result - today).days
        assert delta >= 20

    def test_calculate_next_review_from_mastery_low(self):
        today = date.today()
        result = calculate_next_review_from_mastery(20.0)
        delta = (result - today).days
        assert delta <= 3

    def test_consecutive_wrong_shortens_interval(self):
        today = date.today()
        normal = calculate_next_review_from_mastery(60.0, consecutive_correct=0, consecutive_wrong=0)
        short = calculate_next_review_from_mastery(60.0, consecutive_correct=0, consecutive_wrong=3)
        assert short <= normal


# =============================================================================
# TESTES DE INTEGRAÇÃO COM BANCO
# =============================================================================


class TestKnowledgeStateIntegration:
    """Testes de integração com banco de dados."""

    def test_update_knowledge_state_creates_new(self, app, user, subject, topic, questions):
        with app.app_context():
            ks = update_knowledge_state(user, topic)
            assert ks is not None
            assert ks.user_id == user
            assert ks.topic_id == topic
            assert ks.subject_id == subject

    def test_update_knowledge_state_with_answers(self, app, user, subject, topic, questions):
        with app.app_context():
            for qid in questions[:7]:
                q = db.session.get(Question, qid)
                attempt = QuestionAttempt(
                    user_id=user,
                    question_id=qid,
                    resposta=q.resposta_correta,
                    correta=True,
                    tempo_segundos=30,
                )
                db.session.add(attempt)
            db.session.commit()

            ks = update_knowledge_state(user, topic)
            assert ks.questions_correct == 7
            assert ks.questions_answered == 7
            assert ks.mastery_score > 0

    def test_knowledge_state_multi_user_isolation(self, app, user, subject, topic, questions):
        with app.app_context():
            user2 = User(nome="User 2", email="user2@test.com")
            user2.set_senha("pass")
            db.session.add(user2)
            db.session.commit()

            subject2 = Subject(
                nome="Historia", cor="#ff0000", user_id=user2.id
            )
            db.session.add(subject2)
            db.session.commit()

            topic2 = Topic(
                nome="Brasil Colonial", subject_id=subject2.id, user_id=user2.id
            )
            db.session.add(topic2)
            db.session.commit()

            for qid in questions[:5]:
                q = db.session.get(Question, qid)
                attempt = QuestionAttempt(
                    user_id=user,
                    question_id=qid,
                    resposta=q.resposta_correta,
                    correta=True,
                )
                db.session.add(attempt)
            db.session.commit()

            ks1 = update_knowledge_state(user, topic)
            ks2 = update_knowledge_state(user2.id, topic2.id)

            assert ks1.user_id == user
            assert ks2.user_id == user2.id
            assert ks1.questions_correct == 5
            assert ks2.questions_correct == 0

    def test_get_user_knowledge_summary(self, app, user, subject, topic, questions):
        with app.app_context():
            update_knowledge_state(user, topic)
            summary = get_user_knowledge_summary(user)
            assert summary["total_topics"] == 1
            assert summary["has_data"] is True
            assert summary["average_mastery"] >= 0

    def test_get_topic_attempt_stats(self, app, user, subject, topic, questions):
        with app.app_context():
            stats = get_topic_attempt_stats(user, topic)
            assert stats["total"] == 0
            assert stats["correct"] == 0

    def test_get_subject_attempt_stats(self, app, user, subject):
        with app.app_context():
            stats = get_subject_attempt_stats(user, subject)
            assert stats["total"] == 0

    def test_empty_topic_stats(self, app, user):
        with app.app_context():
            stats = get_topic_attempt_stats(user, 99999)
            assert stats["total"] == 0


# =============================================================================
# TESTES DE RECOMENDAÇÃO COM BANCO
# =============================================================================


class TestRecommendationIntegration:
    """Testes de integração do recommendation engine."""

    def test_recommend_no_data(self, app, user):
        with app.app_context():
            result = recommend_next_topic(user)
            assert result is None

    def test_recommend_with_knowledge_state(self, app, user, subject, topic, questions):
        with app.app_context():
            for qid in questions[:3]:
                q = db.session.get(Question, qid)
                attempt = QuestionAttempt(
                    user_id=user,
                    question_id=qid,
                    resposta="B",
                    correta=False,
                    tempo_segundos=45,
                )
                db.session.add(attempt)
            db.session.commit()

            update_knowledge_state(user, topic)

            result = recommend_next_topic(user)
            assert result is not None
            assert result["topic_id"] == topic
            assert result["subject_id"] == subject
            assert 0 <= result["need_score"] <= 100
            assert len(result["reason_codes"]) > 0

    def test_recommend_multi_topic_priority(self, app, user, subject):
        with app.app_context():
            topic1 = Topic(nome="Algebra", subject_id=subject, user_id=user)
            topic2 = Topic(nome="Geometria", subject_id=subject, user_id=user)
            db.session.add_all([topic1, topic2])
            db.session.commit()

            q1 = Question(
                enunciado="Q1", alternativa_a="A", alternativa_b="B",
                alternativa_c="C", alternativa_d="D", alternativa_e="E",
                resposta_correta="A", subject_id=subject,
                topic_id=topic1.id, user_id=user, dificuldade=3,
            )
            q2 = Question(
                enunciado="Q2", alternativa_a="A", alternativa_b="B",
                alternativa_c="C", alternativa_d="D", alternativa_e="E",
                resposta_correta="A", subject_id=subject,
                topic_id=topic2.id, user_id=user, dificuldade=3,
            )
            db.session.add_all([q1, q2])
            db.session.commit()

            for _ in range(8):
                attempt = QuestionAttempt(
                    user_id=user, question_id=q1.id,
                    resposta="A", correta=True, tempo_segundos=20,
                )
                db.session.add(attempt)

            for _ in range(8):
                attempt = QuestionAttempt(
                    user_id=user, question_id=q2.id,
                    resposta="B", correta=False, tempo_segundos=40,
                )
                db.session.add(attempt)
            db.session.commit()

            update_knowledge_state(user, topic1.id)
            update_knowledge_state(user, topic2.id)

            result = recommend_next_topic(user)
            assert result is not None
            assert result["topic_id"] == topic2.id


# =============================================================================
# TESTES DE EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Testes para cenários extremos."""

    def test_scenario_a_30_questions_high_accuracy(self):
        result = calculate_mastery(
            questions_correct=27,
            questions_wrong=3,
            questions_answered=30,
            recent_correct=9,
            recent_total=10,
            average_difficulty=4.0,
            consecutive_correct=5,
            consecutive_wrong=0,
        )
        assert result["mastery_score"] >= 75

    def test_scenario_b_30_questions_low_accuracy(self):
        result = calculate_mastery(
            questions_correct=10,
            questions_wrong=20,
            questions_answered=30,
            recent_correct=3,
            recent_total=10,
            average_difficulty=3.0,
            consecutive_correct=0,
            consecutive_wrong=3,
        )
        assert result["mastery_score"] <= 40

    def test_scenario_c_historical_good_recent_bad(self):
        result = calculate_mastery(
            questions_correct=24,
            questions_wrong=6,
            questions_answered=30,
            recent_correct=4,
            recent_total=10,
            consecutive_correct=0,
            consecutive_wrong=2,
        )
        trend = get_trend(result["components"]["recent_performance"], result["components"]["accuracy"])
        assert trend in ("declining", "stable")

    def test_scenario_d_low_mastery_recommends_basic(self):
        study_type = recommend_study_type(35)
        assert study_type == "teoria_exercicios"

    def test_scenario_e_high_mastery_recommends_advanced(self):
        study_type = recommend_study_type(88)
        assert study_type == "questoes_enem_revisao"

    def test_only_easy_questions(self):
        result = calculate_mastery(
            questions_correct=8,
            questions_wrong=2,
            questions_answered=10,
            recent_correct=3,
            recent_total=4,
            average_difficulty=1.0,
        )
        assert 0 <= result["mastery_score"] <= 100

    def test_only_hard_questions(self):
        result = calculate_mastery(
            questions_correct=8,
            questions_wrong=2,
            questions_answered=10,
            recent_correct=3,
            recent_total=4,
            average_difficulty=5.0,
        )
        assert 0 <= result["mastery_score"] <= 100

    def test_one_question_only(self):
        result = calculate_mastery(
            questions_correct=1,
            questions_wrong=0,
            questions_answered=1,
            recent_correct=1,
            recent_total=1,
        )
        assert 0 <= result["mastery_score"] <= 100

    def test_three_questions(self):
        result = calculate_mastery(
            questions_correct=2,
            questions_wrong=1,
            questions_answered=3,
            recent_correct=2,
            recent_total=3,
        )
        assert 0 <= result["mastery_score"] <= 100


# =============================================================================
# TESTES DE PERFORMANCE ROUTES
# =============================================================================


class TestPerformanceRoutes:
    """Testes HTTP para rotas de performance."""

    def _login(self, client, email="test@example.com", password="password123"):
        return client.post(
            "/auth/login",
            data={"email": email, "senha": password},
            follow_redirects=False,
        )

    def test_overview_requires_login(self, client):
        response = client.get("/performance/")
        assert response.status_code == 302

    def test_overview_loads(self, client, user):
        self._login(client)
        response = client.get("/performance/")
        assert response.status_code == 200
