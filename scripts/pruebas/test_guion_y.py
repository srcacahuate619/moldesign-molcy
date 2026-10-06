"""La escena `y` (ensamble conformacional) y su contrato, sin lanzar Blender.

El sujeto `ensamble_conformacional` se abstiene (o no) según el paquete traiga un
`ensamble.json` verificable; el guion `y` declara sus beats con `requiere="sujeto"`,
así que sin dato la matriz los omite con motivo. Todo lo que el guion rotula sale del
contrato: nada se inventa, y lo que no cabe en el vídeo queda dicho en el acta.
"""
import hashlib
import json
import pathlib
import re

import pytest

from nucleo.ciencia import Paquete
from sujetos import ensamble_conformacional as suj
from variables import formato as fmt
from variables import guion as gui
from variables.guion import Acta
from variables.sujeto import Montado
from guiones import x as guion_x
from guiones import y as guion_y

PDB = "HEBRA 1TTT\n"


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _paquete(tmp_path, ensamble=None):
    datos = {
        "schema": "moldesign.scene/1",
        "receptor": {"pdb_id": "1TTT", "nombre": "Prueba",
                     "cadena_principal": "A", "sitio_multicadena": False},
        "encuadre": {"objetivo": [1.0, 2.0, 3.0], "caja": [20, 20, 20]},
        "resaltar": {"hotspots": []}, "geometria": {}, "declarado": {},
        "no_dibujar": [], "declarar_si_se_dibuja": [], "procedencia": {},
    }
    (tmp_path / "scene.json").write_text(json.dumps(datos), encoding="utf-8")
    if ensamble is not None:
        (tmp_path / "ensamble.json").write_text(json.dumps(ensamble), encoding="utf-8")
    return Paquete.cargar(tmp_path)


def _archivo(tmp_path, nombre, texto=PDB):
    ruta = tmp_path / "docking" / "ensamble" / nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # Bytes, no texto: en Windows `write_text` traduce los saltos de línea y el
    # SHA-256 del archivo dejaría de ser el de la cadena.
    ruta.write_bytes(texto.encode("utf-8"))
    return {"archivo": f"docking/ensamble/{nombre}", "sha256": _sha(texto)}


def _controles(aprobadas=15, pruebas=15, fallos=()):
    return {"estado": "passed", "aprobadas": aprobadas, "pruebas": pruebas,
            "fallos": list(fallos)}


def _ensamble(tmp_path, n_conf=3, n_poses=4, controles=True):
    conformeros = [{"indice": 10 + i, "semilla": 100 + i, "energia_mmff": 12.5 + i,
                    "torsiones": [{"atomos": ["C1", "C2", "C3", "O4"], "angulo_grados": 120.0}],
                    "mejor_afinidad_kcal_mol": -8.0 + i * 0.5, "poses_entregadas": 1,
                    **_archivo(tmp_path, f"conf_{i}.pdb", PDB + f"{i}\n")}
                   for i in range(n_conf)]
    poses = [{"rank": r, "conformero": 10 + (r - 1) % n_conf, "rank_local": 1,
              "afinidad_kcal_mol": -8.0 + (r - 1) * 0.1,
              "controles": _controles() if controles else None,
              **_archivo(tmp_path, f"pose_{r}.pdb", PDB + f"p{r}\n")}
             for r in range(1, n_poses + 1)]
    return {
        "schema": "moldesign.ensamble/1",
        "caja": {"centro": [1.0, 2.0, 3.0], "tamano": [20.0, 20.0, 20.0]},
        "motor": {"nombre": "AutoDock Vina", "version": "1.2.7"},
        "resumen": {"conformaciones_pedidas": 30, "conformaciones_acopladas": 30,
                    "poses_candidatas": 270, "poses_entregadas": n_poses},
        "conformeros": conformeros, "poses": poses,
        "validacion": {"motor": "posebusters:0.6.5:dock", "estado": "passed"},
    }


