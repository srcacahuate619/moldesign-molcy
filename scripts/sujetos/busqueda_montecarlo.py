"""SUJETO: la busqueda de Montecarlo de Vina sobre la caja de acoplamiento REAL.

Todo lo que se dibuja sale de `docking.json` del paquete, que produce
molDesign-build: la caja son los parametros con los que CORRIO Vina (centro y
tamano en Angstrom), las poses son las que el motor devolvio con su afinidad,
y la traza es el muestreo Metropolis con la funcion de puntaje de Vina, tal
cual salio, con el sembrado declarado. Nada se inventa aqui: si el contrato no
lo trae, este sujeto se abstiene y dice que falta (ver `disponible`).

Nota de diseno (historica): este sujeto NO vive "en el sitio activo". Es una
nube repartida por toda la caja de acoplamiento mas una magnitud que evoluciona
en el tiempo. Por eso quien lo monta es el GUION `x`: plano fijo sobre la
caja, sin pausas, y rotulos de pantalla en vez de etiquetas ancladas.
"""
from __future__ import annotations

from nucleo.ciencia import ESCALA
from variables.sujeto import Contexto, Montado, SujetoNoDisponible

ID = "busqueda_montecarlo"
DESCRIPCION = "La nube de poses candidatas y la puntuacion por iteracion."

MAX_POSES = 5            # las mejores; las demas constan en el acta
MAX_RECHAZADAS = 400     # las aceptadas se dibujan TODAS; el rechazo se muestrea

COLOR_CAJA = (0.36, 0.62, 1.0)
COLOR_ESFERA = (0.50, 0.72, 1.0)
COLOR_ACEPTADA = (1.0, 0.62, 0.20)
COLOR_RECHAZADA = (0.75, 0.32, 0.32)
COLOR_CAMINANTE = (1.0, 0.90, 0.55)


# ── disponibilidad: la cadena de buena fe antes de dibujar nada ─────────────
def disponible(paq) -> tuple[bool, str]:
    d = paq.dock
    if d is None:
        return False, ("el paquete no trae `docking.json` valido "
                       "(schema moldesign.dock/1 con caja y poses). Lo genera "
                       "molDesign-build: `scripts/scene_export/"
                       "build_docking_package.py --pdb-id ...`")
    if not (d.get("traza") or {}).get("pasos"):
        return False, ("docking.json no trae la traza del muestreo "
                       "(energia por iteracion, aceptados y rechazados). "
                       "Sin ella no hay busqueda que contar")
    faltantes = [p["archivo"] for p in d["poses"]
                 if not p.get("archivo") or paq.ruta_dock(p["archivo"]) is None]
    if faltantes:
        return False, ("docking.json cita poses que no estan en el paquete: "
                       + ", ".join(faltantes[:3]))
    return True, (f"{len(d['poses'])} poses, "
                  f"{len(d['traza']['pasos'])} pasos de muestreo")


# ── geometria ───────────────────────────────────────────────────────────────
def _material_emision(nombre: str, color: tuple, fuerza: float):
    """Material de emision puro: fundir() lo enciende por Strength."""
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    salida = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1.0)
    em.inputs["Strength"].default_value = fuerza
    nt.links.new(em.outputs["Emission"], salida.inputs["Surface"])
    return m


def _caja(nombre: str, centro_b: Vector, tam_b: Vector, grosor: float, mat):
    """Las doce aristas de la caja REAL de Vina como una curva biselada."""
    cx, cy, cz = centro_b
    sx, sy, sz = (t / 2.0 for t in tam_b)
    # esquinas ordenadas por bits: i = x + 2y + 4z
    V = [(cx + (sx if i & 1 else -sx), cy + (sy if i & 2 else -sy),
          cz + (sz if i & 4 else -sz)) for i in range(8)]
    aristas = [(0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3), (2, 6),
               (3, 7), (4, 5), (4, 6), (5, 7), (6, 7)]
    cu = bpy.data.curves.new(nombre, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = grosor
    cu.bevel_resolution = 0
    for a, b in aristas:
        s = cu.splines.new("POLY")
        s.points.add(1)
        s.points[0].co = (*V[a], 1.0)
        s.points[1].co = (*V[b], 1.0)
    cu.materials.append(mat)
    obj = bpy.data.objects.new(nombre, cu)
    bpy.context.scene.collection.objects.link(obj)
    return obj, V


def _esfera(nombre: str, centro_b: Vector, radio_b: float, mat):
    """La esfera de evidencia del sitio: translucida, y su radio se MIde."""
    me = bpy.data.meshes.new(nombre)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=radio_b,
                               matrix=Matrix.Translation(centro_b))
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(nombre, me)
    bpy.context.scene.collection.objects.link(obj)
    me.materials.append(mat)
    return obj


