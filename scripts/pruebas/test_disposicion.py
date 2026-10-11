"""El reparto de etiquetas no acepta solapes ni cruces: o cabe limpio o lo dice."""
import itertools

import pytest

from variables.disposicion import SinEspacio, candidato, cruza, disponer, separacion, toca_caja


def _sin_choques(puestas, reservados=(), zonas=()):
    for caja, guia in puestas.values():
        assert -0.95 <= min(caja) and max(caja) <= 0.95
        assert all(separacion(caja, r) >= 0.035 for r in reservados)
        assert not any(toca_caja(*guia, z) for z in zonas)
    for (c1, g1), (c2, g2) in itertools.combinations(puestas.values(), 2):
        assert separacion(c1, c2) >= 0.035
        assert not cruza(*g1, *g2)
        assert not toca_caja(*g1, c2) and not toca_caja(*g2, c1)


@pytest.mark.parametrize("n,ancho,alto", [(2, .38, .18), (6, .30, .10), (7, .26, .09)])
def test_etiquetas_amontonadas_salen_sin_solapes_ni_cruces(n, ancho, alto):
    # Anclas apiñadas en el centro, como las interacciones alrededor de un ligando.
    etiquetas = [(str(i), ((i % 3 - 1) * .04, (i // 3 - .5) * .05), ancho, alto) for i in range(n)]
    reservados = [(-.25, -.25, .25, .25), (-.95, .55, -.2, .95)]
    puestas = disponer(etiquetas, reservados)
    assert set(puestas) == {e[0] for e in etiquetas}
    _sin_choques(puestas, reservados)
    assert puestas == disponer(etiquetas, reservados)          # determinista


def test_el_rotulo_del_sujeto_tampoco_se_solapa_con_las_interacciones():
    # El fallo del vídeo de 4FK3: «Vina top-1», el doble de grande, encima de dos interacciones.
    etiquetas = [("vina_top1", (0.0, 0.0), .60, .14)] + [
        (f"dist{i}", (.05 * (i - 2), .03 * (i % 2)), .42, .12) for i in range(5)]
    puestas = disponer(etiquetas, [(-.2, -.2, .2, .2)])
    _sin_choques(puestas, [(-.2, -.2, .2, .2)])


def test_si_no_hay_sitio_lo_dice_en_vez_de_solapar():
    with pytest.raises(SinEspacio):
        disponer([("uno", (0, 0), .3, .15)], [(-1, -1, 1, 1)])
    with pytest.raises(SinEspacio):
        disponer([("ancha", (0, 0), 2.5, .1)])


def test_las_guias_no_atraviesan_el_texto_de_pantalla():
    titulo = (-.85, .35, -.2, .85)
    puestas = disponer([("a", (0, .1), .3, .15), ("b", (.05, .05), .3, .15)],
                       [titulo], zonas_texto=[titulo])
    _sin_choques(puestas, [titulo], [titulo])


def test_una_etiqueta_no_tapa_su_propia_ancla():
    assert candidato((0, 0), (0.01, 0.0), .3, .1) is None
    caja, (inicio, punta) = candidato((0, 0), (0.5, 0.0), .3, .1)
    assert caja[0] > 0 and 0 < inicio[0] < punta[0] <= caja[0]


def test_segmentos_tangentes_colineales_o_en_t_tambien_chocan():
    assert toca_caja((0, 0), (.1, 0), (-.2, -.2, .2, .2))
    assert toca_caja((-.5, .2), (.5, .2), (-.2, -.2, .2, .2))
    assert not toca_caja((-.5, .6), (.5, .6), (-.2, -.2, .2, .2))
    assert cruza((0, 0), (1, 0), (.5, 0), (1.5, 0))
    assert cruza((0, 0), (1, 0), (.5, 0), (.5, 1))
    assert cruza((0, 0), (1, 1), (0, 1), (1, 0))
    assert not cruza((0, 0), (1, 0), (1.1, 0), (2, 0))
    assert not cruza((0, 0), (1, 0), (0, .1), (1, .1))
