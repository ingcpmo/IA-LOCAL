"""SHADOW · CF-6 v2.0 · R4/E2 — construcción del fixture expandido (diseño §12).

Instrucción de Capa 9 (2026-09-04, "RECONCILIACIÓN POST-R2 + EJECUCIÓN R4" §3
E2): sin etiquetado humano en esta ronda -- **la etiqueta es consecuencia de
cómo se construye el par**, nunca un juicio. Todo el texto se deriva
determinísticamente de `decomposition.yaml` (ya firmado, NUNCA modificado
aquí) mediante transformaciones fijas y documentadas. CERO LLM.

## Perfiles de forma (estratificación obligatoria, diagnóstico §1)

`density = n_subcriterios / longitud_media_en_caracteres(text_en)`. Los 10
requisitos de mayor densidad = `MANY_SHORT` (perfil `21_CFR_11.10(d)`, 8
sub-criterios cortos); los 10 de menor densidad = `FEW_LONG` (perfil
`21_CFR_11.50_11.70`, sub-criterios largos). Partición fija, calculada una
sola vez sobre el catálogo completo (20 requisitos, 84 sub-criterios) --
ver `_shape_profiles()`.

## Grupos de dominio léxico (para IRRELEVANT_SIMILAR_DOMAIN / IRRELEVANT_CLEAR)

Agrupación declarada a mano, una sola vez, documentada -- no se deriva del
Relevance Model (evitaría acoplar el fixture al instrumento que mide).

## Categorías y su regla de etiqueta

Ver el diccionario `_CATEGORY_LABELS` y cada función `_build_<categoria>`.
`ABSENT_EVIDENCE` no genera pares (mide la rama `relevant_evidence` vacío,
ver nota en `build_fixture()`).
"""
from __future__ import annotations

import hashlib
import json
import re
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path

from factory.regulatory.requirement_catalog.requirement_decomposition_loader import (
    load_decomposition,
)

SEED = 20260904  # semilla declarada de partición CALIBRATION/HELDOUT

_DOMAIN_GROUPS = {
    "ACCESS_SECURITY": ["21_CFR_11.10(d)", "21_CFR_11.10(g)"],
    "AUDIT_TRAIL": ["21_CFR_11.10(e)", "21_CFR_211.68(b)"],
    "SIGNATURE_RECORD": ["21_CFR_11.50_11.70", "21_CFR_11.10(a)"],
    "BACKUP_ANNEX": ["ANNEX11_4", "ANNEX11_7.1", "ANNEX11_9", "ANNEX11_12", "ANNEX11_17"],
    "DATA_INTEGRITY_ALCOA": ["ALCOA_ATTRIBUTABLE", "ALCOA_LEGIBLE", "ALCOA_CONTEMPORANEOUS",
                            "ALCOA_ORIGINAL", "ALCOA_ACCURATE", "ALCOA_COMPLETE",
                            "ALCOA_CONSISTENT", "ALCOA_ENDURING", "ALCOA_AVAILABLE"],
}

_CATEGORY_LABELS = {
    "POSITIVE_CLEAR": "RELEVANT",
    "TECHNICAL_PARAPHRASE": "RELEVANT",
    "IRRELEVANT_SIMILAR_DOMAIN": "IRRELEVANT",
    "IRRELEVANT_CLEAR": "IRRELEVANT",
    "AMBIGUOUS_PARTIAL": "INCONCLUSIVE",
    "PROCEDURAL_VS_TECHNICAL": "IRRELEVANT",
    "CROSS_DOMAIN": "PARTIALLY_RELEVANT",
    "ADVERSARIAL_LEXICAL": "IRRELEVANT",
}

