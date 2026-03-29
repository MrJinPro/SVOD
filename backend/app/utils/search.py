from __future__ import annotations


_CYR_TO_LAT_CONFUSABLES = str.maketrans(
    {
        "А": "A",
        "В": "B",
        "С": "C",
        "Е": "E",
        "Н": "H",
        "К": "K",
        "М": "M",
        "О": "O",
        "Р": "P",
        "Т": "T",
        "Х": "X",
        "У": "Y",
        "а": "a",
        "в": "b",
        "с": "c",
        "е": "e",
        "н": "h",
        "к": "k",
        "м": "m",
        "о": "o",
        "р": "p",
        "т": "t",
        "х": "x",
        "у": "y",
    }
)

_LAT_TO_CYR_CONFUSABLES = str.maketrans(
    {
        "A": "А",
        "B": "В",
        "C": "С",
        "E": "Е",
        "H": "Н",
        "K": "К",
        "M": "М",
        "O": "О",
        "P": "Р",
        "T": "Т",
        "X": "Х",
        "Y": "У",
        "a": "а",
        "b": "в",
        "c": "с",
        "e": "е",
        "h": "н",
        "k": "к",
        "m": "м",
        "o": "о",
        "p": "р",
        "t": "т",
        "x": "х",
        "y": "у",
    }
)


def query_variants(value: str) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []

    variants = [raw, raw.translate(_CYR_TO_LAT_CONFUSABLES), raw.translate(_LAT_TO_CYR_CONFUSABLES)]

    out: list[str] = []
    for variant in variants:
        candidate = variant.strip()
        if candidate and candidate not in out:
            out.append(candidate)
    return out


def tokenize_query(value: str, *, max_tokens: int = 6) -> list[str]:
    return [token for token in str(value or "").split() if token][:max_tokens]


def query_needles(value: str) -> list[str]:
    return [f"%{variant}%" for variant in query_variants(value)]