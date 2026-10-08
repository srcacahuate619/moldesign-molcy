"""Los momentos que valen una foto salen de la escena, no de una lista a mano."""
import pytest

from variables import pausas
from variables.momentos import beat_de, sugeridos, validar_fotograma

# Rangos y montaje de Resultado (4FK3, vertical): el sitio vacío es una imagen fija,
# el sujeto y sus seis interacciones se congelan para leerse y la vuelta final no
# tiene pausa.
RANGOS = {"general": (1, 87), "aproximacion": (88, 143), "pausa_hotspots": (144, 191),
          "llegada_por_fundido": (192, 273), "exploracion": (274, 381), "reposo": (382, 389)}
PAPELES = {"general": "establecer", "aproximacion": "aproximar", "pausa_hotspots": "pausa",
           "llegada_por_fundido": "pausa", "exploracion": "explorar", "reposo": "reposo"}
TITULO = {"ventana": (11, 74), "fundido": [(11, 21, 0, 1), (64, 74, 1, 0)]}


def _resultado():
    montaje = pausas.montar(389, 30, [
        pausas.Congelado(144, 0.5, "imagen_fija", (), 191),
        pausas.Congelado(253, 2.8, "lectura", ("lig", "d1", "d2", "d3", "d4", "d5"))])
    return sugeridos(RANGOS, montaje["pausas"], 389, titulo=TITULO, papeles=PAPELES)


def test_resultado_sugiere_titulo_sitio_interacciones_y_vuelta():
    m = _resultado()
    assert [(x["tipo"], x["beat"], x["fotograma"]) for x in m] == [
        ("titulo", "general", 42),            # mitad del tramo en que el título se ve entero
        ("imagen_fija", "pausa_hotspots", 144),
        ("lectura", "llegada_por_fundido", 253),
        ("recorrido", "exploracion", 327),
    ]
    assert m[2]["etiquetas"] == 6
    assert [x["orden"] for x in m] == [1, 2, 3, 4]
    assert len({x["id"] for x in m}) == 4


def test_un_beat_con_pausa_no_repite_su_mitad():
    m = _resultado()
    assert not any(x["tipo"] == "recorrido" and x["beat"] == "llegada_por_fundido" for x in m)
    # `aproximar` es el viaje hacia el sitio: su mitad no es una toma.
    assert not any(x["beat"] == "aproximacion" for x in m)


def test_la_pausa_dice_de_que_pose_es():
    rangos = {"sitio": (1, 30), "convergencia": (31, 90), "salida": (91, 120)}
    montaje = pausas.montar(120, 30, [
        pausas.Congelado(16, 1.0, "lectura", ("s1", "s2")),
        pausas.Congelado(45, 1.0, "lectura", ("p2a",)),
        pausas.Congelado(70, 1.0, "lectura", ("p3a", "p3b"))])
    m = sugeridos(rangos, montaje["pausas"], 120,
                  papeles={"sitio": "aproximar", "convergencia": "explorar", "salida": "explorar"},
                  rotulos_por_pose={1: ["p1a"], 2: ["p2a"], 3: ["p3a", "p3b"]})
    assert [(x["beat"], x["pose"], x["fotograma"]) for x in m] == [
        ("sitio", None, 16), ("convergencia", 2, 45), ("convergencia", 3, 70), ("salida", None, 105)]


def test_un_titulo_que_nunca_se_ve_entero_no_es_toma():
    m = sugeridos({"general": (1, 20)}, [], 20,
                  titulo={"ventana": (5, 12), "fundido": [(5, 10, 0, 1), (9, 12, 1, 0)]},
                  papeles={"general": "establecer"})
    assert [x["tipo"] for x in m] == ["recorrido"]


def test_dos_sugerencias_en_el_mismo_fotograma_quedan_en_una():
    montaje = pausas.montar(40, 30, [pausas.Congelado(20, 1.0, "lectura", ("a",))])
    m = sugeridos({"exploracion": (1, 40)}, montaje["pausas"], 40,
                  titulo={"ventana": (20, 20), "fundido": []}, papeles={"exploracion": "explorar"})
    assert [(x["fotograma"], x["tipo"]) for x in m] == [(20, "lectura")]


def test_beat_de_y_fotograma_libre():
    assert beat_de(88, RANGOS) == "aproximacion"
    assert beat_de(500, RANGOS) is None
    assert validar_fotograma(1, 389) == 1 and validar_fotograma(389, 389) == 389
    for malo in (0, 390, 3.0, "7", True, None):
        with pytest.raises(ValueError):
            validar_fotograma(malo, 389)


def test_una_escena_sin_fotogramas_no_tiene_momentos():
    with pytest.raises(ValueError):
        sugeridos({}, [], 0)
