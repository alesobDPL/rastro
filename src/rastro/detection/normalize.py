import re
import unicodedata

_ACRONYM_BOUNDARY = re.compile(r"([A-Z])([A-Z][a-z])")
_CASE_BOUNDARY = re.compile(r"([a-z])([A-Z])")
_TOKENS = re.compile(r"[a-z]+|[0-9]+")
_CONSONANT_PLURAL = re.compile(r"(?:ales|ares|iles|ones|ores)$")
_INVARIABLE_WORDS = {
    "alias", "atlas", "diabetes", "estatus", "lunes", "martes", "status", "tesis", "virus",
}


def _singular(token: str) -> str:
    if len(token) <= 3 or token in _INVARIABLE_WORDS:
        return token
    if token.endswith("ces"):
        return token[:-3] + "z"
    if _CONSONANT_PLURAL.search(token):
        return token[:-2]
    if token.endswith(("as", "es", "os")):
        return token[:-1]
    return token


def normalize_name(name: str) -> list[str]:
    decomposed = unicodedata.normalize("NFKD", name)
    unaccented = "".join(char for char in decomposed if not unicodedata.combining(char))
    separated = _ACRONYM_BOUNDARY.sub(r"\1 \2", unaccented)
    separated = _CASE_BOUNDARY.sub(r"\1 \2", separated)
    return [_singular(token) for token in _TOKENS.findall(separated.lower())]
