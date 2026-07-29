"""Tests -- factory/regulatory/human_source_registration.py

Cierra la brecha detectada en el assessment de cobertura del 2026-07-29
(W5V2_D1A_D2A_ADDENDUM_DRAFT.md §A.0): no habia camino gobernado para dar de
alta una fuente regulatoria nueva.

Garantias fijadas (una por invariante del modulo):
  - propose_/confirm_ NUNCA escriben registry.json ni copian ficheros
  - apply_ es la UNICA funcion con permiso de escritura
  - apply_ exige human_confirmed+approve: una propuesta sin confirmar no se aplica
  - apply_ NUNCA sobrescribe un source_id existente (el alta es alta)
  - hashes_match se DEMUESTRA: un sha256_original que no cuadra con el fichero
    real aborta el alta
  - regulatory_currency_status siempre 'pending_reverification' -- registrar no
    es declarar vigente
  - los campos derivados no se aceptan del proponente
  - official_origin_status no puede afirmar verificacion contra hash previo en
    una fuente nueva (guarda anti-fabricacion de procedencia)
  - version/effective_date exigen literal o NO_DISPONIBLE con motivo
  - supersedes/reverification_due nunca se infieren
  - un fallo despues de validar no deja fichero copiado ni registry a medias
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.regulatory import human_source_registration as hsr

SOURCE_ID = "fda_cfr_210_211"
CONTENT = b"PART 211 -- CURRENT GOOD MANUFACTURING PRACTICE (texto de prueba)\n"
import hashlib  # noqa: E402
CONTENT_SHA256 = hashlib.sha256(CONTENT).hexdigest()


def _declared(**overrides) -> dict:
    base = {
        "official_source_url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-C/part-211",
        "official_source_description": "eCFR Title 21 Part 211 -- cGMP for Finished Pharmaceuticals",
        "sha256_original": CONTENT_SHA256,
        "normative_type": "regulation",
        "jurisdiction": "US",
        "official_origin_status": hsr.FIRST_INGESTION_ORIGIN_STATUS,
        "version": "NO_DISPONIBLE (eCFR es texto consolidado, sin edicion discreta declarada)",
        "effective_date": "NO_DISPONIBLE (eCFR es texto vivo continuamente actualizado)",
    }
    base.update(overrides)
    return base


@pytest.fixture()
def registry_env(tmp_path, monkeypatch, isolated_decisions):
    """Registry y almacen inmutable aislados -- nunca se toca el real."""
    registry = {
        "registry_version": "1.1",
        "sources": [{
            "source_id": "ecfr_21cfr_part11",
            "canonical_path": "factory/regulatory/sources/sha256/aaa/part11.txt",
            "regulatory_currency_status": "pending_reverification",
        }],
    }
    registry_file = tmp_path / "registry.json"
    registry_file.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(hsr, "SOURCES_REGISTRY_FILE", registry_file)

    store_dir = tmp_path / "sha256"
    monkeypatch.setattr(hsr, "SOURCES_STORE_DIR", store_dir)

    canonical_file = tmp_path / "incoming" / "OFFICIAL_ECFR_21CFR_part211.txt"
    canonical_file.parent.mkdir(parents=True, exist_ok=True)
    canonical_file.write_bytes(CONTENT)

    yield registry_file, store_dir, canonical_file


def _confirmed(canonical_file, declared=None, source_id=SOURCE_ID):
    proposal = hsr.propose_source_registration(
        source_id, canonical_file, declared or _declared(), rationale="alta de la regla predicado",
    )
    return hsr.confirm_source_registration(proposal["decision_id"], confirmed_by="Cesar")


# --- propose_ / confirm_ no escriben ---------------------------------------

def test_propose_writes_nothing(registry_env):
    registry_file, store_dir, canonical_file = registry_env
    before = registry_file.read_text(encoding="utf-8")
    hsr.propose_source_registration(SOURCE_ID, canonical_file, _declared(), rationale="x")
    assert registry_file.read_text(encoding="utf-8") == before
    assert not store_dir.exists()


def test_confirm_writes_nothing(registry_env):
    registry_file, store_dir, canonical_file = registry_env
    proposal = hsr.propose_source_registration(SOURCE_ID, canonical_file, _declared(), rationale="x")
    before = registry_file.read_text(encoding="utf-8")
    hsr.confirm_source_registration(proposal["decision_id"], confirmed_by="Cesar")
    assert registry_file.read_text(encoding="utf-8") == before
    assert not store_dir.exists()


def test_confirm_rejects_empty_identity(registry_env):
    _, _, canonical_file = registry_env
    proposal = hsr.propose_source_registration(SOURCE_ID, canonical_file, _declared(), rationale="x")
    with pytest.raises(hsr.HumanSourceRegistrationError):
        hsr.confirm_source_registration(proposal["decision_id"], confirmed_by="   ")


def test_confirm_rejects_already_confirmed(registry_env):
    _, _, canonical_file = registry_env
    confirmation = _confirmed(canonical_file)
    with pytest.raises(hsr.HumanSourceRegistrationError):
        hsr.confirm_source_registration(confirmation["decision_id"], confirmed_by="Cesar")


# --- validacion de lo declarado -------------------------------------------

def test_propose_rejects_derived_fields(registry_env):
    _, _, canonical_file = registry_env
    with pytest.raises(hsr.HumanSourceRegistrationError, match="derivados"):
        hsr.propose_source_registration(
            SOURCE_ID, canonical_file,
            _declared(regulatory_currency_status="verified_current"), rationale="x",
        )


def test_propose_rejects_missing_required_field(registry_env):
    _, _, canonical_file = registry_env
    declared = _declared()
    del declared["version"]
    with pytest.raises(hsr.HumanSourceRegistrationError, match="faltan campos"):
        hsr.propose_source_registration(SOURCE_ID, canonical_file, declared, rationale="x")


def test_propose_rejects_bare_no_disponible_without_reason(registry_env):
    _, _, canonical_file = registry_env
    with pytest.raises(hsr.HumanSourceRegistrationError, match="motivo"):
        hsr.propose_source_registration(
            SOURCE_ID, canonical_file, _declared(version="NO_DISPONIBLE"), rationale="x",
        )


def test_propose_rejects_malformed_sha256(registry_env):
    _, _, canonical_file = registry_env
    with pytest.raises(hsr.HumanSourceRegistrationError, match="SHA-256"):
        hsr.propose_source_registration(
            SOURCE_ID, canonical_file, _declared(sha256_original="abc"), rationale="x",
        )


def test_propose_rejects_invented_reverification_cadence(registry_env):
    _, _, canonical_file = registry_env
    with pytest.raises(hsr.HumanSourceRegistrationError, match="cadencia"):
        hsr.propose_source_registration(
            SOURCE_ID, canonical_file, _declared(reverification_due="en un mes"), rationale="x",
        )


def test_propose_rejects_existing_source_id(registry_env):
    _, _, canonical_file = registry_env
    with pytest.raises(hsr.HumanSourceRegistrationError, match="ya existe"):
        hsr.propose_source_registration(
            "ecfr_21cfr_part11", canonical_file, _declared(), rationale="x",
        )


# --- apply_: gobernanza ----------------------------------------------------

def test_apply_rejects_unconfirmed_proposal(registry_env):
    registry_file, store_dir, canonical_file = registry_env
    proposal = hsr.propose_source_registration(SOURCE_ID, canonical_file, _declared(), rationale="x")
    before = registry_file.read_text(encoding="utf-8")
    with pytest.raises(hsr.HumanSourceRegistrationError):
        hsr.apply_source_registration(proposal["decision_id"])
    assert registry_file.read_text(encoding="utf-8") == before
    assert not store_dir.exists()


def test_apply_rejects_unknown_decision_id(registry_env):
    with pytest.raises(hsr.HumanSourceRegistrationError):
        hsr.apply_source_registration("no-existe")


def test_apply_never_overwrites_existing_source(registry_env):
    """Aunque la decision sea impecable: si el source_id aparecio en el
    registry entre la propuesta y la aplicacion, apply_ aborta."""
    registry_file, _, canonical_file = registry_env
    confirmation = _confirmed(canonical_file)

    registry = json.loads(registry_file.read_text(encoding="utf-8"))
    registry["sources"].append({"source_id": SOURCE_ID, "canonical_path": "otra/ruta.txt"})
    registry_file.write_text(json.dumps(registry), encoding="utf-8")

    with pytest.raises(hsr.HumanSourceRegistrationError, match="nunca sobrescribe"):
        hsr.apply_source_registration(confirmation["decision_id"])


# --- apply_: integridad ----------------------------------------------------

def test_apply_rejects_hash_mismatch(registry_env):
    """hashes_match se demuestra calculando. Si el fichero real no coincide
    con lo declarado, no hay alta."""
    registry_file, store_dir, canonical_file = registry_env
    confirmation = _confirmed(canonical_file, _declared(sha256_original="b" * 64))
    before = registry_file.read_text(encoding="utf-8")

    with pytest.raises(hsr.HumanSourceRegistrationError, match="no coincide"):
        hsr.apply_source_registration(confirmation["decision_id"])

    assert registry_file.read_text(encoding="utf-8") == before
    assert not store_dir.exists()


def test_apply_rejects_missing_canonical_file(registry_env):
    _, store_dir, canonical_file = registry_env
    confirmation = _confirmed(canonical_file)
    canonical_file.unlink()
    with pytest.raises(hsr.HumanSourceRegistrationError, match="NUNCA descarga"):
        hsr.apply_source_registration(confirmation["decision_id"])
    assert not store_dir.exists()


def test_apply_rejects_false_prior_hash_provenance_claim(registry_env):
    """Guarda anti-fabricacion: una fuente nueva no puede afirmar que su
    origen fue verificado contra un hash previo conocido -- no existe."""
    _, store_dir, canonical_file = registry_env
    confirmation = _confirmed(
        canonical_file,
        _declared(official_origin_status="VERIFIED_AGAINST_PRIOR_KNOWN_HASH_2026-07-06_INGESTION"),
    )
    with pytest.raises(hsr.HumanSourceRegistrationError, match="hash previo"):
        hsr.apply_source_registration(confirmation["decision_id"])
    assert not store_dir.exists()


def test_apply_rejects_unresolvable_supersedes(registry_env):
    _, _, canonical_file = registry_env
    confirmation = _confirmed(canonical_file, _declared(supersedes="fuente_inexistente"))
    with pytest.raises(hsr.HumanSourceRegistrationError, match="supersedes"):
        hsr.apply_source_registration(confirmation["decision_id"])


def test_apply_rejects_empty_canonical_file(registry_env):
    _, _, canonical_file = registry_env
    empty = canonical_file.parent / "vacio.txt"
    empty.write_bytes(b"")
    declared = _declared(sha256_original=hashlib.sha256(b"").hexdigest())
    confirmation = _confirmed(empty, declared)
    with pytest.raises(hsr.HumanSourceRegistrationError, match="vacia"):
        hsr.apply_source_registration(confirmation["decision_id"])


# --- apply_: camino feliz --------------------------------------------------

def test_apply_registers_source_and_ingests_copy(registry_env):
    registry_file, store_dir, canonical_file = registry_env
    confirmation = _confirmed(canonical_file)

    result = hsr.apply_source_registration(confirmation["decision_id"])

    assert result["source_id"] == SOURCE_ID
    assert result["sha256_copy"] == CONTENT_SHA256

    stored = store_dir / CONTENT_SHA256 / canonical_file.name
    assert stored.is_file()
    assert stored.read_bytes() == CONTENT

    registry = json.loads(registry_file.read_text(encoding="utf-8"))
    entry = next(s for s in registry["sources"] if s["source_id"] == SOURCE_ID)
    assert entry["hashes_match"] is True
    assert entry["sha256_copy"] == entry["sha256_original"] == CONTENT_SHA256
    assert entry["size_bytes"] == len(CONTENT)
    assert entry["local_integrity_status"] == "PASS"
    assert entry["derived_artifacts"] == []
    assert entry["supersedes"] is None
    assert entry["reverification_due"] is None


def test_apply_never_declares_source_current(registry_env):
    """Registrar una fuente NO la declara vigente: el enum del schema tiene un
    solo valor y apply_ lo fija, venga lo que venga en la propuesta."""
    registry_file, _, canonical_file = registry_env
    confirmation = _confirmed(canonical_file)
    hsr.apply_source_registration(confirmation["decision_id"])

    registry = json.loads(registry_file.read_text(encoding="utf-8"))
    entry = next(s for s in registry["sources"] if s["source_id"] == SOURCE_ID)
    assert entry["regulatory_currency_status"] == "pending_reverification"


def test_apply_entry_validates_against_real_schema(registry_env):
    """La entrada escrita valida contra el schema REAL del repositorio, no
    contra una copia del test."""
    from factory.regulatory.schema_loader import validate_against

    registry_file, _, canonical_file = registry_env
    confirmation = _confirmed(canonical_file)
    hsr.apply_source_registration(confirmation["decision_id"])

    registry = json.loads(registry_file.read_text(encoding="utf-8"))
    entry = next(s for s in registry["sources"] if s["source_id"] == SOURCE_ID)
    ok, errors = validate_against(entry, "source_registry_entry_v1")
    assert ok, errors


def test_apply_is_idempotent_only_by_refusing_twice(registry_env):
    """La segunda aplicacion de la misma decision falla por unicidad: no
    duplica la fuente ni la reescribe."""
    registry_file, _, canonical_file = registry_env
    confirmation = _confirmed(canonical_file)
    hsr.apply_source_registration(confirmation["decision_id"])

    with pytest.raises(hsr.HumanSourceRegistrationError, match="nunca sobrescribe"):
        hsr.apply_source_registration(confirmation["decision_id"])

    registry = json.loads(registry_file.read_text(encoding="utf-8"))
    assert sum(1 for s in registry["sources"] if s["source_id"] == SOURCE_ID) == 1


def test_apply_writes_exactly_one_audit_event(registry_env, isolated_audit):
    _, _, canonical_file = registry_env
    confirmation = _confirmed(canonical_file)
    hsr.apply_source_registration(confirmation["decision_id"])

    from factory.core import audit_writer as aw
    events = [json.loads(l) for l in aw.AUDIT_FILE.read_text(encoding="utf-8").splitlines()]
    registered = [e for e in events if e.get("event_type") == "regulatory_source_registered"]
    assert len(registered) == 1
    assert registered[0]["data"]["source_id"] == SOURCE_ID
    assert registered[0]["data"]["regulatory_currency_status"] == "pending_reverification"


def test_apply_detects_store_collision_with_different_content(registry_env):
    """Si el directorio del hash ya existe con contenido distinto, el almacen
    inmutable es inconsistente: se aborta, nunca se sobrescribe."""
    registry_file, store_dir, canonical_file = registry_env
    colliding = store_dir / CONTENT_SHA256 / canonical_file.name
    colliding.parent.mkdir(parents=True, exist_ok=True)
    colliding.write_bytes(b"contenido distinto con el mismo nombre de hash")

    confirmation = _confirmed(canonical_file)
    before = registry_file.read_text(encoding="utf-8")

    with pytest.raises(hsr.HumanSourceRegistrationError, match="inconsistente"):
        hsr.apply_source_registration(confirmation["decision_id"])

    assert registry_file.read_text(encoding="utf-8") == before


# --- rutas relativas al repo ----------------------------------------------

def test_repo_relative_strips_repo_root():
    """Defecto real corregido en la primera ejecucion sobre el registry: la
    entrada se escribio con canonical_path ABSOLUTO del host. factory-api
    monta ese arbol en /app/factory, asi que esa ruta no resuelve dentro del
    contenedor y los consumidores de canonical_path se rompen."""
    inside = hsr.REPO_ROOT / "factory" / "regulatory" / "sources" / "sha256" / "abc" / "x.xml"
    assert hsr.repo_relative(inside) == "factory/regulatory/sources/sha256/abc/x.xml"


def test_repo_relative_keeps_absolute_outside_repo(tmp_path):
    """Fuera del repo no hay relativa posible: se conserva la absoluta, que al
    menos es cierta -- nunca se inventa una relativa falsa."""
    outside = tmp_path / "descarga.xml"
    outside.write_bytes(b"x")
    assert hsr.repo_relative(outside) == str(outside.resolve())


# --- estado real del repositorio ------------------------------------------

REAL_REGISTRY = Path("/home/ing_cpmo/factory/regulatory/sources/registry.json")


def test_real_registry_paths_are_repo_relative():
    """Invariante sobre el registry REAL: ninguna ruta gobernada es absoluta.
    Es la regresion que dejo la primera ejecucion de esta herramienta."""
    if not REAL_REGISTRY.exists():
        pytest.skip("registry real no disponible en este entorno")
    registry = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    for source in registry["sources"]:
        assert not source["canonical_path"].startswith("/"), source["source_id"]


def test_real_registry_has_no_unauthorized_source():
    """Las fuentes del registry real son exactamente las decididas por Capa 9:
    las 3 historicas mas ecfr_21cfr_part211 (alcance reducido aprobado el
    2026-07-29). Cualquier alta futura debe pasar por aqui conscientemente."""
    if not REAL_REGISTRY.exists():
        pytest.skip("registry real no disponible en este entorno")
    registry = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    source_ids = {s["source_id"] for s in registry["sources"]}
    assert source_ids == {
        "ecfr_21cfr_part11",
        "eu_gmp_annex11",
        "mhra_gxp_di_guidance_2018",
        "ecfr_21cfr_part211",
    }
    # Las fuentes NO adoptadas siguen fuera: Capa 9 eligio alcance reducido.
    assert "eu_gmp_ch4" not in source_ids
    assert "eu_gmp_annex15" not in source_ids
