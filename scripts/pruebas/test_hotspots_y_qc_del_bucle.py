"""Hotspots que no están en `prepared.pdb` y la puerta de calidad del bucle.

Medido en la previsualización de los 380 receptores del catálogo (Colab, 2026-11-17):

- 23 escenas declaraban hotspots de una cadena que la preparación quitó (la compañera
  de una interfaz, el ADN de 7KQM). Buscados sólo por número caían en OTRO residuo de
  otra cadena: en 9QA4 el TRP95 de la cadena C se dibujaba sobre el ARG95 de la A, a
  41 Å del sitio, y las dianas dispersas hacían saltar la puerta de calidad.
- `camara_se_aleja` rechazaba 10 receptores pequeños en el bucle, que no tiene
  aproximación: sólo orbita a la distancia del plano general.
"""
import json

from nucleo.ciencia import Paquete
from salida import control
from variables import formato as fmt


def _linea(serie, nombre, resname, cadena, numero):
    return (f"ATOM  {serie:5d} {nombre:<4} {resname:>3} {cadena}{numero:4d}    "
            f"{1.0:8.3f}{2.0:8.3f}{3.0:8.3f}  1.00  0.00           C\n")


def _paquete(tmp_path, hotspots, residuos):
    geo = tmp_path / "geometry"
    geo.mkdir()
    (geo / "prepared.pdb").write_text(
        "".join(_linea(i, "CA", rn, c, n) for i, (c, n, rn) in enumerate(residuos, 1)) + "END\n",
        encoding="utf-8")
    datos = {"receptor": {"pdb_id": "TEST", "cadena_principal": "A"},
             "resaltar": {"hotspots": hotspots},
             "geometria": {"prepared": {"cadenas_conservadas": sorted({c for c, _, _ in residuos})}}}
    (tmp_path / "scene.json").write_text(json.dumps(datos), encoding="utf-8")
    return Paquete.cargar(tmp_path)


def _h(nombre, importancia, **extra):
    cadena, resto = nombre.split(":")
    resname, numero = resto[:3], int(resto[3:])
    return {"nombre": nombre, "importancia": importancia, "parseado": True,
            "cadena": cadena, "resname": resname, "numero": numero, **extra}


def test_un_hotspot_de_una_cadena_quitada_no_se_dibuja(tmp_path):
    paq = _paquete(tmp_path,
                   [_h("C:TRP95", 1.0), _h("A:GLU150", 0.9), _h("A:ASP360", 0.8)],
                   [("A", 95, "ARG"), ("A", 150, "GLU"), ("A", 360, "ASP")])
    assert [(h.cadena, h.numero) for h in paq.hotspots(3)] == [("A", 150), ("A", 360)]
    assert paq.hotspots_ausentes() == ["C:TRP95"]


def test_mismo_numero_y_cadena_pero_otro_residuo_tampoco(tmp_path):
    # La cadena sigue, pero en ese número hay otro aminoácido: no es el hotspot.
    paq = _paquete(tmp_path, [_h("A:TRP95", 1.0)], [("A", 95, "ARG")])
    assert paq.hotspots() == []
    assert paq.hotspots_ausentes() == ["A:TRP95"]


def test_lo_que_marca_el_exportador_manda(tmp_path):
    paq = _paquete(tmp_path, [_h("A:GLU150", 1.0, en_preparado=False)], [("A", 150, "GLU")])
    assert paq.hotspots() == []


def test_los_presentes_no_cambian(tmp_path):
    hs = [_h("A:ASP25", 1.0), _h("B:ASP25", 0.9), _h("A:ILE50", 0.8)]
    paq = _paquete(tmp_path, hs, [("A", 25, "ASP"), ("B", 25, "ASP"), ("A", 50, "ILE")])
    assert [(h.cadena, h.numero) for h in paq.hotspots()] == [("A", 25), ("B", 25), ("A", 50)]
    assert paq.hotspots_ausentes() == []


# ── puerta de calidad ────────────────────────────────────────────────────
#: 1CBR, medido: el primer plano a 0.87 de la distancia general, dianas compactas.
MEDIDAS_PEQUENO = {"dist_general": 4.99, "dist_primer_plano": 4.35, "radio_dianas": 1.3}


def _ids(medidas, formato):
    return {a.id for a in control.revisar(medidas, formato).fatales}


def test_el_bucle_no_rechaza_por_alejamiento():
    assert "camara_se_aleja" not in _ids(MEDIDAS_PEQUENO, fmt.cargar("previsualizacion"))


def test_con_aproximacion_sigue_siendo_fatal():
    for nombre in ("biblioteca", "social_vertical"):
        assert "camara_se_aleja" in _ids(MEDIDAS_PEQUENO, fmt.cargar(nombre)), nombre


def test_el_bucle_sigue_rechazando_dianas_dispersas():
    medidas = {"dist_general": 8.51, "dist_primer_plano": 9.8, "radio_dianas": 3.66}   # 9QA4
    assert _ids(medidas, fmt.cargar("previsualizacion")) == {"dianas_dispersas"}
