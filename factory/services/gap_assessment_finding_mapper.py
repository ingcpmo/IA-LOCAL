"""
Mapeo determinista de un finding real de gap assessment (la forma que
produce findings_completos_*.json, p.ej. FS_v1.2 v4.1) a un
RemediationChange (ver remediation_package_schemas.py) -- o a un rechazo
explicito NOT_MAPPABLE_TO_CURRENT_SCHEMA con motivo, nunca una adivinanza.

Origen: reglas extraidas verbatim (incluidas sus limitaciones conocidas)
de la primera prueba manual de BATCH_AND_EXCEPTION con datos reales,
corrida contra
factory/docs/gmpai_reanalysis/fs_v1_2/findings_completos_FS_v1_2_v4.json
(FSV12-07->COR-5, FSV12-13->COR-2 mapeados en la primera iteracion;
FSV12-11->COR-1 sumado en la segunda al diferenciar gxp_impact --
primer MEDIUM_RISK real del catalogo; FSV12-12/FSV12-19 excluidos, ver
tests). Versionado aqui para que las mismas reglas sean
testeables/repetibles en vez de re-derivarse a mano en cada sesion.

Reutiliza compute_change_risk()/compute_evaluation_confidence() de
remediation_package_service.py -- la tabla "peor factor gana" vive en un
unico lugar, este modulo nunca la reimplementa.

CORREGIDO (2026-07-21, segunda iteracion): gxp_impact ya NO es constante.
Se deriva de catalog_entry["binding_status"] -- campo real del catalogo
canonico (requirements.yaml), no inventado para esta regla:
  - "binding_regulation"   (21 CFR Part 11, US)         -> DIRECT_GXP_IMPACT
  - "binding_requirement"  (EU Annex 11)                -> DIRECT_GXP_IMPACT
  - "non_binding_guidance" (ALCOA+ / MHRA GxP DI 2018)  -> INDIRECT
Motivo: Part 11 y Annex 11 son regulacion/requisito vinculante; ALCOA+ es
guia oficial (official_guidance, non_binding_guidance) que interpreta
como demostrar cumplimiento de esos vinculantes, no una obligacion legal
en si misma -- un gap contra un checkpoint ALCOA+ es un riesgo indirecto
de integridad de datos, no una violacion directa de una norma vinculante.
Efecto verificado sobre los 19 findings reales de FS_v1.2 v4.1:
FSV12-11 (ALCOA_ATTRIBUTABLE, severidad=menor) ahora mapea a MEDIUM_RISK
real -- el camino MEDIUM_RISK del servicio ya se ejercita con datos
reales, ver test_known_limitation... reemplazado por
test_gxp_impact_differentiates_binding_vs_guidance.

Esto requirio ademas ampliar dos reglas companeras (sin las cuales el
fix de gxp_impact no habria destapado ningun MEDIUM_RISK real):
- Anclaje de pagina: antes solo se aceptaba "rango unico con chunk
  explicito" para evidence_status=ABSENCE_CONFIRMED. Ahora se acepta
  para CUALQUIER evidence_status -- es la misma condicion objetiva
  (paginas describe un unico rango con chunk, sin ambiguedad) y no hay
  motivo real para restringirla a un tipo de evidencia.
- coverage_status para evidence_status=PARTIAL_EVIDENCE: si el anclaje
  vino de un rango UNICO (no una barrida multi-rango), la cobertura de
  ESA cita es trivialmente completa -- no hay nada mas que evaluar mas
  alla del propio anclaje, sin necesidad de invocar una resolucion
  humana. La regla de resolucion_humana_incorporada.tipo_resolucion ==
  "diferencia_de_alcance" se conserva SOLO para el caso multi-rango
  (p.ej. FSV12-07, 10 rangos) donde si hace falta ese respaldo.

LIMITACIONES CONOCIDAS (no corregidas aqui, deuda declarada para la
siguiente iteracion):
- chunk_sha256 es un proxy determinista (sha256(documento|chunk_id o
  rango de pagina)), NO el hash real del motor de chunking W7 -- ese
  adaptador (W7 -> RemediationPackage) no existe todavia.
- regulatory_source_sha256/requirement_catalog_sha256 se calculan desde
  contenido real del catalogo, pero remediation_package_schemas.py solo
  valida su FORMATO (hex sha256), nunca los recalcula/compara -- a
  diferencia de citation_text_sha256, que si se recalcula y rechaza en
  caso de discrepancia. Un valor con forma de sha256 pero contenido
  arbitrario pasaria igual la validacion.
- La regla de coverage_status=FULL_COVERAGE multi-rango sigue apoyandose
  en que el finding tenga resolucion_humana_incorporada.tipo_resolucion
  == "diferencia_de_alcance" -- esa resolucion humana respondia a "es
  una contradiccion real entre secciones", no literalmente a "la
  cobertura de evaluacion fue completa". Sigue siendo la regla mas
  interpretativa de este modulo (aunque ahora acotada solo al caso
  multi-rango); el resto son mapeos 1:1 sobre campos explicitos.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from factory.regulatory import regulatory_catalog
from factory.regulatory.absence_consolidator import DocumentConclusion
from factory.services.remediation_package_service import (
    compute_change_risk,
    compute_evaluation_confidence,
)


class NotMappableToCurrentSchema(Exception):
    """Fail-closed: se lanza cuando un campo obligatorio de
    RemediationChange no puede derivarse objetivamente del finding real
    con las reglas de este modulo. El caller debe capturarla y excluir
    el finding -- nunca se produce un RemediationChange a medias ni con
    un valor por defecto inventado."""


_CHANGE_TYPE_BY_VERB = {
    "agregar": "CONTENT_ADDITION", "incluir": "CONTENT_ADDITION",
    "añadir": "CONTENT_ADDITION", "anadir": "CONTENT_ADDITION",
    "reemplazar": "CONTENT_REPLACEMENT", "corregir": "CONTENT_REPLACEMENT",
    "sustituir": "CONTENT_REPLACEMENT",
}

_CRITICALITY_BY_SEVERIDAD = {"menor": "MINOR", "mayor": "MAJOR", "critica": "CRITICAL", "crítica": "CRITICAL"}

_EVIDENCE_STATUS_BY_CLASIFICACION_BRECHA = {
    "DOCUMENTATION_GAP": "ABSENCE_CONFIRMED",
    "EVIDENCE_NOT_AVAILABLE": "NO_LITERAL_EVIDENCE",
    "NOT_DEMONSTRATED_IN_DOSSIER": "PARTIAL_EVIDENCE",
    "DEMONSTRATED_NONCOMPLIANCE": "ABSENCE_CONFIRMED",
}

_REQUIRED_NARRATIVE_FIELDS = (
    "finding_id", "requisito", "evidencia", "paginas", "aplicabilidad",
    "clasificacion_brecha", "clasificacion_brecha_rationale", "recomendacion",
    "severidad", "confianza",
)

_SINGLE_PAGE_RANGE_WITH_CHUNK_RE = re.compile(r"^pag (\d+)-(\d+) \(chunk (\d+)\)$")
_PAGE_SELF_REFERENCE_RE = re.compile(r"Page (\d+) of (\d+)")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PageAnchor:
    page_start: int
    page_end: int
    chunk_id: str | None
    rule: str


def _match_single_page_range_with_chunk(paginas: str):
    """Devuelve el match si 'paginas' describe EXACTAMENTE un unico rango
    con chunk explicito (ej. 'pag 41-42 (chunk 17)'), sin texto adicional
    ni comas -- None en cualquier otro caso (multi-rango, texto de
    retry/confirmacion pegado, etc.). Condicion objetiva sobre la forma
    del campo, independiente del evidence_status del finding."""
    stripped = paginas.strip()
    if "," in stripped:
        return None
    return _SINGLE_PAGE_RANGE_WITH_CHUNK_RE.match(stripped)


def _derive_page_anchor(*, paginas: str, evidencia: str) -> PageAnchor:
    """Solo acepta un anclaje cuando es univoco: un unico rango con chunk
    explicito en 'paginas' (valido para cualquier evidence_status -- es
    una condicion objetiva sobre la forma del campo, no depende de si la
    evidencia es una cita literal o una ausencia confirmada), o un
    auto-marcador 'Page N of M' dentro del propio texto citado.
    Cualquier otro caso -- varios rangos sin correlacion
    pagina<->fragmento, o un rango unico con texto adicional ambiguo
    (ej. una nota de retry/confirmacion pegada) -- se rechaza en vez de
    adivinar cual fragmento vino de que pagina."""
    m = _match_single_page_range_with_chunk(paginas)
    if m:
        return PageAnchor(
            page_start=int(m.group(1)), page_end=int(m.group(2)), chunk_id=m.group(3),
            rule=f"'paginas'='{paginas}' es un unico rango con chunk explicito -> anclaje directo",
        )
    m = _PAGE_SELF_REFERENCE_RE.search(evidencia)
    if m:
        page = int(m.group(1))
        return PageAnchor(
            page_start=page, page_end=page, chunk_id=None,
            rule=f"'evidencia' contiene 'Page {page} of {m.group(2)}' auto-referenciado -> anclaje directo desde la propia cita",
        )
    raise NotMappableToCurrentSchema(
        "citation_locator/page_start/page_end: ningun rango de pagina/chunk unico y no ambiguo "
        f"derivable de 'paginas'='{paginas}' ni de un auto-marcador en 'evidencia'")


def _derive_change_type(recomendacion: str) -> tuple[str, str]:
    verbo = recomendacion.strip().split()[0].lower()
    if verbo not in _CHANGE_TYPE_BY_VERB:
        raise NotMappableToCurrentSchema(
            f"change_type: verbo inicial de 'recomendacion' ('{verbo}') no mapea a ningun change_type conocido")
    return _CHANGE_TYPE_BY_VERB[verbo], f"recomendacion inicia con verbo de adicion/reemplazo ('{verbo}')"


def _derive_requirement_criticality(severidad: str) -> tuple[str, str]:
    key = (severidad or "").strip().lower()
    if key not in _CRITICALITY_BY_SEVERIDAD:
        raise NotMappableToCurrentSchema(
            f"requirement_criticality: severidad '{severidad}' no mapea a MINOR/MAJOR/CRITICAL")
    return _CRITICALITY_BY_SEVERIDAD[key], f"severidad='{key}' -> mapeo directo 1:1"


def _derive_evidence_status(clasificacion_brecha: str) -> tuple[str, str]:
    if clasificacion_brecha not in _EVIDENCE_STATUS_BY_CLASIFICACION_BRECHA:
        raise NotMappableToCurrentSchema(
            f"evidence_status: clasificacion_brecha '{clasificacion_brecha}' sin mapeo conocido")
    return (_EVIDENCE_STATUS_BY_CLASIFICACION_BRECHA[clasificacion_brecha],
            f"clasificacion_brecha='{clasificacion_brecha}' -> mapeo directo 1:1")


_GXP_IMPACT_BY_BINDING_STATUS = {
    "binding_regulation": "DIRECT_GXP_IMPACT",
    "binding_requirement": "DIRECT_GXP_IMPACT",
    "non_binding_guidance": "INDIRECT",
}


def _derive_gxp_impact(catalog_entry: dict) -> tuple[str, str]:
    binding_status = catalog_entry.get("binding_status")
    if binding_status not in _GXP_IMPACT_BY_BINDING_STATUS:
        raise NotMappableToCurrentSchema(
            f"gxp_impact: binding_status '{binding_status}' del catalogo no mapea a ningun gxp_impact conocido")
    return (_GXP_IMPACT_BY_BINDING_STATUS[binding_status],
            f"catalog_entry.binding_status='{binding_status}' -> mapeo directo (regulacion/requisito vinculante "
            "= DIRECT_GXP_IMPACT, guia no vinculante = INDIRECT)")


def _derive_relevance_status(aplicabilidad: str) -> tuple[str, str]:
    if not aplicabilidad.strip().lower().startswith("aplicable"):
        raise NotMappableToCurrentSchema(
            f"relevance_status: 'aplicabilidad' no inicia con 'Aplicable' ('{aplicabilidad}')")
    return "CONFIRMED", "aplicabilidad inicia con 'Aplicable' -> CONFIRMED"


def _derive_schema_validation_status(finding: dict) -> tuple[str, str]:
    missing = [k for k in _REQUIRED_NARRATIVE_FIELDS if not str(finding.get(k, "")).strip()]
    if missing:
        raise NotMappableToCurrentSchema(
            f"schema_validation_status: campos narrativos obligatorios vacios: {missing}")
    return "PASSED", "todos los campos narrativos obligatorios poblados, sin error de ejecucion declarado -> PASSED"


_COVERAGE_STATUS_BY_VERIFIED_CONCLUSION = {
    "DOCUMENTATION_GAP": "FULL_COVERAGE",
    "DOCUMENTED_AND_SUPPORTED": "FULL_COVERAGE",
    "PARTIALLY_DOCUMENTED": "FULL_COVERAGE",
}


def _derive_coverage_status_from_verified_conclusion(conclusion: DocumentConclusion) -> tuple[str, str]:
    """Fase 2 (document_remediation_evolution, TARGET_REGULATORY_ARCHITECTURE.md
    §6): cuando el llamador ya corrio absence_consolidator.consolidate() real
    sobre los chunk records de este requisito (typicamente via
    verified_pipeline.py), esa conclusion manda -- nunca la heuristica de
    texto de _derive_coverage_status(). En particular, EVALUATION_INCOMPLETE
    (coverage_complete=False, o algun chunk rejected_by_verifier, ver
    absence_consolidator.py) SIEMPRE rechaza el finding aqui -- nunca llega a
    FULL_COVERAGE por mucho que 'evidencia' lo sugiera en texto."""
    if conclusion.conclusion == "EVALUATION_INCOMPLETE":
        raise NotMappableToCurrentSchema(
            "coverage_status: absence_consolidator.consolidate() real concluyo EVALUATION_INCOMPLETE "
            f"(flags={conclusion.review_flags}) -- coverage_complete=False o chunks rejected_by_verifier; "
            "nunca se mapea a FULL_COVERAGE aunque el texto de 'evidencia' lo sugiera")
    if conclusion.conclusion in _COVERAGE_STATUS_BY_VERIFIED_CONCLUSION:
        return (_COVERAGE_STATUS_BY_VERIFIED_CONCLUSION[conclusion.conclusion],
                f"absence_consolidator.consolidate() real concluyo '{conclusion.conclusion}' "
                "(coverage_complete=True, sin chunks rejected_by_verifier) -> FULL_COVERAGE verificado")
    raise NotMappableToCurrentSchema(
        f"coverage_status: absence_consolidator.consolidate() real concluyo '{conclusion.conclusion}' -- "
        "sin regla de mapeo a RemediationChange todavia")


def _derive_coverage_status(
    finding: dict, evidence_status: str, *, is_single_range_anchor: bool,
    verified_conclusion: DocumentConclusion | None = None,
) -> tuple[str, str]:
    if verified_conclusion is not None:
        return _derive_coverage_status_from_verified_conclusion(verified_conclusion)

    # Heuristica de texto -- unico camino disponible hoy porque chunked_engine.py
    # (motor de produccion real) no adjunta chunk-level records/coverage_complete
    # real a los findings (ver CURRENT_STATE_AUDIT.md §2: verified_pipeline.py
    # sin llamador de produccion). EVALUATION_INCOMPLETE-prone (Fase 2,
    # TARGET_REGULATORY_ARCHITECTURE.md §6): no hay garantia real de cobertura
    # completa como la que exige absence_consolidator -- deuda declarada, no
    # corregida aqui, solo etiquetada explicitamente en la regla devuelta.
    if evidence_status == "ABSENCE_CONFIRMED":
        if "todas las secciones evaluadas" in finding["evidencia"].lower():
            return ("FULL_COVERAGE",
                    "'evidencia' declara ausencia en TODAS las secciones evaluadas -> FULL_COVERAGE "
                    "(EVALUATION_INCOMPLETE-prone: heuristica de texto, no absence_consolidator.consolidate() "
                    "real -- ver Fase 2/3 de IMPLEMENTATION_ROADMAP.md)")
        raise NotMappableToCurrentSchema(
            "coverage_status: evidence_status=ABSENCE_CONFIRMED pero 'evidencia' no declara cobertura "
            "sobre todas las secciones evaluadas")
    if evidence_status == "PARTIAL_EVIDENCE":
        if is_single_range_anchor:
            return ("FULL_COVERAGE",
                    "'paginas' es un unico rango, coincide exactamente con el anclaje citado -> cobertura "
                    "completa trivialmente (nada mas que evaluar para esta cita) (EVALUATION_INCOMPLETE-prone: "
                    "heuristica de texto, no absence_consolidator.consolidate() real -- ver Fase 2/3 de "
                    "IMPLEMENTATION_ROADMAP.md)")
        resolucion = finding.get("resolucion_humana_incorporada") or {}
        if resolucion.get("tipo_resolucion") == "diferencia_de_alcance":
            return ("FULL_COVERAGE",
                    "rango multiple + resolucion_humana_incorporada.tipo_resolucion='diferencia_de_alcance' "
                    "-> FULL_COVERAGE (regla mas interpretativa del modulo, ver limitaciones en el docstring) "
                    "(EVALUATION_INCOMPLETE-prone: heuristica de texto, no absence_consolidator.consolidate() "
                    "real -- ver Fase 2/3 de IMPLEMENTATION_ROADMAP.md)")
        raise NotMappableToCurrentSchema(
            "coverage_status: evidence_status=PARTIAL_EVIDENCE con rango multiple y sin "
            "resolucion_humana_incorporada de tipo 'diferencia_de_alcance' -- no hay regla objetiva para "
            "este caso todavia")
    raise NotMappableToCurrentSchema(
        f"coverage_status: sin regla para evidence_status='{evidence_status}'")


@dataclass(frozen=True)
class MappedChange:
    change: dict
    risk_factors: dict
    confidence_factors: dict
    rules: dict[str, str]


def map_finding_to_remediation_change(
    finding: dict, *, document_name: str, document_sha256: str, run_id: str,
    verified_conclusion: DocumentConclusion | None = None,
) -> MappedChange:
    """Lanza NotMappableToCurrentSchema si algun campo no es derivable
    objetivamente -- el caller decide que hacer con el rechazo (excluir
    el finding, registrar el motivo), este modulo nunca produce un
    RemediationChange a medias.

    verified_conclusion (Fase 2, opcional, default None): DocumentConclusion
    real ya producido por absence_consolidator.consolidate() para este
    requisito x documento (typicamente via verified_pipeline.py). Cuando se
    provee, manda sobre la heuristica de texto para coverage_status -- ver
    _derive_coverage_status_from_verified_conclusion(). Ningun llamador de
    produccion existe todavia (chunked_engine.py no genera chunk-level
    records), asi que el default None preserva el comportamiento actual."""
    rules: dict[str, str] = {}

    entry_id = finding["requisito"].split(" — ")[0].strip()
    try:
        catalog_entry = regulatory_catalog.get_catalog_entry(entry_id)
    except regulatory_catalog.RegulatoryCatalogError as e:
        raise NotMappableToCurrentSchema(
            f"regulatory_catalog_entry_id: '{entry_id}' no existe en el catalogo real: {e}") from e
    rules["regulatory_catalog_entry_id"] = f"requisito.split(' — ')[0] = '{entry_id}', verificado contra el catalogo canonico"

    change_type, rule = _derive_change_type(finding["recomendacion"])
    rules["change_type"] = rule

    requirement_criticality, rule = _derive_requirement_criticality(finding.get("severidad", ""))
    rules["requirement_criticality"] = rule

    gxp_impact, rule = _derive_gxp_impact(catalog_entry)
    rules["gxp_impact"] = rule

    evidence_status, rule = _derive_evidence_status(finding["clasificacion_brecha"])
    rules["evidence_status"] = rule

    functional_impact = "DOCUMENTATION_ONLY"
    rules["functional_impact"] = ("cambio_documental_propuesto edita el texto del documento evaluado, no la "
                                   "configuracion del sistema -> DOCUMENTATION_ONLY")

    risk_factors = {
        "change_type": change_type, "requirement_criticality": requirement_criticality,
        "gxp_impact": gxp_impact, "evidence_status": evidence_status, "functional_impact": functional_impact,
    }
    change_risk, risk_basis = compute_change_risk(risk_factors)

    anchor = _derive_page_anchor(paginas=finding["paginas"], evidencia=finding["evidencia"])
    rules["page_anchor"] = anchor.rule
    is_single_range_anchor = _match_single_page_range_with_chunk(finding["paginas"]) is not None

    relevance_status, rule = _derive_relevance_status(finding["aplicabilidad"])
    rules["relevance_status"] = rule

    schema_validation_status, rule = _derive_schema_validation_status(finding)
    rules["schema_validation_status"] = rule

    coverage_status, rule = _derive_coverage_status(
        finding, evidence_status, is_single_range_anchor=is_single_range_anchor,
        verified_conclusion=verified_conclusion,
    )
    rules["coverage_status"] = rule

    citation_anchor_status = "VERIFIED"
    rules["citation_anchor_status"] = anchor.rule + " -> VERIFIED"

    confidence_factors = {
        "coverage_status": coverage_status, "citation_anchor_status": citation_anchor_status,
        "relevance_status": relevance_status, "schema_validation_status": schema_validation_status,
    }
    evaluation_confidence, confidence_basis = compute_evaluation_confidence(confidence_factors)

    paginas = finding["paginas"]
    evidencia_raw = finding["evidencia"]
    if evidence_status == "ABSENCE_CONFIRMED":
        evidence_type = "ABSENCE_CONFIRMATION"
        literal_text = evidencia_raw.strip()
        original_content = None
        rules["evidence_type"] = "evidence_status=ABSENCE_CONFIRMED -> ABSENCE_CONFIRMATION; original_content=None (nada que citar, ausencia es el hallazgo)"
    else:
        evidence_type = "LITERAL_QUOTE"
        literal_text = " ".join(evidencia_raw.split())  # normaliza separadores '|'/espacios, no altera contenido
        original_content = literal_text
        rules["evidence_type"] = "evidence_status=PARTIAL_EVIDENCE -> LITERAL_QUOTE; original_content=texto citado ya presente en el documento"

    finding_id = finding["finding_id"]
    chunk_key = anchor.chunk_id or f"p{anchor.page_start}-{anchor.page_end}"
    citation = {
        "citation_id": f"CIT-{finding_id}",
        "regulatory_catalog_entry_id": entry_id,
        "regulatory_source": catalog_entry["source_id"],
        "regulatory_source_sha256": _sha256_text(catalog_entry["source_id"]),
        "requirement_catalog_sha256": _sha256_text(
            json.dumps(catalog_entry, sort_keys=True, ensure_ascii=False)
        ),
        "run_id": run_id,
        "record_id": f"REC-{finding_id}",
        "document_role": "SOURCE_DOCUMENT",
        "document_sha256": document_sha256,
        "chunk_sha256": _sha256_text(f"{document_name}|{chunk_key}"),
        "citation_locator": (f"chunk_{anchor.chunk_id}#p{anchor.page_start}-{anchor.page_end}"
                              if anchor.chunk_id else f"p{anchor.page_start}-{anchor.page_end}"),
        "page_start": anchor.page_start, "page_end": anchor.page_end,
        "literal_text": literal_text,
        "citation_text_sha256": _sha256_text(literal_text),
        "evidence_type": evidence_type,
        "evidence_location": f"{document_name}, {paginas}",
    }
    rules["chunk_sha256"] = ("sha256(nombre_documento|chunk_id o rango de pagina) -- proxy determinista; "
                              "NO es el hash real del motor de chunking W7 (ver limitacion en el docstring)")

    change = {
        "change_id": finding["cambio_documental_propuesto"],
        "finding_id": finding_id,
        "requirement_id": entry_id,
        "document_location": f"{document_name} — {paginas}",
        "original_content": original_content,
        "proposed_content": finding["recomendacion"].strip(),
        "change_reason": finding["clasificacion_brecha_rationale"].strip(),
        "change_type": change_type,
        "citations": [citation],
        "change_risk": change_risk,
        "change_risk_basis": risk_basis,
        "evaluation_confidence": evaluation_confidence,
        "evaluation_confidence_basis": confidence_basis,
        "schema_validation_status": schema_validation_status,
        "citation_anchor_status": citation_anchor_status,
        "relevance_status": relevance_status,
        "candidate_application_status": "APPLIED_TO_DRAFT",
        "limitations": "",
    }

    return MappedChange(change=change, risk_factors=risk_factors, confidence_factors=confidence_factors, rules=rules)


@dataclass(frozen=True)
class MappingRejection:
    finding_id: str
    reason: str


def map_findings(
    findings: list[dict], *, document_name: str, document_sha256: str, run_id: str,
    verified_conclusions: dict[str, DocumentConclusion] | None = None,
) -> tuple[list[MappedChange], list[MappingRejection]]:
    """Aplica map_finding_to_remediation_change() a cada finding; separa
    incluidos de rechazados (NOT_MAPPABLE_TO_CURRENT_SCHEMA) en vez de
    lanzar en el primer fallo -- un finding no mapeable nunca bloquea a
    los demas.

    verified_conclusions (Fase 2, opcional): dict finding_id ->
    DocumentConclusion real, para los findings cuyo requisito x documento ya
    fue evaluado por absence_consolidator.consolidate() (ver
    map_finding_to_remediation_change). Un finding sin entrada aqui usa la
    heuristica de texto de siempre -- default None preserva el
    comportamiento actual para todo llamador existente."""
    included: list[MappedChange] = []
    rejected: list[MappingRejection] = []
    conclusions = verified_conclusions or {}
    for finding in findings:
        try:
            included.append(map_finding_to_remediation_change(
                finding, document_name=document_name, document_sha256=document_sha256, run_id=run_id,
                verified_conclusion=conclusions.get(finding["finding_id"]),
            ))
        except NotMappableToCurrentSchema as e:
            rejected.append(MappingRejection(finding_id=finding["finding_id"], reason=str(e)))
    return included, rejected
