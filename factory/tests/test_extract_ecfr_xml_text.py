"""Tests -- factory/regulatory/tools/extract_ecfr_xml_text.py

Por que existe el extractor: `_load_source_full_text` del constructor de
contexto solo lee `.txt` canonico o artefacto pdfplumber, asi que la fuente
XML `ecfr_21cfr_part211` era ilegible para el pipeline y ninguna cita podia
anclarse contra Part 211.

Garantias fijadas:
  - determinismo: mismo XML -> mismo extracted_text_sha256
  - el texto normativo no se reescribe ni se reordena
  - `_SUBSTITUTE_DATE_` vive en atributos y NO contamina la extraccion
  - una unidad por seccion (DIV8), que es la unidad de cita real del CFR
  - fail-closed si el fichero canonico ya no coincide con sha256_copy
  - los artefactos derivados no se sobrescriben
  - sobre el XML REAL: 211.68 se extrae integro y anclable
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.regulatory.tools import extract_ecfr_xml_text as ex

_XML = """<?xml version="1.0"?>
<DIV5 N="211" TYPE="PART" hierarchy_metadata="{&amp;quot;path&amp;quot;:&amp;quot;/on/_SUBSTITUTE_DATE_/x&amp;quot;}">
<HEAD>PART 211&#x2014;TITULO DE PRUEBA</HEAD>
<AUTH><HED>Authority:</HED><PSPACE>21 U.S.C. 321.</PSPACE></AUTH>
<DIV6 N="A" TYPE="SUBPART">
<DIV8 N="211.68" TYPE="SECTION" hierarchy_metadata="{&amp;quot;path&amp;quot;:&amp;quot;/on/_SUBSTITUTE_DATE_/y&amp;quot;}">
<HEAD>&#xA7; 211.68 Equipo automatico.</HEAD>
<P>(a) Primer parrafo    con   espacios raros.</P>
<P>(b) Segundo parrafo.</P>
</DIV8>
<DIV8 N="211.70" TYPE="SECTION"><HEAD>&#xA7; 211.70 Otra.</HEAD><P>Texto.</P></DIV8>
</DIV6>
</DIV5>
"""


@pytest.fixture()
def xml_file(tmp_path):
    path = tmp_path / "part211.xml"
    path.write_text(_XML, encoding="utf-8")
    return path


def test_one_unit_per_section_plus_header(xml_file):
    units = ex.extract_units(xml_file)
    assert len(units) == 3
    assert units[0].startswith("PART 211")
    assert units[1].startswith("§ 211.68")
    assert units[2].startswith("§ 211.70")


def test_substitute_date_placeholder_never_reaches_the_text(xml_file):
    """Vive en atributos hierarchy_metadata. Si apareciera en el texto seria
    una fecha fabricada dentro de una fuente normativa."""
    assert "_SUBSTITUTE_DATE_" not in "\n".join(ex.extract_units(xml_file))


def test_extraction_is_deterministic(xml_file):
    entry = {"source_id": "x", "sha256_copy": "a" * 64}
    a1 = ex.build_artifact(entry, xml_file)
    a2 = ex.build_artifact(entry, xml_file)
    assert a1["extracted_text_sha256"] == a2["extracted_text_sha256"]
    assert a1["pages"] == a2["pages"]


def test_normative_text_is_not_reordered(xml_file):
    section = ex.extract_units(xml_file)[1]
    assert section.index("(a) Primer parrafo") < section.index("(b) Segundo parrafo")
    assert "(a) Primer parrafo con espacios raros." in section


def test_document_without_sections_returns_whole_document(tmp_path):
    path = tmp_path / "sin_secciones.xml"
    path.write_text('<?xml version="1.0"?><DIV5><P>Solo texto suelto.</P></DIV5>', encoding="utf-8")
    units = ex.extract_units(path)
    assert units == ["Solo texto suelto."]


def test_empty_document_raises_instead_of_returning_nothing(tmp_path):
    path = tmp_path / "vacio.xml"
    path.write_text('<?xml version="1.0"?><DIV5></DIV5>', encoding="utf-8")
    with pytest.raises(ex.EcfrXmlExtractionError, match="no produjo texto"):
        ex.extract_units(path)


# --- registro fail-closed --------------------------------------------------

@pytest.fixture()
def registry_env(tmp_path, monkeypatch, xml_file):
    canonical_dir = tmp_path / "repo" / "sources" / "sha256" / "hash"
    canonical_dir.mkdir(parents=True)
    canonical = canonical_dir / "part211.xml"
    canonical.write_text(_XML, encoding="utf-8")
    real_sha = hashlib.sha256(canonical.read_bytes()).hexdigest()

    registry_file = tmp_path / "registry.json"
    registry_file.write_text(json.dumps({
        "sources": [{
            "source_id": "ecfr_21cfr_part211",
            "canonical_path": str(canonical.relative_to(tmp_path / "repo")),
            "sha256_copy": real_sha,
            "derived_artifacts": [],
        }],
    }), encoding="utf-8")

    monkeypatch.setattr(ex, "REPO_ROOT", tmp_path / "repo")
    monkeypatch.setattr(ex, "DERIVED_DIR", tmp_path / "repo" / "sources" / "derived")
    return registry_file, canonical


def test_register_writes_artifact_and_links_it(registry_env):
    registry_file, _ = registry_env
    result = ex.extract_and_register("ecfr_21cfr_part211", registry_file)
    assert result["units"] == 3

    registry = json.loads(registry_file.read_text(encoding="utf-8"))
    artifacts = registry["sources"][0]["derived_artifacts"]
    assert len(artifacts) == 1
    assert artifacts[0]["extractor"] == "ecfr_xml"
    # El loader exige que source_sha256 del derivado == sha256_copy del padre.
    assert artifacts[0]["source_sha256"] == registry["sources"][0]["sha256_copy"]
    assert not artifacts[0]["artifact_path"].startswith("/")


def test_register_aborts_if_canonical_file_no_longer_matches_hash(registry_env):
    """Extraer de un fichero que ya no es el gobernado produciria un derivado
    de algo distinto a la fuente."""
    registry_file, canonical = registry_env
    canonical.write_text("contenido alterado", encoding="utf-8")
    with pytest.raises(ex.EcfrXmlExtractionError, match="ya no coincide"):
        ex.extract_and_register("ecfr_21cfr_part211", registry_file)


def test_register_never_overwrites_an_existing_artifact(registry_env):
    registry_file, _ = registry_env
    ex.extract_and_register("ecfr_21cfr_part211", registry_file)
    with pytest.raises(ex.EcfrXmlExtractionError, match="no se sobrescriben"):
        ex.extract_and_register("ecfr_21cfr_part211", registry_file)


def test_register_rejects_unknown_source(registry_env):
    registry_file, _ = registry_env
    with pytest.raises(ex.EcfrXmlExtractionError, match="no existe"):
        ex.extract_and_register("no_existe", registry_file)


# --- sobre el XML REAL de Part 211 ----------------------------------------

REAL_XML = Path(
    "factory/regulatory/sources/sha256/"
    "ecd9f8ba39e59c7713be98c293f1da4b125a68706d32ce4c77a0b579797423e3/"
    "OFFICIAL_ECFR_21CFR_part211_20260701.xml"
)


def test_real_part211_yields_the_predicate_rule_section_verbatim():
    """La razon de ser de toda la ingesta: 211.68 tiene que quedar anclable
    palabra por palabra, porque es el texto que sostiene NR-01."""
    if not REAL_XML.exists():
        pytest.skip("XML real no disponible en este entorno")
    units = ex.extract_units(REAL_XML)
    section = next(u for u in units if u.startswith("§ 211.68"))
    assert section.startswith("§ 211.68 Automatic, mechanical, and electronic equipment.")
    # Las tres exigencias reales de (b), citadas literalmente del texto oficial.
    assert "instituted only by authorized personnel" in section
    assert "shall be checked for accuracy" in section
    assert "A backup file of data entered into the computer" in section


def test_real_part211_has_no_placeholder_leak():
    if not REAL_XML.exists():
        pytest.skip("XML real no disponible en este entorno")
    assert "_SUBSTITUTE_DATE_" not in "\n".join(ex.extract_units(REAL_XML))
