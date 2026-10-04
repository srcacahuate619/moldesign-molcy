"""El medidor de medallones: de el depende que el medallon 3D encaje en su hueco."""
from pathlib import Path

import numpy as np
import pytest

from marca import medallones as M

EMBLEMA = Path(__file__).resolve().parents[2] / "moldesign" / "assets" / "marca" / "emblema.png"


def _hexagono(ancho, alto, cx, cy, r, giro, grosor=2.0):
    """Un marco hexagonal brillante sobre negro, como en el logo."""
    yy, xx = np.mgrid[0:alto, 0:ancho].astype(np.float32)
    v = M.vertices(cx, cy, r, giro)
    d = np.full((alto, ancho), np.inf, dtype=np.float32)
    for k in range(6):
        a, b = v[k], v[(k + 1) % 6]
        ab = b - a
        t = np.clip(((xx - a[0]) * ab[0] + (yy - a[1]) * ab[1]) / (ab @ ab), 0, 1)
        d = np.minimum(d, np.hypot(xx - (a[0] + t * ab[0]), yy - (a[1] + t * ab[1])))
    return np.clip(1.0 - (d - grosor) / 1.5, 0, 1)


def test_recupera_un_hexagono_conocido():
    img = _hexagono(300, 300, 152.5, 147.0, 68.0, 3.0)
    m = M.ajustar(img, (145, 155), 63)          # partiendo 8 px y 5 px de radio lejos
    assert abs(m["cx"] - 152.5) <= 0.75 and abs(m["cy"] - 147.0) <= 0.75
    assert abs(m["r"] - 68.0) <= 0.75 and abs(m["giro"] - 3.0) <= 0.75


def test_la_mascara_cubre_el_hexagono_y_nada_mas():
    m = {"cx": 100.0, "cy": 100.0, "r": 50.0, "giro": 0.0}
    mask = M.dentro(200, 200, m)
    area_hex = 3 * np.sqrt(3) / 2 * 50 ** 2
    assert abs(mask.sum() - area_hex) / area_hex < 0.02
    assert mask[100, 100] and not mask[100, 155] and not mask[2, 2]
    # un vertice arriba: el pixel justo debajo del vertice superior esta dentro
    assert mask[52, 100] and not mask[48, 100]


@pytest.mark.skipif(not EMBLEMA.exists(), reason="sin emblema preparado")
def test_los_medallones_del_emblema_son_simetricos():
    from PIL import Image
    brillo = np.asarray(Image.open(EMBLEMA).convert("RGB")).astype(np.float32).max(axis=2) / 255
    aprox = [(490, 92), (832, 282), (882, 505), (831, 746),
             (150, 737), (88, 510), (152, 262)]
    res = [M.ajustar(brillo, c, 66) for c in aprox]
    eje = res[0]["cx"]                                  # el de arriba marca el eje
    for der, izq in ((1, 6), (2, 5), (3, 4)):          # parejas espejo
        assert abs((res[der]["cx"] - eje) - (eje - res[izq]["cx"])) < 3
        assert abs(res[der]["cy"] - res[izq]["cy"]) < 2
    assert all(66 <= m["r"] <= 74 for m in res)
    assert all(abs(m["giro"]) <= 4 for m in res)
