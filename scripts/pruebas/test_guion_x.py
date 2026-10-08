"""La escena `x` y el contrato de docking, sin lanzar Blender.

El sujeto `busqueda_montecarlo` se abstiene (o no) segun el paquete traiga
`docking.json` valido; el guion `x` declara sus beats de busqueda con
`requiere="sujeto"` asi que sin dato la matriz los omite con motivo, y el
reparto sigue cubriendo el presupuesto del formato.
"""
import importlib.util
import json

import pytest

from nucleo.ciencia import Paquete
from sujetos import busqueda_montecarlo as suj_mc
from variables import formato as fmt
from variables import guion as gui
from variables.guion import Acta
from guiones import x as guion_x

# estados() viaja por encuadre (mathutils): solo corre donde hay Blender.
_SIN_BLENDER = importlib.util.find_spec("mathutils") is None


def _paquete(tmp_path, dock=None):
    datos = {
        "schema": "moldesign.scene/1",
        "receptor": {"pdb_id": "1TTT", "nombre": "Prueba",
                     "cadena_principal": "A", "sitio_multicadena": False},
        "encuadre": {"objetivo": [1.0, 2.0, 3.0], "caja": [20, 20, 20]},
        "resaltar": {"hotspots": []},
        "geometria": {},
        "declarado": {},
        "no_dibujar": [], "declarar_si_se_dibuja": [],
        "procedencia": {},
    }
    (tmp_path / "scene.json").write_text(json.dumps(datos), encoding="utf-8")
    if dock is not None:
        (tmp_path / "docking.json").write_text(json.dumps(dock), encoding="utf-8")
    return Paquete.cargar(tmp_path)


def _dock(tmp_path, con_traza=True, con_poses=True):
    pose = None
    if con_poses:
        (tmp_path / "docking" / "poses").mkdir(parents=True, exist_ok=True)
        pose = tmp_path / "docking" / "poses" / "pose_001.pdb"
        pose.write_text("HETATM    1  C1  LIG A   1       1.0   2.0   3.0\nEND\n",
                        encoding="utf-8")
    d = {
        "schema": "moldesign.dock/1",
        "motor": {"nombre": "vina", "version": "1.2.7"},
        "caja": {"centro": [1.0, 2.0, 3.0], "tamano": [20.0, 20.0, 20.0]},
        "poses": ([{"rank": 1, "afinidad_kcal_mol": -9.1,
                    "rmsd_cristal_a": 1.2, "archivo": "docking/poses/pose_001.pdb"}]
                  if con_poses else []),
    }
    if con_traza:
        snap = tmp_path / "docking" / "snapshot_001.pdb"
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text("HETATM    1  C1  LIG A   1       1.0   2.0   3.0\nEND\n",
                        encoding="utf-8")
        d["traza_interna"] = {
            "tipo": "vina_monte_carlo_bfgs_interno", "replicas": 2,
            "pasos_totales": 24, "pasos_replica": 12, "aceptados_totales": 8,
            "instantaneas": [{"task": 0, "step": 6,
                               "archivo": "docking/snapshot_001.pdb"}]}
    return d


# ── el contrato ─────────────────────────────────────────────────────────────
def test_sin_docking_json_no_hay_dato(tmp_path):
    assert _paquete(tmp_path).dock is None


def test_schema_desconocido_no_se_acepta(tmp_path):
    paq = _paquete(tmp_path, dock={"schema": "otra-cosa/0", "caja": {}, "poses": [1]})
    assert paq.dock is None


def test_dock_valido_se_exponen_caja_y_poses(tmp_path):
    paq = _paquete(tmp_path, dock=_dock(tmp_path))
    d = paq.dock
    assert d["caja"]["tamano"] == [20.0, 20.0, 20.0]
    assert paq.ruta_dock(paq.dock["poses"][0]["archivo"]).name == "pose_001.pdb"


