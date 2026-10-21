"""Hallazgos de la auditoría científica de MolDesign (2026-10-20) que viven en el motor.

- SCI-A-030: el nombre del residuo de un contacto se busca por (cadena, número).
- SCI-A-031: el recuento del rótulo dice que son los contactos dibujados, con su tope.
- SCI-A-027: cada veredicto de los controles físicos tiene su rótulo.
"""
from __future__ import annotations

import pytest

from nucleo import interacciones


def _pdb(tmp_path, filas):
    """Un PDB mínimo; cada fila es (cadena, número, nombre del residuo)."""
    lineas = []
    for serie, (cadena, numero, residuo) in enumerate(filas, 1):
        lineas.append(f"ATOM  {serie:>5}  CA  {residuo:>3} {cadena}{numero:>4}    "
                      f"{0.0:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00  0.00           C")
    ruta = tmp_path / "prepared.pdb"
    ruta.write_text("\n".join(lineas) + "\nEND\n", encoding="utf-8")
    return ruta


# ── SCI-A-030 ────────────────────────────────────────────────────────────────

def test_dos_cadenas_con_la_misma_numeracion_no_se_confunden(tmp_path):
    nombres = interacciones.mapa_de_residuos(_pdb(tmp_path, [("A", 1, "ALA"), ("B", 1, "ASP")]))
    assert interacciones.nombre_de_residuo(nombres, "B", 1) == "ASP"
    assert interacciones.nombre_de_residuo(nombres, "A", 1) == "ALA"


def test_renumerar_otra_cadena_no_cambia_la_identidad(tmp_path):
    antes = interacciones.mapa_de_residuos(_pdb(tmp_path, [("A", 1, "ALA"), ("B", 1, "ASP")]))
    despues = interacciones.mapa_de_residuos(_pdb(tmp_path, [("A", 7, "ALA"), ("B", 1, "ASP")]))
    assert interacciones.nombre_de_residuo(antes, "B", 1) == \
        interacciones.nombre_de_residuo(despues, "B", 1) == "ASP"


def test_un_nombre_ambiguo_no_se_elige(tmp_path):
    """Dos residuos con la misma cadena y número (códigos de inserción): «?»."""
    nombres = interacciones.mapa_de_residuos(_pdb(tmp_path, [("A", 52, "GLY"), ("A", 52, "SER")]))
    assert interacciones.nombre_de_residuo(nombres, "A", 52) == "?"


def test_sin_correspondencia_de_cadena_el_nombre_no_consta(tmp_path):
    nombres = interacciones.mapa_de_residuos(_pdb(tmp_path, [("A", 1, "ALA")]))
    assert interacciones.nombre_de_residuo(nombres, "-1", 1) == "?"
    assert interacciones.nombre_de_residuo(None, "A", 1) == "?"


def test_el_rotulo_y_el_acta_llevan_el_nombre_de_su_cadena(tmp_path):
    nombres = interacciones.mapa_de_residuos(_pdb(tmp_path, [("A", 1, "ALA"), ("B", 1, "ASP")]))

    class _C:
        tipo, resid, cadena, etiqueta, distancia_a = "polar", 1, "B", "3.00 A", 3.0
        resname = interacciones.nombre_de_residuo(nombres, "B", 1)

    assert interacciones.texto(_C(), con_cadena=True).startswith("ASP1:B")
    assert interacciones.registro(_C())["resname"] == "ASP"


# ── SCI-A-027 ────────────────────────────────────────────────────────────────

def _controles(**cambios):
    from guiones.y import _controles
    base = {"estado": "passed", "aprobadas": 15, "pruebas": 15, "fallos": [], "no_evaluados": 0}
    return _controles({**base, **cambios}, "CONTROLES POSEBUSTERS")


def test_un_fallo_medido_no_se_rotula_como_no_evaluado():
    texto = _controles(estado="failed", aprobadas=14, fallos=["internal_energy"])
    assert "NO EVALUADOS" not in texto
    assert "14/15" in texto and "FALLAN: INTERNAL_ENERGY" in texto


def test_una_bateria_parcial_dice_cuantos_quedaron_sin_evaluar():
    texto = _controles(estado="review", aprobadas=12, no_evaluados=3)
    assert "12/15" in texto and "3 SIN EVALUAR" in texto


def test_revision_sin_fallos_ni_huecos_se_dice():
    assert "REVISION NECESARIA" in _controles(estado="review")


@pytest.mark.parametrize("controles", [None, {"estado": "not_evaluated", "aprobadas": None,
                                              "pruebas": None, "fallos": []}])
def test_lo_que_el_validador_no_midio_sigue_siendo_no_evaluado(controles):
    from guiones.y import _controles
    assert _controles(controles, "CONTROLES FISICOS") == "CONTROLES FISICOS: NO EVALUADOS"


def test_los_rotulos_nuevos_son_ascii():
    for texto in (_controles(estado="failed", aprobadas=14, fallos=["x"]),
                  _controles(estado="review", no_evaluados=2), _controles(estado="review")):
        assert all(ord(c) < 128 for c in texto), texto


# ── SCI-A-031 ────────────────────────────────────────────────────────────────

def test_el_recuento_de_contactos_dice_que_son_los_dibujados_y_su_tope():
    import test_guion_y as guion_y
    t, _ = guion_y._textos(guion_y._montado())
    texto = t["y_pose_1"]["texto"]
    assert f"DIBUJADOS (MAX. {interacciones.MAX_POR_TIPO} POR CLASE)" in texto
    assert "POLARES" in texto and "APOLARES" in texto
