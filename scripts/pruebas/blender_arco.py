"""`oclusion.mejor_arco`: los giros cortos sólo entran cuando ningún giro grande esquiva el receptor.

    blender -b --factory-startup --python scripts/pruebas/blender_arco.py

La visibilidad se sustituye por una función sintética: despejada sólo dentro de
una ventana de azimut alrededor del punto de partida. Caso real: 4CA8, donde el
mejor arco de 90°–150° dejaba el ligando al 9 % durante la retirada.
"""
import math
import sys
from pathlib import Path

import bpy  # noqa: F401  (mejor_arco pide el grafo de dependencias)
from mathutils import Vector

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from nucleo import oclusion  # noqa: E402

fallos = []


def comprobar(nombre, cond):
    print(f"{'OK  ' if cond else 'FALLA'} {nombre}", flush=True)
    if not cond:
        fallos.append(nombre)


pivote = Vector((0.0, 0.0, 0.0))
AZ0, EL0, D0 = 90.0, -16.0, 2.0


def con_ventana(semiancho):
    """Despejado sólo a ±semiancho grados del azimut de partida."""
    def visibilidad(dianas, desde, dg=None, margen=None):
        az = math.degrees(math.atan2(desde.y - pivote.y, desde.x - pivote.x))
        desvio = abs((az - AZ0 + 180.0) % 360.0 - 180.0)
        return 1.0 if desvio <= semiancho else 0.05
    return visibilidad


original = oclusion.visibilidad
try:
    oclusion.visibilidad = con_ventana(180.0)           # todo despejado
    libre = oclusion.mejor_arco([pivote], pivote, AZ0, EL0, D0)
    comprobar("con todo despejado se queda un giro grande, como antes", abs(libre["span"]) >= 90.0)
    comprobar("y su mínimo es el máximo", libre["minimo"] == 1.0)

    oclusion.visibilidad = con_ventana(40.0)            # sólo ±40° despejados
    tapado = oclusion.mejor_arco([pivote], pivote, AZ0, EL0, D0)
    comprobar("si ningún giro grande esquiva el receptor se elige uno corto", abs(tapado["span"]) <= 60.0)
    comprobar("y deja el sujeto visible durante todo el arco", tapado["minimo"] >= 0.9)

    # candidatos explícitos: se respetan tal cual, sin añadir giros cortos
    explicitos = [{"span": 150.0, "el_fin": 0.0, "rampa": 0.3, "hump": 0.0}]
    fijo = oclusion.mejor_arco([pivote], pivote, AZ0, EL0, D0, candidatos=explicitos)
    comprobar("los candidatos explícitos no se amplían", fijo["span"] == 150.0)
finally:
    oclusion.visibilidad = original

if fallos:
    print(f"FALLOS: {fallos}", flush=True)
    sys.exit(1)
print("ARCO_OK", flush=True)
