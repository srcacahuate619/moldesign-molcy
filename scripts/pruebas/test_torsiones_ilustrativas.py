"""Invariantes geométricos y honestidad del prototipo; no importa Blender."""
import copy
import math
from types import SimpleNamespace

import pytest

from nucleo.torsiones import (RigNoDisponible, validar_rig, posiciones, curvas,
                             validar_coordenadas)
from guiones import _ensamble_fluido as fluido
from variables import presentacion, controles, formato
from variables.sujeto import Montado


@pytest.fixture
def fuente():
    # Rig unitario sintético: cadena acíclica ramificada y dos centros no planos.
    # No es evidencia de validez experimental ni de transferencia desde una corrida.
    atomos = [("C1", "C", (-1.2, .8, 0)), ("C2", "C", (0, 0, 0)),
              ("C3", "C", (1.5, 0, 0)), ("C4", "C", (2.2, 1.1, .8)),
              ("O1", "O", (2.1, -1.1, .6)), ("N1", "N", (2., -.6, -1.2)),
              ("F1", "F", (-.3, -1.1, .9))]
    return {"schema": "moldesign.rig-torsional/1", "sdf_sha256": "a" * 64,
            "atomos": [{"id": i, "elemento": e, "xyz_a": list(p)} for i, e, p in atomos],
            "enlaces": [{"atomos": [a, b], "orden": 1, "anillo": False,
                         "aromatico": False, "conjugado": False}
                        for a, b in [("C1", "C2"), ("C2", "C3"), ("C3", "C4"),
                                     ("C3", "O1"), ("C3", "N1"), ("C2", "F1")]],
            "ejes": [{"atomos": ["C1", "C2", "C3", "C4"],
                      "moviles": ["C3", "C4", "O1", "N1"], "amplitud_grados": 30.0}]}


def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def resta(a, b):
    return tuple(x - y for x, y in zip(a, b))


def determinante(a, b, c):
    return (a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0]))


def volumen(puntos, centro, vecinos):
    return determinante(*(resta(puntos[v], puntos[centro]) for v in vecinos))


@pytest.mark.parametrize("variante", ["lenta", "detallada"])
def test_extremos_exactos_fuente_intacta_y_movimientos_reales(fuente, variante):
    antes = copy.deepcopy(fuente)
    rig = validar_rig(fuente, sdf_sha256="a" * 64)
    base = [tuple(a["xyz_a"]) for a in fuente["atomos"]]
    assert posiciones(rig, 0, variante) == base
    assert posiciones(rig, 1, variante) == base
    medio = posiciones(rig, .4, variante)
    # Una distancia entre lados del eje cambia: un giro rígido no lo explicaría.
    assert abs(dist(medio[0], medio[3]) - dist(base[0], base[3])) > .05
    # El enlace estacionario también cambia su orientación por el giro global.
    v0, v1 = resta(base[0], base[1]), resta(medio[0], medio[1])
    giro = math.degrees(math.atan2(v0[0] * v1[1] - v0[1] * v1[0],
                                      v0[0] * v1[0] + v0[1] * v1[1]))
    assert giro == pytest.approx(60 * curvas(.4, variante)[1])
    assert fuente == antes


@pytest.mark.parametrize("variante", ["lenta", "detallada"])
def test_enlaces_angulos_y_configuracion_se_conservan_por_fotograma(fuente, variante):
    rig = validar_rig(fuente)
    indices = {a["id"]: i for i, a in enumerate(rig["atomos"])}
    base = posiciones(rig, 0, variante)
    pares = [(indices[a], indices[b]) for e in fuente["enlaces"] for a, b in [e["atomos"]]]
    # Todas las distancias internas del lado móvil son invariantes, además del grafo.
    pares += [(a, b) for a in (2, 3, 4, 5) for b in (2, 3, 4, 5) if a < b]
    # Ángulos de enlace: equivalen a conservar el tercer lado entre vecinos.
    pares += [(0, 2), (0, 6), (2, 6)]
    v_c3 = volumen(base, 2, [1, 3, 4])
    v_c2 = volumen(base, 1, [0, 2, 6])
    assert abs(v_c3) > .1 and abs(v_c2) > .1
    for frame in range(181):
        xyz = posiciones(rig, frame / 180, variante)
        for a, b in pares:
            assert dist(xyz[a], xyz[b]) == pytest.approx(dist(base[a], base[b]), abs=1e-10)
        assert volumen(xyz, 2, [1, 3, 4]) == pytest.approx(v_c3, abs=1e-10)
        assert volumen(xyz, 1, [0, 2, 6]) == pytest.approx(v_c2, abs=1e-10)
        for i in range(3):
            assert sum(p[i] for p in xyz) == pytest.approx(sum(p[i] for p in base), abs=1e-10)


