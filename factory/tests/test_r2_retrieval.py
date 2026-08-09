"""
R2 (docs_plan/R2_DESIGN_DETALLADO.md, 2026-08-09) -- recuperación
determinista de evidencia (BM25 stdlib, sin dependencias nuevas). Cero
llamadas LLM en todo este archivo -- ni siquiera el pipeline de juicio
(evaluate_chunked) se importa aquí; R2 es una etapa previa e
independiente.

Corre contra el corpus real GMPAI/source/Rockwell/ (mismo patrón que
test_source_baseline_allowlist.py) -- documentos reales ya usados en
R1.5/R1.6/R1.7, hash SHA-256 verificado contra el allowlist real.

Resultados verificados empíricamente antes de fijar los asserts (no
asumidos del diseño original): retrieval_recall_at_5 = 4/7 sobre los 7
positivos del fixture (P1, P4, P6, P7 sí; P2, P3, P5 no -- P5 es
justamente el caso que R1.6/R1.7 ya mostró que el modelo cita de forma
parafraseada, sin vocabulario gobernado literal, así que BM25 -- también
léxico -- tiene el mismo punto ciego). retrieval_recall_at_10 = 6/7.
Ambos negativos del fixture (N1/ANNEX11_4, N2/tabla de contenidos)
confirmados FUERA del top-5."""
from __future__ import annotations

from pathlib import Path

import pytest

from factory.regulatory.retrieval import bm25, indexer, query_builder, retriever

_SOURCE_DIR = Path("/home/ing_cpmo/GMPAI/source/Rockwell")
_RW_0005 = _SOURCE_DIR / "215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"
_RW_0011 = _SOURCE_DIR / "MCCPDC EMS Control Block Narrative revB.pdf"
_RW_0012 = _SOURCE_DIR / "MCCPDC PCS Signal Interface Control Block Narrative.pdf"

_RW_0005_SHA256 = "56095a7541fbb62e30d00e77308fde4c2ac0f4ec945adbf19a968b79debc82eb"

pytestmark = pytest.mark.skipif(
    not _RW_0005.exists(), reason="corpus real GMPAI/source/Rockwell/ no disponible en este entorno"
)


@pytest.fixture(autouse=True)
def isolated_retrieval_index(tmp_path, monkeypatch):
    """Redirige indexer.INDEX_DIR a un temporal -- el índice real
    (gitignored, regenerable) no debe depender del orden de ejecución de
    tests ni acumular basura entre corridas."""
    monkeypatch.setattr(indexer, "INDEX_DIR", tmp_path / "retrieval_index")


def test_indexing_real_document_matches_known_sha256():
    """Confirma que se está indexando el MISMO documento real que usó
    R1.5/R1.6/R1.7 (mismo SHA-256 ya registrado en el allowlist real),
    no una copia ni una versión distinta."""
    idx = indexer.build_index(_RW_0005)
    assert idx["document_sha256"] == _RW_0005_SHA256
    assert len(idx["chunks"]) > 0


def test_indexing_is_idempotent(tmp_path, monkeypatch):
    idx1 = indexer.build_index(_RW_0005)
    mtime1 = (indexer.INDEX_DIR / f"{_RW_0005_SHA256}.json").stat().st_mtime_ns
    idx2 = indexer.build_index(_RW_0005)
    mtime2 = (indexer.INDEX_DIR / f"{_RW_0005_SHA256}.json").stat().st_mtime_ns
    assert idx1 == idx2
    assert mtime1 == mtime2, "no debe reescribir el archivo si el sha256 ya tiene indice"


def test_build_retrieval_query_never_empty_or_weak_keywords_only():
    for req_id in ("ALCOA_CONTEMPORANEOUS", "21_CFR_11.10(e)", "ANNEX11_4", "21_CFR_211.68(b)"):
        query = query_builder.build_retrieval_query(req_id)
        assert query.strip()
        # la query real siempre trae citation_text (frase larga, gobernada) --
        # nunca queda reducida a un puñado de weak_keywords sueltas
        assert len(bm25.tokenize(query)) > 10, (
            req_id, "query sospechosamente corta -- ¿se coló un fallback a weak_keywords?")


