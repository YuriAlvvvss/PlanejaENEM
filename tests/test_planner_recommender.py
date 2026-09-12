from unittest.mock import MagicMock

from app.ai.planner_recommender import (
    PlannerRecommendationInput,
    PlannerRecommender,
)


def _input():
    return PlannerRecommendationInput(
        subjects=[
            {"name": "Matemática", "performance": "low"},
            {"name": "História", "performance": "good"},
        ],
        days_until_exam=20,
    )


def test_disabled_ai_uses_deterministic_guidance():
    client = MagicMock(enabled=False)

    guidance = PlannerRecommender(client).generate(_input())

    assert guidance.study_types["Matemática"] == "teoria"
    assert guidance.study_types["História"] == "questoes_enem"
    client.chat_structured.assert_not_called()


def test_ai_guidance_discards_unknown_subjects_and_types():
    client = MagicMock(enabled=True)
    response = MagicMock()
    response.data = {
        "recommendations": [
            {"subject": "Matemática", "study_type": "revisao"},
            {"subject": "Inexistente", "study_type": "teoria"},
            {"subject": "História", "study_type": "nao_permitido"},
        ],
        "reason": "Foco nos pontos de atenção.",
    }
    response.model = "test-model"
    client.chat_structured.return_value = response

    guidance = PlannerRecommender(client).generate(_input())

    assert guidance.study_types == {"Matemática": "revisao"}
