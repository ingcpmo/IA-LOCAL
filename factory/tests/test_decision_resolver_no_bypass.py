"""Guardia de no-bypass del DecisionScopeResolver — T-20..T-24.

Es el test más importante de G1, y no por lo que prueba sino por lo que
impide: que el resolver exista y nadie lo llame. Ese es exactamente el estado
que la auditoría del 2026-07-29 encontró con las decisiones -- 17 ocurrencias
de `approved_source_ids` en 4 archivos y CERO lecturas para autorizar.

Modelado sobre `test_refresh_readonly.py`, la guardia análoga del read path.

Todo se comprueba por AST, no por `grep`: un `grep` se esquiva con una
concatenación de cadenas, y una guardia que se esquiva sin querer no es una
guardia.

ESTADO: los consumidores se cablean uno a uno en G1.7-G1.11. `WIRED` lleva la
cuenta; lo que no está en esa lista se marca `xfail(strict=True)`. `strict` es
deliberado: en cuanto un consumidor llame al resolver, su test pasará
inesperadamente y la suite EXIGIRÁ moverlo a `WIRED`. Es un andamio que se
retira solo, no un test que se queda mintiendo en verde.

G1.7 cerrado: `source_currency_checker.py` (reverificación de fuentes).
"""
import ast
from pathlib import Path

import pytest
import yaml

FACTORY = Path(__file__).resolve().parents[1]
REPO = FACTORY.parent

RESOLVER_MODULE = "decision_scope_resolver"

# Superficies que SATISFACEN la guardia. Además del resolver, la superficie de
# elegibilidad de packs: `provisional_evidence_model` delega en
# `evaluate_pack_eligibility` en vez de resolver por su cuenta, y eso es
# exactamente el diseño buscado -- una sola superficie. Lo prohibido es
# reimplementar la resolución localmente, no delegar en quien la implementa.
# `test_delegation_targets_really_reach_the_resolver` impide que esto sea un
# agujero: la superficie delegada tiene que llegar al resolver de verdad.
DELEGATION_SURFACES = {
    "factory/regulatory/requirement_catalog/requirement_catalog_loader.py":
        {"evaluate_pack_eligibility", "eligible_requirement_ids"},
}
DELEGATED_NAMES = {n for names in DELEGATION_SURFACES.values() for n in names}

# Los cinco consumidores de DECISION_SCOPE_RESOLVER_SPEC.md §6, con sus
# archivos reales.
CONSUMERS = {
    "source_reverification": ["factory/regulatory/source_currency_checker.py"],
    "evidence_pack_eligibility": [
        "factory/regulatory/requirement_catalog/requirement_catalog_loader.py",
        "factory/regulatory/requirement_catalog/provisional_evidence_model.py",
    ],
    "corpus_planner": ["factory/regulatory/verified_pipeline.py"],
    "formal_baseline": ["factory/regulatory/tools/build_source_baseline_allowlist.py"],
    "release_gate": [
        "factory/core/quality_gate_runner.py",
        "factory/core/release_manager.py",
    ],
}

# Consumidores YA cableados. Esta lista solo crece, y crecer es el progreso de
# G1.7-G1.11. Un fichero aquí se prueba de verdad; uno fuera queda en
# xfail(strict), que fallará en cuanto se cablee y obligará a moverlo.
WIRED = {
    "factory/regulatory/source_currency_checker.py",                        # G1.7
    "factory/regulatory/requirement_catalog/requirement_catalog_loader.py",  # G1.8
    "factory/regulatory/requirement_catalog/provisional_evidence_model.py",  # G1.8
    "factory/regulatory/verified_pipeline.py",                               # G1.9
    "factory/regulatory/tools/build_source_baseline_allowlist.py",           # G1.10
}

ALL_CONSUMER_FILES = sorted({f for fs in CONSUMERS.values() for f in fs})


def _param(rel):
    if rel in WIRED:
        return rel
    return pytest.param(rel, marks=pytest.mark.xfail(
        strict=True, reason="pendiente G1.8-G1.11: consumidor sin cablear"))

# Únicos módulos autorizados a tocar un almacén de decisiones directamente.
STORE_OWNERS = {
    "factory/core/decision_scope_resolver.py",
    "factory/services/decision_store_v2.py",
    "factory/services/decision_legacy_adapter.py",
    "factory/services/w5_human_decisions.py",
    "factory/layer9/decision_log.py",
    "factory/scripts/ops/migrate_decisions_to_v2.py",
}

