"""GUION `sitio_activo`: presentar el receptor y lo que ocupa su sitio activo.

Declara beats con PESO relativo, no segundos: el formato reparte. El mismo
guion da 22.7 s en `biblioteca`, 3 s en bucle en `previsualizacion` (donde las
pausas se descartan solas por no admitir etiquetas) y 12 s en vertical.

Lo que se muestra en el sitio lo pone el SUJETO, no este archivo. Hoy es el
ligando cocristalizado; manana sera otro sin tocar nada de aqui.
"""
from __future__ import annotations

import math

from mathutils import Vector

from nucleo import encuadre
from nucleo.horneado import eo, salida_con_velocidad, ss
from variables.guion import Beat

NOMBRE = "sitio_activo"
DESCRIPCION = "Receptor completo, aproximacion al sitio, sujeto y exploracion."

LENTE_GENERAL, LENTE_PRIMER_PLANO = 35.0, 50.0
EL_GENERAL, EL_PRIMER_PLANO = 12.0, -22.0   # EL_PRIMER_PLANO es solo el respaldo
SWEEP_GENERAL = 338.0     # los 22 que faltan para el 360 los cierra la aproximacion

BEATS = [
    Beat("general", peso=5.5, papel="establecer"),
    Beat("aproximacion", peso=3.5, papel="aproximar"),
    Beat("pausa_hotspots", peso=4.0, papel="pausa"),
    # Se INTENTA con desplazamiento de entrada. Los 380 lo vetan por
    # `trayectoria_de_union`, asi que en la practica siempre cae al fundido.
    # Se deja declarado a proposito: es la prueba de que la prohibicion actua.
    Beat("llegada_sujeto", peso=5.4, papel="pausa",
         permisos=("trayectoria_de_union",), alternativa="llegada_por_fundido",
         requiere="sujeto"),
    # Antes 4.5. Se le quita casi un segundo y se le da a la pausa anterior.
    # Motivo: las etiquetas ancladas NO pueden sobrevivir a este plano —se
    # orientan una vez por pausa y con la camara orbitando se ladearian, que es
    # el fallo original de todo este montaje—, asi que cada segundo de mas aqui
    # es un segundo sin texto. Las lineas de contacto si siguen: son geometria,
    # no se ladean, y hacen de memoria visual de lo que se acaba de explicar.
    Beat("exploracion", peso=3.8, papel="explorar"),
    Beat("reposo", peso=0.5, papel="reposo", minimo_fotogramas=2),
]


#: Fantasma del portal (v4). El radio del cilindro llega medido —la dispersion
#: de las dianas alrededor del pivote— y aqui solo se le da aire. El piso es la
#: opacidad minima de la cascara interpuesta: dibuja la silueta sin tapar el
#: sitio. Ni cero (desaparece, que es lo que se venia a arreglar) ni alto
#: (el bolsillo deja de leerse).
RADIO_FANTASMA = 1.15
PISO_FANTASMA = 0.12

#: El fantasma se apaga al acercarse al pivote: a estas fracciones de la
#: distancia camara->pivote ya no hay fantasma, asi el propio sitio activo
#: queda opaco. La banda es ancha a proposito; la silueta entra y sale de a
#: poco en vez de recortarse contra el bolsillo.
FANTASMA_CERCA, FANTASMA_LEJOS = 0.78, 0.995


def _portal_fantasma(K, pos, distancia: float, fuerza: float, medidas) -> dict:
    """Parametros del cilindro camara->pivote para un fotograma.

    El eje se entrega ya resuelto —direccion y largo— porque el shader no tiene
    por que repetir la resta. `r0`/`r1` son el borde suave del radio, `t1`/`t2`
    el borde suave del fondo: dentro de ambos, fantasma; fuera, normal.
    """
    radio = (medidas.get("radio_portal") or distancia * 0.35) * RADIO_FANTASMA
    eje = K - pos
    largo = max(eje.length, 1e-6)
    eje = eje / largo
    return {"fuerza": max(0.0, min(1.0, float(fuerza))),
            "piso": PISO_FANTASMA,
            "r0": radio * 0.72, "r1": radio * 1.08,
            "t1": largo * FANTASMA_CERCA, "t2": largo * FANTASMA_LEJOS,
            "campos": (pos.x, pos.y, pos.z),
            "dir": (eje.x, eje.y, eje.z)}


