"""
Fase M1 (2026-08-17) -- fix del runner exact-page (Palanca A):
`corpus_runner._extract_pilot_excerpt()` devuelve solo las páginas reales
pedidas (p.ej. página 45 de un PDF de 60), pero `build_page_chunks()`
renumeraba SIEMPRE 1..N por posición dentro de la lista -- una unidad de
1 página quedaba grabada con `evidence_page`/`page_start`=1 sin importar
cuál página real era. El excerpt en sí (el texto que ve el modelo) siempre
fue correcto; solo la metadata de procedencia mentía.

Ver factory/engines/gmpai_integrity/chunked_engine.py::build_page_chunks
(parámetro `page_numbers`) y factory/regulatory/corpus_runner.py
(run_pilot_sample_batch, `page_numbers=[i + 1 for i in unit.page_indices]`).

Nota de alcance honesta (V0, docs_plan/V0_TRUNCAMIENTO/V0_REPORTE.md,
2026-08-17): el raw_response original del caso L4 (chunk truncado con
num_predict=3072 sobre un contrato de 20 criterios) NO existe en este
repositorio -- se perdió con el reinicio de la VM, confirmado por
búsqueda exhaustiva el mismo día que esta fase. El replay test-first
pedido contra ese raw específico no es ejecutable con datos reales; no se
fabrica un sustituto presentado como el original. Lo que SÍ es real y
verificable aquí:
  (a) el presupuesto de salida ya se deriva del contrato (commit
      `c2d58e8`, TestOutputTokenBudget/TestPreflightContextGuard en
      test_output_token_budget.py, preexistente a esta fase) y el
      preflight falla ANTES de gastar una llamada si prompt+num_predict
      no cabe en num_ctx -- eso es la clase de fallo P-1 ya cerrada,
      no una promesa;
  (b) el fix de este archivo (runner exact-page / evidence_page).
"""
from __future__ import annotations

from pathlib import Path

from factory.engines.gmpai_integrity import chunked_engine as ce

PROMPTS = Path(ce.__file__).parent / "prompts"
ANNEX11 = PROMPTS / "annex11_prompts.yaml"


class TestBuildPageChunksRealPageNumbers:

    def test_default_behavior_unchanged_without_page_numbers(self):
        """Ningun llamador existente (CorpusRunUnit / _default_extractor,
        que SI trae todas las paginas del documento en orden) cambia de
        comportamiento: 1..N por posicion sigue siendo el default."""
        chunks = ce.build_page_chunks(["pagina uno", "pagina dos"])
        assert [c["page_start"] for c in chunks] == [1]
        assert chunks[0]["page_end"] == 2

    def test_single_page_excerpt_persists_the_real_page_not_one(self):
        """El caso exacto del defecto: una unidad de 1 sola pagina real
        (p.ej. pagina 45 de un PDF de 60) ya no se graba como pagina 1."""
        chunks = ce.build_page_chunks(["texto de la pagina real"], page_numbers=[45])
        assert len(chunks) == 1
        assert chunks[0]["page_start"] == 45
        assert chunks[0]["page_end"] == 45

    def test_non_contiguous_pages_each_keep_their_real_number(self):
        """paginas 39 y 44 (no consecutivas, como en el runner exact-page
        real de Palanca A) -- se conservan como numero real, no 1 y 2.
        Ambas caben en un solo chunk (textos cortos): el chunk declara su
        rango real page_start=39/page_end=44, nunca 1/2."""
        chunks = ce.build_page_chunks(["contenido pagina 39", "contenido pagina 44"],
                                       page_numbers=[39, 44])
        assert len(chunks) == 1
        assert chunks[0]["page_start"] == 39
        assert chunks[0]["page_end"] == 44

    def test_mismatched_length_is_rejected(self):
        import pytest
        with pytest.raises(ValueError):
            ce.build_page_chunks(["solo una pagina"], page_numbers=[10, 20])


class TestEvaluateChunkedPropagatesRealPageNumbers:

    def test_evidence_page_reflects_the_real_page_end_to_end(self):
        """page_numbers llega hasta chunk_executions -- no solo hasta
        build_page_chunks. Sin llamar a Ollama: provider falso deterministico."""
        import json

        class _FakeProvider:
            model_name = "fake-model"
            context_window = 16384

            def __init__(self):
                self.calls = []

            def generate(self, prompt, *, num_predict=None):
                self.calls.append(num_predict)
                meta = ce.load_prompt_meta(ANNEX11)
                payload = {"checkpoints": [
                    {"req_id": cp["req_id"], "estado": "evidencia_insuficiente",
                     "evidencia_exacta": "", "brecha": "", "recomendacion": ""}
                    for cp in meta["checkpoints"]
                ]}
                return {"response": json.dumps(payload), "done_reason": "stop"}

            def show_digest(self):
                return "sha256:fake-digest"

            def runtime_version(self):
                return "0.0.0-fake"

        provider = _FakeProvider()
        result = ce.evaluate_chunked(
            ANNEX11, "eu_annex11_agent", "v-test", ["texto de la pagina real"],
            "sys", "doc", "v1", "doc.pdf", "a" * 64, run_context="validation",
            provider=provider, page_numbers=[45],
        )
        assert result["chunk_executions"][0]["page_start"] == 45
        assert result["chunk_executions"][0]["page_end"] == 45


class TestOutputBudgetScalesWithContractNotAFixedValue:
    """Complementa TestOutputTokenBudget (test_output_token_budget.py,
    preexistente): confirma explicitamente que un contrato de 1 criterio
    (cgmp211) recibe MENOS presupuesto que uno de 20 (annex11) -- el
    calculo escala con el contrato real, no es un numero fijo disfrazado
    de formula."""

    def test_cgmp211_one_criterion_gets_less_budget_than_annex11_twenty(self):
        cgmp211_budget = ce.output_token_budget(1, 1)
        annex11_budget = ce.output_token_budget(5, 20)
        assert cgmp211_budget < annex11_budget
