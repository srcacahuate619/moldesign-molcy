"""GUION `x`: la busqueda de Montecarlo de Vina sobre la caja de acoplamiento.

Sujeto fijo: `busqueda_montecarlo` (lo fija el propio guion: lo que se cuenta
AQUI no es "lo que hay en el bolsillo", es una magnitud que evoluciona en el
tiempo dentro de la caja que corrio el motor).

Sin beats de pausa: la escena no es un bolsillo que leer con camara quieta,
es una busqueda en marcha. Los numeros (dimensiones de la caja, afinidades,
RMSD) van en etiquetas y rotulos, no en movimientos de camara.

Los tres actos: enmarcar el sitio (general), dibujar la caja y la esfera de
evidencia (caja), dejar correr el muestreo (busqueda) y revelar las poses que
el motor devolvio (convergencia). Si el paquete no trae docking, los beats de
la busqueda se omiten con su motivo en el acta, y queda el plano general.
"""
from __future__ import annotations

import math

from nucleo.horneado import ss
from variables.guion import Beat

NOMBRE = "x"
DESCRIPCION = "La caja de acoplamiento real y la busqueda de Montecarlo en ella."
SUJETO = "busqueda_montecarlo"

#: Los lee `maestro.medir`, que es agnostico del guion pero no de sus constantes.
LENTE_GENERAL, LENTE_PRIMER_PLANO = 35.0, 50.0
EL_GENERAL, EL_PRIMER_PLANO = 12.0, -22.0
SWEEP_GENERAL = 338.0
#: Lo que el guion va a usar de verdad: contexto sobrio alrededor del sitio,
#: no el despegue completo del estandar.
BARRIDO = 60.0
DRIFT_BUSQUEDA = 24.0

#: El primer plano de esta escena encuadra la CAJA de acoplamiento (el
#: volumen donde corrió la búsqueda), que puede ser MÁS ancha que el núcleo
#: del receptor: en `convergencia` la cámara da un paso atrás a propósito.
#: Salida/control lo tolera SOLO cuando el guion lo declara aqui.
QC_PERMITE_ALEJAMIENTO = True
QC_DIANAS_FACTOR = 0.9

BEATS = [
    Beat("general", peso=2.5, papel="establecer"),
    Beat("caja", peso=2.5, papel="aproximar", requiere="sujeto"),
    Beat("busqueda", peso=5.0, papel="explorar", requiere="sujeto"),
    Beat("convergencia", peso=3.5, papel="explorar", requiere="sujeto"),
    Beat("reposo", peso=0.5, papel="reposo", minimo_fotogramas=2),
]


def estados(medidas, rangos, n_frames, formato, experimental=False):
    # experimental=False siempre: la variante de look del estandar no aplica a
    # una escena que cuenta computacion, no geometria del bolsillo.
    # encuadre viaja dentro: importarlo arriba obligaria a mathutils en la
    # interfaz, que no lo tiene (ver variables/controles.py).
    from nucleo import encuadre
    P = medidas["centro_general"]
    K = medidas["pivote"]
    D1 = medidas["dist_general"]
    D0 = medidas["dist_primer_plano"]
    A0 = medidas["azimut"]
    EL_CERCA = medidas.get("elevacion", EL_PRIMER_PLANO)
    EL_LEJOS = medidas.get("elevacion_general", EL_GENERAL)
    grad_lejos = medidas["gradiente_general"]
    grad_cerca = medidas["gradiente_cerca"]
    # La disolucion del estandar escala con D0; aqui el primer plano encuadra
    # la CAJA entera (mas ancha), y escalar con ella haria desaparecer el
    # receptor alrededor del sitio. Se mida contra el radio de las dianas.
    rn = medidas.get("radio_portal") or medidas["radio_dianas"] or D0 * 0.35
    cn_cerca = (rn * 0.12, rn * 0.30)

    fin = lambda b: rangos[b][1] if b in rangos else -1        # noqa: E731
    hay = lambda b: b in rangos                                 # noqa: E731
    punto = encuadre.posicion

    out = []
    for f in range(1, n_frames + 1):
        if hay("general") and f <= fin("general"):
            a, b = rangos["general"]
            u = (f - a) / max(b - a, 1)
            az = A0 - BARRIDO * ss(u)
            T, D, L, fs = P.copy(), D1, LENTE_GENERAL, 5.6
            el, grad, cn = EL_LEJOS, grad_lejos, (0.02, 0.05)
        elif hay("caja") and f <= fin("caja"):
            # La aproximacion: la camara cae sobre la caja y se queda quieta
            # en azimut — lo que vendra es el muestreo, y el ojo no debe andar.
            a, b = rangos["caja"]
            v = (f - a + 1) / (b - a + 1)
            s = ss(v)
            az = A0 - BARRIDO - 22.0 * ss(min(v * 1.2, 1.0))
            el = EL_LEJOS + (EL_CERCA - EL_LEJOS) * s
            D = D1 + (D0 - D1) * s
            T = P + (K - P) * s
            L = LENTE_GENERAL + (LENTE_PRIMER_PLANO - LENTE_GENERAL) * s
            grad = grad_lejos + (grad_cerca - grad_lejos) * s
            fs = 5.6
            g = ss(min(v / 0.7, 1.0))
            cn = (0.02 + (cn_cerca[0] - 0.02) * g, 0.05 + (cn_cerca[1] - 0.05) * g)
        elif hay("busqueda") and f <= fin("busqueda"):
            # Deriva lenta y minima: el relato esta dentro de la caja.
            a, b = rangos["busqueda"]
            w = (f - a + 1) / (b - a + 1)
            az = A0 - BARRIDO - 22.0 + DRIFT_BUSQUEDA * ss(w)
            el = EL_CERCA
            D = D0 * (1.0 + 0.02 * math.sin(math.pi * w))
            T, L, grad = K.copy(), LENTE_PRIMER_PLANO, grad_cerca
            fs = 4.0
            cn = cn_cerca
        elif hay("convergencia") and f <= fin("convergencia"):
            # Se abre un paso para leer poses junto a la caja ya muestreada.
            a, b = rangos["convergencia"]
            w = (f - a + 1) / (b - a + 1)
            s = ss(w)
            az = A0 - BARRIDO - 22.0 + DRIFT_BUSQUEDA + 6.0 * s
            el = EL_CERCA
            D = D0 * (1.0 + 0.15 * s)
            T, L, grad = K.copy(), LENTE_PRIMER_PLANO, grad_cerca
            fs = 5.6 + 2.4 * s
            cn = (cn_cerca[0] * (1 + 0.5 * s), cn_cerca[1] * (1 + 0.5 * s))
        else:
            # reposo: se sostiene el estado con el que cerro la convergencia
            az = A0 - BARRIDO - 22.0 + (DRIFT_BUSQUEDA if hay("busqueda") else 0.0) \
                + (6.0 if hay("convergencia") else 0.0)
            el = EL_CERCA
            D = D0 * 1.15 if hay("convergencia") else D0
            T, L, grad = K.copy(), LENTE_PRIMER_PLANO, grad_cerca
            fs = 8.0
            cn = (cn_cerca[0] * 1.6, cn_cerca[1] * 1.6)

        if not formato.profundidad_de_campo:
            fs = 32.0
        pos = punto(T, az, el, D)
        out.append(dict(pos=pos, objetivo=T, lente=L, diafragma=fs,
                        gradiente=grad, diso0=cn[0], diso1=cn[1], dist=D,
                        giro=math.radians(az - A0)))
    return out


