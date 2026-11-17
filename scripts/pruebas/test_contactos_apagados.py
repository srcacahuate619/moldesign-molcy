"""Apagar los contactos quita las LÍNEAS y sus rótulos de distancia, nada más.

El interruptor `contactos` (`moldesign.presentacion/1`) es arte: no dibuja una
capa, no cambia lo que la escena afirma (`variables/controles.py`). Medido en
3RUT con el guion `x` (2026-11-17): con `contactos=false` el motor borraba
`montado.secundarios`, que en `busqueda_montecarlo` son las nueve poses de Vina.
El ligando desaparecía del sitio, de las poses y de la salida, y las líneas
punteadas seguían; el acta decía «contactos no dibujados».

Sin Blender: el sujeto de `x` se monta con un doble de `bpy` y de Molecular
Nodes que sólo lleva la cuenta de qué objetos hay en la escena.
"""
import ast
import copy
import json
import math
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from nucleo import interacciones
from nucleo.ciencia import Paquete
from variables import presentacion
from variables.sujeto import Contexto, Montado, apagar_contactos

SUJETOS = Path(__file__).resolve().parents[1] / "sujetos"
N_POSES, POR_POSE = 9, 2          # 3RUT: nueve poses de Vina


class V(tuple):
    """Lo de `mathutils.Vector` que usa el montaje del sujeto."""

    def __new__(cls, v=(0.0, 0.0, 0.0)):
        return super().__new__(cls, (float(x) for x in v))

    def __mul__(self, k):
        return V(x * k for x in self)

    __rmul__ = __mul__

    def __sub__(self, o):
        return V(a - b for a, b in zip(self, o))

    def copy(self):
        return V(self)

    @property
    def length(self):
        return math.sqrt(sum(x * x for x in self))


class Escena(dict):
    """nombre -> objeto: lo que habría en `bpy.data.objects`."""

    def nuevo(self, nombre, clase):
        self[nombre] = SimpleNamespace(name=nombre, clase=clase)
        return self[nombre]

    def retirar(self, obj):
        del self[obj.name]

    def de_clase(self, clase):
        return sorted(n for n, o in self.items() if o.clase == clase)


def _paquete_x(tmp_path):
    pdb = "HETATM    1  C1  LIG A   1       1.0   2.0   3.0\nEND\n"
    (tmp_path / "docking" / "poses").mkdir(parents=True)
    poses = []
    for r in range(1, N_POSES + 1):
        (tmp_path / "docking" / "poses" / f"pose_{r:03d}.pdb").write_text(pdb, encoding="utf-8")
        poses.append({"rank": r, "afinidad_kcal_mol": -9.0 + r / 10,
                      "archivo": f"docking/poses/pose_{r:03d}.pdb"}
                     | ({"rmsd_cristal_a": 1.2} if r == 1 else {}))
    (tmp_path / "docking" / "snapshot_001.pdb").write_text(pdb, encoding="utf-8")
    dock = {"schema": "moldesign.dock/1", "motor": {"nombre": "vina"},
            "caja": {"centro": [1.0, 2.0, 3.0], "tamano": [20.0, 20.0, 20.0]}, "poses": poses,
            "traza_interna": {"tipo": "vina_monte_carlo_bfgs_interno", "replicas": 2,
                              "pasos_totales": 24, "pasos_replica": 12, "aceptados_totales": 8,
                              "instantaneas": [{"task": 0, "step": 6,
                                                "archivo": "docking/snapshot_001.pdb"}]}}
    escena = {"schema": "moldesign.scene/1",
              "receptor": {"pdb_id": "3RUT", "nombre": "Prueba", "cadena_principal": "A"},
              "encuadre": {"objetivo": [1.0, 2.0, 3.0], "caja": [20, 20, 20]},
              "resaltar": {"hotspots": []},
              "geometria": {"prepared": {"atomos": 1, "cadenas_conservadas": ["A"]}},
              "declarado": {}, "no_dibujar": [], "declarar_si_se_dibuja": [], "procedencia": {}}
    (tmp_path / "scene.json").write_text(json.dumps(escena), encoding="utf-8")
    (tmp_path / "docking.json").write_text(json.dumps(dock), encoding="utf-8")
    return Paquete.cargar(tmp_path)


