"""
Validação de output da IA - PlanejaENEM 5.0.

Valida todas as respostas da IA antes de salvar, renderizar ou enviar.
Nunca executa output como código.

REGRA DE OURO: A IA é falível. Validação é mandatória.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

_MAX_TEXT_LENGTH = 5000
_MAX_ALTERNATIVE_LENGTH = 500
_MAX_EXPLANATION_LENGTH = 2000

_DANGEROUS_PATTERNS = [
    r"<script",
    r"<iframe",
    r"<object",
    r"<embed",
    r"<svg",
    r"javascript:",
    r"data:text/html",
    r"on\w+\s*=",
    r"eval\s*\(",
    r"exec\s*\(",
    r"__import__",
    r"subprocess",
    r"os\.system",
    r"import\s+os",
    r"import\s+sys",
    r"from\s+os",
    r"from\s+sys",
]

_TRUSTED_URL_DOMAINS = [
    "planejaenem.com.br",
    "openrouter.ai",
]

_UNTRUSTED_URL_PATTERNS = [
    r"(?i)javascript:",
    r"(?i)data:text/html",
    r"(?i)vbscript:",
]


@dataclass
class OutputValidationResult:
    """Resultado de validação de output."""

    is_safe: bool
    errors: list[str]
    sanitized_text: str

    def __bool__(self) -> bool:
        return self.is_safe


def _contains_dangerous_content(text: str) -> list[str]:
    """Verifica se texto contém padrões perigosos."""
    errors = []
    for pattern in _DANGEROUS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            errors.append(f"Conteúdo potencialmente perigoso detectado: padrão '{pattern}'")
    return errors


def _has_untrusted_urls(text: str) -> list[str]:
    """Verifica se texto contém URLs não confiáveis."""
    errors = []
    url_pattern = r"https?://[^\s<>\"']+"
    urls = re.findall(url_pattern, text)

    for url in urls:
        is_untrusted = any(
            re.search(pattern, url, re.IGNORECASE)
            for pattern in _UNTRUSTED_URL_PATTERNS
        )
        if is_untrusted:
            errors.append(f"URL potencialmente perigosa: {url[:100]}")

    return errors


def _strip_dangerous_html(text: str) -> str:
    """Remove HTML perigoso do texto."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<iframe[^>]*>.*?</iframe>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<object[^>]*>.*?</object>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<embed[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<svg[^>]*>.*?</svg>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"on\w+\s*=\s*\"[^\"]*\"", "", text, flags=re.IGNORECASE)
    text = re.sub(r"on\w+\s*=\s*'[^']*'", "", text, flags=re.IGNORECASE)
    return text