class TestPurRetrievalMetricAgainstFixture7P2N:
    """El entregable de esta corrida: retrieval_recall_at_k sobre el
    fixture set real, sin llamada LLM. Ver docs_plan/R2_DESIGN_DETALLADO.md
    "Métrica de recuperación pura"."""

    @staticmethod
    def _rank_of_page(document_path: Path, req_id: str, target_page_1indexed: int) -> int | None:
        idx = indexer.build_index(document_path)
        results_all = retriever.retrieve_top_k(idx["document_sha256"], req_id, k=len(idx["chunks"]))
        for rank, r in enumerate(results_all, start=1):
            if r["page_start"] <= target_page_1indexed <= r["page_end"]:
                return rank
        return None

    def test_p1_21_cfr_11_10e_rank_1_in_top5(self):
        rank = self._rank_of_page(_RW_0005, "21_CFR_11.10(e)", 46)
        assert rank is not None and rank <= 5

    def test_p2_21_cfr_11_10g_not_in_top5_but_in_top10(self):
        rank = self._rank_of_page(_RW_0005, "21_CFR_11.10(g)", 40)
        assert rank is not None and 5 < rank <= 10

    def test_p3_annex11_12_not_in_top10(self):
        """Registrado tal cual, sin maquillar: P3 no aparece ni en el
        top-10 con la query actual (citation_text+evidence_min_criteria+
        requirement_terms de ANNEX11_12)."""
        rank = self._rank_of_page(_RW_0005, "ANNEX11_12", 45)
        assert rank is not None and rank > 10

    def test_p4_alcoa_attributable_rank_in_top5(self):
        rank = self._rank_of_page(_RW_0011, "ALCOA_ATTRIBUTABLE", 13)
        assert rank is not None and rank <= 5

    def test_p5_alcoa_contemporaneous_not_in_top5_but_in_top10(self):
        """Mismo punto ciego que R1.6/R1.7 ya documentaron por otra vía:
        la evidencia real de P5 no repite vocabulario gobernado literal,
        así que un método léxico (BM25 igual que la heurística anterior)
        no la prioriza. SÍ aparece en el top-10 (rank 9)."""
        rank = self._rank_of_page(_RW_0005, "ALCOA_CONTEMPORANEOUS", 46)
        assert rank is not None and 5 < rank <= 10

    def test_p6_21_cfr_211_68b_rank_in_top5(self):
        rank = self._rank_of_page(_RW_0011, "21_CFR_211.68(b)", 13)
        assert rank is not None and rank <= 5

    def test_p7_21_cfr_211_68b_different_document_rank_in_top5(self):
        rank = self._rank_of_page(_RW_0012, "21_CFR_211.68(b)", 14)
        assert rank is not None and rank <= 5

    def test_retrieval_recall_at_5_is_4_of_7(self):
        """El número que importa para el reporte -- fijado explícitamente
        como su propio test para que cualquier cambio futuro al chunking/
        query/BM25 tenga que declarar conscientemente si sube o baja."""
        positives = [
            (_RW_0005, "21_CFR_11.10(e)", 46),
            (_RW_0005, "21_CFR_11.10(g)", 40),
            (_RW_0005, "ANNEX11_12", 45),
            (_RW_0011, "ALCOA_ATTRIBUTABLE", 13),
            (_RW_0005, "ALCOA_CONTEMPORANEOUS", 46),
            (_RW_0011, "21_CFR_211.68(b)", 13),
            (_RW_0012, "21_CFR_211.68(b)", 14),
        ]
        hits = sum(
            1 for doc, req, page in positives
            if (r := self._rank_of_page(doc, req, page)) is not None and r <= 5
        )
        assert hits == 4

    def test_negative_n1_annex11_4_reference_list_not_in_top5(self):
        """GAMP5 citado en la lista de Reference Documents (página 2,
        1-indexado) de RW-0005 -- el mismo falso positivo real de la
        corrida URS v2.1. No debe aparecer en el top-5 para ANNEX11_4."""
        rank = self._rank_of_page(_RW_0005, "ANNEX11_4", 2)
        assert rank is None or rank > 5

    def test_negative_n2_table_of_contents_not_in_top5(self):
        """'F12.00: Audit Trail ... 45' en la tabla de contenidos
        (página 4, 1-indexado) de RW-0005 -- no debe aparecer en el
        top-5 para 21_CFR_11.10(e)."""
        rank = self._rank_of_page(_RW_0005, "21_CFR_11.10(e)", 4)
        assert rank is None or rank > 5