def test_ruta_dock_no_sale_del_paquete(tmp_path):
    paq = _paquete(tmp_path, dock=_dock(tmp_path))
    assert paq.ruta_dock("../secreto.pdb") is None
    assert paq.ruta_dock("docking/poses/no_existe.pdb") is None


# ── el sujeto se abstiene diciendo por que ──────────────────────────────────
def test_sujeto_disponible_solo_con_caja_poses_y_traza(tmp_path):
    assert not suj_mc.disponible(_paquete(tmp_path))[0]
    assert not suj_mc.disponible(_paquete(tmp_path, dock=_dock(tmp_path, con_poses=False, con_traza=True)))[0]
    assert not suj_mc.disponible(_paquete(tmp_path, dock=_dock(tmp_path, con_traza=False)))[0]
    ok, razon = suj_mc.disponible(_paquete(tmp_path, dock=_dock(tmp_path)))
    assert ok, razon


def test_sujeto_disponible_solo_si_las_poses_existen_en_disco(tmp_path):
    d = _dock(tmp_path)
    d["poses"][0]["archivo"] = "docking/poses/borrada.pdb"
    paq = _paquete(tmp_path, dock=d)
    ok, razon = suj_mc.disponible(paq)
    assert not ok and "poses" in razon


def test_sujeto_rechaza_instantaneas_ausentes(tmp_path):
    d = _dock(tmp_path)
    d["traza_interna"]["instantaneas"][0]["archivo"] = "docking/borrada.pdb"
    ok, razon = suj_mc.disponible(_paquete(tmp_path, dock=d))
    assert not ok and "instantaneas" in razon


def test_ventanas_dan_turno_a_todas_las_poses_y_muestras():
    rangos = {"busqueda": (61, 150), "convergencia": (151, 270)}
    poses = guion_x.ventanas_poses(rangos, 9)
    muestras = guion_x.ventanas_instantaneas(rangos, 12)
    assert len(poses) == 9 and len(muestras) == 12
    assert poses[0][0] == 151 and poses[-1][1] == 270
    assert muestras[0][0] == 61 and muestras[-1][1] == 150
    assert all(b + 1 == c for (_, b), (c, _) in zip(poses, poses[1:]))


# ── el guion: registro, contrato con la matriz y reparto ────────────────────
def test_el_guion_x_se_describe_sin_blender_y_fija_su_sujeto():
    # el catalogo AST es el que lee la interfaz, que no tiene mathutils
    assert "x" in gui.catalogo()
    assert gui.catalogo()["x"]["SUJETO"] == "busqueda_montecarlo"


def test_sin_sujeto_los_beats_de_busqueda_se_omiten_con_motivo():
    acta = Acta()
    vivos = gui.resolver(guion_x.BEATS, None, {"sujeto": False},
                         fmt.cargar("biblioteca"), acta)
    ids = [b.id for b in vivos]
    assert ids == ["general", "reposo"]
    assert any(d.get("beat") == "busqueda" and d.get("motivo") == "dato ausente"
               for d in acta.decisiones)


def test_con_sujeto_el_reparto_cubre_el_presupuesto_en_todos_los_formatos():
    for n, f in fmt.disponibles().items():
        acta = Acta()
        beats = gui.resolver(guion_x.BEATS, None, {"sujeto": True}, f, acta)
        rangos, total = gui.repartir(beats, f)
        assert total == f.fotogramas, n
        ajustados = guion_x.ajustar_rangos(rangos, f)
        if not f.bucle:
            assert ajustados["sitio"] == (1, f.fps)
            assert ajustados["salida"] == (total - 3 * f.fps + 1, total)
            assert list(ajustados) == ["sitio", "caja", "busqueda", "convergencia", "salida"]


