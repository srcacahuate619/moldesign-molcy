"""Escena Y: el ensamble conformacional, de las entradas a las poses entregadas.

Cuenta, en cinco beats, lo que el producto hizo con una evaluación de ensamble:

    sitio         el bolsillo y de qué se trata
    conformeros   las geometrías de entrada que aportaron poses entregadas
    corridas      la mejor pose de cada corrida independiente de Vina
    validacion    la piscina reordenada: cada pose entregada con su afinidad, sus
                  controles físicos y sus interacciones
    salida        la retirada, con todas las poses entregadas a la vez

El encuadre es el de la escena `x` (`ajustar_medidas` y el recorrido suavizado):
la cámara sigue lo que se enseña y deja siempre el sitio sin receptor por delante.

Lo que NO hace: no anima rotaciones entre conformaciones (ETKDG entrega geometrías
finales discretas, no una trayectoria) ni sugiere que una conformación sea «la
correcta». Cada elemento visual cita una medición del contrato `ensamble.json`.
"""
from __future__ import annotations

import math

from nucleo.horneado import ss
from variables.guion import Beat

NOMBRE = "y"
DESCRIPCION = ("Ensamble conformacional: conformaciones de entrada, corridas de Vina, "
               "poses entregadas y sus controles físicos.")
SUJETO = "ensamble_conformacional"

#: Los lee `maestro.medir`, que es agnóstico del guion pero no de sus constantes.
LENTE_GENERAL, LENTE_PRIMER_PLANO = 35.0, 50.0
EL_GENERAL, EL_PRIMER_PLANO = 12.0, -22.0
SWEEP_GENERAL = 338.0
#: El recorrido sigue poses que pueden quedar más lejos que el núcleo del
#: receptor; el control de calidad lo tolera sólo porque este guion lo declara.
QC_PERMITE_ALEJAMIENTO = True
QC_DIANAS_FACTOR = 0.9

#: Giro de la retirada final y deriva mientras explora (grados), como en `x`.
BARRIDO = 120.0
REPOSICION = 12.0
DERIVA = 24.0
MARGEN_SEGUIMIENTO = 1.6
SUAVIZADO_S = 0.15

#: Fotogramas mínimos que merece cada elemento para que se lea: por debajo, no se
#: enseña (queda dicho en el acta). A 30 fps son 0.4 s, 0.4 s y 0.6 s.
MINIMO_CONFORMERO, MINIMO_CORRIDA, MINIMO_POSE = 12, 12, 18
#: Una pose se ve menos de esto y su rótulo 3D no llega a leerse: se omite.
MINIMO_ROTULO = 6
#: Líneas de diedros y de controles fallidos que caben en pantalla.
MAX_DIEDROS, MAX_FALLOS = 6, 2

BEATS = [
    Beat("sitio", peso=1.0, papel="aproximar", requiere="sujeto"),
    Beat("conformeros", peso=2.0, papel="explorar", requiere="sujeto"),
    Beat("corridas", peso=2.0, papel="explorar", requiere="sujeto"),
    Beat("validacion", peso=5.0, papel="explorar", requiere="sujeto"),
    Beat("salida", peso=2.5, papel="explorar", requiere="sujeto"),
]
_ORDEN = tuple(b.id for b in BEATS)


