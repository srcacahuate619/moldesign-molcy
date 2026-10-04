"""El número solicitado se aplica a Cycles; no ejecuta un video."""
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
import pytest
from variables import cpu
from variables.formato import cargar


def test_threads_default_and_single_processor(monkeypatch):
    monkeypatch.delenv("MOLCY_CPU_THREADS", raising=False)
    monkeypatch.setattr(cpu.os, "cpu_count", lambda: 8)
    assert cpu.hilos_cpu() == 7
    monkeypatch.setattr(cpu.os, "cpu_count", lambda: 1)
    assert cpu.hilos_cpu() == 1


@pytest.mark.parametrize("raw", ["0", "-1", "9", "dos", "1.5"])
def test_invalid_cpu_environment_is_rejected(monkeypatch, raw):
    monkeypatch.setattr(cpu.os, "cpu_count", lambda: 8)
    monkeypatch.setenv("MOLCY_CPU_THREADS", raw)
    with pytest.raises(ValueError): cpu.hilos_cpu()


def test_selected_threads_reach_blender_settings(monkeypatch):
    monkeypatch.setattr(cpu.os, "cpu_count", lambda: 8)
    monkeypatch.setenv("MOLCY_CPU_THREADS", "3")
    scene = SimpleNamespace(render=SimpleNamespace(image_settings=SimpleNamespace()),
                            cycles=SimpleNamespace(), eevee=SimpleNamespace())
    bpy = types.ModuleType("bpy"); bpy.context = SimpleNamespace(scene=scene)
    monkeypatch.setitem(sys.modules, "bpy", bpy)
    path = Path(__file__).resolve().parents[1] / "salida/render.py"
    spec = importlib.util.spec_from_file_location("molcy_threads_test", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.configurar(cargar("previsualizacion"), "cpu")
    assert scene.render.threads_mode == "FIXED"
    assert scene.render.threads == 3
    assert scene.cycles.device == "CPU"
