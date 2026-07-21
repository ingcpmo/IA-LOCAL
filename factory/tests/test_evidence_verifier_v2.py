"""W5 Ciclo 1 (v2), Fase 2, Bloque 2.4 — tests del verificador v2."""
from __future__ import annotations

from factory.regulatory.evidence_verifier import (
    match_citation, relevance_score, verify_llm_output, load_requirement_terms,
)

KNOWN_REQS = {"21_CFR_11.10(d)", "ANNEX11_9"}
CHUNK = {
    "text": "El sistema requiere autenticacion de dos factores para el acceso "
            "de operadores. El audit-trail registra cada evento con timestamp.",
    "page_start": 10, "page_end": 11,
}
AUDIT_TERMS = ["audit", "trail", "log", "event", "timestamp", "record"]


def _base_output(**overrides):
    out = {
        "requirement_id": "ANNEX11_9",
        "chunk_observation": "observed",
        "evidence_quote": "El audit-trail registra cada evento con timestamp.",
        "evidence_page": 10,
        "confidence": 0.85,
        "rationale": "Cita explicita de audit trail.",
        "flags": [],
    }
    out.update(overrides)
    return out


def test_exact_citation_is_verified():
    out = _base_output()
    result = verify_llm_output(out, CHUNK, KNOWN_REQS, AUDIT_TERMS)
    assert result.status == "verified"
    assert result.checks["citation_match_type"] == "exact"


def test_citation_with_spaces_and_dashes_is_normalized_and_verified():
    chunk = dict(CHUNK, text=CHUNK["text"].replace("audit-trail", "audit‐trail  "))
    out = _base_output(evidence_quote="El audit-trail  registra cada evento con timestamp.")
    result = verify_llm_output(out, chunk, KNOWN_REQS, AUDIT_TERMS)
    assert result.status == "verified"
    assert result.checks["citation_match_type"] in ("exact", "normalized")


def test_fuzzy_citation_in_range_is_verified_with_deviation():
    # Cita casi identica (una coma final agregada por el modelo) -> similitud
    # alta (0.9494, verificado con match_citation) pero no exacta/normalizada.
    chunk = dict(CHUNK, text="El sistema requiere autenticacion de dos factores para el "
                              "acceso de operadores. El audit-trail registra cada evento "
                              "con timestamp exacto y preciso segun norma.")
    out = _base_output(evidence_quote="El audit-trail registra cada evento con timestamp "
                                       "exacto y preciso segun norma,")
    result = verify_llm_output(out, chunk, KNOWN_REQS, AUDIT_TERMS)
    assert result.checks["citation_match_type"] == "fuzzy"
    assert result.status == "verified_with_deviation"
    assert "CITATION_DEVIATION" in result.review_flags


def test_low_fuzzy_citation_is_rejected_citation_not_found():
    """Caso tipo C-inventada: cita que no existe en el chunk, ni siquiera
    de forma aproximada."""
    out = _base_output(evidence_quote="El sistema calcula la presion diferencial del autoclave en tiempo real.")
    result = verify_llm_output(out, CHUNK, KNOWN_REQS, AUDIT_TERMS)
    assert result.status == "rejected_by_verifier"
    assert "citation_not_found" in result.rejection_reason
    assert result.checks["citation_match_type"] == "not_found"


def test_real_but_irrelevant_quote_is_review_required_not_rejected():
    """Caso tipo C1/C3 (citas trasladadas): la cita SI existe literalmente
    en el chunk pero no habla del requisito evaluado -- debe quedar en
    revision humana, nunca auto-rechazada ni verificada limpiamente (P6)."""
    chunk = dict(CHUNK, text="La calibracion del sensor de presion se realiza cada 12 meses "
                              "segun el procedimiento SOP-CAL-004.")
    out = _base_output(
        requirement_id="ANNEX11_9",
        evidence_quote="La calibracion del sensor de presion se realiza cada 12 meses "
                       "segun el procedimiento SOP-CAL-004.",
    )
    result = verify_llm_output(out, chunk, KNOWN_REQS, AUDIT_TERMS)
    assert result.checks["citation"] == "PASS"  # la cita SI esta anclada
    assert result.status == "review_required"
    assert "RELEVANCE_REVIEW_REQUIRED" in result.review_flags


