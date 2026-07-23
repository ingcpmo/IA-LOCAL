"""
Tests -- W5 V2 Fase J: factory.services.document_generation_strategy.

Cubre: las 14 entradas reales del allowlist de Rockwell (Fase A) reciben
una decision de estrategia correcta y explicita -- ningun archivo real
queda sin decision, ninguna decision se fabrica sin justificacion.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import yaml

from factory.services.document_generation_strategy import (
    decide_generation_strategy, is_strategy_implemented,
)

_ALLOWLIST_PATH = Path("factory/regulatory/scope/source_baseline_allowlist.yaml")


def _entry(**overrides) -> dict:
    base = {
        "file_id": "RW-9999", "extension": ".pdf",
        "extraction_capability": "TEXT_NATIVE", "processing_state": "ORIGINAL_SOURCE_CONFIRMED",
    }
    base.update(overrides)
    return base


class TestDecideGenerationStrategySynthetic:

    def test_ocr_required_is_blocked_for_insufficient_fidelity(self):
        d = decide_generation_strategy(_entry(extraction_capability="OCR_REQUIRED"))
        assert d.strategy == "GENERATION_BLOCKED_INSUFFICIENT_FIDELITY"
        assert d.generation_ready is False

    def test_not_extractable_is_blocked(self):
        d = decide_generation_strategy(_entry(extraction_capability="NOT_EXTRACTABLE"))
        assert d.strategy == "GENERATION_BLOCKED_INSUFFICIENT_FIDELITY"

    def test_duplicate_is_not_eligible_regardless_of_format(self):
        d = decide_generation_strategy(_entry(processing_state="DUPLICATE"))
        assert d.strategy == "NOT_ELIGIBLE_YET"
        assert "DUPLICATE" in d.reason

    def test_human_review_required_is_not_eligible(self):
        d = decide_generation_strategy(_entry(processing_state="HUMAN_REVIEW_REQUIRED"))
        assert d.strategy == "NOT_ELIGIBLE_YET"

    def test_text_native_pdf_is_ready(self):
        d = decide_generation_strategy(_entry())
        assert d.strategy == "PDF_RECONSTRUCTED_DOCX_AND_PDF"
        assert d.generation_ready is True

    def test_xlsx_declared_not_implemented_not_fabricated(self):
        d = decide_generation_strategy(_entry(extension=".xlsx"))
        assert d.strategy == "XLSX_CANDIDATE_CELL_LEVEL"
        assert d.generation_ready is False
        assert "caso real" in d.reason.lower()

    def test_docm_declared_not_implemented_not_fabricated(self):
        d = decide_generation_strategy(_entry(extension=".docm"))
        assert d.strategy == "DOCM_CANDIDATE_SAFE_EXTRACTION"
        assert d.generation_ready is False
        assert "caso real" in d.reason.lower()

    def test_docx_maps_to_implemented_strategy(self):
        d = decide_generation_strategy(_entry(extension=".docx"))
        assert d.strategy == "DOCX_CANDIDATE_AND_PDF"
        assert d.generation_ready is True

    def test_unsupported_combination_blocks_explicitly(self):
        d = decide_generation_strategy(_entry(extension=".txt", extraction_capability="TEXT_NATIVE"))
        assert d.strategy == "DOCUMENT_GENERATION_BLOCKED"
        assert d.generation_ready is False

    def test_never_raises_for_any_valid_entry_shape(self):
        for ext in (".pdf", ".docx", ".docm", ".xlsx", ".txt"):
            for cap in ("TEXT_NATIVE", "OCR_REQUIRED", "NOT_EXTRACTABLE"):
                for state in ("ORIGINAL_SOURCE_CONFIRMED", "DUPLICATE", "HUMAN_REVIEW_REQUIRED"):
                    decide_generation_strategy(_entry(extension=ext, extraction_capability=cap, processing_state=state))


class TestIsStrategyImplemented:

    def test_pdf_reconstructed_is_implemented(self):
        assert is_strategy_implemented("PDF_RECONSTRUCTED_DOCX_AND_PDF") is True

    def test_xlsx_strategy_is_not_implemented(self):
        assert is_strategy_implemented("XLSX_CANDIDATE_CELL_LEVEL") is False

    def test_docm_strategy_is_not_implemented(self):
        assert is_strategy_implemented("DOCM_CANDIDATE_SAFE_EXTRACTION") is False

    def test_generation_ready_implies_implemented_for_all_real_rockwell_entries(self):
        """Invariante dura: si una decision real dice generation_ready=True,
        su estrategia debe estar realmente implementada -- nunca una
        promesa sin generador detras."""
        entries = yaml.safe_load(_ALLOWLIST_PATH.read_text(encoding="utf-8"))
        for entry in entries:
            d = decide_generation_strategy(entry)
            if d.generation_ready:
                assert is_strategy_implemented(d.strategy), (
                    f"{d.file_id}: generation_ready=True pero estrategia {d.strategy!r} no implementada"
                )


class TestRealRockwellAllowlistCoverage:

    def test_all_14_real_files_get_a_decision(self):
        entries = yaml.safe_load(_ALLOWLIST_PATH.read_text(encoding="utf-8"))
        decisions = [decide_generation_strategy(e) for e in entries]
        assert len(decisions) == 14
        assert all(d.strategy for d in decisions)

    def test_expected_strategy_distribution_on_real_corpus(self):
        """Fija el resultado real de esta fase contra el allowlist real de
        Fase A -- un cambio futuro en el allowlist que altere esta
        distribucion debe notarse aqui, no como sorpresa."""
        entries = yaml.safe_load(_ALLOWLIST_PATH.read_text(encoding="utf-8"))
        decisions = {d.file_id: d.strategy for d in (decide_generation_strategy(e) for e in entries)}
        assert decisions["RW-0001"] == "GENERATION_BLOCKED_INSUFFICIENT_FIDELITY"  # PLC Panel, OCR_REQUIRED
        assert decisions["RW-0003"] == "GENERATION_BLOCKED_INSUFFICIENT_FIDELITY"  # SAT3 Scanned
        assert decisions["RW-0004"] == "NOT_ELIGIBLE_YET"  # FS_v1.2-2 (DUPLICATE)
        assert decisions["RW-0005"] == "PDF_RECONSTRUCTED_DOCX_AND_PDF"  # FS_v1.2 canonico
        assert decisions["RW-0007"] == "DOCM_CANDIDATE_SAFE_EXTRACTION"
        assert decisions["RW-0008"] == "NOT_ELIGIBLE_YET"  # T-039 PDF (HUMAN_REVIEW_REQUIRED)
        assert decisions["RW-0013"] == "XLSX_CANDIDATE_CELL_LEVEL"
        ready_count = sum(
            1 for e in entries if decide_generation_strategy(e).generation_ready
        )
        assert ready_count == 8