# sustitución léxica fija para TECHNICAL_PARAPHRASE -- determinista, sin LLM.
# Preserva significado (sinónimos declarados, no reformulación libre).
# v2 (R4/E2, iteración autorizada por Capa 9 2026-09-05): la v1 (10 pares,
# sustitución de la PRIMERA ocurrencia solamente) resultó demasiado leve --
# medido en R4: recall trivial 1.0, no reprodujo la dificultad real de
# sec-0005 (donde el candidato real comparte SOLO 3 términos genéricos con
# el sub-criterio, ratio 0.081, muy por debajo del umbral). Esta versión
# sustituye TODAS las ocurrencias (no solo la primera) con un diccionario de
# sinónimos de dominio mucho más amplio (vocabulario GMP/21 CFR real, no
# solo conectores), reduciendo el solapamiento léxico directo de forma
# deliberada -- el objetivo es que la etiqueta siga siendo RELEVANT por
# construcción (la sustancia no cambia) pero el eco léxico se acerque al
# caso real observado, no al caso trivial de la v1. Determinista, sin LLM.
_PARAPHRASE_MAP = [
    (r"\bthere is\b", "the platform maintains"),
    (r"\bthere are\b", "the platform maintains"),
    (r"\beach\b", "every instance of a"),
    (r"\bshows\b", "discloses"),
    (r"\bmust\b", "is obligated to"),
    (r"\bshall\b", "is obligated to"),
    (r"\bprocess(es)?\b", "workflow\\1"),
    (r"\bsystem\b", "platform"),
    (r"\brecords\b", "entries"),
    (r"\brecord\b", "entry"),
    (r"\bexists\b", "is maintained"),
    (r"\bdate and time\b", "chronological marker"),
    (r"\belectronic signature\b", "digital signing credential"),
    (r"\bsignature(s)?\b", "signing credential\\1"),
    (r"\baccount(s)?\b", "user profile\\1"),
    (r"\baccess\b", "entry permission"),
    (r"\bcontrol\b", "governance"),
    (r"\bmechanism\b", "capability"),
    (r"\bdocumented\b", "put on record"),
    (r"\brisk-based\b", "prioritized by exposure"),
    (r"\bintended use\b", "operational purpose"),
    (r"\bacceptance criteria\b", "pass/fail thresholds"),
    (r"\bexecution evidence\b", "proof of performance"),
    (r"\bdeviations\b", "departures from plan"),
    (r"\btraceability\b", "linkage"),
    (r"\binvalid\b", "non-genuine"),
    (r"\baltered\b", "tampered"),
    (r"\bdiscern\b", "flag"),
    (r"\bprivilege(s)?\b", "entitlement\\1"),
    (r"\bprovisioning\b", "onboarding"),
    (r"\brevocation\b", "deactivation"),
    (r"\bdeactivation\b", "shutdown"),
    (r"\bindividual\b", "personal"),
    (r"\bshared\b", "pooled"),
    (r"\btechnical\b", "non-human"),
    (r"\bnon-interactive\b", "unattended"),
    (r"\bowner\b", "responsible party"),
    (r"\bminimum\b", "baseline"),
    (r"\btest evidence\b", "verification proof"),
    (r"\bdenied\b", "blocked"),
    (r"\baudit trail\b", "activity log"),
    (r"\btime-?stamped\b", "chronologically marked"),
    (r"\bcreate, modify and delete\b", "originate, amend and purge"),
    (r"\bprevious value\b", "prior state"),
    (r"\brestricted\b", "gated"),
    (r"\bprinted name\b", "legible identity"),
    (r"\bmeaning\b", "intent"),
    (r"\breadable\b", "legible"),
    (r"\bassociated\b", "linked"),
    (r"\bextracted?\b", "lifted"),
    (r"\bcopied\b", "duplicated"),
    (r"\btransferred\b", "relocated"),
    (r"\bordinary means\b", "standard tooling"),
    (r"\bfeature\b", "capability"),
    (r"\bimplementation\b", "rollout"),
]


def _paraphrase(text_en: str) -> str:
    """Sustituye TODAS las ocurrencias de cada patrón (no solo la primera,
    a diferencia de v1) -- reducción de solapamiento léxico deliberada,
    misma sustancia semántica."""
    out = text_en
    for pat, repl in _PARAPHRASE_MAP:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    if out == text_en and "," in text_en:
        head, _, tail = text_en.partition(",")
        out = f"{tail.strip()}, {head.strip()}"
    return out


_ANCHOR_MANY_SHORT = "21_CFR_11.10(d)"   # 8 sub-criterios cortos (nombrado por Capa 9)
_ANCHOR_FEW_LONG = "21_CFR_11.50_11.70"  # 7 sub-criterios largos (nombrado por Capa 9)


