"""Interacciones ligando–receptor que se dibujan y se rotulan: polares y apolares.

Reúne lo que `contactos` mide y lo que el vídeo enseña, para que una pose
dockeada (Resultado, Búsqueda) tenga las mismas líneas y los mismos rótulos de
distancia que tenía el ligando cocristalizado:

- **polar**: proximidad N/O entre 2,4 y 3,5 Å; línea punteada.
- **apolar**: carbono apolar del ligando contra una cadena lateral, 2,8–4,5 Å;
  línea de trazos.

Cada clase tiene su color, pero ningún texto lo nombra: el rótulo dice POLAR o
APOLAR (el nombre de un color puede leerse como el de un elemento).

Se miden contra TODOS los residuos del bolsillo, no sólo contra los hotspots del
catálogo (muchos receptores no traen ninguno y la escena salía sin una sola
interacción); los hotspots que sí existan pasan primero (`preferidos`). Un
contacto por residuo y clase, como en el motor original.

Lo que NO es: no hay protonación ni ángulos donante–H–aceptor, así que «polar» es
una proximidad geométrica y no un puente de hidrógeno confirmado, y «apolar» es
compatible con asociación hidrofóbica, no una energía. El rótulo dice exactamente
eso (POLAR / APOLAR + la distancia medida) y las notas del acta lo declaran.
"""
from __future__ import annotations

#: Por clase y por pose: más líneas tapan el bolsillo y los rótulos no caben.
MAX_POR_TIPO = 3
#: Entorno del ligando donde se buscan átomos del receptor, en Å.
RADIO_A = 12.0

#: Tamaño del rótulo de una interacción respecto al de los demás rótulos 3D (que se calibraron
#: para una cámara más lejana): son dos líneas por interacción y hasta seis por pose.
ESCALA_ROTULO = 0.36

#: Colores de los rótulos, iguales a los de sus líneas (ámbar y turquesa); sólo en el render.
COLOR_POLAR = (1.0, 0.72, 0.20)
COLOR_APOLAR = (0.20, 0.82, 0.84)


def medir(receptor_mol, sujeto_mol, centro, *, nombres=None, cadenas=None,
          preferidos=(), max_por_tipo: int = MAX_POR_TIPO):
    """(elegidos, n_polares_medidos, n_apolares_medidos) de un ligando en su pose."""
    from . import contactos          # importa bpy: sólo cuando se mide, no al rotular
    polares = contactos.medir(receptor_mol, sujeto_mol, cerca_de=centro,
                              radio_a=RADIO_A, nombres=nombres, cadenas=cadenas)
    apolares = contactos.medir_hidrofobicos(receptor_mol, sujeto_mol, cerca_de=centro,
                                            radio_a=RADIO_A, nombres=nombres,
                                            cadenas=cadenas)
    elegidos = contactos.elegir_por_tipo(polares, apolares, max_por_tipo,
                                         preferidos=preferidos)
    return elegidos, len(polares), len(apolares)


def tipo(c) -> str:
    return "apolar" if c.tipo == "hidrofobico" else "polar"


def color(c):
    return COLOR_APOLAR if c.tipo == "hidrofobico" else COLOR_POLAR


def texto(c, con_cadena: bool = False) -> str:
    """Rótulo de una interacción: residuo, clase y distancia medida, en dos líneas.

    Sin tildes ni signos raros salvo la Å: es la tipografía del resto de rótulos.
    """
    nombre = (c.resname if c.resname and c.resname != "?" else "RES").upper()
    cadena = f":{c.cadena}" if con_cadena and c.cadena not in ("", "-1") else ""
    return f"{nombre}{c.resid}{cadena}\n{tipo(c).upper()}  {c.etiqueta}"


def registro(c) -> dict:
    """Lo que queda en el acta de cada interacción dibujada."""
    return {"tipo": tipo(c), "resname": c.resname, "resid": c.resid,
            "cadena": c.cadena, "distancia_a": round(c.distancia_a, 2)}


NOTA = ("Interacciones medidas por distancia sobre las coordenadas del paquete: polar = "
        "proximidad N/O de 2.4 a 3.5 A (linea punteada); apolar = carbono apolar del ligando contra "
        "cadena lateral de 2.8 a 4.5 A (linea de trazos). Un contacto por residuo y clase. NO es un "
        "PLIF: sin protonar, sin angulos donante-H-aceptor; no son puentes de hidrogeno "
        "confirmados ni energias de union.")
