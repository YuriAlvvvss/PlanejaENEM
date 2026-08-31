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
from app.ai.exceptions import (
    AIDisabledError,
    AIConfigurationError,
    AIError,
    AIProviderError,
    AIRateLimitError,
    AIValidationError,
    AITimeoutError,
)
from app.ai.question_generator import (
    GeneratedQuestion,
    QuestionGenerator,
    QuestionGeneratorConfig,
)
from app.ai.prompts import PROMPT_VERSION
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
    "ChatRequest",
    "ChatResponse",
    "GeneratedQuestion",
    "Message",
    "PROMPT_VERSION",
    "QuestionGenerator",
    "QuestionGeneratorConfig",
    "StructuredChatResponse",
    "UsageInfo",
    "UsageTracker",
    "ValidationResult",
    "load_ai_config",
    "sanitize_question",
    "validate_question",
    "validate_question_batch",
]
