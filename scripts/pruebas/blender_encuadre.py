"""`encuadre.distancia_visible` contra la proyección real de la cámara de Blender.

    blender -b --factory-startup --python scripts/pruebas/blender_encuadre.py

Un ligando ENTRE la cámara y el pivote sale recortado con `distancia`, que suma
la profundidad en vez de restarla. Aquí se comprueba, con una cámara de verdad,
que a la distancia de `distancia_visible` el punto más lateral cae justo en el
borde del cuadro y que `distancia` se queda corta.
"""
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from nucleo import encuadre  # noqa: E402

#: mathutils trabaja en float32: las tolerancias son de 1e-6.
fallos = []


def comprobar(nombre, cond):
    print(f"{'OK  ' if cond else 'FALLA'} {nombre}", flush=True)
    if not cond:
        fallos.append(nombre)


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
cam_data = bpy.data.cameras.new("cam")
cam_data.lens, cam_data.sensor_width, cam_data.sensor_fit = 50.0, 36.0, "HORIZONTAL"
cam = bpy.data.objects.new("cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam
aspecto = 1080 / 1920


def colocar(centro, az, el, dist):
    cam.location = encuadre.posicion(centro, az, el, dist)
    mirar = centro - cam.location
    cam.rotation_euler = mirar.to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()


def ndc(p):
    v = world_to_camera_view(sc, cam, p)
    return v.x, v.y, v.z


centro = Vector((0.0, 0.0, 0.0))
# camara en +X mirando a -X; un sujeto 0.5 por DELANTE del pivote (hacia la camara)
puntos = [Vector((0.5, 0.20, 0.0)), Vector((0.5, -0.20, 0.0))]
D = encuadre.distancia_visible(puntos, centro, 50.0, aspecto, 0.0, [0.0])
D_vieja = encuadre.distancia(puntos, centro, 50.0, aspecto, 0.0, [0.0])
th = math.tan(math.atan(18.0 / 50.0))
comprobar("fórmula: x/th − z", abs(D - (0.20 / th + 0.5)) < 1e-6)
comprobar("la fórmula antigua se queda corta con el sujeto delante", D_vieja < D - 0.9)

colocar(centro, 0.0, 0.0, D)
x, y, z = ndc(puntos[0])
comprobar("a esa distancia el punto lateral cae en el borde del cuadro",
          abs(x - 1.0) < 1e-3 or abs(x - 0.0) < 1e-3 or abs(ndc(puntos[1])[0] - 0.0) < 1e-3
          or abs(ndc(puntos[1])[0] - 1.0) < 1e-3)
comprobar("y todos caben", all(-1e-6 <= ndc(p)[0] <= 1 + 1e-6 and ndc(p)[2] > 0 for p in puntos))

colocar(centro, 0.0, 0.0, D_vieja)
comprobar("con la distancia antigua el sujeto se sale", any(
    not (0.0 <= ndc(p)[0] <= 1.0) or ndc(p)[2] <= 0 for p in puntos))

# detrás del pivote no hace falta alejarse más: el cuadro es más ancho allá
detras = [Vector((-0.5, 0.20, 0.0))]
comprobar("lo que queda detrás pide menos distancia",
          encuadre.distancia_visible(detras, centro, 50.0, aspecto, 0.0, [0.0])
          < encuadre.distancia_visible([Vector((0.0, 0.20, 0.0))], centro, 50.0, aspecto, 0.0, [0.0]))

# holgura mínima con la lente
pegado = [Vector((0.9, 0.0, 0.0))]
comprobar("nada queda pegado a la lente",
          encuadre.distancia_visible(pegado, centro, 50.0, aspecto, 0.0, [0.0], cerca=0.25) >= 0.9 + 0.25 - 1e-6)

# el margen multiplica la distancia
base = encuadre.distancia_visible(puntos, centro, 50.0, aspecto, 0.0, [0.0])
comprobar("el margen multiplica", abs(encuadre.distancia_visible(
    puntos, centro, 50.0, aspecto, 0.0, [0.0], 1.5) - 1.5 * base) < 1e-6)

if fallos:
    print(f"FALLOS: {fallos}", flush=True)
    sys.exit(1)
print("ENCUADRE_OK", flush=True)