# ── el contrato ─────────────────────────────────────────────────────────────
def test_sin_ensamble_json_no_hay_dato(tmp_path):
    assert _paquete(tmp_path).ensamble is None


@pytest.mark.parametrize("cambio", [
    {"schema": "otra-cosa/0"},
    {"caja": {}},
    {"conformeros": []},
    {"poses": []},
])
def test_un_contrato_incompleto_no_se_acepta(tmp_path, cambio):
    assert _paquete(tmp_path, {**_ensamble(tmp_path), **cambio}).ensamble is None


def test_un_contrato_valido_se_expone(tmp_path):
    assert _paquete(tmp_path, _ensamble(tmp_path)).ensamble["resumen"]["poses_candidatas"] == 270


def test_ensamble_json_ilegible_es_ausencia_no_excepcion(tmp_path):
    _paquete(tmp_path)
    (tmp_path / "ensamble.json").write_text("{no es json", encoding="utf-8")
    assert Paquete.cargar(tmp_path).ensamble is None


def test_ruta_ensamble_no_sale_del_paquete(tmp_path):
    fuera = tmp_path.parent / "secreto.txt"
    fuera.write_text("x", encoding="utf-8")
    paq = _paquete(tmp_path, _ensamble(tmp_path))
    assert paq.ruta_ensamble("../secreto.txt") is None
    assert paq.ruta_ensamble("docking/ensamble/pose_1.pdb") is not None
    assert paq.ruta_ensamble("") is None


# ── el sujeto se abstiene diciendo qué falta ────────────────────────────────
def test_sujeto_disponible_con_un_paquete_verificado(tmp_path):
    ok, razon = suj.disponible(_paquete(tmp_path, _ensamble(tmp_path)))
    assert ok, razon
    assert "270" in razon and "4 poses" in razon


def test_sujeto_se_abstiene_sin_contrato(tmp_path):
    ok, razon = suj.disponible(_paquete(tmp_path))
    assert not ok and "ensamble.json" in razon


def test_sujeto_se_abstiene_si_un_archivo_cambio(tmp_path):
    ens = _ensamble(tmp_path)
    paq = _paquete(tmp_path, ens)
    (tmp_path / ens["poses"][0]["archivo"]).write_text("OTRA COSA\n", encoding="utf-8")
    ok, razon = suj.disponible(paq)
    assert not ok and "SHA-256" in razon and "pose 1" in razon


def test_sujeto_se_abstiene_si_falta_un_archivo(tmp_path):
    ens = _ensamble(tmp_path)
    paq = _paquete(tmp_path, ens)
    (tmp_path / ens["conformeros"][1]["archivo"]).unlink()
    ok, razon = suj.disponible(paq)
    assert not ok and "conformacion 11" in razon


def test_sujeto_se_abstiene_si_una_pose_cita_una_conformacion_que_no_trae(tmp_path):
    ens = _ensamble(tmp_path)
    ens["poses"][0]["conformero"] = 99
    ok, razon = suj.disponible(_paquete(tmp_path, ens))
    assert not ok and "99" in razon


def test_el_registro_ofrece_el_sujeto_real_y_ya_no_el_hueco():
    # `variables.sujeto.disponibles()` importa cada sujeto y algunos importan
    # Molecular Nodes, que sólo existe dentro de Blender: se lee el ID del fuente.
    import sujetos
    ids = set()
    for ruta in pathlib.Path(sujetos.__path__[0]).glob("[!_]*.py"):
        encontrado = re.search(r'^ID = "([^"]+)"', ruta.read_text(encoding="utf-8"), re.M)
        if encontrado:
            ids.add(encontrado.group(1))
    assert "ensamble_conformacional" in ids
    assert "poses_ensamble" not in ids


def test_el_guion_y_esta_registrado_y_fija_su_sujeto():
    assert guion_y.SUJETO == suj.ID
    assert gui.catalogo()["y"]["SUJETO"] == "ensamble_conformacional"


