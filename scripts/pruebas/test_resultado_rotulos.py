"""Resultado (`sitio_activo`): los rótulos entran, la imagen se congela y se leen."""
import sys
import types

from variables import formato as fmt
from variables.pausas import Congelado, montar, segundos_de_lectura

# `sitio_activo` importa `mathutils` (de Blender) para la cámara; los rótulos no lo usan.
# El sustituto se retira en cuanto se importa: otras pruebas miran si Blender está.
_SUSTITUTO = False
try:
    import mathutils  # noqa: F401
except ImportError:
    sys.modules["mathutils"] = types.SimpleNamespace(Vector=tuple)
    _SUSTITUTO = True
from guiones import sitio_activo  # noqa: E402
if _SUSTITUTO:
    del sys.modules["mathutils"]

#: Los beats reales del vídeo vertical de Resultado de 4FK3 (acta de la corrida, 360 fotogramas).
RANGOS = {"general": (1, 87), "aproximacion": (88, 143), "pausa_hotspots": (144, 206),
          "llegada_por_fundido": (207, 292), "exploracion": (293, 352), "reposo": (353, 360)}


def _plan(**kw):
    formato = fmt.cargar("social_vertical")
    return sitio_activo.anotaciones(RANGOS, formato, formato.fps, **kw)


def _montaje(plan, eventos):
    congelados = [Congelado(p["en"], p.get("segundos") or segundos_de_lectura(len(eventos[p["en"]])),
                            p["tipo"], tuple(eventos.get(p["en"], ())), p.get("omitir_hasta"))
                  for p in plan["pausas"] if p["tipo"] != "lectura" or eventos.get(p["en"])]
    return montar(360, 30, congelados)


def test_los_rotulos_del_sujeto_entran_despues_del_ligando_y_se_congelan_juntos():
    plan = _plan(n_sujeto=6, n_hotspots=0)
    a, b = RANGOS["llegada_por_fundido"]
    sujeto = plan["sujeto"]
    assert len(sujeto) == 6
    assert sujeto[0]["ventana"][0] > a + 0.8 * 30                       # el ligando ya está
    entradas = [c["ventana"][0] for c in sujeto]
    assert entradas == sorted(entradas) and len(set(entradas)) == 6      # de uno en uno
    completo = {c["colocar_en"] for c in sujeto}
    assert len(completo) == 1                                            # todos con la misma cámara
    (f,) = completo
    assert f == max(c["fundido"][0][1] for c in sujeto)                  # cuando entró el último
    assert all(c["fundido"][1][0] > f for c in sujeto)                   # y se van después
    pausa = next(p for p in plan["pausas"] if p["en"] == f)
    assert pausa["tipo"] == "lectura" and "segundos" not in pausa


def test_con_seis_rotulos_la_imagen_se_congela_tres_segundos():
    plan = _plan(n_sujeto=6, n_hotspots=0)
    f = plan["sujeto"][0]["colocar_en"]
    m = _montaje(plan, {f: [f"r{i}" for i in range(6)]})
    lectura = next(p for p in m["pausas"] if p["tipo"] == "lectura")
    assert lectura["segundos"] == 3.0 and lectura["fuente"] == f
    # Los quietos que quedaban hasta la salida no se rinden: los sustituye la pausa.
    assert lectura["omitidos"][1] == plan["sujeto"][0]["fundido"][1][0] - 1


def test_sin_hotspots_el_sitio_vacio_se_ve_medio_segundo_y_se_rinde_una_vez():
    plan = _plan(n_sujeto=6, n_hotspots=0)
    a, b = RANGOS["pausa_hotspots"]
    assert plan["hotspots"] == []
    fija = next(p for p in plan["pausas"] if p["tipo"] == "imagen_fija")
    assert fija["en"] == a and fija["omitir_hasta"] == b
    m = _montaje(plan, {plan["sujeto"][0]["colocar_en"]: ["x"]})
    assert m["fuentes"].count(a) == 15                                   # 0,5 s a 30 fps
    assert not any(a < f <= b for f in m["fuentes"])                     # un solo render


def test_con_hotspots_tambien_se_congelan_al_completarse():
    plan = _plan(n_sujeto=3, n_hotspots=3)
    hot = plan["hotspots"]
    assert len(hot) == 3 and len({c["colocar_en"] for c in hot}) == 1
    a, b = RANGOS["pausa_hotspots"]
    assert a < hot[0]["colocar_en"] < b
    assert not any(p["tipo"] == "imagen_fija" for p in plan["pausas"])


