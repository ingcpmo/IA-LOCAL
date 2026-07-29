"""Gate 4 -- "100% prompts con Evidence Pack completo; pack incompleto
BLOQUEA LA LLAMADA, no la corrida" (ACCEPTANCE_AND_VALIDATION_GATES.md).

Defecto real que cierra (informe de validacion corregido del 2026-07-28,
commit 71168e4): el gate declaraba bloquear la llamada y el codigo hacia lo
contrario -- `_lookup_regulatory_text()` devolvia None en silencio y
`build_prompt()` seguia adelante con solo req_id + label. Eso es fail-OPEN,
y es exactamente el antipatron del baseline de 121 llamadas (§3.1.5-6 del
plan) que produjo el falso positivo de ANNEX11_4.

Lo que se prueba aqui NO es que el gate exista, sino que bloquea de verdad:
que el req_id sin pack no aparece en el prompt, que no se hace ninguna
llamada al modelo por el, y que su ausencia de hallazgo no se convierte en
un incumplimiento afirmado.
"""
from pathlib import Path

import pytest

from factory.engines.gmpai_integrity import chunked_engine as ce

PROMPTS_DIR = Path("factory/engines/gmpai_integrity/prompts")
CATALOG_REQ = "ANNEX11_4"  # req_id real y completo del catalogo


class TestValidateEvidencePack:

    def test_real_catalog_requirement_is_complete(self):
        verdict = ce.validate_evidence_pack(CATALOG_REQ)
        assert verdict.complete is True
        assert verdict.missing == ()

    def test_unknown_requirement_is_incomplete_not_an_exception(self):
        """Nunca lanza: devuelve veredicto. Un gate que revienta bloquea la
        corrida entera, y el gate 4 debe bloquear solo la llamada."""
        verdict = ce.validate_evidence_pack("REQ_QUE_NO_EXISTE")
        assert verdict.complete is False
        assert "sin entrada valida en el catalogo" in verdict.detail

    def test_every_interpreted_requirement_has_a_complete_pack(self):
        """Cobertura real: todo req_id con interpretacion humana pasa el gate.
        Si falla, el catalogo perdio un campo que el prompt inyecta.

        Los requisitos en PENDING_HUMAN_INTERPRETATION_REQ_IDS se excluyen a
        proposito -- su pack esta incompleto POR DISENO, y el test de abajo
        exige que por eso mismo sigan bloqueados."""
        import yaml
        from tests.conftest import PENDING_HUMAN_INTERPRETATION_REQ_IDS
        catalog = yaml.safe_load(
            Path("factory/regulatory/requirement_catalog/requirements.yaml").read_text()
        )
        incomplete = {
            rid: ce.validate_evidence_pack(rid).missing
            for rid in catalog["requirements"]
            if rid not in PENDING_HUMAN_INTERPRETATION_REQ_IDS
            and not ce.validate_evidence_pack(rid).complete
        }
        assert incomplete == {}, f"req_id interpretado con pack incompleto: {incomplete}"

    def test_pending_interpretation_requirements_are_incomplete_and_blocked(self):
        """La otra mitad de la invariante: un requisito sin interpretacion
        humana NO puede colarse como operativo. Debe estar incompleto de
        verdad (si estuviera completo, sobraria en la lista) y bloqueado."""
        import yaml
        from tests.conftest import PENDING_HUMAN_INTERPRETATION_REQ_IDS
        catalog = yaml.safe_load(
            Path("factory/regulatory/requirement_catalog/requirements.yaml").read_text()
        )
        for rid in PENDING_HUMAN_INTERPRETATION_REQ_IDS:
            entry = catalog["requirements"][rid]
            assert not ce.validate_evidence_pack(rid).complete, rid
            assert entry["evidence_pack_status"] == "structure_only_pending_human_interpretation", rid
            assert entry["content_review_status"] == "PENDING_HUMAN_INTERPRETATION", rid
            assert entry["production_eligibility"] == "BLOCKED", rid
            assert entry["ready_for_regulatory_use"] is False, rid

    @pytest.mark.parametrize("field,expected_missing", [
        ("citation_text", "citation.citation_text"),
        ("section_page_paragraph", "citation.section_page_paragraph"),
    ])
    def test_mutation_missing_citation_field_blocks(self, field, expected_missing, monkeypatch):
        """Verificacion por MUTACION: se vacia un campo real del pack y el
        gate debe pasar de completo a bloqueado. Sin esto, el test anterior
        solo demuestra que hoy no falta nada, no que el gate detecte algo."""
        real = ce.validate_evidence_pack(CATALOG_REQ)
        assert real.complete is True

        loader = "factory.regulatory.requirement_catalog.requirement_catalog_loader"
        import importlib
        mod = importlib.import_module(loader)
        original = mod.get_requirement

        def mutated(req_id):
            entry = dict(original(req_id))
            entry["citation"] = {**entry["citation"], field: ""}
            return entry

        monkeypatch.setattr(mod, "get_requirement", mutated)
        verdict = ce.validate_evidence_pack(CATALOG_REQ)
        assert verdict.complete is False
        assert expected_missing in verdict.missing

    def test_mutation_missing_evidence_min_criteria_blocks(self, monkeypatch):
        """evidence_min_criteria es OPCIONAL en el JSON Schema pero
        OBLIGATORIO en §11 del plan -- el hueco exacto que el gate cubre."""
        import importlib
        mod = importlib.import_module(
            "factory.regulatory.requirement_catalog.requirement_catalog_loader")
        original = mod.get_requirement

        def mutated(req_id):
            entry = dict(original(req_id))
            entry["evidence_min_criteria"] = []
            return entry

        monkeypatch.setattr(mod, "get_requirement", mutated)
        verdict = ce.validate_evidence_pack(CATALOG_REQ)
        assert verdict.complete is False
        assert "evidence_min_criteria" in verdict.missing


