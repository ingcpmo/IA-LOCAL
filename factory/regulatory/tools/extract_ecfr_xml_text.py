"""Extractor de texto para fuentes canonicas eCFR en XML (W5 V2, paso 3).

Por que existe: `build_requirement_evidence_pack_context._load_source_full_text`
solo sabe leer un `.txt` canonico o un `derived_artifact` de pdfplumber. La
fuente `ecfr_21cfr_part211` ingerida el 2026-07-29 es XML, asi que hoy ese
lector lanza excepcion y NINGUNA cita puede anclarse contra Part 211. Este
modulo produce el artefacto derivado que faltaba, con el mismo contrato que
los de pdfplumber (mismas claves, mismo registro en `derived_artifacts`).

Reglas que hereda del resto del modulo regulatorio:

  - El XML canonico NUNCA se sustituye: sigue siendo `canonical_path`. Esto
    es un artefacto DERIVADO, como dice el schema.
  - No se reescribe, reordena ni normaliza el texto normativo: se concatena
    el contenido textual de los nodos en orden de documento. Lo unico que se
    anade son saltos de linea entre bloques, para que las secciones no queden
    pegadas y la busqueda por contexto encuentre fronteras reales.
  - `_SUBSTITUTE_DATE_` (72 ocurrencias en Part 211) vive en atributos
    `hierarchy_metadata`, no en el texto; al extraer solo texto de nodos,
    no contamina la extraccion. No se toca ni se sustituye por nada: inventar
    una fecha ahi seria fabricar procedencia.
  - Determinista: mismo XML de entrada -> mismo `extracted_text_sha256`.

Unidad de "pagina": un XML de eCFR no tiene paginas. Se usa **una entrada por
seccion** (`DIV8`), que es la unidad de cita real del CFR (`§ 211.68`), mas una
entrada inicial con el encabezado de la parte. `page_count` cuenta esas
unidades; llamarlas paginas seria mentir, y por eso el artefacto declara
ademas `unit="section"`.
"""
from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

EXTRACTOR = "ecfr_xml"
EXTRACTOR_VERSION = "1.0"

REGISTRY_PATH = Path(__file__).parent.parent / "sources" / "registry.json"
DERIVED_DIR = Path(__file__).parent.parent / "sources" / "derived"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

#: Etiquetas cuyo contenido textual NO es texto normativo del cuerpo.
#: `hierarchy_metadata` es un atributo, no una etiqueta, y por eso no aparece.
_SKIPPED_TAGS = frozenset({"EDNOTE", "FTNT"})


class EcfrXmlExtractionError(Exception):
    pass


def _node_text(node: ET.Element) -> str:
    """Texto de un nodo en orden de documento, sin reescribir nada."""
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in node:
        if child.tag not in _SKIPPED_TAGS:
            parts.append(_node_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _collapse(text: str) -> str:
    """Colapsa espacios dentro de una linea pero conserva los saltos: el
    XML trae saltos de linea de formato dentro de un mismo parrafo."""
    return "\n".join(" ".join(line.split()) for line in text.splitlines()).strip()


def extract_units(xml_path: Path) -> list[str]:
    """Una unidad por seccion (DIV8), precedida por el encabezado de la parte.

    Si el documento no tuviera ninguna DIV8, se devuelve el documento entero
    como unidad unica en vez de fallar en silencio con una lista vacia.
    """
    root = ET.parse(xml_path).getroot()
    sections = root.findall(".//DIV8")

    header_parts: list[str] = []
    for tag in ("HEAD", "AUTH", "SOURCE"):
        node = root.find(tag)
        if node is not None:
            header_parts.append(_collapse(_node_text(node)))
    header = "\n".join(p for p in header_parts if p)

    if not sections:
        whole = _collapse(_node_text(root))
        if not whole:
            raise EcfrXmlExtractionError(f"{xml_path} no produjo texto extraible")
        return [whole]

    units = [header] if header else []
    for section in sections:
        text = _collapse(_node_text(section))
        if text:
            units.append(text)
    if not units:
        raise EcfrXmlExtractionError(f"{xml_path} no produjo texto extraible")
    return units


def build_artifact(source_entry: dict, xml_path: Path) -> dict:
    units = extract_units(xml_path)
    joined = "\n".join(units)
    return {
        "source_id": source_entry["source_id"],
        "source_sha256": source_entry["sha256_copy"],
        "extractor": EXTRACTOR,
        "extractor_version": EXTRACTOR_VERSION,
        "extraction_params": {"unit": "section", "skipped_tags": sorted(_SKIPPED_TAGS)},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "page_count": len(units),
        "extracted_text_sha256": hashlib.sha256(joined.encode("utf-8")).hexdigest(),
        "pages": units,
    }


def extract_and_register(source_id: str, registry_path: Path = REGISTRY_PATH) -> dict:
    """Extrae y registra el artefacto derivado en `derived_artifacts`.

    Fail-closed: verifica que el XML canonico en disco sigue teniendo el
    `sha256_copy` declarado ANTES de extraer nada. Extraer de un fichero que
    ya no es el gobernado produciria un artefacto derivado de algo distinto
    a la fuente, que es justo lo que el registro de hashes existe para evitar.
    """
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    entry = next((s for s in registry["sources"] if s["source_id"] == source_id), None)
    if entry is None:
        raise EcfrXmlExtractionError(f"source_id={source_id!r} no existe en el registry")

    canonical = REPO_ROOT / entry["canonical_path"]
    if not canonical.is_file():
        raise EcfrXmlExtractionError(f"copia canonica no encontrada: {canonical}")

    real_sha256 = hashlib.sha256(canonical.read_bytes()).hexdigest()
    if real_sha256 != entry["sha256_copy"]:
        raise EcfrXmlExtractionError(
            f"el fichero canonico de {source_id!r} ya no coincide con sha256_copy "
            f"({real_sha256} != {entry['sha256_copy']}) -- extraccion abortada"
        )

    if any(a["extractor"] == EXTRACTOR for a in entry.get("derived_artifacts", [])):
        raise EcfrXmlExtractionError(
            f"{source_id!r} ya tiene un derived_artifact de {EXTRACTOR!r} -- "
            "los artefactos derivados no se sobrescriben"
        )

    artifact = build_artifact(entry, canonical)

    artifact_dir = DERIVED_DIR / entry["sha256_copy"]
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{EXTRACTOR}_extraction_v1.json"
    payload = json.dumps(artifact, indent=2, ensure_ascii=False) + "\n"
    artifact_path.write_text(payload, encoding="utf-8")

    entry.setdefault("derived_artifacts", []).append({
        "extractor": EXTRACTOR,
        "extractor_version": EXTRACTOR_VERSION,
        "source_sha256": entry["sha256_copy"],
        "extraction_params": artifact["extraction_params"],
        "artifact_path": str(artifact_path.resolve().relative_to(REPO_ROOT)),
        "artifact_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
    })

    tmp_path = registry_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp_path.replace(registry_path)

    return {
        "source_id": source_id,
        "artifact_path": str(artifact_path),
        "units": artifact["page_count"],
        "extracted_text_sha256": artifact["extracted_text_sha256"],
    }