def test_not_observed_with_quote_present_is_rejected_incoherence():
    out = _base_output(chunk_observation="not_observed_in_chunk",
                        evidence_quote="El audit-trail registra cada evento.")
    result = verify_llm_output(out, CHUNK, KNOWN_REQS, AUDIT_TERMS)
    assert result.status == "rejected_by_verifier"
    assert "quote_present_on_not_observed" in result.rejection_reason


def test_not_observed_without_quote_is_verified():
    out = _base_output(chunk_observation="not_observed_in_chunk", evidence_quote="",
                        evidence_page=None)
    result = verify_llm_output(out, CHUNK, KNOWN_REQS, AUDIT_TERMS)
    assert result.status == "verified"
    assert result.checks["page"] == "n/a"


def test_missing_page_is_review_required_never_clean_verified():
    out = _base_output(evidence_page=None)
    result = verify_llm_output(out, CHUNK, KNOWN_REQS, AUDIT_TERMS)
    assert result.status == "review_required"
    assert "PAGE_NOT_VERIFIABLE" in result.review_flags


def test_page_out_of_range_is_rejected():
    out = _base_output(evidence_page=999)
    result = verify_llm_output(out, CHUNK, KNOWN_REQS, AUDIT_TERMS)
    assert result.status == "rejected_by_verifier"
    assert "page_out_of_range" in result.rejection_reason


def test_unknown_requirement_is_rejected():
    out = _base_output(requirement_id="NOT_A_REAL_REQ")
    result = verify_llm_output(out, CHUNK, KNOWN_REQS, AUDIT_TERMS)
    assert result.status == "rejected_by_verifier"
    assert "requirement_unknown" in result.rejection_reason


def test_missing_requirement_terms_is_not_verifiable_never_pass_or_reject():
    out = _base_output()
    result = verify_llm_output(out, CHUNK, KNOWN_REQS, requirement_terms=[])
    assert result.checks["relevance"] == "NOT_VERIFIABLE"
    assert "RELEVANCE_NOT_EVALUABLE" in result.review_flags
    assert result.status == "review_required"  # nunca rejected ni verified limpio


def test_match_citation_taxonomy_exact_normalized_fuzzy_not_found():
    src = "The audit trail is enabled by default."
    assert match_citation("The audit trail is enabled by default.", src)[0] == "exact"
    assert match_citation("the   audit trail is enabled by default", src)[0] == "normalized"
    assert match_citation("completely unrelated text about calibration", src)[0] == "not_found"


def test_relevance_score_returns_negative_one_when_not_evaluable():
    assert relevance_score("some quote", []) == -1.0
    assert relevance_score("", ["audit"]) == -1.0


# --- W5.6: chunk 20 real de "215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"
# (chunk_sha256 63cbaa57e7e05278c22f314d1c124c0b57e82e6e4b48c382da85e17a27ff663d,
# run w5v3-validation-46ccbbe29eb3, ETAPA 4) -- congelado tal cual lo extrajo
# pypdf 4.3.1, incluye el membrete de pagina real y el defecto real de
# kerning ("wheneve r"). La cita es la evidence_quote real emitida por el
# modelo (qwen2.5:7b-instruct-q4_K_M) para ALCOA_CONTEMPORANEOUS, que quedo
# rejected_by_verifier/citation_not_found antes de este fix. ---