def test_el_recorrido_del_receptor_sin_sujeto_no_rinde_dos_veces_la_misma_imagen():
    plan = _plan(n_sujeto=0, n_hotspots=0)
    assert plan["sujeto"] == []
    fijas = [p for p in plan["pausas"] if p["tipo"] == "imagen_fija"]
    assert [p["en"] for p in fijas] == [RANGOS["pausa_hotspots"][0], RANGOS["llegada_por_fundido"][0]]
    m = _montaje(plan, {})
    # El sitio vacío medio segundo; el beat del sujeto (vacío) dura lo mismo, un render.
    assert len(m["fuentes"]) == 360 - (206 - 144 + 1) + 15
    assert m["fotogramas_render_unicos"] == 360 - (206 - 144) - (292 - 207)


def test_si_no_caben_entran_mas_rapido_y_nunca_despues_de_la_salida():
    formato = fmt.cargar("social_vertical")
    rangos = dict(RANGOS, llegada_por_fundido=(207, 250))
    plan = sitio_activo.anotaciones(rangos, formato, formato.fps, n_sujeto=7, n_hotspots=0)
    for c in plan["sujeto"]:
        assert c["fundido"][0][1] <= c["colocar_en"] < c["fundido"][1][0]


def test_sin_etiquetas_3d_no_hay_rotulos_ni_pausas():
    from dataclasses import replace
    formato = replace(fmt.cargar("social_vertical"), etiquetas_3d=False)
    plan = sitio_activo.anotaciones(RANGOS, formato, formato.fps, n_sujeto=6, n_hotspots=3)
    assert plan == {"hotspots": [], "sujeto": [], "pausas": []}


def _rangos_reales(formato):
    """Los beats del guion repartidos por el formato (la llegada, ya degradada a fundido)."""
    from variables import guion as gui
    from variables.guion import Beat
    beats = [Beat("llegada_por_fundido", b.peso, b.papel) if b.id == "llegada_sujeto" else b
             for b in sitio_activo.BEATS]
    return gui.repartir(beats, formato)[0]


def test_la_vuelta_final_se_alarga_hasta_caber_entera_a_su_velocidad():
    formato = fmt.cargar("social_vertical")
    rangos = _rangos_reales(formato)
    nuevos = sitio_activo.ajustar_rangos(rangos, formato)
    a, b = nuevos["exploracion"]
    segundos = (b - a + 1) / formato.fps
    assert segundos >= sitio_activo.VUELTA_FINAL / sitio_activo.VELOCIDAD_VUELTA
    antes = {k: v for k, v in rangos.items() if k not in ("exploracion", "reposo")}
    assert {k: v for k, v in nuevos.items() if k not in ("exploracion", "reposo")} == antes
    assert nuevos["reposo"][0] == b + 1
    assert nuevos["reposo"][1] - nuevos["reposo"][0] == rangos["reposo"][1] - rangos["reposo"][0]


def test_la_vuelta_no_se_alarga_en_cpu_ni_sin_la_cascara_ni_si_ya_cabe():
    from dataclasses import replace
    for formato, experimental in ((fmt.cargar("biblioteca"), True),
                                  (fmt.cargar("social_vertical"), False),
                                  (replace(fmt.cargar("social_vertical"), segundos=3.0), True)):
        rangos = _rangos_reales(formato)
        assert sitio_activo.ajustar_rangos(rangos, formato, experimental=experimental) == rangos


def test_la_vuelta_va_a_velocidad_constante_y_solo_acelera_en_los_extremos():
    vc = sitio_activo.velocidad_constante
    assert vc(0.0) == 0.0 and abs(vc(1.0) - 1.0) < 1e-12 and vc(-1) == 0.0 and vc(2) == 1.0
    pasos = [vc((i + 1) / 100) - vc(i / 100) for i in range(100)]
    assert all(p >= 0 for p in pasos)                                   # nunca vuelve atrás
    crucero = pasos[20:80]
    assert max(crucero) - min(crucero) < 1e-9                           # sin vaivén
    assert pasos[0] < crucero[0] and pasos[-1] < crucero[0]             # arranca y frena suave
