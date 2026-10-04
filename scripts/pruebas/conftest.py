"""Pruebas de la logica pura (sin Blender).

    python -m pytest scripts/pruebas -q

Lo que necesita `bpy` se prueba con los scripts `blender_*.py` de esta misma
carpeta, que se lanzan con `blender -b ... --python`.
"""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