# Lecturas directas que EXISTEN HOY y no son bypasses de autorización. Se
# enumeran en vez de ocultarse: la lista es la deuda, y encogerla es el
# progreso. Se retiran en G8 junto con los escritores legacy.
TRANSITIONAL_DIRECT_READERS = {
    # Resuelve un decision_id para MOSTRAR el registro de cierre de FS_v1.2
    # (qué run es el vigente). No autoriza nada; es presentación.
    "factory/services/gmpai_artifact_service.py",
}

STORE_FILENAMES = ("decisions_v2.jsonl", "decisions.jsonl", "w5_human_decisions.jsonl")


def _tree(rel: str) -> ast.AST:
    return ast.parse((REPO / rel).read_text(encoding="utf-8"), filename=rel)


def _imports_resolver(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(RESOLVER_MODULE in a.name for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if RESOLVER_MODULE in (node.module or ""):
                return True
            names = {a.name for a in node.names}
            if any(RESOLVER_MODULE in n for n in names):
                return True
            if names & DELEGATED_NAMES:
                return True
    return False


def _calls_resolver(tree: ast.AST) -> bool:
    wanted = {"resolve", "resolve_many", "coverage_report",
              "is_authorized"} | DELEGATED_NAMES
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id in wanted:
            return True
        if isinstance(fn, ast.Attribute) and fn.attr in wanted:
            return True
    return False


def _python_files():
    for path in FACTORY.rglob("*.py"):
        rel = path.relative_to(REPO).as_posix()
        if any(part in rel for part in
               ("__pycache__", "/.venv/", "/workspaces/", "/deployments/", "factory/tests/")):
            continue
        yield rel, path


# ===========================================================================
# T-20 / T-21 -- los consumidores llaman al resolver
# ===========================================================================

@pytest.mark.parametrize("rel", [_param(f) for f in ALL_CONSUMER_FILES])
def test_t20_consumer_imports_the_resolver(rel):
    assert (REPO / rel).is_file(), f"consumidor declarado inexistente: {rel}"
    assert _imports_resolver(_tree(rel)), (
        f"{rel} no importa el resolver: su autorización no está enforced"
    )


@pytest.mark.parametrize("rel", [_param(f) for f in ALL_CONSUMER_FILES])
def test_t21_consumer_calls_the_resolver(rel):
    assert _calls_resolver(_tree(rel)), (
        f"{rel} importa el resolver pero no lo llama"
    )


def test_delegation_targets_really_reach_the_resolver():
    """Impide que DELEGATION_SURFACES sea un agujero: una superficie delegada
    solo vale si ella misma llama al resolver de verdad. Sin esto, bastaría
    con declarar cualquier función como 'delegada' para esquivar la guardia."""
    for rel, names in DELEGATION_SURFACES.items():
        tree = _tree(rel)
        assert _imports_resolver(tree), f"{rel} no importa el resolver"
        defined = {n.name for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        assert names <= defined, f"{rel} no define {names - defined}"
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
                reaches = any(
                    isinstance(c, ast.Call)
                    and getattr(c.func, "attr", getattr(c.func, "id", "")) in
                        {"resolve", "resolve_many", "coverage_report", "is_authorized"}
                        | (names - {node.name})
                    for c in ast.walk(node))
                assert reaches, f"{rel}:{node.name} no llega al resolver"


def test_every_consumer_file_exists():
    """Sin xfail: un consumidor declarado que apunta a un fichero inexistente
    es un error de configuración hoy, no una tarea pendiente."""
    missing = [f for f in ALL_CONSUMER_FILES if not (REPO / f).is_file()]
    assert not missing, f"consumidores declarados inexistentes: {missing}"


# ===========================================================================
# T-22 / T-23 -- nadie lo esquiva. Estos SÍ aplican hoy.
# ===========================================================================

def test_t22_no_module_outside_the_owners_reads_a_decision_store():
    """Solo se marca un literal que SEA exactamente el nombre del almacén.

    El spec proponía buscar el nombre como subcadena, pero implementarlo
    demostró que eso caza prosa: docstrings y mensajes de error que MENCIONAN
    `decisions.jsonl` sin abrirlo. Una guardia que grita por un comentario se
    desactiva a la semana. Un literal igual al nombre del fichero es, en
    cambio, casi siempre construcción de ruta.
    """
    allowed = STORE_OWNERS | TRANSITIONAL_DIRECT_READERS
    offenders = []
    for rel, path in _python_files():
        if rel in allowed:
            continue
        for node in ast.walk(_tree(rel)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value.strip() in STORE_FILENAMES:
                    offenders.append(f"{rel}:{node.lineno}: {node.value!r}")
    assert not offenders, (
        "módulos abriendo un almacén de decisiones sin pasar por el resolver:\n  "
        + "\n  ".join(offenders)
    )


def test_t23_no_parallel_decision_coverage_logic():
    """Ningún módulo puede definir su propia noción de 'la decisión lo cubre'.

    El patrón del spec —`(coverage|authoriz|approved_source|covered_by)`— era
    DEMASIADO AMPLIO: en el árbol real caza nueve funciones legítimas sobre
    *cobertura documental de un requisito* (`verify_coverage`,
    `check_no_partial_coverage_gap`, `post_deploy_if_authorized`…), que es un
    concepto distinto y no tiene nada que ver con decisiones. Una guardia con
    falsos positivos estructurales se acaba borrando entera, y con ella la
    protección real. Se acota a la semántica que sí importa.
    """
    import re
    pattern = re.compile(
        r"(decision_coverage|approved_source_ids|covered_by_decision"
        r"|decision_authoriz|resolve_decision|decision_scope)", re.I)
    offenders = []
    for rel, path in _python_files():
        if rel in STORE_OWNERS:
            continue
        for node in ast.walk(_tree(rel)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if pattern.search(node.name):
                    offenders.append(f"{rel}:{node.lineno} def {node.name}")
    assert not offenders, (
        "lógica de cobertura de DECISIONES paralela al resolver (una sola "
        "superficie, como path_policy):\n  " + "\n  ".join(offenders)
    )


def test_transitional_direct_readers_is_debt_not_a_loophole():
    """La lista de excepciones solo vale si encoge. Este test la congela: si
    alguien añade una, tiene que tocar el test y justificarlo."""
    assert TRANSITIONAL_DIRECT_READERS == {
        "factory/services/gmpai_artifact_service.py"
    }, "añadir un lector directo exige justificarlo aquí, no ampliarlo en silencio"


# ===========================================================================
# T-24 -- el registro de familias y los consumidores no pueden divergir
# ===========================================================================

def test_t24_every_declared_consumer_is_a_known_one():
    """Sin xfail: esto SÍ debe cumplirse hoy. Si alguien añade una familia con
    un consumidor inventado, falla aquí y no dentro de seis meses."""
    data = yaml.safe_load(
        (FACTORY / "registry" / "decision_families.yaml").read_text(encoding="utf-8"))
    known = set(data["known_consumers"])
    for name, spec in data["families"].items():
        declared = set(spec.get("consumers") or [])
        assert declared <= known, f"familia {name}: consumidores desconocidos {declared - known}"


@pytest.mark.xfail(strict=True, reason="pendiente G1.8-G1.11: 4 de 5 consumidores sin cablear")
def test_t24_declared_consumers_have_a_wired_module():
    """El test que impide que el diseño se degrade con el tiempo: añadir una
    familia con un consumidor nuevo falla HASTA que ese consumidor llame al
    resolver."""
    data = yaml.safe_load(
        (FACTORY / "registry" / "decision_families.yaml").read_text(encoding="utf-8"))
    declared = {c for spec in data["families"].values() for c in (spec.get("consumers") or [])}
    unwired = []
    for consumer in sorted(declared):
        files = CONSUMERS.get(consumer)
        if not files:
            unwired.append(f"{consumer}: sin módulo mapeado en CONSUMERS")
            continue
        if not any(_calls_resolver(_tree(f)) for f in files):
            unwired.append(f"{consumer}: ninguno de {files} llama al resolver")
    assert not unwired, "consumidores declarados sin cablear:\n  " + "\n  ".join(unwired)


# ===========================================================================
# El resolver es read-only por construcción
# ===========================================================================

def test_resolver_never_writes_audit():
    """R-5: `resolve()` no puede escribir auditoría ni aunque alguien lo
    intente en el futuro -- el módulo no importa write_event."""
    tree = _tree("factory/core/decision_scope_resolver.py")
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and "audit_writer" in (node.module or ""):
            pytest.fail("el resolver importa audit_writer: dejaría de ser read-only")
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
            assert name != "write_event", "el resolver no puede emitir eventos"
