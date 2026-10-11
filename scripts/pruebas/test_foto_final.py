"""La foto: escena + capa de rótulos como en el vídeo, y qué hay en cada esquina."""
import json

import pytest

pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

import correr_foto  # noqa: E402
from salida.contraste import reforzar  # noqa: E402
from salida.foto_final import ESQUINAS, componer, ocupacion_esquinas  # noqa: E402

FONDO = (6, 12, 17)


def _escena(size=(200, 120)):
    return Image.new("RGB", size, (90, 100, 110))


def test_sin_capa_la_foto_es_la_escena():
    foto, capa = componer(_escena(), None, [], 10)
    assert capa is None and foto.mode == "RGB"
    assert foto.getpixel((5, 5)) == (90, 100, 110)
    assert ocupacion_esquinas(None, foto.size) == {e: 0 for e in ESQUINAS}


def test_la_capa_se_refuerza_y_se_compone_encima():
    capa = Image.new("RGBA", (200, 120), (0, 0, 0, 0))
    ImageDraw.Draw(capa).rectangle((90, 50, 110, 60), fill=(245, 245, 245, 255))
    etiquetas = [{"id": "a", "ventana": [10, 10], "caja": [-0.2, -0.2, 0.2, 0.2]}]
    foto, reforzada = componer(_escena(), capa, etiquetas, 10)
    assert min(foto.getpixel((100, 55))) > 230          # el texto
    assert max(foto.getpixel((82, 50))) < 60            # la placa oscura alrededor
    assert foto.getpixel((5, 5)) == (90, 100, 110)      # lejos, la escena intacta
    assert reforzada.getchannel("A").getextrema()[1] == 255


def test_una_etiqueta_en_la_esquina_la_ocupa():
    capa = Image.new("RGBA", (200, 120), (0, 0, 0, 0))
    ImageDraw.Draw(capa).rectangle((185, 105, 195, 115), fill=(255, 255, 255, 255))
    ocupado = ocupacion_esquinas(reforzar(capa), (200, 120))
    assert ocupado["inferior_derecha"] > 0
    assert ocupado["superior_derecha"] == ocupado["superior_izquierda"] == ocupado["inferior_izquierda"] == 0


def test_capa_de_otro_tamano_es_un_error():
    with pytest.raises(ValueError):
        componer(_escena(), Image.new("RGBA", (100, 60)), [], 1)


def test_el_halo_crece_con_la_foto_y_el_video_no_cambia():
    def ancho_del_halo(lado):
        capa = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        ImageDraw.Draw(capa).point((lado // 2, lado // 2), fill=(255, 255, 255, 255))
        alfa = reforzar(capa).getchannel("A")
        caja = alfa.getbbox()
        return caja[2] - caja[0]
    assert ancho_del_halo(720) == 3 and ancho_del_halo(1080) == 3      # lo que mide el vídeo
    assert ancho_del_halo(2160) == 7                                     # una foto 4K


def test_miniaturas_conservan_el_aspecto():
    assert correr_foto.tamano_miniatura({"ancho": 1080, "alto": 1920}) == (270, 480)
    assert correr_foto.tamano_miniatura({"ancho": 1920, "alto": 1080}) == (480, 270)
    assert correr_foto.tamano_miniatura({"ancho": 720, "alto": 720}) == (480, 480)


def _escena_en(tmp_path, blend_bytes=b"blend", **cambios):
    (tmp_path / "blender").mkdir()
    (tmp_path / "blender" / "x.blend").write_bytes(blend_bytes)
    escena = {"schema": "molcy.fotos.escena/1", "blend": {"nombre": "x.blend",
              "sha256": correr_foto.sha256(tmp_path / "blender" / "x.blend")}, **cambios}
    ruta = tmp_path / "escena_fotos_a.json"
    ruta.write_text(json.dumps(escena), encoding="utf-8")
    return ruta


def test_el_blend_tiene_que_ser_el_de_la_escena(tmp_path):
    ruta = _escena_en(tmp_path)
    escena, blend = correr_foto.leer_escena(ruta)
    assert blend.name == "x.blend"
    (tmp_path / "blender" / "x.blend").write_bytes(b"otro")
    with pytest.raises(correr_foto.Fallo, match="BLEND_NO_COINCIDE"):
        correr_foto.leer_escena(ruta)


def test_un_acta_que_no_es_de_fotos_no_se_usa(tmp_path):
    ruta = _escena_en(tmp_path, schema="molcy.video/1")
    with pytest.raises(correr_foto.Fallo, match="ESCENA_DESCONOCIDA"):
        correr_foto.leer_escena(ruta)


class _Hecho:
    def __init__(self, salida, codigo=0):
        self.stdout, self.returncode = salida, codigo


@pytest.mark.parametrize("salida,codigo,motivo", [
    ("QC_ABORTADO: no se construye", 2, "QC_ABORTADO"),
    ("SIN_GPU_CYCLES: Cycles no encontró ninguna GPU utilizable", 1, "SIN_GPU_CYCLES"),
    ("Traceback (most recent call last):", 1, "TRACEBACK"),
    ("todo bien pero sin marca", 0, "SIN_FOTO_LISTA"),
    ("FOTO_LISTA", 3, "BLENDER_EXIT_3"),
])
def test_un_blender_que_falla_dice_por_que(monkeypatch, tmp_path, salida, codigo, motivo):
    exe = tmp_path / "blender.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(correr_foto.subprocess, "run", lambda *a, **k: _Hecho(salida, codigo))
    with pytest.raises(correr_foto.Fallo, match=motivo):
        correr_foto.blender(str(exe), [], "FOTO_LISTA")


def test_sin_blender_no_se_lanza_nada(tmp_path):
    with pytest.raises(correr_foto.Fallo, match="SIN_BLENDER"):
        correr_foto.blender(str(tmp_path / "no.exe"), [], "FOTO_LISTA")


@pytest.mark.parametrize("nombre", ["../fuera", "a/b", ".oculto", ""])
def test_el_nombre_de_la_foto_no_sale_de_la_carpeta(tmp_path, nombre):
    ruta = _escena_en(tmp_path)
    a = type("A", (), {"carpeta": str(tmp_path), "escena": str(ruta), "nombre": nombre})
    with pytest.raises(correr_foto.Fallo, match="NOMBRE_INVALIDO"):
        correr_foto.tomar(a)


def test_preparar_exige_que_la_salida_sea_la_carpeta(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("MOLCY_OUTPUT_DIR", str(tmp_path / "otra"))
    codigo = correr_foto.main(["preparar", "--pdb", "1ABC", "--formato", "biblioteca",
                               "--carpeta", str(tmp_path), "--dispositivo", "cpu"])
    assert codigo == 1 and "FALLO SALIDA_DISTINTA" in capsys.readouterr().out