class TestEvidencePackGatePartitionsCheckpoints:

    def test_real_agents_block_exactly_what_lacks_human_interpretation(self):
        """Invariante, no conteo (reescrito 2026-07-29): para TODO prompt
        gobernado del directorio, el gate bloquea exactamente sus req_id
        pendientes de interpretacion humana y admite todo lo demas.

        Antes esto recorria una lista fija de 3 archivos y exigia blocked==[]
        -- cgmp211_prompts.yaml no se habria comprobado nunca, y si se hubiera
        agregado a la lista habria fallado por hacer lo correcto."""
        import yaml
        from tests.conftest import PENDING_HUMAN_INTERPRETATION_REQ_IDS
        prompts = sorted(PROMPTS_DIR.glob("*_prompts.yaml"))
        assert len(prompts) >= 4
        for path in prompts:
            meta = yaml.safe_load(path.read_text(encoding="utf-8"))
            if "checkpoints" not in meta:
                continue
            admitted, blocked = ce.evidence_pack_gate(meta)
            req_ids = [cp["req_id"] for cp in meta["checkpoints"]]
            esperado_bloqueado = [r for r in req_ids if r in PENDING_HUMAN_INTERPRETATION_REQ_IDS]
            assert [v.req_id for v in blocked] == esperado_bloqueado, path.name
            assert [c["req_id"] for c in admitted] == \
                [r for r in req_ids if r not in PENDING_HUMAN_INTERPRETATION_REQ_IDS], path.name

    def test_mixed_meta_admits_only_the_one_with_a_pack(self):
        meta = {
            "common_contract": "c",
            "checkpoints": [
                {"req_id": CATALOG_REQ, "label": "con pack"},
                {"req_id": "REQ_SIN_PACK", "label": "sin pack"},
            ],
        }
        admitted, blocked = ce.evidence_pack_gate(meta)
        assert [c["req_id"] for c in admitted] == [CATALOG_REQ]
        assert [v.req_id for v in blocked] == ["REQ_SIN_PACK"]

    def test_blocked_checkpoint_never_reaches_the_prompt(self):
        meta = {
            "common_contract": "c",
            "checkpoints": [
                {"req_id": CATALOG_REQ, "label": "con pack"},
                {"req_id": "REQ_SIN_PACK", "label": "etiqueta que no debe viajar"},
            ],
        }
        prompt = ce.build_prompt(meta, "documento")
        assert CATALOG_REQ in prompt
        assert "REQ_SIN_PACK" not in prompt
        assert "etiqueta que no debe viajar" not in prompt

    def test_token_budget_counts_only_admitted_criteria(self):
        """El presupuesto se dimensiona sobre el contrato que SE ENVIA."""
        real = ce.load_prompt_meta(PROMPTS_DIR / "annex11_prompts.yaml")
        with_extra = {
            **real,
            "checkpoints": real["checkpoints"] + [{"req_id": "REQ_SIN_PACK", "label": "x"}],
        }
        assert ce._count_contract_criteria(with_extra) == ce._count_contract_criteria(real)


