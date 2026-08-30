ENEM_AREAS = [
    ("linguagens", "Linguagens"),
    ("humanas", "Ciências Humanas"),
    ("natureza", "Ciências da Natureza"),
    ("matematica", "Matemática"),
    ("redacao", "Redação"),
    ("outro", "Outro"),
]

AREA_LABELS = dict(ENEM_AREAS)

_KEYWORD_MAP = (
    ("redacao", ("redacao", "redação", "dissert", "escrita")),
    ("matematica", ("matematic", "matemát", "algebra", "álgebra", "geometr")),
    ("linguagens", ("portug", "literat", "ingles", "inglês", "espanhol", "linguag", "arte")),
    ("humanas", ("histor", "histór", "geograf", "filos", "sociol", "humanas")),
    ("natureza", ("fisic", "físic", "quim", "quím", "biolog", "naturez")),
)


def infer_area(nome):
    normalized = (nome or "").strip().lower()
    for area, keywords in _KEYWORD_MAP:
        if any(keyword in normalized for keyword in keywords):
            return area
    return "outro"


def area_label(area_key):
    return AREA_LABELS.get(area_key or "outro", "Outro")
