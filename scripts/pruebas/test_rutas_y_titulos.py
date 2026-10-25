from pathlib import Path

from nucleo.ciencia import Paquete
from nucleo.rutas import carpeta_de_caso
from variables.titulos import nombre_legible, titulo_pantalla


# ── carpeta del caso ─────────────────────────────────────────────────────
def test_reutiliza_la_carpeta_existente(tmp_path):
    (tmp_path / "016_topoisomerase_1EI1").mkdir()
    assert carpeta_de_caso("1EI1", "otra", tmp_path).name == "016_topoisomerase_1EI1"


def test_numera_el_siguiente_libre(tmp_path):
    (tmp_path / "025_methyltransferase_1HVY").mkdir()
    (tmp_path / "_lote_v4_estado.log").write_text("")
    assert carpeta_de_caso("1IAS", "kinase", tmp_path).name == "026_kinase_1IAS"


def test_dos_receptores_nuevos_no_comparten_numero_si_se_crea_al_calcular(tmp_path):
    (tmp_path / "025_x_1HVY").mkdir()
    a = carpeta_de_caso("1IAS", "kinase", tmp_path)
    a.mkdir()
    b = carpeta_de_caso("1IGZ", "oxidoreductase", tmp_path)
    assert (a.name[:3], b.name[:3]) == ("026", "027")


def test_familia_vacia(tmp_path):
    assert carpeta_de_caso("9XYZ", "", tmp_path).name == "001_desconocida_9XYZ"


# ── titulos ──────────────────────────────────────────────────────────────
def test_siglas_y_especie():
    assert nombre_legible(
        "DIMERIZATION OF E. COLI DNA GYRASE B PROVIDES A STRUCTURAL MECHANISM"
    ) == "Dimerization of E. coli DNA Gyrase B Provides a Structural Mechanism"


def test_letra_final_no_es_articulo():
    assert nombre_legible("AN HDAC HOMOLOG COMPLEXED WITH TRICHOSTATIN A") \
        == "An HDAC Homolog Complexed with Trichostatin A"
    assert nombre_legible("DNA GYRASE A C-TERMINAL DOMAIN") == "DNA Gyrase A C-Terminal Domain"


def test_cola_truncada_y_prefijo():
    assert nombre_legible("CRYSTAL STRUCTURE OF A COMPLEX OF THE SRC SH2 DOMAIN WITH") \
        == "A Complex of the SRC SH2 Domain"
    assert nombre_legible("THE Crystal Structure of PDE6D in Complex with the Inhibitor") \
        == "PDE6D in Complex with the Inhibitor"


def test_caja_mixta_no_se_toca():
    s = "Human thymidylate synthase complexed with dUMP"
    assert nombre_legible(s) == s


def test_unidades_genero_y_factor():
    assert nombre_legible("E. COLI 24KDA DOMAIN IN COMPLEX WITH CLOROBIOCIN") \
        == "E. coli 24 kDa Domain in Complex with Clorobiocin"
    assert nombre_legible("REVERSE GYRASE FROM ARCHAEOGLOBUS FULGIDUS") \
        == "Reverse Gyrase from Archaeoglobus fulgidus"
    assert nombre_legible("HUMAN COAGULATION FACTOR XA COMPLEXED WITH RPR208815") \
        == "Human Coagulation Factor Xa Complexed with RPR208815"


def test_titulo_curado_y_dos_lineas():
    texto, escala = titulo_pantalla("1HSG", "HIV-1 PROTEASE", 2.0)
    assert texto.startswith("HIV-1 Protease") and "1HSG" in texto
    texto, escala = titulo_pantalla(
        "1EI1", "DIMERIZATION OF E. COLI DNA GYRASE B PROVIDES A STRUCTURAL "
        "MECHANISM FOR ACTIVATING THE ATPASE CATALYTIC CENTER", 2.3)
    assert len(texto.split("\n")) <= 2
    assert 0.0 < escala <= 0.78


def test_seccion_demostracion_se_rotula_en_el_idioma_del_cierre():
    texto, _ = titulo_pantalla("1HSG", "HIV-1 PROTEASE", 2.0, seccion="demostracion", idioma="es")
    assert texto.split("\n")[-1] == "Demostración"
    texto, _ = titulo_pantalla("1HSG", "HIV-1 PROTEASE", 2.0, seccion="demostracion", idioma="en")
    assert texto.split("\n")[-1] == "Demonstration"


def test_sin_seccion_o_verificado_el_titulo_no_cambia():
    base = titulo_pantalla("1HSG", "HIV-1 PROTEASE", 2.0)
    assert titulo_pantalla("1HSG", "HIV-1 PROTEASE", 2.0, seccion=None) == base
    assert titulo_pantalla("1HSG", "HIV-1 PROTEASE", 2.0, seccion="verificado", idioma="es") == base
    assert "Demostración" not in base[0]


def test_la_etiqueta_se_añade_sin_recortar_el_nombre():
    texto, escala = titulo_pantalla(
        "1EI1", "DIMERIZATION OF E. COLI DNA GYRASE B PROVIDES A STRUCTURAL "
        "MECHANISM FOR ACTIVATING THE ATPASE CATALYTIC CENTER", 2.3,
        seccion="demostracion", idioma="es")
    assert texto.split("\n")[-1] == "Demostración"
    assert len(texto.split("\n")) == 3
    assert 0.0 < escala <= 0.78


def test_un_titulo_propio_no_quita_la_etiqueta_de_demostracion():
    # El alias (controles de presentación) sustituye al nombre, pero el vídeo sigue diciendo lo que dice la aplicación.
    alias = "Mi estudio del ligando flexible con una descripcion editorial extensa de ochenta"
    for idioma, etiqueta in (("es", "Demostración"), ("en", "Demonstration")):
        texto, escala = titulo_pantalla("1HSG", "HIV-1 PROTEASE", 2.0, seccion="demostracion", idioma=idioma, alias=alias)
        assert texto.splitlines()[-1] == etiqueta
        assert " ".join(alias.split()) in " ".join(texto.split())
        assert 0.0 < escala <= 0.78
    sin_seccion, _ = titulo_pantalla("1HSG", "HIV-1 PROTEASE", 2.0, alias=alias)
    assert "Demostración" not in sin_seccion and "Demonstration" not in sin_seccion


def test_maestro_pasa_la_seccion_en_cada_titulo():
    import ast
    arbol = ast.parse((Path(__file__).resolve().parents[1] / "maestro.py").read_text(encoding="utf-8"))
    llamadas = [n for n in ast.walk(arbol) if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "titulo_pantalla"]
    assert len(llamadas) == 3
    for llamada in llamadas:
        assert {k.arg for k in llamada.keywords} >= {"seccion", "alias"}, ast.unparse(llamada)


def test_el_paquete_declara_su_seccion_o_no_la_declara():
    assert Paquete(raiz=Path("."), datos={"receptor": {"pdb_id": "1HSG", "seccion": "demostracion"}}).seccion \
        == "demostracion"
    assert Paquete(raiz=Path("."), datos={"receptor": {"pdb_id": "1HSG"}}).seccion is None
