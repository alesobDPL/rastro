import re
from itertools import cycle

_RUT = re.compile(r"([0-9]{1,8}|[0-9]{1,2}\.[0-9]{3}\.[0-9]{3}|[0-9]{1,3}\.[0-9]{3})-([0-9Kk])")
_PHONE = re.compile(
    r"(?:\+?56[ -]?)?(?:"
    r"(?:[2-9]|\([2-9]\))[ -]?[0-9]{4}[ -]?[0-9]{4}"
    r"|(?:[2-7][0-9]|\([2-7][0-9]\))[ -]?[0-9]{3}[ -]?[0-9]{4})"
)
_CONSONANTS = "[BCDFGHJKLMNPQRSTVWXYZ]"
_PLATE = re.compile(
    r"[A-Z]{2}[ -]?[0-9]{4}|"
    rf"{_CONSONANTS}{{2}}[ -]?{_CONSONANTS}{{2}}[ -]?[0-9]{{2}}"
)
_EMAIL = re.compile(r"[^\s@.]+(?:\.[^\s@.]+)*@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]+")


def is_valid_rut(value: str) -> bool:
    match = _RUT.fullmatch(value.strip())
    if match is None:
        return False
    body, check_digit = match.groups()
    digits = reversed(body.replace(".", ""))
    total = sum(int(digit) * weight for digit, weight in zip(digits, cycle(range(2, 8))))
    return check_digit.upper() == "0123456789K"[-total % 11]


def luhn_ok(digits: str) -> bool:
    if not digits.isascii() or not digits.isdecimal():
        return False
    total = 0
    for digit, weight in zip(reversed(digits), cycle((1, 2))):
        product = int(digit) * weight
        total += product if product < 10 else product - 9
    return total % 10 == 0


def is_cl_phone(value: str) -> bool:
    return _PHONE.fullmatch(value.strip()) is not None


def is_plate(value: str) -> bool:
    value = value.strip()
    return value.isascii() and _PLATE.fullmatch(value.upper()) is not None


def is_email(value: str) -> bool:
    return _EMAIL.fullmatch(value.strip()) is not None