def estados(medidas, rangos, n_frames, formato, experimental=False):
    """Estado de camara y material por fotograma."""
    P = medidas["centro_general"]
    K = medidas["pivote"]
    D1 = medidas["dist_general"]
    D0 = medidas["dist_primer_plano"]
    A0 = medidas["azimut"]
    # La elevacion del primer plano ya no es constante: la mide la pose heroe.
    EL_CERCA = medidas.get("elevacion", EL_PRIMER_PLANO)
    # En bucle, la altura de la orbita tambien se mide (ver bug del punto ciego)
    EL_LEJOS = medidas.get("elevacion_general", EL_GENERAL)
    arco = medidas["arco"]
    grad_lejos, grad_cerca = medidas["gradiente_general"], medidas["gradiente_cerca"]
    diso_cerca = medidas["disolucion_cerca"]

    fin = lambda b: rangos[b][1] if b in rangos else -1        # noqa: E731
    hay = lambda b: b in rangos                                 # noqa: E731
    beat_sujeto = "llegada_sujeto" if hay("llegada_sujeto") else "llegada_por_fundido"

    out = []
    for f in range(1, n_frames + 1):
        fantasma = 0.0
        if hay("general") and f <= fin("general"):
            a, b = rangos["general"]
            if formato.bucle:
                # Un fotograma MENOS de vuelta completa: si el ultimo cayera
                # sobre el primero, el bucle repetiria un fotograma y se veria
                # un tartamudeo en cada vuelta. Y sin suavizado: un bucle no
                # puede arrancar ni frenar, tiene que girar parejo.
                u = (f - a) / (b - a + 1)
                az = A0 - 360.0 * u
            else:
                u = (f - a) / max(b - a, 1)
                az = A0 - SWEEP_GENERAL * salida_con_velocidad(u, 0.2046)
            el, D, T, L, fs = EL_LEJOS, D1, P.copy(), LENTE_GENERAL, 8.0 if experimental else 5.6
            grad, cn = grad_lejos, (0.02, 0.05)
        elif hay("aproximacion") and f <= fin("aproximacion"):
            a, b = rangos["aproximacion"]
            v = (f - a + 1) / (b - a + 1)
            s = ss(v)
            az = (A0 - SWEEP_GENERAL) - 22.0 * eo(v)
            el = EL_LEJOS + (EL_CERCA - EL_LEJOS) * s
            D = D1 + (D0 - D1) * s
            T = P + (K - P) * s
            L = LENTE_GENERAL + (LENTE_PRIMER_PLANO - LENTE_GENERAL) * s
            grad = grad_lejos + (grad_cerca - grad_lejos) * s
            if experimental:
                fs = (5.6 + (4.8 - 5.6) * ss(v / 0.55)) if v < 0.55 \
                    else 4.8 + (14.0 - 4.8) * ss((v - 0.55) / 0.45)
                # El fantasma entra con el push-in: la cascara empieza a
                # dibujarse cuando la camara ya esta encima del sitio.
                fantasma = ss(max(0.0, min(1.0, (v - 0.40) / 0.60)))
                cn = (0.0, 0.05)
            elif v < 0.70:
                fs = (5.6 + (2.4 - 5.6) * ss(v / 0.55)) if v < 0.55 \
                    else 2.4 + (22.0 - 2.4) * ss((v - 0.55) / 0.45)
                g = ss(v / 0.70)
                cn = (0.02 + (D0 * 0.17 - 0.02) * g, 0.05 + (D0 * 0.45 - 0.05) * g)
            else:
                fs = (5.6 + (2.4 - 5.6) * ss(v / 0.55)) if v < 0.55 \
                    else 2.4 + (22.0 - 2.4) * ss((v - 0.55) / 0.45)
                h = ss((v - 0.70) / 0.30)
                cn = (D0 * 0.17 + (diso_cerca[0] - D0 * 0.17) * h,
                      D0 * 0.45 + (diso_cerca[1] - D0 * 0.45) * h)
        elif hay("exploracion") and f < rangos["exploracion"][0]:
            az, el, D, T = A0 - SWEEP_GENERAL - 22.0, EL_CERCA, D0, K.copy()
            L, fs, grad = LENTE_PRIMER_PLANO, 22.0, grad_cerca
            cn = (0.0, 0.05) if experimental else diso_cerca
            fantasma = 1.0
        elif hay("exploracion") and f <= fin("exploracion"):
            a, b = rangos["exploracion"]
            w = (f - a + 1) / (b - a + 1)
            s = ss(w)
            az = (A0 - SWEEP_GENERAL - 22.0) + arco["span"] * s
            el = EL_CERCA + (arco["el_fin"] - EL_CERCA) \
                * ss(min(w / arco["rampa"], 1.0)) + arco["hump"] * math.sin(math.pi * w)
            D = D0 * (1.0 + 0.07 * s) + D0 * 0.12 * math.sin(math.pi * w)
            # Micro-respiracion: el horneado es matematicamente exacto y el ojo
            # lo lee como "CG". Dos senos incomensurables (7.3 y 4.1 vueltas por
            # plano) dan una deriva de +-0.3% que no se percibe como oscilacion
            # pero quita la rigidez. No toca geometria, tiempos ni encuadre.
            D *= 1.0 + 0.003 * (math.sin(w * 7.3 * math.tau)
                                + 0.6 * math.sin(w * 4.1 * math.tau + 1.7))
            T, L, grad = K.copy(), LENTE_PRIMER_PLANO, grad_cerca
            if experimental:
                if w < 0.18:
                    fs = 7.0 + (4.8 - 7.0) * ss(w / 0.18)
                elif w < 0.82:
                    fs = 4.8
                else:
                    fs = 4.8 + (7.0 - 4.8) * ss((w - 0.82) / 0.18)
                # El receptor recupera opacidad durante el primer 20% de la
                # orbita final: el fantasma se apaga con el mismo suavizado.
                h = ss(min(w / 0.20, 1.0))
                fantasma = 1.0 - h
                cn = (0.0, 0.05)
            else:
                if w < 0.15:
                    fs = 22.0 + (3.2 - 22.0) * ss(w / 0.15)
                elif w < 0.85:
                    fs = 3.2
                else:
                    fs = 3.2 + (8.0 - 3.2) * ss((w - 0.85) / 0.15)
                h = ss(min(w / 0.2, 1.0))
                cn = (diso_cerca[0] * (1 + 0.8 * h),
                      diso_cerca[1] * (1 + 0.8 * h))
        else:
            az = (A0 - SWEEP_GENERAL - 22.0) + (arco["span"] if hay("exploracion") else 0.0)
            el = arco["el_fin"] if hay("exploracion") else EL_CERCA
            D, T = D0 * 1.07, K.copy()
            L, fs, grad = LENTE_PRIMER_PLANO, 8.0, grad_cerca
            cn = (0.0, 0.05) if experimental else (diso_cerca[0] * 1.8, diso_cerca[1] * 1.8)

        if not formato.profundidad_de_campo:
            fs = 32.0
        estado = dict(pos=encuadre.posicion(T, az, el, D), objetivo=T,
                      lente=L, diafragma=fs, gradiente=grad,
                      diso0=cn[0], diso1=cn[1], dist=D,
                      giro=math.radians(az - A0))
        if experimental:
            estado["portal"] = _portal_fantasma(K, estado["pos"], D, fantasma,
                                                medidas)
        out.append(estado)
    return out