def _blender_de_mentira(monkeypatch, escena):
    """`bpy`, Molecular Nodes y los módulos de `nucleo` que dibujan, sin Blender."""
    import nucleo
    import sujetos
    from sujetos import busqueda_montecarlo as suj

    def modulo(nombre, **attrs):
        m = types.ModuleType(nombre)
        m.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, nombre, m)
        return m

    def cargar_molecula(_ruta, name):
        return SimpleNamespace(object=escena.nuevo(name, "molecula"),
                               add_style=lambda *_a, **_k: None)

    mn = modulo("bl_ext.blender_org.molecularnodes",
                Molecule=SimpleNamespace(load=cargar_molecula))
    blender_org = modulo("bl_ext.blender_org", molecularnodes=mn)
    modulo("bl_ext", blender_org=blender_org)
    modulo("bpy")
    modulo("bmesh")
    modulo("mathutils", Vector=V, Matrix=object)
    material = lambda nombre, *_a, **_k: SimpleNamespace(name=nombre)   # noqa: E731
    falsos = {
        "arte": modulo("nucleo.arte", material_del_estilo=lambda _mol, _estilo, nombre: material(nombre),
                       realzar_protagonista=lambda _m: None,
                       puntos_evaluados=lambda _o: [V()], centro_evaluado=lambda _o: V((1, 2, 3))),
        "receptor": modulo("nucleo.receptor"),
        "contactos": modulo("nucleo.contactos", mapa_de_residuos=lambda _r: {},
                            dibujar=lambda nombre, _c, _m: escena.nuevo(nombre, "linea")),
    }
    for nombre, falso in falsos.items():
        monkeypatch.setattr(nucleo, nombre, falso, raising=False)
    monkeypatch.setattr(sujetos, "ligando_cocristal",
                        modulo("sujetos.ligando_cocristal", inferir_enlaces=lambda _o: 0),
                        raising=False)

    def medir(_rec, _mol, _centro, **_k):
        contactos = [SimpleNamespace(tipo=tipo, a=V((0, 0, 0)), b=V((3, 0, 0)), medio=V((1.5, 0, 0)),
                                     resname="ASP", resid=30 + j, cadena="A", distancia_a=3.0,
                                     etiqueta="3.0 A")
                     for j, tipo in enumerate(("polar", "hidrofobico")[:POR_POSE])]
        return contactos, 1, 1
    monkeypatch.setattr(interacciones, "medir", medir)
    monkeypatch.setattr(interacciones, "materiales_de_linea",
                        lambda _arte, pref: (material(pref + "ContactoPolar"),
                                             material(pref + "ContactoApolar")))
    for nombre in ("_material_emision", "_material_translucido"):
        monkeypatch.setattr(suj, nombre, material)
    monkeypatch.setattr(suj, "_caja", lambda nombre, *_a: (escena.nuevo(nombre, "caja"), [V()] * 8))
    monkeypatch.setattr(suj, "_esfera", lambda nombre, *_a: escena.nuevo(nombre, "esfera"))
    monkeypatch.setattr(suj, "_silueta_anterior", lambda nombre, *_a: escena.nuevo(nombre, "silueta"))
    # `cargar` los fija como globales del módulo: que se deshagan al terminar.
    for nombre in ("bpy", "bmesh", "mn", "Matrix", "Vector", "arte", "receptor"):
        monkeypatch.setattr(suj, nombre, None, raising=False)
    return suj


def test_en_x_apagar_contactos_conserva_las_nueve_poses_y_quita_solo_las_lineas(tmp_path, monkeypatch):
    escena = Escena()
    suj = _blender_de_mentira(monkeypatch, escena)
    ctx = Contexto(receptor=SimpleNamespace(hotspots=[], molecula=object()), arte={}, pivote=V((1, 2, 3)))
    m = suj.cargar(_paquete_x(tmp_path), ctx)

    poses = escena.de_clase("molecula")
    poses = [n for n in poses if "_Pose" in n]
    assert len(poses) == N_POSES
    assert len(escena.de_clase("linea")) == N_POSES * POR_POSE
    # El sujeto declara sus líneas, y sólo sus líneas: ninguna pose entre ellas.
    assert sorted(o.name for o in m.lineas_contacto) == escena.de_clase("linea")
    medido = copy.deepcopy(m.medido)
    assert len(medido["contactos"]) == N_POSES * POR_POSE
    materiales_poses = list(m.materiales_secundarios)

    retiradas = []
    quitado = apagar_contactos(m, lambda o: (retiradas.append(o.clase), escena.retirar(o)))

    assert quitado["lineas"] == N_POSES * POR_POSE and set(retiradas) == {"linea"}
    assert escena.de_clase("linea") == []
    # El ligando sigue: las nueve poses en la escena, en `secundarios` y en lo que anima el guion.
    assert [n for n in escena.de_clase("molecula") if "_Pose" in n] == poses
    assert sorted(o.name for o in m.secundarios) == poses
    assert all(p["nombre"] in escena for p in m.extra["poses"])
    assert m.materiales_secundarios == materiales_poses
    # Los rótulos de distancia se van con sus líneas; los de las poses y la caja, no.
    ids = [a[0] for a in m.anclas]
    assert not [i for i in ids if i.startswith("dist")]
    assert quitado["rotulos"] == N_POSES * POR_POSE + POR_POSE      # + los del primer plano del sitio
    assert {f"pose{r}" for r in range(1, N_POSES + 1)} | {"caja", "rmsd"} == set(ids)
    # Lo medido no se toca: el acta sigue diciendo qué contactos hay.
    assert m.medido == medido


