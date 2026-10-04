"""El límite CPU rige en todos los formatos y conserva el cierre."""
from dataclasses import replace
import pytest
from variables.formato import cargar, para_dispositivo

@pytest.mark.parametrize("name,outro", [("previsualizacion",3.6),("social_vertical",3.6),("biblioteca",4.4)])
def test_cpu_clamps_after_controls_and_keeps_the_outro(name,outro):
    original=cargar(name)
    # el cierre ya no se puede quitar ni siquiera antes de llegar aquí: replace() lo rechaza (ver test_cierre_obligatorio.py)
    effective=para_dispositivo(replace(original,segundos=99),"cpu")
    assert effective.segundos == 3 and effective.fotogramas == 90
    assert not effective.bucle and effective.cierre_s == outro
    effective=para_dispositivo(original,"cpu")
    assert effective.cierre_s == outro
    assert para_dispositivo(original,"gpu") is original
