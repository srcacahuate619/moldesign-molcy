"""El montaje de pausas: repetir un fotograma ya rendido, nunca rendirlo otra vez."""
import pytest

from variables.pausas import Congelado, indice, montar, segundos_de_lectura


def test_sin_pausas_el_video_es_el_guion_tal_cual():
    m = montar(90, 30)
    assert m["fuentes"] == list(range(1, 91))
    assert m["pausas"] == [] and m["fotogramas_render_unicos"] == 90


def test_una_lectura_repite_su_fotograma_y_no_rinde_ninguno_mas():
    m = montar(100, 30, [Congelado(20, 1.0, etiquetas=("dist0",))])
    assert m["fuentes"] == list(range(1, 20)) + [20] * 30 + list(range(21, 101))
    assert m["fotogramas_render_unicos"] == 100          # los mismos PNG que sin pausa
    assert m["fotogramas_salida"] == 129 and m["fotogramas_repetidos"] == 29
    assert m["pausas"] == [{"fuente": 20, "salida": [20, 49], "segundos": 1.0,
                            "tipo": "lectura", "etiquetas": ["dist0"]}]


def test_los_fotogramas_identicos_tras_el_congelado_no_se_rinden():
    m = montar(100, 30, [Congelado(40, 2.5, omitir_hasta=55)])
    assert 41 not in m["fuentes"] and 55 not in m["fuentes"] and 56 in m["fuentes"]
    assert m["fotogramas_omitidos"] == 15 and m["fotogramas_render_unicos"] == 85
    assert m["pausas"][0]["salida"] == [40, 114] and m["pausas"][0]["omitidos"] == [41, 55]


def test_una_imagen_fija_se_rinde_una_vez_y_dura_lo_mismo():
    m = montar(60, 30, [Congelado(11, 20 / 30, tipo="imagen_fija", omitir_hasta=30)])
    assert len(m["fuentes"]) == 60                        # misma duración
    assert m["fuentes"][10:30] == [11] * 20 and m["fotogramas_render_unicos"] == 41


def test_el_orden_de_los_fotogramas_fuente_nunca_cambia():
    m = montar(300, 30, [Congelado(15, 1.0), Congelado(150, 1.0), Congelado(260, 1.0)])
    cambios = [f for i, f in enumerate(m["fuentes"]) if i == 0 or f != m["fuentes"][i - 1]]
    assert cambios == list(range(1, 301))
    for p in m["pausas"]:
        a, b = p["salida"]
        assert b - a + 1 == 30 and set(m["fuentes"][a - 1:b]) == {p["fuente"]}


@pytest.mark.parametrize("pausas", [
    [Congelado(0, 1.0)], [Congelado(101, 1.0)], [Congelado(10, 0.0)],
    [Congelado(10, 1.0, omitir_hasta=5)], [Congelado(10, 1.0), Congelado(10, 2.0)],
    [Congelado(10, 1.0, omitir_hasta=30), Congelado(20, 1.0)],
])
def test_una_pausa_imposible_falla_en_vez_de_montar_otra_cosa(pausas):
    with pytest.raises(ValueError):
        montar(100, 30, pausas)


def test_la_lectura_dura_de_dos_a_tres_segundos_segun_cuantas_etiquetas():
    assert segundos_de_lectura(1) == 2.0
    assert segundos_de_lectura(4) == pytest.approx(2.6)
    assert segundos_de_lectura(6) == 3.0 and segundos_de_lectura(12) == 3.0


def test_el_indice_da_las_pausas_en_segundos_del_video():
    m = montar(100, 30, [Congelado(31, 1.0, etiquetas=("a", "b"))])
    assert indice(m, 30) == [{"inicio_s": 1.0, "fin_s": 2.0, "tipo": "lectura", "etiquetas": 2}]