# ── el guion: beats y reparto ───────────────────────────────────────────────
def _vivos(paq_ok=True, formato="biblioteca"):
    f = fmt.cargar(formato)
    acta = Acta()
    beats = gui.resolver(guion_y.BEATS, None, {"sujeto": paq_ok}, f, acta)
    return f, acta, beats


def test_sin_sujeto_se_omiten_todos_los_beats_con_motivo():
    _f, acta, beats = _vivos(paq_ok=False)
    assert beats == []
    assert {d["beat"] for d in acta.decisiones} == {b.id for b in guion_y.BEATS}
    assert all(d["decision"] == "omitido" for d in acta.decisiones)


@pytest.mark.parametrize("nombre", ["biblioteca", "social_vertical", "previsualizacion"])
def test_el_reparto_cubre_todo_el_presupuesto_sin_huecos(nombre):
    from dataclasses import replace
    f = replace(fmt.cargar(nombre), papeles=None, bucle=False)
    beats = gui.resolver(guion_y.BEATS, None, {"sujeto": True}, f, Acta())
    rangos, n = gui.repartir(beats, f)
    rangos = guion_y.ajustar_rangos(rangos, f)
    orden = [rangos[b.id] for b in beats if b.id in rangos]
    assert orden[0][0] == 1 and orden[-1][1] == n
    for (a0, b0), (a1, b1) in zip(orden, orden[1:]):
        assert a1 == b0 + 1, f"hueco o solape entre {b0} y {a1}"
    assert all(a <= b for a, b in orden)


def test_ventanas_cubren_el_rango_y_no_se_solapan():
    v = guion_y.ventanas((11, 100), 4)
    assert v[0][0] == 11 and v[-1][1] == 100
    assert all(b0 + 1 == a1 for (_, b0), (a1, _) in zip(v, v[1:]))


def test_ventanas_enseñan_menos_elementos_si_no_caben_con_su_minimo():
    # 30 fotogramas, 18 de mínimo por elemento: sólo cabe uno, y es el primero.
    assert guion_y.ventanas((1, 30), 5, minimo=18) == [(1, 30)]
    assert guion_y.ventanas((1, 90), 5, minimo=18) == [
        (1, 18), (19, 36), (37, 54), (55, 72), (73, 90)]
    assert guion_y.ventanas((1, 10), 0) == []
    assert guion_y.ventanas(None, 3) == []


# ── los rótulos: lo que dicen y lo que se niegan a decir ────────────────────
class _Montado(Montado):
    pass


def _montado(n_conf=3, n_poses=4, controles=True, **resumen):
    m = Montado()
    m.extra["conformeros"] = [
        {"nombre": f"C{i}", "indice": 10 + i, "semilla": 100 + i, "energia_mmff": 12.5 + i,
         "torsiones": [{"atomos": ["C1", "C2", "C3", "O4"], "angulo_grados": -120.0}]}
        for i in range(n_conf)]
    m.extra["poses"] = [
        {"nombre": f"P{r}", "rank": r, "conformero": 10 + (r - 1) % n_conf, "rank_local": 1,
         "afinidad": -8.0 + (r - 1) * 0.1,
         "controles": _controles(fallos=["internal_energy"], aprobadas=14) if controles and r == 2
         else (_controles() if controles else None),
         "contactos": {"polares": 2, "hidrofobicos": 1}}
        for r in range(1, n_poses + 1)]
    vistas = {}
    for p in m.extra["poses"]:
        vistas.setdefault(p["conformero"], p)
    m.extra["corridas"] = [{"conformero": c["indice"], "rank": vistas[c["indice"]]["rank"],
                            "nombre": vistas[c["indice"]]["nombre"], "rank_local": 1,
                            "afinidad": vistas[c["indice"]]["afinidad"]}
                           for c in m.extra["conformeros"] if c["indice"] in vistas]
    m.extra["resumen"] = {"conformaciones_acopladas": 30, "poses_candidatas": 270,
                          "poses_entregadas": n_poses, **resumen}
    m.extra["validacion"] = {"motor": "posebusters:0.6.5:dock"}
    m.extra["rotulos_por_pose"] = {p["rank"]: [f"dist_p{p['rank']}_0"] for p in m.extra["poses"]}
    m.extra["puntos_poses"] = [[] for _ in m.extra["poses"]]
    m.anclas = [(f"dist_p{p['rank']}_0", "TXT", None) for p in m.extra["poses"]]
    return m


