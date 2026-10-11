"""Placa y halo oscuros en la capa de rótulos: se leen sobre el receptor claro."""
import json

import pytest

pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

from salida.contraste import cajas_en_pixeles, main, reforzar  # noqa: E402


def test_el_texto_claro_se_lee_sobre_un_receptor_blanco():
    capa = Image.new("RGBA", (100, 60), (0, 0, 0, 0))
    ImageDraw.Draw(capa).rectangle((35, 25, 65, 35), fill=(245, 245, 245, 255))
    final = Image.alpha_composite(Image.new("RGBA", capa.size, (255, 255, 255, 255)),
                                  reforzar(capa, [(30, 20, 70, 40)]))
    assert min(final.getpixel((50, 30))[:3]) > 230          # el texto sigue claro
    assert max(final.getpixel((31, 21))[:3]) < 80           # y la placa detrás es oscura
    assert final.getpixel((2, 2))[:3] == (255, 255, 255)    # fuera, la escena intacta


def test_sin_etiqueta_visible_no_hay_placa():
    vacia = reforzar(Image.new("RGBA", (100, 60), (0, 0, 0, 0)), [(30, 20, 70, 40)])
    assert vacia.getchannel("A").getextrema() == (0, 0)


def test_las_cajas_del_acta_pasan_a_pixeles_solo_en_su_ventana():
    etiquetas = [{"id": "a", "ventana": [10, 20], "caja": [-0.5, -0.5, 0.5, 0.5]}]
    assert cajas_en_pixeles(etiquetas, 9, 200, 100) == []
    (x0, y0, x1, y1), = cajas_en_pixeles(etiquetas, 15, 200, 100)
    assert x0 < 50 < 150 < x1 and y0 < 25 < 75 < y1


def test_procesa_la_carpeta_de_la_capa(tmp_path):
    capa = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
    ImageDraw.Draw(capa).rectangle((30, 35, 50, 45), fill=(255, 200, 50, 255))
    capa.save(tmp_path / "f_0012.png")
    acta = tmp_path / "build.json"
    acta.write_text(json.dumps({"etiquetas_lectura": [
        {"id": "a", "ventana": [12, 12], "caja": [-0.3, -0.2, 0.3, 0.2]}]}), encoding="utf-8")
    assert main([str(tmp_path), str(acta)]) == 0
    with Image.open(tmp_path / "f_0012.png") as hecho:
        assert hecho.getpixel((28, 40))[3] > 150            # la placa ya está en la capa