def test_en_sitio_activo_se_quitan_las_lineas_y_el_ligando_se_queda():
    """La forma de `ligando_cocristal` y `pose_evaluada`: las líneas también son secundarios."""
    escena = Escena()
    ligando = escena.nuevo("3RUT_ligando", "molecula")
    lineas = [escena.nuevo(f"Contacto_{i}", "linea") for i in range(3)]
    mat_ligando, mat_linea = SimpleNamespace(name="lig"), SimpleNamespace(name="linea")
    m = Montado(objetos=[ligando], materiales=[mat_ligando], secundarios=list(lineas),
                materiales_secundarios=[mat_linea], lineas_contacto=list(lineas),
                anclas=[("lig", "MK1", None)] + [(f"dist{i}", "x", None) for i in range(3)],
                extra={"materiales_contacto": [mat_linea]}, medido={"contactos": [{"resid": 30}]})

    quitado = apagar_contactos(m, escena.retirar)

    assert quitado == {"lineas": 3, "rotulos": 3}
    assert list(escena) == ["3RUT_ligando"]
    assert m.objetos == [ligando] and m.materiales == [mat_ligando]
    assert m.secundarios == [] and m.materiales_secundarios == [] and m.lineas_contacto == []
    assert m.anclas == [("lig", "MK1", None)]
    assert m.medido == {"contactos": [{"resid": 30}]}


def test_el_color_de_las_lineas_no_tine_las_poses_de_x():
    """En `x`, `materiales_secundarios` son las poses: el color polar no va ahí."""
    def material():
        return SimpleNamespace(diffuse_color=None, node_tree=None)
    rec = SimpleNamespace(mat_cartoon=material(), mat_hotspots=material(),
                          objeto=SimpleNamespace(hide_render=False, hide_viewport=False))
    pose, polar, apolar = material(), material(), material()
    m = Montado(materiales_secundarios=[pose], extra={"materiales_contacto": [polar, apolar]})
    datos = presentacion.validar({"colores_lineas": {"polar": "#FF0000", "apolar": "#0000FF"}})
    presentacion.aplicar_montado(datos, rec, m)
    assert polar.diffuse_color == presentacion.rgba("#FF0000")
    assert apolar.diffuse_color == presentacion.rgba("#0000FF")
    assert pose.diffuse_color is None
    sin_lineas = Montado(materiales_secundarios=[pose])
    presentacion.aplicar_montado(datos, rec, sin_lineas)
    assert pose.diffuse_color is None


def _lineas_sin_declarar(fuente):
    """Las líneas que una función dibuja (`contactos.dibujar` / `malla_punteada`) y no
    pone en `lineas_contacto`: el motor no podría apagarlas."""
    dibujan, sin_declarar = False, []
    for fn in ast.walk(ast.parse(fuente)):
        if not isinstance(fn, ast.FunctionDef):
            continue
        dibujadas, declaradas = set(), set()
        for n in ast.walk(fn):
            if (isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
                    and isinstance(n.value.func, ast.Attribute)
                    and n.value.func.attr in ("dibujar", "malla_punteada")
                    and getattr(n.value.func.value, "id", None) == "contactos"):
                dibujadas |= {t.id for t in n.targets if isinstance(t, ast.Name)}
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "append"
                    and getattr(n.func.value, "attr", None) == "lineas_contacto"):
                declaradas |= {a.id for a in n.args if isinstance(a, ast.Name)}
        dibujan |= bool(dibujadas)
        sin_declarar += [f"{fn.name}: {v}" for v in sorted(dibujadas - declaradas)]
    return dibujan, sin_declarar


def test_todo_sujeto_que_dibuja_lineas_las_declara_en_lineas_contacto():
    dibujan = set()
    for ruta in sorted(SUJETOS.glob("*.py")):
        dibuja, faltan = _lineas_sin_declarar(ruta.read_text(encoding="utf-8"))
        assert not faltan, f"{ruta.name} dibuja líneas que el interruptor no puede apagar: {faltan}"
        if dibuja:
            dibujan.add(ruta.stem)
    assert dibujan == {"busqueda_montecarlo", "ensamble_conformacional",
                       "ligando_cocristal", "pose_evaluada"}
