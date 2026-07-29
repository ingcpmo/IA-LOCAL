"""W5 V2, Fase A -- AGT-INV: inventario, procedencia, hashes, duplicados y
allowlist de un árbol de documentos originales (p.ej. GMPAI/source/Rockwell/).

Deliberadamente autocontenido: NO importa nada de
factory/workspaces/gmpai_document_validation/app/ (ese árbol está en
.gitignore -- ver factory/.gitignore 'workspaces/*', confirmado en la
auditoría CURRENT_AGENT_RUNTIME_AUDIT.md). Un script git-tracked no puede
depender de módulos que no existen en un checkout limpio. Reimplementa
localmente solo lo mínimo necesario (hash, extracción de muestreo,
detección de versión), con las mismas dependencias ya declaradas en
requirements.txt (pypdf, python-docx) más zipfile/XML de la stdlib para
XLSX/DOCM -- sin agregar dependencias nuevas.

Reglas duras aplicadas (ver ROCKWELL_SOURCE_INVENTORY_AND_SCOPE_SPEC.md):
- Solo lectura sobre el árbol fuente. Nunca escribe, mueve ni borra ahí.
- DOCM: jamás se ejecuta el proyecto VBA (word/vbaProject.bin no se abre).
- Todo archivo real del find aparece EXACTAMENTE una vez con un
  processing_state terminal -- test de cobertura obligatorio antes de
  escribir el YAML.
- doc_type se decide por reglas de nombre; cuando el CONTENIDO real
  contradice la regla de nombre (caso confirmado: T-039, ver
  _CONTENT_OVERRIDES abajo), la evidencia de contenido prevalece y se dice
  explícitamente por qué -- nunca se declara silenciosamente.
- applicability es SIEMPRE 'PENDING_AGT_APP_ASSIGNMENT' en esta fase; AGT-INV
  no decide aplicabilidad regulatoria (responsabilidad de AGT-APP, Fase B).

W5 V2 G1.10 -- CONSUMIDOR C-4 del DecisionScopeResolver
--------------------------------------------------------
El INVENTARIO no se gobierna: enumerar los ficheros que hay en un arbol es
solo lectura y no autoriza nada, asi que `build_allowlist()` sigue sin
consultar ninguna decision. Negarse a inventariar por falta de firma dejaria
a la fabrica sin saber siquiera QUE documentos existen, que es lo contrario
de lo que busca la gobernanza.

Lo que si se gobierna es la BASELINE FORMAL: `classify_baseline_eligibility()`
separa lo que puede sustentar una conclusion formal de lo que solo entra a la
baseline provisional CON SU LIMITACION DECLARADA. Exige dos coberturas
distintas:

  D3 sobre el `file_id` del documento    -- alguien firmo su clasificacion
  D1 sobre CADA fuente regulatoria       -- alguien firmo que esas normas se
                                            usen

La segunda es por documento pero no del documento: una baseline formal se
apoya en las fuentes regulatorias, asi que si alguna no esta cubierta, NINGUN
documento puede sustentar una conclusion formal por impecable que sea su
propia clasificacion.

Se anade como CONSULTA, no como campo nuevo del YAML: ese artefacto esta
gobernado por `source_baseline_allowlist_entry_v1` con
`additionalProperties:false`, y meterle campos derivados de un estado que
cambia con cada decision lo volveria un dato mutable disfrazado de inventario.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

import yaml

from factory.core import decision_scope_resolver as _resolver

_WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

_VERSION_RE = re.compile(r"(?<![a-zA-Z])v(\d+(?:\.\d+)?)\b", re.IGNORECASE)
_REV_RE = re.compile(r"(?<![a-zA-Z])rev\s*([a-h0-9]{1,2})\b", re.IGNORECASE)

# Umbral empírico (ver evidencia real en ROCKWELL_SOURCE_INVENTORY_AND_SCOPE_SPEC.md):
# archivos con prosa real superan largamente 1800 chars/página muestreada;
# un set de planos/drawings sin capa de texto da <5 chars/página muestreada.
_OCR_CHARS_PER_PAGE_THRESHOLD = 20
_PDF_SAMPLE_MAX_PAGES = 5


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sample_pdf_pages(path: Path) -> tuple[int, int]:
    """Retorna (chars_muestreados, paginas_muestreadas). Muestrea como
    máximo _PDF_SAMPLE_MAX_PAGES páginas (primera, última y equiespaciadas)
    en vez de extraer el documento completo -- necesario porque un PDF de
    planos/escaneado sin capa de texto puede tardar decenas de segundos por
    página en pypdf incluso devolviendo 0 caracteres (confirmado real:
    25s para 24 páginas en el corpus de esta corrida)."""
    import pypdf
    reader = pypdf.PdfReader(str(path))
    n = len(reader.pages)
    if n == 0:
        return (0, 0)
    if n <= _PDF_SAMPLE_MAX_PAGES:
        idxs = list(range(n))
    else:
        step = (n - 1) / (_PDF_SAMPLE_MAX_PAGES - 1)
        idxs = sorted({round(i * step) for i in range(_PDF_SAMPLE_MAX_PAGES)})
    total_chars = 0
    for i in idxs:
        total_chars += len(reader.pages[i].extract_text() or "")
    return (total_chars, len(idxs))


def _extract_docx_chars(path: Path) -> int:
    import docx as python_docx
    d = python_docx.Document(str(path))
    paras = [p.text for p in d.paragraphs]
    return sum(len(p) for p in paras)


def _extract_docm_chars_safe(path: Path) -> int:
    """Lee word/document.xml directo del ZIP OOXML. word/vbaProject.bin
    JAMÁS se abre ni se ejecuta -- solo se confirma su existencia si aplica,
    nunca se lee su contenido."""
    with zipfile.ZipFile(path) as z:
        with z.open("word/document.xml") as f:
            tree = ET.parse(f)
    total = 0
    for p_el in tree.getroot().iter(f"{{{_WORD_NS['w']}}}p"):
        for t in p_el.iter(f"{{{_WORD_NS['w']}}}t"):
            total += len(t.text or "")
    return total


def extraction_capability_for(path: Path) -> tuple[str, str]:
    """Retorna (extraction_capability, nota). Reglas deterministas por
    formato; PDF se decide por muestreo real (ver _sample_pdf_pages)."""
    ext = path.suffix.lower()
    if ext == ".xlsx":
        return ("TEXT_NATIVE", "formato estructurado (hojas/celdas), siempre extraíble")
    if ext == ".docx":
        chars = _extract_docx_chars(path)
        return ("TEXT_NATIVE", f"extracción OOXML directa, {chars} chars")
    if ext == ".docm":
        chars = _extract_docm_chars_safe(path)
        return ("TEXT_NATIVE", f"extracción OOXML directa sin ejecutar macro, {chars} chars")
    if ext == ".pdf":
        chars, sampled_pages = _sample_pdf_pages(path)
        avg = chars / max(sampled_pages, 1)
        if avg < _OCR_CHARS_PER_PAGE_THRESHOLD:
            return ("OCR_REQUIRED", f"muestreo de {sampled_pages} páginas: {avg:.1f} chars/página promedio (<{_OCR_CHARS_PER_PAGE_THRESHOLD})")
        return ("TEXT_NATIVE", f"muestreo de {sampled_pages} páginas: {avg:.1f} chars/página promedio")
    return ("NOT_EXTRACTABLE", f"extensión '{ext}' fuera de PDF/DOCX/DOCM/XLSX")


def detect_version(filename: str) -> str:
    m = _VERSION_RE.search(filename)
    if m:
        return f"v{m.group(1)}"
    m = _REV_RE.search(filename)
    if m:
        return f"Rev{m.group(1).upper()}"
    return "NO_DISPONIBLE"


# ── Clasificación por nombre (reglas genéricas, reutilizables) ──────────────

_FILENAME_DOC_TYPE_RULES: list[tuple[str, str]] = [
    (r"\burs\b", "URS"),
    (r"\bfs[_\s]?v?\d", "FS"),
    (r"\bfunctional spec", "FS"),
    (r"\bdesign docs?\b", "DS"),
    (r"sys[_\s]?arch|\barchitecture\b", "DRAWING"),
    (r"\bpanel\b", "DRAWING"),
    (r"\bnarrative\b", "DS"),
    (r"\bsat\d?\b.*completed|\bcompleted\b.*\bsat\d?\b", "REPORT"),
    (r"\bsat\d?\b", "REPORT"),
]


def classify_by_filename(filename: str) -> tuple[str, str]:
    """(doc_type, basis). 'OTHER' con basis explícita si ninguna regla aplica."""
    name = filename.lower()
    for pattern, doc_type in _FILENAME_DOC_TYPE_RULES:
        if re.search(pattern, name, re.IGNORECASE):
            return (doc_type, f"nombre coincide con /{pattern}/")
    return ("OTHER", "sin coincidencia de nombre -- requiere revisión")


# ── Excepciones respaldadas por evidencia de contenido real (Fase A) ────────
#
# T-039 (.docm y .pdf): la regla de nombre clasifica "Design Docs" -> DS, pero
# el CONTENIDO real extraído (ambos archivos, verificado en esta corrida)
# es una hoja de TRANSMITTAL ("Outgoing Transmittal... Transmittal Number:
# MAVERICK/215115305 / 039", fecha 2023-03-27) que acompaña el envío de
# 'MCCPDC PCS-CP01 Alarms Hard Soft IO Listing revH.xlsx' -- no es en sí
# mismo una especificación de diseño. La evidencia de contenido prevalece
# sobre la heurística de nombre.
_CONTENT_OVERRIDES: dict[str, tuple[str, str]] = {
    "215115305-T-039 Design Docs for ASantiago.docm": (
        "OTHER",
        "Contenido real es una hoja de TRANSMITTAL (Transmittal Number "
        "MAVERICK/215115305 / 039, 2023-03-27) que acompaña el envío del "
        "XLSX de alarmas/IO -- NO es una especificación de diseño pese al "
        "nombre 'Design Docs'. Verificado por extracción real del "
        "documento en esta corrida (Fase A).",
    ),
    "215115305-T-039 Design Docs for ASantiago.pdf": (
        "OTHER",
        "Mismo transmittal (mismo Transmittal Number y fecha) que la "
        "contraparte .docm, pero con SHA-256 distinto -- no es duplicado "
        "exacto. Contenido con el mismo transmittal number sugiere que es "
        "una renderización/impresión del .docm, pero el hash distinto no "
        "lo confirma por sí solo; ver HUMAN_REVIEW_REQUIRED en origin_class.",
    ),
}


@dataclass
class AllowlistEntry:
    file_id: str
    path: str
    name: str
    extension: str
    version: str
    size_bytes: int
    sha256: str
    provenance: str
    doc_type: str
    origin_class: str
    duplicate_of: str | None
    extraction_capability: str
    processing_state: str
    applicability: str
    related_requirements: list[str] = field(default_factory=list)
    justification: str | None = None


def load_manifest(manifest_path: Path, manifest_root: Path) -> dict[str, str]:
    """path relativo (con prefijo, p.ej. 'source/Rockwell/...') -> sha256."""
    out: dict[str, str] = {}
    if not manifest_path.exists():
        return out
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = line.rstrip("\n")
        if not line.strip():
            continue
        h, _, p = line.partition("  ")
        if not p:
            h, _, p = line.partition(" ")
        out[p.strip()] = h.strip()
    return out


def build_allowlist(
    source_dir: Path,
    manifest_path: Path | None = None,
    manifest_root: Path | None = None,
) -> list[AllowlistEntry]:
    """Construye el allowlist completo, en solo-lectura sobre source_dir.
    Regla dura: cada archivo real aparece EXACTAMENTE una vez."""
    manifest = load_manifest(manifest_path, manifest_root) if manifest_path else {}
    root = manifest_root if manifest_root is not None else source_dir.parent

    files = sorted(p for p in source_dir.rglob("*") if p.is_file())

    # Primera pasada: hash de todos para detectar duplicados exactos.
    hashes: dict[Path, str] = {p: sha256_file(p) for p in files}
    by_hash: dict[str, list[Path]] = {}
    for p, h in hashes.items():
        by_hash.setdefault(h, []).append(p)
    # Dentro de cada grupo de duplicados exactos, el canónico es el nombre
    # SIN sufijo numérico de copia (p.ej. 'FS_v1.2.pdf' sobre
    # 'FS_v1.2-2.pdf') -- el orden alfabético puro pondría '-2' primero
    # ('-' < '.' en ASCII), que sería el resultado contrario al esperado.
    _dup_suffix_re = re.compile(r"-\d+(?=\.[^.]+$)")
    for h, paths in by_hash.items():
        if len(paths) > 1:
            paths.sort(key=lambda p: (bool(_dup_suffix_re.search(p.name)), p.name))

    entries: list[AllowlistEntry] = []
    file_id_by_path: dict[Path, str] = {}
    for i, p in enumerate(files, start=1):
        file_id_by_path[p] = f"RW-{i:04d}"

    for p in files:
        file_id = file_id_by_path[p]
        h = hashes[p]
        rel_for_manifest = str(p.relative_to(root))
        manifest_hash = manifest.get(rel_for_manifest)

        if manifest_hash is not None and manifest_hash == h:
            provenance = f"confirmado contra manifiesto {manifest_path.name} (hash coincide)"
        elif manifest_hash is not None:
            provenance = f"NO_DISPONIBLE -- hash NO coincide con {manifest_path.name}"
        else:
            provenance = "NO_DISPONIBLE -- sin entrada en manifiesto"

        doc_type, basis = classify_by_filename(p.name)
        override = _CONTENT_OVERRIDES.get(p.name)
        justification_parts: list[str] = []
        if override:
            doc_type, override_reason = override
            justification_parts.append(override_reason)
        else:
            justification_parts.append(f"doc_type por regla de nombre: {basis}")

        extraction_capability, extraction_note = extraction_capability_for(p)
        justification_parts.append(f"extraction_capability: {extraction_note}")

        version = detect_version(p.name)

        dup_group = by_hash[h]
        is_duplicate_non_canonical = len(dup_group) > 1 and dup_group[0] != p
        duplicate_of = file_id_by_path[dup_group[0]] if is_duplicate_non_canonical else None

        origin_class = "ORIGINAL"
        processing_state: str
        if is_duplicate_non_canonical:
            processing_state = "DUPLICATE"
            justification_parts.append(
                f"SHA-256 idéntico a {duplicate_of} ({dup_group[0].name}) -- "
                "copia redundante, no una versión distinta."
            )
        elif extraction_capability == "OCR_REQUIRED":
            processing_state = "OCR_REQUIRED"
        elif p.name in _CONTENT_OVERRIDES and p.suffix.lower() == ".pdf":
            # T-039 PDF: mismo transmittal que el .docm pero hash distinto,
            # relación no confirmada automáticamente -- requiere revisión humana.
            processing_state = "HUMAN_REVIEW_REQUIRED"
        elif manifest_hash is not None and manifest_hash != h:
            processing_state = "ORIGINAL_SOURCE_UNCONFIRMED"
            justification_parts.append("hash no coincide con el manifiesto gobernado")
        else:
            processing_state = "ORIGINAL_SOURCE_CONFIRMED"

        entries.append(AllowlistEntry(
            file_id=file_id,
            path=rel_for_manifest,
            name=p.name,
            extension=p.suffix.lower(),
            version=version,
            size_bytes=p.stat().st_size,
            sha256=h,
            provenance=provenance,
            doc_type=doc_type,
            origin_class=origin_class,
            duplicate_of=duplicate_of,
            extraction_capability=extraction_capability,
            processing_state=processing_state,
            applicability="PENDING_AGT_APP_ASSIGNMENT",
            related_requirements=[],
            justification="; ".join(justification_parts) if justification_parts else None,
        ))

    return entries


def verify_coverage(source_dir: Path, entries: list[AllowlistEntry]) -> None:
    """Gate determinista obligatorio: count(find) == count(allowlist), sin
    omisiones silenciosas. Levanta AssertionError si falla -- nunca degrada."""
    real_files = sorted(p for p in source_dir.rglob("*") if p.is_file())
    if len(real_files) != len(entries):
        raise AssertionError(
            f"Cobertura incompleta: {len(real_files)} archivos reales vs. "
            f"{len(entries)} entradas en el allowlist -- 0 omisiones permitidas."
        )
    entry_names = {e.name for e in entries}
    real_names = {p.name for p in real_files}
    missing = real_names - entry_names
    if missing:
        raise AssertionError(f"Archivos omitidos del allowlist: {sorted(missing)}")


# ---------------------------------------------------------------------------
# C-4 -- elegibilidad para la BASELINE FORMAL
# ---------------------------------------------------------------------------

FORMAL = "FORMAL_BASELINE_ELIGIBLE"
PROVISIONAL = "PROVISIONAL_ONLY"


@dataclass(frozen=True)
class BaselineEligibility:
    file_id: str
    eligibility: str                 # FORMAL | PROVISIONAL
    document_decision_authorized: bool
    regulatory_sources_authorized: bool
    uncovered_source_ids: tuple[str, ...]
    declared_limitations: tuple[str, ...]

    @property
    def formal(self) -> bool:
        return self.eligibility == FORMAL


def classify_baseline_eligibility(
    file_ids,
    regulatory_source_ids,
    *,
    decision_store_file: Path | None = None,
) -> list[BaselineEligibility]:
    """Separa lo que puede sustentar una conclusion FORMAL de lo que solo
    entra a la baseline PROVISIONAL con su limitacion declarada.

    Nunca excluye en silencio: lo no cubierto sigue en la lista, marcado
    PROVISIONAL y con el motivo escrito. Una baseline a la que le faltan
    documentos sin explicacion es peor que una que declara sus limites.
    """
    source_results = {
        sid: _resolver.resolve("D1", sid, store_file=decision_store_file)
        for sid in sorted(set(regulatory_source_ids))
    }
    uncovered_sources = tuple(
        sid for sid, r in sorted(source_results.items()) if not r.authorized)
    sources_ok = not uncovered_sources

    out = []
    for file_id in file_ids:
        doc = _resolver.resolve("D3", file_id, store_file=decision_store_file)
        limitations = []
        if not doc.authorized:
            limitations.append(f"D3/{file_id}: {doc.denial_reason}")
        for sid in uncovered_sources:
            limitations.append(f"D1/{sid}: {source_results[sid].denial_reason}")

        out.append(BaselineEligibility(
            file_id=file_id,
            eligibility=FORMAL if (doc.authorized and sources_ok) else PROVISIONAL,
            document_decision_authorized=doc.authorized,
            regulatory_sources_authorized=sources_ok,
            uncovered_source_ids=uncovered_sources,
            declared_limitations=tuple(limitations),
        ))
    return out


def entries_to_yaml_dict(entries: list[AllowlistEntry]) -> list[dict]:
    return [
        {
            "file_id": e.file_id,
            "path": e.path,
            "name": e.name,
            "extension": e.extension,
            "version": e.version,
            "size_bytes": e.size_bytes,
            "sha256": e.sha256,
            "provenance": e.provenance,
            "doc_type": e.doc_type,
            "origin_class": e.origin_class,
            "duplicate_of": e.duplicate_of,
            "extraction_capability": e.extraction_capability,
            "processing_state": e.processing_state,
            "applicability": e.applicability,
            "related_requirements": e.related_requirements,
            "justification": e.justification,
        }
        for e in entries
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-dir", type=Path, default=Path("/home/ing_cpmo/GMPAI/source/Rockwell"))
    ap.add_argument("--manifest", type=Path, default=Path("/home/ing_cpmo/GMPAI/manifests/SHA256SUMS.txt"))
    ap.add_argument("--manifest-root", type=Path, default=Path("/home/ing_cpmo/GMPAI"))
    ap.add_argument("--out", type=Path, default=Path("factory/regulatory/scope/source_baseline_allowlist.yaml"))
    args = ap.parse_args()

    entries = build_allowlist(args.source_dir, args.manifest, args.manifest_root)
    verify_coverage(args.source_dir, entries)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = entries_to_yaml_dict(entries)
    args.out.write_text(
        "# W5 V2, Fase A -- generado por build_source_baseline_allowlist.py\n"
        "# Solo lectura sobre el árbol fuente; NUNCA modifica originales.\n"
        + yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    print(f"OK: {len(entries)} entradas escritas en {args.out}")

    # El inventario no depende de decisiones, pero quien lo genera debe ver el
    # estado REAL de la baseline formal -- no descubrirlo al intentar liberar.
    try:
        from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
            known_source_ids,
        )
        classification = classify_baseline_eligibility(
            [e.file_id for e in entries], known_source_ids())
    except Exception as exc:  # noqa: BLE001 -- informativo; nunca tumba el build
        print(f"AVISO: no se pudo clasificar la baseline ({type(exc).__name__}: {exc})")
        return

    formal = [c for c in classification if c.formal]
    print(f"  baseline formal elegible : {len(formal)}/{len(classification)}")
    if not formal:
        uncovered = classification[0].uncovered_source_ids if classification else ()
        print("  NINGUN documento puede sustentar una conclusion formal todavia.")
        if uncovered:
            print(f"  fuentes regulatorias sin cobertura D1: {list(uncovered)}")


if __name__ == "__main__":
    main()
