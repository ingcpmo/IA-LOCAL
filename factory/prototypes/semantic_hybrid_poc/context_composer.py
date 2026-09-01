"""Compositor de contexto (R9) -- ejecutado por CODIGO, no por el modelo.
Lee el store canonico REAL en SOLO LECTURA. FASE 2, aislado."""
from __future__ import annotations

from pathlib import Path

from factory.regulatory.canonical.persistence import CanonicalStore

CANON_DIR = Path("factory/regulatory/canonical_store")

# required_elements por regla -- FIJADOS AQUI (no los genera el modelo, R6).
# Derivados del REQUIRED_BEHAVIOR de technical_completeness_rules v1.2 y de Palanca C.
REQUIRED_ELEMENTS: dict[str, list[dict]] = {
    "AUTHORITY_CHECK_GAP": [
        {"element_id": "ac1", "description": "un chequeo de autoridad EJECUTADO POR EL SISTEMA (no solo control administrativo)"},
        {"element_id": "ac2", "description": "el chequeo ocurre EN EL MOMENTO de ejecutar la operacion (no solo en el login)"},
        {"element_id": "ac3", "description": "aplica a CADA operacion aplicable"},
    ],
    "ACCESS_CONTROL_GAP": [
        {"element_id": "cc1", "description": "se describe el NIVEL DE AUTORIZACION requerido"},
        {"element_id": "cc2", "description": "por CADA operacion/funcion aplicable del sistema"},
    ],
    "BACKUP_RECOVERY_GAP": [
        {"element_id": "br1", "description": "se realizan backups REGULARES"},
        {"element_id": "br2", "description": "se VERIFICA la capacidad de RESTAURAR durante la validacion"},
        {"element_id": "br3", "description": "la verificacion de restauracion se repite PERIODICAMENTE"},
    ],
    "AUDIT_TRAIL_DESIGN_GAP": [
        {"element_id": "ad1", "description": "control de acceso PRIVILEGIADO sobre el propio audit trail"},
        {"element_id": "ad2", "description": "un mecanismo que IMPIDE o HACE DETECTABLE la modificacion/borrado de sus entradas"},
    ],
    "AUDIT_TRAIL_INTEGRITY_GAP": [
        {"element_id": "ai1", "description": "una alteracion NO AUTORIZADA de los registros de auditoria es DETECTABLE (por cualquier medio)"},
    ],
    "ALCOA_ATTRIBUTABLE_GAP": [
        {"element_id": "at1", "description": "toda accion humana registrada se atribuye a una identidad INDIVIDUAL Y UNICA"},
        {"element_id": "at2", "description": "sostenida por un MECANISMO TECNICO (no un campo de texto libre)"},
    ],
    "REGULATORY_INCONCLUSIVE": [
        {"element_id": "ri1", "description": "el documento describe el comportamiento del sub-criterio regulatorio citado con evidencia concreta (no solo menciona el tema)"},
    ],
    "REQUIREMENT_NOT_TESTED": [
        {"element_id": "rt1", "description": "el documento describe o referencia una PRUEBA/verificacion para este requisito"},
    ],
}

# intencion regulatoria por regla (texto para el prompt)
REG_INTENT = {
    "AUTHORITY_CHECK_GAP": "21 CFR 11.10(g): el sistema verifica tecnicamente la autoridad del usuario en el momento de ejecutar cada operacion aplicable, no solo en el login.",
    "ACCESS_CONTROL_GAP": "21 CFR 11.10(g): cada operacion aplicable del sistema tiene un nivel de autorizacion definido (en cualquier forma: prosa, lista, tabla).",
    "BACKUP_RECOVERY_GAP": "EU GMP Annex 11 Section 7.2: hay backups regulares Y se verifica la capacidad de restaurar los datos durante validacion y periodicamente.",
    "AUDIT_TRAIL_DESIGN_GAP": "21 CFR 11.10(e): existe control de acceso privilegiado sobre el audit trail y un mecanismo que impide o hace detectable la modificacion/borrado de sus entradas.",
    "AUDIT_TRAIL_INTEGRITY_GAP": "21 CFR 11.10(e): una alteracion no autorizada de los registros de auditoria es detectable por cualquier medio.",
    "ALCOA_ATTRIBUTABLE_GAP": "ALCOA Attributable + 21 CFR 11.10(d): cada dato de accion humana es atribuible a un individuo unico mediante un mecanismo tecnico.",
    "REGULATORY_INCONCLUSIVE": "El sub-criterio regulatorio citado exige que el documento describa el comportamiento con evidencia anclada; mencionar el tema no basta.",
    "REQUIREMENT_NOT_TESTED": "Todo requisito con implementacion aguas abajo debe tener una prueba/verificacion trazable.",
}


def _claims(store: CanonicalStore) -> list[dict]:
    try:
        return store.all("claim")
    except Exception:  # noqa: BLE001
        return []


def compose(finding: dict) -> dict:
    """Contexto para un finding. Devuelve dict con scope_texts (por section_id),
    section_local_text, neighbor_texts, y metadatos. NO llama a ningun modelo,
    NO ejecuta retrieval cross-seccion en el POC (se marca NOT_EVALUATED, R9)."""
    doc = finding["document"]
    sec_id = finding.get("section")
    with CanonicalStore(doc, store_dir=CANON_DIR) as s:
        claims = _claims(s)
        sections = {row["section_id"]: row for row in s.all("section")} if claims else {}

    # scope local: todos los claims de la seccion del finding
    local = [c for c in claims if c.get("section_id") == sec_id] if sec_id else []
    local.sort(key=lambda c: (c.get("pagina") or 0, c.get("claim_id") or ""))
    local_text = "\n".join(c.get("source_text") or "" for c in local)

    # secciones vecinas: mismo prefijo de numero + padre inmediato
    scope_texts: dict[str, str] = {}
    if sec_id:
        scope_texts[sec_id] = local_text
    anchor_num = (sections.get(sec_id) or {}).get("numero") if sec_id else None
    neighbor_ids = []
    if anchor_num:
        parent = anchor_num.rsplit(".", 1)[0] if "." in anchor_num else None
        for sid, row in sections.items():
            num = row.get("numero") or ""
            if sid == sec_id:
                continue
            if num == anchor_num or num.startswith(anchor_num + ".") or (parent and num == parent):
                neighbor_ids.append(sid)
    for sid in neighbor_ids[:4]:
        txt = "\n".join(c.get("source_text") or "" for c in claims if c.get("section_id") == sid)
        if txt:
            scope_texts[sid] = txt

    # fallback: si no hay seccion resuelta, ventana +-6 claims por pagina
    if not local:
        page = finding.get("page") or 0
        win = [c for c in claims if abs((c.get("pagina") or 0) - page) <= 2]
        win.sort(key=lambda c: (c.get("pagina") or 0, c.get("claim_id") or ""))
        local_text = "\n".join(c.get("source_text") or "" for c in win)
        scope_texts["_window"] = local_text

    return {
        "document_id": doc,
        "analyzed_section": sec_id,
        "section_local_text": local_text,
        "neighbor_section_ids": neighbor_ids,
        "scope_texts": scope_texts,          # <- lo que consume el gate R5
        "document_scope_status": "NOT_EVALUATED",   # R9: sin retrieval cross-seccion en el POC
        "n_local_claims": len(local),
        "context_chars": sum(len(t) for t in scope_texts.values()),
    }