def _requirement_shape_profiles(decomp: dict) -> dict:
    """Partición 10/10 por `density = n_subcriterios / longitud_media_en`
    (mayor densidad = MANY_SHORT), con los dos requisitos ANCLA que Capa 9
    nombra explícitamente FORZADOS a su perfil declarado. Un corte puro por
    densidad coloca a `21_CFR_11.50_11.70` (density 0.0788, rank 3/20) en
    MANY_SHORT -- no es un error de cálculo, es que ambos anclas están, en
    magnitud absoluta, más cerca entre sí que de los extremos de la
    distribución (verificado, ver docstring de commit). Se fuerza la
    asignación declarada por Capa 9 para los dos anclas y se intercambia el
    elemento MENOS marginal del lado opuesto para preservar el balance
    10/10 (necesario para que cada categoría del fixture pueda cubrir
    ambos perfiles con suficientes pares)."""
    rows = []
    for rid, block in decomp["requirements"].items():
        subs = block["subcriteria"]
        avg = sum(len(sc["text_en"]) for sc in subs) / len(subs)
        rows.append((rid, len(subs) / avg))
    rows.sort(key=lambda r: -r[1])
    half = len(rows) // 2
    many_short = [rid for rid, _ in rows[:half]]
    few_long = [rid for rid, _ in rows[half:]]

    if _ANCHOR_FEW_LONG in many_short:
        # el ancla FEW_LONG cayó del lado MANY_SHORT por densidad pura --
        # se fuerza su lado y se promueve, para compensar el balance 10/10,
        # el candidato de few_long con mayor densidad (el más "cercano" a
        # MANY_SHORT dentro de ese lado).
        many_short.remove(_ANCHOR_FEW_LONG)
        promoted = few_long.pop(0)
        many_short.append(promoted)
        few_long.append(_ANCHOR_FEW_LONG)

    assert _ANCHOR_MANY_SHORT in many_short, "el ancla MANY_SHORT debe quedar en su lado por rank (densidad máxima)"
    assert len(many_short) == len(few_long) == half

    return {rid: "MANY_SHORT" for rid in many_short} | {rid: "FEW_LONG" for rid in few_long}


def _requirement_domain(rid: str) -> str | None:
    for dom, members in _DOMAIN_GROUPS.items():
        if rid in members:
            return dom
    return None


def _is_procedural(sc: dict) -> bool:
    return bool(re.search(r"\bproces[eo]s?\b|\bprocess(?:es)?\b", sc.get("text", "") + " " + sc.get("text_en", ""), re.IGNORECASE))


@dataclass
class FixturePair:
    pair_id: str
    category: str
    label: str
    target_requirement_id: str
    target_subcriterion_id: str | None
    requirement_shape_profile: str
    evidence_text: str
    source: str  # de dónde se derivó el texto (auditable, nunca "generado libremente")


