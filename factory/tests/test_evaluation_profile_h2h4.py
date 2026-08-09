"""`evaluation_profile` de `chunked_engine.evaluate_chunked()` (R1.5,
docs_plan/R1_5_PRODUCTIZACION_H2H4.md) -- productiza la configuración H2
(1 requirement_id por llamada, la única que midió 2/7 de recall sobre el
fixture set 7P+2N -- ver docs_plan/W5V2_RECALL_EXPERIMENTS_RESULTADOS.md)
desde los scripts de diagnóstico aislados (h2_experiment.py/
h4_experiment.py, nunca versionados) al motor real.

Ollama SIEMPRE mockeado (nunca un modelo real en la suite pytest) --
mismo patrón que test_gmpai_chunked_engine.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.engines.gmpai_integrity import ollama_client
from factory.regulatory import corpus_runner as runner
from factory.regulatory import model_qualification_gate as mqg
from factory.tests.test_corpus_runner import FakeCorpusProvider

ALCOA_PROMPT_PATH = (
    Path(__file__).parent.parent / "engines" / "gmpai_integrity" / "prompts" / "alcoa_prompts.yaml"
)
ALL_ALCOA_REQ_IDS = [cp["req_id"] for cp in ce.load_prompt_meta(ALCOA_PROMPT_PATH)["checkpoints"]]


def _ollama_response(payload: dict) -> dict:
    return {"response": json.dumps(payload), "done": True, "done_reason": "stop"}


def _single_checkpoint_payload(req_id: str, *, estado: str = "evidencia_insuficiente",
                               evidencia: str = "") -> dict:
    return {"checkpoints": [
        {"req_id": req_id, "estado": estado, "evidencia_exacta": evidencia,
         "brecha": "n/a", "recomendacion": "n/a"},
    ]}


def _all_checkpoints_payload(req_ids: list[str]) -> dict:
    return {"checkpoints": [
        {"req_id": r, "estado": "evidencia_insuficiente", "evidencia_exacta": "",
         "brecha": "n/a", "recomendacion": "n/a"}
        for r in req_ids
    ]}


@pytest.fixture(autouse=True)
def _stub_ollama(monkeypatch):
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "sha256:fake-digest")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")


# ===========================================================================
# 1. Regresión: sin pedir perfil, BASELINE idéntico al contrato de siempre
# ===========================================================================

def test_baseline_sin_perfil_evalua_todos_los_checkpoints_del_agente(monkeypatch):
    captured_prompts = []

    def fake_generate(prompt, *a, **k):
        captured_prompts.append(prompt)
        return _ollama_response(_all_checkpoints_payload(ALL_ALCOA_REQ_IDS))

    monkeypatch.setattr(ollama_client, "generate", fake_generate)
    result = ce.evaluate_chunked(
        ALCOA_PROMPT_PATH, "alcoa_plus_agent", "1.0.0", ["Texto de una pagina real. " * 40],
        "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="production")

    assert len(captured_prompts) == 1
    prompt = captured_prompts[0]
    for req_id in ALL_ALCOA_REQ_IDS:
        assert f"- {req_id}:" in prompt, f"{req_id} debe seguir en el prompt BASELINE"
    assert len(result["findings"]) == len(ALL_ALCOA_REQ_IDS)
    assert result["preflight_metadata"]["evaluation_profile"] == "BASELINE"
    assert result["preflight_metadata"]["target_requirement_ids"] is None
    assert result["preflight_metadata"]["run_fingerprint"]["evaluation_profile"] == "BASELINE"
    assert result["preflight_metadata"]["run_fingerprint"]["target_requirement_ids"] is None


def test_baseline_explicito_es_identico_a_no_pasar_el_parametro(monkeypatch):
    """Guardián del contrato (§2 de R1_5_PRODUCTIZACION_H2H4.md): pedir
    BASELINE explícitamente no puede diferir de omitir el parámetro."""
    prompts_by_call = {}

    def fake_generate(prompt, *a, **k):
        prompts_by_call.setdefault("prompt", prompt)
        return _ollama_response(_all_checkpoints_payload(ALL_ALCOA_REQ_IDS))

    monkeypatch.setattr(ollama_client, "generate", fake_generate)

    kwargs = dict(
        agent_id="alcoa_plus_agent", agent_version="1.0.0",
        per_unit_text=["Texto de una pagina real. " * 40],
        sistema="Rockwell", documento="doc.pdf", version="1.0", archivo="path/doc.pdf",
        document_sha256="sha-test", run_context="production")

    r_implicit = ce.evaluate_chunked(ALCOA_PROMPT_PATH, **kwargs)
    prompt_implicit = prompts_by_call["prompt"]
    prompts_by_call.clear()
    r_explicit = ce.evaluate_chunked(ALCOA_PROMPT_PATH, evaluation_profile="BASELINE", **kwargs)
    prompt_explicit = prompts_by_call["prompt"]

    assert prompt_implicit == prompt_explicit
    assert r_implicit["preflight_metadata"]["run_fingerprint"] == r_explicit["preflight_metadata"]["run_fingerprint"]


# ===========================================================================
# 2. Perfil H2H4: filtra a UN solo requirement_id, reutiliza el prompt real
# ===========================================================================

def test_h2h4_filtra_el_prompt_a_un_solo_requirement(monkeypatch):
    captured_prompts = []

    def fake_generate(prompt, *a, **k):
        captured_prompts.append(prompt)
        return _ollama_response(_single_checkpoint_payload(
            "ALCOA_CONTEMPORANEOUS", estado="cumple", evidencia="cita literal de prueba"))

    monkeypatch.setattr(ollama_client, "generate", fake_generate)
    result = ce.evaluate_chunked(
        ALCOA_PROMPT_PATH, "alcoa_plus_agent", "1.0.0", ["cita literal de prueba " * 40],
        "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="production",
        evaluation_profile="H2H4", target_requirement_ids=["ALCOA_CONTEMPORANEOUS"])

    prompt = captured_prompts[0]
    assert "- ALCOA_CONTEMPORANEOUS:" in prompt
    for req_id in ALL_ALCOA_REQ_IDS:
        if req_id != "ALCOA_CONTEMPORANEOUS":
            assert f"- {req_id}:" not in prompt, (
                f"{req_id} NO debe aparecer en el prompt H2H4 filtrado a ALCOA_CONTEMPORANEOUS")
    # mismo common_contract/schema gobernado -- H2H4 no reescribe el prompt,
    # solo reduce la lista de checkpoints (nota honesta de alcance, ver
    # docstring de evaluate_chunked).
    assert "Responde EXCLUSIVAMENTE" in prompt or "JSON" in prompt

    assert len(result["findings"]) == 1
    assert result["findings"][0]["requisito_regulatorio"].startswith("ALCOA_CONTEMPORANEOUS")
    assert result["preflight_metadata"]["evaluation_profile"] == "H2H4"
    assert result["preflight_metadata"]["target_requirement_ids"] == ["ALCOA_CONTEMPORANEOUS"]


def test_h2h4_reduce_el_presupuesto_de_salida_frente_a_baseline(monkeypatch):
    """La mayor parte de la ganancia de velocidad de H4 (schema minimo) se
    obtiene gratis al filtrar: output_token_budget() escala con
    n_checkpoints Y n_criteria, ambos menores tras el filtro -- sin tocar
    el schema. Ver nota honesta de alcance en evaluate_chunked()."""
    captured_num_predict = []

    def fake_generate(prompt, *, num_predict=None):
        captured_num_predict.append(num_predict)
        return _ollama_response(_single_checkpoint_payload("ALCOA_CONTEMPORANEOUS"))

    monkeypatch.setattr(ollama_client, "generate", fake_generate)
    ce.evaluate_chunked(
        ALCOA_PROMPT_PATH, "alcoa_plus_agent", "1.0.0", ["texto " * 40],
        "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="production",
        evaluation_profile="H2H4", target_requirement_ids=["ALCOA_CONTEMPORANEOUS"])
    h2h4_num_predict = captured_num_predict[0]

    captured_num_predict.clear()
    monkeypatch.setattr(ollama_client, "generate",
                        lambda prompt, num_predict=None: (
                            captured_num_predict.append(num_predict),
                            _ollama_response(_all_checkpoints_payload(ALL_ALCOA_REQ_IDS)))[1])
    ce.evaluate_chunked(
        ALCOA_PROMPT_PATH, "alcoa_plus_agent", "1.0.0", ["texto " * 40],
        "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="production")
    baseline_num_predict = captured_num_predict[0]

    assert h2h4_num_predict < baseline_num_predict


# ===========================================================================
# 3. Guardias de entrada
# ===========================================================================

def test_h2h4_exige_target_requirement_ids():
    with pytest.raises(ValueError, match="target_requirement_ids"):
        ce.evaluate_chunked(
            ALCOA_PROMPT_PATH, "alcoa_plus_agent", "1.0.0", ["texto"],
            "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="production",
            evaluation_profile="H2H4")


def test_h2h4_rechaza_requirement_id_inexistente_en_el_prompt_real():
    with pytest.raises(ValueError, match="no existen en el prompt real"):
        ce.evaluate_chunked(
            ALCOA_PROMPT_PATH, "alcoa_plus_agent", "1.0.0", ["texto"],
            "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="production",
            evaluation_profile="H2H4", target_requirement_ids=["NO_EXISTE_EN_ALCOA"])


def test_evaluation_profile_invalido_rechazado():
    with pytest.raises(ValueError, match="evaluation_profile"):
        ce.evaluate_chunked(
            ALCOA_PROMPT_PATH, "alcoa_plus_agent", "1.0.0", ["texto"],
            "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="production",
            evaluation_profile="H2")  # ni BASELINE ni H2H4 -- typo deliberado


# ===========================================================================
# 4. El perfil invalida cache: un checkpoint BASELINE no se reanuda como H2H4
# ===========================================================================

def test_cambiar_de_perfil_invalida_el_checkpoint_y_no_reanuda(monkeypatch, tmp_path):
    monkeypatch.setattr(ollama_client, "generate",
                        lambda prompt, num_predict=None: _ollama_response(
                            _all_checkpoints_payload(ALL_ALCOA_REQ_IDS)))
    store = ce.CheckpointStore(tmp_path / "ckpt")
    baseline_result = ce.evaluate_chunked(
        ALCOA_PROMPT_PATH, "alcoa_plus_agent", "1.0.0", ["texto " * 40],
        "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="production",
        checkpoint_store=store)
    assert baseline_result["preflight_metadata"]["resumed_chunk_count"] == 0

    monkeypatch.setattr(ollama_client, "generate",
                        lambda prompt, num_predict=None: _ollama_response(
                            _single_checkpoint_payload("ALCOA_CONTEMPORANEOUS")))
    h2h4_result = ce.evaluate_chunked(
        ALCOA_PROMPT_PATH, "alcoa_plus_agent", "1.0.0", ["texto " * 40],
        "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="production",
        checkpoint_store=store, evaluation_profile="H2H4",
        target_requirement_ids=["ALCOA_CONTEMPORANEOUS"])
    assert h2h4_result["preflight_metadata"]["resumed_chunk_count"] == 0, (
        "un checkpoint BASELINE no debe poder reanudarse bajo perfil H2H4 -- "
        "el prompt real que vio el modelo es distinto")
    assert h2h4_result["run_id"] != baseline_result["run_id"]


# ===========================================================================
# 5. Integración con corpus_runner.run_pilot_sample_batch
# ===========================================================================

def _sample_unit(document_id="RW-0005", agent_id="alcoa_plus_agent",
                 requirement_id="ALCOA_CONTEMPORANEOUS", page_indices=(0,)):
    return runner.PilotSampleUnit(
        document_id=document_id, document_type="FS", agent_id=agent_id,
        requirement_id=requirement_id, page_indices=page_indices,
        selection_reason="fixture de test para evaluation_profile")


class _Scope:
    def __init__(self, authorized=True, covering_instances=("PILOT-INST-1",), denial_reason=None):
        self.authorized = authorized
        self.covering_instances = set(covering_instances)
        self.denial_reason = denial_reason


@pytest.fixture()
def _authorized_pilot(monkeypatch, tmp_path):
    from factory.core import decision_scope_resolver as resolver

    monkeypatch.setattr(runner, "PILOT_CHECKPOINT_DIR", tmp_path / "pilot_checkpoints")
    monkeypatch.setattr(runner, "PILOT_MANIFEST_DIR", tmp_path / "pilot_manifests")
    monkeypatch.setattr(mqg, "require_inference_authorized", lambda *a, **k: None)
    monkeypatch.setattr(runner, "mqg", mqg)
    monkeypatch.setattr(runner, "_write_batch_event", lambda *a, **k: None)
    monkeypatch.setattr(runner, "_resolve_document_path",
                        lambda doc_id: (runner.PROMPTS_DIR, "0" * 64))
    monkeypatch.setattr(runner, "_extract_pilot_excerpt",
                        lambda path, page_indices: ["Texto corto real de prueba." * 10
                                                     for _ in page_indices])

    def fake_resolve(family, target_id, *, store_file=None):
        return _Scope()
    monkeypatch.setattr(resolver, "resolve", fake_resolve)
    monkeypatch.setattr(runner, "resolver", resolver)
    monkeypatch.setattr(runner.decision_store, "read_all", lambda store_file=None: [
        {"decision_instance_id": "PILOT-INST-1",
         "payload": {"max_calls": 5, "authorizes_corpus": False, "authorizes_baseline": False}},
    ])
    return tmp_path


def _checkpoint_fingerprint(checkpoint_dir: Path, run_id: str) -> dict:
    import json as _json
    matches = list(Path(checkpoint_dir).glob(f"{run_id}*.checkpoint.json"))
    assert matches, f"no se encontro checkpoint para run_id={run_id!r} en {checkpoint_dir}"
    return _json.loads(matches[0].read_text(encoding="utf-8"))["fingerprint"]


def test_run_pilot_sample_batch_default_profile_es_baseline(_authorized_pilot):
    """Regresión explícita: un llamador que no pide perfil (todos los
    existentes hoy) sigue produciendo un checkpoint BASELINE -- cero cambio
    de comportamiento. Corre evaluate_chunked REAL (nunca mockeado a este
    nivel, para no filtrarse hacia evaluate_model_qualification() -- que
    también llama a chunked_engine internamente contra el mismo módulo)."""
    ckpt_dir = _authorized_pilot / "ckpt"
    summary = runner.run_pilot_sample_batch(
        [_sample_unit()], provider=FakeCorpusProvider(),
        checkpoint_dir=ckpt_dir, manifest_dir=_authorized_pilot / "manifest")

    assert summary.evaluation_profile == "BASELINE"
    assert summary.units[0].status == "COMPLETED"
    fp = _checkpoint_fingerprint(ckpt_dir, summary.units[0].run_id)
    assert fp["evaluation_profile"] == "BASELINE"
    assert fp["target_requirement_ids"] is None


def test_run_pilot_sample_batch_h2h4_pasa_el_requirement_id_de_la_unidad(_authorized_pilot):
    ckpt_dir = _authorized_pilot / "ckpt"
    unit = _sample_unit(requirement_id="ALCOA_CONTEMPORANEOUS")
    summary = runner.run_pilot_sample_batch(
        [unit], provider=FakeCorpusProvider(),
        checkpoint_dir=ckpt_dir, manifest_dir=_authorized_pilot / "manifest",
        evaluation_profile="H2H4")

    assert summary.evaluation_profile == "H2H4"
    assert summary.units[0].status == "COMPLETED"
    fp = _checkpoint_fingerprint(ckpt_dir, summary.units[0].run_id)
    assert fp["evaluation_profile"] == "H2H4"
    assert fp["target_requirement_ids"] == ["ALCOA_CONTEMPORANEOUS"]
