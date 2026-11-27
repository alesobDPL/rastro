import re

from rastro.models import ValueKind

_RUT = re.compile(r"(?:[0-9]{1,2}(?:\.[0-9]{3}){2}-|[0-9]{7,8}-?)[0-9Kk]")
_EMAIL = re.compile(
    r"([^\s@.]+(?:\.[^\s@.]+)*)@([a-z0-9-]+(?:\.[a-z0-9-]+)*)(\.[a-z]{2,})",
    re.IGNORECASE,
)
_PHONE = re.compile(r"\+?(?:[0-9]+[ .-]?)?(?:\([0-9]+\)[ .-]?)?[0-9]+(?:[ .-][0-9]+)*")
_CARD = re.compile(r"[0-9]+(?:[ -][0-9]+)*")
_PLATE = re.compile(r"(?:[a-z]{4}[ -]?[0-9]{2}|[a-z]{2}[ -]?[0-9]{4})", re.IGNORECASE)


def _mask_digits(value: str, keep_first: int, keep_last: int) -> str:
    chars = list(value)
    digits = [index for index, char in enumerate(chars) if char.isascii() and char.isdigit()]
    for index in digits[keep_first : len(digits) - keep_last]:
        chars[index] = "*"
    return "".join(chars)


def _mask_generic(value: str) -> str:
    result = []
    in_letters = False
    for char in value:
        if char.isalpha() and in_letters:
            result.append("*")
        elif char.isdigit():
            result.append("#")
        else:
            result.append(char)
        in_letters = char.isalpha()
    return "".join(result)


def mask(value: str, kind: ValueKind) -> str:
    if kind == ValueKind.RUT and _RUT.fullmatch(value):
        return value[0] + re.sub(r"[0-9]", "*", value[1:-1]) + value[-1]

    if kind == ValueKind.EMAIL and (email := _EMAIL.fullmatch(value)):
        local, domain, tld = email.groups()
        first_local = next((i for i, char in enumerate(local) if char.isalpha()), None)
        first_domain = next((i for i, char in enumerate(domain) if char.isalpha()), None)
        if first_local is not None and first_domain is not None:
            return (
                "*" * first_local + local[first_local] + "*" * (len(local) - first_local - 1)
                + "@"
                + "*" * first_domain + domain[first_domain] + "*" * (len(domain) - first_domain - 1)
                + tld
            )

    if kind in (ValueKind.PHONE, ValueKind.CARD):
        digits = "".join(re.findall(r"[0-9]", value))
        if kind == ValueKind.PHONE and 7 <= len(digits) <= 15 and _PHONE.fullmatch(value):
            return _mask_digits(value, 3 if digits.startswith("56") else 1, 2)
        if kind == ValueKind.CARD and 13 <= len(digits) <= 19 and _CARD.fullmatch(value):
            return _mask_digits(value, 0, 4)

    if kind == ValueKind.PLATE and _PLATE.fullmatch(value):
        return value[0] + "*" * (len(value) - 2) + value[-1]

    return _mask_generic(value)
