"""EL MAESTRO. Unico punto de entrada; todo lo demas se enchufa aqui.

    blender -b --factory-startup --addons bl_ext.blender_org.molecularnodes \
        --python maestro.py -- 1HSG --guion sitio_activo --formato biblioteca

    blender -b --python maestro.py -- 1HSG --listar

No contiene ninguna decision artistica ni cientifica: solo cablea las capas y
escribe el acta. Cada variable vive en su archivo y se descubre sola.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
if str(AQUI) not in sys.path:
    sys.path.insert(0, str(AQUI))

import bpy                                                      # noqa: E402
from mathutils import Vector                                    # noqa: E402

from nucleo import arte, camara, encuadre, horneado as H, oclusion, receptor  # noqa: E402
from nucleo.ciencia import Paquete                              # noqa: E402
from nucleo.rutas import ESCENAS, PLANTILLA_ARTE, carpeta_de_caso  # noqa: E402
from salida import control, procedencia, render                 # noqa: E402
from variables import formato as fmt                            # noqa: E402
from variables import guion as gui                              # noqa: E402
from variables import controles, rotulos, sujeto                # noqa: E402


# ── inventario ───────────────────────────────────────────────────────────
def listar(paq=None) -> None:
    print("\nFORMATOS (para donde es):")
    for n, f in sorted(fmt.disponibles().items()):
        print(f"  {n:<18} {f.ancho}x{f.alto} {f.segundos:>5.1f}s  "
              f"bucle={int(f.bucle)} etq3d={int(f.etiquetas_3d)}  {f.descripcion}")
    print("\nGUIONES (que se cuenta):")
    for n, g in sorted(gui.disponibles().items()):
        print(f"  {n:<18} {len(g.BEATS)} beats  {getattr(g, 'DESCRIPCION', '')}")
    print("\nSUJETOS (que hay en el sitio activo):")
    if paq is None:
        for n, m in sorted(sujeto.disponibles().items()):
            print(f"  {n:<22} {getattr(m, 'DESCRIPCION', '')}")
    else:
        for n, info in sujeto.inventario(paq).items():
            marca = "si " if info["disponible"] else "NO "
            print(f"  [{marca}] {n:<22} {info['razon']}")
    print()


# ── carpeta del caso ─────────────────────────────────────────────────────
def carpeta(paq: Paquete) -> Path:
    if os.environ.get("MOLCY_OUTPUT_DIR"):
        return Path(os.environ["MOLCY_OUTPUT_DIR"]).resolve()
    return carpeta_de_caso(paq.pdb_id, paq.familia)


def sembrar(paq: Paquete, destino: Path) -> None:
    (destino / "raw").mkdir(parents=True, exist_ok=True)
    (destino / "blender").mkdir(exist_ok=True)
    for n in ("scene.json", "MANIFEST.sha256", "docking.json"):
        if (paq.raiz / n).exists():
            shutil.copy2(paq.raiz / n, destino / n)
    for n in ("deposited", "prepared", "site_ligand"):
        p = paq.ruta(n)
        if p:
            shutil.copy2(p, destino / "raw" / p.name)
    if paq.dock is not None and (paq.raiz / "docking").is_dir():
        shutil.copytree(paq.raiz / "docking", destino / "docking",
                        dirs_exist_ok=True)


def huella_de_construccion(registro: dict) -> str:
    """Que tiene que ser igual para poder retomar un render cortado.

    El acta (sin los tiempos), el codigo de la maquina y la plantilla de arte.
    Si cualquiera cambia, los fotogramas viejos ya no son de este video.
    """
    h = hashlib.sha256()
    estable = {k: v for k, v in registro.items() if k != "construido_s"}
    h.update(json.dumps(estable, sort_keys=True, ensure_ascii=False,
                        default=str).encode("utf-8"))
    for py in sorted(AQUI.rglob("*.py")):
        if {"interfaz", "pruebas", "herramientas", "__pycache__"} & set(py.parts):
            continue
        h.update(py.relative_to(AQUI).as_posix().encode("utf-8"))
        h.update(py.read_bytes())
    if PLANTILLA_ARTE.exists():
        h.update(PLANTILLA_ARTE.read_bytes())
    return h.hexdigest()


def vista_previa(pos: float, salida: str, formato, rangos, n_frames,
                 capa_titulo) -> int:
    """Un fotograma, para ver el efecto de los mandos antes de gastar un video.

    A media resolucion y con el titulo en la pasada principal (en el video va
    en su propia capa): es una aproximacion rapida, no un fotograma final.
    """
    sc = bpy.context.scene
    f = 1 + int(round(min(100.0, max(0.0, pos)) / 100.0 * (n_frames - 1)))
    beat = next((b for b, (i, j) in rangos.items() if i <= f <= j), "")
    if capa_titulo:
        for nombre in capa_titulo.get("objetos", [capa_titulo.get("objeto")]):
            if nombre and bpy.data.objects.get(nombre):
                bpy.data.objects[nombre].visible_camera = True
    pct = min(formato.escala_render, 50)
    sc.render.stamp_font_size = max(8, int(sc.render.stamp_font_size * pct
                                           / formato.escala_render))
    sc.render.resolution_percentage = pct
    sc.frame_set(f)
    sc.render.filepath = salida
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"VISTA_PREVIA: {salida}.png cuadro={f}/{n_frames} beat={beat} "
          f"segundos={time.time() - t:.2f}", flush=True)
    return 0


# ── medicion ─────────────────────────────────────────────────────────────
def medir(paq, rec, montado, guion, formato) -> dict:
    sc = bpy.context.scene
    sc.frame_set(1)
    bpy.context.view_layer.update()

    pts = receptor.puntos(rec.molecula)
    centro, nucleo = encuadre.centro_recortado(pts, 0.97)
    asp = formato.aspecto
    azimuts = [i * 30.0 for i in range(12)]
    # Si el sujeto declara contenido que debe caber ya en el plano general
    # (la caja de acoplamiento), encuadra receptor Y sujeto, no solo receptor.
    if montado.dianas_generales:
        nucleo = list(nucleo) + list(montado.dianas_generales)
    D1 = encuadre.distancia(nucleo, centro, guion.LENTE_GENERAL, asp,
                            guion.EL_GENERAL, azimuts, margen=1.08)

    K = Vector(paq.objetivo)
    dianas = []
    for h in rec.hotspots:
        c = receptor.centro_de_residuo(rec.molecula, h.numero,
                                       receptor.indice_de_cadena(paq, h.cadena))
        if c:
            dianas.append(c)
    dianas += list(montado.dianas)
    # los puntos medios de los contactos son parte de lo que hay que ver
    for _id, _txt, _pos in montado.anclas:
        if _id.startswith("dist"):
            dianas.append(_pos)
    if not dianas:
        # Un receptor sin ligando sigue teniendo geometría real alrededor de
        # la caja. Usarla sólo para la cámara evita una distancia cero sin
        # inventar un sitio, hotspot o contacto molecular.
        cercanos = sorted(pts, key=lambda p: (p - K).length)[:60]
        dianas = cercanos[::max(1, len(cercanos) // 20)]
        if not dianas or max((p - K).length for p in dianas) < 1e-6:
            raise ValueError("El receptor no contiene geometría para encuadrar")

    provisional = encuadre.distancia(dianas, K, guion.LENTE_PRIMER_PLANO, asp,
                                     guion.EL_PRIMER_PLANO, [0, 90, 180, 270],
                                     margen=1.75)

    # Pose heroe: azimut Y elevacion, ponderando por grupo y premiando que las
    # dianas queden separadas en pantalla. Antes solo se buscaba el azimut, con
    # la elevacion clavada en una constante heredada de la camara de EGFR.
    grupos = []
    if montado.dianas:
        grupos.append(("ligando", 0.50, list(montado.dianas)))
    for h in rec.hotspots:
        c = receptor.centro_de_residuo(rec.molecula, h.numero,
                                       receptor.indice_de_cadena(paq, h.cadena))
        if c:
            grupos.append((f"hot_{h.etiqueta}", 0.35 / max(len(rec.hotspots), 1), [c]))
    medios = [p for i, _t, p in montado.anclas if i.startswith("dist")]
    if medios:
        grupos.append(("contactos", 0.15, medios))
    if not grupos:
        grupos = [("sitio", 1.0, dianas)]

    def _dist_req(az_, el_):
        return encuadre.distancia(dianas, K, guion.LENTE_PRIMER_PLANO, asp,
                                  el_, [az_], margen=1.75)

    pose = oclusion.mejor_pose(grupos, K, provisional, guion.LENTE_PRIMER_PLANO,
                               asp, distancia_requerida=_dist_req)
    az, el = pose["azimut"], pose["elevacion"]
    vis = oclusion.visibilidad(dianas, encuadre.posicion(K, az, el, provisional))
    D0 = encuadre.distancia(dianas, K, guion.LENTE_PRIMER_PLANO, asp,
                            el, [az], margen=1.75)

    orbita = None
    if formato.bucle:
        # En un bucle se pasa por los 360 grados a la fuerza: el azimut no se
        # elige. Lo unico ajustable es la altura del recorrido, y no se estaba
        # ajustando. Se puntua por el peor instante, que en un bucle se repite.
        orbita = oclusion.mejor_elevacion_orbita(dianas, centro, D1)
    arco = (oclusion.arco_cerrado(dianas, K, az - guion.SWEEP_GENERAL - 22.0,
                                  el, D0)
            if formato.bucle else
            oclusion.mejor_arco(dianas, K, az - guion.SWEEP_GENERAL - 22.0,
                                el, D0))

    campos = encuadre.posicion(K, az, el, D0)
    cerca = [(p - K).length for p in pts if (p - campos).length < D0 * 1.7]
    g0 = encuadre.tope_de_gradiente(cerca, 0.38) or D0 * 0.42
    g1 = encuadre.tope_de_gradiente([(p - K).length for p in pts], 0.55) or D1 * 0.65

    # Radio del fantasma: cuanto se aparta del pivote lo que hay que ensenar.
    # Es la dispersion de las dianas, no un numero inventado: si los hotspots
    # se abren, el cilindro del portal se abre con ellos.
    radio = max(((p - K).length for p in dianas), default=0.0)
    radio_portal = radio if radio > 1e-6 else D0 * 0.35

    return {"centro_general": centro, "dist_general": D1, "pivote": K,
            "dist_primer_plano": D0, "azimut": az, "elevacion": el,
            "pose_heroe": pose,
            "visibilidad_azimut": round(vis, 3), "arco": arco,
            "elevacion_general": (orbita["elevacion"] if orbita
                                  else guion.EL_GENERAL),
            "orbita": orbita,
            "gradiente_general": max(g1, g0), "gradiente_cerca": g0,
            "disolucion_cerca": (D0 * 0.068, D0 * 0.181),
            "radio_portal": round(radio_portal, 4),
            # Lo lee la puerta `dianas_dispersas`, que sin esta clave nunca
            # disparaba. En las 22 carpetas con acta el maximo es 0.26 * D1;
            # el umbral fatal es 0.35.
            "radio_dianas": round(radio, 4),
            "n_dianas": len(dianas)}


# ── principal ────────────────────────────────────────────────────────────
def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="maestro")
    ap.add_argument("pdb_id", nargs="?")
    ap.add_argument("--guion", default="sitio_activo")
    ap.add_argument("--formato", default="biblioteca")
    ap.add_argument("--renderizador", choices=("cpu", "gpu"), default="gpu")
    ap.add_argument("--sujeto", default="ligando_cocristal")
    ap.add_argument("--hotspots", type=int, default=3)
    ap.add_argument("--sufijo", default="",
                    help="se anade a .blend, build_*.json, render_* y MP4: "
                         "asi una iteracion nueva nunca pisa la anterior")
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--solo-construir", action="store_true")
    ap.add_argument("--forzar", action="store_true",
                    help="renderiza aunque la puerta de calidad encuentre "
                         "fallos fatales (deja constancia en el acta)")
    ap.add_argument("--experimental-look", action="store_true",
                    help="activa variantes visuales desechables")
    ap.add_argument("--ajustes", default="",
                    help="JSON con las barras (0-100) e interruptores de la "
                         "interfaz; ver variables/controles.py")
    ap.add_argument("--vista-previa", type=float, default=None,
                    help="rinde UN fotograma en esa posicion del video (0-100) "
                         "y sale: sin .blend, sin acta y sin tocar el caso")
    ap.add_argument("--salida-vista", default="",
                    help="ruta del PNG de la vista previa, sin extension")
    a = ap.parse_args(argv)

    if a.listar:
        paq = Paquete.cargar(ESCENAS / a.pdb_id) if a.pdb_id else None
        listar(paq)
        return 0
    if not a.pdb_id:
        ap.error("falta el PDB ID (o usa --listar)")

    t0 = time.time()
    sufijo = f"_{a.sufijo}" if a.sufijo else ""
    paq = Paquete.cargar(ESCENAS / a.pdb_id)
    formato = fmt.cargar(a.formato)
    # Los mandos de la interfaz: solo lo que el usuario movio. Sin ajustes,
    # formato y extras quedan exactamente como en produccion.
    ajustes = controles.leer(a.ajustes) if a.ajustes else {}
    formato, extras, resueltos = controles.aplicar(formato, ajustes)
    formato = fmt.para_dispositivo(formato, a.renderizador)
    experimental = a.experimental_look and extras["look_v4"]
    vista = a.vista_previa is not None
    guion = gui.cargar(a.guion)
    # El guion puede fijar su sujeto: el de `x` es la busqueda de Montecarlo y
    # no negocia con `--sujeto`. La bandera manda solo si el guion no fija uno.
    mod_sujeto = sujeto.cargar(getattr(guion, "SUJETO", None) or a.sujeto)
    acta = gui.Acta()
    destino = carpeta(paq)
    print(f"CASO: {destino.name} | guion={guion.NOMBRE} formato={formato.nombre} "
          f"sujeto={mod_sujeto.ID}")
    if not vista:
        sembrar(paq, destino)

    # montaje
    sc = bpy.context.scene
    arte.limpiar_escena_por_defecto()
    arte_importado = arte.importar()
    rec = receptor.montar(paq, arte_importado, n_hotspots=a.hotspots)
    arte.acabado_receptor(rec.mat_cartoon, experimental=experimental)
    receptor.anclar_gradiente(rec, Vector(paq.objetivo))
    arte.colocar_luces(arte_importado, Vector(paq.objetivo))

    arte.compositor()
    ok, razon = mod_sujeto.disponible(paq)
    montado = sujeto.Montado()
    if ok:
        ctx = sujeto.Contexto(receptor=rec, arte=arte_importado,
                              pivote=Vector(paq.objetivo))
        montado = mod_sujeto.cargar(paq, ctx)
        if not extras["contactos"] and montado.secundarios:
            # Apagar la capa no cambia lo medido (sigue en el acta): solo no se
            # dibujan las lineas ni sus etiquetas de distancia.
            for o in montado.secundarios:
                bpy.data.objects.remove(o, do_unlink=True)
            montado.secundarios.clear()
            montado.materiales_secundarios.clear()
            montado.anclas[:] = [x for x in montado.anclas
                                 if not x[0].startswith("dist")]
            print("AJUSTE: lineas de contacto apagadas")
    else:
        acta.anota(sujeto=mod_sujeto.ID, decision="omitido", razon=razon)
        print(f"SUJETO NO DISPONIBLE: {mod_sujeto.ID} — {razon}")

    # Las varillas se crean AHORA, no en el montaje: una linea de contacto es
    # una afirmacion sobre dos atomos, asi que el residuo que la recibe tiene
    # que estar dibujado. Ver `receptor.poner_varillas`.
    dibujados = receptor.poner_varillas(
        rec, paq, (montado.medido.get("residuos_de_contacto", ())
                   if extras["contactos"] else ()))
    if dibujados:
        print(f"VARILLAS: residuos {dibujados}")

    # guion x formato
    if guion.NOMBRE == "x":
        from dataclasses import replace
        formato = replace(formato, papeles=None, bucle=False)
    beats = gui.resolver(guion.BEATS, paq, {"sujeto": ok}, formato, acta)
    rangos, n_frames = gui.repartir(beats, formato)
    if hasattr(guion, "ajustar_rangos"):
        rangos = guion.ajustar_rangos(rangos, formato)
    frames = list(range(1, n_frames + 1))
    sc.frame_start, sc.frame_end = 1, n_frames
    render.configurar(formato, a.renderizador)
    if extras["exposicion"] is not None:
        sc.view_settings.exposure = extras["exposicion"]
    if resueltos:
        print(f"AJUSTES: {json.dumps(resueltos, ensure_ascii=False)}")
    for d in acta.decisiones:
        print(f"CONTRATO {d.get('decision','').upper()}: {d.get('beat') or d.get('sujeto')}"
              f" -> {d.get('a') or 'omitido'} ({d.get('regla') or d.get('motivo')})")

    medidas = medir(paq, rec, montado, guion, formato)
    if hasattr(guion, "ajustar_medidas"):
        guion.ajustar_medidas(medidas, paq, rec, montado, formato)
    ph = medidas["pose_heroe"]
    print(f"MEDIDO: D_gen={medidas['dist_general']:.2f} D_cerca={medidas['dist_primer_plano']:.2f} "
          f"pose az={medidas['azimut']:.0f} el={medidas['elevacion']:.0f} "
          f"(cobertura {ph['cobertura']} separacion {ph['separacion']}) "
          f"arco span={medidas['arco']['span']:.0f} min={medidas['arco']['minimo']}")
    print(f"POR_GRUPO: {ph['por_grupo']}")
    if medidas.get("orbita"):
        o = medidas["orbita"]
        print(f"ORBITA (bucle): elevacion={o['elevacion']:.0f} "
              f"minimo={o['minimo']} media={o['media']}")

    informe = control.revisar(medidas, formato, guion=guion)
    for av in informe.avisos:
        print(f"QC {av.gravedad.upper()} [{av.id}]: {av.detalle}")
    if not informe.ok and not a.forzar and vista:
        print("QC_ABORTADO: la vista previa no se rinde; el video tampoco "
              "saldria sin --forzar.")
        return 2
    if not informe.ok and not a.forzar:
        (destino / f"qc_{formato.nombre}{sufijo}.json").write_text(
            json.dumps({"pdb_id": paq.pdb_id, "formato": formato.nombre,
                        "avisos": informe.como_lista(),
                        "medidas": {k: (round(v, 4) if isinstance(v, float) else None)
                                    for k, v in medidas.items()
                                    if isinstance(v, float)}},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        print("QC_ABORTADO: no se construye la camara ni se renderiza. "
              "Usa --forzar si sabes lo que haces.")
        return 2

    # camara
    rig = camara.montar_rig(Vector(paq.objetivo), guion.LENTE_GENERAL)
    if not formato.profundidad_de_campo and "desenfoque" in resueltos:
        rig.camara.data.dof.use_dof = False
    if extras["piso_fantasma"] is not None:
        guion.PISO_FANTASMA = extras["piso_fantasma"]
    nodo_diso = camara.preparar_disolucion(rec.mat_cartoon,
                                           portal=experimental)
    if experimental:
        # Disposable portal variant: keep the reference DITHERED method.
        # BLENDED softened the entire receptor in Eevee, including the open
        # shot; the calibrated alpha range already supplies the portal.
        rec.mat_cartoon.surface_render_method = "DITHERED"
    rec.mat_cartoon.update_tag()
    bpy.context.view_layer.update()
    est = guion.estados(medidas, rangos, n_frames, formato,
                        experimental=experimental)
    if extras["factor_desenfoque"] > 0 and extras["factor_desenfoque"] != 1.0:
        # Mas fuerza de desenfoque = diafragma mas abierto (f mas bajo).
        for e in est:
            e["diafragma"] = e["diafragma"] / extras["factor_desenfoque"]
    camara.hornear_trayecto(rig, est, frames, rec.mat_cartoon, nodo_diso,
                            medidas["dist_primer_plano"])
    rec.mat_cartoon.update_tag()
    bpy.context.view_layer.update()

    # apariciones del receptor y del sujeto
    ap_h = guion.aparicion_de_hotspots(rangos, formato.fps)
    if rec.mat_hotspots and ap_h:
        H.fundir(rec.mat_hotspots, frames, H.curva(ap_h["fundido"], frames))
    ap_s = guion.aparicion_del_sujeto(rangos, formato.fps)
    if montado.objetos and ap_s:
        for m in montado.materiales:
            H.fundir(m, frames, H.curva(ap_s["fundido"], frames))
        for o in montado.objetos:
            H.visible_en(o, frames, ap_s["ventana"][0], n_frames)
    ap_c = (guion.aparicion_de_contactos(rangos, formato.fps)
            if hasattr(guion, "aparicion_de_contactos") else None)
    if montado.secundarios and ap_c:
        for m in montado.materiales_secundarios:
            if hasattr(m, "surface_render_method"):
                m.surface_render_method = "DITHERED"
            H.fundir(m, frames, H.curva(ap_c["fundido"], frames))
        for o in montado.secundarios:
            H.visible_en(o, frames, ap_c["ventana"][0], n_frames)
    if hasattr(guion, "animar_sujeto") and montado.extra:
        # P.ej. el caminante de la escena x: el guion pone los fotogramas,
        # las posiciones son las que dejo el muestreo, medidas no inventadas.
        guion.animar_sujeto(rangos, formato.fps, montado, frames)

    # rotulos
    proto = bpy.data.objects.get("Lab_Erlo")
    proto_guia = bpy.data.objects.get("Leader_Lab_Erlo")
    creados = []
    capa_titulo = None
    plan = guion.anotaciones(rangos, formato, formato.fps,
                             n_sujeto=len(montado.anclas))
    # Las ancladas viven en el mundo y su tamano en pantalla lo pone la
    # perspectiva: el aumento de movil es solo para el texto de pantalla.
    esc_ancladas = (formato.escala_etiquetas_3d
                    if formato.escala_etiquetas_3d is not None
                    else formato.escala_texto)
    if proto is not None:
        grupo_h = []
        for i, (cfg, h) in enumerate(zip(plan["hotspots"], rec.hotspots)):
            c = receptor.centro_de_residuo(rec.molecula, h.numero,
                                           receptor.indice_de_cadena(paq, h.cadena))
            if c is None:
                continue
            r = rotulos.crear_anclada(
                f"hot{i}", h.etiqueta_con_cadena(paq.sitio_multicadena),
                c, proto, proto_guia, esc_ancladas)
            r.ventana, r.fundido = cfg["ventana"], cfg["fundido"]
            grupo_h.append(r)
        grupo_s = []
        for cfg, (sid, texto, pos) in zip(plan["sujeto"], montado.anclas):
            r = rotulos.crear_anclada(sid, texto, pos, proto, proto_guia,
                                       esc_ancladas)
            r.ventana, r.fundido = cfg["ventana"], cfg["fundido"]
            grupo_s.append(r)
        # En vertical las ancladas se colocan con busqueda dinamica (texto
        # grande en cuadro angosto); en horizontal, la de siempre.
        colocar = (rotulos.colocar_dinamicas if formato.vertical
                   else rotulos.colocar_ancladas)
        for grupo, beat, sep in ((grupo_h, "pausa_hotspots", 0.17),
                                 (grupo_s, "llegada_por_fundido", 0.30),
                                 (grupo_s, "llegada_sujeto", 0.30)):
            if not grupo or beat not in rangos:
                continue
            a0, b0 = rangos[beat]
            sc.frame_set((a0 + b0) // 2)
            bpy.context.view_layer.update()
            colocar(rig.camara, grupo, sep)
        creados = grupo_h + grupo_s
        cfg_tit = (guion.titulo(rangos, formato, formato.fps)
                   if hasattr(guion, "titulo") else None)
        if cfg_tit:
            texto_titulo, escala_titulo = rotulos.titulo_pantalla(
                paq.pdb_id, paq.nombre, paq.resolucion,
                base=formato.escala_texto * 0.78)
            t = rotulos.crear_pantalla(
                "titulo", texto_titulo,
                rig.camara, proto, esquina="inferior_izquierda",
                escala_texto=escala_titulo,
                lente_referencia=guion.LENTE_GENERAL,
                distancia=medidas["dist_general"])
            t.ventana, t.fundido = cfg_tit["ventana"], cfg_tit["fundido"]
            creados.append(t)
            # El titulo va a la profundidad del receptor, asi que la geometria
            # por delante puede taparlo: se rinde aparte y se compone encima.
            capa_titulo = {"objeto": t.objeto.name, "objetos": [t.objeto.name],
                           "ventana": tuple(cfg_tit["ventana"])}
            # El titulo se ve SOLO por su pasada aislada (nitida, sin DoF); en
            # el pase principal se esconde para que su copia suave no asome por
            # los bordes del texto bueno y lo haga leer borroso.
            t.objeto.visible_camera = False
            print(f"TITULO: {t.texto}")
        if hasattr(guion, "rotulos_datos"):
            for cfg in guion.rotulos_datos(rangos, formato, formato.fps, montado):
                dato = rotulos.crear_pantalla(
                    cfg["id"], cfg["texto"], rig.camara, proto,
                    esquina=cfg.get("esquina", "superior_izquierda"),
                    escala_texto=cfg.get("escala", formato.escala_texto),
                    lente_referencia=guion.LENTE_PRIMER_PLANO,
                    distancia=medidas["dist_sitio"] if "dist_sitio" in medidas
                    else medidas["dist_primer_plano"])
                dato.ventana = tuple(cfg["ventana"])
                creados.append(dato)
                dato.objeto.visible_camera = False
                if capa_titulo is None:
                    capa_titulo = {"objetos": [], "ventana": dato.ventana}
                capa_titulo["objetos"].append(dato.objeto.name)
                capa_titulo["ventana"] = (
                    min(capa_titulo["ventana"][0], dato.ventana[0]),
                    max(capa_titulo["ventana"][1], dato.ventana[1]))
    rotulos.hornear(creados, frames)
    # Credito de marca en vez de la ficha tecnica: el pdb_id y el sha siguen en
    # el acta y el MANIFEST, y la esquina inferior ya identifica la estructura.
    sello = procedencia.sellar(paq, formato, nota=procedencia.CREDITO)
    if sello:
        print(f"SELLO: {sello}")

    if vista:
        return vista_previa(a.vista_previa, a.salida_vista, formato, rangos,
                            n_frames, capa_titulo)

    sc.frame_set(1)
    blend = destino / "blender" / f"{paq.pdb_id}_{formato.nombre}{sufijo}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    print(f"BLEND: {blend}")

    def limpio(v):
        if isinstance(v, Vector):
            return [round(x, 4) for x in v]
        if isinstance(v, (int, str, bool)) or v is None:
            return v
        if isinstance(v, float):
            return round(v, 4)
        if isinstance(v, (list, tuple)):
            return [limpio(x) for x in v]
        if isinstance(v, dict):
            return {k: limpio(x) for k, x in v.items()}
        return str(v)

    registro = {
        "pdb_id": paq.pdb_id, "guion": guion.NOMBRE, "formato": formato.resumen(),
        "sujeto": {"id": mod_sujeto.ID, "disponible": ok, "razon": razon},
        "fotogramas": n_frames, "duracion_s": round(n_frames / formato.fps, 2),
        "beats": {k: list(v) for k, v in rangos.items()},
        "medidas": limpio({k: v for k, v in medidas.items() if k != "arco"}),
        "arco": limpio(medidas["arco"]),
        "decisiones_del_contrato": acta.decisiones,
        "control_de_calidad": informe.como_lista(),
        "forzado": bool(a.forzar),
        "presentacion": {
            "titulo": rotulos.titulo_pantalla(
                paq.pdb_id, paq.nombre, paq.resolucion)[0],
            "experimental_look": bool(experimental),
        },
        "capa_titulo": capa_titulo,
        # Constitucion del fantasma en el acta: si el video sale con mas o menos
        # transparencia de la buscada, aqui esta el numero que la produjo.
        "portal_fantasma": ({
            "piso": getattr(guion, "PISO_FANTASMA", None),
            "radio": getattr(guion, "RADIO_FANTASMA", None),
            "cerca": getattr(guion, "FANTASMA_CERCA", None),
            "lejos": getattr(guion, "FANTASMA_LEJOS", None),
        } if experimental else None),
        # Mandos de la interfaz: posiciones 0-100 tal como llegaron y el valor
        # real en que se tradujeron. Sin ajustes, el video es el de produccion.
        "ajustes": ({"entrada": ajustes, "resueltos": resueltos}
                    if resueltos else None),
        "notas": rec.notas + montado.notas,
        "estructura_secundaria": rec.censo_estructura,
        "medido_por_el_sujeto": montado.medido,
        "sujetos_posibles": sujeto.inventario(paq),
        "procedencia_paquete": paq.procedencia,
        # Lo que EEVEE usa de verdad, no solo lo que pide el formato: sombras,
        # GI y rayos venian de la plantilla y no constaban en ningun sitio.
        "render_ajustes": render.ajustes(),
        "construido_s": round(time.time() - t0, 1),
    }

    def escribir(ruta: Path) -> None:
        ruta.write_text(json.dumps(registro, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    acta_final = destino / f"build_{formato.nombre}{sufijo}.json"
    if a.solo_construir:
        escribir(acta_final)
        print("CONSTRUIDO_OK", json.dumps(
            {k: registro[k] for k in ("fotogramas", "duracion_s", "beats", "notas")},
            ensure_ascii=False))
        return 0

    # Mientras se rinde, el acta es PARCIAL: si el proceso muere, lo que queda
    # se llama `.parcial.json` y no pasa por un acta de video entregado (asi
    # quedaron `build_*_1019.json` en 015 y 016, sin video y listos para
    # commitearse). Solo se escribe la final cuando el render termino.
    acta_parcial = destino / f"build_{formato.nombre}{sufijo}.parcial.json"
    escribir(acta_parcial)
    huella = huella_de_construccion(registro)
    info = render.secuencia(destino / f"render_{formato.nombre}{sufijo}", frames,
                            huella=huella)
    registro["render"] = info
    if capa_titulo:
        info_capa = render.pasada_titulo(
            destino / f"render_{formato.nombre}{sufijo}_titulo",
            capa_titulo.get("objetos", [capa_titulo.get("objeto")]), capa_titulo["ventana"])
        capa_titulo.update(info_capa)
        print(f"CAPA_TITULO: {info_capa['fotogramas']} fotogramas de titulo "
              f"con alfa; se componen por encima al codificar")
    escribir(acta_final)
    acta_parcial.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
