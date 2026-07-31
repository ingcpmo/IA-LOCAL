"""
Agente fda_cgmp_211_agent (regla predicado 21 CFR Part 211) -- 2026-07-29.

Cierra la mitad tecnica de la EXCEPCION DECLARADA de applicability_matrix
v2.1: "21_CFR_211.68(b) SI esta en el catalogo y en la matriz, pero TODAVIA
NO tiene prompt ni agente [...] falta el agente fda_cgmp_211".

Lo que se prueba aqui NO es que el agente exista (eso lo diria un `ls`),
sino las dos mitades de su estado real, que es lo unico que puede
malinterpretarse:

  (a) HOY el agente NO evalua: su unico req_id tiene el Evidence Pack en
      PENDING_HUMAN_INTERPRETATION, el gate 4 bloquea la llamada, y el
      requisito sale como no evaluado -- jamas como incumplido. "Declarado"
      no es "operativo", y aqui esta la prueba de la diferencia.

  (b) Lo unico que falta es la interpretacion humana, NO codigo: inyectando
      evidence_min_criteria (mutacion controlada, sin tocar el catalogo real)
      el agente admite su checkpoint, construye el prompt con texto normativo
      canonico y criterios numerados, y ejecuta. Si algun dia falla por otra
      razon, este test lo dira antes de que alguien lo atribuya al pack.
"""
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.engines.gmpai_integrity import ollama_client

PROMPTS_DIR = Path("factory/engines/gmpai_integrity/prompts")
PROMPT_PATH = PROMPTS_DIR / "cgmp211_prompts.yaml"
REQ = "21_CFR_211.68(b)"
LOADER = "factory.regulatory.requirement_catalog.requirement_catalog_loader"


@pytest.fixture()
def meta():
    return ce.load_prompt_meta(PROMPT_PATH)


class TestAgentDeclaration:

    def test_agent_identity_and_governance_fields(self, meta):
        assert meta["agent_id"] == "fda_cgmp_211_agent"
        assert meta["base_agent"] == "integrity"
        assert meta["profile_name"] == "integrity_cgmp211_ot_profile"
        assert meta["schema_version"] == "checkpoint_llm_response_v1"
        assert meta["prompt_version"] in {c["version"] for c in meta["changelog"]}
        assert hashlib.sha256(meta["common_contract"].encode()).hexdigest() == \
            meta["common_contract_sha256"]

    def test_single_checkpoint_is_the_ingested_predicate_rule(self, meta):
        assert [cp["req_id"] for cp in meta["checkpoints"]] == [REQ]
        for cp in meta["checkpoints"]:
            assert set(cp.keys()) == {"req_id", "label"}, (
                "el YAML gobernado solo lleva req_id+label; el texto normativo "
                "se inyecta en runtime desde el catalogo (Fase E)"
            )

    def test_checkpoint_resolves_against_the_real_ingested_source(self):
        """El req_id no es una etiqueta inventada: resuelve al texto oficial
        del XML de eCFR ingerido el 2026-07-29."""
        text = ce._lookup_regulatory_text(REQ)
        assert text is not None
        assert "Appropriate controls shall be exercised over computer" in text
        assert "§ 211.68, paragraph (b)" in text

    def test_contract_forbids_importing_part11_requirements(self, meta):
        """Regla 5 -- razon de ser del agente separado. Sin ella, el modelo
        resuelve un requisito predicado citando controles de Part 11, que es
        el falso cumplimiento que motivo un agente por fuente."""
        contract = meta["common_contract"]
        assert "REGLA PREDICADO" in contract
        assert "no importes" in contract
        assert "criterion_assessments" in contract and "criterion_index" in contract

    def test_profile_is_declared_in_the_integrity_profiles_catalog(self, meta):
        profiles = yaml.safe_load(
            Path("factory/profiles/integrity_profiles.yaml").read_text(encoding="utf-8")
        )["profiles"]
        profile = profiles[meta["profile_name"]]
        assert profile["base_agent"] == meta["base_agent"]
        assert len(profile["test_questions"]) >= 3, "checklist de perfil derivado"

    def test_requirement_terms_exist_for_relevance_scoring(self):
        """Sin terminos, verify_semantic_relevance devuelve NOT_VERIFIABLE
        para este requisito y todo hallazgo suyo nace marcado para revision."""
        from factory.regulatory.evidence_verifier import load_requirement_terms
        assert load_requirement_terms(REQ)