@pytest.mark.skipif(_SIN_BLENDER, reason="estados() corre dentro de Blender")
def test_estados_da_un_fotograma_por_cuadro():
    from mathutils import Vector
    f = fmt.cargar("social_vertical")
    beats = gui.resolver(guion_x.BEATS, None, {"sujeto": True}, f, Acta())
    rangos, total = gui.repartir(beats, f)
    medidas = {
        "centro_general": Vector((0, 0, 0)), "pivote": Vector((0.1, 0.2, 0.3)),
        "dist_general": 40.0,
        "dist_primer_plano": 12.0, "azimut": 30.0, "elevacion": -20.0,
        "elevacion_general": 12.0, "gradiente_general": 14.0,
        "gradiente_cerca": 5.0, "disolucion_cerca": (0.8, 2.1),
        "arco": {"el_fin": -20.0},
    }
    est = guion_x.estados(medidas, rangos, total, f)
    assert len(est) == total
    assert all({"pos", "objetivo", "lente", "diafragma", "gradiente",
                "diso0", "diso1", "dist", "giro"} <= set(e) for e in est)


def test_cpu_three_seconds_has_a_frame_for_each_native_sample():
    from dataclasses import replace
    formato = replace(fmt.cargar("biblioteca"), segundos=3.0, bucle=False)
    rangos, n = gui.repartir(guion_x.BEATS, formato)
    rangos = guion_x.ajustar_rangos(rangos, formato)
    windows = guion_x.ventanas_instantaneas(rangos, 12)
    assert n == 90
    assert all(a <= b for a,b in windows)
    assert rangos["salida"][1] == n


# ── los rótulos y el plano de cámara ────────────────────────────────────────
def _montado_con_rotulos():
    from types import SimpleNamespace
    poses = [{"nombre": f"P{i}", "rank": i, "afinidad": -6.0 - i / 10,
              "rmsd_vina_inferior_a": 1.0 * i,
              "contactos": {"polares": 2, "hidrofobicos": 3}} for i in range(1, 4)]
    muestras = [{"nombre": f"S{i}", "step": 1602 * i, "task": 0,
                 "fantasma": f"A{i}" if i > 1 else None,
                 "metrica_interna": {"candidata": 1.0, "retenida": -5.46,
                                     "mejor_hasta_paso": -7.05,
                                     "aceptada_en_paso": bool(i % 2),
                                     "aceptadas_acumuladas": 6213}}
                for i in range(1, 4)]
    traza = {"replicas": 8, "pasos_replica": 16065, "pasos_totales": 128520,
             "torsiones_activas": 3}
    return SimpleNamespace(extra={"poses": poses, "instantaneas": muestras,
                                  "traza_interna": traza, "contactos_visibles": True})


def _rangos_x(nombre="social_vertical"):
    formato = fmt.cargar(nombre)
    beats = gui.resolver(guion_x.BEATS, None, {"sujeto": True}, formato, Acta())
    rangos, _ = gui.repartir(beats, formato)
    return formato, guion_x.ajustar_rangos(rangos, formato)


def test_ningun_rotulo_de_x_pasa_de_36_caracteres_por_linea():
    # En 9:16 caben ~36; «ESTADO RETENIDO … | PROPUESTA ACEPTADA» (43) se salía del cuadro.
    formato, rangos = _rangos_x()
    rotulos = guion_x.rotulos_datos(rangos, formato, formato.fps, _montado_con_rotulos())
    assert rotulos
    for r in rotulos:
        for linea in r["texto"].split("\n"):
            assert len(linea) <= 36, (r["id"], linea)


def test_la_caja_aparece_en_su_beat_y_no_en_la_retirada():
    _, rangos = _rangos_x()
    ap = guion_x.aparicion_del_sujeto(rangos, 30)
    assert ap["ventana"][0] == rangos["caja"][0]
    # sin beat `caja` se conserva la entrada de la retirada
    assert guion_x.aparicion_del_sujeto({"salida": (271, 360)}, 30)["ventana"][0] == 271


def _planes(n_estados=12, n_poses=9):
    # `objetivo` es un número: la aritmética del recorrido es la misma que con Vector.
    plano = lambda d: {"objetivo": d, "dist": d, "radio": 1.0}      # noqa: E731
    return {"plan_camara": {"sitio": plano(1.0), "caja": plano(6.0),
                            "estados_vina": [plano(4.0 - i * 0.2) for i in range(n_estados)],
                            "poses": [plano(1.5 + (i % 3) * 0.5) for i in range(n_poses)]}}


