"""VARIABLE: que hay en el sitio activo.

Hoy es el ligando cocristalizado. Manana puede ser un ensamble de poses o la
nube de una busqueda de Montecarlo. Un sujeto declara tres cosas:

    disponible(paq) -> (bool, razon)   ¿el contrato trae el dato?
    cargar(paq)     -> Montado         objetos, materiales y anclas
    anotaciones()   -> list[dict]      que rotular, y con que texto

La comprobacion de disponibilidad es parte del contrato, no una comodidad: el
maestro puede listar que sujetos admite cada receptor y por que, antes de
gastar media hora de render.
"""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import Any

from nucleo.ciencia import Prohibido


def _vector_cero():
    """mathutils solo existe dentro de Blender: este fichero lo lee tambien la
    interfaz (que no lo tiene), asi que el Zero se construye de forma perezosa.
    """
    from mathutils import Vector
    return Vector()


@dataclass
class Contexto:
    """Lo que el sujeto necesita saber de la escena ya montada.

    Sin esto un sujeto no puede medir nada contra el receptor, y medir contra el
    receptor es justo lo que convierte un modelo bonito en una afirmacion
    cientifica (contactos, coordinacion, huecos).
    """
    receptor: Any = None
    arte: dict = field(default_factory=dict)
    pivote: Vector = field(default_factory=_vector_cero)


@dataclass
class Montado:
    """Lo que un sujeto deja en la escena."""
    objetos: list[Any] = field(default_factory=list)
    materiales: list[Any] = field(default_factory=list)
    #: Puntos que la camara tiene que dejar ver, en coordenadas de mundo.
    dianas: list[Vector] = field(default_factory=list)
    #: Dianas del PLANO GENERAL: lo del sujeto que ese plano debe contener
    #: p.ej. la caja de acoplamiento de la escena x, que puede ser mas ancha
    #: que el encuadre ceńido del receptor. Vacio = el receptor manda.
    dianas_generales: list[Vector] = field(default_factory=list)
    #: (id, texto, posicion) para las etiquetas ancladas.
    anclas: list[tuple[str, str, Vector]] = field(default_factory=list)
    #: Objetos que aparecen DESPUES del sujeto: se funden aparte. En `sitio_activo`
    #: son las lineas de contacto; en `x`, las poses de Vina. No es lo que retira el
    #: interruptor `contactos`: eso es `lineas_contacto`.
    secundarios: list[Any] = field(default_factory=list)
    materiales_secundarios: list[Any] = field(default_factory=list)
    #: Las lineas de contacto que el sujeto dibujo, y nada mas: lo unico que se
    #: retira (con sus rotulos `dist*`) si se apagan los contactos. Una linea puede
    #: estar tambien en `secundarios`. Sus materiales, en `extra["materiales_contacto"]`.
    lineas_contacto: list[Any] = field(default_factory=list)
    #: Datos para el GUION (p.ej. la traza aceptada que anima el caminante):
    #: nombres de objetos y coordenadas de mundo, nada de medidas.
    extra: dict = field(default_factory=dict)
    #: Lo medido, para el acta.
    medido: dict = field(default_factory=dict)
    notas: list[str] = field(default_factory=list)


class SujetoNoDisponible(RuntimeError):
    """El paquete de escena no trae lo que este sujeto necesita."""


def apagar_contactos(montado: Montado, retirar) -> dict[str, int]:
    """El interruptor `contactos` apagado: no se dibujan las lineas ni sus rotulos.

    Se retiran SOLO las lineas que el sujeto declaro en `lineas_contacto` y las
    anclas `dist*` (sus rotulos de distancia). El ligando, las poses y lo medido
    se quedan: apagar una capa no cambia lo que la escena afirma
    (`variables/controles.py`). Antes se borraba `secundarios`, que en la escena
    `x` son las poses de Vina: el ligando desaparecia y las lineas seguian.

    `retirar(objeto)` lo quita de la escena (en Blender,
    `bpy.data.objects.remove(o, do_unlink=True)`); se recibe como argumento para
    que esto se pruebe sin Blender. Devuelve cuantas lineas y rotulos se quitaron.
    """
    lineas = list(montado.lineas_contacto)
    # Primero se dejan de citar y despues se borran: un objeto ya borrado no se
    # puede ni comparar (Blender lanza ReferenceError al tocarlo).
    montado.secundarios[:] = [o for o in montado.secundarios if o not in lineas]
    montado.objetos[:] = [o for o in montado.objetos if o not in lineas]
    de_lineas = list(montado.extra.get("materiales_contacto") or ())
    montado.materiales_secundarios[:] = [m for m in montado.materiales_secundarios
                                         if m not in de_lineas]
    antes = len(montado.anclas)
    montado.anclas[:] = [a for a in montado.anclas if not a[0].startswith("dist")]
    montado.lineas_contacto.clear()
    for o in lineas:
        retirar(o)
    return {"lineas": len(lineas), "rotulos": antes - len(montado.anclas)}


# ── registro ─────────────────────────────────────────────────────────────
def disponibles() -> dict:
    import sujetos
    out = {}
    for m in pkgutil.iter_modules(sujetos.__path__):
        if m.name.startswith("_"):
            continue
        mod = importlib.import_module(f"sujetos.{m.name}")
        if hasattr(mod, "ID") and hasattr(mod, "disponible"):
            out[mod.ID] = mod
    return out


def cargar(nombre: str):
    todos = disponibles()
    if nombre not in todos:
        raise SystemExit(f"sujeto desconocido: {nombre}. "
                         f"Hay: {', '.join(sorted(todos))}")
    return todos[nombre]


def inventario(paq) -> dict[str, dict]:
    """Que sujetos admite ESTE receptor, y por que no los demas."""
    out = {}
    for nombre, mod in sorted(disponibles().items()):
        ok, razon = mod.disponible(paq)
        out[nombre] = {"disponible": ok, "razon": razon,
                       "descripcion": getattr(mod, "DESCRIPCION", "")}
    return out
