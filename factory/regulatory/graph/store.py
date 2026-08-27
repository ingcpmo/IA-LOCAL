"""GraphStore — nodos y aristas tipadas sobre SQLite local (V2, B2).

docs_plan/PLAN_IMPLEMENTACION_ANALIZADOR_GMP_LOCAL_V2.md B2.

Reglas duras:
  - Aristas TIPADAS: `rel` debe estar en `EDGE_RELATIONS`.
  - SIN aristas colgantes: ambos extremos de una arista deben existir como
    nodo registrado; si no, `DanglingEdgeError` (fail-closed).
  - Ids deterministas: `edge_id = f(src, dst, rel)` -> re-poblar el grafo
    es idempotente.
  - Un grafo por PROYECTO (spanning multi-documento), clave `project_id`.

stdlib `sqlite3`, sin dependencia nueva. Nada sale del servidor.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

STORE_DIR = Path(__file__).resolve().parent.parent / "graph_store"

NODE_KINDS = (
    "document", "section", "table", "claim", "control", "actor",
    "system_component", "test", "requirement", "regulation",
)

#: rel -> (kinds válidos de origen, kinds válidos de destino). "*" = cualquiera.
EDGE_RELATIONS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "regulated_by":   (("requirement",), ("regulation",)),
    "implemented_by": (("requirement", "claim", "section"), ("claim", "section")),
    "designed_by":    (("claim", "section"), ("claim", "section")),
    "tested_by":      (("claim", "section", "requirement"), ("test",)),
    "verifies":       (("test",), ("requirement", "claim")),
    "supports":       (("claim", "table", "test"), ("control", "requirement")),
    "contradicts":    (("claim", "table"), ("claim", "control")),
    "refers_to":      (("claim", "section"), ("system_component", "actor")),
    "supersedes":     (("document",), ("document",)),
}


class DanglingEdgeError(ValueError):
    """Una arista cuyo origen o destino no existe como nodo. Fail-closed:
    no se persiste, no se crea el nodo implícito."""


class UnknownRelationError(ValueError):
    """`rel` no está en EDGE_RELATIONS, o los kinds de los extremos no son
    válidos para ese rel."""


def _edge_id(src: str, dst: str, rel: str) -> str:
    raw = f"{src}\x1f{rel}\x1f{dst}"
    return "edg-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


@dataclass
class Node:
    node_id: str
    kind: str
    document_id: str | None
    label: str
    attrs: dict = field(default_factory=dict)


@dataclass
class Edge:
    edge_id: str
    src_id: str
    dst_id: str
    rel: str
    attrs: dict = field(default_factory=dict)


class GraphStore:
    def __init__(self, project_id: str, *, store_dir: Path = STORE_DIR):
        self.project_id = project_id
        store_dir.mkdir(parents=True, exist_ok=True)
        self.path = store_dir / f"{project_id}.sqlite3"
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS nodes ("
            "  node_id TEXT PRIMARY KEY,"
            "  kind TEXT NOT NULL,"
            "  document_id TEXT,"
            "  label TEXT NOT NULL,"
            "  attrs TEXT NOT NULL DEFAULT '{}'"
            ")"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS edges ("
            "  edge_id TEXT PRIMARY KEY,"
            "  src_id TEXT NOT NULL,"
            "  dst_id TEXT NOT NULL,"
            "  rel TEXT NOT NULL,"
            "  attrs TEXT NOT NULL DEFAULT '{}',"
            "  FOREIGN KEY (src_id) REFERENCES nodes(node_id),"
            "  FOREIGN KEY (dst_id) REFERENCES nodes(node_id)"
            ")"
        )
        cur.execute("CREATE INDEX IF NOT EXISTS ix_edges_src ON edges(src_id, rel)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_edges_dst ON edges(dst_id, rel)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_nodes_kind ON nodes(kind)")
        self._conn.commit()

    # ── nodos ────────────────────────────────────────────────────────────

    def add_node(self, node_id: str, kind: str, label: str, *,
                 document_id: str | None = None, attrs: dict | None = None) -> str:
        if kind not in NODE_KINDS:
            raise ValueError(f"kind de nodo inválido: {kind!r}")
        if not node_id:
            raise ValueError("node_id vacío")
        self._conn.execute(
            "INSERT INTO nodes (node_id, kind, document_id, label, attrs) VALUES (?,?,?,?,?) "
            "ON CONFLICT(node_id) DO UPDATE SET kind=excluded.kind, "
            "document_id=excluded.document_id, label=excluded.label, attrs=excluded.attrs",
            (node_id, kind, document_id, label[:500],
             json.dumps(attrs or {}, ensure_ascii=False, sort_keys=True)),
        )
        self._conn.commit()
        return node_id

    def has_node(self, node_id: str) -> bool:
        return self._conn.execute(
            "SELECT 1 FROM nodes WHERE node_id=?", (node_id,)
        ).fetchone() is not None

    def get_node(self, node_id: str) -> Node | None:
        row = self._conn.execute(
            "SELECT node_id, kind, document_id, label, attrs FROM nodes WHERE node_id=?",
            (node_id,),
        ).fetchone()
        if not row:
            return None
        return Node(row[0], row[1], row[2], row[3], json.loads(row[4]))

    def nodes(self, *, kind: str | None = None, document_id: str | None = None) -> list[Node]:
        q = "SELECT node_id, kind, document_id, label, attrs FROM nodes WHERE 1=1"
        args: list = []
        if kind:
            q += " AND kind=?"; args.append(kind)
        if document_id:
            q += " AND document_id=?"; args.append(document_id)
        q += " ORDER BY node_id"
        return [Node(r[0], r[1], r[2], r[3], json.loads(r[4]))
                for r in self._conn.execute(q, args).fetchall()]

    # ── aristas ──────────────────────────────────────────────────────────

    def add_edge(self, src_id: str, dst_id: str, rel: str, *,
                 attrs: dict | None = None) -> str:
        if rel not in EDGE_RELATIONS:
            raise UnknownRelationError(f"rel desconocido: {rel!r}")
        src = self.get_node(src_id)
        dst = self.get_node(dst_id)
        if src is None or dst is None:
            missing = src_id if src is None else dst_id
            raise DanglingEdgeError(f"arista {rel}: nodo inexistente {missing!r}")
        ok_src, ok_dst = EDGE_RELATIONS[rel]
        if "*" not in ok_src and src.kind not in ok_src:
            raise UnknownRelationError(
                f"rel {rel!r}: origen debe ser {ok_src}, es {src.kind!r}")
        if "*" not in ok_dst and dst.kind not in ok_dst:
            raise UnknownRelationError(
                f"rel {rel!r}: destino debe ser {ok_dst}, es {dst.kind!r}")
        eid = _edge_id(src_id, dst_id, rel)
        self._conn.execute(
            "INSERT INTO edges (edge_id, src_id, dst_id, rel, attrs) VALUES (?,?,?,?,?) "
            "ON CONFLICT(edge_id) DO UPDATE SET attrs=excluded.attrs",
            (eid, src_id, dst_id, rel,
             json.dumps(attrs or {}, ensure_ascii=False, sort_keys=True)),
        )
        self._conn.commit()
        return eid

    def edges(self, *, src_id: str | None = None, dst_id: str | None = None,
              rel: str | None = None) -> list[Edge]:
        q = "SELECT edge_id, src_id, dst_id, rel, attrs FROM edges WHERE 1=1"
        args: list = []
        if src_id:
            q += " AND src_id=?"; args.append(src_id)
        if dst_id:
            q += " AND dst_id=?"; args.append(dst_id)
        if rel:
            q += " AND rel=?"; args.append(rel)
        q += " ORDER BY edge_id"
        return [Edge(r[0], r[1], r[2], r[3], json.loads(r[4]))
                for r in self._conn.execute(q, args).fetchall()]

    def neighbors(self, node_id: str, *, rel: str | None = None,
                  direction: str = "out") -> list[Node]:
        if direction not in ("out", "in", "both"):
            raise ValueError("direction debe ser out|in|both")
        out_ids: list[str] = []
        if direction in ("out", "both"):
            out_ids += [e.dst_id for e in self.edges(src_id=node_id, rel=rel)]
        if direction in ("in", "both"):
            out_ids += [e.src_id for e in self.edges(dst_id=node_id, rel=rel)]
        seen: set[str] = set()
        result: list[Node] = []
        for nid in out_ids:
            if nid in seen:
                continue
            seen.add(nid)
            n = self.get_node(nid)
            if n:
                result.append(n)
        return result

    def counts(self) -> dict:
        n_nodes = self._conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        n_edges = self._conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        by_kind = dict(self._conn.execute(
            "SELECT kind, COUNT(*) FROM nodes GROUP BY kind").fetchall())
        by_rel = dict(self._conn.execute(
            "SELECT rel, COUNT(*) FROM edges GROUP BY rel").fetchall())
        return {"nodes": n_nodes, "edges": n_edges,
                "nodes_by_kind": by_kind, "edges_by_rel": by_rel}

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "GraphStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
