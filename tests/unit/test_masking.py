import pytest

from rastro.masking import mask
from rastro.models import ValueKind


@pytest.mark.parametrize(
    ("value", "kind", "expected"),
    [
        ("12.345.678-5", ValueKind.RUT, "1*.***.***-5"),
        ("juana.perez@gmail.com", ValueKind.EMAIL, "j**********@g****.com"),
        ("+56 9 8765 4321", ValueKind.PHONE, "+56 9 **** **21"),
        ("4111 1111 1111 1111", ValueKind.CARD, "**** **** **** 1111"),
        ("BBCD12", ValueKind.PLATE, "B****2"),
        ("paciente con diabetes", ValueKind.GENERIC, "p******* c** d*******"),
        ("987654321", ValueKind.PHONE, "9******21"),
        ("12345678-K", ValueKind.RUT, "1*******-K"),
        ("", ValueKind.GENERIC, ""),
        ("N/A", ValueKind.GENERIC, "N/A"),
        ("Ñuñoa Peñalolén", ValueKind.GENERIC, "Ñ**** P********"),
        ("12.345.678-5", ValueKind.EMAIL, "##.###.###-#"),
        ("4111 1111 1111 1111", ValueKind.PLATE, "#### #### #### ####"),
    ],
)
def test_mask(value: str, kind: ValueKind, expected: str) -> None:
    assert mask(value, kind) == expected


def test_mask_preserves_length_of_long_generic_value() -> None:
    assert len(mask("a" * 1000, ValueKind.GENERIC)) == 1000
