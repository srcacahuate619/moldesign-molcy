"""Rótulos 3D: tamaño constante entre planos y entrada escalonada de muchas interacciones.

    blender -b --factory-startup --python scripts/pruebas/blender_rotulos.py
"""
import sys
from pathlib import Path

import bpy  # noqa: F401  (rotulos importa bpy)

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from guiones import sitio_activo  # noqa: E402
from variables import formato as fmt  # noqa: E402
from variables import rotulos  # noqa: E402

fallos = []


def comprobar(nombre, cond):
    print(f"{'OK  ' if cond else 'FALLA'} {nombre}", flush=True)
    if not cond:
        fallos.append(nombre)


# 1. tamaño constante: el factor escala por la profundidad respecto a la nominal
z = {"a": 1.1, "b": 2.2, "c": 4.4}
f = rotulos._factor_de_tamano(z, True)
comprobar("con `igualar` el rótulo crece con su profundidad (tamaño en pantalla constante)",
          abs(f["a"] - 0.5) < 1e-9 and abs(f["b"] - 1.0) < 1e-9 and abs(f["c"] - 2.0) < 1e-9)
comprobar("sin `igualar` no se toca", all(v == 1.0 for v in rotulos._factor_de_tamano(z, False).values()))
comprobar("el factor está acotado", rotulos._factor_de_tamano({"x": 0.01, "y": 99.0}, True) == {"x": 0.35, "y": 2.0})

# 2. la entrada escalonada de las etiquetas de `sitio_activo`
formato = fmt.cargar("social_vertical")
# Los beats reales del vídeo de Resultado de 4CA8 (acta de la corrida, 360 fotogramas).
rangos = {"general": (1, 87), "aproximacion": (88, 143), "pausa_hotspots": (144, 206),
          "llegada_por_fundido": (207, 292), "exploracion": (293, 352), "reposo": (353, 360)}
a, b = rangos["llegada_por_fundido"]

pocos = sitio_activo.anotaciones(rangos, formato, formato.fps, n_sujeto=2)["sujeto"]
comprobar("con 2 rótulos la entrada es la de siempre (0,5 s entre ellos)",
          len(pocos) == 2 and pocos[1]["ventana"][0] - pocos[0]["ventana"][0] == max(4, int(0.5 * formato.fps)))

muchos = sitio_activo.anotaciones(rangos, formato, formato.fps, n_sujeto=7)["sujeto"]
comprobar("con 7 rótulos entran los 7", len(muchos) == 7)
entra_ultimo = max(c["fundido"][0][1] for c in muchos)
sale_primero = min(c["fundido"][1][0] for c in muchos)
comprobar("el último termina de aparecer antes de que el primero empiece a irse", entra_ultimo <= sale_primero)
comprobar("todos se van a la vez, antes de acabar la pausa",
          len({c["fundido"][1] for c in muchos}) == 1 and muchos[0]["ventana"][1] == b - 3)

if fallos:
    print(f"FALLOS: {fallos}", flush=True)
    sys.exit(1)
print("ROTULOS_OK", flush=True)