def anotaciones(rangos, formato, fps, n_sujeto: int = 1):
    """La caja se presenta en su beat; poses y RMSD en la convergencia."""
    fade = max(4, int(0.40 * fps))
    paso = max(4, int(0.5 * fps))
    plan = {"hotspots": [], "sujeto": []}
    if not (formato.etiquetas_3d and n_sujeto):
        return plan
    for i in range(n_sujeto):
        if i == 0 and "caja" in rangos:
            a, b = rangos["caja"]
            e0 = a + max(2, int(0.4 * fps))
            window = (e0, b - 3)
        else:
            clave = "convergencia" if "convergencia" in rangos else None
            if clave is None:
                break
            a, b = rangos[clave]
            e0 = a + max(3, int(1.2 * fps)) + (i - 1) * paso
            window = (e0, b - 3)
        if window[0] + fade >= window[1]:
            continue
        plan["sujeto"].append({
            "ventana": window,
            "fundido": [(window[0], window[0] + fade, 0, 1),
                        (window[1] - fade, window[1], 1, 0)]})
    return plan


def aparicion_del_sujeto(rangos, fps):
    """Caja, esfera y nube entran con el acercamiento sobre la caja."""
    if "caja" not in rangos:
        return None
    a, b = rangos["caja"]
    return {"ventana": (a, None), "fundido": [(a, a + max(5, int(0.9 * fps)), 0, 1)]}


def aparicion_de_hotspots(rangos, fps):
    """Los hotspots del receptor se presentan en el plano general: son la
    evidencia biológica antes de que la caja (el cómputo) se dibuje."""
    if "general" not in rangos:
        return None
    a, b = rangos["general"]
    i0 = a + int(0.30 * (b - a))
    return {"ventana": (i0, None),
            "fundido": [(i0, a + int(0.75 * (b - a)), 0, 1)]}


def aparicion_de_contactos(rangos, fps):
    """Las poses del motor se revelan cuando el muestreo termino.
    (Son `secundarios` del montado: aparecer ANTES del muestreo seria dar por
    hecho el resultado.)"""
    if "convergencia" not in rangos:
        return None
    a, b = rangos["convergencia"]
    i1 = min(b - 2, a + max(6, int(0.9 * fps)))
    return {"ventana": (a, None), "fundido": [(a, i1, 0, 1)]}


def titulo(rangos, formato, fps):
    """Rotulo de pantalla durante el plano general."""
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


def animar_sujeto(rangos, fps, montado, frames):
    """El caminante recorre los pasos ACEPTADOS de la traza real.

    Lo que se mueve en un muestreo Metropolis son los aceptados: los rechazos
    no son un paso, son un intento. El guion solo decide los fotogramas; las
    posiciones son las que dejo el muestreo, en el orden en que ocurrieron.
    """
    import bpy
    from nucleo.horneado import hornear
    nombre = (montado.extra or {}).get("caminante")
    puntos = (montado.extra or {}).get("traza_aceptados") or []
    if not nombre or len(puntos) < 2 or "busqueda" not in rangos:
        return
    obj = bpy.data.objects.get(nombre)
    if obj is None:
        return
    a, b = rangos["busqueda"]
    ultimo = len(puntos) - 1
    por_eje = [[], [], []]
    for f in frames:
        if f < a:
            p = puntos[0]
        elif f > b:
            p = puntos[ultimo]
        else:
            p = puntos[int((f - a) / max(b - a, 1) * ultimo)]
        for i in range(3):
            por_eje[i].append(p[i])
    for i in range(3):
        hornear(obj, "location", i, frames, por_eje[i])
