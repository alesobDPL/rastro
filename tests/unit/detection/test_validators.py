import pytest

from rastro.detection.validators import is_cl_phone, is_email, is_plate, is_valid_rut, luhn_ok


@pytest.mark.parametrize(
    "value",
    ["12.345.678-5", "12345678-5", "10.000.013-K", "10000013-k", "10.000.004-0"],
)
def test_valid_rut(value: str) -> None:
    assert is_valid_rut(value)


@pytest.mark.parametrize("value", ["12.345.678-4", "12345678", "abc"])
def test_invalid_rut(value: str) -> None:
    assert not is_valid_rut(value)


def test_luhn() -> None:
    assert luhn_ok("4111111111111111")
    assert not luhn_ok("4111111111111112")
    assert not luhn_ok("")
    assert not luhn_ok("²")


@pytest.mark.parametrize(
    "value",
    ["+56 9 8765 4321", "987654321", "56987654321", "+56-2-2345-6789", "(41) 234 5678"],
)
def test_valid_cl_phone(value: str) -> None:
    assert is_cl_phone(value)


@pytest.mark.parametrize("value", ["12345", "+54 9 8765 4321", "98765x4321"])
def test_invalid_cl_phone(value: str) -> None:
    assert not is_cl_phone(value)


@pytest.mark.parametrize("value", ["AB1234", "BBCD12", "BB-CD-12", "AB 1234"])
def test_valid_plate(value: str) -> None:
    assert is_plate(value)


def test_invalid_plate() -> None:
    assert not is_plate("BACD12")


def test_email() -> None:
    assert is_email("juana.perez@gmail.com")
    assert not is_email("juana@")
    assert not is_email("juana@example..cl")
