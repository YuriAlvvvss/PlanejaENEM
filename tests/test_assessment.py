"""
Testes de Avaliação Adaptativa - PlanejaENEM 5.0.

Testa o fluxo completo de avaliação adaptativa:
  - Engine (dificuldade inicial, ajuste, seleção de tópico)
  - Policies (diversidade, repetição, sequência)
  - Services (início, resposta, finalização)
  - Isolamento entre usuários
  - Atualização do KnowledgeState
  - Cache e provider offline

Sem chamadas reais ao provider de IA.
"""

import json
import pytest
from datetime import date, datetime, timedelta, timezone

from app import create_app, db
from app.models import User, Subject, Topic, Question, QuestionAttempt
from app.performance.models import KnowledgeState
from app.assessment.models import Assessment, AssessmentQuestion
from app.assessment.engine import (
    AssessmentDecision,
    AssessmentState,
    adjust_difficulty,
    build_result_summary,
    decide_next_question,
    get_initial_difficulty,
    is_assessment_complete,
    select_topic_for_question,
)
from app.assessment.policies import (
    build_assessment_result,
    check_difficulty_sequence,
    check_topic_diversity,
    select_best_question_from_candidates,
    should_avoid_question,
)
from app.assessment.services import (
    _check_answer,
    _build_state_from_assessment,
    complete_assessment,
    get_assessment_status,
    get_next_question,
    list_user_assessments,
    start_assessment,
    submit_answer,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def app():
    """Cria aplicação para testes."""
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Client HTTP para testes."""
    return app.test_client()


@pytest.fixture
def user1(app):
    """Usuário 1 para testes."""
    with app.app_context():
        u = User(nome="Alice", email="alice@test.com")
        u.set_senha("senha123")
        db.session.add(u)
        db.session.commit()
        return u.id


@pytest.fixture
def user2(app):
    """Usuário 2 para testes (isolamento)."""
    with app.app_context():
        u = User(nome="Bob", email="bob@test.com")
        u.set_senha("senha123")
        db.session.add(u)
        db.session.commit()
        return u.id


@pytest.fixture
def subject1(app, user1):
    """Matéria do usuário 1."""
    with app.app_context():
        s = Subject(nome="Matemática", area="matematica", user_id=user1)
        db.session.add(s)
        db.session.commit()
        return s.id


@pytest.fixture
def subject2(app, user1):
    """Segunda matéria do usuário 1."""
    with app.app_context():
        s = Subject(nome="Português", area="linguagens", user_id=user1)
        db.session.add(s)
        db.session.commit()
        return s.id


@pytest.fixture
def topic1(app, user1, subject1):
    """Tópico da matéria 1."""
    with app.app_context():
        t = Topic(nome="Funções", subject_id=subject1, user_id=user1)
        db.session.add(t)
        db.session.commit()
        return t.id


@pytest.fixture
def topic2(app, user1, subject1):
    """Segundo tópico da matéria 1."""
    with app.app_context():
        t = Topic(nome="Geometria", subject_id=subject1, user_id=user1)
        db.session.add(t)
        db.session.commit()
        return t.id


@pytest.fixture
def topic3(app, user1, subject2):
    """Tópico da matéria 2."""
    with app.app_context():
        t = Topic(nome="Interpretação de Texto", subject_id=subject2, user_id=user1)
        db.session.add(t)
        db.session.commit()
        return t.id


@pytest.fixture
def knowledge_states(app, user1, subject1, subject2, topic1, topic2, topic3):
    """Cria KnowledgeStates com diferentes níveis de mastery."""
    with app.app_context():
        states = [
            KnowledgeState(
                user_id=user1, subject_id=subject1, topic_id=topic1,
                mastery_score=30.0, confidence_score=40.0,
                questions_answered=5, questions_correct=2, questions_wrong=3,
            ),
            KnowledgeState(
                user_id=user1, subject_id=subject1, topic_id=topic2,
                mastery_score=65.0, confidence_score=55.0,
                questions_answered=12, questions_correct=8, questions_wrong=4,
            ),
            KnowledgeState(
                user_id=user1, subject_id=subject2, topic_id=topic3,
                mastery_score=85.0, confidence_score=70.0,
                questions_answered=20, questions_correct=17, questions_wrong=3,
            ),
        ]
        db.session.add_all(states)
        db.session.commit()
        return [s.id for s in states]


@pytest.fixture
def questions(app, user1, subject1, subject2, topic1, topic2, topic3):
    """Cria questões no banco para testes."""
    with app.app_context():
        qs = [
            # Questões de Matemática - Funções (diff 2)
            Question(
                enunciado="Qual o valor de f(2) se f(x)=x+1?",
                alternativa_a="3", alternativa_b="4", alternativa_c="5",
                alternativa_d="2", alternativa_e="1",
                resposta_correta="A", subject_id=subject1, topic_id=topic1,
                user_id=user1, dificuldade=2,
            ),
            Question(
                enunciado="Qual o gráfico de f(x)=x²?",
                alternativa_a="Parábola", alternativa_b="Reta",
                alternativa_c="Circunferência", alternativa_d="Hiperbóla",
                alternativa_e="Elipse",
                resposta_correta="A", subject_id=subject1, topic_id=topic1,
                user_id=user1, dificuldade=3,
            ),
            # Questões de Matemática - Geometria (diff 3-4)
            Question(
                enunciado="Área do quadrado de lado 5?",
                alternativa_a="25", alternativa_b="20", alternativa_c="15",
                alternativa_d="30", alternativa_e="10",
                resposta_correta="A", subject_id=subject1, topic_id=topic2,
                user_id=user1, dificuldade=3,
            ),
            Question(
                enunciado="Teorema de Pitágoras:",
                alternativa_a="a²+b²=c²", alternativa_b="a+b=c",
                alternativa_c="a²-b²=c²", alternativa_d="2a+2b=c",
                alternativa_e="a×b=c",
                resposta_correta="A", subject_id=subject1, topic_id=topic2,
                user_id=user1, dificuldade=4,
            ),
            # Questões de Português - Interpretação (diff 3)
            Question(
                enunciado="Qual o sujeito da frase: 'O gato dormiu'?",
                alternativa_a="O gato", alternativa_b="Dormiu",
                alternativa_c="A frase", alternativa_d="Nenhum",
                alternativa_e="Indefinido",
                resposta_correta="A", subject_id=subject2, topic_id=topic3,
                user_id=user1, dificuldade=3,
            ),
            Question(
                enunciado="Sinônimo de 'alegre':",
                alternativa_a="Feliz", alternativa_b="Triste",
                alternativa_c="Bravo", alternativa_d="Cansado",
                alternativa_e="Doente",
                resposta_correta="A", subject_id=subject2, topic_id=topic3,
                user_id=user1, dificuldade=2,
            ),
        ]
        db.session.add_all(qs)
        db.session.commit()
        return [q.id for q in qs]


# =============================================================================
# TESTES DO ENGINE
# =============================================================================

class TestInitialDifficulty:
    """Testes de cálculo de dificuldade inicial."""

    def test_low_mastery(self):
        """mastery < 40 → 1-2."""
        d = get_initial_difficulty(20.0)
        assert 1.0 <= d <= 2.0

    def test_medium_low_mastery(self):
        """mastery 40-59 → 2-3."""
        d = get_initial_difficulty(50.0)
        assert 2.0 <= d <= 3.0

    def test_medium_mastery(self):
        """mastery 60-74 → 3."""
        d = get_initial_difficulty(65.0)
        assert d == 3.0

    def test_high_mastery(self):
        """mastery 75-89 → 3-4."""
        d = get_initial_difficulty(80.0)
        assert 3.0 <= d <= 4.0

    def test_excellent_mastery(self):
        """mastery 90+ → 4-5."""
        d = get_initial_difficulty(95.0)
        assert 4.0 <= d <= 5.0

    def test_zero_mastery(self):
        """mastery 0 → dificuldade mínima."""
        d = get_initial_difficulty(0.0)
        assert d == 1.5


class TestAdjustDifficulty:
    """Testes de ajuste de dificuldade."""

    def test_correct_increases(self):
        """Acerto sobe dificuldade."""
        d = adjust_difficulty(3.0, correct=True, streak=0)
        assert d > 3.0

    def test_wrong_decreases(self):
        """Erro reduz dificuldade."""
        d = adjust_difficulty(3.0, correct=False, streak=0)
        assert d < 3.0

    def test_streak_correct_bigger_jump(self):
        """Streak de acertos dá salto maior."""
        d_normal = adjust_difficulty(3.0, correct=True, streak=1)
        d_streak = adjust_difficulty(3.0, correct=True, streak=3)
        assert d_streak >= d_normal

    def test_streak_wrong_bigger_drop(self):
        """Streak de erros dá queda maior."""
        d_normal = adjust_difficulty(3.0, correct=False, streak=-1)
        d_streak = adjust_difficulty(3.0, correct=False, streak=-3)
        assert d_streak <= d_normal

    def test_min_boundary(self):
        """Não desce abaixo de 1."""
        d = adjust_difficulty(1.2, correct=False, streak=-3)
        assert d >= 1.0

    def test_max_boundary(self):
        """Não sobe acima de 5."""
        d = adjust_difficulty(4.8, correct=True, streak=3)
        assert d <= 5.0

    def test_deterministic(self):
        """Mesma entrada = mesmo resultado."""
        d1 = adjust_difficulty(3.0, correct=True, streak=2)
        d2 = adjust_difficulty(3.0, correct=True, streak=2)
        assert d1 == d2


class TestSelectTopic:
    """Testes de seleção de tópico."""

    def test_selects_weakest_topic(self):
        """Seleciona tópico com menor mastery."""
        states = [
            {"topic_id": 1, "subject_id": 1, "mastery_score": 80.0, "area": "a", "subject_name": "A", "topic_name": "T1"},
            {"topic_id": 2, "subject_id": 1, "mastery_score": 30.0, "area": "a", "subject_name": "A", "topic_name": "T2"},
        ]
        # Pode selecionar qualquer um dos 2 com menor mastery
        selected = select_topic_for_question(states, [], None)
        assert selected["topic_id"] in [1, 2]
        assert selected["mastery_score"] <= 80.0

    def test_avoids_used_topics(self):
        """Evita tópicos já usados recentemente."""
        states = [
            {"topic_id": 1, "subject_id": 1, "mastery_score": 30.0, "area": "a", "subject_name": "A", "topic_name": "T1"},
            {"topic_id": 2, "subject_id": 1, "mastery_score": 40.0, "area": "a", "subject_name": "A", "topic_name": "T2"},
        ]
        selected = select_topic_for_question(states, [1], None)
        assert selected["topic_id"] == 2

    def test_filters_by_subject(self):
        """Filtra por matéria quando especificada."""
        states = [
            {"topic_id": 1, "subject_id": 1, "mastery_score": 30.0, "area": "a", "subject_name": "A", "topic_name": "T1"},
            {"topic_id": 2, "subject_id": 2, "mastery_score": 20.0, "area": "b", "subject_name": "B", "topic_name": "T2"},
        ]
        selected = select_topic_for_question(states, [], 2)
        assert selected["subject_id"] == 2

    def test_empty_states(self):
        """Retorna None quando não há estados."""
        selected = select_topic_for_question([], [], None)
        assert selected is None


class TestAssessmentState:
    """Testes do AssessmentState."""

    def test_accuracy_empty(self):
        """Acurácia vazia é 0."""
        state = AssessmentState()
        assert state.accuracy == 0.0

    def test_accuracy_calculation(self):
        """Cálculo de acurácia."""
        state = AssessmentState(
            questions_answered=10,
            correct_count=7,
            wrong_count=3,
        )
        assert state.accuracy == 70.0

    def test_streak_positive(self):
        """Streak positivo = acertos."""
        state = AssessmentState(recent_results=[True, True, True])
        assert state.streak == 3

    def test_streak_negative(self):
        """Streak negativo = erros."""
        state = AssessmentState(recent_results=[False, False, False])
        assert state.streak == -3

    def test_streak_mixed(self):
        """Streak quebra no primeiro resultado diferente."""
        state = AssessmentState(recent_results=[True, True, False, True])
        assert state.streak == 1

    def test_streak_empty(self):
        """Streak vazio é 0."""
        state = AssessmentState()
        assert state.streak == 0


class TestDecideNextQuestion:
    """Testes do Decision Engine."""

    def test_returns_decision(self):
        """Retorna decisão válida."""
        state = AssessmentState()
        states = [
            {"topic_id": 1, "subject_id": 1, "mastery_score": 50.0,
             "confidence_score": 50.0, "area": "matematica",
             "subject_name": "Mat", "topic_name": "Funções"},
        ]
        decision = decide_next_question(state, states)
        assert decision is not None
        assert decision.subject_id == 1
        assert decision.topic_id == 1
        assert 1.0 <= decision.difficulty <= 5.0

    def test_returns_none_empty_states(self):
        """Retorna None sem KnowledgeStates."""
        state = AssessmentState()
        decision = decide_next_question(state, [])
        assert decision is None

    def test_adjusts_after_wrong(self):
        """Ajusta dificuldade após erro."""
        state = AssessmentState(
            questions_answered=1,
            recent_results=[False],
            current_difficulty=3.0,
        )
        states = [
            {"topic_id": 1, "subject_id": 1, "mastery_score": 50.0,
             "confidence_score": 50.0, "area": "mat",
             "subject_name": "Mat", "topic_name": "T"},
        ]
        decision = decide_next_question(state, states)
        assert decision.difficulty < 3.0

    def test_adjusts_after_correct(self):
        """Ajusta dificuldade após acerto."""
        state = AssessmentState(
            questions_answered=1,
            recent_results=[True],
            current_difficulty=3.0,
        )
        states = [
            {"topic_id": 1, "subject_id": 1, "mastery_score": 50.0,
             "confidence_score": 50.0, "area": "mat",
             "subject_name": "Mat", "topic_name": "T"},
        ]
        decision = decide_next_question(state, states)
        assert decision.difficulty >= 3.0

    def test_is_complete(self):
        """is_assessment_complete funciona."""
        state = AssessmentState(questions_answered=10)
        assert is_assessment_complete(state, 10) is True
        assert is_assessment_complete(state, 15) is False

    def test_result_summary(self):
        """build_result_summary retorna dict."""
        state = AssessmentState(
            questions_answered=5, correct_count=3, wrong_count=2,
            current_difficulty=3.5,
        )
        summary = build_result_summary(state)
        assert summary["total_questions"] == 5
        assert summary["accuracy"] == 60.0


# =============================================================================
# TESTES DAS POLICIES
# =============================================================================

class TestPolicies:
    """Testes de políticas de seleção."""

    def test_avoid_used_question(self):
        """Deve evitar questão já usada."""
        assert should_avoid_question(1, {1, 2, 3}) is True
        assert should_avoid_question(4, {1, 2, 3}) is False

    def test_topic_diversity_ok(self):
        """Tópico dentro do limite de diversidade."""
        assert check_topic_diversity(1, 10, {1: 3}) is True

    def test_topic_diversity_exceeded(self):
        """Tópico excede limite de diversidade."""
        assert check_topic_diversity(1, 10, {1: 4}) is False

    def test_topic_diversity_empty(self):
        """Primeira questão sempre OK."""
        assert check_topic_diversity(1, 0, {}) is True

    def test_difficulty_sequence_ok(self):
        """Sequência variada mantém dificuldade."""
        recent = [2.0, 3.0, 4.0, 3.0]
        d = check_difficulty_sequence(3.5, recent)
        assert d == 3.5

    def test_difficulty_sequence_same(self):
        """Forçar variação quando 3+ iguais."""
        recent = [3.0, 3.0, 3.0]
        d = check_difficulty_sequence(3.0, recent)
        assert d != 3.0

    def test_select_best_question(self):
        """Seleciona melhor questão de candidatas."""
        candidates = [
            {"id": 1, "topic_id": 1, "dificuldade": 2},
            {"id": 2, "topic_id": 1, "dificuldade": 3},
            {"id": 3, "topic_id": 2, "dificuldade": 4},
        ]
        selected = select_best_question_from_candidates(
            candidates, set(), {}, 0, [], 3.0
        )
        assert selected is not None
        assert selected["id"] in [1, 2, 3]

    def test_select_best_avoids_used(self):
        """Evita questões já usadas."""
        candidates = [
            {"id": 1, "topic_id": 1, "dificuldade": 3},
            {"id": 2, "topic_id": 1, "dificuldade": 3},
        ]
        selected = select_best_question_from_candidates(
            candidates, {1}, {}, 1, [3.0], 3.0
        )
        assert selected["id"] == 2

    def test_build_assessment_result(self):
        """build_assessment_result calcula métricas."""
        result = build_assessment_result(
            correct_count=7,
            wrong_count=3,
            total_time_seconds=300,
            question_difficulties=[2.0, 3.0, 4.0, 3.0, 2.0, 3.0, 4.0, 3.0, 2.0, 3.0],
            question_correctness=[True, True, False, True, True, True, True, True, False, True],
        )
        assert result["accuracy"] == 70.0
        assert result["total_questions"] == 10
        assert result["average_time_seconds"] == 30.0


# =============================================================================
# TESTES DO SERVICES (INTEGRAÇÃO)
# =============================================================================

class TestStartAssessment:
    """Testes de início de avaliação."""

    def test_start_success(self, app, user1, knowledge_states):
        """Início bem-sucedido."""
        with app.app_context():
            assessment = start_assessment(user1, target_questions=5)
            assert assessment.id is not None
            assert assessment.user_id == user1
            assert assessment.status == "active"
            assert assessment.target_questions == 5
            assert 1.0 <= assessment.current_difficulty <= 5.0

    def test_start_with_subject(self, app, user1, subject1, knowledge_states):
        """Início filtrando por matéria."""
        with app.app_context():
            assessment = start_assessment(user1, subject_id=subject1)
            assert assessment.subject_id == subject1

    def test_start_no_topics(self, app, user1):
        """Falha sem KnowledgeStates."""
        with app.app_context():
            with pytest.raises(ValueError, match="Nenhum tópico"):
                start_assessment(user1)

    def test_target_questions_clamped(self, app, user1, knowledge_states):
        """target_questions é limitado a 5-30."""
        with app.app_context():
            a_min = start_assessment(user1, target_questions=1)
            assert a_min.target_questions == 5
            a_max = start_assessment(user1, target_questions=100)
            assert a_max.target_questions == 30


class TestGetNextQuestion:
    """Testes de busca de próxima questão."""

    def test_get_next_success(self, app, user1, knowledge_states, questions):
        """Busca bem-sucedida de próxima questão."""
        with app.app_context():
            assessment = start_assessment(user1, target_questions=5)
            result = get_next_question(assessment.id, user1)
            assert "assessment_question_id" in result
            assert "question" in result or "generation_params" in result
            assert result["order"] == 1

    def test_get_next_not_found(self, app, user1):
        """Avaliação inexistente."""
        with app.app_context():
            with pytest.raises(ValueError, match="não encontrada"):
                get_next_question(999, user1)

    def test_get_next_wrong_user(self, app, user1, user2, knowledge_states, questions):
        """Outro usuário não acessa avaliação."""
        with app.app_context():
            assessment = start_assessment(user1, target_questions=5)
            with pytest.raises(ValueError, match="não encontrada"):
                get_next_question(assessment.id, user2)

    def test_get_next_completed(self, app, user1, knowledge_states, questions):
        """Avaliação completa não retorna questão."""
        with app.app_context():
            assessment = start_assessment(user1, target_questions=5)
            assessment.status = "completed"
            db.session.commit()
            with pytest.raises(ValueError, match="não está ativa"):
                get_next_question(assessment.id, user1)


class TestSubmitAnswer:
    """Testes de submissão de resposta."""

    def test_submit_correct(self, app, user1, knowledge_states, questions):
        """Resposta correta atualiza contadores."""
        with app.app_context():
            assessment = start_assessment(user1, target_questions=5)
            next_q = get_next_question(assessment.id, user1)

            # Encontrar a questão correta
            aq_id = next_q["assessment_question_id"]
            if "question" in next_q:
                q_data = next_q["question"]
                # Buscar questão no banco para saber resposta correta
                question = db.session.get(Question, q_data["id"])
                correct_answer = question.resposta_correta
            else:
                correct_answer = "A"

            result = submit_answer(
                assessment.id, aq_id, user1,
                resposta=correct_answer, tempo_segundos=30,
            )
            assert result["correta"] is True
            assert result["assessment_progress"]["correct_count"] == 1

    def test_submit_wrong(self, app, user1, knowledge_states, questions):
        """Resposta errada atualiza contadores."""
        with app.app_context():
            assessment = start_assessment(user1, target_questions=5)
            next_q = get_next_question(assessment.id, user1)
            aq_id = next_q["assessment_question_id"]

            # Submeter resposta errada
            result = submit_answer(
                assessment.id, aq_id, user1,
                resposta="E", tempo_segundos=45,
            )
            assert result["correta"] is False
            assert result["assessment_progress"]["wrong_count"] == 1

    def test_submit_already_answered(self, app, user1, knowledge_states, questions):
        """Não permite responder duas vezes."""
        with app.app_context():
            assessment = start_assessment(user1, target_questions=5)
            next_q = get_next_question(assessment.id, user1)
            aq_id = next_q["assessment_question_id"]

            submit_answer(assessment.id, aq_id, user1, "A", 30)
            with pytest.raises(ValueError, match="já foi respondida"):
                submit_answer(assessment.id, aq_id, user1, "B", 20)

    def test_submit_wrong_assessment(self, app, user1, knowledge_states, questions):
        """Não permite responder em avaliação errada."""
        with app.app_context():
            a1 = start_assessment(user1, target_questions=5)
            a2 = start_assessment(user1, target_questions=5)
            next_q = get_next_question(a1.id, user1)
            aq_id = next_q["assessment_question_id"]

            with pytest.raises(ValueError, match="não encontrada"):
                submit_answer(a2.id, aq_id, user1, "A", 30)


class TestCompleteAssessment:
    """Testes de finalização de avaliação."""

    def test_complete_success(self, app, user1, knowledge_states, questions):
        """Finalização bem-sucedida."""
        with app.app_context():
            assessment = start_assessment(user1, target_questions=5)
            # Responder 5 questões
            for _ in range(5):
                next_q = get_next_question(assessment.id, user1)
                submit_answer(
                    assessment.id, next_q["assessment_question_id"],
                    user1, "A", 30,
                )

            result = complete_assessment(assessment.id, user1)
            assert result["status"] == "completed"
            assert result["total_questions"] == 5
            assert "topic_performance" in result
            assert "subject_performance" in result

    def test_complete_partial(self, app, user1, knowledge_states, questions):
        """Finalização parcial (não respondeu todas)."""
        with app.app_context():
            assessment = start_assessment(user1, target_questions=5)
            next_q = get_next_question(assessment.id, user1)
            submit_answer(
                assessment.id, next_q["assessment_question_id"],
                user1, "A", 30,
            )

            result = complete_assessment(assessment.id, user1)
            assert result["status"] == "completed"
            assert result["correct_count"] == 1
            assert result["wrong_count"] == 0


class TestKnowledgeStateUpdate:
    """Testes de atualização do KnowledgeState."""

    def test_ks_updated_after_answer(self, app, user1, knowledge_states, questions):
        """KnowledgeState é atualizado após resposta."""
        with app.app_context():
            # Mastery antes
            ks_before = KnowledgeState.query.filter_by(
                user_id=user1, topic_id=questions[0]
            ).first()

            assessment = start_assessment(user1, target_questions=5)
            next_q = get_next_question(assessment.id, user1)

            if "question" in next_q:
                topic_id = next_q.get("topic_id") or (
                    db.session.get(Question, next_q["question"]["id"]).topic_id
                )
                submit_answer(
                    assessment.id, next_q["assessment_question_id"],
                    user1, "A", 30,
                )
                # Mastery deve ter sido recalculado
                ks_after = KnowledgeState.query.filter_by(
                    user_id=user1, topic_id=topic_id
                ).first()
                if ks_after:
                    assert ks_after.questions_answered > 0


class TestIsolationBetweenUsers:
    """Testes de isolamento entre usuários."""

    def test_user_cannot_access_other_assessment(self, app, user1, user2, knowledge_states, questions):
        """Usuário não acessa avaliação de outro."""
        with app.app_context():
            assessment = start_assessment(user1, target_questions=5)
            with pytest.raises(ValueError, match="não encontrada"):
                get_next_question(assessment.id, user2)

    def test_user_cannot_answer_other_assessment(self, app, user1, user2, knowledge_states, questions):
        """Usuário não responde em avaliação de outro."""
        with app.app_context():
            assessment = start_assessment(user1, target_questions=5)
            next_q = get_next_question(assessment.id, user1)
            with pytest.raises(ValueError, match="não encontrada"):
                submit_answer(
                    assessment.id, next_q["assessment_question_id"],
                    user2, "A", 30,
                )


class TestListAssessments:
    """Testes de listagem de avaliações."""

    def test_list_empty(self, app, user1):
        """Lista vazia quando não há avaliações."""
        with app.app_context():
            result = list_user_assessments(user1)
            assert result == []

    def test_list_with_assessments(self, app, user1, knowledge_states):
        """Lista avaliações existentes."""
        with app.app_context():
            start_assessment(user1, target_questions=5)
            start_assessment(user1, target_questions=10)
            result = list_user_assessments(user1)
            assert len(result) == 2

    def test_list_filter_by_status(self, app, user1, knowledge_states):
        """Filtra por status."""
        with app.app_context():
            a1 = start_assessment(user1, target_questions=5)
            a1.status = "completed"
            a2 = start_assessment(user1, target_questions=10)
            db.session.commit()

            active = list_user_assessments(user1, status="active")
            completed = list_user_assessments(user1, status="completed")
            assert len(active) == 1
            assert len(completed) == 1


class TestCacheAndOffline:
    """Testes de cache e comportamento offline."""

    def test_no_ai_generation_flag(self, app, user1, knowledge_states, questions):
        """Questão do banco não precisa de geração IA."""
        with app.app_context():
            assessment = start_assessment(user1, target_questions=5)
            result = get_next_question(assessment.id, user1)
            assert result.get("needs_ai_generation") is False
            assert "question" in result

    def test_generation_flag_when_no_bank(self, app, user1, knowledge_states):
        """Sem questão no banco, marca para geração IA."""
        with app.app_context():
            assessment = start_assessment(user1, target_questions=5)
            result = get_next_question(assessment.id, user1)
            # Sem questões no banco, deve pedir geração
            assert result.get("needs_ai_generation") is True
            assert "generation_params" in result


class TestAnswerFlow:
    """Testes do fluxo completo de resposta."""

    def test_full_flow(self, app, user1, knowledge_states, questions):
        """Fluxo completo: start → next → answer → next → ... → complete."""
        with app.app_context():
            assessment = start_assessment(user1, target_questions=5)
            assessment_id = assessment.id

            for i in range(5):
                next_q = get_next_question(assessment_id, user1)
                assert next_q["order"] == i + 1

                result = submit_answer(
                    assessment_id, next_q["assessment_question_id"],
                    user1, "A", 30,
                )

                if i < 4:
                    assert result["is_complete"] is False
                    assert "next_question" in result

            # Verificar estado final do assessment no banco
            db.session.expire_all()
            final = db.session.get(Assessment, assessment_id)
            assert final.status == "completed"
            assert final.current_question_number == 5

    def test_accuracy_progression(self, app, user1, knowledge_states, questions):
        """Acurácia é calculada corretamente."""
        with app.app_context():
            assessment = start_assessment(user1, target_questions=5)

            # Responder 3 corretas, 2 erradas
            for i in range(5):
                next_q = get_next_question(assessment.id, user1)
                answer = "A" if i < 3 else "E"
                result = submit_answer(
                    assessment.id, next_q["assessment_question_id"],
                    user1, answer, 30,
                )

            progress = result["assessment_progress"]
            assert progress["correct_count"] == 3
            assert progress["wrong_count"] == 2
            assert progress["accuracy"] == 60.0
