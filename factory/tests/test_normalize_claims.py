"""Tests -- factory/regulatory/canonical/normalize_claims.py (V2, B1).

docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md FASE 2.4:
heurística léxica, sin LLM. `Claim.source_text` se preserva LITERAL (es
la única cita citable); `normalized_statement` limpia formato pero NUNCA
reescribe, infiere ni añade/quita vocabulario del cuerpo de la frase.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.canonical import normalize_claims as nc


def test_normalize_statement_is_format_only():
    src = "  Note that   the   system  shall   generate an audit trail record.  "
    out = nc.normalize_statement(src)
    # colapsó espacios y quitó la muletilla inicial "Note that"
    assert out == "the system shall generate an audit trail record."
    # no inventó palabras: cada palabra del output (sin puntuación) está en el input
    import string
    strip = lambda w: w.strip(string.punctuation)
    src_words = {strip(w) for w in src.lower().split()}
    for w in out.lower().split():
        assert strip(w) in src_words


def test_normalize_does_not_translate_or_paraphrase():
    src = "El sistema restringe el acceso a personal autorizado con credenciales vigentes."
    out = nc.normalize_statement(src)
    assert out == src.strip()          # ya estaba limpio -> intacto
    assert "restringe" in out          # no se traduce a inglés
    assert "authorized" not in out.lower()


def test_source_text_preserved_byte_for_byte():
    section = (
        "1 Introduction\n"
        "The system shall generate an audit trail record for every change "
        "to a critical alarm threshold, including the operator identity, "
        "date, time, previous value and new value.\n"
        "F12.00: Audit Trail .............................................. 45\n"
    )
    claims = nc.extract_claims_for_section("RW-0005", 45, section,
                                           section_numero="1", section_titulo="Introduction")
    assert claims, "debería extraer al menos un claim sustantivo"
    audit_claim = next(c for c in claims if "audit trail record" in c.source_text)
    # el literal se conserva exactamente como venía en la sección
    assert "operator identity, date, time, previous value and new value" in audit_claim.source_text
    # source_hash corresponde al literal (no al normalizado)
    import hashlib
    assert audit_claim.source_hash == hashlib.sha256(audit_claim.source_text.encode("utf-8")).hexdigest()
    # la línea de tabla de contenido NO produce claim
    assert not any(".............." in c.source_text for c in claims)


def test_toc_and_furniture_lines_filtered():
    section = (
        "Page 3 of 58\n"
        "© 2022 Rockwell Automation, Inc. All Rights Reserved\n"
        "5 Data .......................................................... 45\n"
        "The operator must authenticate with a unique credential before "
        "performing any regulated operation.\n"
    )
    claims = nc.extract_claims_for_section("RW-0005", 39, section)
    assert len(claims) == 1
    assert "authenticate with a unique credential" in claims[0].source_text
    assert claims[0].tipo in ("control", "actor_action")


def test_classification_hints():
    assert nc._classify("The system shall restrict access to authorized personnel.") == "control"
    assert nc._classify("This function displays the current alarm status on the HMI.") == "function"
    assert nc._classify("Test case SAT-039: verify that the alarm triggers at setpoint.") == "test"
    assert nc._classify("The high alarm threshold shall be set to 120 psi.") == "parameter"


def test_dedup_within_section():
    section = ("The system shall log all changes.\n"
               "The system shall log all changes.\n"
               "A different substantive statement about backup and recovery procedures.\n")
    claims = nc.extract_claims_for_section("RW-0005", 10, section)
    texts = [c.normalized_statement.lower() for c in claims]
    assert len(texts) == len(set(texts))    # sin duplicados
    assert len(claims) == 2