def anotaciones(rangos, formato, fps, n_sujeto: int = 1):
    """Cuando entra y sale cada rotulo. Solo dentro de pausas."""
    fade = max(4, int(0.40 * fps))
    paso = max(4, int(0.40 * fps))
    plan = {"hotspots": [], "sujeto": []}

    if formato.etiquetas_3d and "pausa_hotspots" in rangos:
        a, b = rangos["pausa_hotspots"]
        inicio = a + max(2, int(0.2 * fps))
        for i in range(3):
            e0 = inicio + i * paso
            if e0 + fade >= b - 3:
                break
            plan["hotspots"].append({
                "ventana": (e0, b - 3),
                "fundido": [(e0, e0 + fade, 0, 1), (b - fade - 3, b - 3, 1, 0)]})

    clave = "llegada_sujeto" if "llegada_sujeto" in rangos else "llegada_por_fundido"
    if formato.etiquetas_3d and clave in rangos:
        a, b = rangos[clave]
        # El nombre del sujeto entra primero; las distancias medidas detras, una
        # cada medio segundo, para que se lean en orden y no de golpe.
        base = a + max(3, int(1.4 * fps))
        for i in range(max(1, n_sujeto)):
            e0 = base + i * max(4, int(0.5 * fps))
            if e0 + fade >= b - 3:
                break
            plan["sujeto"].append({
                "ventana": (e0, b - 3),
                "fundido": [(e0, e0 + fade, 0, 1), (b - fade - 3, b - 3, 1, 0)]})
    return plan