# --------------------------------------------------------------------------
# Extremo a extremo sobre evaluate_chunked: el gate debe bloquear la LLAMADA
# y no la corrida, y el requisito bloqueado no puede acabar como un
# incumplimiento afirmado. Ollama SIEMPRE mockeado (nunca modelo real).
# --------------------------------------------------------------------------

import json  # noqa: E402

import yaml  # noqa: E402

from factory.engines.gmpai_integrity import ollama_client  # noqa: E402

_REAL_REQS = ("21_CFR_11.10(a)", "21_CFR_11.10(d)", "21_CFR_11.10(e)",
              "21_CFR_11.10(g)", "21_CFR_11.50_11.70")


def _prompt_file(tmp_path, checkpoints):
    meta = ce.load_prompt_meta(PROMPTS_DIR / "part11_prompts.yaml")
    meta["checkpoints"] = checkpoints
    path = tmp_path / "prompts_bajo_prueba.yaml"
    path.write_text(yaml.safe_dump(meta, allow_unicode=True), encoding="utf-8")
    return path


def _mock_runtime(monkeypatch, calls):
    def fake_generate(prompt, *a, **k):
        calls.append(prompt)
        return {"response": json.dumps({"checkpoints": [
            {"req_id": r, "estado": "evidencia_insuficiente", "evidencia_exacta": "",
             "brecha": "n/a", "recomendacion": "n/a"} for r in _REAL_REQS
        ]})}

    monkeypatch.setattr(ollama_client, "generate", fake_generate)
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "sha256:fake")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")


