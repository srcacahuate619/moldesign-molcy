"""Escena X: ligando dockeado, estados internos de Vina y poses calculadas."""
from __future__ import annotations

import math

from nucleo.horneado import ss
from variables.guion import Beat

NOMBRE = "x"
DESCRIPCION = "Ligando dockeado, busqueda interna instrumentada de Vina, poses y orbita final."
SUJETO = "busqueda_montecarlo"

#: Los lee `maestro.medir`, que es agnostico del guion pero no de sus constantes.
LENTE_GENERAL, LENTE_PRIMER_PLANO = 35.0, 50.0
EL_GENERAL, EL_PRIMER_PLANO = 12.0, -22.0
SWEEP_GENERAL = 338.0
#: Lo que el guion va a usar de verdad: contexto sobrio alrededor del sitio,
#: con giro final alrededor del complejo.
BARRIDO = 120.0
REPOSICION = 12.0

#: El primer plano de esta escena encuadra la CAJA de acoplamiento (el
#: volumen donde corrió la búsqueda), que puede ser MÁS ancha que el núcleo
#: del receptor: en `convergencia` la cámara da un paso atrás a propósito.
#: Salida/control lo tolera SOLO cuando el guion lo declara aqui.
QC_PERMITE_ALEJAMIENTO = True
QC_DIANAS_FACTOR = 0.9

BEATS = [
    Beat("sitio", peso=2.0, papel="aproximar", requiere="sujeto"),
    Beat("caja", peso=1.5, papel="aproximar", requiere="sujeto"),
    Beat("busqueda", peso=5.0, papel="explorar", requiere="sujeto"),
    Beat("convergencia", peso=2.5, papel="explorar", requiere="sujeto"),
    Beat("salida", peso=2.5, papel="explorar", requiere="sujeto"),
    Beat("general", peso=3.0, papel="establecer"),
    Beat("reposo", peso=0.5, papel="reposo", minimo_fotogramas=2),
]


