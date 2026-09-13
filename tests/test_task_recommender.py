from app.ai.schemas import StructuredChatResponse, UsageInfo
from app.ai.task_recommender import TaskRecommendationInput, TaskRecommender


class WrongSubjectClient:
    enabled = True

    def chat_structured(self, request, expected_keys, feature):
        return StructuredChatResponse(
            data={
                "title": "Revisar História",
                "description": "Resolver questões de História.",
                "subject": "História",
                "study_type": "questoes",
                "duration_minutes": 30,
                "reason": "Prática guiada.",
            },
            raw_content="",
            model="test-model",
            usage=UsageInfo(),
            latency_ms=0,
        )


def test_recommender_fallback_respects_target_subject():
    recommender = TaskRecommender(WrongSubjectClient())
    recommendation = recommender.generate(
        TaskRecommendationInput(
            subjects=["Matemática", "História"],
            weak_subjects=[],
            pending_tasks=[],
            available_minutes=30,
            target_subject="Matemática",
        )
    )

    assert recommendation.subject == "Matemática"