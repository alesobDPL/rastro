import pytest

from rastro.detection.normalize import normalize_name


@pytest.mark.parametrize(
    ("name", "tokens"),
    [
        ("fechaNac2", ["fecha", "nac", "2"]),
        ("Dirección_Envío", ["direccion", "envio"]),
        ("RUTCliente", ["rut", "cliente"]),
        ("Proveedores/Observaciones", ["proveedor", "observacion"]),
        ("direcciones_regiones_comunas", ["direccion", "region", "comuna"]),
        ("nombres_apellidos", ["nombre", "apellido"]),
    ],
)
def test_normalize(name: str, tokens: list[str]) -> None:
    assert normalize_name(name) == tokens