def ajustar_rangos(rangos, formato):
    """Fija el primer segundo y reserva los ultimos tres para la retirada."""
    if formato.bucle or not all(k in rangos for k in
                               ("sitio", "caja", "busqueda", "convergencia", "salida")):
        return rangos
    n = max(b for _, b in rangos.values())
    salida = min(3 * formato.fps, max(1, n // 3))
    sitio = min(formato.fps, max(1, (n - salida) // 4))
    if n <= 3 * formato.fps:
        sitio = min(sitio, max(1, formato.fps // 3))
    caja = min(formato.fps, max(1, (n - salida - sitio) // 3))
    if n <= 3 * formato.fps:
        caja = min(caja, max(1, formato.fps // 3))
    convergencia = min(4 * formato.fps,
                       max(1, (n - salida - sitio - caja) * (1 if n <= 3 * formato.fps else 2) // (2 if n <= 3 * formato.fps else 3)))
    busqueda = n - salida - sitio - caja - convergencia
    if busqueda < 1:
        return rangos
    largos = (sitio, caja, busqueda, convergencia, salida)
    nuevos, inicio = {}, 1
    for clave, largo in zip(("sitio", "caja", "busqueda", "convergencia", "salida"), largos):
        nuevos[clave] = (inicio, inicio + largo - 1)
        inicio += largo
    return nuevos


def ajustar_medidas(medidas, paq, rec, montado, formato):
    """Separa el sitio biologico del volumen computacional, sin mover datos."""
    from nucleo import encuadre, receptor, oclusion
    K = medidas["pivote"]
    puntos = []
    for h in rec.hotspots:
        c = receptor.centro_de_residuo(rec.molecula, h.numero,
                                      receptor.indice_de_cadena(paq, h.cadena))
        if c is not None:
            puntos.append(c)
    puntos += list((montado.extra or {}).get("ligando_dock_puntos", []))
    if not puntos:
        puntos = [p for p in receptor.puntos(rec.molecula) if (p - K).length <= 0.8]
    if puntos:
        def distancia(az, el):
            return max(0.8, encuadre.distancia(puntos, K, LENTE_PRIMER_PLANO,
                formato.aspecto, el, [az], margen=2.1))
        pose = oclusion.mejor_pose([("sitio", 1.0, puntos)], K,
            distancia(0, EL_PRIMER_PLANO), LENTE_PRIMER_PLANO, formato.aspecto,
            distancia_requerida=distancia)
        az, el = pose["azimut"], pose["elevacion"]
        medidas.update(azimut=az, elevacion=el, pose_sitio=pose,
                       dist_sitio=distancia(az, el),
                       radio_sitio=max((p - K).length for p in puntos))
        medidas["dist_primer_plano"] = max(medidas["dist_sitio"],
            encuadre.distancia(list(montado.dianas) + puntos, K,
                LENTE_PRIMER_PLANO, formato.aspecto, el, [az], margen=1.3))
        # En vertical, un bolsillo encuadrado solo por tres residuos puede
        # atravesar la cinta. Conserva suficiente receptor alrededor del sitio.
        medidas["dist_sitio"] = max(medidas["dist_sitio"],
                                      medidas["dist_primer_plano"] * 0.45)


def _portal_fantasma(K, pos, distancia, fuerza, medidas):
    from guiones.sitio_activo import _portal_fantasma as portal
    return portal(K, pos, distancia, fuerza, medidas)


def estados(medidas, rangos, n_frames, formato, experimental=False):
    from nucleo import encuadre
    P, K = medidas["centro_general"], medidas["pivote"]
    D0 = medidas["dist_primer_plano"]
    Ds = min(medidas.get("dist_sitio", D0), D0)
    # La salida siempre se aleja fisicamente, incluso con una caja muy grande.
    D1 = max(medidas["dist_general"], D0 * 1.12)
    A0 = medidas["azimut"]
    Ar = A0 + REPOSICION
    ec = medidas.get("elevacion", EL_PRIMER_PLANO)
    eg = medidas.get("elevacion_general", EL_GENERAL)
    gc, gg = medidas["gradiente_cerca"], medidas["gradiente_general"]
    rn = medidas.get("radio_sitio", medidas.get("radio_portal", Ds * 0.35))
    cn = (rn * 0.12, rn * 0.30)
    out = []
    for f in range(1, n_frames + 1):
        beat = next((k for k, (a, b) in rangos.items() if a <= f <= b), "reposo")
        a, b = rangos.get(beat, (f, f))
        u = ss((f - a) / max(b - a, 1))
        T, D, L, el, az, grad = K.copy(), D0, LENTE_PRIMER_PLANO, ec, A0, gc
        fuerza, diso = 1.0, cn
        if beat == "sitio":
            D = Ds
        elif beat == "caja":
            D = Ds
            az = A0 + REPOSICION * u
        elif beat in ("busqueda", "convergencia"):
            D = Ds
            az = Ar
        elif beat == "salida":
            az = Ar + BARRIDO * u
            T = K + (P - K) * u
            D = Ds + (D1 - Ds) * u
            L = LENTE_PRIMER_PLANO + (LENTE_GENERAL - LENTE_PRIMER_PLANO) * u
            el = ec + (eg - ec) * u
            grad = gc + (gg - gc) * u
            fuerza = 1.0 - u
            diso = tuple(v + (z - v) * u for v, z in zip(cn, (0.02, 0.05)))
        elif beat in ("general", "reposo"):
            T, D, L, el, grad = P.copy(), D1, LENTE_GENERAL, eg, gg
            az = A0 + BARRIDO * (u if beat == "general" else 1.0)
            if formato.bucle:
                az = A0 + 360.0 * (f - 1) / n_frames
            fuerza, diso = 0.0, (0.02, 0.05)
        pos = encuadre.posicion(T, az, el, D)
        estado = dict(pos=pos, objetivo=T, lente=L,
                      diafragma=14.0 if formato.profundidad_de_campo else 32.0,
                      gradiente=grad, diso0=diso[0], diso1=diso[1], dist=D,
                      giro=math.radians(az - A0))
        if experimental:
            estado["portal"] = _portal_fantasma(K, pos, D, fuerza,
                dict(medidas, radio_portal=rn))
        out.append(estado)
    return out


def anotaciones(rangos, formato, fps, n_sujeto: int = 1):
    """Las poses se identifican en pantalla, sin etiquetas sobre el sitio."""
    return {"hotspots": [], "sujeto": []}


def aparicion_del_sujeto(rangos, fps):
    """La caja real aparece cuando la camara se abre para darle contexto."""
    if "salida" not in rangos:
        return None
    a, b = rangos["salida"]
    return {"ventana": (a, None), "fundido": [(a, a + max(5, int(0.9 * fps)), 0, 1)]}


def aparicion_de_hotspots(rangos, fps):
    """Los hotspots del receptor se presentan en el plano general: son la
    evidencia biológica antes de que la caja (el cómputo) se dibuje."""
    if "sitio" not in rangos:
        return None
    a, b = rangos["sitio"]
    return {"ventana": (a, None), "fundido": [(a, a, 1, 1)]}


def aparicion_de_contactos(rangos, fps):
    """Cada pose tiene su propia ventana, horneada por animar_sujeto."""
    return None


def titulo(rangos, formato, fps):
    return None


def ventanas_poses(rangos, n):
    """Una pose de Vina por turno; todos los rangos son inclusivos."""
    if n < 1 or "convergencia" not in rangos:
        return []
    a, b = rangos["convergencia"]
    largo = b - a + 1
    return [(a + (i * largo) // n,
             a + ((i + 1) * largo) // n - 1) for i in range(n)]


def ventanas_instantaneas(rangos, n):
    if n < 1 or "busqueda" not in rangos:
        return []
    a, b = rangos["busqueda"]
    largo = b - a + 1
    return [(a + (i * largo) // n,
             a + ((i + 1) * largo) // n - 1) for i in range(n)]


def rotulos_datos(rangos, formato, fps, montado):
    """Distingue los pasos internos reales de las poses finales."""
    if not formato.rotulos_pantalla:
        return []
    poses = (montado.extra or {}).get("poses") or []
    traza = (montado.extra or {}).get("traza_interna") or {}
    if not poses:
        return []
    total = len(poses)
    mejor = poses[0].get("afinidad")
    energia = f"{mejor:.2f} kcal/mol" if isinstance(mejor, (int, float)) else ""
    escala = formato.escala_texto * 0.62
    out = []
    def poner(id_, texto, ventana, esquina="superior_izquierda"):
        out.append(dict(id=id_, texto=texto, ventana=ventana,
                        esquina=esquina, escala=escala))
    if "sitio" in rangos:
        a = rangos["sitio"][0]
        b = rangos.get("caja", rangos["sitio"])[1]
        poner("vina_ligando", f"RESULTADO ANTICIPADO\nVINA  |  {total} POSES", (a, b))
    instantaneas = (montado.extra or {}).get("instantaneas") or []
    if "busqueda" in rangos and traza.get("torsiones_activas"):
        poner("vina_torsiones", f"{traza['torsiones_activas']} TORSIONES ACTIVAS",
              rangos["busqueda"])
    for i, (muestra, ventana) in enumerate(zip(
            instantaneas, ventanas_instantaneas(rangos, len(instantaneas)))):
        anterior = "\nVIOLETA: MUESTRA ANTERIOR" if muestra.get("fantasma") else ""
        metrica = muestra.get("metrica_interna") or {}
        lectura = ""
        if metrica:
            estado = "PROPUESTA ACEPTADA" if metrica["aceptada_en_paso"] else "PROPUESTA RECHAZADA"
            lectura = (f"\nESTADO RETENIDO {metrica['retenida']:.2f}  |  {estado}"
                       f"\nMEJOR DE ESTA REPLICA {metrica['mejor_hasta_paso']:.2f}"
                       f"\nACEPTADOS {metrica['aceptadas_acumuladas']:,}/{muestra['step']:,}")
        poner(f"vina_pasos_{i}",
              f"VINA  |  REPLICA 1/{traza['replicas']}\n"
              f"PASO {muestra['step']:,}/{traza['pasos_replica']:,}"
              f"{lectura}{anterior}",
              ventana, "inferior_izquierda")
    for i, (pose, ventana) in enumerate(zip(poses, ventanas_poses(rangos, total)), 1):
        af = pose.get("afinidad")
        valor = f"{af:.2f} kcal/mol" if isinstance(af, (int, float)) else ""
        cuenta = pose.get("contactos", {})
        lectura = (f"\nORO POLAR {cuenta.get('polares', 0)}  |  "
                   f"CIAN HIDROFOBICO {cuenta.get('hidrofobicos', 0)}"
                   if montado.extra.get("contactos_visibles", True) else "")
        rmsd = pose.get("rmsd_vina_inferior_a")
        if i > 1 and isinstance(rmsd, (int, float)):
            lectura += f"\nRMSD VS POSE 1: {rmsd:.2f} A (COTA INFERIOR)"
        poner(f"vina_pose_{i}",
              f"VINA  |  POSE {i}/{total}\n{valor}{lectura}", ventana)
    if "salida" in rangos:
        poner("vina_resultado", f"VINA  |  {total} POSES\nMEJOR {energia}",
              rangos["salida"])
        if traza.get("pasos_totales"):
            poner("vina_total", f"BUSQUEDA INTERNA\n{traza['pasos_totales']:,} PASOS / {traza['replicas']} REPLICAS",
                  rangos["salida"], "inferior_izquierda")
    return out


def animar_sujeto(rangos, fps, montado, frames):
    """Enseña el ligando y cada pose real sin inventar una trayectoria."""
    import bpy
    from nucleo.horneado import hornear, visible_en
    poses = (montado.extra or {}).get("poses") or []
    ventanas = ventanas_poses(rangos, len(poses))
    busqueda = rangos.get("busqueda")
    for i, pose in enumerate(poses):
        obj = bpy.data.objects.get(pose["nombre"])
        if obj is None:
            continue
        ventana = ventanas[i] if i < len(ventanas) else None
        oculto = []
        for f in frames:
            en_pose = ventana is not None and ventana[0] <= f <= ventana[1]
            mejor = i == 0 and (busqueda is None or
                               f < busqueda[0] or f > rangos["convergencia"][1])
            oculto.append(0.0 if en_pose or mejor else 1.0)
        hornear(obj, "hide_render", -1, frames, oculto, "CONSTANT")
        hornear(obj, "hide_viewport", -1, frames, oculto, "CONSTANT")
        for nombre in montado.extra.get("contactos_por_pose", {}).get(
                pose.get("rank"), []):
            linea = bpy.data.objects.get(nombre)
            if linea is not None:
                hornear(linea, "hide_render", -1, frames, oculto, "CONSTANT")
                hornear(linea, "hide_viewport", -1, frames, oculto, "CONSTANT")
    instantaneas = (montado.extra or {}).get("instantaneas", [])
    for muestra, ventana in zip(instantaneas,
                               ventanas_instantaneas(rangos, len(instantaneas))):
        obj = bpy.data.objects.get(muestra["nombre"])
        if obj is not None:
            visible_en(obj, frames, *ventana)
        fantasma = bpy.data.objects.get(muestra.get("fantasma") or "")
        if fantasma is not None:
            visible_en(fantasma, frames, *ventana)
