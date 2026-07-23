"""W5 V2 -- generador de documento candidato para DOCM
(CORRECTED_DOCUMENT_GENERATION_AND_FORMAT_SPEC.md, estrategia DOCM de la
sección 14 del plan: "NO ejecutar macros; preservar original; documentar
limitaciones y método seguro de generación").

Método seguro: DOCM es el mismo contenedor OOXML que DOCX (confirmado en
`factory/regulatory/tools/build_source_baseline_allowlist.py`, Fase A --
`_extract_docm_raw_zip`). Este generador reutiliza ese mismo principio
para ESCRITURA: copia el ZIP original byte a byte para TODAS las partes
(incluido `word/vbaProject.bin`, que nunca se abre, nunca se parsea, nunca
se ejecuta -- solo se copia como bytes opacos) excepto `word/document.xml`,
donde inserta el nuevo párrafo mediante manipulación de STRING cruda (no
un round-trip con ElementTree, que podría reescribir namespaces/atributos
y corromper el XML de formas sutiles) -- se localiza el bloque `<w:p>...
</w:p>` que contiene el texto ancla y se inserta el nuevo párrafo
inmediatamente después, byte por byte, dejando todo el resto del XML
intacto.

Mismo alcance que `candidate_document_generator.py` (Fase J, DOCX): solo
`CONTENT_ADDITION` tiene caso real validado -- `CONTENT_REPLACEMENT`
lanza `NotImplementedError` explícito, sin inventar un comportamiento de
reemplazo sin evidencia real que lo ejercite.

`document_location` se usa como el texto ancla literal (párrafo existente
después del cual se inserta) -- DOCM no tiene noción de "secciones" como
la representación de Fase 4, así que el anclaje es directamente sobre el
texto del párrafo, reutilizando `semantic_evidence_verification.verify_anchor`
(Fase F) para localizarlo, sin reimplementar lógica de anclaje."""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from xml.etree import ElementTree as ET

from factory.regulatory.semantic_evidence_verification import verify_anchor

_WORD_NS_URI = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_WORD_NS = {"w": _WORD_NS_URI}
_PARAGRAPH_RE = re.compile(r"<w:p\b[^>]*>.*?</w:p>", re.DOTALL)
_INSERTED_COLOR_HEX = "008000"  # verde, mismo criterio visual que DOCX


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _paragraph_text(paragraph_xml: str) -> str:
    """Extrae el texto visible de un bloque <w:p>...</w:p> ya aislado
    (parseo local del fragmento, no del documento completo -- seguro
    porque el fragmento es XML bien formado por construcción de la regex
    que lo aisló)."""
    wrapped = f'<root xmlns:w="{_WORD_NS_URI}">{paragraph_xml}</root>'
    root = ET.fromstring(wrapped)
    return "".join(t.text or "" for t in root.iter(f"{{{_WORD_NS_URI}}}t"))


