"""Tests -- factory/regulatory/retrieval/rerank.py (V2, B3).

docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md FASE 4.2:
reranker léxico determinista contra el texto del sub-criterio. Sin
modelo, sin LLM, sin descargas. Determinista y estable.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.retrieval import rerank as rr


def test_lexical_score_deterministic():
    a = rr.lexical_score("audit trail record with timestamp", "the system writes an audit trail record with a timestamp")
    b = rr.lexical_score("audit trail record with timestamp", "the system writes an audit trail record with a timestamp")
    assert a == b
    assert a > 0


def test_lexical_score_rewards_overlap_and_bigrams():
    sc = "cada entrada del audit trail registra fecha y hora"
    strong = "cada entrada del audit trail incluye la fecha y hora del evento"
    weak = "el manual de usuario describe la pantalla principal del sistema"
    assert rr.lexical_score(sc, strong) > rr.lexical_score(sc, weak)


def test_rerank_orders_by_relevance_and_is_stable():
    sc = "el acceso para modificar el audit trail está restringido a usuarios privilegiados"
    cands = [
        {"text": "la pantalla muestra la temperatura actual del reactor"},
        {"text": "solo usuarios con rol administrador pueden modificar el audit trail; el resto tiene acceso de solo lectura"},
        {"text": "el sistema arranca al energizar el panel"},
        {"text": "el audit trail se puede exportar a csv para inspección"},
    ]
    out = rr.rerank(sc, cands, top_k=2)
    assert len(out) == 2
    assert "usuarios con rol administrador" in out[0]["text"]
    assert out[0]["rerank_score"] >= out[1]["rerank_score"]
    assert out[0]["rerank_method"] == "lexical_v1"


def test_rerank_ties_preserve_input_order():
    cands = [{"text": "zzz none"}, {"text": "yyy none"}, {"text": "xxx none"}]
    out = rr.rerank("completely unrelated query about elephants", cands, top_k=3)
    assert [c["text"] for c in out] == ["zzz none", "yyy none", "xxx none"]


def test_rerank_top_k_bound():
    cands = [{"text": f"audit trail item {i}"} for i in range(30)]
    assert len(rr.rerank("audit trail", cands, top_k=5)) == 5


def test_cross_encoder_reranker_absent_raises_not_silently_wrong():
    """El hook opcional no está cableado; instanciarlo sin el modelo debe
    fallar explícito, nunca degradar en silencio."""
    import pytest
    try:
        import sentence_transformers  # noqa: F401
    except Exception:
        with pytest.raises(RuntimeError):
            rr.CrossEncoderReranker()
    else:
        pytest.skip("sentence-transformers presente en el entorno; el hook podría instanciarse")
