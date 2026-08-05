"""Versionado de artefactos — VZ-01..VZ-11 de ARTIFACT_VERSIONING_SPEC.md §6.

La invariante que se defiende:

    sha256 cambia  <=>  version cambia  <=>  existe una decision ACTIVE

VZ-09 es el de mas valor a largo plazo: el glob dinamico es lo unico que hoy
detecta un artefacto NUEVO, y es exactamente el tipo de codigo que una
"optimizacion" futura convertiria en una tupla congelada. Cuando aparecio
`cgmp211_prompts.yaml` fue el glob -- y solo el glob -- lo que hizo que el
fingerprint dejara de coincidir sin que nadie se lo recordara.

VZ-10 NO esta aqui: exige el `payload.scope_decision` de la decision migrada
`SOURCE_REGISTRATION-2026-002`, y la migracion es lo primero de G2. Escribirlo
hoy contra el almacen real solo probaria que un almacen vacio no autoriza
nada, que ya prueban otros veinte tests. Queda para G2.
"""
import copy
import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core import artifact_version_guard as guard
from factory.scripts.ops import bootstrap_artifact_versions as bootstrap
from factory.services import decision_store_v2 as store

REPO = Path(__file__).resolve().parents[2]
FACTORY = REPO / "factory"

CATALOG_REL = "factory/regulatory/requirement_catalog/requirements.yaml"
MATRIX_REL = "factory/regulatory/applicability_matrix.yaml"

# §1 del spec: los dos hashes de referencia medidos el 2026-07-29.
CATALOG_RAW_SHA256_TODAY = "a83c81682309af41615a86f93498a2d31b7b2316a2e30ad56fdcfb3b8a9e55ae"
CATALOG_RAW_SHA256_QUALIFIED = "6486405abecd729d85e32ec4a9af03cd13ad144162ebcb300ee9d25016202b8d"


def _state(**over) -> guard.ArtifactState:
    base = dict(artifact="catalog", artifact_id=CATALOG_REL,
                version="1.0", sha256="a" * 64)
    base.update(over)
    return guard.ArtifactState(**base)


def _record(state: guard.ArtifactState, **over) -> dict:
    """Registro APROBADO por defecto.

    Trae `approved_by_decision` porque los tests de las tres invariantes de
    trazabilidad (VZ-01..VZ-03) prueban hash-vs-version, y sin aprobacion
    arrastrarian ademas el WARN de `NO_APPROVING_DECISION`, mezclando dos
    reglas distintas en una sola asercion. Los tests que SI prueban la
    aprobacion nula la ponen explicitamente.
    """
    rec = guard.build_version_record(
        state, approved_by_decision="ARTIFACT_VERSION-2026-001")
    rec.update(over)
    return rec


def _approving_store(tmp_path: Path, artifact_ids, *, name="av.jsonl") -> Path:
    rec = store.build_record(
        decision_family="ARTIFACT_VERSION", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=list(artifact_ids),
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        decision_instance_id="ARTIFACT_VERSION-2026-001")
    path = tmp_path / name
    path.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


@pytest.fixture()
def empty_decisions(tmp_path) -> Path:
    path = tmp_path / "sin_decisiones.jsonl"
    path.write_text("", encoding="utf-8")
    return path


# ===========================================================================
# VZ-01..VZ-03 -- las tres direcciones de la invariante
# ===========================================================================

def test_vz01_content_changed_with_same_version_fails(empty_decisions):
    """Fixture real: el catalogo de hoy contra el hash congelado en la
    calificacion, ambos declarando `1.0`.

    Es el defecto medido en §1 del spec: se anadio `21_CFR_211.68(b)` -- la
    regla predicado de la que dependen los 5 requisitos de Part 11 -- y la
    version siguio diciendo 1.0.
    """
    hoy = _state(sha256=CATALOG_RAW_SHA256_TODAY, version="1.0")
    congelado = _record(_state(sha256=CATALOG_RAW_SHA256_QUALIFIED, version="1.0"))

    findings = guard.check_artifact(hoy, congelado,
                                    decision_store_file=empty_decisions)
    codes = {f.code for f in findings}
    assert guard.CONTENT_CHANGED_VERSION_SAME in codes
    assert [f.severity for f in findings if f.code == guard.CONTENT_CHANGED_VERSION_SAME] == ["FAIL"]


