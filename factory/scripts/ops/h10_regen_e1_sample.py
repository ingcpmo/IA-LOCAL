"""Regenera la muestra determinista de verificación humana E1
(`H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json`) desde los stores paralelos v2 ya
materializados (`canonical_store_v2/` + `graph_store_v2/`).

Se usa tras un cambio en `_link_refers_to` / la extracción de entidades para
producir el `refers_to`/`tested_by` que el humano debe re-revisar (E1).

Política de muestreo (idéntica a la muestra original):
  - `tested_by`: TODAS
  - `refers_to`: las 60 primeras por `edge_id` (id determinista = f(src, rel, dst))

`sample_sha256` = sha256 del JSON canónico (`sort_keys`) de `rows` sin los
campos `HUMAN_*`. Sin red, determinista, no toca producción ni el ledger.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from factory.regulatory.canonical.persistence import CanonicalStore
from factory.regulatory.graph.store import GraphStore

_REPO = Path(__file__).resolve().parents[3]
_GDIR = _REPO / "factory/regulatory/graph_store_v2"
_CDIR = _REPO / "factory/regulatory/canonical_store_v2"
_OUT = (_REPO / "factory/regulatory/pilot_run/h10_extraction_v2_20260830"
        / "H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json")
_PROJECT_ID = "RW-H10-V2"
_DOCS = ["RW-0005", "RW-0006", "RW-0009", "RW-0011", "RW-0012", "RW-0014", "RW-0003"]


def _provenance_by_dst() -> dict[str, dict]:
    """`node_id -> {anchor, hash}` para nodos destino (component/actor/test)."""
    prov: dict[str, dict] = {}
    for did in _DOCS:
        if not (_CDIR / f"{did}.sqlite3").exists():
            continue
        with CanonicalStore(did, store_dir=_CDIR) as s:
            for kind, idkey in (("system_component", "component_id"),
                                ("actor", "actor_id"), ("test", "test_id")):
                for r in s.all(kind):
                    pr = r.get("provenance") or {}
                    prov[r[idkey]] = {
                        "anchor": (pr.get("source_text") or "")[:200],
                        "hash": pr.get("source_hash") or "",
                    }
    return prov


def build_sample() -> dict:
    g = GraphStore(_PROJECT_ID, store_dir=_GDIR)
    nodes = {n.node_id: n for n in g.nodes()}
    prov = _provenance_by_dst()

    def row(e) -> dict:
        s, d = nodes[e.src_id], nodes[e.dst_id]
        pr = prov.get(e.dst_id, {})
        return {
            "relation": e.rel,
            "source_document": s.document_id,
            "page": (s.attrs or {}).get("pagina"),
            "exact_source_anchor": pr.get("anchor", ""),
            "source_node": e.src_id, "source_kind": s.kind,
            "source_label": s.label,
            "destination_node": e.dst_id, "destination_kind": d.kind,
            "destination_label": d.label[:120],
            "table_id_if_test": ((d.attrs or {}).get("identificador")
                                 if d.kind == "test" else None),
            "requirement_or_ref": e.attrs.get("via_ref") or e.attrs.get("match") or "",
            "provenance_hash": pr.get("hash", ""),
            "HUMAN_VERIFIED": None, "HUMAN_VERDICT": "", "HUMAN_NOTE": "",
        }

    tb = sorted(g.edges(rel="tested_by"), key=lambda e: e.edge_id)
    rt = sorted(g.edges(rel="refers_to"), key=lambda e: e.edge_id)[:60]
    rows = [row(e) for e in tb] + [row(e) for e in rt]
    core = [{k: v for k, v in r.items() if not k.startswith("HUMAN_")} for r in rows]
    sha = hashlib.sha256(
        json.dumps(core, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    totals = {"refers_to": len(g.edges(rel="refers_to")),
              "tested_by": len(g.edges(rel="tested_by"))}
    g.close()

    return {
        "artifact": "H-10 new-relations sample for HUMAN verification (RW-6 + RW-0003 SAT)",
        "extraction_version": "canonical-v1-2026-08+tests-v1",
        "governed_stores": {"canonical": "factory/regulatory/canonical_store_v2",
                            "graph": "factory/regulatory/graph_store_v2"},
        "relation_totals": totals,
        "sample_sha256": sha,
        "sample_size": len(rows),
        "sample_policy": "tested_by + verifies: TODAS; refers_to: 60 primeras por edge_id",
        "sha_rule": "sha256(json canonico de rows sin campos HUMAN_)",
        "HUMAN_INSTRUCTIONS": ("Fija HUMAN_VERIFIED true/false, HUMAN_VERDICT in "
                               "{CORRECT,WRONG_NODE,SPURIOUS,AMBIGUOUS}, HUMAN_NOTE. "
                               "La maquina NO marca ninguna."),
        "H10_HUMAN_SAMPLE_VERIFICATION": "PENDING",
        "rows": rows,
    }


def main() -> int:
    doc = build_sample()
    _OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"written": str(_OUT), "sample_sha256": doc["sample_sha256"],
                      "relation_totals": doc["relation_totals"],
                      "sample_size": doc["sample_size"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
