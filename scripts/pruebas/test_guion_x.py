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
        d["traza"] = {"tipo": "metropolis", "semilla": 7,
                      "pasos": [{"i": i, "centro": [1.0 + i * 0.01, 2.0, 3.0],
                                 "energia": -2.0 - i * 0.1, "aceptada": i % 3 == 0}
                                for i in range(12)]}
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
