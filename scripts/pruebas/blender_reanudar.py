"""La reanudacion de `render.secuencia`, contra una escena real y sin video.

    blender -b --factory-startup --addons bl_ext.blender_org.molecularnodes \
        <caso>/blender/<algo>.blend --python scripts/pruebas/blender_reanudar.py -- <carpeta_temporal>

Rinde a 8 muestras y a la cuarta parte de resolucion: aqui interesa que
fotogramas se rehacen, no como salen.
"""
import sys
import tempfile
from pathlib import Path

import bpy

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from salida import render  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
base = Path(argv[0]) if argv else Path(tempfile.mkdtemp())
destino = base / "render_prueba_reanudar"
sc = bpy.context.scene
sc.eevee.taa_render_samples = 8
sc.render.resolution_percentage = 25
fallos = []


def comprobar(nombre, cond):
    print(f"{'OK  ' if cond else 'FALLA'} {nombre}", flush=True)
    if not cond:
        fallos.append(nombre)


# 1. corrida cortada: solo 3 de 5 fotogramas
info = render.secuencia(destino, [1, 2, 3], huella="h1")
comprobar("primera corrida rinde 3", info["rendidos"] == 3)

# 2. el proceso murio a mitad de escribir el 2
png2 = destino / "f_0002.png"
datos = png2.read_bytes()
png2.write_bytes(datos[: len(datos) // 2])
comprobar("PNG truncado detectado", not render.png_completo(png2))

# 3. se retoma con la misma huella: solo 2 (truncado), 4 y 5
info = render.secuencia(destino, [1, 2, 3, 4, 5], huella="h1")
comprobar("retoma: rinde 3 (2, 4 y 5)", info["rendidos"] == 3)
comprobar("retoma: reaprovecha 2 (1 y 3)", info["reanudados"] == 2)
comprobar("los 5 quedan enteros",
          all(render.png_completo(destino / f"f_{f:04d}.png") for f in range(1, 6)))

# 4. otra huella (cambio el codigo o el acta): se tira todo
info = render.secuencia(destino, [1, 2, 3, 4, 5], huella="h2")
comprobar("huella distinta: rinde los 5", info["rendidos"] == 5 and info["reanudados"] == 0)

# 5. sin huella, como antes: nunca reaprovecha
info = render.secuencia(destino, [1, 2], huella=None)
comprobar("sin huella: borra y rinde", info["rendidos"] == 2
          and not (destino / "f_0005.png").exists())

print("REANUDAR_PRUEBAS", "FALLAN: " + ", ".join(fallos) if fallos else "TODAS_OK", flush=True)
sys.exit(1 if fallos else 0)
