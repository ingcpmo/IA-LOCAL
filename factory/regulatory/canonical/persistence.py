"""Persistencia local del modelo canónico (V2, B1) —
docs_plan/PLAN_IMPLEMENTACION_ANALIZADOR_GMP_LOCAL_V2.md B1.

SQLite (stdlib `sqlite3`, sin dependencia nueva), un archivo por store en
`factory/regulatory/canonical_store/`. Artefacto de runtime, regenerable
desde el PDF real — mismo criterio que `factory/regulatory/retrieval_index/`
(gitignored).

Un objeto por tabla; los objetos DERIVADOS se rechazan al guardar si su
provenance no valida (los constructores de `model.py` ya lo garantizan,
esto es la segunda barrera). Idempotente: `upsert` por id determinista.

NADA sale del servidor. Sin red, sin servicio, sin cliente.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from factory.regulatory.canonical.model import (
    Claim, Control, Document, Evidence, Section, SystemComponent, Table, Test,
    as_dict, validate_provenance,
)

STORE_DIR = Path(__file__).resolve().parent.parent / "canonical_store"

_TABLES = {
    "document": Document,
    "section": Section,
    "table_obj": Table,
    "claim": Claim,
    "control": Control,
    "actor": None,
    "system_component": SystemComponent,
    "test": Test,
    "evidence": Evidence,
}

_ID_FIELD = {
    "document": "document_id",
    "section": "section_id",
    "table_obj": "table_id",
    "claim": "claim_id",
    "control": "control_id",
    "actor": "actor_id",
    "system_component": "component_id",
    "test": "test_id",
    "evidence": "evidence_id",
}

_PROV_BEARING = {"section", "table_obj", "claim", "test"}


class CanonicalStore:
    def __init__(self, document_id: str, *, store_dir: Path = STORE_DIR):
        self.document_id = document_id
        store_dir.mkdir(parents=True, exist_ok=True)
        self.path = store_dir / f"{document_id}.sqlite3"
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        for tbl, idf in _ID_FIELD.items():
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {tbl} ("
                f"  id TEXT PRIMARY KEY,"
                f"  document_id TEXT NOT NULL,"
                f"  payload TEXT NOT NULL"
                f")"
            )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        self._conn.commit()

    # ── escritura ────────────────────────────────────────────────────────

    def _kind(self, obj) -> str:
        for tbl, cls in _TABLES.items():
            if cls is not None and isinstance(obj, cls):
                return tbl
        # Actor no tiene provenance ni clase importada arriba para evitar
        # ciclo; se detecta por atributo.
        if hasattr(obj, "actor_id") and hasattr(obj, "nombre_rol"):
            return "actor"
        raise TypeError(f"objeto no reconocido para el store: {type(obj).__name__}")

    def put(self, obj) -> str:
        kind = self._kind(obj)
        if kind in _PROV_BEARING:
            validate_provenance(getattr(obj, "provenance", None))
        idf = _ID_FIELD[kind]
        obj_id = getattr(obj, idf)
        payload = json.dumps(as_dict(obj), ensure_ascii=False, sort_keys=True)
        self._conn.execute(
            f"INSERT INTO {kind} (id, document_id, payload) VALUES (?,?,?) "
            f"ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, document_id=excluded.document_id",
            (obj_id, getattr(obj, "document_id", self.document_id), payload),
        )
        self._conn.commit()
        return obj_id

    def put_many(self, objs) -> int:
        n = 0
        for o in objs:
            self.put(o)
            n += 1
        return n

    def set_meta(self, key: str, value) -> None:
        self._conn.execute(
            "INSERT INTO meta (key,value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )
        self._conn.commit()

    # ── lectura ──────────────────────────────────────────────────────────

    def get_meta(self, key: str, default=None):
        row = self._conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def all(self, kind: str) -> list[dict]:
        if kind not in _ID_FIELD:
            raise KeyError(f"kind desconocido: {kind!r}")
        rows = self._conn.execute(
            f"SELECT payload FROM {kind} WHERE document_id=? ORDER BY id", (self.document_id,)
        ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def get(self, kind: str, obj_id: str) -> dict | None:
        row = self._conn.execute(
            f"SELECT payload FROM {kind} WHERE id=?", (obj_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def counts(self) -> dict:
        return {k: self._conn.execute(
            f"SELECT COUNT(*) FROM {k} WHERE document_id=?", (self.document_id,)
        ).fetchone()[0] for k in _ID_FIELD}

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "CanonicalStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
