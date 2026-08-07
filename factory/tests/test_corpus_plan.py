"""R(d,a) real -- factory/regulatory/corpus_plan.py.

Verificado contra los DOS puntos de datos ya calibrados en
test_corpus_budget_formula.py (eu_annex11 5cp/20crit, alcoa_plus 9cp/25crit,
ambos sobre FS con TODOS los requisitos del agente elegibles hoy) -- si
`resolve_document_agent_plan` reproduce exactamente esos dos números para
FS, la resolución de agente+elegibilidad es correcta."""
from __future__ import annotations

from factory.regulatory.corpus_plan import (
    is_requirement_eligible, load_agent_of_requirement,
    resolve_document_agent_plan,
)


def test_load_agent_of_requirement_covers_the_full_catalog_without_guessing_by_prefix():
    from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
        load_requirements,
    )
    agents = load_agent_of_requirement()
    assert set(agents) == set(load_requirements()["requirements"])
    assert agents["21_CFR_211.68(b)"] == "fda_cgmp_211_agent"
    assert agents["21_CFR_11.10(a)"] == "fda_part11_agent"
    assert agents["ANNEX11_4"] == "eu_annex11_agent"
    assert agents["ALCOA_ACCURATE"] == "alcoa_plus_agent"


def test_fs_reproduces_the_two_already_calibrated_agent_budgets():
    """eu_annex11_agent (5cp/20crit->budget 3072, corrida real 481 min) y
    alcoa_plus_agent (9cp/25crit->budget 4096, 10.7h) -- ambos ya
    verificados en test_corpus_budget_formula.py contra corridas reales.
    Todos sus requisitos aplican a FS y están elegibles hoy (D2 cubierto +
    fuentes VERIFIED), así que el plan real debe reproducir exactamente
    esos dos contratos."""
    plan = resolve_document_agent_plan("FS")
    assert plan["eu_annex11_agent"]["n_checkpoints"] == 5
    assert plan["eu_annex11_agent"]["n_criteria"] == 20
    assert plan["alcoa_plus_agent"]["n_checkpoints"] == 9
    assert plan["alcoa_plus_agent"]["n_criteria"] == 25


def test_ds_only_includes_the_one_part11_clause_expected_or_cross_referenced_for_ds():
    """21_CFR_11.10(e) es EXPECTED/cross_reference_expected para DS; los
    otros 4 son review_required -- confirmado en applicability_matrix.yaml.
    """
    plan = resolve_document_agent_plan("DS")
    assert plan["fda_part11_agent"]["requirement_ids"] == ["21_CFR_11.10(e)"]
    assert plan["fda_part11_agent"]["n_criteria"] == 9  # criterios propios de esa clausula


def test_agents_with_no_applicable_requirement_are_absent_not_zero():
    """Un agente sin ningun requisito aplicable a un tipo documental no debe
    aparecer -- una lista vacia seguiria generando una llamada de 0
    criterios, que no es lo mismo que 'este agente no corre aqui'.

    PROTOCOL no tiene ninguna fila 'expected'/'optional'/
    'cross_reference_expected' en ninguno de los 20 requisitos del
    catalogo hoy -- ningun agente debe aparecer, el plan debe quedar
    vacio en vez de listar agentes con 0 checkpoints."""
    plan = resolve_document_agent_plan("PROTOCOL")
    assert plan == {}


def test_ineligible_requirement_never_enters_the_plan_even_if_matrix_allows_it(tmp_path):
    """Elegibilidad (D2 + fuente VERIFIED) es una condicion AL MENOS tan
    fuerte como la matriz -- un almacen de decisiones vacio (D2 sin cubrir
    para nadie) debe vaciar el plan entero, no solo advertir."""
    empty_store = tmp_path / "decisions_v2.jsonl"
    empty_store.write_text("", encoding="utf-8")
    plan = resolve_document_agent_plan("FS", decision_store_file=empty_store)
    assert plan == {}


def test_is_requirement_eligible_true_for_all_twenty_today():
    from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
        load_requirements,
    )
    for req_id in load_requirements()["requirements"]:
        assert is_requirement_eligible(req_id), req_id
