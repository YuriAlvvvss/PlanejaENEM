"""
Prompts para geração de questões - PlanejaENEM 5.0.

Prompts enxutos e otimizados para economia de tokens.
Cada prompt é uma função pura que recebe contexto e retorna mensagens.
NÃO acessa banco, não executa SQL, não modifica scores.
"""

PROMPT_VERSION = "1.0"

_QUESTION_SCHEMA_INSTRUCTIONS = """\
Responda APENAS com JSON válido (sem markdown, sem ```).
Schema obrigatório:
{
  "questions": [
    {
      "statement": "enunciado da questão",
      "alternative_a": "alternativa A",
      "alternative_b": "alternativa B",
      "alternative_c": "alternativa C",
      "alternative_d": "alternativa D",
      "alternative_e": "alternativa E",
      "correct_answer": "A|B|C|D|E",
      "explanation": "explicação concisa",
      "difficulty": 1-5,
      "topic": "tópico específico"
    }
  ]
}"""

_DIFFICULTY_MAP = {
    1: "fácil",
    2: "médio-fácil",
    3: "médio",
    4: "médio-difícil",
    5: "difícil",
}


def build_question_generation_prompt(
    area: str,
    materia: str,
    assunto: str,
    dificuldade: int,
    quantidade: int,
    tipo_questao: str = "multipla_escolha",
) -> list[dict]:
    """
    Gera lista de mensagens para geração de questões.

    Args:
        area: Área do conhecimento (ex: "matematica", "humanas").
        materia: Matéria (ex: "Matemática", "História").
        assunto: Assunto específico (ex: "Equações do 2º grau").
        dificuldade: Nível de dificuldade (1-5).
        quantidade: Número de questões a gerar.
        tipo_questao: Tipo da questão (padrão: "multipla_escolha").

    Returns:
        Lista de dicts no formato OpenAI messages.
    """
    diff_label = _DIFFICULTY_MAP.get(dificuldade, "médio")

    system_msg = (
        f"Você é um gerador de questões do ENEM. "
        f"Gere exatamente {quantidade} questão(ões) de múltipla escolha.\n\n"
        f"REGRAS:\n"
        f"- Cada questão deve ter EXATAMENTE 5 alternativas (A-E).\n"
        f"- Apenas UMA resposta correta.\n"
        f"- Formato da resposta: gabarito (A, B, C, D ou E).\n"
        f"- NÃO inclua texto em negrito, itálico ou formatação especial.\n"
        f"- Alternativas devem ser plausíveis mas com apenas uma correta.\n"
        f"- Explicação concisa (máx. 2 frases).\n"
        f"- difficulty deve ser número inteiro de 1 a 5.\n"
        f"- topic deve ser o assunto específico.\n\n"
        f"{_QUESTION_SCHEMA_INSTRUCTIONS}"
    )

    user_msg = (
        f"Gere {quantidade} questão(ões) do ENEM:\n"
        f"- Área: {area}\n"
        f"- Matéria: {materia}\n"
        f"- Assunto: {assunto}\n"
        f"- Dificuldade: {dificuldade}/5 ({diff_label})\n"
        f"- Tipo: {tipo_questao}\n\n"
        f"Retorne APENAS o JSON no schema especificado."
    )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def build_single_question_prompt(
    area: str,
    materia: str,
    assunto: str,
    dificuldade: int,
) -> list[dict]:
    """Atalho para gerar uma única questão."""
    return build_question_generation_prompt(
        area=area,
        materia=materia,
        assunto=assunto,
        dificuldade=dificuldade,
        quantidade=1,
    )