def test_vz02_version_changed_with_same_content_fails(empty_decisions):
    """"Versionar" sin tocar nada, para simular que hubo revision."""
    nuevo = _state(version="2.0", sha256="b" * 64)
    viejo = _record(_state(version="1.0", sha256="b" * 64))

    findings = guard.check_artifact(nuevo, viejo,
                                    decision_store_file=empty_decisions)
    assert guard.VERSION_CHANGED_CONTENT_SAME in {f.code for f in findings}


def test_vz03_version_changed_without_active_decision_fails(empty_decisions):
    """Fixture real: la matriz declara 2.1 y `MC-0001` solo cubre la 2.0."""
    nuevo = _state(artifact="applicability_matrix", artifact_id=MATRIX_REL,
                   version="2.1", sha256="c" * 64)
    viejo = _record(_state(artifact="applicability_matrix",
                           artifact_id=MATRIX_REL, version="2.0",
                           sha256="d" * 64),
                    approved_by_decision="MC-0001")

    findings = guard.check_artifact(nuevo, viejo,
                                    decision_store_file=empty_decisions)
    assert guard.VERSION_CHANGED_WITHOUT_DECISION in {f.code for f in findings}


def test_vz03_a_named_decision_does_not_substitute_for_an_active_one(empty_decisions):
    """`approved_by_decision` en el registro NO basta: se pregunta al resolver.

    Un registro puede nombrar una decision revocada, superada o nunca
    confirmada. Fiarse del campo seria dejar que el artefacto declare su
    propia aprobacion, que es el defecto de raiz de todo este trabajo.
    """
    nuevo = _state(version="2.0", sha256="e" * 64)
    viejo = _record(_state(version="1.0", sha256="f" * 64),
                    approved_by_decision="ARTIFACT_VERSION-2026-001")

    findings = guard.check_artifact(nuevo, viejo,
                                    decision_store_file=empty_decisions)
    assert guard.VERSION_CHANGED_WITHOUT_DECISION in {f.code for f in findings}


def test_vz03_a_real_active_decision_clears_the_third_rule(tmp_path):
    """El bloqueo no es incondicional: con firma humana real, la regla pasa."""
    approving = _approving_store(tmp_path, [CATALOG_REL])
    nuevo = _state(version="2.0", sha256="1" * 64)
    viejo = _record(_state(version="1.0", sha256="2" * 64))

    findings = guard.check_artifact(nuevo, viejo, decision_store_file=approving)
    assert guard.VERSION_CHANGED_WITHOUT_DECISION not in {f.code for f in findings}


def test_a_consistent_artifact_produces_no_findings(empty_decisions):
    """Hash igual y version igual: nada que reportar."""
    estado = _state(version="1.0", sha256="9" * 64)
    findings = guard.check_artifact(estado, _record(estado),
                                    decision_store_file=empty_decisions)
    assert findings == []


# ===========================================================================
# VZ-04..VZ-07 -- canonicalizacion
# ===========================================================================