CHUNK20_TEXT = 'ller B \nSerialization B \nVial Syringe Labeler  B \nParts Washer / Sterilizer  B \nClean Steam Generator B \nWaste Lift and Neutralization  B \nWater for Injection  B \nWeigh / Dispense B \nAlarm Details B \nAlarm Limit Modification (page 1 of 2) E \nAlarm Limit Modification2 (page 2 of 2) E \n3Table 4-2: Security Code Assignments for Graphic Displays \n \n2 Screen access is defined by the first code (least rest rictive), additional codes indicate objects on screen are \nsubject to additional restrictions \n Project: Mark Cuban Cost Plus Drug Company, PBC – \n MCCPDC - SCADA and PCS MISC. PLC System \n \nFunctional Specification for the MCCPDC - SCADA and PCS MISC. PLC System  \n \n \nID code: 215115305 -FS (V1.2) Page 45 of 58 \n© 2022 Rockwell Automation, Inc. All Rights Reserved / Author: Buol, Scott \n5 Data \nF11.00: Databases and Historical Logging \nThis function implements the following user requirement(s)  \nUR3.3.6 Data retentio n time on the system \n1. The system shall have provision for retaining 1 year of historical data locally before it is \narchived in an alternate location for safe keeping.   \nUR5.4.7 [URS-PCS-SR-041] The PLC system shall co mmunicate with a plant historian (collect and \ntransfer data).   \n F11.01: Process Historian \nThis system contains the Rockwell FactoryTalk Historian SE software and server which \nsatisfies the requirement to collect and transfer data. \n F11.02: Critical Data Records \nThis system maintains the following critical runtime data records: \n FactoryTalk View SE alarm log and activity log data are stored in the corresponding \ndatabases as analog, digital and string values.     \n Analog, digital and string device tags that are transferred from the PLC to the \nFactoryTalk View SE system. \nF12.00: Audit Trail \nThis function implements the following user requirement(s)  \nUR3.3.1 Every time a critical alarm threshold is modified and audit trail record shall be generated.  The \nrecord shall contain the following fields  \n1. Date and time stamps of the change \n2. Original threshold value \n3. Threshold value after change \n4. User ID of the individual who has changed the threshold value (performer) \n5. Full name of the individual who has changed the threshold value (performer) \n6. Meaning of signature (performer) \n7. User ID of the individual who has approved the change (approver) \n8. Full name of the individual who has approved the change (approver) \n9. Meaning of signature (approver).  \nUR3.3.2 Every time a critical alarm condition occurs an audit trail record shall be generated with the \nfollowing fields  \n1. Alarm date and time stamps  \n2. Alarm tag 3. Alarm value \n4. Alarm description \n5. A similar record shall be generated wheneve r a critical alarm condition returns to normal \ncondition.  \n\nProject: Mark Cuban Cost Plus Drug Company, PBC – \n MCCPDC - SCADA and PCS MISC. PLC System \n \nFunctional Specification for the MCCPDC - SCADA and PCS MISC. PLC System  \n \n \nID code: 215115305 -FS (V1.2) Page 46 of 58 \n© 2022 Rockwell Automation, Inc. All Rights Reserved / Author: Buol, Scott \nThis function implements the following user requirement(s)  \nUR3.3.3 Audit trail records shall be archived.  \nUR3.3.3 Audit trail records shall be archived.   \nUR5.2.3 [URS-PCS-SR-009] Logins, logouts, and logi n attempts must be recorded in the Audit Trail.   \nUR5.4.2 [URS-PCS-SR-036] All manual interactions  (parameter changes, device mode changes, etc.) \nshall be sent to a database for event logging,  including user name, action and timestamp.   \n \nFactoryTalk View SE provides an electronic signature feature for capturing operator actions \nperformed in the production system.  This feature is  available in an E-Signature control, as well \nas the native button, numeric, and string input objects. \nWith the FactoryTalk View SE electronic signature feature, each entry into the FactoryTalk View \nSE activity log is identified with: \n time and date the action occurred, \n name of the logged-in operator who performed the action, \n terminal the action was performed from, \n type of operation that was performed, and \n value of the changed item before and after the change. \nWhen electronic signatures are used, the operator’s username and full name are also included. \n The Critical Alarm Threshold Change Audit Trail entry will contain the following information: \n Date and time stamps of the change \n Original threshold value \n Threshold value after change \n User ID of the individual who has changed the threshold value (performer) \n Full name of the individual who has changed the threshold value (performer) \n Meaning of signature (performer) \n User ID of the individual who has approved the change (approver) \n Full name of the individual who has approved the change (approver) \n Meaning of signature (approver). \n \nThe Critical Alarm Audit Trail entry will contain the following information: \n Alarm date and time stamps \n Alarm tag \n Alarm value \n Alarm description \n A similar record shall be generated whenever a critical alarm condition returns to \nnormal condition. \n '