class TestEvaluateChunkedBlocksTheCallNotTheRun:

    def test_blocked_requirement_is_absent_from_every_prompt_sent(self, tmp_path, monkeypatch):
        calls = []
        _mock_runtime(monkeypatch, calls)
        path = _prompt_file(tmp_path, [
            {"req_id": "21_CFR_11.10(d)", "label": "con pack"},
            {"req_id": "REQ_SIN_PACK", "label": "sin pack"},
        ])
        result = ce.evaluate_chunked(
            path, "fda_part11_agent", "1.0.0", ["Contenido de prueba. " * 100],
            "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="validation")

        assert calls, "la corrida debe continuar con el checkpoint admitido"
        assert all("REQ_SIN_PACK" not in p for p in calls)
        assert all("21_CFR_11.10(d)" in p for p in calls)
        gate = result["preflight_metadata"]["evidence_pack_gate"]
        assert gate["admitted_req_ids"] == ["21_CFR_11.10(d)"]
        assert [b["req_id"] for b in gate["blocked"]] == ["REQ_SIN_PACK"]

    def test_blocked_requirement_never_becomes_a_no_cumple(self, tmp_path, monkeypatch):
        """El riesgo real del fix: sin candidatos, la rama de ausencia emite
        'no_cumple / mayor'. Afirmar incumplimiento de un requisito que jamas
        se le mostro al modelo seria peor que el fail-open original."""
        calls = []
        _mock_runtime(monkeypatch, calls)
        path = _prompt_file(tmp_path, [
            {"req_id": "21_CFR_11.10(d)", "label": "con pack"},
            {"req_id": "REQ_SIN_PACK", "label": "sin pack"},
        ])
        result = ce.evaluate_chunked(
            path, "fda_part11_agent", "1.0.0", ["Contenido de prueba. " * 100],
            "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="validation")

        blocked = next(f for f in result["findings"]
                       if f["requisito_regulatorio"].startswith("REQ_SIN_PACK"))
        assert blocked["estado"] == "evidencia_insuficiente"
        assert blocked["estado"] != "no_cumple"
        assert "EVIDENCE_PACK_INCOMPLETE" in blocked["brecha"]
        assert blocked["revision_humana_requerida"] is True
        assert blocked["evidencia_exacta"] == ""

    def test_all_blocked_makes_zero_model_calls_and_still_completes(self, tmp_path, monkeypatch):
        """'Bloquea la llamada, no la corrida': cero inferencias, pero la
        corrida termina y deja constancia por requisito."""
        calls = []
        _mock_runtime(monkeypatch, calls)
        path = _prompt_file(tmp_path, [
            {"req_id": "REQ_SIN_PACK_1", "label": "a"},
            {"req_id": "REQ_SIN_PACK_2", "label": "b"},
        ])
        result = ce.evaluate_chunked(
            path, "fda_part11_agent", "1.0.0", ["Contenido de prueba. " * 100],
            "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="validation")

        assert calls == [], "no debe hacerse NINGUNA llamada al modelo"
        assert result["chunk_executions"], "la corrida se ejecuta y queda registrada"
        assert result["preflight_metadata"]["evidence_pack_gate"]["all_checkpoints_blocked"] is True
        assert len(result["findings"]) == 2
        assert all(f["estado"] == "evidencia_insuficiente" for f in result["findings"])
        assert all("EVIDENCE_PACK_INCOMPLETE" in f["brecha"] for f in result["findings"])

    def test_gate_block_is_not_a_technical_execution_failure(self, tmp_path, monkeypatch):
        """Un bloqueo de gobernanza no es un fallo tecnico: marcarlo como tal
        dispararia el reintento dirigido, que repetiria el bloqueo para
        siempre."""
        calls = []
        _mock_runtime(monkeypatch, calls)
        path = _prompt_file(tmp_path, [{"req_id": "REQ_SIN_PACK", "label": "a"}])
        result = ce.evaluate_chunked(
            path, "fda_part11_agent", "1.0.0", ["Contenido de prueba. " * 100],
            "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="validation")

        for execution in result["chunk_executions"]:
            assert execution["technical_execution_failure"] is False
            assert execution["failure_reason"] is None
            assert "evidence_pack_gate" in execution["error"]

    def test_real_agent_run_is_unchanged_by_the_gate(self, tmp_path, monkeypatch):
        """Guardia de no-regresion: con el prompt gobernado real, los 5
        checkpoints se envian igual que antes del fix."""
        calls = []
        _mock_runtime(monkeypatch, calls)
        result = ce.evaluate_chunked(
            PROMPTS_DIR / "part11_prompts.yaml", "fda_part11_agent", "1.0.0",
            ["Contenido de prueba. " * 100],
            "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="validation")

        assert len(calls) == len(result["chunk_executions"]) >= 1
        assert result["preflight_metadata"]["evidence_pack_gate"]["blocked"] == []
        assert len(result["findings"]) == 5
        assert all("EVIDENCE_PACK_INCOMPLETE" not in f["brecha"] for f in result["findings"])