def _nube(nombre: str, puntos: list[Vector], radio: float, mat):
    """Una unica malla con todas las esferas de la traza (barata de rendir)."""
    if not puntos:
        return None
    bm = bmesh.new()
    for p in puntos:
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=radio,
                                   matrix=Matrix.Translation(p))
    me = bpy.data.meshes.new(nombre)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(nombre, me)
    bpy.context.scene.collection.objects.link(obj)
    me.materials.append(mat)
    return obj


def _material_translucido(nombre: str, color: tuple, alfa: float):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    nt = m.node_tree
    bs = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"),
              None)
    if bs:
        bs.inputs["Base Color"].default_value = (*color, 1.0)
        bs.inputs["Alpha"].default_value = alfa
        bs.inputs["Roughness"].default_value = 0.6
    m.surface_render_method = "DITHERED"
    return m


# ── montaje ─────────────────────────────────────────────────────────────────
def cargar(paq, ctx: Contexto | None = None) -> Montado:
    ok, razon = disponible(paq)
    if not ok:
        raise SujetoNoDisponible(razon)
    ctx = ctx or Contexto()
    # Todo lo que dibuja se importa AQUI: `disponible` tiene que poder
    # responder sin Blender (la interfaz y las pruebas no lo tienen).
    global bpy, bmesh, mn, Matrix, Vector, arte, receptor
    import bmesh                                                             # noqa: E402
    import bpy                                                               # noqa: E402
    import bl_ext.blender_org.molecularnodes as mn                           # noqa: E402
    from mathutils import Matrix, Vector                                     # noqa: E402
    from nucleo import arte, receptor                                        # noqa: E402
    d = paq.dock
    pref = f"{paq.pdb_id}_Dock_"

    m = Montado()
    centro_a = Vector(d["caja"]["centro"])
    tam_a = Vector(d["caja"]["tamano"])
    centro_b = centro_a * ESCALA
    tam_b = tam_a * ESCALA

    faltantes = [p["archivo"] for p in d["poses"]
                 if paq.ruta_dock(p["archivo"]) is None]
    if faltantes:
        raise SujetoNoDisponible("faltan archivos de pose: " + ", ".join(faltantes))

    # caja: los parametros con los que CORRIO el motor
    mat_caja = _material_emision(pref + "Caja", COLOR_CAJA, 4.0)
    caja_obj, esquinas = _caja(pref + "Caja", centro_b, tam_b,
                               max(tam_b) * 0.004, mat_caja)
    m.objetos.append(caja_obj)
    m.materiales.append(mat_caja)
    s, sy, sz = (float(v) for v in tam_a)
    m.anclas.append(("caja", f"caja de busqueda: {s:g} x {sy:g} x {sz:g} A",
                     Vector(esquinas[7])))
    m.medido["caja_a"] = {"centro": [round(v, 3) for v in centro_a],
                          "tamano": [round(v, 3) for v in tam_a]}
    # La caja es el encuadre de AMBOS planos en esta escena: en el general por
    # contexto y de cerca porque ES el sujeto. Que el plano de cerca quede más
    # lejos que el general del receptor es correcto aquí: la cámara da un paso
    # atrás para mostrar dónde buscó el algoritmo (ver _TOLERANCIA_QC).
    m.dianas_generales += [Vector(v) for v in esquinas]
    m.dianas += [Vector(v) for v in esquinas]

    # esfera de evidencia: radio medido por dispersion de hotspots
    radio_a = min(tam_a) / 2.0
    if ctx.receptor is not None and ctx.receptor.hotspots:
        distancias = []
        for h in ctx.receptor.hotspots:
            c = receptor.centro_de_residuo(ctx.receptor.molecula, h.numero,
                                           receptor.indice_de_cadena(paq, h.cadena))
            if c is not None:
                distancias.append((c - ctx.pivote).length / ESCALA)
        if distancias:
            radio_a = max(distancias)
            m.medido["esfera_radio_a"] = round(radio_a, 2)
    mat_esfera = _material_translucido(pref + "Esfera", COLOR_ESFERA, 0.10)
    m.objetos.append(_esfera(pref + "Esfera", centro_b, radio_a * ESCALA,
                             mat_esfera))
    m.materiales.append(mat_esfera)

    # traza del muestreo: aceptadas enteras, rechazadas muestreadas y declarado
    pasos = d["traza"]["pasos"]
    aceptadas = [p for p in pasos if p.get("aceptada")]
    rechazadas = [p for p in pasos if not p.get("aceptada")]
    if len(rechazadas) > MAX_RECHAZADAS:
        n = len(rechazadas)
        rechazadas = [rechazadas[i * n // MAX_RECHAZADAS]
                      for i in range(MAX_RECHAZADAS)]
        m.notas.append(
            f"traza: de los {n} pasos rechazados se dibuja una muestra "
            f"uniforme de {MAX_RECHAZADAS} (los {len(aceptadas)} pasos "
            "aceptados se dibujan TODOS). La energia por iteracion completa "
            "sigue en docking.json.")
    r_acep, r_rech = max(tam_b) * 0.010, max(tam_b) * 0.005
    mat_acep = _material_emision(pref + "Aceptadas", COLOR_ACEPTADA, 6.0)
    mat_rech = _material_emision(pref + "Rechazadas", COLOR_RECHAZADA, 1.2)
    pts_a = [Vector(p["centro"]) * ESCALA for p in aceptadas]
    pts_r = [Vector(p["centro"]) * ESCALA for p in rechazadas]
    nube_a = _nube(pref + "Aceptadas", pts_a, r_acep, mat_acep)
    nube_r = _nube(pref + "Rechazadas", pts_r, r_rech, mat_rech)
    for o in (nube_a, nube_r):
        if o is not None:
            m.objetos.append(o)
    m.materiales += [mat_acep, mat_rech]
    m.dianas += (pts_a + pts_r)[:: max(1, len(pts_a + pts_r) // 40)]

    # el caminante: recorre por la caja los pasos ACEPTADOS, que es lo unico
    # que se mueve en un muestreo Metropolis. Su ruta sale de la traza real.
    mat_cam = _material_emision(pref + "Caminante", COLOR_CAMINANTE, 10.0)
    cam = _esfera(pref + "Caminante", pts_a[0] if pts_a else centro_b,
                  r_acep * 2.6, mat_cam)
    m.objetos.append(cam)
    m.materiales.append(mat_cam)
    m.extra["caminante"] = cam.name
    m.extra["traza_aceptados"] = [tuple(p) for p in pts_a]

    # poses del acoplamiento, orden del motor, mejor primero
    poses = sorted(d["poses"], key=lambda p: p.get("rank", 99))[:MAX_POSES]
    for p in poses:
        ruta = paq.ruta_dock(p["archivo"])
        mol = mn.Molecule.load(str(ruta), name=f"{pref}Pose{p['rank']}")
        # el PDB de la pose no trae CONECT (como site_ligand.pdb): enlaces por
        # distancia, misma convención declarada del ligando cocristalizado
        from sujetos.ligando_cocristal import inferir_enlaces
        inferir_enlaces(mol.object)
        mol.add_style("ball_and_stick", name=f"pose{p['rank']}")
        mat = arte.material_del_estilo(mol, "Ball and Stick",
                                       f"{pref}Pose{p['rank']}_mat")
        if mat:
            arte.realzar_protagonista(mat)
        obj = mol.object
        m.secundarios.append(obj)
        if mat:
            m.materiales_secundarios.append(mat)
        c = arte.centro_evaluado(obj)
        af = p.get("afinidad_kcal_mol")
        texto = f"#{p['rank']}" + (f"  {af:.1f} kcal/mol"
                                   if isinstance(af, (int, float)) else "")
        m.anclas.append((f"pose{p['rank']}", texto, c))
        m.dianas.append(c)
        if p["rank"] == 1:
            m.medido["mejor_pose"] = {k: p.get(k) for k in
                                      ("afinidad_kcal_mol", "rmsd_cristal_a")}
            rmsd = p.get("rmsd_cristal_a")
            if isinstance(rmsd, (int, float)):
                m.anclas.append(("rmsd", f"RMSD {rmsd:.2f} A vs cristal", c))

    m.medido["n_poses_dibujadas"] = len(poses)
    m.medido["n_pasos"] = len(pasos)
    m.medido["n_aceptados"] = len(aceptadas)
    m.medido["motor"] = d.get("motor", {})
    if aceptadas:
        m.notas.append(
            f"traza {d['traza'].get('tipo', 'muestreo')} con semilla "
            f"{d['traza'].get('semilla')}: {len(aceptadas)} aceptados de "
            f"{len(pasos)} pasos. La afinidad de las poses sale de la corrida "
            "de acoplamiento real; el muestreo no incluye refinado por "
            "gradiente (el MC puro de Vina).")
    return m