def _write_yaml(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_vz04_reordering_keys_does_not_change_the_hash(tmp_path):
    a = _write_yaml(tmp_path / "a.yaml",
                    "prompt_version: '1.0.0'\nalpha: 1\nbeta: 2\n")
    b = _write_yaml(tmp_path / "b.yaml",
                    "beta: 2\nprompt_version: '1.0.0'\nalpha: 1\n")
    assert guard.canonical_hash_yaml(a, "prompt") == \
        guard.canonical_hash_yaml(b, "prompt")


def test_vz05_changing_a_comment_does_not_change_the_hash(tmp_path):
    a = _write_yaml(tmp_path / "a.yaml", "# nota original\nalpha: 1\n")
    b = _write_yaml(tmp_path / "b.yaml", "# nota reescrita por completo\nalpha: 1\n")
    assert guard.canonical_hash_yaml(a, "prompt") == \
        guard.canonical_hash_yaml(b, "prompt")


def test_vz06_adding_an_evidence_criterion_changes_the_hash():
    """Lo que SI es contenido. Sin esto, la canonicalizacion seria un colador."""
    pack = {"evidence_min_criteria": ["criterio A"], "exclusion_criteria": [],
            "weak_keywords": [], "typical_insufficient_evidence": [],
            "governed_interpretation": "texto", "expected_doc_types": ["URS"]}
    otro = copy.deepcopy(pack)
    otro["evidence_min_criteria"] = ["criterio A", "criterio B"]

    assert guard.canonical_hash_pack(pack) != guard.canonical_hash_pack(otro)


def test_vz06_a_derived_field_does_not_change_the_pack_hash():
    """Solo los SEIS campos de juicio humano entran en el hash.

    Los ~24 restantes son derivados o deterministas; si entraran, un recalculo
    automatico pareceria una revision humana.
    """
    pack = {"evidence_min_criteria": ["A"], "exclusion_criteria": [],
            "weak_keywords": [], "typical_insufficient_evidence": [],
            "governed_interpretation": "t", "expected_doc_types": ["URS"]}
    con_derivados = dict(pack, pack_version="9.9-draft",
                         runtime_eligibility=False, citation="lo que sea")
    assert guard.canonical_hash_pack(pack) == guard.canonical_hash_pack(con_derivados)


def test_vz06_absent_and_empty_are_not_the_same_pack():
    """`None` y `[]` son estados distintos: "nadie lo escribio" y "se decidio
    que no hay ninguno". Colapsarlos borraria justo lo que el pack 211 hace
    visible hoy -- 0 criterios, pendiente de interpretacion humana.
    """
    vacio = {"evidence_min_criteria": []}
    ausente = {}
    assert guard.canonical_hash_pack(vacio) != guard.canonical_hash_pack(ausente)


@pytest.mark.parametrize("cls,field,other", [
    ("catalog", "catalog_version", "2.0"),
    ("applicability_matrix", "matrix_version", "3.0"),
    ("prompt", "prompt_version", "9.9.9"),
])
def test_vz07_the_version_field_itself_is_excluded_from_the_hash(
        tmp_path, cls, field, other):
    """Si no se excluyera, cambiar la version cambiaria el hash y la
    invariante seria trivialmente cierta -- y por tanto inutil.
    """
    a = _write_yaml(tmp_path / "a.yaml", f"{field}: '1.0'\nalpha: 1\n")
    b = _write_yaml(tmp_path / "b.yaml", f"{field}: '{other}'\nalpha: 1\n")
    assert guard.canonical_hash_yaml(a, cls) == guard.canonical_hash_yaml(b, cls)


def test_vz07_excluding_the_version_still_catches_real_content_change(tmp_path):
    """La exclusion no puede volverse un agujero: el resto si cuenta."""
    a = _write_yaml(tmp_path / "a.yaml", "catalog_version: '1.0'\nalpha: 1\n")
    b = _write_yaml(tmp_path / "b.yaml", "catalog_version: '1.0'\nalpha: 2\n")
    assert guard.canonical_hash_yaml(a, "catalog") != \
        guard.canonical_hash_yaml(b, "catalog")


def test_the_canonical_hash_is_deliberately_not_the_raw_file_hash():
    """El fingerprint de calificacion usa el hash CRUDO; este usa el canonico.

    Coexisten a proposito y responden a preguntas distintas: "cambio el
    fichero" vs "cambio lo que significa". Este test existe para que nadie
    "arregle" uno para que cuadre con el otro.
    """
    canonico = guard.canonical_hash_yaml(guard.CATALOG_PATH, "catalog")
    assert canonico != CATALOG_RAW_SHA256_TODAY


# ===========================================================================
# VZ-08 -- el bootstrap fotografia, no aprueba
# ===========================================================================

def test_vz08_bootstrap_emits_null_approval(tmp_path):
    records = bootstrap.build_bootstrap_records(store_file=tmp_path / "vacio.jsonl")
    assert records
    for r in records:
        assert r["approved_by_decision"] is None
        assert r["bootstrap"] is True
        assert "NO representa una aprobacion humana" in r["bootstrap_note"]


def test_vz08_no_version_record_is_a_warn_never_a_pass(empty_decisions):
    """Sin `version_record`: WARN, no aprobacion.

    WARN y no FAIL porque un artefacto sin fotografiar es una tarea pendiente,
    no una corrupcion. Un FAIL aqui dejaria la fabrica en rojo por el bootstrap
    sin correr.

    Este test SE LLAMABA `..._a_null_approval_is_a_warn_never_a_pass` y no
    comprobaba eso: probaba `record=None`, que es "sin registro", no "registro
    con aprobacion nula". El nombre prometia lo que nunca verificaba, y por ese
    hueco entro el defecto que cerro
    `test_vz08_a_bootstrap_record_is_still_a_warn_not_an_approval`.
    """
    findings = guard.check_artifact(_state(), None,
                                    decision_store_file=empty_decisions)
    assert [f.code for f in findings] == [guard.NO_VERSION_RECORD]
    assert findings[0].severity == "WARN"


def test_vz08_a_bootstrap_record_is_still_a_warn_not_an_approval(empty_decisions):
    """DEFECTO REAL, detectado al EJECUTAR el bootstrap de G4.

    `check_artifact` solo avisaba cuando NO habia registro. En cuanto el
    bootstrap escribio los 28, la guardia paso a PASS y Gate 0 a verde --
    **sin que nadie hubiera aprobado nada**. Una foto leida como una
    aprobacion, que es exactamente el colapso que este trabajo combate.

    La spec lo dice literal: "la guardia de Gate 0 trata `null` como WARN, no
    como aprobacion".
    """
    estado = _state(version="1.0", sha256="c" * 64)
    boot = guard.build_version_record(estado, bootstrap=True,
                                      bootstrap_note="foto del estado observado")
    assert boot["approved_by_decision"] is None

    findings = guard.check_artifact(estado, boot,
                                    decision_store_file=empty_decisions)
    codes = [f.code for f in findings]
    assert guard.NO_APPROVING_DECISION in codes, (
        "un registro de bootstrap paso como aprobado")
    assert all(f.severity == "WARN" for f in findings)
    assert any("no habilita conclusiones formales" in f.detail for f in findings)


def test_vz08_a_record_with_a_real_decision_stops_warning(empty_decisions):
    """El aviso no es perpetuo: con una decision que lo apruebe, se apaga.

    Sin esto, la guardia seria un WARN eterno y alguien la silenciaria entera.
    """
    estado = _state(version="1.0", sha256="d" * 64)
    aprobado = guard.build_version_record(
        estado, approved_by_decision="ARTIFACT_VERSION-2026-001")
    findings = guard.check_artifact(estado, aprobado,
                                    decision_store_file=empty_decisions)
    assert findings == []


def test_vz08_bootstrap_record_does_not_authorize_a_version_change(tmp_path,
                                                                   empty_decisions):
    """Un registro de bootstrap NO habilita un cambio de version posterior."""
    estado = _state(version="1.0", sha256="7" * 64)
    boot = guard.build_version_record(estado, bootstrap=True,
                                      bootstrap_note="foto")
    siguiente = _state(version="2.0", sha256="8" * 64)

    findings = guard.check_artifact(siguiente, boot,
                                    decision_store_file=empty_decisions)
    assert guard.VERSION_CHANGED_WITHOUT_DECISION in {f.code for f in findings}


def test_vz08_bootstrap_is_dry_run_and_writes_nothing_by_default(tmp_path,
                                                                 monkeypatch):
    """Un script de gobernanza que escribe por defecto es un script que alguien
    ejecuta "para ver que hace" y deja el almacen sembrado."""
    destino = tmp_path / "artifact_versions.jsonl"
    monkeypatch.setattr(sys, "argv", ["bootstrap", "--store", str(destino)])
    assert bootstrap.main() == 0
    assert not destino.exists()


def test_vz08_bootstrap_appends_and_never_rewrites(tmp_path):
    """Append-only, y no re-fotografia lo ya versionado.

    Rebootstrapear un artefacto ya versionado sobrescribiria su historia con
    una foto sin firma.
    """
    destino = tmp_path / "av.jsonl"
    primeros = bootstrap.build_bootstrap_records(store_file=destino)
    bootstrap.append_records(primeros, destino)

    segundos = bootstrap.build_bootstrap_records(store_file=destino)
    assert segundos == []
    assert len(guard.read_version_records(destino)) == len(primeros)


# ===========================================================================
# VZ-09 -- el glob dinamico
# ===========================================================================

def test_vz09_a_new_prompt_appears_without_touching_any_list(tmp_path):
    """Regresion de C-1: enumerar el mundo, no una lista congelada.

    Se construye un arbol minimo, se cuenta, se anade un prompt y se vuelve a
    contar. Si alguien sustituye el glob por una tupla, el segundo recuento no
    cambia y este test cae.
    """
    prompts = tmp_path / "factory" / "engines" / "gmpai_integrity" / "prompts"
    prompts.mkdir(parents=True)
    (prompts / "alpha_prompts.yaml").write_text("prompt_version: '1.0.0'\na: 1\n")

    antes = guard.enumerate_artifacts(repo=tmp_path)
    assert [s.artifact_id for s in antes] == \
        ["factory/engines/gmpai_integrity/prompts/alpha_prompts.yaml"]

    (prompts / "beta_prompts.yaml").write_text("prompt_version: '2.0.0'\nb: 2\n")
    despues = guard.enumerate_artifacts(repo=tmp_path)

    assert len(despues) == 2
    assert any(s.artifact_id.endswith("beta_prompts.yaml") for s in despues)


def test_vz09_the_five_real_prompts_are_enumerated_including_cgmp211():
    """El prompt que destapo el defecto sigue estando."""
    prompts = {Path(s.artifact_id).name
               for s in guard.enumerate_artifacts() if s.artifact == "prompt"}
    assert prompts == {"alcoa_prompts.yaml", "annex11_prompts.yaml",
                       "cgmp211_prompts.yaml", "part11_prompts.yaml",
                       "traceability_prompts.yaml"}


def test_vz09_enumeration_has_no_hardcoded_artifact_list():
    """Estructural: ninguna lista literal de artefactos dentro del enumerador."""
    import ast
    tree = ast.parse((FACTORY / "core" / "artifact_version_guard.py")
                     .read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "enumerate_artifacts")
    for node in ast.walk(fn):
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            literals = [e.value for e in node.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            assert not any(".yaml" in v or ".py" in v for v in literals), (
                f"linea {node.lineno}: lista de artefactos escrita a mano")


# ===========================================================================
# VZ-11 -- los 28 artefactos reales, deterministas
# ===========================================================================

def test_vz11_the_real_tree_has_the_twenty_eight_expected_artifacts():
    states = guard.enumerate_artifacts()
    by_class: dict[str, int] = {}
    for s in states:
        by_class[s.artifact] = by_class.get(s.artifact, 0) + 1

    assert by_class == {"catalog": 1, "applicability_matrix": 1,
                        "evidence_pack": 20, "prompt": 5, "golden_dataset": 1}
    assert len(states) == 28


def test_vz11_two_runs_produce_identical_hashes():
    """Determinismo. Un hash que dependa del orden de un `dict` o de un
    `datetime` haria que cada corrida pareciera un cambio de contenido."""
    a = {s.artifact_id: s.sha256 for s in guard.enumerate_artifacts()}
    b = {s.artifact_id: s.sha256 for s in guard.enumerate_artifacts()}
    assert a == b


def test_vz11_every_artifact_id_is_unique():
    """Dos artefactos con el mismo id se pisarian en el almacen: el ultimo
    registro ganaria y uno de los dos quedaria sin gobernar en silencio."""
    ids = [s.artifact_id for s in guard.enumerate_artifacts()]
    assert len(ids) == len(set(ids))


def test_vz11_golden_dataset_declares_no_version_instead_of_inventing_one():
    """`None` es el valor honesto: el artefacto existe y no esta versionado."""
    golden = [s for s in guard.enumerate_artifacts() if s.artifact == "golden_dataset"]
    assert len(golden) == 1
    assert golden[0].version is None
    assert golden[0].sha256


def test_vz11_golden_hash_ignores_comments_but_catches_code(tmp_path):
    base = "# comentario\ndef caso():\n    return 1\n"
    a = tmp_path / "a.py"
    a.write_text(base, encoding="utf-8")
    h1 = guard.canonical_hash_golden(a)

    a.write_text("# COMENTARIO REESCRITO\ndef caso():\n    return 1\n", encoding="utf-8")
    assert guard.canonical_hash_golden(a) == h1

    a.write_text("# comentario\ndef caso():\n    return 2\n", encoding="utf-8")
    assert guard.canonical_hash_golden(a) != h1


# ===========================================================================
# Reporte completo
# ===========================================================================

def test_guard_report_today_is_all_warns_and_no_fails(tmp_path, empty_decisions):
    """Estado real de hoy: 28 artefactos, 0 version_record, 28 WARN, 0 FAIL.

    Ni verde ni rojo: el almacen no existe todavia y el bootstrap no se ha
    ejecutado. Cuando G4 lo ejecute, estos WARN se apagan uno a uno.
    """
    report = guard.guard_report(store_file=tmp_path / "no_existe.jsonl",
                                decision_store_file=empty_decisions)
    assert report["artifacts_seen"] == 28
    assert report["records_in_store"] == 0
    assert report["fail_count"] == 0
    assert report["warn_count"] == 28
    assert report["status"] == "WARN"


def test_guard_report_turns_red_on_a_single_silent_content_change(tmp_path,
                                                                  empty_decisions):
    """Un solo artefacto cambiado en silencio pone el reporte entero en FAIL."""
    states = guard.enumerate_artifacts()
    records = [guard.build_version_record(s, bootstrap=True) for s in states]
    records[0]["sha256"] = "0" * 64          # contenido distinto, version igual

    almacen = tmp_path / "av.jsonl"
    almacen.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                               for r in records), encoding="utf-8")

    report = guard.guard_report(store_file=almacen,
                                decision_store_file=empty_decisions)
    # Un FAIL manda sobre cualquier cantidad de WARN: el estado del reporte es
    # el peor de sus hallazgos, no el mas frecuente.
    assert report["status"] == "FAIL"
    assert report["fail_count"] == 1
    fails = [f for f in report["findings"] if f["severity"] == "FAIL"]
    assert fails[0]["code"] == guard.CONTENT_CHANGED_VERSION_SAME