class TestWhenTheEvidencePackLacksCriteria:
    """Mitad (a): declarado != operativo -- la REGLA, no la foto de un dia.

    `21_CFR_211.68(b)` tuvo evidence_min_criteria real desde el 2026-07-30
    (G4). Este bloque prueba el mismo comportamiento que probaba cuando el
    pack estaba vacio, quitando el campo via mutacion controlada -- asi la
    prueba no depende de que el catalogo siga o deje de estar interpretado
    (el proximo requisito sin redactar entra en el mismo caso)."""

    @pytest.fixture()
    def without_human_criteria(self, monkeypatch):
        import importlib
        mod = importlib.import_module(LOADER)
        original = mod.get_requirement

        def mutated(req_id):
            entry = dict(original(req_id))
            if req_id == REQ:
                entry["evidence_min_criteria"] = []
            return entry

        monkeypatch.setattr(mod, "get_requirement", mutated)
        return mod

    def test_gate_4_blocks_the_checkpoint_without_criteria(self, meta, without_human_criteria):
        admitted, blocked = ce.evidence_pack_gate(meta)
        assert admitted == []
        assert [v.req_id for v in blocked] == [REQ]
        assert "evidence_min_criteria" in blocked[0].missing

    def test_nothing_of_the_requirement_reaches_the_prompt(self, meta, without_human_criteria):
        prompt = ce.build_prompt(meta, "documento de prueba")
        assert REQ not in prompt
        assert "Texto normativo canonico" not in prompt
        assert "Criterios minimos de evidencia" not in prompt

    def test_run_makes_zero_model_calls_and_never_affirms_non_compliance(
            self, tmp_path, monkeypatch, without_human_criteria):
        """El desenlace que importa: la corrida termina, no gasta ninguna
        inferencia, y el requisito sale como NO EVALUADO. Un 'no_cumple' aqui
        seria un incumplimiento afirmado sobre un requisito que jamas se le
        mostro al modelo."""
        calls = []
        monkeypatch.setattr(ollama_client, "generate",
                            lambda prompt, *a, **k: calls.append(prompt) or {"response": "{}"})
        monkeypatch.setattr(ollama_client, "show_digest", lambda: "sha256:fake")
        monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")

        result = ce.evaluate_chunked(
            PROMPT_PATH, "fda_cgmp_211_agent", "1.0.0", ["Contenido de prueba. " * 100],
            "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-cgmp211",
            run_context="validation")

        assert calls == []
        gate = result["preflight_metadata"]["evidence_pack_gate"]
        assert gate["all_checkpoints_blocked"] is True
        assert [b["req_id"] for b in gate["blocked"]] == [REQ]
        assert result["chunk_executions"], "la corrida se ejecuta y queda registrada"
        assert all(e["technical_execution_failure"] is False for e in result["chunk_executions"])

        finding = next(f for f in result["findings"]
                       if f["requisito_regulatorio"].startswith(REQ))
        assert finding["estado"] == "evidencia_insuficiente"
        assert "EVIDENCE_PACK_INCOMPLETE" in finding["brecha"]
        assert finding["revision_humana_requerida"] is True


