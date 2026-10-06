"""La pasada del título sólo dibuja rótulos: ni el sujeto animado ni las curvas.

    blender -b --factory-startup --python scripts/pruebas/blender_titulo.py -- <carpeta_temporal>

Caso real (Búsqueda de 1J38): el ligando tiene `hide_render` ANIMADO y la caja es una
CURVA. `pasada_titulo` sólo apagaba mallas con `hide_render`, que la animación
pisa al evaluarse, así que el ligando salía en la capa del título y, por ir más
cerca de la cámara, tapaba el rótulo. Aquí hay un cubo animado, una curva y un
rótulo; la capa del título tiene que traer sólo el rótulo.
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
fallos = []


def comprobar(nombre, cond):
    print(f"{'OK  ' if cond else 'FALLA'} {nombre}", flush=True)
    if not cond:
        fallos.append(nombre)


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = 96, 96
sc.render.resolution_percentage = 100
sc.eevee.taa_render_samples = 4
sc.frame_start, sc.frame_end = 1, 3

cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
sc.collection.objects.link(cam)
cam.location = (0.0, -6.0, 0.0)
cam.rotation_euler = (1.5707963, 0.0, 0.0)
sc.camera = cam

# 1. el sujeto: un cubo grande que tapa el centro, con hide_render ANIMADO
bpy.ops.mesh.primitive_cube_add(size=3.0, location=(0.0, -2.0, 0.0))
cubo = bpy.context.object
cubo.name = "Sujeto"
for f in (1, 3):
    cubo.hide_render = False
    cubo.keyframe_insert("hide_render", frame=f)

# 2. una curva con volumen (como la caja de acoplamiento)
curva = bpy.data.curves.new("caja", "CURVE")
curva.dimensions = "3D"
curva.bevel_depth = 0.3
spline = curva.splines.new("POLY")
spline.points.add(1)
spline.points[0].co = (-2.0, -1.0, 0.0, 1.0)
spline.points[1].co = (2.0, -1.0, 0.0, 1.0)
caja = bpy.data.objects.new("Caja", curva)
sc.collection.objects.link(caja)

# 3. el rótulo (FONT), a la profundidad del sujeto
texto = bpy.data.curves.new("rot", "FONT")
texto.body = "OK"
texto.size = 0.6
rotulo = bpy.data.objects.new("Rot_prueba", texto)
sc.collection.objects.link(rotulo)
rotulo.location = (-1.4, 0.0, 1.2)
rotulo.rotation_euler = (1.5707963, 0.0, 0.0)

destino = base / "titulo_prueba"
info = render.pasada_titulo(destino, ["Rot_prueba"], (1, 2))
comprobar("rinde dos fotogramas", info.get("fotogramas") == 2)

png = destino / "f_0001.png"
comprobar("existe el PNG", png.exists())
img = bpy.data.images.load(str(png))
w, h = img.size
px = list(img.pixels)


def alfa(x, y):
    return px[(y * w + x) * 4 + 3]


opacos = sum(1 for i in range(3, len(px), 4) if px[i] > 0.05)
comprobar("la capa está casi vacía (sólo el rótulo)", opacos / (w * h) < 0.12)
comprobar("el centro, donde está el cubo, es transparente", alfa(w // 2, h // 2) < 0.01)
comprobar("el centro de la curva es transparente", alfa(w // 2, int(h * 0.42)) < 0.01)
comprobar("el rótulo SÍ está", opacos > 5)

# lo apagado se restaura y la animación vuelve
comprobar("el cubo conserva su animación", cubo.animation_data and cubo.animation_data.action is not None)
comprobar("el cubo vuelve a rendirse", cubo.hide_render is False)

if fallos:
    print(f"FALLOS: {fallos}", flush=True)
    sys.exit(1)
print("TITULO_OK", flush=True)