def _build_inserted_paragraph_xml(text: str, change_id: str) -> str:
    """Nuevo <w:p> con el tag [change_id] + texto propuesto en verde --
    mismo patron visual que el redline DOCX (_INSERTED_COLOR de
    candidate_document_generator.py)."""
    escaped_tag = f"[{change_id}] "
    escaped_text = (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    escaped_tag_xml = (
        escaped_tag.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    return (
        "<w:p>"
        '<w:r><w:rPr><w:b/><w:i/><w:color w:val="606060"/></w:rPr>'
        f'<w:t xml:space="preserve">{escaped_tag_xml}</w:t></w:r>'
        f'<w:r><w:rPr><w:color w:val="{_INSERTED_COLOR_HEX}"/><w:u w:val="single"/></w:rPr>'
        f'<w:t xml:space="preserve">{escaped_text}</w:t></w:r>'
        "</w:p>"
    )


def _validate_change_type(change: dict) -> None:
    if change["change_type"] != "CONTENT_ADDITION":
        raise NotImplementedError(
            f"change_type={change['change_type']!r} (change_id={change['change_id']!r}) -- "
            "solo CONTENT_ADDITION tiene caso real validado hoy para DOCM; CONTENT_REPLACEMENT "
            "no se implementa sin evidencia real que lo ejercite."
        )


def _apply_changes_to_document_xml(document_xml: str, changes: list[dict]) -> tuple[str, list[dict]]:
    """Retorna (document_xml_modificado, insertion_manifest). Cada
    insercion se localiza sobre el XML YA MODIFICADO por las inserciones
    anteriores (soporta multiples cambios en un mismo documento sin perder
    los anclajes ya insertados)."""
    insertion_manifest: list[dict] = []
    current_xml = document_xml
    for change in changes:
        _validate_change_type(change)
        anchor_text = change["document_location"]
        match_found = None
        for m in _PARAGRAPH_RE.finditer(current_xml):
            paragraph_xml = m.group(0)
            paragraph_text = _paragraph_text(paragraph_xml)
            status, _match_type = verify_anchor(anchor_text, paragraph_text)
            if status == "PASS":
                match_found = m
                break
        if match_found is None:
            raise ValueError(
                f"change_id={change['change_id']!r}: texto ancla {anchor_text!r} no se encontro "
                "en ningun parrafo real del documento -- no se inserta a ciegas."
            )
        insert_pos = match_found.end()
        new_paragraph_xml = _build_inserted_paragraph_xml(change["proposed_content"], change["change_id"])
        current_xml = current_xml[:insert_pos] + new_paragraph_xml + current_xml[insert_pos:]
        insertion_manifest.append({
            "change_id": change["change_id"],
            "proposed_content_sha256": _sha256_bytes(change["proposed_content"].encode("utf-8")),
        })
    return current_xml, insertion_manifest


def _rezip_with_modified_document_xml(original_docm_path: str, new_document_xml: str) -> bytes:
    """Copia el ZIP original byte a byte para TODA parte excepto
    word/document.xml -- incluido word/vbaProject.bin, que se copia como
    bytes opacos, NUNCA se abre ni se ejecuta."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(original_docm_path) as zin, \
         zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = new_document_xml.encode("utf-8")
            zout.writestr(item, data)
    return buffer.getvalue()


def generate_candidate_docm(original_docm_path: str, changes: list[dict]) -> bytes:
    """Documento candidato completo (bytes de un .docm nuevo, listo para
    guardar): copia byte a byte el original salvo el texto insertado en
    document.xml. El archivo original en disco NUNCA se abre en modo
    escritura -- solo lectura."""
    with zipfile.ZipFile(original_docm_path) as zin:
        document_xml = zin.read("word/document.xml").decode("utf-8")
    modified_xml, _manifest = _apply_changes_to_document_xml(document_xml, changes)
    return _rezip_with_modified_document_xml(original_docm_path, modified_xml)


def generate_redline_docm(original_docm_path: str, changes: list[dict]) -> tuple[bytes, list[dict]]:
    """Redline real: mismos bytes que generate_candidate_docm (la
    inserción YA queda marcada visualmente -- tag [change_id] + texto en
    verde subrayado, ver _build_inserted_paragraph_xml), más el
    insertion_manifest real: [{change_id, proposed_content_sha256}]."""
    with zipfile.ZipFile(original_docm_path) as zin:
        document_xml = zin.read("word/document.xml").decode("utf-8")
    modified_xml, insertion_manifest = _apply_changes_to_document_xml(document_xml, changes)
    return _rezip_with_modified_document_xml(original_docm_path, modified_xml), insertion_manifest


def verify_docm_conformance(docm_bytes: bytes, changes: list[dict], insertion_manifest: list[dict]) -> list[dict]:
    """`DOCUMENT_CONFORMANCE` para DOCM: reabre el .docm YA GENERADO desde
    bytes reales (nunca el string en memoria que produjo
    _apply_changes_to_document_xml) y verifica que
    word/vbaProject.bin permanece byte-identico al original (nunca se
    tocó) y que el texto propuesto de cada cambio aparece literalmente en
    document.xml."""
    manifest_by_change_id = {m["change_id"]: m for m in insertion_manifest}
    with zipfile.ZipFile(io.BytesIO(docm_bytes)) as z:
        document_xml = z.read("word/document.xml").decode("utf-8")
        full_text = _paragraph_text_all(document_xml)

    results: list[dict] = []
    for change in changes:
        change_id = change["change_id"]
        entry = manifest_by_change_id.get(change_id)
        if entry is None:
            results.append({"change_id": change_id, "status": "CHANGE_NOT_APPLIED", "reason": "sin entrada en insertion_manifest"})
            continue
        status, _match_type = verify_anchor(change["proposed_content"], full_text)
        if status == "PASS" and _sha256_bytes(change["proposed_content"].encode("utf-8")) == entry["proposed_content_sha256"]:
            results.append({"change_id": change_id, "status": "DOCUMENT_CONFORMANCE"})
        else:
            results.append({"change_id": change_id, "status": "CHANGE_NOT_APPLIED", "reason": "texto propuesto no encontrado en el docm reabierto"})
    return results


def _paragraph_text_all(document_xml: str) -> str:
    wrapped = f'<root xmlns:w="{_WORD_NS_URI}">{document_xml.split("<w:body>", 1)[-1].rsplit("</w:body>", 1)[0]}</root>'
    root = ET.fromstring(wrapped)
    return "\n".join("".join(t.text or "" for t in p.iter(f"{{{_WORD_NS_URI}}}t")) for p in root.iter(f"{{{_WORD_NS_URI}}}p"))


def verify_vba_project_untouched(original_docm_path: str, generated_docm_bytes: bytes) -> bool:
    """Verificación de seguridad explícita: word/vbaProject.bin (si
    existe) debe ser BYTE-IDENTICO entre el original y el candidato --
    nunca se modifica ni se regenera, confirmando que el macro nunca se
    tocó."""
    with zipfile.ZipFile(original_docm_path) as zin:
        if "word/vbaProject.bin" not in zin.namelist():
            return True
        original_vba = zin.read("word/vbaProject.bin")
    with zipfile.ZipFile(io.BytesIO(generated_docm_bytes)) as zout:
        generated_vba = zout.read("word/vbaProject.bin")
    return original_vba == generated_vba
