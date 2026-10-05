"""El lema del cierre sigue el idioma de la interfaz de MolDesign; el cierre sigue siendo obligatorio en los dos.

`MOLCY_IDIOMA` es `es` o `en`: ausente o desconocido conserva el español, que no cambia ni un byte. El idioma entra en la huella, en la
carpeta de caché del cierre y en el manifiesto, y el sellador rechaza un manifiesto que no acredite el idioma pedido (un vídeo en inglés
no puede reutilizar el cierre en español).
"""
import ast
import hashlib
import json
import os
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
LEMA_ES = "EVIDENCIA ESTRUCTURAL REPRODUCIBLE"
LEMA_EN = "REPRODUCIBLE STRUCTURAL EVIDENCE"


def cargar(monkeypatch, idioma):
    """Ejecuta las constantes y la huella REALES de `marca/cierre.py`, sin emular el render de Blender."""
    if idioma is None:
        monkeypatch.delenv("MOLCY_IDIOMA", raising=False)
    else:
        monkeypatch.setenv("MOLCY_IDIOMA", idioma)
    fuente = SCRIPTS / "marca" / "cierre.py"
    arbol = ast.parse(fuente.read_text(encoding="utf-8"))
    nodos = [n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == "huella"]
    for n in arbol.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "LEMA" for t in n.targets):
            nodos.insert(0, n)
    espacio = {
        "__file__": str(fuente), "SCRIPTS": SCRIPTS, "AQUI": SCRIPTS / "marca", "MARCA": SCRIPTS.parent / "moldesign" / "assets" / "marca",
        "Path": Path, "hashlib": hashlib, "json": json, "os": os,
        "bpy": SimpleNamespace(app=SimpleNamespace(version_string="5.2.2")), "FUENTE_NOMBRE": None, "FUENTE_MONO": None,
    }
    idioma_py = SCRIPTS / "marca" / "idioma.py"
    if idioma_py.exists():
        espacio.update(runpy.run_path(str(idioma_py)))
    exec(compile(ast.Module(body=nodos, type_ignores=[]), str(fuente), "exec"), espacio)
    return espacio


@pytest.mark.parametrize("idioma, esperado", [("en", LEMA_EN), ("es", LEMA_ES), (None, LEMA_ES), ("xx", LEMA_ES)])
def test_el_lema_sigue_el_idioma_y_el_espanol_no_cambia(monkeypatch, idioma, esperado):
    assert cargar(monkeypatch, idioma)["LEMA"] == esperado


def test_la_huella_separa_los_idiomas(monkeypatch):
    formato = SimpleNamespace(ancho=720, alto=720, fps=30)
    es = cargar(monkeypatch, "es")["huella"](formato, 3.6, 64)
    en = cargar(monkeypatch, "en")["huella"](formato, 3.6, 64)
    assert es != en
    assert es == cargar(monkeypatch, "xx")["huella"](formato, 3.6, 64)


def test_la_carpeta_de_cache_del_lanzador_separa_los_idiomas():
    assert "${Formato}_${Renderizador}_${idioma}" in (SCRIPTS / "correr_caso.ps1").read_text(encoding="utf-8")


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_el_acta_registra_el_idioma_y_el_lema(monkeypatch, tmp_path, idioma):
    monkeypatch.setenv("MOLCY_IDIOMA", idioma)
    lema = LEMA_EN if idioma == "en" else LEMA_ES
    video = tmp_path / "v.mp4"
    video.write_bytes(b"video")
    acta = tmp_path / "acta.json"
    acta.write_text('{"fotogramas": 90}', encoding="utf-8")
    manifiesto = tmp_path / "manifiesto.json"
    manifiesto.write_text(json.dumps({"segundos": 3.6, "fps": 30, "fotogramas": 108, "idioma": idioma, "lema": lema}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["sellar_mp4.py", str(video), str(acta), "--cierre", str(manifiesto)])
    assert runpy.run_path(str(SCRIPTS / "salida" / "sellar_mp4.py"))["main"]() == 0
    cierre = json.loads(acta.read_text(encoding="utf-8"))["cierre"]
    assert cierre["idioma"] == idioma and cierre["lema"] == lema