CHUNK20_QUOTE = 'UR3.3.1 Every time a critical alarm threshold is modified and audit trail record shall be generated. The record shall contain the following fields\n1. Date and time stamps of the change\n2. Original threshold value\n3. Threshold value after change\n4. User ID of the individual who has changed the threshold value (performer)\n5. Full name of the individual who has changed the threshold value (performer)\n6. Meaning of signature (performer)\n7. User ID of the individual who has approved the change (approver)\n8. Full name of the individual who has approved the change (approver)\n9. Meaning of signature (approver).\nUR3.3.2 Every time a critical alarm condition occurs an audit trail record shall be generated with the following fields\n1. Alarm date and time stamps\n2. Alarm tag 3. Alarm value\n4. Alarm description\n5. A similar record shall be generated whenever a critical alarm condition returns to normal condition.\nUR3.3.3 Audit trail records shall be archived.'


def test_real_chunk20_citation_spanning_page_furniture_is_anchored():
    """Regresion del hallazgo real ETAPA 4: la cita es literal y correcta
    (dos UR reales, sin alterar contenido), pero cruza un membrete de pagina
    Rockwell real (Project/Functional Specification/ID code/copyright) mas
    un defecto real de kerning ("wheneve r"). Antes de W5.6 esto era
    rejected_by_verifier/citation_not_found -- ahora debe anclar (despaced)
    sin necesitar el heuristico fuzzy."""
    mtype, score = match_citation(CHUNK20_QUOTE, CHUNK20_TEXT)
    assert mtype == "despaced"
    assert score == 1.0

    chunk = {"text": CHUNK20_TEXT, "page_start": 45, "page_end": 46}
    llm_output = {
        "requirement_id": "ALCOA_CONTEMPORANEOUS",
        "chunk_observation": "observed",
        "evidence_quote": CHUNK20_QUOTE,
        "evidence_page": 46,
        "confidence": 1.0,
        "rationale": "cita real",
    }
    terms = load_requirement_terms("ALCOA_CONTEMPORANEOUS")
    result = verify_llm_output(llm_output, chunk, {"ALCOA_CONTEMPORANEOUS"}, terms)
    assert result.checks["citation"] == "PASS"
    assert result.checks["citation_match_type"] == "despaced"
    assert result.status != "rejected_by_verifier"
    assert result.rejection_reason != "citation_not_found"


def test_chunk20_altered_quote_still_rejected_not_a_semantic_relaxation():
    """Negativo: una cita que SI cruza el mismo membrete pero con contenido
    sustantivo alterado (numero de campo inventado que no esta en el chunk)
    debe seguir siendo rechazada -- W5.6 no acepta coincidencias amplias,
    solo ignora ruido de formato (espacios/membrete), nunca contenido
    distinto."""
    altered_quote = CHUNK20_QUOTE.replace(
        "9. Meaning of signature (approver).",
        "9. Meaning of signature (approver) and 10. GPS coordinates of the operator.",
    )
    mtype, score = match_citation(altered_quote, CHUNK20_TEXT)
    assert mtype == "not_found"

    chunk = {"text": CHUNK20_TEXT, "page_start": 45, "page_end": 46}
    llm_output = {
        "requirement_id": "ALCOA_CONTEMPORANEOUS",
        "chunk_observation": "observed",
        "evidence_quote": altered_quote,
        "evidence_page": 46,
        "confidence": 1.0,
        "rationale": "cita alterada",
    }
    result = verify_llm_output(llm_output, chunk, {"ALCOA_CONTEMPORANEOUS"}, [])
    assert result.status == "rejected_by_verifier"
    assert "citation_not_found" in result.rejection_reason


def test_chunk20_quote_fabricated_from_different_chunk_still_rejected():
    """Negativo: una cita real de OTRO documento/seccion (no presente en
    absoluto en este chunk) debe seguir siendo not_found -- el fix de
    membrete/despaciado no vuelve el anclaje mas permisivo con contenido
    ausente."""
    fabricated = "The autoclave differential pressure is calculated in real time by the SCADA historian."
    assert match_citation(fabricated, CHUNK20_TEXT)[0] == "not_found"


def test_page_furniture_is_stripped_before_matching():
    """La cita real que rodea el punto exacto de corte del membrete (justo
    antes de 'Project:' y justo despues de 'This function implements...')
    debe anclar una vez removido el membrete -- confirma que
    _strip_page_furniture actua y no solo el despaciado."""
    quote = ("A similar record shall be generated whenever a critical alarm "
             "condition returns to normal condition.\nUR3.3.3 Audit trail "
             "records shall be archived.")
    mtype, _ = match_citation(quote, CHUNK20_TEXT)
    assert mtype in ("normalized", "despaced")