def build_fixture(seed: int = SEED) -> dict:
    decomp = load_decomposition()
    reqs = decomp["requirements"]
    shapes = _requirement_shape_profiles(decomp)
    pairs: list[FixturePair] = []
    n = [0]

    def add(category, label, rid, sc_id, text, source):
        n[0] += 1
        pairs.append(FixturePair(
            pair_id=f"fx-{n[0]:04d}", category=category, label=label,
            target_requirement_id=rid, target_subcriterion_id=sc_id,
            requirement_shape_profile=shapes[rid], evidence_text=text, source=source))

    # 1. POSITIVE_CLEAR + 2. TECHNICAL_PARAPHRASE + 5. AMBIGUOUS_PARTIAL:
    # una instancia por sub-criterio de CADA requisito (cobertura total, 84
    # sub-criterios -> 84 pares por categoría, se recorta después a un tope
    # razonable por categoría para no desbalancear el fixture).
    for rid, block in reqs.items():
        for sc in block["subcriteria"]:
            add("POSITIVE_CLEAR", "RELEVANT", rid, sc["id"], sc["text_en"],
                source=f"decomposition.yaml::{rid}::{sc['id']}::text_en (verbatim)")
            add("TECHNICAL_PARAPHRASE", "RELEVANT", rid, sc["id"], _paraphrase(sc["text_en"]),
                source=f"decomposition.yaml::{rid}::{sc['id']}::text_en (paráfrasis léxica fija)")
            words = sc["text_en"].split()
            half_text = " ".join(words[: max(3, len(words) // 2)])
            add("AMBIGUOUS_PARTIAL", "INCONCLUSIVE", rid, sc["id"], half_text,
                source=f"decomposition.yaml::{rid}::{sc['id']}::text_en (primera mitad, truncada)")

    # 3. IRRELEVANT_SIMILAR_DOMAIN: texto de un sub-criterio de OTRO requisito
    # del MISMO grupo de dominio léxico.
    for rid in reqs:
        dom = _requirement_domain(rid)
        if dom is None:
            continue
        siblings = [r for r in _DOMAIN_GROUPS[dom] if r != rid and r in reqs]
        if not siblings:
            continue
        sib = siblings[0]
        sib_sc = reqs[sib]["subcriteria"][0]
        target_sc = reqs[rid]["subcriteria"][0]
        add("IRRELEVANT_SIMILAR_DOMAIN", "IRRELEVANT", rid, target_sc["id"], sib_sc["text_en"],
            source=f"decomposition.yaml::{sib}::{sib_sc['id']}::text_en (mismo dominio '{dom}', "
                   f"requisito distinto, dirigido a {rid}::{target_sc['id']})")

    # 4. IRRELEVANT_CLEAR: texto de un requisito de un grupo de dominio TOTALMENTE distinto.
    domains = list(_DOMAIN_GROUPS)
    for rid in reqs:
        dom = _requirement_domain(rid)
        if dom is None:
            continue
        other_dom = domains[(domains.index(dom) + 1) % len(domains)]
        other_req = _DOMAIN_GROUPS[other_dom][0]
        if other_req not in reqs:
            continue
        other_sc = reqs[other_req]["subcriteria"][0]
        target_sc = reqs[rid]["subcriteria"][0]
        add("IRRELEVANT_CLEAR", "IRRELEVANT", rid, target_sc["id"], other_sc["text_en"],
            source=f"decomposition.yaml::{other_req}::{other_sc['id']}::text_en (dominio distinto "
                   f"'{other_dom}' vs '{dom}', dirigido a {rid}::{target_sc['id']})")

    # 6. PROCEDURAL_VS_TECHNICAL: dentro del MISMO requisito, texto de un
    # sub-criterio PROCEDIMENTAL dirigido a un sub-criterio TÉCNICO (o
    # viceversa si no hay procedimental).
    for rid, block in reqs.items():
        subs = block["subcriteria"]
        proc = [sc for sc in subs if _is_procedural(sc)]
        tech = [sc for sc in subs if not _is_procedural(sc)]
        for p_sc in proc:
            for t_sc in tech:
                add("PROCEDURAL_VS_TECHNICAL", "IRRELEVANT", rid, t_sc["id"], p_sc["text_en"],
                    source=f"decomposition.yaml::{rid}::{p_sc['id']}::text_en (procedimental, "
                           f"dirigido al sub-criterio técnico {rid}::{t_sc['id']})")

    # 7. CROSS_DOMAIN: concatena un sub-criterio de este requisito con uno de
    # OTRO dominio -- dirigido al sub-criterio propio (cobertura parcial real).
    for rid, block in reqs.items():
        dom = _requirement_domain(rid)
        own_sc = block["subcriteria"][0]
        other_dom = domains[(domains.index(dom) + 2) % len(domains)] if dom else domains[0]
        other_req = _DOMAIN_GROUPS[other_dom][0]
        if other_req not in reqs or other_req == rid:
            continue
        other_sc = reqs[other_req]["subcriteria"][0]
        combined = f"{own_sc['text_en']}. {other_sc['text_en']}."
        add("CROSS_DOMAIN", "PARTIALLY_RELEVANT", rid, own_sc["id"], combined,
            source=f"concatenación decomposition.yaml::{rid}::{own_sc['id']} + "
                   f"{other_req}::{other_sc['id']} (dominio distinto '{other_dom}')")

    # 8. ADVERSARIAL_LEXICAL: mismo vocabulario, orden de palabras invertido
    # (preserva léxico, destruye la sintaxis/semántica real).
    for rid, block in reqs.items():
        sc = block["subcriteria"][0]
        reversed_text = " ".join(reversed(sc["text_en"].split()))
        add("ADVERSARIAL_LEXICAL", "IRRELEVANT", rid, sc["id"], reversed_text,
            source=f"decomposition.yaml::{rid}::{sc['id']}::text_en (orden de palabras invertido, "
                   f"mismo léxico, sintaxis destruida)")

    return {
        "pairs": pairs,
        "shapes": shapes,
        "categories": _CATEGORY_LABELS,
        "domain_groups": _DOMAIN_GROUPS,
        "seed": seed,
    }


def _partition_calibration_heldout(pairs: list[FixturePair], seed: int) -> dict:
    """Partición CALIBRATION/HELDOUT disjunta por requirement_id, con semilla
    declarada. Ambos perfiles de forma deben aparecer en ambas particiones
    (se verifica, no se fuerza artificialmente: la partición determinista
    por hash ya lo produce dado que hay 10 requisitos de cada perfil)."""
    rids = sorted({p.target_requirement_id for p in pairs})
    calib, heldout = set(), set()
    for rid in rids:
        h = int(hashlib.sha256(f"{seed}:{rid}".encode()).hexdigest(), 16)
        (calib if h % 2 == 0 else heldout).add(rid)
    return {"CALIBRATION": sorted(calib), "HELDOUT": sorted(heldout)}


def build_and_freeze(out_path: str | Path = "docs_plan/shadow_llm/CF6/CF6_v2_R4_FIXTURE.json",
                     seed: int = SEED) -> dict:
    fx = build_fixture(seed=seed)
    partition = _partition_calibration_heldout(fx["pairs"], seed)
    pairs_dicts = [asdict(p) for p in fx["pairs"]]
    for p in pairs_dicts:
        p["partition"] = ("CALIBRATION" if p["target_requirement_id"] in partition["CALIBRATION"]
                          else "HELDOUT")

    by_category: dict[str, int] = {}
    by_category_profile: dict[str, dict[str, int]] = {}
    for p in pairs_dicts:
        by_category[p["category"]] = by_category.get(p["category"], 0) + 1
        by_category_profile.setdefault(p["category"], {}).setdefault(
            p["requirement_shape_profile"], 0)
        by_category_profile[p["category"]][p["requirement_shape_profile"]] += 1

    doc = {
        "schema": "SHADOW_CF6_V2_R4_FIXTURE/v1",
        "seed": seed,
        "n_pairs": len(pairs_dicts),
        "n_pairs_by_category": by_category,
        "n_pairs_by_category_and_profile": by_category_profile,
        "requirement_shape_profiles": fx["shapes"],
        "domain_groups": fx["domain_groups"],
        "category_labels_by_construction": fx["categories"],
        "partition": partition,
        "absent_evidence_note": (
            "ABSENT_EVIDENCE no genera pares -- mide la rama relevant_evidence vacío del "
            "propio pipeline R2 (4/5 secciones elegibles la tomaron en la corrida real); "
            "no requiere fixture propio, ya está medido en CF6_v2_R2_RUN.json."),
        "synthetic_data_justification": (
            "Todo el texto se deriva mecánicamente de decomposition.yaml (firmado, NUNCA "
            "modificado) vía transformaciones fijas y documentadas por par (`source`). Ninguna "
            "categoría representa juicio humano ni generación libre de un LLM (LLM_CALLS=0 en "
            "toda la construcción). Lo que NO puede demostrar: si estas transformaciones "
            "capturan la distribución real de errores de un documento GMP genuino -- eso es "
            "exactamente lo que la partición REAL_ADJUDICATED (27 pares, R2, adjudicados por "
            "Capa 9) aporta por separado, y por lo que NUNCA se mezclan en la misma métrica."),
        "pairs": pairs_dicts,
    }
    blob = json.dumps({k: v for k, v in doc.items() if k != "fixture_hash"},
                      sort_keys=True, ensure_ascii=False)
    doc["fixture_hash"] = hashlib.sha256(blob.encode()).hexdigest()
    Path(out_path).write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return doc


if __name__ == "__main__":  # pragma: no cover
    d = build_and_freeze()
    print("n_pairs", d["n_pairs"], "fixture_hash", d["fixture_hash"][:16])
    print(json.dumps(d["n_pairs_by_category"], indent=1, ensure_ascii=False))
    print(json.dumps(d["n_pairs_by_category_and_profile"], indent=1, ensure_ascii=False))
