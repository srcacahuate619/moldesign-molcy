import re
from pathlib import Path

import pytest

from variables import controles as C
from variables import formato as fmt

V = fmt.cargar("social_vertical")


def test_sin_ajustes_el_formato_no_cambia():
    f, extras, resueltos = C.aplicar(V, {})
    assert f == V and resueltos == {}
    assert extras == {"factor_desenfoque": 1.0, "piso_fantasma": None,
                      "exposicion": None, "contactos": True, "look_v4": True}


def test_posicion_de_produccion_vuelve_al_mismo_valor():
    for nombre, f in fmt.disponibles().items():
        reales = C.por_defecto(f)
        for b in C.BARRAS:
            assert b.valor(b.posicion(reales[b.id])) == pytest.approx(reales[b.id], abs=0.011), \
                (nombre, b.id)


def test_extremos_de_las_barras():
    f, extras, r = C.aplicar(V, {"barras": {"calidad": 0, "sombras": 0, "resolucion": 0,
                                            "duracion": 100, "estela": 0, "desenfoque": 0}})
    assert (f.muestras, f.escala_sombras, f.escala_render) == (16, 0.25, 50)
    assert f.segundos == 18.0 and f.fotogramas == 540
    assert not f.desenfoque_movimiento and not f.profundidad_de_campo
    f, _, _ = C.aplicar(V, {"barras": {"calidad": 100, "estela": 100}})
    assert f.muestras == 128 and f.obturador == 0.7 and f.desenfoque_movimiento


def test_texto_escala_titulo_y_etiquetas():
    f, _, _ = C.aplicar(V, {"barras": {"texto": 100}})
    assert f.escala_texto == pytest.approx(2.8) and f.escala_etiquetas_3d == pytest.approx(4.48)


def test_interruptores():
    f, extras, _ = C.aplicar(V, {"interruptores": {"titulo": False, "etiquetas": False,
                                                   "sello": False, "contactos": False,
                                                   "look_v4": False}})
    assert not (f.rotulos_pantalla or f.etiquetas_3d or f.sello_procedencia)
    assert extras["contactos"] is False and extras["look_v4"] is False


@pytest.mark.parametrize("malo", [
    {"barras": {"rayos_x": 50}},
    {"barras": {"calidad": 101}},
    {"barras": {"calidad": True}},
    {"interruptores": {"titulo": "no"}},
    {"otra_cosa": {}},
])
def test_validar_rechaza(malo):
    with pytest.raises(ValueError):
        C.validar(malo)


def test_estimacion_calibrada_en_016():
    # los cuatro puntos medidos el 2026-09-22, dentro del 12 %
    e = C.estimar(V)
    assert e["por_fotograma_s"] == pytest.approx(1.62, rel=0.12)
    assert e["fotogramas"] == 360
    alta = C.estimar(V, {"barras": {"calidad": C.BARRAS[0].posicion(96), "sombras": 100}})
    assert alta["por_fotograma_s"] == pytest.approx(4.36, rel=0.12)
    borrador = C.estimar(V, {"barras": C.preset("borrador")})
    assert borrador["por_fotograma_s"] == pytest.approx(0.35, rel=0.15)
    assert borrador["total_s"] == pytest.approx(160, rel=0.2)       # ~2.7 min reales
    p = C.estimar(fmt.cargar("previsualizacion"))
    assert p["por_fotograma_s"] == pytest.approx(0.47, rel=0.12)
    assert borrador["total_s"] < e["total_s"] / 3


def test_presets():
    b = C.preset("borrador")
    f, _, _ = C.aplicar(V, {"barras": b})
    assert (f.muestras, f.escala_sombras, f.escala_render) == (16, 0.25, 50)
    assert C.preset("produccion") == {}


def test_piso_fantasma_igual_que_el_guion():
    fuente = (Path(__file__).resolve().parents[1] / "guiones" / "sitio_activo.py") \
        .read_text(encoding="utf-8")
    assert float(re.search(r"^PISO_FANTASMA = ([\d.]+)", fuente, re.M).group(1)) \
        == C.PISO_FANTASMA


def test_json_para_la_interfaz():
    j = C.como_json(fmt.disponibles())
    assert {b["id"] for b in j["barras"]} == {b.id for b in C.BARRAS}
    d = j["defecto"]["social_vertical"]
    assert d["calidad"] == C.BARRAS[0].posicion(64) and d["titulo"] is True
    assert j["defecto"]["previsualizacion"]["titulo"] is False


# ── cierre de marca ──────────────────────────────────────────────────────
def test_formatos_llevan_cierre_y_no_sello():
    assert (V.cierre_s, V.sello_procedencia) == (3.6, False)
    b = fmt.cargar("biblioteca")
    assert (b.cierre_s, b.sello_procedencia) == (4.4, False)
    # un bucle no termina: sin cierre
    assert fmt.cargar("previsualizacion").cierre_s == 0.0


def test_interruptor_de_cierre():
    assert C.por_defecto(V)["cierre"] is True
    f, _, r = C.aplicar(V, {"interruptores": {"cierre": False}})
    assert f.cierre_s == 0.0 and r == {"cierre": False}
    # pedirlo en el bucle no lo crea
    p = fmt.cargar("previsualizacion")
    assert C.aplicar(p, {"interruptores": {"cierre": True}})[0].cierre_s == 0.0
    j = C.como_json(fmt.disponibles())
    assert j["defecto"]["social_vertical"]["cierre"] is True
    assert j["defecto"]["previsualizacion"]["cierre"] is False