def test_el_recorrido_abre_en_el_sitio_y_nunca_pasa_de_la_caja():
    formato, rangos = _rangos_x()
    r = guion_x._recorrido(_planes(), rangos, formato.fps)
    assert sorted(r) == list(range(1, rangos["convergencia"][1] + 1))
    assert r[1][1] == pytest.approx(1.0, abs=0.05)
    distancias = [v[1] for v in r.values()]
    assert max(distancias) <= 6.0 + 1e-9 and min(distancias) >= 1.0 - 1e-9


def test_el_recorrido_no_sacude_la_camara():
    formato, rangos = _rangos_x()
    r = guion_x._recorrido(_planes(), rangos, formato.fps)
    saltos = [abs(r[f + 1][1] - r[f][1]) for f in range(1, len(r))]
    assert max(saltos) < 0.3


def test_sin_planes_de_seguimiento_manda_el_plano_unico():
    formato, rangos = _rangos_x()
    assert guion_x._recorrido({}, rangos, formato.fps) is None
    assert guion_x._recorrido({"plan_camara": {"sitio": {}, "caja": {}}}, rangos, formato.fps) is None


def test_suavizar_conserva_lo_constante_y_redondea_un_escalon():
    assert guion_x._suavizar([2.0] * 20, 3.0) == pytest.approx([2.0] * 20)
    escalon = guion_x._suavizar([0.0] * 20 + [1.0] * 20, 3.0)
    assert all(a <= b + 1e-12 for a, b in zip(escalon, escalon[1:]))
    assert 0.0 < escalon[20] < 1.0


# ── interacciones: rótulos 3D por pose ──────────────────────────────────────
def _contacto(tipo, resname="TYR", resid=507, distancia=3.1, cadena="A"):
    from types import SimpleNamespace
    return SimpleNamespace(tipo=tipo, resname=resname, resid=resid, cadena=cadena,
                           distancia_a=distancia, etiqueta=f"{distancia:.2f} Å")


def test_el_rotulo_de_una_interaccion_dice_residuo_clase_y_distancia_sin_nombres_de_color():
    from nucleo import interacciones
    polar = interacciones.texto(_contacto("polar", "ASP", 120, 2.87))
    apolar = interacciones.texto(_contacto("hidrofobico", "LEU", 45, 3.912))
    assert polar == "ASP120\nPOLAR  2.87 Å"
    assert apolar == "LEU45\nAPOLAR  3.91 Å"
    texto_entero = (polar + apolar + interacciones.NOTA).lower()
    # «oro» se lee como el elemento: ningún texto nombra los colores
    assert " oro" not in texto_entero and "cian" not in texto_entero and "dorad" not in texto_entero
    assert interacciones.color(_contacto("polar")) != interacciones.color(_contacto("hidrofobico"))


def test_el_rotulo_lleva_la_cadena_solo_si_el_sitio_es_multicadena():
    from nucleo import interacciones
    c = _contacto("polar", "SER", 12, 3.0, cadena="B")
    assert interacciones.texto(c) == "SER12\nPOLAR  3.00 Å"
    assert interacciones.texto(c, con_cadena=True) == "SER12:B\nPOLAR  3.00 Å"
    assert interacciones.texto(_contacto("polar", "?", 7)).startswith("RES7")


def test_el_registro_del_acta_usa_polar_y_apolar():
    from nucleo import interacciones
    assert interacciones.registro(_contacto("hidrofobico"))["tipo"] == "apolar"
    assert interacciones.registro(_contacto("polar"))["tipo"] == "polar"