def test_guard_report_is_green_only_when_everything_is_also_approved(
        tmp_path, empty_decisions):
    """Verde de verdad exige hash y version consistentes Y aprobacion.

    Antes este test usaba registros de bootstrap y esperaba PASS -- por eso el
    defecto de G4 paso: una foto contaba como aprobacion. Ahora los registros
    llevan `approved_by_decision`, y con bootstrap el mismo almacen sale WARN.
    """
    states = guard.enumerate_artifacts()
    almacen = tmp_path / "av.jsonl"
    almacen.write_text(
        "".join(json.dumps(guard.build_version_record(
            s, approved_by_decision="ARTIFACT_VERSION-2026-001"),
            ensure_ascii=False) + "\n" for s in states),
        encoding="utf-8")

    report = guard.guard_report(store_file=almacen,
                                decision_store_file=empty_decisions)
    assert report["status"] == "PASS"
    assert report["fail_count"] == 0 and report["warn_count"] == 0


def test_guard_report_stays_warn_when_the_store_is_only_a_photograph(
        tmp_path, empty_decisions):
    """El mismo almacen, con registros de bootstrap: WARN, no PASS.

    Es el par del test de arriba y la prueba directa del defecto de G4.
    """
    states = guard.enumerate_artifacts()
    almacen = tmp_path / "boot.jsonl"
    almacen.write_text(
        "".join(json.dumps(guard.build_version_record(s, bootstrap=True),
                           ensure_ascii=False) + "\n" for s in states),
        encoding="utf-8")

    report = guard.guard_report(store_file=almacen,
                                decision_store_file=empty_decisions)
    assert report["status"] == "WARN"
    assert report["fail_count"] == 0
    assert report["warn_count"] == len(states)