def ajustar_rangos(rangos, formato):
    """Fija el primer segundo y reserva los últimos tres para la retirada."""
    if formato.bucle or not all(k in rangos for k in _ORDEN):
        return rangos
    n = max(b for _, b in rangos.values())
    salida = min(3 * formato.fps, max(1, n // 4))
    sitio = min(formato.fps, max(1, (n - salida) // 6))
    resto = n - salida - sitio
    if resto < 3:
        return rangos
    # Lo que queda se reparte 2 : 2 : 5 entre conformaciones, corridas y poses.
    conf = max(1, round(resto * 2 / 9))
    corr = max(1, round(resto * 2 / 9))
    val = resto - conf - corr
    if val < 1:
        return rangos
    nuevos, inicio = {}, 1
    for clave, largo in zip(_ORDEN, (sitio, conf, corr, val, salida)):
        nuevos[clave] = (inicio, inicio + largo - 1)
        inicio += largo
    return nuevos


def ventanas(rango, n, minimo=1):
    """Un turno por elemento, todos los rangos inclusivos.

    Si no caben `n` elementos con al menos `minimo` fotogramas cada uno, se
    enseñan sólo los primeros que sí caben: el orden de los elementos es el de su
    importancia (mejores primero), así que lo que se omite es lo menos relevante.
    """
    if not rango or n < 1:
        return []
    a, b = rango
    largo = b - a + 1
    n = max(1, min(n, largo // max(1, minimo)))
    return [(a + (i * largo) // n, a + ((i + 1) * largo) // n - 1) for i in range(n)]


def conteos(montado) -> dict[str, int]:
    """Cuántos elementos tiene cada beat; viaja en `medidas` hasta `estados`."""
    extra = montado.extra or {}
    return {"conformeros": len(extra.get("conformeros") or []),
            "corridas": len(extra.get("corridas") or []),
            "poses": len(extra.get("poses") or [])}


def _ventanas_conformeros(rangos, n):
    return ventanas(rangos.get("conformeros"), n, MINIMO_CONFORMERO)


def _ventanas_corridas(rangos, n):
    return ventanas(rangos.get("corridas"), n, MINIMO_CORRIDA)


def _ventanas_poses(rangos, n):
    return ventanas(rangos.get("validacion"), n, MINIMO_POSE)


# ── cámara ───────────────────────────────────────────────────────────────────
def ajustar_medidas(medidas, paq, rec, montado, formato):
    """El plano de `x` (sitio, conformaciones, poses) más un plano por corrida.

    `x.ajustar_medidas` elige el azimut y la elevación que dejan el sitio sin
    receptor por delante y calcula un plano por nube; aquí las nubes son las
    conformaciones (`puntos_instantaneas`) y las poses entregadas (`puntos_poses`).
    """
    from guiones import x as escena_x
    from nucleo import encuadre
    extra = montado.extra
    extra["puntos_instantaneas"] = extra.get("puntos_conformeros", [])
    medidas["conteos_y"] = conteos(montado)
    escena_x.ajustar_medidas(medidas, paq, rec, montado, formato)
    # `x` sale sin plan si no hay ningún punto del sitio que encuadrar: entonces
    # manda el plano único de `maestro.medir`, y aquí no hay nada que ampliar.
    if "plan_camara" not in medidas or not extra.get("puntos_corridas"):
        return
    az, el = medidas["azimut"], medidas["elevacion"]
    corridas = []
    nubes = extra["puntos_corridas"]
    for i in range(len(nubes)):
        grupo = [p for nube in nubes[max(0, i - 1):i + 2] for p in nube]
        centro = escena_x._centro(grupo)
        corridas.append({
            "objetivo": centro,
            "dist": encuadre.distancia_visible(grupo, centro, LENTE_PRIMER_PLANO,
                                               formato.aspecto, el, [az],
                                               MARGEN_SEGUIMIENTO),
            "radio": escena_x._radio(grupo, centro)})
    plan = medidas["plan_camara"]
    plan["corridas"] = corridas
    # Con todo encuadrado la cámara está lo más abierta posible: ningún plano de
    # seguimiento puede pedir más que el que lo contiene.
    plan["caja"]["dist"] = max([plan["caja"]["dist"]] + [p["dist"] for p in corridas])


def _recorrido(medidas, rangos, fps):
    """Objetivo, distancia y radio por fotograma hasta el final de la validación."""
    plan = medidas.get("plan_camara") or {}
    est, cor, pos = plan.get("estados_vina"), plan.get("corridas"), plan.get("poses")
    if not (est and pos and all(k in rangos for k in _ORDEN)):
        return None
    entrada = lambda p: (p["objetivo"], p["dist"], p["radio"])      # noqa: E731
    n = medidas.get("conteos_y") or {}
    sitio = plan["sitio"]
    controles = [(1, *entrada(sitio)), (rangos["sitio"][1], *entrada(sitio))]
    for ventana, p in zip(_ventanas_conformeros(rangos, n.get("conformeros", 0)), est):
        controles.append(((ventana[0] + ventana[1]) / 2, *entrada(p)))
    for ventana, p in zip(_ventanas_corridas(rangos, n.get("corridas", 0)), cor or []):
        controles.append(((ventana[0] + ventana[1]) / 2, *entrada(p)))
    ventanas_pose = _ventanas_poses(rangos, n.get("poses", 0))
    for ventana, p in zip(ventanas_pose, pos):
        controles.append(((ventana[0] + ventana[1]) / 2, *entrada(p)))
    fin = rangos["validacion"][1]
    controles.append((fin, *entrada(pos[max(0, min(len(pos), len(ventanas_pose)) - 1)])))
    controles.sort(key=lambda c: c[0])
    from guiones import x as escena_x
    crudo = [escena_x._interpolar(controles, f) for f in range(1, fin + 1)]
    sigma = SUAVIZADO_S * max(1, fps)
    objetivos = escena_x._suavizar([c[0] for c in crudo], sigma)
    distancias = escena_x._suavizar([c[1] for c in crudo], sigma)
    radios = escena_x._suavizar([c[2] for c in crudo], sigma)
    return {f + 1: (objetivos[f], distancias[f], radios[f]) for f in range(fin)}


def estados(medidas, rangos, n_frames, formato, experimental=False):
    from guiones import x as escena_x
    from nucleo import encuadre
    P = medidas["centro_general"]
    plan = medidas.get("plan_camara") or {}
    seguido = _recorrido(medidas, rangos, formato.fps)
    unico = {"objetivo": medidas["pivote"],
             "dist": medidas["dist_primer_plano"],
             "radio": medidas.get("radio_sitio", 1.0)}
    fin_val = rangos.get("validacion", (1, 1))[1]
    if seguido:
        cierre = seguido[fin_val]
        fin = {"objetivo": cierre[0], "dist": cierre[1], "radio": cierre[2]}
    else:
        fin = (plan.get("poses") or [unico])[-1]
    D1 = max(medidas["dist_general"], fin["dist"] * 1.12)
    A0 = medidas["azimut"]
    Ar = A0 + REPOSICION
    ec = medidas.get("elevacion", EL_PRIMER_PLANO)
    eg = medidas.get("elevacion_general", EL_GENERAL)
    gc, gg = medidas["gradiente_cerca"], medidas["gradiente_general"]
    cercano = lambda d: (d * 0.076, d * 0.19)                       # noqa: E731
    out = []
    for f in range(1, n_frames + 1):
        beat = next((k for k, (a, b) in rangos.items() if a <= f <= b), "reposo")
        a, b = rangos.get(beat, (f, f))
        u = ss((f - a) / max(b - a, 1))
        L, el, az, grad = LENTE_PRIMER_PLANO, ec, A0, gc
        fuerza = 1.0
        if beat in ("sitio", "conformeros", "corridas", "validacion"):
            if seguido:
                T, D, radio = seguido[f]
            else:
                T, D, radio = unico["objetivo"], unico["dist"], unico["radio"]
            diso = cercano(D)
            if beat != "sitio":
                a0, b0 = rangos["conformeros"][0], rangos["validacion"][1]
                az = Ar + DERIVA * (f - a0) / max(b0 - a0, 1)
        elif beat == "salida":
            az = Ar + DERIVA + BARRIDO * u
            T = escena_x._mezcla(fin["objetivo"], P, u)
            D = escena_x._mezcla(fin["dist"], D1, u)
            radio = fin["radio"]
            L = LENTE_PRIMER_PLANO + (LENTE_GENERAL - LENTE_PRIMER_PLANO) * u
            el = ec + (eg - ec) * u
            grad = gc + (gg - gc) * u
            fuerza = 1.0 - u
            diso = tuple(v + (z - v) * u for v, z in zip(cercano(fin["dist"]), (0.02, 0.05)))
        else:       # reposo
            T, D, L, el, grad = P.copy(), D1, LENTE_GENERAL, eg, gg
            radio = fin["radio"]
            az = A0 + BARRIDO
            fuerza, diso = 0.0, (0.02, 0.05)
        pos = encuadre.posicion(T, az, el, D)
        estado = dict(pos=pos, objetivo=T, lente=L,
                      diafragma=14.0 if formato.profundidad_de_campo else 32.0,
                      gradiente=grad, diso0=diso[0], diso1=diso[1], dist=D,
                      giro=math.radians(az - A0))
        if experimental:
            estado["portal"] = escena_x._portal_fantasma(
                T, pos, D, fuerza, dict(medidas, radio_portal=radio))
        out.append(estado)
    return out


# ── rótulos 3D: cada interacción, en la ventana de su pose ─────────────────────
def anotaciones(rangos, formato, fps, n_sujeto: int = 1, montado=None):
    plan = {"hotspots": [], "sujeto": []}
    if montado is None or not formato.etiquetas_3d:
        return plan
    extra = montado.extra or {}
    por_pose = extra.get("rotulos_por_pose") or {}
    poses = extra.get("poses") or []
    ventana_de = dict(zip((p["rank"] for p in poses), _ventanas_poses(rangos, len(poses))))
    nubes = {p["rank"]: nube for p, nube in zip(poses, extra.get("puntos_poses") or [])}

    def entrada(a, b, rank):
        if b - a + 1 < MINIMO_ROTULO:
            return None
        fade = max(2, min(int(0.2 * fps), (b - a + 1) // 3))
        return {"ventana": (a, b), "colocar_en": (a + b) // 2,
                "reservar": nubes.get(rank),
                "fundido": [(a, a + fade, 0, 1), (b - fade, b, 1, 0)]}

    for ident, _texto, _pos in montado.anclas:
        rank = next((r for r, ids in por_pose.items() if ident in ids), None)
        plan["sujeto"].append(entrada(*ventana_de[rank], rank) if rank in ventana_de else None)
    return plan


def aparicion_del_sujeto(rangos, fps):
    return None


def aparicion_de_hotspots(rangos, fps):
    """Los hotspots del receptor se presentan desde el primer plano del sitio."""
    if "sitio" not in rangos:
        return None
    a, _b = rangos["sitio"]
    return {"ventana": (a, None), "fundido": [(a, a, 1, 1)]}


def aparicion_de_contactos(rangos, fps):
    """Cada pose tiene su propia ventana, horneada por `animar_sujeto`."""
    return None


def titulo(rangos, formato, fps):
    return None


# ── rótulos de pantalla ──────────────────────────────────────────────────────
def _energia(e):
    return f"{e:.2f} KCAL/MOL" if isinstance(e, (int, float)) else ""


def _diedros(torsiones):
    """Los diedros medidos sobre la geometría de entrada, uno por línea."""
    lineas = [f"{t['atomos'][1]}-{t['atomos'][2]} {t['angulo_grados']:+.0f}°"
              for t in torsiones[:MAX_DIEDROS]]
    if len(torsiones) > MAX_DIEDROS:
        lineas.append(f"+{len(torsiones) - MAX_DIEDROS} MAS")
    return "\n".join(lineas)


def _controles(controles, nombre):
    """«CONTROLES …  a/n» y los que fallan; «no evaluados» si no se evaluó."""
    if not controles or controles.get("pruebas") in (None, 0):
        return f"{nombre}: NO EVALUADOS"
    fallos = controles.get("fallos") or []
    linea = f"{nombre} {controles['aprobadas']}/{controles['pruebas']}"
    if fallos:
        visibles = ", ".join(str(f).upper() for f in fallos[:MAX_FALLOS])
        resto = f" +{len(fallos) - MAX_FALLOS}" if len(fallos) > MAX_FALLOS else ""
        linea += f"\nFALLAN: {visibles}{resto}"
    return linea


def rotulos_datos(rangos, formato, fps, montado):
    if not formato.rotulos_pantalla:
        return []
    extra = montado.extra or {}
    conformeros = extra.get("conformeros") or []
    corridas = extra.get("corridas") or []
    poses = extra.get("poses") or []
    if not poses:
        return []
    resumen = extra.get("resumen") or {}
    validacion = extra.get("validacion") or {}
    motor = str(validacion.get("motor") or "")
    nombre_controles = ("CONTROLES POSEBUSTERS" if motor.startswith("posebusters")
                        else "CONTROLES FISICOS")
    escala = formato.escala_texto * 0.59
    out = []

    def poner(id_, texto, ventana, esquina="superior_izquierda", factor=1.0):
        out.append(dict(id=id_, texto=texto, ventana=ventana, esquina=esquina,
                        escala=escala * factor))

    k, cand = resumen.get("conformaciones_acopladas"), resumen.get("poses_candidatas")
    entregadas = resumen.get("poses_entregadas", len(poses))
    if "sitio" in rangos:
        cuenta = " | ".join(x for x in (
            f"{k} CONFORMACIONES" if k else "", f"{cand} POSES CANDIDATAS" if cand else "") if x)
        poner("y_intro", "ENSAMBLE CONFORMACIONAL\n" + (cuenta + "\n" if cuenta else "")
              + f"{entregadas} ENTREGADAS DE LA PISCINA", rangos["sitio"])
    vent_c = _ventanas_conformeros(rangos, len(conformeros))
    for pos, (c, ventana) in enumerate(zip(conformeros, vent_c), 1):
        linea = f"SEMILLA {c['semilla']}" if c.get("semilla") is not None else ""
        if isinstance(c.get("energia_mmff"), (int, float)):
            linea += f"{'  |  ' if linea else ''}MMFF {_energia(c['energia_mmff'])}"
        poner(f"y_conf_{c['indice']}",
              f"CONFORMACION {c['indice']}  |  {pos}/{len(vent_c)}" + (f"\n{linea}" if linea else ""),
              ventana)
        if c.get("torsiones"):
            poner(f"y_diedros_{c['indice']}",
                  "DIEDROS MEDIDOS EN LA ENTRADA\n" + _diedros(c["torsiones"]),
                  ventana, "inferior_izquierda", 0.75)
    vent_r = _ventanas_corridas(rangos, len(corridas))
    for pos, (r, ventana) in enumerate(zip(corridas, vent_r), 1):
        poner(f"y_corrida_{r['conformero']}",
              f"VINA  |  CORRIDA {pos}/{len(vent_r)}\nCONFORMACION {r['conformero']}\n"
              f"POSE {r['rank_local']} DE SU CORRIDA | {_energia(r['afinidad'])}",
              ventana)
    for pose, ventana in zip(poses, _ventanas_poses(rangos, len(poses))):
        cuenta = pose.get("contactos", {})
        lectura = (f"\nPOLARES {cuenta.get('polares', 0)}  |  "
                   f"APOLARES {cuenta.get('hidrofobicos', 0)}"
                   if extra.get("contactos_visibles", True) else "")
        poner(f"y_pose_{pose['rank']}",
              f"PISCINA DE VINA  |  POSE {pose['rank']}/{len(poses)}\n"
              f"CONFORMACION {pose['conformero']}  |  {_energia(pose['afinidad'])}\n"
              f"{_controles(pose.get('controles'), nombre_controles)}{lectura}",
              ventana)
    if "salida" in rangos:
        mejor = poses[0]
        poner("y_final",
              f"ENSAMBLE  |  {entregadas} POSES ENTREGADAS\n"
              + (f"{cand} CANDIDATAS | {k} CORRIDAS DE VINA\n" if cand and k else "")
              + f"MEJOR {_energia(mejor['afinidad'])} | CONFORMACION {mejor['conformero']}",
              rangos["salida"])
        if motor:
            poner("y_motor_controles", f"CONTROLES: {motor.replace(':', ' ').upper()}\n"
                  "APLICADOS DESPUES DEL ACOPLAMIENTO", rangos["salida"],
                  "inferior_izquierda", 0.75)
    return out


# ── visibilidad por beat ─────────────────────────────────────────────────────
def mostradas(rangos, montado) -> dict:
    """Cuántos elementos de cada beat caben en el formato, frente a los que hay."""
    n = conteos(montado)
    vistas = {"conformeros": len(_ventanas_conformeros(rangos, n["conformeros"])),
              "corridas": len(_ventanas_corridas(rangos, n["corridas"])),
              "poses": len(_ventanas_poses(rangos, n["poses"]))}
    return {**vistas, "disponibles": n}


def animar_sujeto(rangos, fps, montado, frames):
    """Enseña cada conformación, cada corrida y cada pose en su turno."""
    import bpy
    from nucleo.horneado import hornear
    extra = montado.extra or {}
    poses = extra.get("poses") or []
    # Va al acta aunque el formato no lleve rótulos: quien lea el vídeo y el acta
    # tiene que poder saber qué se quedó fuera por duración.
    montado.medido["mostradas_en_el_video"] = mostradas(rangos, montado)
    asignados: dict[str, list[tuple[int, int]]] = {}

    def dar(nombre, ventana):
        if nombre and ventana:
            asignados.setdefault(nombre, []).append(tuple(ventana))

    conformeros = extra.get("conformeros") or []
    corridas = extra.get("corridas") or []
    for c, ventana in zip(conformeros, _ventanas_conformeros(rangos, len(conformeros))):
        dar(c["nombre"], ventana)
    for r, ventana in zip(corridas, _ventanas_corridas(rangos, len(corridas))):
        dar(r["nombre"], ventana)
    for p, ventana in zip(poses, _ventanas_poses(rangos, len(poses))):
        dar(p["nombre"], ventana)
        for linea in extra.get("contactos_por_pose", {}).get(p["rank"], []):
            dar(linea, ventana)
    # La retirada enseña TODAS las entregadas: el ensamble amplía la cobertura
    # geométrica y eso sólo se ve con las poses juntas.
    for p in poses:
        dar(p["nombre"], rangos.get("salida"))
    todos = ([c["nombre"] for c in extra.get("conformeros") or []]
             + [p["nombre"] for p in poses]
             + [n for ls in extra.get("contactos_por_pose", {}).values() for n in ls])
    for nombre in dict.fromkeys(todos):
        obj = bpy.data.objects.get(nombre)
        if obj is None:
            continue
        ventanas_obj = asignados.get(nombre, [])
        oculto = [0.0 if any(a <= f <= b for a, b in ventanas_obj) else 1.0 for f in frames]
        hornear(obj, "hide_render", -1, frames, oculto, "CONSTANT")
        hornear(obj, "hide_viewport", -1, frames, oculto, "CONSTANT")
