"""VARIABLE: para donde es el video.

El formato es un eje aparte del guion a proposito. Los destinos tienen
requisitos incompatibles —una previsualizacion al pasar el cursor no puede
llevar texto ni durar 22 segundos, y una pieza vertical no cabe en 16:9— y
meterlos dentro del guion produce guiones x formatos archivos que se
desincronizan. Separandolos, es una matriz.
"""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import asdict, dataclass, field, replace


@dataclass(frozen=True)
class Formato:
    nombre: str
    descripcion: str

    ancho: int = 1920
    alto: int = 1080
    fps: int = 30
    segundos: float = 22.7           # presupuesto total a repartir entre beats
    escala_render: int = 100
    muestras: int = 128

    #: Resolucion de los mapas de sombra de EEVEE (`shadow_resolution_scale`).
    #: Vivia escondida en la plantilla de arte. Con la camara dentro del
    #: bolsillo, las sombras de las tres luces de area son el grueso del coste
    #: del primer plano (medido en 016 vertical: 5.9 -> 3.0 s por fotograma a
    #: 0.5, con el percentil 99.9 de la diferencia en 8/255).
    escala_sombras: float = 1.0

    #: Cierra el recorrido sobre si mismo. Obligatorio si el video se va a
    #: reproducir en bucle (previsualizacion al pasar el cursor).
    bucle: bool = False

    #: Etiquetas ancladas en 3D. Necesitan pausas de camara: si el formato no
    #: las admite, el reparto descarta los beats cuyo papel es `pausa`.
    etiquetas_3d: bool = True

    #: Rotulos pegados a la camara. Viven durante el movimiento.
    rotulos_pantalla: bool = False

    #: Segundos del cierre de marca (`marca/cierre.py`) que se pega al final.
    #: 0 = sin cierre: un bucle no termina, asi que no lleva firma al final.
    cierre_s: float = 0.0

    desenfoque_movimiento: bool = True
    #: Obturador del motion blur, en fracciones de fotograma.
    obturador: float = 0.35
    profundidad_de_campo: bool = True
    sello_procedencia: bool = True

    #: Escala del texto respecto al alto de cuadro. Un vertical se ve en un
    #: movil y necesita el doble.
    escala_texto: float = 1.0

    #: Escala de las etiquetas ancladas en 3D. None = la de `escala_texto`.
    #: El aumento de movil es para el texto de pantalla; en el mundo, a doble
    #: tamano las etiquetas se salen del cuadro angosto.
    escala_etiquetas_3d: float | None = None

    #: Papeles de beat que este formato acepta. None = todos.
    #: Un formato en bucle solo admite papeles que NO cambian la distancia de
    #: camara: si el video empieza en plano general y acaba en primer plano,
    #: no empalma consigo mismo por mucho que el arco sea de 360 grados.
    papeles: tuple[str, ...] | None = None

    @property
    def aspecto(self) -> float:
        return self.ancho / self.alto

    @property
    def fotogramas(self) -> int:
        return int(round(self.segundos * self.fps))

    @property
    def vertical(self) -> bool:
        return self.alto > self.ancho

    def resumen(self) -> dict:
        d = asdict(self)
        d["aspecto"] = round(self.aspecto, 3)
        d["fotogramas"] = self.fotogramas
        return d


# ── registro: se descubren solos, no hay lista que mantener ──────────────
def disponibles() -> dict[str, Formato]:
    import formatos
    out = {}
    for m in pkgutil.iter_modules(formatos.__path__):
        if m.name.startswith("_"):
            continue
        mod = importlib.import_module(f"formatos.{m.name}")
        f = getattr(mod, "FORMATO", None)
        if isinstance(f, Formato):
            out[f.nombre] = f
    return out


def cargar(nombre: str) -> Formato:
    todos = disponibles()
    if nombre not in todos:
        raise SystemExit(f"formato desconocido: {nombre}. "
                         f"Hay: {', '.join(sorted(todos))}")
    return todos[nombre]


def para_dispositivo(formato: Formato, dispositivo: str) -> Formato:
    """CPU: hasta tres segundos de escena y el cierre de marca del formato.

    Se aplica después de los controles para que ningún ajuste quite el l?mite.
    La pieza cuadrada CPU deja de ser un bucle y también incluye el outro.
    """
    if dispositivo not in {"cpu", "gpu"}:
        raise ValueError("Renderizador desconocido")
    if dispositivo == "gpu":
        return formato
    return replace(formato, segundos=min(formato.segundos, 3.0), bucle=False,
                   cierre_s=formato.cierre_s or 3.6)