def test_guard_never_writes_anything(tmp_path, empty_decisions):
    """Read-only: la guardia mide, no corrige."""
    almacen = tmp_path / "av.jsonl"
    guard.guard_report(store_file=almacen, decision_store_file=empty_decisions)
    assert not almacen.exists()


def test_the_bootstrapped_store_photographs_without_approving():
    """G4: el almacen YA EXISTE con los 28 registros del bootstrap, y NINGUNO
    aprueba nada.

    Hasta G4 este test afirmaba que el fichero no existia. Su sustitucion es el
    registro de que el bootstrap se ejecuto, y la invariante que sobrevive es la
    que importa: fotografiar no es aprobar.

    G4a (2026-07-30) anadio un registro NO-bootstrap (redaccion real del pack
    de 21_CFR_211.68(b), `bootstrap` ausente -- nunca `bootstrap: False`
    fabricado): el almacen sigue append-only, asi que el total sube a 29 sin
    que los 28 originales cambien. Se verifican por separado para no perder
    la invariante original (todo bootstrap es no-aprobado).

    G4 (2026-07-31): Cesar firmo D2-2026-009 (CORRECTION real sobre el pack)
    -- se registro un 30o record, TAMPOCO bootstrap, con
    approved_by_decision='D2-2026-009'. Es el primero de los 30 con una
    decision real detras; los otros 29 (28 bootstrap + el borrador de
    Claude) siguen sin aprobar nada.

    G4c (2026-08-01): Cesar firmo ARTIFACT_VERSION-2026-002, y
    `apply_catalog_version_bump()` aplico el bump real de `catalog_version`
    (1.0 -> 2.0) -- se registro un 31o record, tampoco bootstrap, con
    approved_by_decision='ARTIFACT_VERSION-2026-002' para el propio
    catalogo, distinto del artefacto `21_CFR_211.68(b)` que aprobaron los
    dos records anteriores.

    G4c otra vez (2026-08-05, panel ARQ desbloqueo de firma): -005 expiro
    por TTL sin firmar; re-propuesta como -006, firmada por Cesar como
    -007, y `apply_catalog_version_bump()` aplico el segundo bump real
    (2.0 -> 2.1) -- 32o record, mismo artefacto del catalogo,
    approved_by_decision='ARTIFACT_VERSION-2026-007'.

    G6 (2026-08-05, misma sesion): Cesar firmo ARTIFACT_VERSION-2026-008
    como -009 (primera aprobacion del golden dataset, sin bump de version
    ni cambio de contenido) y `apply_artifact_first_approval()` escribio el
    33o record, primero para el artefacto `golden_dataset` con
    approved_by_decision='ARTIFACT_VERSION-2026-009'.
    """
    assert guard.STORE_FILE.exists(), "el almacen deberia existir tras el bootstrap de G4"
    records = guard.read_version_records()
    assert len(records) == 33, f"se esperaban 33 registros (28 bootstrap + 5 reales), hay {len(records)}"
    bootstrap_records = [r for r in records if r.get("bootstrap")]
    assert len(bootstrap_records) == 28
    for r in bootstrap_records:
        assert r["approved_by_decision"] is None, (
            f"{r['artifact_id']} salio aprobado del bootstrap")
        assert r["bootstrap"] is True

    real_records = [r for r in records if not r.get("bootstrap")]
    assert [r["artifact_id"] for r in real_records] == [
        "21_CFR_211.68(b)", "21_CFR_211.68(b)",
        "factory/regulatory/requirement_catalog/requirements.yaml",
        "factory/regulatory/requirement_catalog/requirements.yaml",
        "factory/regulatory/golden_dataset/semantic_verification_golden_dataset.py",
    ]
    assert real_records[0]["approved_by_decision"] is None, (
        "el borrador de Claude no es una aprobacion humana")
    assert real_records[1]["approved_by_decision"] == "D2-2026-009", (
        "el segundo registro real SI tiene detras la firma de Cesar"
    )
    assert real_records[2]["approved_by_decision"] == "ARTIFACT_VERSION-2026-002", (
        "el bump de G4c (1.0->2.0) SI tiene detras la firma de Cesar"
    )
    assert real_records[3]["approved_by_decision"] == "ARTIFACT_VERSION-2026-007", (
        "el segundo bump de G4c (2.0->2.1) SI tiene detras la firma de Cesar"
    )
    assert real_records[4]["approved_by_decision"] == "ARTIFACT_VERSION-2026-009", (
        "la primera aprobacion del golden dataset SI tiene detras la firma de Cesar"
    )

    # G5/D2-A (2026-08-05, mismo dia): la matriz cambio de version (2.1->2.2,
    # +4 document_types) sin decision humana todavia -- 1 FAIL real y
    # esperado (VERSION_CHANGED_WITHOUT_DECISION), mismo patron que el
    # catalogo tuvo antes de G4c. 25 avisos de aprobacion ausente, sin
    # cambio: ni 21_CFR_211.68(b), ni el catalogo, ni el golden dataset
    # estan en la lista de avisos.
    report = guard.guard_report()
    assert report["status"] == "FAIL"
    assert report["fail_count"] == 1
    assert report["warn_count"] == 25


def test_the_bootstrap_is_idempotent_on_the_real_store():
    """Volver a correrlo no re-fotografia lo ya versionado.

    Rebootstrapear sobrescribiria la historia de un artefacto con una foto sin
    firma.
    """
    assert bootstrap.build_bootstrap_records() == []
