"""El montaje de pausas: repetir un fotograma ya rendido, nunca rendirlo otra vez."""
import pytest

from variables.pausas import Congelado, indice, montar, representantes, segundos_de_lectura


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


def _firma(estados):
    """estados: {fotograma: valor}; fuera de la lista, un valor propio (todo cambia)."""
    return lambda f: estados.get(f, ("propio", f))


def test_un_tramo_quieto_se_rinde_una_vez():
    estados = {f: "quieto" for f in range(10, 21)}
    rep = representantes(range(1, 31), _firma(estados))
    # Con estela, el primero y el último del tramo dependen de sus vecinos que se mueven.
    assert rep == {f: 11 for f in range(12, 20)}


def test_sin_estela_basta_con_que_el_estado_sea_igual():
    estados = {f: "quieto" for f in range(10, 21)}
    rep = representantes(range(1, 31), _firma(estados), vecinos=False)
    assert rep == {f: 10 for f in range(11, 21)}


def test_dos_tramos_con_el_mismo_estado_comparten_render_aunque_esten_lejos():
    estados = {**{f: "A" for f in range(5, 9)}, **{f: "A" for f in range(40, 44)}}
    rep = representantes(range(1, 50), _firma(estados), vecinos=False)
    assert rep == {6: 5, 7: 5, 8: 5, 40: 5, 41: 5, 42: 5, 43: 5}


def test_los_congelados_se_rinden_siempre_y_nada_cambia_si_todo_se_mueve():
    estados = {f: "quieto" for f in range(10, 21)}
    rep = representantes(range(1, 31), _firma(estados), vecinos=False, propios={12})
    assert 12 not in rep and rep[13] == 10
    assert representantes(range(1, 31), _firma({})) == {}


def test_solo_se_reutiliza_lo_que_se_iba_a_rendir():
    estados = {f: "quieto" for f in range(1, 31)}
    rep = representantes([3, 7, 9], _firma(estados), vecinos=False)
    assert rep == {7: 3, 9: 3}



def test_un_fundido_de_entrada_empieza_en_cero_sin_destello():
    # `horneado.curva` valía 1 en el primer fotograma del fundido: un destello.
    from nucleo.fundido import curva
    v = curva([(10, 16, 0, 1), (30, 36, 1, 0)], range(8, 40))
    assert v[:3] == [0.0, 0.0, 0.0]                       # 8, 9 y el 10, donde empieza
    assert all(a <= b for a, b in zip(v[2:9], v[3:9]))    # sube sin bajar
    assert v[8] == 1.0 and v[22] == 1.0 and v[-1] == 0.0
    assert curva([(1, 2, 1, 1)], range(1, 5)) == [1.0] * 4
