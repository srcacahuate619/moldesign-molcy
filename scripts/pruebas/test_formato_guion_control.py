from nucleo.ciencia import Prohibido
from salida import control
from variables import formato as fmt
from variables import guion as gui
from variables.guion import Acta, Beat


class PaqueteFalso:
    """Solo lo que usa `resolver`: un contrato que veta la trayectoria."""

    def exigir(self, *ids):
        if "trayectoria_de_union" in ids:
            raise Prohibido("trayectoria_de_union", "no hay trayectoria medida",
                            "fundido")


BEATS = [
    Beat("general", 5.5, "establecer"),
    Beat("aproximacion", 3.5, "aproximar"),
    Beat("pausa_hotspots", 4.0, "pausa"),
    Beat("llegada_sujeto", 5.4, "pausa", permisos=("trayectoria_de_union",),
         alternativa="llegada_por_fundido", requiere="sujeto"),
    Beat("exploracion", 3.8, "explorar"),
    Beat("reposo", 0.5, "reposo", minimo_fotogramas=2),
]


# ── formatos ─────────────────────────────────────────────────────────────
def test_se_descubren_los_tres_formatos():
    assert {"biblioteca", "previsualizacion", "social_vertical"} <= set(fmt.disponibles())


def test_vertical_medido():
    v = fmt.cargar("social_vertical")
    assert (v.ancho, v.alto, v.fotogramas) == (1080, 1920, 360)
    assert v.muestras == 64 and v.escala_sombras == 0.5
    assert v.vertical and "escala_sombras" in v.resumen()


def test_el_resto_no_cambia_de_sombras():
    for n in ("biblioteca", "previsualizacion"):
        assert fmt.cargar(n).escala_sombras == 1.0


# ── guion x formato ──────────────────────────────────────────────────────
def test_repartir_cubre_el_presupuesto_sin_huecos():
    for n, f in fmt.disponibles().items():
        acta = Acta()
        beats = gui.resolver(BEATS, PaqueteFalso(), {"sujeto": True}, f, acta)
        rangos, total = gui.repartir(beats, f)
        assert total == f.fotogramas, n
        tramos = sorted(rangos.values())
        assert tramos[0][0] == 1 and tramos[-1][1] == total
        for (a0, b0), (a1, b1) in zip(tramos, tramos[1:]):
            assert a1 == b0 + 1 and a0 <= b0


def test_el_contrato_degrada_y_lo_anota():
    acta = Acta()
    vivos = gui.resolver(BEATS, PaqueteFalso(), {"sujeto": True},
                         fmt.cargar("social_vertical"), acta)
    ids = [b.id for b in vivos]
    assert "llegada_por_fundido" in ids and "llegada_sujeto" not in ids
    assert any(d.get("decision") == "degradado" for d in acta.decisiones)


def test_la_previsualizacion_tira_las_pausas():
    vivos = gui.resolver(BEATS, PaqueteFalso(), {"sujeto": True},
                         fmt.cargar("previsualizacion"), Acta())
    assert [b.id for b in vivos] == ["general"]


# ── puerta de calidad ────────────────────────────────────────────────────
def test_qc_camara_que_se_aleja_es_fatal():
    inf = control.revisar({"dist_general": 5.0, "dist_primer_plano": 5.2},
                          fmt.cargar("social_vertical"))
    assert not inf.ok and inf.fatales[0].id == "camara_se_aleja"


def test_qc_encuadre_bueno_pasa():
    inf = control.revisar({"dist_general": 9.81, "dist_primer_plano": 2.17,
                           "arco": {"minimo": 0.63}, "visibilidad_azimut": 1.0},
                          fmt.cargar("social_vertical"))
    assert inf.ok and not inf.avisos


def test_qc_dianas_dispersas_es_fatal():
    # la clave la produce `maestro.medir`; antes no existia y esto no saltaba
    inf = control.revisar({"dist_general": 10.0, "dist_primer_plano": 2.0,
                           "radio_dianas": 5.7}, fmt.cargar("biblioteca"))
    assert [a.id for a in inf.fatales] == ["dianas_dispersas"]


def test_maestro_publica_radio_dianas():
    from pathlib import Path
    fuente = (Path(__file__).resolve().parents[1] / "maestro.py").read_text(encoding="utf-8")
    assert '"radio_dianas":' in fuente