@pytest.mark.parametrize("variante", ["lenta", "detallada"])
def test_ambos_movimientos_son_simultaneos_y_arrancan_frenan_suaves(variante):
    for t in (.1, .2, .3, .7, .8, .9):
        a, b = curvas(t, variante)
        da, db = curvas(t + .001, variante)
        assert a > 0 and b > 0
        assert abs(da - a) > 1e-7 and abs(db - b) > 1e-7
    assert max(curvas(1e-5, variante)) < 1e-10
    assert max(curvas(1 - 1e-5, variante)) < 1e-10
    assert curvas(.3, "lenta") != curvas(.3, "detallada")


@pytest.mark.parametrize("campo,valor", [("anillo", True), ("aromatico", True),
                                       ("conjugado", True), ("orden", 2)])
def test_no_rotar_enlace_restringido(fuente, campo, valor):
    fuente["enlaces"][1][campo] = valor
    with pytest.raises(RigNoDisponible):
        validar_rig(fuente)


def test_no_abrir_anillo_aunque_bandera_del_productor_sea_falsa(fuente):
    fuente["enlaces"].append({"atomos": ["C4", "C1"], "orden": 1,
                              "anillo": False, "aromatico": False, "conjugado": False})
    with pytest.raises(RigNoDisponible, match="ciclo"):
        validar_rig(fuente)


def test_no_rotar_un_subgrupo_incompleto(fuente):
    fuente["ejes"][0]["moviles"].remove("O1")
    with pytest.raises(RigNoDisponible, match="componente exacta"):
        validar_rig(fuente)


def test_rechaza_hash_ajeno_ids_ambiguos_y_mesh_ajeno(fuente):
    with pytest.raises(RigNoDisponible, match="SDF verificado"):
        validar_rig(fuente, sdf_sha256="b" * 64)
    rig = validar_rig(fuente)
    xyz = posiciones(rig, 0)
    xyz[0] = (99, 99, 99)
    with pytest.raises(RigNoDisponible, match="extremo guardado"):
        validar_coordenadas(rig, xyz)
    fuente["atomos"][1]["id"] = "C1"
    with pytest.raises(RigNoDisponible, match="repetidos"):
        validar_rig(fuente)


@pytest.mark.parametrize("valor", [True, float("nan"), float("inf"), 0, 1000])
def test_no_amplitudes_invalidas(fuente, valor):
    fuente["ejes"][0]["amplitud_grados"] = valor
    with pytest.raises(RigNoDisponible):
        validar_rig(fuente)


def montado_fluido(fuente, variante):
    rig = validar_rig(fuente)
    m = Montado()
    m.extra = {
        "conformeros": [{"indice": i, "nombre": f"Conf{i}"} for i in (7, 28, 12)],
        "puntos_conformeros": [[], [], []], "puntos_poses": [[], [], []],
        "corridas": [{"conformero": 7}], "puntos_corridas": [[]],
        "poses": [{"nombre": f"Pose{i}", "rank": i, "conformero": (7, 28, 12)[i - 1],
                   "afinidad": -6 + i / 100, "controles": None} for i in (1, 2, 3)],
        "rigs_torsionales": {7: {"nombre": "Conf7", "rig": rig}}}
    fluido.configurar(m, {"variante": variante, "conformero": 7})
    return m


@pytest.mark.parametrize("variante", ["lenta", "detallada"])
def test_presupuesto_camara_y_numeros_cientificos_solo_en_poses(fuente, variante):
    m = montado_fluido(fuente, variante)
    rangos = fluido.rangos(30)
    assert rangos["salida"][1] == 600
    assert 600 + round(3.6 * 30) == 708
    estados = [{"pos": (f, f, f), "lente": 50 + f, "portal": {"radio": f}}
               for f in range(600)]
    fijos = fluido.camara_fija(estados, rangos, 2)
    assert all(e == fijos[30] for e in fijos[30:270])
    assert fijos[0] == estados[0] and fijos[-1] == estados[-1]
    f = SimpleNamespace(escala_texto=2)
    rotulos = fluido.rotulos(rangos, f, 30, m, lambda *_: "NO EVALUADO")
    inicio, fin = fluido.ventana_movimiento(rangos, 30)
    sobre_movimiento = [r for r in rotulos if r["ventana"][0] <= fin and r["ventana"][1] >= inicio]
    assert len(sobre_movimiento) == 1
    assert "TRANSICION ILUSTRATIVA" in sobre_movimiento[0]["texto"]
    assert "KCAL/MOL" not in sobre_movimiento[0]["texto"]
    assert all(r["ventana"][0] >= 301 for r in rotulos if "KCAL/MOL" in r["texto"])
    assert fluido.mostradas(m)["poses_en_conjunto"] == 3
    assert fluido.mostradas(m)["conformeros"] == 1