def _montado_con_interacciones():
    from types import SimpleNamespace
    poses = [{"nombre": f"P{i}", "rank": i} for i in range(1, 4)]
    anclas = [("caja", "caja", None), ("pose1", "#1", None)]
    por_pose = {}
    for i in (1, 2, 3):
        ids = [f"dist_p{i}_{j}" for j in range(2)]
        por_pose[i] = ids
        anclas += [(ident, "x", None) for ident in ids]
    anclas += [("dist_s_0", "x", None), ("dist_s_1", "x", None)]
    return SimpleNamespace(anclas=anclas, extra={
        "poses": poses, "rotulos_por_pose": por_pose,
        "rotulos_sitio": ["dist_s_0", "dist_s_1"],
        "puntos_poses": [["p1"], ["p2"], ["p3"]]})


def test_cada_interaccion_se_rotula_en_la_ventana_de_su_pose_y_las_de_la_mejor_tambien_en_el_sitio():
    formato, rangos = _rangos_x()
    montado = _montado_con_interacciones()
    plan = guion_x.anotaciones(rangos, formato, formato.fps, n_sujeto=len(montado.anclas),
                               montado=montado)
    assert len(plan["sujeto"]) == len(montado.anclas)          # alineado con las anclas
    por_id = {a[0]: cfg for a, cfg in zip(montado.anclas, plan["sujeto"])}
    assert por_id["caja"] is None and por_id["pose1"] is None   # no son interacciones
    ventanas = guion_x.ventanas_poses(rangos, 3)
    for rank in (1, 2, 3):
        cfg = por_id[f"dist_p{rank}_0"]
        a, b = ventanas[rank - 1]
        # UN fotograma, a mitad de la ventana de su pose: el que el montaje congela.
        assert cfg["ventana"] == (cfg["colocar_en"],) * 2 and a <= cfg["colocar_en"] <= b
        assert por_id[f"dist_p{rank}_1"]["colocar_en"] == cfg["colocar_en"]
        assert cfg["reservar"] == [f"p{rank}"]                   # la nube de ESA pose
    sitio = por_id["dist_s_0"]
    assert rangos["sitio"][0] < sitio["colocar_en"] <= rangos["sitio"][1]
    assert sitio["reservar"] == ["p1"]
    assert all(c["fundido"] == [] for c in plan["sujeto"] if c)  # se ven enteros, sin fundido


def test_cada_grupo_de_rotulos_de_x_congela_la_imagen_un_segundo():
    formato, rangos = _rangos_x()
    plan = guion_x.anotaciones(rangos, formato, formato.fps, montado=_montado_con_interacciones())
    instantes = sorted({c["colocar_en"] for c in plan["sujeto"] if c})
    assert [p["en"] for p in plan["pausas"]] == instantes and len(instantes) == 4  # sitio + 3 poses
    assert all(p["segundos"] == guion_x.PAUSA_LECTURA_S == 1.0 and p["tipo"] == "lectura"
               and not p.get("omitir_hasta") for p in plan["pausas"])


def test_sin_montado_o_sin_etiquetas_3d_no_hay_rotulos_de_interaccion():
    from dataclasses import replace
    formato, rangos = _rangos_x()
    assert guion_x.anotaciones(rangos, formato, formato.fps)["sujeto"] == []
    sin = replace(formato, etiquetas_3d=False)
    assert guion_x.anotaciones(rangos, sin, sin.fps, montado=_montado_con_interacciones())["sujeto"] == []


def test_una_pose_demasiado_corta_no_se_rotula():
    from dataclasses import replace
    formato = replace(fmt.cargar("biblioteca"), segundos=3.0, bucle=False)
    rangos, _ = gui.repartir(guion_x.BEATS, formato)
    rangos = guion_x.ajustar_rangos(rangos, formato)
    plan = guion_x.anotaciones(rangos, formato, formato.fps, montado=_montado_con_interacciones())
    ventanas = guion_x.ventanas_poses(rangos, 3)
    for cfg in (c for c in plan["sujeto"] if c):
        a, b = next(v for v in ventanas + [rangos["sitio"]] if v[0] <= cfg["colocar_en"] <= v[1])
        assert b - a + 1 >= guion_x.MINIMO_ROTULO
