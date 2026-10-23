"""La caché no puede convertir una deformación molecular en un plano congelado."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def cargar(monkeypatch, *, deformacion=True, driver=False):
    curva = SimpleNamespace(evaluate=lambda f: float(f))
    accion = SimpleNamespace(fcurves=[curva])
    key = SimpleNamespace(animation_data=SimpleNamespace(action=accion, drivers=[1] if driver else []),
                          as_pointer=lambda: 9001)
    datos = SimpleNamespace(**{n: [] for n in (
        "objects", "cameras", "lights", "materials", "node_groups", "worlds",
        "scenes", "curves", "meshes")}, shape_keys=[key] if deformacion else [])
    monkeypatch.setitem(__import__("sys").modules, "bpy", SimpleNamespace(data=datos))
    ruta = Path(__file__).parents[1] / "salida" / "firmas.py"
    spec = importlib.util.spec_from_file_location("firmas_deformacion_aislada", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_una_camara_quieta_no_congela_el_mesh_deformado(monkeypatch):
    firmas = cargar(monkeypatch).de_escena([], 180)
    assert firmas[60] != firmas[90] != firmas[120]
    assert len(set(firmas.values())) == 182


def test_sin_cambios_la_cache_sigue_reutilizando(monkeypatch):
    firmas = cargar(monkeypatch, deformacion=False).de_escena([], 180)
    assert len(set(firmas.values())) == 1


def test_un_driver_de_shape_key_tambien_impide_reutilizar(monkeypatch):
    assert cargar(monkeypatch, driver=True).hay_controladores() is True
