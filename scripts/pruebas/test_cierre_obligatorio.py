"""El cierre de MolDesign es OBLIGATORIO en todo video: ningún formato, mando, ajuste ni script lo deja fuera.

Es parte del producto (la firma de marca al final de cada video generado). La única forma de quitarlo es editar el video a mano o modificar este código,
que es GPL y se puede modificar; lo que el motor garantiza es que NO ofrece ninguna vía para hacerlo: ni un interruptor, ni un ajuste, ni un formato con
cierre cero, ni un lanzador o un codificador que acepten un video sin él.
"""
import json
import runpy
import sys
import types
from dataclasses import replace
from pathlib import Path

import pytest

from variables import controles as C
from variables import formato as fmt
from variables.formato import CIERRE_MINIMO_S, Formato, cargar, para_dispositivo

RAIZ = Path(__file__).resolve().parents[1]


# ── el formato ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("nombre", sorted(fmt.disponibles()))
def test_todo_formato_declara_su_cierre(nombre):
    f = cargar(nombre)
    assert f.cierre_s >= CIERRE_MINIMO_S, f"{nombre} sin cierre"


def test_los_formatos_conocidos_y_sus_cierres():
    assert {n: cargar(n).cierre_s for n in ("previsualizacion", "social_vertical", "biblioteca")} == {
        "previsualizacion": 3.6, "social_vertical": 3.6, "biblioteca": 4.4}


@pytest.mark.parametrize("valor", [0, 0.0, 2.9, -1, None, "3.6", True, False])
def test_un_formato_sin_cierre_valido_no_se_puede_crear(valor):
    with pytest.raises(ValueError, match="obligatorio"):
        Formato(nombre="x", descripcion="x", cierre_s=valor)


def test_replace_no_puede_quitar_el_cierre():
    f = cargar("social_vertical")
    with pytest.raises(ValueError, match="obligatorio"):
        replace(f, cierre_s=0.0)
    assert replace(f, cierre_s=CIERRE_MINIMO_S).cierre_s == CIERRE_MINIMO_S  # el minimo exacto vale


def test_el_valor_por_defecto_ya_es_un_cierre():
    assert Formato(nombre="nuevo", descripcion="un formato futuro").cierre_s == fmt.CIERRE_POR_DEFECTO_S >= CIERRE_MINIMO_S


@pytest.mark.parametrize("dispositivo", ["cpu", "gpu"])
@pytest.mark.parametrize("nombre", ["previsualizacion", "social_vertical", "biblioteca"])
def test_cpu_y_gpu_llevan_el_mismo_cierre(nombre, dispositivo):
    original = cargar(nombre)
    assert para_dispositivo(original, dispositivo).cierre_s == original.cierre_s


# ── los mandos ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("ajustes", [
    {"interruptores": {"cierre": False}},
    {"interruptores": {"cierre": True}},
    {"barras": {"cierre": 0}},
    {"cierre": False},
    {"interruptores": {"cierre": False, "titulo": True}},
])
def test_ningun_ajuste_toca_el_cierre(ajustes):
    with pytest.raises(ValueError, match="cierre de MolDesign es obligatorio"):
        C.validar(ajustes)
    with pytest.raises(ValueError, match="cierre de MolDesign es obligatorio"):
        C.aplicar(cargar("social_vertical"), ajustes)


def test_un_fichero_de_ajustes_con_cierre_se_rechaza(tmp_path):
    ruta = tmp_path / "ajustes.json"
    ruta.write_text(json.dumps({"interruptores": {"cierre": False}}), encoding="utf-8")
    with pytest.raises(ValueError, match="obligatorio"):
        C.leer(ruta)


def test_los_demas_ajustes_no_cambian_el_cierre():
    for nombre in ("previsualizacion", "social_vertical", "biblioteca"):
        f = cargar(nombre)
        g, _, _ = C.aplicar(f, {"barras": {"calidad": 0}, "interruptores": {"titulo": True, "etiquetas": False, "sello": True}})
        assert g.cierre_s == f.cierre_s


