"""R3-T1.2/F0.6 (2026-08-12) -- source_lifecycle.sync_catalog_source_verification_status().

Espejo mecanico hacia requirements.yaml: source_verification_status por
requisito debe reflejar el estado REAL y vivo de evaluate_registry(), nunca
un campo congelado desde una corrida anterior. Hallazgo real que motiva
esto: tras la reingesta G3 (2026-08-07, verificada en vivo -- las 4 fuentes
ya estan LOCAL_CANONICAL_COPY_VERIFIED), requirements.yaml (v2.1,
generado 2026-07-17) seguia diciendo PENDING_REVERIFICATION en las 20
entradas -- nadie lo habia vuelto a sincronizar."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory import source_lifecycle as sl
from factory.tests.test_source_lifecycle import _covered_store, _entry


def _registry(tmp_path: Path, entries: list[dict], *, name="registry.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps({"sources": entries}, ensure_ascii=False), encoding="utf-8")
    return path


_CATALOG_TEXT = """catalog_version: '2.1'
requirements:
  REQ_A:
    source_id: src_verified
    source_verification_status: PENDING_REVERIFICATION
    other_field: sin tocar
  REQ_B:
    source_id: src_still_pending
    source_verification_status: PENDING_REVERIFICATION
    other_field: sin tocar tampoco
  REQ_C:
    source_id: src_verified
    source_verification_status: LOCAL_CANONICAL_COPY_VERIFIED
"""


def test_sync_promotes_only_requirements_whose_source_is_verified(tmp_path):
    verified = _entry(tmp_path, source_id="src_verified", regulatory_currency_status="verified_current")
    still_pending = _entry(tmp_path, source_id="src_still_pending",
                            official_origin_status="FIRST_INGESTION_NO_PRIOR_KNOWN_HASH_2026-01-01")
    registry_path = _registry(tmp_path, [verified, still_pending])
    store_path = _covered_store(tmp_path, ["src_verified", "src_still_pending"])

    order = [("REQ_A", "src_verified"), ("REQ_B", "src_still_pending"), ("REQ_C", "src_verified")]
    new_text, changes = sl.sync_catalog_source_verification_status(
        _CATALOG_TEXT, order, registry_path=registry_path, decision_store_file=store_path, repo=tmp_path)

    # REQ_A: su fuente SI esta verificada -> promovido
    assert changes == {"REQ_A": {"from": "PENDING_REVERIFICATION",
                                  "to": "LOCAL_CANONICAL_COPY_VERIFIED"}}
    assert "REQ_B" not in changes  # su fuente sigue pendiente -- no se toca
    assert "REQ_C" not in changes  # ya estaba correcto -- ningun cambio espurio

    statuses = [m.group(1) for m in
                __import__("re").finditer(r"source_verification_status: (\S+)", new_text)]
    assert statuses == ["LOCAL_CANONICAL_COPY_VERIFIED", "PENDING_REVERIFICATION",
                         "LOCAL_CANONICAL_COPY_VERIFIED"]  # REQ_A, REQ_B, REQ_C en ese orden


def test_sync_never_touches_unrelated_lines(tmp_path):
    verified = _entry(tmp_path, source_id="src_verified")
    registry_path = _registry(tmp_path, [verified])
    store_path = _covered_store(tmp_path, ["src_verified"])
    order = [("REQ_A", "src_verified"), ("REQ_B", "src_verified"), ("REQ_C", "src_verified")]

    new_text, _ = sl.sync_catalog_source_verification_status(
        _CATALOG_TEXT, order, registry_path=registry_path, decision_store_file=store_path, repo=tmp_path)

    assert "other_field: sin tocar" in new_text
    assert "other_field: sin tocar tampoco" in new_text
    assert "catalog_version: '2.1'" in new_text  # el bump de version NO es responsabilidad de esta funcion


def test_sync_downgrades_if_source_regresses_to_unverified(tmp_path):
    """La sincronizacion es honesta en ambas direcciones -- si una fuente
    que estaba verificada deja de estarlo (revocada, hash divergente), el
    catalogo debe REFLEJARLO, nunca conservar un verde estancado."""
    regressed = _entry(tmp_path, source_id="src_regressed",
                       official_origin_status="UNVERIFIED")
    registry_path = _registry(tmp_path, [regressed])
    store_path = _covered_store(tmp_path, ["src_regressed"])
    catalog = ("requirements:\n  REQ_X:\n    source_id: src_regressed\n"
               "    source_verification_status: LOCAL_CANONICAL_COPY_VERIFIED\n")
    order = [("REQ_X", "src_regressed")]

    new_text, changes = sl.sync_catalog_source_verification_status(
        catalog, order, registry_path=registry_path, decision_store_file=store_path, repo=tmp_path)

    assert changes == {"REQ_X": {"from": "LOCAL_CANONICAL_COPY_VERIFIED",
                                  "to": "PENDING_REVERIFICATION"}}


def test_sync_treats_unknown_source_id_as_pending(tmp_path):
    """Un requisito cuyo source_id no resuelve en absoluto (huerfano) nunca
    puede promoverse por accidente -- fail-closed, no una excepcion que
    tumbe toda la sincronizacion por un solo requisito huerfano."""
    registry_path = _registry(tmp_path, [])
    store_path = _covered_store(tmp_path, [])
    catalog = ("requirements:\n  REQ_ORPHAN:\n    source_id: no_existe\n"
               "    source_verification_status: LOCAL_CANONICAL_COPY_VERIFIED\n")
    order = [("REQ_ORPHAN", "no_existe")]

    new_text, changes = sl.sync_catalog_source_verification_status(
        catalog, order, registry_path=registry_path, decision_store_file=store_path, repo=tmp_path)

    assert changes["REQ_ORPHAN"]["to"] == "PENDING_REVERIFICATION"


def test_sync_fails_closed_on_mismatched_requirement_count(tmp_path):
    """Nunca adivina el emparejamiento linea<->requisito si los conteos no
    coinciden -- preferible fallar explicito a corromper la entrada
    equivocada."""
    registry_path = _registry(tmp_path, [])
    store_path = _covered_store(tmp_path, [])
    with pytest.raises(ValueError, match="no se puede emparejar"):
        sl.sync_catalog_source_verification_status(
            _CATALOG_TEXT, [("SOLO_UNO", "x")],
            registry_path=registry_path, decision_store_file=store_path, repo=tmp_path)


def test_sync_against_real_catalog_file_is_idempotent(tmp_path):
    """Corrida contra el archivo real de produccion: aplicar dos veces
    seguidas (segunda vez sobre el resultado de la primera) no debe volver
    a reportar cambios -- confirma que la funcion es realmente idempotente,
    no que "cambia todo cada vez que se llama"."""
    import yaml
    real_path = (Path(__file__).parent.parent / "regulatory"
                / "requirement_catalog" / "requirements.yaml")
    text = real_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    order = [(rid, entry["source_id"]) for rid, entry in data["requirements"].items()]

    new_text, changes_1 = sl.sync_catalog_source_verification_status(text, order)
    assert len(changes_1) == 20  # el hallazgo real de esta corrida: las 20 estaban desincronizadas

    order_2 = [(rid, entry["source_id"]) for rid, entry in yaml.safe_load(new_text)["requirements"].items()]
    _, changes_2 = sl.sync_catalog_source_verification_status(new_text, order_2)
    assert changes_2 == {}
