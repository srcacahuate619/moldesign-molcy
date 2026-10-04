"""VARIABLE: que se rotula, y de que clase.

Dos clases, y la diferencia no es estetica sino geometrica:

`EtiquetaAnclada` — texto 3D con linea guia hasta un atomo o un residuo. Tiene
    posicion en el mundo, asi que **se ladea en cuanto la camara se mueve**. Por
    eso solo existe durante pausas, y se orienta y coloca UNA vez al entrar en
    cada una. Esa es toda la solucion al problema de las etiquetas torcidas: si
    nada se mueve, nada hay que recalcular, y no hace falta ningun manejador por
    fotograma.

`RotuloPantalla` — texto emparentado a la camara. No tiene ancla, no se ladea y
    **puede vivir durante el movimiento**. Es lo que necesita la busqueda de
    Montecarlo, que no tiene ningun momento quieto, y el gancho de los primeros
    segundos en redes sociales.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import bpy
from mathutils import Matrix, Vector

from nucleo import horneado as H
# El nombre del rotulo inferior vive en `titulos.py`, sin bpy, para poder
# probarlo fuera de Blender. Se reexporta: el maestro lo llama desde aqui.
from variables.titulos import NOMBRES_CURADOS, nombre_legible, titulo_pantalla  # noqa: F401

#: Fraccion de la distancia camara->ancla a la que se coloca la etiqueta.
#: Cerca de la camara para quedar por delante de la geometria.
CERCANIA = 0.45

#: Hasta donde puede llegar el ANCLA del texto, en fraccion del semicuadro.
#: Sin este tope, apartar la etiqueta del centroide la empuja fuera de cuadro y
#: el texto sale cortado por el borde.
LIMITE_CUADRO = 0.80


@dataclass
class Rotulo:
    id: str
    texto: str
    objeto: object = None
    guia: object = None
    material: object = None
    ventana: tuple[int, int] = (1, 1)
    fundido: list = field(default_factory=list)


def _duplicar(prototipo, nombre: str, texto: str, escala_texto: float):
    """Duplica el prototipo del caso 001 para heredar tipografia y material."""
    lab = prototipo.copy()
    lab.data = prototipo.data.copy()
    # Sin esto las copias comparten la accion del prototipo y cada horneado
    # pisa al anterior: la ultima etiqueta acaba decidiendo por todas.
    lab.animation_data_clear()
    lab.name = nombre
    lab.data.body = texto
    if "tamano_base" not in lab.data:
        lab.data["tamano_base"] = prototipo.data.size
    lab.data.size = lab.data["tamano_base"] * escala_texto
    lab.data.materials.clear()
    mat = prototipo.data.materials[0].copy()
    mat.name = f"Mat_{nombre}"
    H.limpiar_material(mat)
    mat.blend_method = "BLEND"
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    lab.data.materials.append(mat)
    lab.hide_render = lab.hide_viewport = False
    # Una etiqueta no puede arrojar sombra: estaba imprimiendo su texto sobre
    # la helice de detras como si fuera un grabado, y se leia como un duplicado
    # fantasma. Tampoco debe recibirla ni aparecer en reflejos.
    for prop in ("visible_shadow", "visible_diffuse", "visible_glossy"):
        if hasattr(lab, prop):
            setattr(lab, prop, False)
    bpy.context.scene.collection.objects.link(lab)
    return lab, mat


# ── etiqueta anclada en 3D ───────────────────────────────────────────────
def crear_anclada(id_: str, texto: str, ancla: Vector, prototipo, proto_guia,
                  escala_texto: float = 1.0) -> Rotulo:
    lab, mat = _duplicar(prototipo, f"Lab_{id_}", texto, escala_texto)
    lab["ancla_pos"] = list(ancla)
    guia = proto_guia.copy()
    guia.data = proto_guia.data.copy()
    guia.animation_data_clear()
    guia.name = f"Guia_{id_}"
    guia.data.materials.clear()
    guia.data.materials.append(mat)
    guia.hide_render = guia.hide_viewport = False
    for prop in ("visible_shadow", "visible_diffuse", "visible_glossy"):
        if hasattr(guia, prop):
            setattr(guia, prop, False)
    bpy.context.scene.collection.objects.link(guia)
    return Rotulo(id=id_, texto=texto, objeto=lab, guia=guia, material=mat)


def colocar_ancladas(cam, rotulos, separacion: float = 0.17) -> None:
    """Coloca y orienta un grupo respecto a una camara QUIETA.

    `separacion` sube cuando hay pocas etiquetas: el reparto las aparta del
    centroide del grupo, y con dos el centroide cae entre ellas y la etiqueta
    acaba encima de la propia molecula.
    """
    sc = bpy.context.scene
    grupo = [r for r in rotulos if r.objeto is not None]
    if not grupo:
        return
    M = cam.matrix_world
    q = M.to_quaternion()
    rg, uv, fw = q @ Vector((1, 0, 0)), q @ Vector((0, 1, 0)), q @ Vector((0, 0, -1))
    hx = math.atan(cam.data.sensor_width / 2 / cam.data.lens)
    asp = sc.render.resolution_x / max(sc.render.resolution_y, 1)
    # En cuadro angosto el mismo texto ocupa mas fraccion de cuadro: se aparta
    # menos del centroide y se acota mas adentro. En 16:9 el factor es 1.0.
    estrecho = min(1.0, asp)
    limite = LIMITE_CUADRO * estrecho
    separacion = separacion * estrecho
    anclas = {r.id: Vector(r.objeto["ancla_pos"]) for r in grupo}
    C = sum(anclas.values(), Vector()) / len(anclas)

    def pantalla(p):
        d = p - M.translation
        z = d.dot(fw)
        if abs(z) < 1e-6:
            return Vector((0.0, 0.0)), 1e-6
        return Vector((d.dot(rg) / (math.tan(hx) * z),
                       d.dot(uv) / (math.tan(hx) * z / asp))), z

    cn, _ = pantalla(C)
    for r in grupo:
        ac = anclas[r.id]
        n, z = pantalla(ac)
        d = n - cn
        if d.length < 1e-3:
            d = Vector((0.0, 1.0))
        d.normalize()
        wh = math.tan(hx) * z
        hh = wh / asp
        # Posicion en coordenadas de cuadro, acotada para que no se salga.
        destino = n + d * (separacion * 2)
        destino.x = max(-limite, min(limite, destino.x))
        destino.y = max(-limite, min(limite, destino.y))
        objetivo = ac + rg * ((destino.x - n.x) * wh) + uv * ((destino.y - n.y) * hh)
        k = CERCANIA
        lab = r.objeto
        # El texto crece HACIA DENTRO: alineado a la derecha si esta en la mitad
        # derecha, a la izquierda si no. Asi nunca invade el borde aunque el
        # ancla quede justo en el limite.
        lab.data.align_x = "RIGHT" if destino.x > 0.15 else "LEFT"
        lab.location = M.translation + (objetivo - M.translation) * k
        lab.scale = (k, k, k)
        lab.rotation_mode = "QUATERNION"
        lab.rotation_quaternion = q
        if r.guia is None:
            continue
        anc = M.translation + (ac - M.translation) * k
        u = lab.location - anc
        L = u.length
        if L < 0.03:
            r.guia.scale = (0, 0, 0)
            continue
        uu = u.normalized()
        ini, fin = min(0.12 * k, L * 0.34), L * 0.68
        if fin - ini < 0.008:
            r.guia.scale = (0, 0, 0)
            continue
        a0, a1 = anc + uu * ini, anc + uu * fin
        r.guia.location = (a0 + a1) * 0.5
        r.guia.rotation_mode = "QUATERNION"
        r.guia.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(uu)
        r.guia.scale = (0.0013, 0.0013, (a1 - a0).length)


#: Busqueda dinamica de sitio para etiquetas (vertical). Direcciones por
#: anillo y radios en fraccion de SEMIANCHO de cuadro. Determinista: mismo
#: orden, mismos candidatos, mismo cuadro en cada construccion.
#:
#: CONVENCION: todo aqui vive en NDC -1..1 (lo que devuelve `pantalla()`), NO
#: en 0..1. Los umbrales van al doble que en fraccion de cuadro completa, y
#: los radios llegan a ~1.0 para cubrir el cuadro entero desde un ancla
#: central. Confundirlas deja la busqueda ciego (paso una vez: todo seguia
#: igual con pesos x100 porque los umbrales median otra cosa).
DINAMICA_DIRECCIONES = 16
DINAMICA_RADIOS = (0.12, 0.24, 0.36, 0.48, 0.62, 0.76, 0.90, 1.04)
#: Margen dentro del cual el texto tiene que caber entero.
DINAMICA_MARGEN = 0.03
#: Peso de preferir fondo vacio, medido con un rayo de camara por candidato.
#: A 0 se apaga el trazado y queda busqueda 2D pura.
DINAMICA_FONDO = 0.15
#: Pesos del costo: cerca del ancla, lejos del sitio, no pisarse, no
#: amontonarse en el mismo sector. Suman direcciones, no mandatos: lo que cabe
#: manda primero (el `fuera` de abajo).
DINAMICA_PESO_CERCA = 1.0
DINAMICA_PESO_FUERA = 2.2
DINAMICA_PESO_SOLAPE = 3.0
DINAMICA_PESO_SECTOR = 3.0
#: Distancia minima entre textos, de borde a borde. Por debajo, el candidato
#: se descarta salvo que no quede otro sitio.
DINAMICA_SEPARACION = 0.07
#: Distancia minima entre guias. El cruce entre guias pesa tanto que solo se
#: permite si no hay alternativa.
DINAMICA_SEPARACION_GUIA = 0.04
DINAMICA_PESO_VIOLACION = 50.0
DINAMICA_PESO_CRUCE = 10.0
#: Aire entre una guia y un texto ajeno. Mayor que entre guias: un palito
#: rozando letras se lee peor que dos palitos paralelos.
DINAMICA_SEPARACION_GUIA_TEXTO = 0.08
#: Peso de esa violacion. Por encima del de textos entre si: lo pidio el ojo.
DINAMICA_PESO_GUIA_TEXTO = 80.0
#: Desde que fraccion de la guia se miden los roces con textos (la mitad
#: interior nace junto a las anclas vecinas y ahi casi todo roza: medirlo
#: atraparia la busqueda y las etiquetas no saldrian nunca del bolsillo).
DINAMICA_GUIA_DESDE = 0.45


def _caja_local(lab) -> tuple[float, float]:
    """Semiejes del texto en sus unidades. Si Blender aun no los midio, estima
    por avance medio: mejor una caja aproximada que ninguna busqueda."""
    xs = [c[0] for c in lab.bound_box]
    ys = [c[1] for c in lab.bound_box]
    hx0, hy0 = (max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2
    if hx0 <= 0 or hy0 <= 0:
        tam = lab.data.size * max(len(lab.data.body or ""), 1)
        hx0, hy0 = 0.30 * tam, 0.35 * tam
    return hx0, hy0


def _orientacion(a, b, c) -> float:
    """Signo del giro a->b->c. Base del test de cruce de segmentos."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segmentos_cruzan(p1, p2, p3, p4) -> bool:
    """Cruce interior con interior. Tocarse en un extremo no cuenta: las guias
    nacen juntas alrededor del bolsillo y eso no es cruzarse."""
    o1 = _orientacion(p1, p2, p3)
    o2 = _orientacion(p1, p2, p4)
    o3 = _orientacion(p3, p4, p1)
    o4 = _orientacion(p3, p4, p2)
    return ((o1 > 0) != (o2 > 0)) and ((o3 > 0) != (o4 > 0))


