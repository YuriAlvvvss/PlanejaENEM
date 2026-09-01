"""
AI Gateway - PlanejaENEM 5.0.

Camada central para IA generativa.
Fornece client, configuração, schemas, rastreamento de uso
e geração de questões.

REGRA DE OURO: A IA generativa NUNCA é a fonte da verdade.
Banco de dados, estatísticas, regras determinísticas,
KnowledgeState e Decision Engine continuam sendo a fonte da verdade.
A IA apenas gera, explica, resume e personaliza.

Uso:
    from app.ai import AIClient, AIConfig, ChatRequest, Message

    client = AIClient(config, tracker)
    response = client.chat(ChatRequest(
        messages=[Message(role="user", content="Explique equações")]
    ))
"""

from app.ai.client import AIClient
from app.ai.config import AIConfig, load_ai_config
from app.ai.cost_estimator import estimate_cost, estimate_monthly_cost
from app.ai.exceptions import (
    AIDisabledError,
    AIConfigurationError,
    AIError,
    AIProviderError,
    AIRateLimitError,
    AIValidationError,
    AITimeoutError,
)
from app.ai.explanation_generator import (
    ExplanationGenerator,
    ExplanationInput,
    ExplanationOutput,
)
from app.ai.feedback_generator import (
    FeedbackGenerator,
    FeedbackOutput,
    PerformanceData,
)
from app.ai.models import AIUsage
from app.ai.output_validator import (
    OutputValidationResult,
    sanitize_output,
    validate_explanation_output,
    validate_feedback_output,
    validate_question_output,
    validate_review_output,
    validate_text_output,
)
from app.ai.question_generator import (
    GeneratedQuestion,
    QuestionGenerator,
    QuestionGeneratorConfig,
)
from app.ai.prompts import PROMPT_VERSION
from app.ai.rate_limiter import AIRateLimiter
from app.ai.review_generator import (
    ReviewGenerator,
    ReviewInput,
    ReviewOutput,
)
from app.ai.sanitizer import (
    build_safe_prompt,
    get_injection_details,
    has_injection_attempt,
    sanitize_user_content,
)
from app.ai.schemas import (
    ChatRequest,
    ChatResponse,
    Message,
    StructuredChatResponse,
    UsageInfo,
)
from app.ai.usage import UsageTracker
from app.ai.validators import ValidationResult, validate_question, validate_question_batch, sanitize_question

__all__ = [
    "AIClient",
    "AIConfig",
    "AIDisabledError",
    "AIConfigurationError",
    "AIError",
    "AIProviderError",
    "AIRateLimitError",
    "AIValidationError",
    "AITimeoutError",
    "AIUsage",
    "AIRateLimiter",
    "ChatRequest",
    "ChatResponse",
    "ExplanationGenerator",
    "ExplanationInput",
    "ExplanationOutput",
    "FeedbackGenerator",
    "FeedbackOutput",
    "GeneratedQuestion",
    "Message",
    "OutputValidationResult",
    "PROMPT_VERSION",
    "PerformanceData",
    "QuestionGenerator",
    "QuestionGeneratorConfig",
    "ReviewGenerator",
    "ReviewInput",
    "ReviewOutput",
    "StructuredChatResponse",
    "UsageInfo",
    "UsageTracker",
    "ValidationResult",
    "build_safe_prompt",
    "estimate_cost",
    "estimate_monthly_cost",
    "get_injection_details",
    "has_injection_attempt",
    "load_ai_config",
    "sanitize_output",
    "sanitize_question",
    "sanitize_user_content",
    "validate_explanation_output",
    "validate_feedback_output",
    "validate_question",
    "validate_question_batch",
    "validate_question_output",
    "validate_review_output",
    "validate_text_output",
]