# ── los scripts ──────────────────────────────────────────────────────────
def test_el_lanzador_no_codifica_ni_sella_sin_cierre():
    ps1 = (RAIZ / "correr_caso.ps1").read_text(encoding="utf-8")
    assert "SIN_CIERRE" in ps1
    assert ps1.count("Fallo 'SIN_CIERRE'") >= 2
    assert "if ($cierreS -lt 3.0)" in ps1
    # el cierre ya no es condicional al codificar ni al sellar
    assert "if ($cierreDir) {" not in ps1 and "if ($cierreManifiesto) {" not in ps1
    assert "'--cierre', $cierreDir" in ps1 and "'--cierre', $cierreManifiesto" in ps1


def test_el_sellador_rechaza_un_video_sin_manifiesto_de_cierre(tmp_path, capsys):
    sellar = runpy.run_path(str(RAIZ / "salida" / "sellar_mp4.py"), run_name="no_main")
    video, acta = tmp_path / "v.mp4", tmp_path / "build.json"
    video.write_bytes(b"datos")
    acta.write_text("{}", encoding="utf-8")
    sys.argv = ["sellar_mp4.py", str(video), str(acta)]
    assert sellar["main"]() == 1
    assert "SELLO_SIN_CIERRE" in capsys.readouterr().out
    assert not (tmp_path / "v.mp4.sha256").exists()
    assert json.loads(acta.read_text(encoding="utf-8")) == {}, "no debe sellar el acta de un video sin cierre"
    # con un manifiesto inexistente tampoco
    sys.argv = ["sellar_mp4.py", str(video), str(acta), "--cierre", str(tmp_path / "no-existe.json")]
    assert sellar["main"]() == 1


def test_el_sellador_con_cierre_registra_la_firma_y_la_duracion_total(tmp_path):
    sellar = runpy.run_path(str(RAIZ / "salida" / "sellar_mp4.py"), run_name="no_main")
    video, acta, manifiesto = tmp_path / "v.mp4", tmp_path / "build.json", tmp_path / "manifiesto.json"
    video.write_bytes(b"datos")
    acta.write_text(json.dumps({"fotogramas": 90}), encoding="utf-8")
    manifiesto.write_text(json.dumps({"segundos": 3.6, "fotogramas": 108, "muestras": 48, "huella": "h", "blender": "5.2.2", "fps": 30}),
                          encoding="utf-8")
    sys.argv = ["sellar_mp4.py", str(video), str(acta), "--cierre", str(manifiesto)]
    assert sellar["main"]() == 0
    datos = json.loads(acta.read_text(encoding="utf-8"))
    assert datos["cierre"] == {"segundos": 3.6, "fotogramas": 108, "muestras": 48, "huella": "h", "blender": "5.2.2"}
    assert datos["video"]["segundos"] == 6.6      # 90 fotogramas a 30 fps + 3,6 s de cierre
    assert (tmp_path / "v.mp4.sha256").exists()


def test_el_codificador_aborta_sin_cierre(monkeypatch, tmp_path):
    """`codificar.py` corre dentro de Blender; aquí se sustituye `bpy` por uno vacío: el aborto ocurre ANTES de usarlo."""
    monkeypatch.setitem(sys.modules, "bpy", types.ModuleType("bpy"))
    monkeypatch.setattr(sys, "argv", ["blender", "--", str(tmp_path / "png"), str(tmp_path / "salida.mp4"), "30"])
    with pytest.raises(SystemExit, match="SIN_CIERRE"):
        runpy.run_path(str(RAIZ / "salida" / "codificar.py"), run_name="__main__")
    # `--cierre` sin valor también es «sin cierre»
    monkeypatch.setattr(sys, "argv", ["blender", "--", str(tmp_path / "png"), str(tmp_path / "salida.mp4"), "--cierre"])
    with pytest.raises(SystemExit, match="SIN_CIERRE"):
        runpy.run_path(str(RAIZ / "salida" / "codificar.py"), run_name="__main__")


# ── el autotest: lo que esta prueba dice que ve, lo ve ───────────────────
def test_la_prueba_ve_un_formato_que_si_pasaria_sin_el_minimo(monkeypatch):
    """Si alguien baja el minimo a 0, `test_un_formato_sin_cierre_valido_no_se_puede_crear` tiene que fallar: se comprueba aquí que el valor 0 es
    precisamente lo que el minimo actual rechaza."""
    assert CIERRE_MINIMO_S > 0
    assert 0 < CIERRE_MINIMO_S <= min(cargar(n).cierre_s for n in fmt.disponibles())