def _dist_punto_segmento(p, a, b) -> float:
    vx, vy = b[0] - a[0], b[1] - a[1]
    l2 = vx * vx + vy * vy
    if l2 < 1e-12:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / l2))
    return math.hypot(p[0] - (a[0] + t * vx), p[1] - (a[1] + t * vy))


def _dist_segmentos(p1, p2, p3, p4) -> float:
    if _segmentos_cruzan(p1, p2, p3, p4):
        return 0.0
    return min(_dist_punto_segmento(p1, p3, p4),
               _dist_punto_segmento(p2, p3, p4),
               _dist_punto_segmento(p3, p1, p2),
               _dist_punto_segmento(p4, p1, p2))


def _gap_cajas(a, b) -> float:
    """Separacion de borde a borde entre cajas. Negativa si se invaden."""
    dx = max(b[0] - a[2], a[0] - b[2])
    dy = max(b[1] - a[3], a[1] - b[3])
    if dx < 0 and dy < 0:
        return -min(-dx, -dy)
    return math.hypot(max(dx, 0.0), max(dy, 0.0))


def _dist_seg_caja(s0, s1, caja) -> float:
    """Distancia de un segmento a una caja. Cero si la toca o la cruza."""
    x0, y0, x1, y1 = caja
    if x0 <= s0[0] <= x1 and y0 <= s0[1] <= y1:
        return 0.0
    if x0 <= s1[0] <= x1 and y0 <= s1[1] <= y1:
        return 0.0
    esquinas = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    d = float("inf")
    for i in range(4):
        b0, b1 = esquinas[i], esquinas[(i + 1) % 4]
        if _segmentos_cruzan(s0, s1, b0, b1):
            return 0.0
        d = min(d, _dist_segmentos(s0, s1, b0, b1))
    return d


