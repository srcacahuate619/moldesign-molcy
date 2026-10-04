"""FORMATO: la pieza de la biblioteca cinematografica.

La completa: 16:9 a 1080p, con etiquetas ancladas y sus pausas. Es el formato
que aprobo el caso 001.
"""
from variables.formato import Formato

FORMATO = Formato(
    nombre="biblioteca",
    descripcion="Pieza completa 16:9 con etiquetas 3D. ~28 min de render.",
    ancho=1920, alto=1080, fps=30, segundos=22.7,
    # 64 y no 128: medido sobre 1HWK, el coste escala lineal con las muestras
    # y a 64 no se ve grano en la cinta. 128 duplicaba el tiempo sin ganancia
    # visible. El encuadre correcto (camara DENTRO del bolsillo, con la
    # disolucion por transparencia activa) ya es el caso caro de EEVEE.
    muestras=64, escala_render=100,
    bucle=False, etiquetas_3d=True, rotulos_pantalla=True,
    desenfoque_movimiento=True, profundidad_de_campo=True,
    # La firma va al final (cierre 3D de marca), no quemada arriba.
    sello_procedencia=False, cierre_s=4.4, escala_texto=1.15,
)