class TestOnlyHumanInterpretationIsMissing:
    """Mitad (b): con criterios redactados, el agente funciona sin tocar
    codigo. `21_CFR_211.68(b)` ya tiene evidence_min_criteria real desde
    G4 (2026-07-30) -- esta mutacion los SOBRESCRIBE con un set corto de
    prueba (sin tocar el catalogo real) para no acoplar este test al
    contenido interpretativo vigente, que puede crecer sin romper esto."""

    CRITERIA = [
        "Los cambios en recetas/setpoints solo pueden instituirse por personal autorizado.",
        "Existe verificacion documentada de exactitud de entrada/salida del sistema.",
        "Existe respaldo (backup) de los datos ingresados al sistema.",
    ]

    @pytest.fixture()
    def with_human_criteria(self, monkeypatch):
        import importlib
        mod = importlib.import_module(LOADER)
        original = mod.get_requirement

        def mutated(req_id):
            entry = dict(original(req_id))
            if req_id == REQ:
                entry["evidence_min_criteria"] = list(self.CRITERIA)
            return entry

        monkeypatch.setattr(mod, "get_requirement", mutated)
        return mod

    def test_gate_admits_the_checkpoint_once_criteria_exist(self, meta, with_human_criteria):
        admitted, blocked = ce.evidence_pack_gate(meta)
        assert [c["req_id"] for c in admitted] == [REQ]
        assert blocked == []

    def test_prompt_carries_canonical_text_and_numbered_criteria(
            self, meta, with_human_criteria):
        prompt = ce.build_prompt(meta, "documento de prueba")
        assert REQ in prompt
        assert "Appropriate controls shall be exercised over computer" in prompt
        assert "Criterios minimos de evidencia" in prompt
        for i, criterion in enumerate(self.CRITERIA, start=1):
            assert f"{i}. {criterion}" in prompt

    def test_token_budget_is_derived_from_this_contract(self, meta, with_human_criteria):
        """El presupuesto sale del contrato real (1 checkpoint, N criterios),
        no de una constante escrita a mano para los otros tres agentes."""
        assert ce._count_contract_criteria(meta) == len(self.CRITERIA)
        assert ce.output_token_budget(1, len(self.CRITERIA)) == \
            ce.output_token_budget(len(meta["checkpoints"]), ce._count_contract_criteria(meta))

    def test_run_sends_the_requirement_and_produces_a_finding(
            self, tmp_path, monkeypatch, with_human_criteria):
        calls = []

        def fake_generate(prompt, *a, **k):
            calls.append(prompt)
            return {"response": json.dumps({"checkpoints": [{
                "req_id": REQ, "estado": "evidencia_insuficiente", "evidencia_exacta": "",
                "brecha": "n/a", "recomendacion": "n/a", "criterion_assessments": [],
            }]})}

        monkeypatch.setattr(ollama_client, "generate", fake_generate)
        monkeypatch.setattr(ollama_client, "show_digest", lambda: "sha256:fake")
        monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")

        result = ce.evaluate_chunked(
            PROMPT_PATH, "fda_cgmp_211_agent", "1.0.0", ["Contenido de prueba. " * 100],
            "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-cgmp211-ok",
            run_context="validation")

        assert calls, "con el pack completo el agente SI llama al modelo"
        assert all(REQ in p for p in calls)
        assert result["preflight_metadata"]["evidence_pack_gate"]["blocked"] == []
        finding = next(f for f in result["findings"]
                       if f["requisito_regulatorio"].startswith(REQ))
        assert "EVIDENCE_PACK_INCOMPLETE" not in finding["brecha"]


class TestLayer8SelectsTheAgent:
    """Sin esto el agente existe pero ninguna mision lo elige nunca: la
    deteccion de 21_CFR_PART_211 ya existia en REGULATORY_KEYWORDS y moria
    ahi."""

    def _spec(self, **kwargs):
        from factory.layer8.requirement_interpreter import RequirementSpec
        base = dict(
            project_id="p1", domains=[], regulatory_scope=[], dual_use=False,
            part11_required=False, alcoa_plus_required=False, annex11_required=False,
            client_needs=[], constraints=[], pending_documents=[], raw_objective="",
        )
        return RequirementSpec(**{**base, **kwargs})

    def test_predicate_rule_in_the_objective_reaches_the_spec(self):
        from factory.layer8.requirement_interpreter import extract_regulatory_scope
        scope = extract_regulatory_scope(
            {"objective": "Validar documentacion SCADA bajo 21 CFR Part 211", "regulatory_scope": []})
        assert scope["cgmp211_required"] is True

    def test_spec_defaults_to_false_for_existing_callers(self):
        assert self._spec().cgmp211_required is False

    def test_agent_is_proposed_when_required(self):
        from factory.layer8.agent_design_engine import decide_inherited_profiles_custom
        decisions = decide_inherited_profiles_custom(self._spec(cgmp211_required=True))
        decision = next(d for d in decisions if d.agent_id == "fda_cgmp_211_agent")
        assert decision.decision == "profile"
        assert decision.profile_name == "integrity_cgmp211_ot_profile"

    def test_agent_is_not_proposed_when_not_required(self):
        from factory.layer8.agent_design_engine import decide_inherited_profiles_custom
        decisions = decide_inherited_profiles_custom(self._spec(part11_required=True))
        assert all(d.agent_id != "fda_cgmp_211_agent" for d in decisions)