def _guia_mundo(anc, centro):
    """Tramo dibujado de la guia, en mundo. None si degenera. La misma cuenta
    para evaluar candidatas que para dibujar la ganadora: no hay dos verdades.
    """
    u = centro - anc
    L = u.length
    if L < 1e-6:
        return None
    uu = u / L
    k = CERCANIA
    ini, fin = min(0.08 * k, L * 0.15), L * 0.88
    if L < 0.03 or fin - ini < 0.008:
        return None
    return anc + uu * ini, anc + uu * fin


def colocar_dinamicas(cam, rotulos, separacion: float = 0.17) -> None:
    """Cada etiqueta busca su sitio en espiral alrededor de su ancla.

    Solo para cuadro angosto (vertical): con texto grande y anclas juntas, el
    reparto fijo por centroide no garantiza nada —empuja hasta el borde y el
    acote recorta—. Aqui el primer candidato que cabe entero, gana; entre los
    que caben, el mas cercano al ancla que menos se pisa con las ya puestas y
    que mira a fondo mas vacio (un rayo de camara por candidato). La guia se
    dibuja despues, del ancla al sitio elegido: los rayos se adaptan solos.

    Reglas universales, en orden: caber entero; distancia minima entre textos;
    guias sin cruces ni roces y sin pasar sobre textos ajenos; sectores
    distintos alrededor del sitio; cerca del ancla y sobre fondo vacio. Lo que
    no cabe en ningun sitio va al que menos se sale —pero siempre dentro si
    hay hueco—.
    """
    sc = bpy.context.scene
    grupo = [r for r in rotulos if r.objeto is not None]
    if not grupo:
        return
    M = cam.matrix_world
    q = M.to_quaternion()
    rg, uv, fw = q @ Vector((1, 0, 0)), q @ Vector((0, 1, 0)), q @ Vector((0, 0, -1))
    hx = math.atan(cam.data.sensor_width / 2 / cam.data.lens)
    asp = sc.render.resolution_x / max(sc.render.resolution_y, 1)
    tan_hx = math.tan(hx)
    m = DINAMICA_MARGEN
    k = CERCANIA
    anclas = {r.id: Vector(r.objeto["ancla_pos"]) for r in grupo}
    C = sum(anclas.values(), Vector()) / len(anclas)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()

    def pantalla(p):
        d = p - M.translation
        z = d.dot(fw)
        if abs(z) < 1e-6:
            return Vector((0.0, 0.0)), 1e-6
        return Vector((d.dot(rg) / (tan_hx * z),
                       d.dot(uv) / (tan_hx * z / asp))), z

    def fondo(centro):
        # Que hay DETRAS del rotulo: 1.0 es vacio, 0.0 es pared pegada. El
        # origen va un poco por delante del texto para no medirse a si mismo.
        o = centro + (centro - M.translation).normalized() * 0.15
        dv = o - M.translation
        L = dv.length
        if L < 1e-6:
            return 0.0
        pega, donde, _n, _i, _o, _mm = sc.ray_cast(dg, o, dv / L, distance=30.0)
        if not pega:
            return 1.0
        return min(1.0, (donde - centro).length / 8.0)

    cn, _ = pantalla(C)
    puestas, centros, guias = [], [], []
    for r in grupo:
        ac = anclas[r.id]
        n, z_a = pantalla(ac)
        if z_a < 1e-6:
            continue
        lab = r.objeto
        hx0, hy0 = _caja_local(lab)
        anc = M.translation + (ac - M.translation) * k
        d = n - cn
        if d.length < 1e-3:
            d = Vector((0.0, 1.0))
        d.normalize()
        base = n + d * (separacion * 2)
        base.x = max(-LIMITE_CUADRO, min(LIMITE_CUADRO, base.x))
        base.y = max(-LIMITE_CUADRO, min(LIMITE_CUADRO, base.y))
        candidatos = [base]
        for ri, radio in enumerate(DINAMICA_RADIOS):
            for j in range(DINAMICA_DIRECCIONES):
                ang = (2 * math.pi * j / DINAMICA_DIRECCIONES
                       + (ri % 2) * (math.pi / DINAMICA_DIRECCIONES))
                candidatos.append(n + Vector((math.cos(ang),
                                              math.sin(ang))) * radio)
        wh = tan_hx * z_a
        hh = wh / asp
        mejor, mejor_costo, peor, peor_fuera = None, float("inf"), None, float("inf")
        for cand in candidatos:
            objetivo = ac + rg * ((cand.x - n.x) * wh) + uv * ((cand.y - n.y) * hh)
            centro = M.translation + (objetivo - M.translation) * k
            z_c = (centro - M.translation).dot(fw)
            if z_c < 1e-6:
                continue
            c, _ = pantalla(centro)
            ex = hx0 * k / (tan_hx * z_c)
            ey = hy0 * k / (tan_hx * z_c / asp)
            caja = (c.x - ex, c.y - ey, c.x + ex, c.y + ey)
            b0, b1 = m - 1.0, 1.0 - m
            fuera = max(b0 - caja[0], caja[2] - b1, b0 - caja[1],
                        caja[3] - b1, 0.0)
            if fuera > 0:
                if fuera < peor_fuera:
                    peor, peor_fuera = (caja, centro, c), fuera
                continue
            solape = 0.0
            area = max(1e-9, (caja[2] - caja[0]) * (caja[3] - caja[1]))
            for p in puestas:
                ix0, iy0 = max(caja[0], p[0]), max(caja[1], p[1])
                ix1, iy1 = min(caja[2], p[2]), min(caja[3], p[3])
                if ix1 > ix0 and iy1 > iy0:
                    solape += (ix1 - ix0) * (iy1 - iy0) / area
            # Distancia minima entre textos, de borde a borde.
            sep_viol = 0.0
            for p in puestas:
                gap = _gap_cajas(caja, p)
                if gap < DINAMICA_SEPARACION:
                    sep_viol = max(sep_viol, 1.0 - gap / DINAMICA_SEPARACION)
            # La guia candidata, medida como se dibujaria: ni cruces ni roces
            # con las puestas, ni sobre textos ajenos (con mas aire que entre
            # guias: un palito rozando letras se lee peor que paralelas). Los
            # roces se miden desde fuera del primer tramo: ahi las guias nacen
            # juntas y eso no cuenta.
            guia_viol = 0.0
            guia_txt = 0.0
            tramo = _guia_mundo(anc, centro)
            g = None
            if tramo is not None:
                a0n, _ = pantalla(tramo[0])
                a1n, _ = pantalla(tramo[1])
                g = ((a0n.x, a0n.y), (a1n.x, a1n.y))
                t0 = DINAMICA_GUIA_DESDE
                ge = ((g[0][0] + (g[1][0] - g[0][0]) * t0,
                       g[0][1] + (g[1][1] - g[0][1]) * t0), g[1])
                for h in guias:
                    if h is None:
                        continue
                    if _segmentos_cruzan(g[0], g[1], h[0], h[1]):
                        guia_viol += DINAMICA_PESO_CRUCE
                    else:
                        dg01 = _dist_segmentos(g[0], g[1], h[0], h[1])
                        if dg01 < DINAMICA_SEPARACION_GUIA:
                            guia_viol += 1.0 - dg01 / DINAMICA_SEPARACION_GUIA
                for p in puestas:
                    dg02 = _dist_seg_caja(ge[0], ge[1], p)
                    if dg02 < DINAMICA_SEPARACION_GUIA_TEXTO:
                        guia_txt += 1.0 - dg02 / DINAMICA_SEPARACION_GUIA_TEXTO
                for h in guias:
                    if h is None:
                        continue
                    he = ((h[0][0] + (h[1][0] - h[0][0]) * t0,
                           h[0][1] + (h[1][1] - h[0][1]) * t0), h[1])
                    dg03 = _dist_seg_caja(he[0], he[1], caja)
                    if dg03 < DINAMICA_SEPARACION_GUIA_TEXTO:
                        guia_txt += 1.0 - dg03 / DINAMICA_SEPARACION_GUIA_TEXTO
            # Fuera del sitio y en otro sector que las ya puestas: asi se
            # reparten arriba/abajo/izquierda en vez de amontonarse encima del
            # bolsillo. `cn` es el centroide de anclas, o sea el sitio en cuadro.
            vc = cand - cn
            lejos = vc.length
            ang_c = math.atan2(vc.y, vc.x)
            sector = 0.0
            for pc in centros:
                vp = pc - cn
                if vp.length < 1e-6:
                    continue
                sector += max(0.0, math.cos(ang_c - math.atan2(vp.y, vp.x))) ** 2
            costo = (DINAMICA_PESO_CERCA * (cand - n).length
                     - DINAMICA_PESO_FUERA * lejos
                     + DINAMICA_PESO_SOLAPE * solape
                     + DINAMICA_PESO_SECTOR * sector
                     - DINAMICA_FONDO * fondo(centro)
                     + DINAMICA_PESO_VIOLACION * (sep_viol + guia_viol)
                     + DINAMICA_PESO_GUIA_TEXTO * guia_txt)
            if costo < mejor_costo:
                mejor, mejor_costo = (caja, centro, c), costo
        if mejor is None:
            if peor is None:
                continue
            caja, centro, c = peor
        else:
            caja, centro, c = mejor
        puestas.append(caja)
        centros.append(c)
        lab.data.align_x = "RIGHT" if c.x > 0.15 else "LEFT"
        lab.location = centro
        lab.scale = (k, k, k)
        lab.rotation_mode = "QUATERNION"
        lab.rotation_quaternion = q
        if r.guia is None:
            guias.append(None)
            continue
        tramo = _guia_mundo(anc, lab.location)
        if tramo is None:
            r.guia.scale = (0, 0, 0)
            guias.append(None)
            continue
        a0, a1 = tramo
        r.guia.location = (a0 + a1) * 0.5
        r.guia.rotation_mode = "QUATERNION"
        r.guia.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(
            ((a1 - a0) / (a1 - a0).length))
        # Guia gruesa: en vertical se lee a distancia de movil.
        r.guia.scale = (0.0022, 0.0022, (a1 - a0).length)
        g0, _ = pantalla(a0)
        g1, _ = pantalla(a1)
        guias.append(((g0.x, g0.y), (g1.x, g1.y)))


