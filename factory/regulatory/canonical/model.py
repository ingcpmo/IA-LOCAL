"""Objetos del modelo canónico documental + validación de provenance.

docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md FASE 2.1/2.2.

Regla dura (fail-closed, mismo criterio que `chunked_engine.evidence_pack_gate`):
todo objeto DERIVADO (`Section`, `Table`, `Claim`, `Control`, `Actor`,
`SystemComponent`, `Test`, `Evidence`) lleva provenance completo
(`document_id · page · section · source_text · source_hash ·
extraction_version`). Un objeto sin provenance completo NO se persiste:
`build_*()` lanza `ProvenanceError`. Esto hace de la trazabilidad una
propiedad estructural, no algo que se reconstruye después.

Los ids son deterministas (derivados por hash del contenido + posición),
para que re-extraer el mismo documento sea idempotente y comparable entre
`extraction_version`.

Sin dependencias nuevas: solo stdlib.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, fields

#: Se sube cuando cambia la lógica de extracción de forma que altere el
#: contenido/estructura de los objetos derivados (mismo régimen que
#: `evidence_verifier`/prompts: un cambio de extracción es un cambio de
#: resultado y debe quedar registrado en cada objeto).
EXTRACTION_VERSION = "canonical-v1-2026-08"

#: WP-D -- etapa de extracción de objetos `Test` (SAT/OQ/IQ/PQ). ADITIVA y GOBERNADA
#: POR FLAG: OFF por default -> la salida del pipeline es idéntica a hoy y
#: `EXTRACTION_VERSION` no cambia. Activarla (env `V2_TEST_EXTRACTION=1` o el
#: parámetro `extract_tests=True`) sube la versión efectiva a
#: `EXTRACTION_VERSION + "+tests-v1"` -> re-derivación explícita, decisión de Capa 9.
TEST_EXTRACTION_ENV = "V2_TEST_EXTRACTION"
TEST_EXTRACTION_SUFFIX = "+tests-v1"


def test_extraction_enabled(override: bool | None = None) -> bool:
    if override is not None:
        return bool(override)
    import os
    return os.environ.get(TEST_EXTRACTION_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def effective_extraction_version(override: bool | None = None) -> str:
    return (EXTRACTION_VERSION + TEST_EXTRACTION_SUFFIX
            if test_extraction_enabled(override) else EXTRACTION_VERSION)


DOCUMENT_TYPES = ("URS", "FS", "DS", "SAT", "OQ", "IQ", "PQ", "SOP", "OTHER")
CLAIM_TYPES = ("control", "function", "test", "parameter", "actor_action", "statement")
CONTROL_CATEGORIES = (
    "access", "audit_trail", "backup_recovery", "time_sync", "integrity",
    "security", "interface", "redundancy", "data_retention", "other",
)
ACTOR_TYPES = ("human", "system", "role")
COMPONENT_TYPES = ("PLC", "SCADA", "HMI", "Historian", "DB", "network", "server", "other")
ANCHOR_STATUSES = ("anchored", "pending", "not_anchored")


class ProvenanceError(ValueError):
    """Un objeto derivado sin provenance completo. Fail-closed: no se
    persiste, no se degrada en silencio."""


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _det_id(prefix: str, *parts: object) -> str:
    """Id determinista: prefijo + primeros 16 hex del sha256 de las
    partes. Mismo contenido/posición ⇒ mismo id ⇒ re-extracción
    idempotente."""
    raw = "\x1f".join(str(p) for p in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


# ── Provenance ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Provenance:
    document_id: str
    page: int                      # 1-indexado, página real del documento
    source_text: str               # literal, nunca normalizado
    source_hash: str               # sha256 de source_text
    extraction_version: str
    section_numero: str | None = None
    section_titulo: str | None = None

    @staticmethod
    def build(document_id: str, page: int, source_text: str, *,
              section_numero: str | None = None,
              section_titulo: str | None = None,
              extraction_version: str = EXTRACTION_VERSION) -> "Provenance":
        p = Provenance(
            document_id=document_id, page=page, source_text=source_text,
            source_hash=sha256_text(source_text),
            extraction_version=extraction_version,
            section_numero=section_numero, section_titulo=section_titulo,
        )
        validate_provenance(p)
        return p


def validate_provenance(p: "Provenance | None") -> None:
    if p is None:
        raise ProvenanceError("provenance ausente")
    if not p.document_id:
        raise ProvenanceError("provenance.document_id vacío")
    if not isinstance(p.page, int) or p.page < 1:
        raise ProvenanceError(f"provenance.page inválida: {p.page!r} (debe ser int >= 1)")
    if not (p.source_text or "").strip():
        raise ProvenanceError("provenance.source_text vacío — sin evidencia anclada, no se persiste")
    if p.source_hash != sha256_text(p.source_text):
        raise ProvenanceError("provenance.source_hash no corresponde a source_text")
    if not p.extraction_version:
        raise ProvenanceError("provenance.extraction_version vacío")


# ── Documento y estructura ───────────────────────────────────────────────

@dataclass
class Document:
    document_id: str               # RW-XXXX u otro id de gobernanza
    sha256: str                    # sha256 del archivo original
    tipo: str                      # DOCUMENT_TYPES
    titulo: str
    n_paginas: int
    extraction_version: str = EXTRACTION_VERSION
    cliente: str | None = None
    archivo: str | None = None     # ruta local, solo lectura

    def __post_init__(self) -> None:
        if self.tipo not in DOCUMENT_TYPES:
            raise ValueError(f"Document.tipo inválido: {self.tipo!r}")
        if not self.document_id:
            raise ValueError("Document.document_id vacío")
        if self.n_paginas < 0:
            raise ValueError(f"Document.n_paginas inválido: {self.n_paginas}")


@dataclass
class Section:
    section_id: str
    document_id: str
    numero: str | None             # "1", "2"... None si el doc no tiene TOC parseable
    titulo: str | None
    pagina_inicio: int
    pagina_fin: int
    nivel: int = 1
    parent_section_id: str | None = None
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        validate_provenance(self.provenance)


@dataclass
class Table:
    table_id: str
    document_id: str
    pagina: int
    headers: list[str]
    rows: list[list[str]]
    merged_cells: list[dict] = field(default_factory=list)  # {"row":i,"col":j,"rowspan":r,"colspan":c}
    caption: str | None = None
    section_id: str | None = None
    #: columnas cuyo rol (actor/timestamp/old_value/new_value/...) no se
    #: pudo mapear de forma determinista. NUNCA se inventa un rol: se marca.
    columns_unmapped: list[int] = field(default_factory=list)
    #: mapeo columna_index -> rol semántico, solo para las que sí se
    #: resolvieron por heurística determinista.
    column_roles: dict = field(default_factory=dict)
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        validate_provenance(self.provenance)
        if self.rows and self.headers and any(len(r) != len(self.headers) for r in self.rows):
            # No es error: pdfplumber a veces devuelve filas irregulares.
            # Se registra normalizando a la anchura del header (celdas
            # faltantes -> "" al final; sobrantes -> se preservan).
            self.rows = [_pad_or_keep(r, len(self.headers)) for r in self.rows]


def _pad_or_keep(row: list[str], width: int) -> list[str]:
    if len(row) < width:
        return list(row) + [""] * (width - len(row))
    return list(row)


# ── Objetos de conocimiento ──────────────────────────────────────────────

@dataclass
class Claim:
    claim_id: str
    document_id: str
    section_id: str | None
    pagina: int
    source_text: str               # literal — la ÚNICA cita citable
    source_hash: str
    tipo: str                      # CLAIM_TYPES
    normalized_statement: str      # heurística en B1; NUNCA se usa como cita
    provenance: Provenance | None = None
    #: B1.2 -- identificador del requisito al que pertenece el claim
    #: (número jerárquico 3+ niveles o id formal tipo URS-PCS-SR-037),
    #: propio o HEREDADO de una línea anterior del mismo bloque de
    #: requisito. None si no se pudo determinar. NO es una cita citable.
    local_id: str | None = None

    def __post_init__(self) -> None:
        if self.tipo not in CLAIM_TYPES:
            raise ValueError(f"Claim.tipo inválido: {self.tipo!r}")
        if self.source_hash != sha256_text(self.source_text):
            raise ProvenanceError("Claim.source_hash no corresponde a source_text")
        validate_provenance(self.provenance)


@dataclass
class Control:
    control_id: str
    document_id: str
    categoria: str                 # CONTROL_CATEGORIES
    descripcion_operativa: str
    claim_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.categoria not in CONTROL_CATEGORIES:
            raise ValueError(f"Control.categoria inválida: {self.categoria!r}")


@dataclass
class Actor:
    actor_id: str
    document_id: str
    nombre_rol: str
    tipo: str                      # ACTOR_TYPES

    def __post_init__(self) -> None:
        if self.tipo not in ACTOR_TYPES:
            raise ValueError(f"Actor.tipo inválido: {self.tipo!r}")


@dataclass
class SystemComponent:
    component_id: str
    document_id: str
    nombre: str
    tipo: str                      # COMPONENT_TYPES
    version: str | None = None

    def __post_init__(self) -> None:
        if self.tipo not in COMPONENT_TYPES:
            raise ValueError(f"SystemComponent.tipo inválido: {self.tipo!r}")


@dataclass
class Test:
    test_id: str
    document_id: str
    section_id: str | None
    identificador: str             # "SAT-039", "OQ-12"...
    descripcion: str
    resultado: str | None = None   # "pass" | "fail" | None
    verifies_requirement_ids: list[str] = field(default_factory=list)
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        validate_provenance(self.provenance)


@dataclass
class Evidence:
    evidence_id: str
    document_id: str
    pagina: int
    source_text: str
    source_hash: str
    extraction_version: str
    claim_id: str | None = None
    table_id: str | None = None
    anchor_status: str = "pending"  # ANCHOR_STATUSES

    def __post_init__(self) -> None:
        if self.anchor_status not in ANCHOR_STATUSES:
            raise ValueError(f"Evidence.anchor_status inválido: {self.anchor_status!r}")
        if self.source_hash != sha256_text(self.source_text):
            raise ProvenanceError("Evidence.source_hash no corresponde a source_text")
        if not (self.claim_id or self.table_id):
            raise ProvenanceError("Evidence sin claim_id ni table_id — no ancla a nada")


# ── Constructores (aplican validación) ───────────────────────────────────

def build_section(document_id: str, numero: str | None, titulo: str | None,
                  pagina_inicio: int, pagina_fin: int, *, nivel: int = 1,
                  parent_section_id: str | None = None,
                  source_text: str = "") -> Section:
    prov = Provenance.build(
        document_id, pagina_inicio, source_text or (titulo or f"seccion-{numero}"),
        section_numero=numero, section_titulo=titulo,
    )
    return Section(
        section_id=_det_id("sec", document_id, numero, titulo, pagina_inicio),
        document_id=document_id, numero=numero, titulo=titulo,
        pagina_inicio=pagina_inicio, pagina_fin=pagina_fin, nivel=nivel,
        parent_section_id=parent_section_id, provenance=prov,
    )


def build_claim(document_id: str, pagina: int, source_text: str, tipo: str,
                normalized_statement: str, *, section_id: str | None = None,
                section_numero: str | None = None,
                section_titulo: str | None = None,
                local_id: str | None = None) -> Claim:
    prov = Provenance.build(
        document_id, pagina, source_text,
        section_numero=section_numero, section_titulo=section_titulo,
    )
    return Claim(
        claim_id=_det_id("clm", document_id, pagina, source_text),
        document_id=document_id, section_id=section_id, pagina=pagina,
        source_text=source_text, source_hash=sha256_text(source_text),
        tipo=tipo, normalized_statement=normalized_statement, provenance=prov,
        local_id=local_id,
    )


def build_table(document_id: str, pagina: int, headers: list[str],
                rows: list[list[str]], *, section_id: str | None = None,
                merged_cells: list[dict] | None = None, caption: str | None = None,
                column_roles: dict | None = None,
                columns_unmapped: list[int] | None = None,
                source_text: str = "") -> Table:
    st = source_text or _table_source_text(headers, rows)
    prov = Provenance.build(document_id, pagina, st)
    return Table(
        table_id=_det_id("tbl", document_id, pagina, st),
        document_id=document_id, pagina=pagina, headers=list(headers),
        rows=[list(r) for r in rows], merged_cells=list(merged_cells or []),
        caption=caption, section_id=section_id,
        column_roles=dict(column_roles or {}),
        columns_unmapped=list(columns_unmapped or []),
        provenance=prov,
    )


def build_test(document_id: str, pagina: int, identificador: str,
               descripcion: str, *, section_id: str | None = None,
               resultado: str | None = None,
               verifies_requirement_ids: list[str] | None = None,
               source_text: str = "") -> Test:
    prov = Provenance.build(document_id, pagina, source_text or descripcion)
    return Test(
        test_id=_det_id("tst", document_id, identificador),
        document_id=document_id, section_id=section_id,
        identificador=identificador, descripcion=descripcion, resultado=resultado,
        verifies_requirement_ids=list(verifies_requirement_ids or []),
        provenance=prov,
    )


def build_evidence(document_id: str, pagina: int, source_text: str, *,
                   claim_id: str | None = None, table_id: str | None = None,
                   anchor_status: str = "pending",
                   extraction_version: str = EXTRACTION_VERSION) -> Evidence:
    return Evidence(
        evidence_id=_det_id("evd", document_id, pagina, source_text, claim_id, table_id),
        document_id=document_id, pagina=pagina, source_text=source_text,
        source_hash=sha256_text(source_text), extraction_version=extraction_version,
        claim_id=claim_id, table_id=table_id, anchor_status=anchor_status,
    )


def _table_source_text(headers: list[str], rows: list[list[str]]) -> str:
    lines = [" | ".join(str(h) for h in headers)]
    lines += [" | ".join(str(c) for c in r) for r in rows]
    return "\n".join(lines)


def as_dict(obj) -> dict:
    """Serialización superficial para persistencia/JSON (Provenance
    anidada incluida)."""
    out = {}
    for f in fields(obj):
        v = getattr(obj, f.name)
        if isinstance(v, Provenance):
            out[f.name] = dict(v.__dict__)
        else:
            out[f.name] = v
    return out
