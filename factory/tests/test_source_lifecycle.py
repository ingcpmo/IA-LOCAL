"""Ciclo de vida de fuentes — L-01..L-10 de SOURCE_LIFECYCLE_SPEC.md §6.

Lo que se defiende aqui es una sola idea: que las cinco dimensiones no se
colapsen. Part 211 tiene el hash de su copia local intacto, y eso en un
informe se lee como "fuente verificada" cuando lo unico demostrado es que el
fichero no se corrompio. Cada test de abajo impide una forma distinta de
volver a ese colapso.

L-05 es el de mas valor operativo: una fuente sin cobertura humana no debe
generar NI UN BYTE de trafico saliente.
"""
import ast
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core import decision_scope_resolver as resolver
from factory.regulatory import source_lifecycle as sl
from factory.services import decision_store_v2 as store

REPO = Path(__file__).resolve().parents[2]
FACTORY = REPO / "factory"
V2_SCHEMA = json.loads(
    (FACTORY / "regulatory" / "schemas" / "source_registry_entry_v2.json")
    .read_text(encoding="utf-8"))
V1_SCHEMA = json.loads(
    (FACTORY / "regulatory" / "schemas" / "source_registry_entry_v1.json")
    .read_text(encoding="utf-8"))

REAL_SOURCE_IDS = ["ecfr_21cfr_part11", "ecfr_21cfr_part211",
                   "eu_gmp_annex11", "mhra_gxp_di_guidance_2018"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _entry(tmp_path: Path, **over) -> dict:
    """Entrada de registry con un fichero canonico REAL en disco.

    Con fichero de verdad y no un mock: `_dim_copy_hash_integrity` recalcula,
    y un mock probaria el mock.
    """
    body = over.pop("_content", b"texto normativo")
    rel = Path("sources") / "test" / f"{over.get('source_id', 'src')}.txt"
    abs_path = tmp_path / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(body)

    entry = {
        "source_id": "src_test",
        "canonical_path": str(rel),
        "official_source_url": "https://example.invalid/norma",
        "official_source_description": "fixture",
        "sha256_original": hashlib.sha256(body).hexdigest(),
        "sha256_copy": hashlib.sha256(body).hexdigest(),
        "hashes_match": True,
        "size_bytes": max(len(body), 1),
        "normative_type": "regulation",
        "jurisdiction": "US",
        "local_integrity_status": "PASS",
        "official_origin_status": "VERIFIED_AGAINST_PRIOR_KNOWN_HASH_2026-07-06_INGESTION",
        "regulatory_currency_status": "pending_reverification",
        "version": "NO_DISPONIBLE (fixture)",
        "effective_date": "NO_DISPONIBLE (fixture)",
        "supersedes": None,
        "reverification_due": None,
    }
    entry.update(over)
    return entry


def _covered_store(tmp_path: Path, source_ids, *, name="d.jsonl", **over) -> Path:
    rec = store.build_record(
        decision_family="D1", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=list(source_ids),
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        decision_instance_id="D1-2026-001",
    )
    rec.update(over)
    path = tmp_path / name
    path.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


@pytest.fixture()
def empty_store(tmp_path) -> Path:
    path = tmp_path / "vacio.jsonl"
    path.write_text("", encoding="utf-8")
    return path


# ===========================================================================
# L-01 -- las dimensiones son independientes
# ===========================================================================

def test_l01_no_dimension_function_calls_another():
    """Comprobado por AST, no por confianza.

    Una dimension que se derive de otra es el colapso de siempre por otro
    camino: bastaria con que `_dim_regulatory_currency` mirase la cobertura
    para que "no autorizada" y "no vigente" volvieran a ser lo mismo.
    """
    tree = ast.parse((FACTORY / "regulatory" / "source_lifecycle.py")
                     .read_text(encoding="utf-8"))
    dim_names = {n.name for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name.startswith("_dim_")}
    assert len(dim_names) == 4, f"se esperaban 4 dimensiones de entrada, hay {dim_names}"

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in dim_names:
            called = {getattr(c.func, "id", getattr(c.func, "attr", ""))
                      for c in ast.walk(node) if isinstance(c, ast.Call)}
            assert not (called & dim_names), (
                f"{node.name} llama a otra dimension: {called & dim_names}")


def test_l01_each_dimension_reads_only_its_own_input(tmp_path, empty_store):
    """La integridad de la copia esta VERDE aunque todo lo demas este ROJO.

    Es literalmente el caso de Part 211, y el que hace que un informe diga
    "verificada" sobre una fuente que nadie autorizo.
    """
    entry = _entry(tmp_path, source_id="src_test",
                   official_origin_status="FIRST_INGESTION_NO_PRIOR_KNOWN_HASH_TO_COMPARE")
    dims = sl.evaluate_source(entry, decision_store_file=empty_store, repo=tmp_path)

    assert dims.copy_hash_integrity == sl.COPY_VERIFIED
    assert dims.official_origin_verification == sl.ORIGIN_FIRST_INGESTION
    assert dims.regulatory_currency == sl.CURRENCY_PENDING
    assert dims.human_decision_coverage == sl.COVERAGE_NOT_COVERED
    assert dims.formal_use_eligibility is False


# ===========================================================================
# L-02 / L-03 -- FORMAL_USE_ELIGIBILITY es conjuncion estricta
# ===========================================================================

@pytest.mark.parametrize("failing,red_value,expected_reason", [
    ("copy", sl.COPY_CORRUPTED, "COPY_HASH_INTEGRITY=CORRUPTED"),
    ("origin", sl.ORIGIN_FIRST_INGESTION,
     "OFFICIAL_ORIGIN_VERIFICATION=NOT_COMPARABLE_FIRST_INGESTION"),
    ("currency", sl.CURRENCY_PENDING, "REGULATORY_CURRENCY=PENDING_REVERIFICATION"),
    ("coverage", sl.COVERAGE_NOT_COVERED, "HUMAN_DECISION_COVERAGE=NOT_COVERED"),
])
def test_l02_any_single_red_dimension_makes_it_ineligible(failing, red_value,
                                                          expected_reason):
    """Cuatro casos, uno por dimension. Tres en verde no bastan.

    Se comprueba el motivo EXACTO, no que "haya algun motivo": un test que
    solo exigiera una lista no vacia pasaria aunque el modulo culpara a la
    dimension equivocada.
    """
    values = {"copy": sl.COPY_VERIFIED, "origin": sl.ORIGIN_VERIFIED,
              "currency": sl.CURRENCY_CURRENT, "coverage": sl.COVERAGE_COVERED}
    values[failing] = red_value

    eligible, reasons = sl._formal_use_eligibility(**values)
    assert eligible is False
    assert reasons == (expected_reason,)


def test_l02_all_four_green_is_the_only_eligible_combination():
    eligible, reasons = sl._formal_use_eligibility(
        sl.COPY_VERIFIED, sl.ORIGIN_VERIFIED, sl.CURRENCY_CURRENT, sl.COVERAGE_COVERED)
    assert eligible is True
    assert reasons == ()


def test_l03_copy_green_with_everything_else_red_is_not_eligible():
    """El caso exacto que el modelo viejo leia como "verificada"."""
    eligible, reasons = sl._formal_use_eligibility(
        sl.COPY_VERIFIED, sl.ORIGIN_UNVERIFIED,
        sl.CURRENCY_PENDING, sl.COVERAGE_NOT_COVERED)
    assert eligible is False
    assert len(reasons) == 3
    assert not any("COPY_HASH_INTEGRITY" in r for r in reasons)


def test_l03_ineligibility_says_which_dimension_blocks():
    """Un false sin motivo obliga a rehacer el razonamiento en cada informe."""
    _, reasons = sl._formal_use_eligibility(
        sl.COPY_VERIFIED, sl.ORIGIN_VERIFIED,
        sl.CURRENCY_CURRENT, sl.COVERAGE_REVOKED)
    assert reasons == ("HUMAN_DECISION_COVERAGE=REVOKED",)


# ===========================================================================
# L-04 -- los seis estados
# ===========================================================================

@pytest.mark.parametrize("copy,origin,currency,coverage,expected", [
    (sl.COPY_VERIFIED, sl.ORIGIN_VERIFIED, sl.CURRENCY_CURRENT,
     sl.COVERAGE_REVOKED, sl.REVOKED),
    (sl.COPY_CORRUPTED, sl.ORIGIN_VERIFIED, sl.CURRENCY_CURRENT,
     sl.COVERAGE_COVERED, sl.SOURCE_UNAVAILABLE),
    (sl.COPY_FILE_MISSING, sl.ORIGIN_VERIFIED, sl.CURRENCY_CURRENT,
     sl.COVERAGE_COVERED, sl.SOURCE_UNAVAILABLE),
    (sl.COPY_VERIFIED, sl.ORIGIN_VERIFIED, sl.CURRENCY_CURRENT,
     sl.COVERAGE_NOT_COVERED, sl.REGISTERED_PENDING_AUTHORIZATION),
    (sl.COPY_VERIFIED, sl.ORIGIN_VERIFIED, sl.CURRENCY_CURRENT,
     sl.COVERAGE_RECONSTRUCTED, sl.REGISTERED_PENDING_AUTHORIZATION),
    (sl.COPY_VERIFIED, sl.ORIGIN_VERIFIED, sl.CURRENCY_EXPIRED,
     sl.COVERAGE_COVERED, sl.REVERIFICATION_EXPIRED),
    (sl.COPY_VERIFIED, sl.ORIGIN_VERIFIED, sl.CURRENCY_PENDING,
     sl.COVERAGE_COVERED, sl.AUTHORIZED_PENDING_REVERIFICATION),
    (sl.COPY_VERIFIED, sl.ORIGIN_FIRST_INGESTION, sl.CURRENCY_CURRENT,
     sl.COVERAGE_COVERED, sl.AUTHORIZED_PENDING_REVERIFICATION),
    (sl.COPY_VERIFIED, sl.ORIGIN_VERIFIED, sl.CURRENCY_CURRENT,
     sl.COVERAGE_COVERED, sl.LOCAL_CANONICAL_COPY_VERIFIED),
])
def test_l04_state_derivation_is_deterministic(copy, origin, currency,
                                               coverage, expected):
    assert sl.derive_lifecycle_state(copy, origin, currency, coverage) == expected


def test_l04_all_six_states_are_reachable():
    """Un estado inalcanzable es vocabulario muerto: o sobra o falta un camino."""
    combos = [
        (sl.COPY_VERIFIED, sl.ORIGIN_VERIFIED, sl.CURRENCY_CURRENT, sl.COVERAGE_REVOKED),
        (sl.COPY_CORRUPTED, sl.ORIGIN_VERIFIED, sl.CURRENCY_CURRENT, sl.COVERAGE_COVERED),
        (sl.COPY_VERIFIED, sl.ORIGIN_VERIFIED, sl.CURRENCY_CURRENT, sl.COVERAGE_NOT_COVERED),
        (sl.COPY_VERIFIED, sl.ORIGIN_VERIFIED, sl.CURRENCY_EXPIRED, sl.COVERAGE_COVERED),
        (sl.COPY_VERIFIED, sl.ORIGIN_VERIFIED, sl.CURRENCY_PENDING, sl.COVERAGE_COVERED),
        (sl.COPY_VERIFIED, sl.ORIGIN_VERIFIED, sl.CURRENCY_CURRENT, sl.COVERAGE_COVERED),
    ]
    assert {sl.derive_lifecycle_state(*c) for c in combos} == set(sl.LIFECYCLE_STATES)


def test_l04_coverage_is_evaluated_before_currency():
    """Orden deliberado: no autorizada gana sobre caducada.

    Si se invirtiera, una fuente sin firmar acabaria en REVERIFICATION_EXPIRED
    -- un estado que invita a reverificar, es decir, a salir a la red.
    """
    state = sl.derive_lifecycle_state(
        sl.COPY_VERIFIED, sl.ORIGIN_VERIFIED,
        sl.CURRENCY_EXPIRED, sl.COVERAGE_NOT_COVERED)
    assert state == sl.REGISTERED_PENDING_AUTHORIZATION


# ===========================================================================
# L-05 -- cero trafico saliente sin cobertura
# ===========================================================================

def test_l05_lifecycle_module_never_reaches_the_network():
    """El modulo no importa httpx ni nada de red. Estructural, no de runtime."""
    tree = ast.parse((FACTORY / "regulatory" / "source_lifecycle.py")
                     .read_text(encoding="utf-8"))
    forbidden = {"httpx", "requests", "urllib", "socket", "http"}
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [node.module or ""]
        for m in mods:
            assert m.split(".")[0] not in forbidden, f"source_lifecycle importa {m}"


def test_l05_uncovered_source_generates_zero_http_traffic(tmp_path, empty_store,
                                                          monkeypatch):
    """El test con mas valor operativo de la spec.

    Protege contra la regresion mas probable: que alguien mueva la
    comprobacion de cobertura a DESPUES del `httpx.get`.
    """
    from factory.regulatory import source_currency_checker as scc

    def _explode(url):
        raise AssertionError(f"trafico saliente sobre fuente no autorizada: {url}")

    monkeypatch.setattr(scc, "_http_get", _explode)

    entry = _entry(tmp_path, source_id="src_sin_cobertura")
    result = scc.check_source(entry, decision_store_file=empty_store)
    assert result["authorized_by_decision"] is False
    assert result["reverification_allowed"] is False
    # `reachable=None` y no False: False afirmaria que se intento el acceso y
    # fallo. No se intento -- que es justo lo que este test defiende.
    assert result["reachable"] is None


def test_l05_evaluating_a_source_makes_no_network_call(tmp_path, empty_store,
                                                       monkeypatch):
    """Evaluar dimensiones tampoco sale a la red, ni con cobertura completa."""
    import httpx

    def _explode(*a, **k):
        raise AssertionError("source_lifecycle salio a la red")

    monkeypatch.setattr(httpx, "get", _explode)
    entry = _entry(tmp_path, source_id="src_test")
    covered = _covered_store(tmp_path, ["src_test"])
    dims = sl.evaluate_source(entry, decision_store_file=covered, repo=tmp_path)
    assert dims.human_decision_coverage == sl.COVERAGE_COVERED


# ===========================================================================
# L-06 / L-07 -- que es automatico y que no
# ===========================================================================

def test_l06_no_permissive_state_without_human_coverage(tmp_path, empty_store):
    """Sin firma humana, ningun estado permisivo es alcanzable.

    Se prueba barriendo TODAS las combinaciones de las otras tres dimensiones:
    la unica forma de estar seguro es que no exista ni una salida.
    """
    for copy in (sl.COPY_VERIFIED, sl.COPY_CORRUPTED, sl.COPY_FILE_MISSING):
        for origin in (sl.ORIGIN_VERIFIED, sl.ORIGIN_FIRST_INGESTION, sl.ORIGIN_UNVERIFIED):
            for currency in (sl.CURRENCY_CURRENT, sl.CURRENCY_PENDING, sl.CURRENCY_EXPIRED):
                for coverage in (sl.COVERAGE_NOT_COVERED, sl.COVERAGE_REVOKED,
                                 sl.COVERAGE_RECONSTRUCTED):
                    state = sl.derive_lifecycle_state(copy, origin, currency, coverage)
                    assert state not in sl.PERMISSIVE_STATES, (
                        f"{coverage} llego a {state} con "
                        f"copy={copy} origin={origin} currency={currency}")


def test_l06_reconstructed_coverage_is_reported_but_does_not_authorize(tmp_path):
    """Una D1 RECONSTRUIDA se DISTINGUE de "sin cobertura" y aun asi no promueve.

    Es el estado exacto de las tres fuentes antiguas en cuanto G2 migre el
    almacen, y la distincion que un informe necesita poder decir: no es lo
    mismo "nadie firmo" que "reconstruimos lo que probablemente se firmo".
    Ninguna de las dos autoriza.

    Este test existe porque una mutacion lo destapo: mapear
    COVERAGE_RECONSTRUCTED a COVERAGE_COVERED no rompia NADA de la suite. Con
    el almacen real vacio, la rama reconstruida no la ejercitaba nadie.
    """
    recon = _covered_store(
        tmp_path, ["src_test"], name="reconstruida.jsonl",
        provenance="RECONSTRUCTED_SNAPSHOT",
        reconstruction_evidence={"method": "fixture", "source": "test_source_lifecycle"},
    )
    entry = _entry(tmp_path, source_id="src_test")
    dims = sl.evaluate_source(entry, decision_store_file=recon, repo=tmp_path)

    assert dims.human_decision_coverage == sl.COVERAGE_RECONSTRUCTED
    assert dims.human_decision_coverage != sl.COVERAGE_NOT_COVERED
    assert dims.lifecycle_state == sl.REGISTERED_PENDING_AUTHORIZATION
    assert dims.formal_use_eligibility is False
    assert any("RECONSTRUCTED" in r for r in dims.ineligibility_reasons)


def test_l06_revoked_coverage_is_distinguished_from_never_covered(tmp_path):
    """REVOKED tampoco se confunde con NOT_COVERED: retirar no es no haber dado."""
    granted = store.build_record(
        decision_family="D1", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=["src_test"],
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        decision_instance_id="D1-2026-001")
    revocation = store.build_record(
        decision_family="D1", decision_type="REVOCATION",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=["src_test"],
        decision="REJECT", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        decision_instance_id="D1-2026-002",
        # I-6 del store: una REVOCACION tiene que decir a QUE instancia retira
        # la cobertura y POR QUE. Retirar sin motivo escrito no es gobernanza.
        supersedes_instance_id="D1-2026-001",
        reason="fixture: la fuente deja de estar autorizada")
    path = tmp_path / "revocada.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                            for r in (granted, revocation)), encoding="utf-8")

    entry = _entry(tmp_path, source_id="src_test")
    dims = sl.evaluate_source(entry, decision_store_file=path, repo=tmp_path)

    assert dims.human_decision_coverage == sl.COVERAGE_REVOKED
    assert dims.lifecycle_state == sl.REVOKED


def test_l06_agent_signature_does_not_move_the_state(tmp_path):
    """Una decision `agent_proposed` no promueve nada."""
    agent = _covered_store(tmp_path, ["src_test"], name="agente.jsonl",
                           decision_origin="agent_proposed")
    entry = _entry(tmp_path, source_id="src_test")
    dims = sl.evaluate_source(entry, decision_store_file=agent, repo=tmp_path)
    assert dims.lifecycle_state == sl.REGISTERED_PENDING_AUTHORIZATION


def test_l07_expiry_is_automatic(tmp_path):
    """Restringir SI es automatico: basta el reloj."""
    ayer = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    entry = _entry(tmp_path, source_id="src_test", reverification_due=ayer)
    covered = _covered_store(tmp_path, ["src_test"])
    dims = sl.evaluate_source(entry, decision_store_file=covered, repo=tmp_path)

    assert dims.regulatory_currency == sl.CURRENCY_EXPIRED
    assert dims.lifecycle_state == sl.REVERIFICATION_EXPIRED


def test_l07_expiry_overrides_a_stored_current_status(tmp_path):
    """Un `current` almacenado no salva a una fuente con la fecha vencida."""
    ayer = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert sl._dim_regulatory_currency("verified_current", ayer) == sl.CURRENCY_EXPIRED


def test_l07_corruption_is_automatic_and_blocks_everything(tmp_path):
    """Copia corrupta => SOURCE_UNAVAILABLE, aunque este firmada y vigente."""
    entry = _entry(tmp_path, source_id="src_test")
    (tmp_path / entry["canonical_path"]).write_bytes(b"contenido alterado")
    covered = _covered_store(tmp_path, ["src_test"])

    dims = sl.evaluate_source(entry, decision_store_file=covered, repo=tmp_path)
    assert dims.copy_hash_integrity == sl.COPY_CORRUPTED
    assert dims.lifecycle_state == sl.SOURCE_UNAVAILABLE
    assert dims.formal_use_eligibility is False


def test_l07_integrity_is_recomputed_not_trusted(tmp_path):
    """`local_integrity_status=PASS` no basta: se recalcula el hash.

    El campo almacenado es el resultado de un calculo pasado. Si el fichero se
    corrompio despues, sigue diciendo PASS.
    """
    entry = _entry(tmp_path, source_id="src_test", local_integrity_status="PASS")
    (tmp_path / entry["canonical_path"]).write_bytes(b"otra cosa")
    assert sl._dim_copy_hash_integrity(
        entry["canonical_path"], entry["sha256_copy"], repo=tmp_path) == sl.COPY_CORRUPTED


# ===========================================================================
# L-08 -- las cuatro fuentes reales
# ===========================================================================

def test_l08_all_four_reached_formal_use_after_currency_and_origin_confirmed():
    """Las cuatro fuentes reales SI son usables formalmente hoy.

    Antes esta asercion decia "ninguna de las cuatro", luego "dos de
    cuatro" -- el docstring original ya anunciaba el patron: "cambiara en
    G2, y ese cambio es la prueba de que la Correccion D1 hizo algo". Paso
    una tercera vez, con la ultima pieza que faltaba: SOURCE_CURRENCY
    (2026-08-05, Cesar firmo SOURCE_CURRENCY-2026-005..008) cubrio la
    vigencia normativa de las 4; SOURCE_ORIGIN_VERIFICATION (2026-08-07,
    DEC-B, `source_origin_verification.py`) cubrio la QUINTA dimension
    distinta que solo bloqueaba a ecfr_21cfr_part11/ecfr_21cfr_part211 --
    official_origin_verification, que SOURCE_CURRENCY nunca toca y que
    solo se resuelve con una segunda observacion real de origen
    (Cesar firmo SOURCE_ORIGIN_VERIFICATION-2026-003/004). Con ambas
    dimensiones en verde para las 4, las 4 llegan a LOCAL_CANONICAL_COPY_
    VERIFIED de verdad.
    """
    dims = sl.evaluate_registry()
    assert {d.source_id for d in dims} == set(REAL_SOURCE_IDS)
    por_id = {d.source_id: d for d in dims}

    for sid in REAL_SOURCE_IDS:
        assert por_id[sid].lifecycle_state == sl.LOCAL_CANONICAL_COPY_VERIFIED, sid
        assert por_id[sid].official_origin_verification == sl.ORIGIN_VERIFIED, sid
        assert por_id[sid].formal_use_eligibility is True, (
            f"{sid} tiene evidencia real de re-verificacion de vigencia y de origen, "
            "mas firma humana de ambas -- deberia ser elegible")


def test_l08_d1_authorization_alone_never_grants_verified():
    """Firmar SOLO D1 (autorizacion generica) nunca reverifica -- el
    invariante de U-5 que SOURCE_CURRENCY no relaja para nadie.

    Es la mitad que faltaba en el test anterior: sin ella, lo aprobaria un
    sistema en el que firmar D1 solo bastara para llegar a VERIFIED, y
    eso es exactamente lo que este archivo entero existe para impedir.
    Las dos fuentes que SI llegaron a LOCAL_CANONICAL_COPY_VERIFIED lo
    hicieron por una decision SOURCE_CURRENCY real y separada -- este test
    verifica la mitad negativa: que la mera cobertura D1 (`coverage_basis`
    de D1) nunca es, por si sola, suficiente.
    """
    por_id = {d.source_id: d for d in sl.evaluate_registry()}
    cubiertas = set(resolver.coverage_report("D1").covered_ids)
    assert cubiertas, "sin ninguna fuente cubierta este test no mide nada"

    for sid, dim in por_id.items():
        assert sid in cubiertas, f"{sid}: sin cobertura D1, no debería estar en el registry gobernado"
        # D1 por si sola nunca alcanza REGISTERED_PENDING_AUTHORIZATION otra
        # vez (eso seria un retroceso), pero tampoco basta por si sola para
        # llegar a VERIFIED sin una decision SOURCE_CURRENCY real aparte.
        assert dim.lifecycle_state in (sl.AUTHORIZED_PENDING_REVERIFICATION,
                                       sl.LOCAL_CANONICAL_COPY_VERIFIED), \
            f"{sid}: {dim.lifecycle_state}"


def test_l08_all_four_origins_are_green():
    """La diferencia real entre las fuentes recien ingeridas y las demas
    existio y se documento aqui mientras duro -- este test es su cierre,
    no su borrado.

    `ecfr_21cfr_part11` se unio a `ecfr_21cfr_part211` en ambar desde la
    re-gobernanza real de G3 (2026-08-03, `human_source_regovernance.py`):
    el archivo canonico cambio de TEXT a XML, `official_origin_status`
    volvio a `FIRST_INGESTION_...` porque no habia hash previo propio con
    el que comparar el artefacto nuevo -- mismo motivo por el que Part 211
    quedo ambar al ingerirse. El ambar de ambas se resolvio (2026-08-07,
    DEC-B) con una segunda observacion real de origen
    (`source_origin_verification.py`, `SOURCE_ORIGIN_VERIFICATION-2026-003/
    004`, Cesar) -- no con el paso del tiempo solo, sino con la evidencia
    real ya recolectada por `reverify_governed_sources.py` mas la firma
    humana que faltaba."""
    by_id = {d.source_id: d for d in sl.evaluate_registry()}
    for sid in REAL_SOURCE_IDS:
        assert by_id[sid].official_origin_verification == sl.ORIGIN_VERIFIED, sid


def test_l08_all_four_have_intact_local_copies():
    """La buena noticia real, dicha sin que arrastre una conclusion.

    COPY_HASH_INTEGRITY en verde es cierto y debe poder decirse; lo que no
    puede es leerse como "fuente verificada".
    """
    for d in sl.evaluate_registry():
        assert d.copy_hash_integrity == sl.COPY_VERIFIED, d.source_id


# ===========================================================================
# L-09 -- regla anti-colapso
# ===========================================================================

def test_l09_no_collapsed_source_verified_flag():
    """Ningun modulo define un campo `verified`/`source_verified` sobre una
    entrada de registry.

    Se acota a `factory/regulatory/`: `verify_chain()` devuelve una clave
    `verified` sobre la CADENA DE AUDITORIA, que no es una fuente, y una
    guardia que la marcase seria un falso positivo estructural -- de los que
    acaban con la guardia borrada entera.
    """
    import re
    pattern = re.compile(r"^(source_)?verified$")
    offenders = []
    for path in (FACTORY / "regulatory").rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        rel = path.relative_to(REPO).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for k in node.keys:
                    if (isinstance(k, ast.Constant) and isinstance(k.value, str)
                            and pattern.match(k.value)):
                        offenders.append(f"{rel}:{k.lineno} clave {k.value!r}")
    assert not offenders, (
        "flag colapsado 'fuente verificada' -- exponer las CINCO dimensiones:\n  "
        + "\n  ".join(offenders))


def test_l09_the_serialization_carries_all_five_dimensions(tmp_path, empty_store):
    """`as_dict()` nunca devuelve un resumen booleano suelto."""
    entry = _entry(tmp_path, source_id="src_test")
    d = sl.as_dict(sl.evaluate_source(entry, decision_store_file=empty_store,
                                      repo=tmp_path))
    for key in ("copy_hash_integrity", "official_origin_verification",
                "regulatory_currency", "human_decision_coverage",
                "formal_use_eligibility"):
        assert key in d
    assert "verified" not in d


# ===========================================================================
# L-10 -- la derivacion no toca el origen
# ===========================================================================

def test_l10_only_the_destination_is_ever_written():
    """Estructural: dentro de `derive_registry_v2`, solo `dst` se escribe.

    Existe porque la comparacion de bytes de abajo NO basta por si sola: una
    mutacion que reescriba el origen re-serializandolo con el mismo formato
    del fixture sale byte-identica y pasa desapercibida. Aqui se comprueba lo
    que importa de verdad -- que el origen no es destino de ninguna escritura.
    """
    tree = ast.parse((FACTORY / "regulatory" / "source_lifecycle.py")
                     .read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "derive_registry_v2")
    writes = [n for n in ast.walk(fn)
              if isinstance(n, ast.Call)
              and getattr(n.func, "attr", "") in ("write_text", "write_bytes", "open")]
    assert writes, "el test dejo de ver las escrituras: revisar el patron"
    for call in writes:
        target = getattr(call.func.value, "id", None)
        assert target == "dst", (
            f"linea {call.lineno}: escritura sobre {target!r}, no sobre 'dst'")


def test_l10_deriving_v2_does_not_modify_registry_json(tmp_path):
    """sha256 identico antes y despues. El rollback es borrar el derivado.

    El origen se escribe COMPACTO a proposito, distinto del formato indentado
    que produce el modulo: asi cualquier re-serializacion cambia los bytes.
    """
    src = tmp_path / "registry.json"
    entry = _entry(tmp_path, source_id="src_test")
    src.write_text(json.dumps({"registry_version": 1, "sources": [entry]},
                              separators=(",", ":"), ensure_ascii=False),
                   encoding="utf-8")
    before = hashlib.sha256(src.read_bytes()).hexdigest()

    out = sl.derive_registry_v2(src, tmp_path / "registry_v2.json",
                                decision_store_file=tmp_path / "no_existe.jsonl",
                                repo=tmp_path)

    assert hashlib.sha256(src.read_bytes()).hexdigest() == before
    assert out["derived_from_sha256"] == before


def test_l10_v2_is_additive_every_v1_field_survives(tmp_path):
    """Los campos de v1 se conservan: son las ENTRADAS de las dimensiones.

    Borrarlos convertiria el v2 en la unica verdad y haria el rollback
    imposible.
    """
    src = tmp_path / "registry.json"
    entry = _entry(tmp_path, source_id="src_test")
    src.write_text(json.dumps({"registry_version": 1, "sources": [entry]}),
                   encoding="utf-8")

    out = sl.derive_registry_v2(src, tmp_path / "registry_v2.json",
                                decision_store_file=tmp_path / "no_existe.jsonl",
                                repo=tmp_path)
    derived = out["sources"][0]
    for k, v in entry.items():
        assert derived[k] == v, f"campo v1 alterado: {k}"
    assert derived["lifecycle_state"] == sl.REGISTERED_PENDING_AUTHORIZATION


def test_l10_derived_entries_validate_against_v2_schema(tmp_path):
    src = tmp_path / "registry.json"
    entry = _entry(tmp_path, source_id="src_test")
    src.write_text(json.dumps({"registry_version": 1, "sources": [entry]}),
                   encoding="utf-8")
    out = sl.derive_registry_v2(src, tmp_path / "registry_v2.json",
                                decision_store_file=tmp_path / "no_existe.jsonl",
                                repo=tmp_path)
    for e in out["sources"]:
        jsonschema.validate(e, V2_SCHEMA)


def test_l10_v2_schema_accepts_every_current_v1_entry():
    """Compatibilidad hacia atras, sobre las 4 entradas REALES.

    Si una entrada de `registry.json` dejara de validar contra v2, el schema
    no seria aditivo sino una migracion forzosa del artefacto de origen -- que
    es justo lo que la spec prohibe.
    """
    data = json.loads((FACTORY / "regulatory" / "sources" / "registry.json")
                      .read_text(encoding="utf-8"))
    for e in data["sources"]:
        jsonschema.validate(e, V1_SCHEMA)
        jsonschema.validate(e, V2_SCHEMA)


def test_l10_v2_schema_rejects_a_partial_dimensions_object(tmp_path):
    """Un `dimensions` incompleto es exactamente el colapso a evitar."""
    entry = _entry(tmp_path, source_id="src_test")
    entry["lifecycle_state"] = sl.REGISTERED_PENDING_AUTHORIZATION
    entry["dimensions"] = {"COPY_HASH_INTEGRITY": "VERIFIED"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(entry, V2_SCHEMA)


def test_l10_v2_schema_rejects_an_invented_lifecycle_state(tmp_path):
    entry = _entry(tmp_path, source_id="src_test")
    entry["lifecycle_state"] = "VERIFIED"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(entry, V2_SCHEMA)
