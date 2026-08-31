"""
Validadores de questões geradas - PlanejaENEM 5.0.

Validação determinística do output da IA NUNCA confia diretamente.
Cada função retorna (isValid, lista_de_erros).

REGRA DE OURO: A IA é falível. Validação é mandatória.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_ANSWER_LETTERS = {"A", "B", "C", "D", "E"}
_MAX_STATEMENT_LENGTH = 5000
_MAX_ALTERNATIVE_LENGTH = 500
_MAX_EXPLANATION_LENGTH = 2000


@dataclass
class ValidationResult:
    """Resultado de uma validação."""

    is_valid: bool
    errors: list[str]

    def __bool__(self) -> bool:
        return self.is_valid


def _strip(text: str | None) -> str:
    """Remove espaços extras e normaliza."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())


def validate_question(data: dict) -> ValidationResult:
    """
    Valida uma única questão gerada pela IA.

    Checks:
        - Campos obrigatórios presentes
        - Exatamente 5 alternativas (A-E)
        - Uma resposta correta (A-E)
        - Dificuldade 1-5
        - Tópico válido
        - Tamanhos máximos
        - Alternativas não duplicadas (normalizadas)

    Args:
        data: Dicionário com a questão gerada.

    Returns:
        ValidationResult com is_valid e lista de erros.
    """
    errors: list[str] = []

    required_fields = [
        "statement",
        "alternative_a",
        "alternative_b",
        "alternative_c",
        "alternative_d",
        "alternative_e",
        "correct_answer",
        "explanation",
        "difficulty",
        "topic",
    ]

    missing = [f for f in required_fields if f not in data or data[f] is None]
    if missing:
        errors.append(f"Campos obrigatórios ausentes: {', '.join(missing)}")
        return ValidationResult(is_valid=False, errors=errors)

    statement = _strip(str(data.get("statement", "")))
    if not statement:
        errors.append("Enunciado não pode ser vazio")
    elif len(statement) > _MAX_STATEMENT_LENGTH:
        errors.append(f"Enunciado excede {_MAX_STATEMENT_LENGTH} caracteres")

    alternatives = {}
    for letter in _ANSWER_LETTERS:
        key = f"alternative_{letter.lower()}"
        value = _strip(str(data.get(key, "")))
        if not value:
            errors.append(f"Alternativa {letter} não pode ser vazia")
        elif len(value) > _MAX_ALTERNATIVE_LENGTH:
            errors.append(f"Alternativa {letter} excede {_MAX_ALTERNATIVE_LENGTH} caracteres")
        alternatives[letter] = value

    normalized_alts = [v.lower() for v in alternatives.values() if v]
    if len(set(normalized_alts)) < len(normalized_alts):
        errors.append("Alternativas duplicadas detectadas")

    correct = str(data.get("correct_answer", "")).strip().upper()
    if correct not in _ANSWER_LETTERS:
        errors.append(f"Resposta correta inválida: '{data.get('correct_answer')}' (deve ser A-E)")

    difficulty = data.get("difficulty")
    try:
        diff_int = int(difficulty)
        if diff_int < 1 or diff_int > 5:
            errors.append(f"Dificuldade {diff_int} fora do intervalo 1-5")
    except (TypeError, ValueError):
        errors.append(f"Dificuldade inválida: '{difficulty}'")

    topic = _strip(str(data.get("topic", "")))
    if not topic:
        errors.append("Tópico não pode ser vazio")

    explanation = _strip(str(data.get("explanation", "")))
    if not explanation:
        errors.append("Explicação não pode ser vazia")
    elif len(explanation) > _MAX_EXPLANATION_LENGTH:
        errors.append(f"Explicação excede {_MAX_EXPLANATION_LENGTH} caracteres")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)


def validate_question_batch(questions: list[dict]) -> list[ValidationResult]:
    """
    Valida um lote de questões.

    Args:
        questions: Lista de dicts com questões geradas.

    Returns:
        Lista de ValidationResult, um por questão.
    """
    return [validate_question(q) for q in questions]


def sanitize_question(data: dict) -> dict:
    """
    Normaliza e limpa uma questão gerada pela IA.

    Não altera a semântica, apenas formatação:
        - Strip em strings
        - uppercase no gabarito
        - difficulty como int

    Args:
        data: Dicionário bruto da questão.

    Returns:
        Dicionário sanitizado.
    """
    sanitized = dict(data)

    for key in [
        "statement",
        "alternative_a", "alternative_b", "alternative_c",
        "alternative_d", "alternative_e",
        "explanation", "topic",
    ]:
        if key in sanitized and isinstance(sanitized[key], str):
            sanitized[key] = _strip(sanitized[key])

    if "correct_answer" in sanitized:
        sanitized["correct_answer"] = str(sanitized["correct_answer"]).strip().upper()

    if "difficulty" in sanitized:
        try:
            sanitized["difficulty"] = int(sanitized["difficulty"])
        except (TypeError, ValueError):
            sanitized["difficulty"] = 3

    return sanitized