def _normalize_text(text: str) -> str:
    """Normaliza texto."""
    text = html.unescape(text)
    text = _strip_dangerous_html(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def validate_text_output(
    text: str,
    max_length: int = _MAX_TEXT_LENGTH,
    field_name: str = "output",
) -> OutputValidationResult:
    """
    Valida e sanitiza um campo de texto da resposta da IA.

    Args:
        text: Texto a validar.
        max_length: Tamanho máximo permitido.
        field_name: Nome do campo (para mensagens de erro).

    Returns:
        OutputValidationResult com is_safe, errors e sanitized_text.
    """
    if not text:
        return OutputValidationResult(
            is_safe=True, errors=[], sanitized_text=""
        )

    text = str(text)
    errors = []

    # Verifica conteúdo perigoso
    dangerous = _contains_dangerous_content(text)
    errors.extend(dangerous)

    # Verifica URLs não confiáveis
    url_errors = _has_untrusted_urls(text)
    errors.extend(url_errors)

    # Sanitiza
    sanitized = _normalize_text(text)

    # Limita tamanho
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
        errors.append(
            f"Campo '{field_name}' truncado de {len(text)} para {max_length} caracteres"
        )

    is_safe = len(dangerous) == 0 and len(url_errors) == 0

    return OutputValidationResult(
        is_safe=is_safe,
        errors=errors,
        sanitized_text=sanitized,
    )


def validate_question_output(data: dict) -> OutputValidationResult:
    """
    Valida output de uma questão gerada pela IA.

    Args:
        data: Dicionário com dados da questão.

    Returns:
        OutputValidationResult.
    """
    errors = []

    required_fields = [
        "statement", "alternative_a", "alternative_b", "alternative_c",
        "alternative_d", "alternative_e", "correct_answer", "explanation",
        "difficulty", "topic",
    ]

    missing = [f for f in required_fields if f not in data or data[f] is None]
    if missing:
        return OutputValidationResult(
            is_safe=False,
            errors=[f"Campos obrigatórios ausentes: {', '.join(missing)}"],
            sanitized_text="",
        )

    # Valida cada campo de texto
    text_fields = {
        "statement": _MAX_TEXT_LENGTH,
        "alternative_a": _MAX_ALTERNATIVE_LENGTH,
        "alternative_b": _MAX_ALTERNATIVE_LENGTH,
        "alternative_c": _MAX_ALTERNATIVE_LENGTH,
        "alternative_d": _MAX_ALTERNATIVE_LENGTH,
        "alternative_e": _MAX_ALTERNATIVE_LENGTH,
        "explanation": _MAX_EXPLANATION_LENGTH,
        "topic": 200,
    }

    for field_name, max_len in text_fields.items():
        result = validate_text_output(
            str(data.get(field_name, "")),
            max_length=max_len,
            field_name=field_name,
        )
        if not result.is_safe:
            errors.extend(result.errors)

    # Valida resposta correta
    correct = str(data.get("correct_answer", "")).strip().upper()
    if correct not in {"A", "B", "C", "D", "E"}:
        errors.append(f"Resposta correta inválida: '{correct}'")

    # Valida dificuldade
    try:
        diff = int(data.get("difficulty", 0))
        if diff < 1 or diff > 5:
            errors.append(f"Dificuldade fora do intervalo 1-5: {diff}")
    except (TypeError, ValueError):
        errors.append(f"Dificuldade inválida: '{data.get('difficulty')}'")

    return OutputValidationResult(
        is_safe=len(errors) == 0,
        errors=errors,
        sanitized_text="",
    )


def validate_explanation_output(data: dict) -> OutputValidationResult:
    """
    Valida output de uma explicação gerada pela IA.

    Args:
        data: Dicionário com dados da explicação.

    Returns:
        OutputValidationResult.
    """
    errors = []

    required_fields = ["summary", "concept", "steps", "common_mistake", "study_tip"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return OutputValidationResult(
            is_safe=False,
            errors=[f"Campos obrigatórios ausentes: {', '.join(missing)}"],
            sanitized_text="",
        )

    text_fields = {
        "summary": 1000,
        "concept": 500,
        "common_mistake": 500,
        "study_tip": 500,
    }

    for field_name, max_len in text_fields.items():
        result = validate_text_output(
            str(data.get(field_name, "")),
            max_length=max_len,
            field_name=field_name,
        )
        if not result.is_safe:
            errors.extend(result.errors)

    # Valida steps
    steps = data.get("steps", [])
    if not isinstance(steps, list):
        errors.append("Campo 'steps' deve ser uma lista")

    return OutputValidationResult(
        is_safe=len(errors) == 0,
        errors=errors,
        sanitized_text="",
    )


def validate_feedback_output(data: dict) -> OutputValidationResult:
    """
    Valida output de feedback gerado pela IA.

    Args:
        data: Dicionário com dados do feedback.

    Returns:
        OutputValidationResult.
    """
    errors = []

    required_fields = ["summary", "strengths", "weaknesses", "advice", "next_step"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return OutputValidationResult(
            is_safe=False,
            errors=[f"Campos obrigatórios ausentes: {', '.join(missing)}"],
            sanitized_text="",
        )

    text_fields = {
        "summary": 1000,
        "advice": 1000,
        "next_step": 500,
    }

    for field_name, max_len in text_fields.items():
        result = validate_text_output(
            str(data.get(field_name, "")),
            max_length=max_len,
            field_name=field_name,
        )
        if not result.is_safe:
            errors.extend(result.errors)

    # Valida listas
    for list_field in ["strengths", "weaknesses"]:
        value = data.get(list_field, [])
        if not isinstance(value, list):
            errors.append(f"Campo '{list_field}' deve ser uma lista")

    return OutputValidationResult(
        is_safe=len(errors) == 0,
        errors=errors,
        sanitized_text="",
    )


def validate_review_output(data: dict) -> OutputValidationResult:
    """
    Valida output de revisão gerada pela IA.

    Args:
        data: Dicionário com dados da revisão.

    Returns:
        OutputValidationResult.
    """
    errors = []

    required_fields = [
        "title", "summary", "key_concepts",
        "worked_example", "common_mistakes", "quick_check",
    ]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return OutputValidationResult(
            is_safe=False,
            errors=[f"Campos obrigatórios ausentes: {', '.join(missing)}"],
            sanitized_text="",
        )

    text_fields = {
        "title": 200,
        "summary": 1000,
        "worked_example": 2000,
        "quick_check": 500,
    }

    for field_name, max_len in text_fields.items():
        result = validate_text_output(
            str(data.get(field_name, "")),
            max_length=max_len,
            field_name=field_name,
        )
        if not result.is_safe:
            errors.extend(result.errors)

    # Valida listas
    for list_field in ["key_concepts", "common_mistakes"]:
        value = data.get(list_field, [])
        if not isinstance(value, list):
            errors.append(f"Campo '{list_field}' deve ser uma lista")

    return OutputValidationResult(
        is_safe=len(errors) == 0,
        errors=errors,
        sanitized_text="",
    )


def sanitize_output(text: str) -> str:
    """
    Limpa output da IA antes de renderizar.

    Remove HTML perigoso, normaliza e limita tamanho.

    Args:
        text: Texto da resposta da IA.

    Returns:
        Texto seguro para renderizar.
    """
    if not text:
        return ""

    result = validate_text_output(text)
    return result.sanitized_text