def test_presentacion_estricta_y_defaults_no_ocultan_datos():
    f = formato.cargar("social_vertical")
    cambiado, extras, resueltos = controles.aplicar(f, {"presentacion": {
        "titulo": "  Mi estudio  ", "color_receptor": "#Ab12ef", "etiquetas": False}})
    assert cambiado.rotulos_pantalla is True
    assert cambiado.etiquetas_3d is False
    assert extras["presentacion"]["titulo"] == "Mi estudio"
    assert extras["presentacion"]["color_receptor"] == "#AB12EF"
    assert resueltos["presentacion"]["receptor"] == "automatico"
    for d in ({"cierre": False}, {"etiquetas": "false"}, {"color_receptor": "#fff"},
              {"titulo": "x\nfalso"}, {"receptor": "fantasma"}, {"colores_lineas": []}):
        with pytest.raises(ValueError):
            presentacion.validar(d)
    assert presentacion.validar({})["contactos"] is True


def test_acta_conserva_entrada_exacta_y_normaliza_por_separado(tmp_path):
    import json
    receta = {"presentacion": {"color_receptor": "#ab12ef", "titulo": "Mi estudio"},
              "ensamble_fluido": {"variante": "lenta", "conformero": 7}}
    ruta = tmp_path / "ajustes.json"
    ruta.write_text(json.dumps(receta), encoding="utf-8")
    entrada = controles.leer_entrada(ruta)
    assert entrada == receta
    _, _, resueltos = controles.aplicar(formato.cargar("social_vertical"), entrada)
    assert resueltos["presentacion"]["color_receptor"] == "#AB12EF"
    assert entrada == receta and "barras" not in entrada


def test_alias_no_lo_sustituye_el_catalogo_ni_trunca_silenciosamente():
    from variables.titulos import titulo_pantalla
    alias = "Mi estudio del ligando flexible con una descripcion editorial extensa de ochenta"
    texto, _ = titulo_pantalla("1CX2", "Nombre cientifico", alias=alias)
    assert " ".join(alias.split()) in " ".join(texto.split())
    assert "1CX2" in texto
    automatico, _ = titulo_pantalla("1CX2", "Nombre cientifico")
    assert automatico != texto


@pytest.mark.parametrize("activar", [True, False])
def test_muestra_anterior_es_objeto_real_y_no_desenfoque(monkeypatch, activar):
    import sys
    class Objetos(dict):
        def remove(self, obj, do_unlink=False):
            assert do_unlink
            del self[obj.name]
    anterior = SimpleNamespace(name="AnteriorReal")
    actual = SimpleNamespace(name="MuestraActual")
    objetos = Objetos(AnteriorReal=anterior, MuestraActual=actual)
    monkeypatch.setitem(sys.modules, "bpy", SimpleNamespace(data=SimpleNamespace(objects=objetos)))
    material = SimpleNamespace(diffuse_color=None, node_tree=None)
    rec = SimpleNamespace(mat_cartoon=material, mat_hotspots=material,
                          objeto=SimpleNamespace(hide_render=False, hide_viewport=False))
    m = Montado()
    m.extra = {"instantaneas": [{"fantasma": anterior.name, "nombre": actual.name}]}
    datos = presentacion.validar({"muestra_anterior": activar})
    presentacion.aplicar_montado(datos, rec, m)
    assert ("AnteriorReal" in objetos) is activar
    assert m.extra["instantaneas"][0]["fantasma"] == ("AnteriorReal" if activar else None)
    assert objetos["MuestraActual"] is actual
    assert rec.objeto.hide_render is False


def test_alias_conserva_posicion_y_tamano_proyectados_al_cambiar_lente(monkeypatch):
    import sys
    from nucleo import horneado
    cam = SimpleNamespace(data=SimpleNamespace(lens=20))
    lentes = {1: 20, 2: 55, 3: 100}
    sc = SimpleNamespace(frame_set=lambda f: setattr(cam.data, "lens", lentes[f]))
    monkeypatch.setitem(sys.modules, "bpy", SimpleNamespace(context=SimpleNamespace(scene=sc)))
    curvas_ = {}
    monkeypatch.setattr(horneado, "hornear", lambda o,r,i,fs,vs: curvas_.update({(r,i):vs}))
    obj = SimpleNamespace(location=(-3, -2, -4), scale=(4, 4, 4))
    presentacion.fijar_alias_en_cuadro(obj, cam, [1,2,3], 20)
    for ruta, i, base in (("location",0,-3),("location",1,-2),
                           ("scale",0,4),("scale",1,4),("scale",2,4)):
        assert [v*lentes[f] for f,v in zip((1,2,3),curvas_[ruta,i])] == pytest.approx([base*20]*3)
    assert ("location",2) not in curvas_