def _rangos(formato="biblioteca"):
    from dataclasses import replace
    f = replace(fmt.cargar(formato), papeles=None, bucle=False)
    beats = gui.resolver(guion_y.BEATS, None, {"sujeto": True}, f, Acta())
    rangos, _n = gui.repartir(beats, f)
    return f, guion_y.ajustar_rangos(rangos, f)


def _textos(m, formato="biblioteca"):
    f, rangos = _rangos(formato)
    return {r["id"]: r for r in guion_y.rotulos_datos(rangos, f, f.fps, m)}, rangos


def test_los_rotulos_dicen_las_cuentas_del_contrato():
    t, _ = _textos(_montado())
    assert "30 CONFORMACIONES" in t["y_intro"]["texto"]
    assert "270 POSES CANDIDATAS" in t["y_intro"]["texto"]
    assert "4 ENTREGADAS" in t["y_intro"]["texto"]
    assert "SEMILLA 100" in t["y_conf_10"]["texto"] and "MMFF 12.50 KCAL/MOL" in t["y_conf_10"]["texto"]
    assert "-120°" in t["y_diedros_10"]["texto"]
    assert "CONFORMACION 10" in t["y_corrida_10"]["texto"]
    assert "POSE 1/4" in t["y_pose_1"]["texto"] and "-8.00 KCAL/MOL" in t["y_pose_1"]["texto"]
    assert "CONTROLES POSEBUSTERS 15/15" in t["y_pose_1"]["texto"]


def test_un_control_que_falla_se_nombra():
    t, _ = _textos(_montado())
    assert "CONTROLES POSEBUSTERS 14/15" in t["y_pose_2"]["texto"]
    assert "FALLAN: INTERNAL_ENERGY" in t["y_pose_2"]["texto"]


def test_sin_controles_se_dice_no_evaluados_nunca_aprobados():
    t, _ = _textos(_montado(controles=False))
    texto = t["y_pose_1"]["texto"]
    assert "NO EVALUADOS" in texto
    assert not re.search(r"\d+/\d+ ?$", texto.splitlines()[2])


def test_los_rotulos_son_ascii_salvo_el_grado_y_no_nombran_colores():
    t, _ = _textos(_montado())
    prohibidas = ("ORO", "CIAN", "VIOLETA", "AMBAR", "TURQUESA", "NARANJA", "AZUL", "ROJO")
    for rotulo in t.values():
        extraños = set(rotulo["texto"]) - {chr(c) for c in range(128)} - {"°"}
        assert not extraños, (rotulo["id"], extraños)
        palabras = set(re.findall(r"[A-Z]+", rotulo["texto"]))
        assert not palabras & set(prohibidas), (rotulo["id"], palabras & set(prohibidas))


def test_el_final_cita_el_motor_de_controles_y_dice_que_es_posterior():
    t, _ = _textos(_montado())
    assert "POSEBUSTERS" in t["y_motor_controles"]["texto"]
    assert "DESPUES DEL ACOPLAMIENTO" in t["y_motor_controles"]["texto"]


def test_en_un_formato_corto_dice_cuantos_elementos_se_enseñan():
    m = _montado(n_conf=9, n_poses=9)
    f, rangos = _rangos("social_vertical")
    vistas = guion_y.mostradas(rangos, m)
    assert vistas["disponibles"] == {"conformeros": 9, "corridas": 9, "poses": 9}
    assert 1 <= vistas["poses"] < 9
    assert 1 <= vistas["conformeros"] < 9


