"""El renderizador debe detenerse antes de agotar la unidad de PNG."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


def _render(monkeypatch):
    monkeypatch.setitem(sys.modules, "bpy", types.ModuleType("bpy"))
    path = Path(__file__).resolve().parents[1] / "salida" / "render.py"
    spec = importlib.util.spec_from_file_location("molcy_render_disk_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_aborta_antes_de_llenar_el_volumen(monkeypatch, tmp_path: Path):
    render = _render(monkeypatch)
    monkeypatch.setattr(render.shutil, "disk_usage", lambda _: SimpleNamespace(free=render._ESPACIO_MINIMO))
    with pytest.raises(RuntimeError, match="ESPACIO_INSUFICIENTE"):
        render.comprobar_espacio(tmp_path, 1920, 1080)


def test_permite_un_fotograma_con_reserva_suficiente(monkeypatch, tmp_path: Path):
    render = _render(monkeypatch)
    monkeypatch.setattr(render.shutil, "disk_usage", lambda _: SimpleNamespace(free=2 * render._ESPACIO_MINIMO))
    render.comprobar_espacio(tmp_path, 1920, 1080)


def test_secuencia_no_invoca_blender_si_se_consumio_reserva(monkeypatch, tmp_path: Path):
    render = _render(monkeypatch)
    scene = SimpleNamespace(render=SimpleNamespace(resolution_x=720, resolution_y=720))
    render.bpy.context = SimpleNamespace(scene=scene)
    render.bpy.ops = SimpleNamespace(render=SimpleNamespace(
        render=lambda **_: pytest.fail("Blender no debe escribir otro fotograma")))
    monkeypatch.setattr(render.shutil, "disk_usage", lambda _: SimpleNamespace(free=render._ESPACIO_MINIMO))
    with pytest.raises(RuntimeError, match="ESPACIO_INSUFICIENTE"):
        render.secuencia(tmp_path / "cuadros", [1], huella="misma-escena")
    assert not list((tmp_path / "cuadros").glob("*.png"))