def aparicion_de_contactos(rangos, fps):
    """Las lineas de contacto entran DESPUES del ligando, nunca antes.

    Un contacto es una relacion entre dos cosas: dibujarlo antes de que exista
    la segunda deja lineas punteadas apuntando al vacio. Se probo encenderlas
    durante la aproximacion —que es cuando mas ayudan a leer el bolsillo— y el
    resultado era justo eso: doradas flotando hacia ningun sitio durante cuatro
    segundos, porque el ligando no llega hasta su propio beat.

    Entran cuando el ligando ya esta al 60% de su fundido, y acaban de encender
    antes de que entren sus etiquetas de distancia.
    """
    clave = "llegada_sujeto" if "llegada_sujeto" in rangos else "llegada_por_fundido"
    if clave not in rangos:
        return None
    a, b = rangos[clave]
    i0 = a + max(3, int(0.5 * fps))
    i1 = min(b - 2, i0 + max(6, int(0.7 * fps)))
    return {"ventana": (i0, None), "fundido": [(i0, i1, 0, 1)]}


def titulo(rangos, formato, fps):
    """Rotulo de PANTALLA durante el plano general.

    El formato `social_vertical` declaraba `rotulos_pantalla: true` y
    `escala_texto: 2.0` y ningun guion creaba uno: el flag y la escala se
    desperdiciaban y el vertical salia sin gancho ni identificacion.

    Va en el plano general y no en las pausas por dos razones: ahi la camara
    orbita —y un rotulo de pantalla es justo la clase que sobrevive al
    movimiento— y la distancia de enfoque es constante durante todo el beat,
    asi que el texto se puede colocar EN FOCO sin animar su profundidad.
    """
    if not formato.rotulos_pantalla or "general" not in rangos:
        return None
    a, b = rangos["general"]
    entra = a + max(3, int(0.35 * fps))
    sale = b - max(4, int(0.45 * fps))
    if sale <= entra + 4:
        return None
    fade = max(4, int(0.35 * fps))
    return {"ventana": (entra, sale),
            "fundido": [(entra, entra + fade, 0, 1), (sale - fade, sale, 1, 0)]}


def aparicion_del_sujeto(rangos, fps):
    """Ventana y fundido del sujeto. Sin desplazamiento: el contrato lo veta."""
    clave = "llegada_sujeto" if "llegada_sujeto" in rangos else "llegada_por_fundido"
    if clave not in rangos:
        return None
    a, b = rangos[clave]
    return {"ventana": (a, None),
            "fundido": [(a, a + max(4, int(0.8 * fps)), 0, 1)]}


def aparicion_de_hotspots(rangos, fps):
    if "aproximacion" not in rangos:
        return {"ventana": (1, None), "fundido": [(1, 2, 1, 1)]}
    a, b = rangos["aproximacion"]
    i0 = a + int(0.32 * (b - a))
    return {"ventana": (i0, None),
            "fundido": [(i0, a + int(0.76 * (b - a)), 0, 1)]}