def test_en_biblioteca_caben_todos():
    m = _montado(n_conf=9, n_poses=9)
    f, rangos = _rangos("biblioteca")
    vistas = guion_y.mostradas(rangos, m)
    assert (vistas["poses"], vistas["conformeros"], vistas["corridas"]) == (9, 9, 9)


def test_lo_que_se_rotula_es_exactamente_lo_que_se_cuenta_como_mostrado():
    m = _montado(n_conf=9, n_poses=9)
    f, rangos = _rangos("social_vertical")
    ids = {r["id"] for r in guion_y.rotulos_datos(rangos, f, f.fps, m)}
    vistas = guion_y.mostradas(rangos, m)
    assert len([i for i in ids if i.startswith("y_pose_")]) == vistas["poses"]
    assert len([i for i in ids if i.startswith("y_conf_")]) == vistas["conformeros"]
    assert len([i for i in ids if i.startswith("y_corrida_")]) == vistas["corridas"]


def test_sin_rotulos_de_pantalla_no_se_rotula_nada():
    m = _montado()
    f, rangos = _rangos("biblioteca")
    from dataclasses import replace
    assert guion_y.rotulos_datos(rangos, replace(f, rotulos_pantalla=False), f.fps, m) == []


def test_cada_interaccion_se_rotula_en_la_ventana_de_su_pose():
    m = _montado()
    f, rangos = _rangos("biblioteca")
    plan = guion_y.anotaciones(rangos, f, f.fps, n_sujeto=len(m.anclas), montado=m)
    assert len(plan["sujeto"]) == len(m.anclas)
    ventanas = guion_y.ventanas(rangos["validacion"], 4, guion_y.MINIMO_POSE)
    for cfg, (a, b) in zip(plan["sujeto"], ventanas):
        assert cfg["ventana"] == (a, b)
        assert a <= cfg["colocar_en"] <= b


def test_anotaciones_sin_sujeto_o_sin_etiquetas_es_vacio():
    f, rangos = _rangos("biblioteca")
    assert guion_y.anotaciones(rangos, f, f.fps)["sujeto"] == []
    from dataclasses import replace
    sin = replace(f, etiquetas_3d=False)
    assert guion_y.anotaciones(rangos, sin, f.fps, montado=_montado())["sujeto"] == []


def test_la_escena_no_tiene_titulo_de_pantalla_ni_contactos_aparte():
    assert guion_y.titulo({}, None, 30) is None
    assert guion_y.aparicion_del_sujeto({}, 30) is None
    assert guion_y.aparicion_de_contactos({}, 30) is None


# ── la cámara: se mide la visibilidad del LIGANDO, no la del volumen del sitio ──
def test_x_acepta_una_visibilidad_propia_y_sin_ella_no_cambia():
    """`y` sustituye la medida de `x`; el defecto de `x` tiene que seguir siendo suyo."""
    import inspect
    parametros = inspect.signature(guion_x.ajustar_medidas).parameters
    assert "visibilidad" in parametros
    assert parametros["visibilidad"].default is None


def test_la_visibilidad_del_ligando_es_una_funcion_con_la_firma_de_la_de_x():
    import inspect
    visible = guion_y._visibilidad_del_ligando([object()] * 400)
    assert callable(visible)
    # Misma firma que `x._visibilidad`: (centro, radio, desde, objeto_receptor).
    assert list(inspect.signature(visible).parameters) == ["_centro", "_radio", "desde", "objeto_receptor"]
    assert list(inspect.signature(guion_x._visibilidad).parameters) == [
        "centro", "radio", "desde", "objeto_receptor"]


def test_no_se_lanzan_mas_rayos_de_los_que_el_tope_permite():
    assert guion_y.MAX_PUNTOS_VISIBILIDAD <= 120