# ── rotulo pegado a la camara ────────────────────────────────────────────
def crear_pantalla(id_: str, texto: str, cam, prototipo,
                   esquina: str = "inferior_izquierda",
                   escala_texto: float = 1.0, margen: float = 0.10,
                   lente_referencia: float | None = None,
                   distancia: float | None = None) -> Rotulo:
    """Texto emparentado a la camara: nunca se ladea ni sale de cuadro.

    Se cuelga a 1 unidad por delante y se situa en coordenadas de cuadro, asi
    que vale igual para 16:9 que para 9:16 sin tocar nada.

    `lente_referencia` tiene que ser la lente MAS LARGA del plano, no la del
    momento de crearlo: la lente esta animada, y colocar el rotulo con el
    encuadre abierto lo deja fuera de cuadro en cuanto se cierra.

    AVISO: a `dist` corta, la profundidad de campo —enfocada al sitio activo—
    lo deja irreconocible. Para texto permanente (procedencia) usar el sellado
    nativo de `salida/procedencia.py`. Esto sirve para ganchos de redes en
    planos sin desenfoque, o con `formato.profundidad_de_campo=False`.
    """
    sc = bpy.context.scene
    lab, mat = _duplicar(prototipo, f"Rot_{id_}", texto, escala_texto * 0.42)
    lab.parent = cam
    # Identidad, NO la inversa de la camara: la camara lleva una restriccion
    # Track To y su matriz cambia cada fotograma, asi que una inversa tomada al
    # crear el rotulo lo deja transformado dos veces y fuera de cuadro.
    lab.matrix_parent_inverse = Matrix.Identity(4)

    # `distancia` deberia ser la DISTANCIA DE ENFOQUE del plano: ahi el texto
    # sale nitido. Como la posicion y la escala son lineales en `dist`, el
    # tamano en pantalla no cambia, solo la profundidad — asi que se puede
    # mover libremente para esquivar el desenfoque o la geometria.
    dist = distancia if distancia else 0.12
    lente = lente_referencia or cam.data.lens
    hx = math.atan(cam.data.sensor_width / 2 / lente)
    semi_x = math.tan(hx) * dist
    semi_y = semi_x / (sc.render.resolution_x / max(sc.render.resolution_y, 1))
    x = -semi_x + margen * 2 * semi_x
    y = -semi_y + margen * 2 * semi_y
    lab.data.align_x = "LEFT"
    if hasattr(lab.data, "space_line"):
        lab.data.space_line = 0.90
    # Blender alinea el texto por ARRIBA por defecto, asi que un rotulo puesto
    # en el borde inferior cuelga fuera de cuadro. Hay que decirlo explicito.
    lab.data.align_y = "BOTTOM"
    if "derecha" in esquina:
        x = semi_x - margen * 2 * semi_x
        lab.data.align_x = "RIGHT"
    if "superior" in esquina:
        y = semi_y - margen * 2 * semi_y
        lab.data.align_y = "TOP"
    lab.location = (x, y, -dist)
    # El prototipo viene en modo QUATERNION (se lo puso el billboard viejo), y
    # con ese modo `rotation_euler` no hace absolutamente nada: el rotulo salia
    # girado en diagonal con la orientacion heredada.
    lab.rotation_mode = "XYZ"
    lab.rotation_euler = (0.0, 0.0, 0.0)
    lab.scale = (dist, dist, dist)
    return Rotulo(id=id_, texto=texto, objeto=lab, guia=None, material=mat)


# ── horneado comun ───────────────────────────────────────────────────────
def hornear(rotulos, frames) -> None:
    """Ventana de visibilidad y fundido de cada rotulo."""
    for r in rotulos:
        if r.objeto is None:
            continue
        a, b = r.ventana
        for o in (r.objeto, r.guia):
            if o is not None:
                H.visible_en(o, frames, a, b)
        if r.fundido:
            H.fundir(r.material, frames, H.curva(r.fundido, frames))
