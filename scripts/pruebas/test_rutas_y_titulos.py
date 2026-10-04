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
