"""Prueba dirigida: la capa semantica como RED DE SEGURIDAD DE RECALL (FASE 2, aislado).

Corre la capa semantica (qwen, gate endurecido H-1/H-2/H-3, estabilidad H-4)
contra el MISMO instrumento que el roadmap usa para medir recall: el fixture set
7P + 2N (`docs_plan/W5V2_RECALL_FIXTURE_SET_DRAFT.md`, verificado 2026-08-08).

Pregunta: para los 7 positivos (evidencia REAL presente, que el pipeline de
JUICIO no ancla -> recall 2/7), ¿un LLM local pinneado y restringido por el gate
R5 recupera la cita literal en la ubicacion conocida? Y para los 2 negativos
(palabra mencionada, requisito NO evidenciado), ¿se abstiene correctamente?

NO toca producto, reglas, findings, pipeline ni el modelo de JUICIO. Ollama
local. Store canonico SOLO LECTURA. Log propio. No commitea nada.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from factory.regulatory.canonical.persistence import CanonicalStore
from factory.prototypes.semantic_hybrid_poc import pinned_client as pc
from factory.prototypes.semantic_hybrid_poc import context_composer as cc
from factory.prototypes.semantic_hybrid_poc.stability import warmup, assess_stable

MODEL = "qwen2.5:7b-instruct-q4_K_M"
CANON_DIR = Path("factory/regulatory/canonical_store")
OUT_DIR = Path("factory/prototypes/semantic_hybrid_poc/bakeoff_results")
STABILITY_N = 2
RETRIEVE_K = 40           # top-K claims por overlap de terminos (retrieval a nivel DOC, R9)

# ---- fixture set 7P + 2N (fuente: W5V2_RECALL_FIXTURE_SET_DRAFT.md) -----------
# page = pagina del fixture (0-based en el doc). La ventana +-2 claims del
# composer absorbe un posible desfase 0/1-based.
FIXTURES = [
    {"id": "P1", "polarity": "POS", "document": "RW-0005", "requirement": "21_CFR_11.10(e)",
     "page": 45, "note": "audit trail archivado + logins/logouts/intentos registrados"},
    {"id": "P2", "polarity": "POS", "document": "RW-0005", "requirement": "21_CFR_11.10(g)",
     "page": 39, "note": "Seccion 4 Security / F09.00 Physical Security, control de acceso al operador"},
    {"id": "P3", "polarity": "POS", "document": "RW-0005", "requirement": "ANNEX11_17",
     "page": 44, "note": "UR3.3.6 Data retention 1 anio, archivado en ubicacion alterna"},
    {"id": "P4", "polarity": "POS", "document": "RW-0011", "requirement": "ALCOA_ATTRIBUTABLE",
     "page": 12, "note": "accion de calibracion atada a credenciales del operador"},
    {"id": "P5", "polarity": "POS", "document": "RW-0005", "requirement": "ALCOA_CONTEMPORANEOUS",
     "page": 45, "note": "pasaje audit trail, envio a base de datos con timestamp"},
    {"id": "P6", "polarity": "POS", "document": "RW-0011", "requirement": "21_CFR_211.68(b)",
     "page": 12, "note": "mismo pasaje credenciales/calibracion que P4"},
    {"id": "P7", "polarity": "POS", "document": "RW-0012", "requirement": "21_CFR_211.68(b)",
     "page": 13, "note": "pasaje casi identico a P6, documento distinto"},
    {"id": "N1", "polarity": "NEG", "neg_kind": "strict", "document": "RW-0005", "requirement": "ANNEX11_4",
     "page": 1, "note": "\"GAMP5\" en lista de referencias numeradas — rechazo correcto en Piloto 1"},
    {"id": "N2", "polarity": "NEG", "neg_kind": "page_scoped_only", "document": "RW-0005", "requirement": "21_CFR_11.10(e)",
     "page": 3, "note": "entrada de indice \"F12.00: Audit Trail ... 45\" — palabra, no evidencia (en p.3). "
                        "Con retrieval a nivel DOC el requisito SI esta evidenciado en otra parte (P1/P5) -> R9: RECOVERED es correcto; "
                        "el FALLO seria citar la propia linea del indice."},
]

# elementos del comportamiento regulatorio por requirement_id (FIJADOS por codigo,
# no los genera el modelo). Nivel: lo que el pasaje del fixture podria evidenciar.
PROBE_ELEMENTS = {
    "21_CFR_11.10(e)": [
        {"element_id": "e1", "description": "un audit trail generado por el sistema con marca de tiempo"},
        {"element_id": "e2", "description": "registra acciones sobre los registros y/o logins, logouts e intentos de login"},
        {"element_id": "e3", "description": "conserva el valor previo (no sobrescribe)"},
    ],
    "21_CFR_11.10(g)": [
        {"element_id": "g1", "description": "un control de acceso que restringe el uso del sistema a individuos autorizados"},
        {"element_id": "g2", "description": "el control aplica en el punto de uso de las operaciones/funciones del sistema"},
    ],
    "ANNEX11_17": [
        {"element_id": "a1", "description": "los datos se archivan / retienen por un periodo definido"},
        {"element_id": "a2", "description": "el dato archivado puede recuperarse/leerse durante ese periodo"},
    ],
    "ALCOA_ATTRIBUTABLE": [
        {"element_id": "t1", "description": "cada accion registrada se atribuye a una identidad individual"},
        {"element_id": "t2", "description": "mediante un mecanismo tecnico (credenciales / login), no texto libre"},
    ],
    "ALCOA_CONTEMPORANEOUS": [
        {"element_id": "c1", "description": "la accion o el dato se registra en el momento en que ocurre (timestamp del sistema / envio inmediato a la base de datos)"},
    ],
    "21_CFR_211.68(b)": [
        {"element_id": "b1", "description": "verificacion de exactitud de entrada/salida de la informacion, o atribucion de la accion a credenciales del operador"},
        {"element_id": "b2", "description": "control de acceso o de cambios sobre el equipo automatizado"},
    ],
    "ANNEX11_4": [
        {"element_id": "v1", "description": "el documento describe con evidencia concreta el comportamiento del requisito citado (no solo menciona el tema o lo lista como referencia)"},
    ],
}
PROBE_INTENT = {
    "21_CFR_11.10(e)": "El sistema genera un audit trail automatico, con timestamp, seguro y que preserva el valor previo, para acciones sobre registros electronicos.",
    "21_CFR_11.10(g)": "El sistema verifica que solo individuos autorizados usan el sistema y ejecutan operaciones (chequeo de autoridad).",
    "ANNEX11_17": "Los datos deben archivarse y poder recuperarse legibles durante todo el periodo de retencion definido.",
    "ALCOA_ATTRIBUTABLE": "Cada dato/accion es atribuible a un individuo unico mediante un mecanismo tecnico.",
    "ALCOA_CONTEMPORANEOUS": "El dato se registra en el momento en que la actividad ocurre.",
    "21_CFR_211.68(b)": "Los equipos automatizados tienen controles de exactitud de I/O, de acceso/cambios y respaldo de datos.",
    "ANNEX11_4": "El sub-criterio exige evidencia anclada del comportamiento; mencionar el tema o listarlo como referencia no basta.",
}


# terminos de recuperacion por fixture (retrieval determinista, por CODIGO -- R9).
# El canonical store de este corpus tiene `pagina` gruesa/poco fiable; se recupera
# por contenido a nivel de DOCUMENTO, no por ventana de pagina.
RETRIEVAL_TERMS = {
    "P1": ["audit trail", "archiv", "login", "logout", "log in", "records shall", "recorded"],
    "P2": ["security", "physical security", "f09", "operator", "access", "authorized", "password", "role", "privilege"],
    "P3": ["retention", "retain", "archiv", "ur3.3.6", "1 year", "one year", "alternate location", "data retention"],
    "P4": ["calibration", "credential", "operator", "log in", "login", "user id", "user name",
           "attribut", "sign", "access level", "security level", "supervisor", "engineer", "role"],
    "P5": ["audit trail", "timestamp", "time stamp", "database", "contemporaneous", "recorded", "date and time"],
    "P6": ["calibration", "credential", "operator", "login", "user id", "access level", "security level",
           "automated", "input", "output", "accuracy", "verif"],
    "P7": ["calibration", "credential", "operator", "login", "user id", "access level", "security level",
           "automated", "input", "output", "accuracy", "verif"],
    "N1": ["gamp", "gamp5", "gamp 5", "iso", "reference"],
    "N2": ["audit trail", "f12.00", "f11.00", "f13.00", "contents", "table of contents"],
}


def _tokenize(s: str) -> list[str]:
    return re.findall(r"[a-z0-9.]+", (s or "").lower())


def _retrieve(document: str, terms: list[str], k: int = RETRIEVE_K) -> dict:
    """Top-K claims del DOCUMENTO por overlap con `terms` (substring, case-insensitive).
    Devuelve un ctx con el shape que consume runner.assess / prompt.build_prompt."""
    with CanonicalStore(document, store_dir=CANON_DIR) as s:
        claims = s.all("claim")
    tl = [t.lower() for t in terms]
    scored = []
    for c in claims:
        txt = (c.get("source_text") or "")
        low = txt.lower()
        hits = sum(1 for t in tl if t in low)
        if hits:
            scored.append((hits, len(txt), c))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    top = [c for _, _, c in scored[:k]]
    # ordena por seccion/pagina para dar continuidad al bloque de contexto
    top.sort(key=lambda c: (str(c.get("section_id") or ""), c.get("pagina") or 0,
                            c.get("claim_id") or ""))
    text = "\n".join(c.get("source_text") or "" for c in top)
    return {
        "document_id": document,
        "analyzed_section": None,
        "section_local_text": text,
        "neighbor_section_ids": [],
        "scope_texts": {"_retrieved": text},        # <- consume el gate R5
        "document_scope_status": "EVALUATED",         # R9: SI se recorrio el documento entero
        "n_local_claims": len(top),
        "n_candidate_claims": len(scored),
        "context_chars": len(text),
        "retrieval_terms": terms,
    }


def _register_probe_vocab():
    """Inyecta los elementos/intent por-requisito en los dicts del composer/prompt
    (mutacion IN-PLACE: prompt.py referencia los mismos objetos). Solo para el probe."""
    for req, els in PROBE_ELEMENTS.items():
        cc.REQUIRED_ELEMENTS[req] = els
    for req, intent in PROBE_INTENT.items():
        cc.REG_INTENT[req] = intent


def _fixture_to_finding(fx: dict) -> dict:
    return {
        "finding_id": f"recallprobe-{fx['id']}",
        "document": fx["document"],
        "page": fx["page"],
        "section": None,                    # -> compose usa la ventana +-2 claims por pagina
        "subtype": fx["requirement"],       # el prompt lee ELEMENTS/INTENT por esta clave
        "finding_class": "RecallProbe",
        "technical_basis": fx["requirement"],
        "source_text": fx["note"],
        "source_hash": f"recallprobe-{fx['id']}",
    }


_TOC_RE = re.compile(r"\.{4,}|F1[123]\.00|table of contents", re.IGNORECASE)


def _score(fx: dict, rec: dict) -> dict:
    els = rec.get("required_elements") or []
    present_verified = [e for e in els
                        if e.get("verdict") == "PRESENT" and e.get("quote_verified") is True]
    grounded = [g.get("quote") for g in (rec.get("grounded_quotes") or [])]
    fabricated = len(rec.get("fabricated_quotes") or [])
    claims_support = bool(present_verified)
    cites_toc = any(_TOC_RE.search(q or "") for q in grounded)

    if fx["polarity"] == "POS":
        verdict = "RECOVERED" if claims_support else "MISSED"
    elif fx.get("neg_kind") == "page_scoped_only":
        # R9: el requisito SI esta en el documento; el fallo real es citar la linea del indice
        verdict = "FALSE_SUPPORT_TOC" if (claims_support and cites_toc) else \
                  ("RECOVERED_ELSEWHERE" if claims_support else "CORRECT_ABSTENTION")
    else:  # neg_kind == strict
        verdict = "CORRECT_ABSTENTION" if not claims_support else "FALSE_SUPPORT"
    return {
        "probe_verdict": verdict,
        "assessment_status": rec.get("assessment_status"),
        "semantic_coverage": rec.get("semantic_coverage"),
        "present_verified_elements": [e.get("element_id") for e in present_verified],
        "verified_quotes": grounded[:3],
        "cites_toc_line": cites_toc,
        "fabricated_quotes": fabricated,
        "stability_flag": rec.get("stability_flag", False),
        "stability": rec.get("stability", {}),
    }


def run():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _register_probe_vocab()
    print(f"[recall_probe] modelo={MODEL} digest={pc.model_digest(MODEL)[:16]} "
          f"ollama={pc.ollama_version()}  stability_n={STABILITY_N}")
    w = warmup(MODEL)
    print(f"[recall_probe] warmup {w['wall_time_s']}s (err={w['transport_error']})")

    results = []
    for fx in FIXTURES:
        finding = _fixture_to_finding(fx)
        ctx = _retrieve(fx["document"], RETRIEVAL_TERMS[fx["id"]])
        t0 = time.time()
        rec = assess_stable(finding, MODEL, n=STABILITY_N, context_override=ctx)
        sc = _score(fx, rec)
        row = {"fixture": fx["id"], "polarity": fx["polarity"],
               "document": fx["document"], "requirement": fx["requirement"],
               "page": fx["page"], "note": fx["note"],
               "retrieved_claims": ctx["n_local_claims"], "candidate_claims": ctx["n_candidate_claims"],
               "context_chars": ctx["context_chars"], **sc,
               "wall_time_s": round(time.time() - t0, 2)}
        results.append(row)
        print(f"  {fx['id']} ({fx['polarity']}) {fx['requirement']:22s} {fx['document']}"
              f"  ret={ctx['n_local_claims']:2d}/{ctx['n_candidate_claims']:<3d}"
              f" -> {sc['probe_verdict']:18s} [{sc['assessment_status']}]"
              f" fab={sc['fabricated_quotes']} stab={sc['stability_flag']} {row['wall_time_s']}s")

    pos = [r for r in results if r["polarity"] == "POS"]
    neg = [r for r in results if r["polarity"] == "NEG"]
    _NEG_OK = {"CORRECT_ABSTENTION", "RECOVERED_ELSEWHERE"}
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model": MODEL, "model_digest": pc.model_digest(MODEL),
        "pinned_options": pc.PINNED_OPTIONS, "prompt_version": pc.PROMPT_VERSION,
        "stability_n": STABILITY_N, "retrieve_k": RETRIEVE_K,
        "retrieval": "por CODIGO, overlap de terminos a nivel de DOCUMENTO (R9); "
                     "el `pagina` del canonical store de este corpus es grueso",
        "source": "docs_plan/W5V2_RECALL_FIXTURE_SET_DRAFT.md (7P+2N, verif. 2026-08-08)",
        "judgment_pipeline_recall_baseline": "2/7 (roadmap, config H2+H4)",
        "positives_recovered": sum(1 for r in pos if r["probe_verdict"] == "RECOVERED"),
        "positives_total": len(pos),
        "positives_missed": [r["fixture"] for r in pos if r["probe_verdict"] == "MISSED"],
        "negatives_handled_ok": sum(1 for r in neg if r["probe_verdict"] in _NEG_OK),
        "negatives_total": len(neg),
        "negatives_false_support": [r["fixture"] for r in neg
                                    if r["probe_verdict"] in ("FALSE_SUPPORT", "FALSE_SUPPORT_TOC")],
        "fabricated_quotes_total": sum(r["fabricated_quotes"] for r in results),
        "stability_flagged": sum(1 for r in results if r["stability_flag"]),
        "per_fixture": results,
    }
    (OUT_DIR / "recall_probe_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print("\n=== RESUMEN ===")
    print(f"  positivos recuperados : {summary['positives_recovered']}/{summary['positives_total']}"
          f"   (baseline pipeline de juicio: 2/7)   missed={summary['positives_missed']}")
    print(f"  negativos manejados OK : {summary['negatives_handled_ok']}/{summary['negatives_total']}"
          f"   false_support={summary['negatives_false_support']}")
    print(f"  citas fabricadas      : {summary['fabricated_quotes_total']}  (debe ser 0)")
    print(f"  marcados inestables   : {summary['stability_flagged']}")
    return summary


if __name__ == "__main__":
    run()
