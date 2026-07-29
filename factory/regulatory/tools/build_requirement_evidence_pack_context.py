"""W5 V2, Fase C -- AGT-REP (parcial): backfill mecánico de context_before/
context_after sobre las 19 entradas ya gobernadas de
factory/regulatory/requirement_catalog/requirements.yaml.

Alcance EXPLÍCITAMENTE acotado (decisión de Capa 9, 2026-07-23): solo se
generan automáticamente los campos MECÁNICOS del Requirement Evidence Pack
(context_before, context_after, pack_version, evidence_pack_status). Los
campos interpretativos (evidence_min_criteria, exclusion_criteria,
weak_keywords, typical_insufficient_evidence, governed_interpretation,
expected_doc_types) NUNCA se generan aquí -- requieren juicio regulatorio
humano y quedan ausentes, marcados por evidence_pack_status=
'structure_only_pending_human_interpretation'.

Método de extracción: localiza citation_text dentro del texto COMPLETO ya
extraído del documento canónico gobernado (sin descargar ni re-extraer
nada nuevo):
  - fuente .txt (eCFR): lectura directa del archivo canónico.
  - fuente .pdf (Annex 11, MHRA): usa el derived_artifact pdfplumber ya
    gobernado en registry.json (mismo extractor con el que se generó la
    cita original -- no se re-extrae con un método distinto que podría
    tokenizar distinto).

La búsqueda es por texto NORMALIZADO (espacios/saltos de línea colapsados
a un único espacio) porque el texto de página conserva saltos de línea que
citation_text no tiene; se mapea el índice normalizado de vuelta al índice
real del texto original para poder recortar el contexto real (nunca se
inventa ni se reconstruye texto -- se recorta lo que ya está ahí)."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

CATALOG_DIR = Path("factory/regulatory/requirement_catalog")
REQUIREMENTS_PATH = CATALOG_DIR / "requirements.yaml"
REGISTRY_PATH = Path("factory/regulatory/sources/registry.json")

CONTEXT_CHARS = 300
PACK_VERSION = "1.0"
EVIDENCE_PACK_STATUS = "structure_only_pending_human_interpretation"


def _normalize_with_mapping(text: str) -> tuple[str, list[int]]:
    """Colapsa cada corrida de espacio/salto de linea a un solo ' '.
    mapping[i] = indice en `text` del caracter normalizado en posicion i."""
    out: list[str] = []
    mapping: list[int] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            out.append(" ")
            mapping.append(i)
            while i < n and text[i].isspace():
                i += 1
        else:
            out.append(c)
            mapping.append(i)
            i += 1
    return "".join(out), mapping


#: Extractores gobernados cuyos artefactos derivados sirven como texto
#: completo. `ecfr_xml` se anadio con la ingesta de Part 211 (2026-07-29):
#: su copia canonica es XML, formato que ni la rama .txt ni pdfplumber
#: cubrian, de modo que la fuente era ilegible para este constructor.
_SUPPORTED_EXTRACTORS = ("pdfplumber", "ecfr_xml")


def _load_source_full_text(source_entry: dict) -> str:
    canonical_path = Path(source_entry["canonical_path"])
    if canonical_path.suffix == ".txt":
        return canonical_path.read_text(encoding="utf-8")
    artifacts = source_entry.get("derived_artifacts", [])
    for extractor in _SUPPORTED_EXTRACTORS:
        for artifact in artifacts:
            if artifact["extractor"] == extractor:
                data = json.loads(Path(artifact["artifact_path"]).read_text(encoding="utf-8"))
                return "\n".join(data["pages"])
    found = sorted({a["extractor"] for a in artifacts}) or ["ninguno"]
    raise ValueError(
        f"sin texto completo disponible para source_id={source_entry['source_id']} "
        f"(canonico {canonical_path.suffix or 'sin extension'}, extractores presentes: "
        f"{found}; soportados: {list(_SUPPORTED_EXTRACTORS)})"
    )


def find_context(full_text: str, citation_text: str, context_chars: int = CONTEXT_CHARS) -> tuple[str, str]:
    """Retorna (context_before, context_after) reales, o ('', '') con nota
    si la cita no se pudo localizar por busqueda normalizada -- nunca
    inventa contexto."""
    norm_full, mapping = _normalize_with_mapping(full_text)
    norm_needle, _ = _normalize_with_mapping(citation_text)
    idx = norm_full.find(norm_needle)
    if idx == -1:
        return ("", "")
    start = mapping[idx]
    end = mapping[idx + len(norm_needle) - 1] + 1
    context_before = full_text[max(0, start - context_chars):start]
    context_after = full_text[end:end + context_chars]
    return (context_before, context_after)


def backfill(requirements_path: Path = REQUIREMENTS_PATH, registry_path: Path = REGISTRY_PATH) -> dict:
    catalog = yaml.safe_load(requirements_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    sources_by_id = {s["source_id"]: s for s in registry["sources"]}

    not_found: list[str] = []
    for req_id, entry in catalog["requirements"].items():
        source_entry = sources_by_id.get(entry["source_id"])
        if source_entry is None:
            raise ValueError(f"{req_id}: source_id {entry['source_id']!r} no existe en registry.json")
        full_text = _load_source_full_text(source_entry)
        context_before, context_after = find_context(full_text, entry["citation"]["citation_text"])
        if not context_before and not context_after:
            not_found.append(req_id)
        entry["context_before"] = context_before
        entry["context_after"] = context_after
        entry["pack_version"] = PACK_VERSION
        entry["evidence_pack_status"] = EVIDENCE_PACK_STATUS

    if not_found:
        raise ValueError(
            f"citation_text no localizado (ni exacto ni normalizado) para: {not_found} "
            "-- revisar manualmente antes de continuar, no se escribe contexto vacio en silencio."
        )
    return catalog


def main() -> None:
    catalog = backfill()
    text = yaml.safe_dump(catalog, sort_keys=False, allow_unicode=True, width=100)
    REQUIREMENTS_PATH.write_text(text, encoding="utf-8")
    print(f"OK: {len(catalog['requirements'])} requisitos con context_before/after en {REQUIREMENTS_PATH}")


if __name__ == "__main__":
    main()
