"""
Tests -- W5 V2 Fase E: inyección de texto regulatorio real en
chunked_engine.build_prompt() (_lookup_regulatory_text). También cubre la
ampliación de Fase F (D real, 2026-07-25): inyección de
evidence_min_criteria (_lookup_evidence_min_criteria).

Regla dura que esto corrige (confirmada en el baseline real de la corrida
URS v2.1): 'una LLM NUNCA recibe únicamente requirement_id + descripción
breve' -- causa raíz del falso positivo semántico ANNEX11_4. Cubre: los 19
req_id reales del catálogo (Fase C) inyectan su citation_text real y
verificable; un req_id fuera del catálogo cae de vuelta a solo label sin
romper la construcción del prompt; los 3 prompts gobernados
(part11/annex11/alcoa) quedan con texto normativo real para el 100% de
sus checkpoints.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
import yaml

from factory.engines.gmpai_integrity import chunked_engine as ce

PROMPTS_DIR = Path(__file__).parent.parent / "engines" / "gmpai_integrity" / "prompts"


class TestLookupRegulatoryText:

    def test_returns_real_citation_for_known_requirement(self):
        text = ce._lookup_regulatory_text("21_CFR_11.10(a)")
        assert text is not None
        assert "Validation of systems" in text
        assert "eCFR" in text

    def test_returns_none_for_unknown_requirement_id(self):
        assert ce._lookup_regulatory_text("REQ_QUE_NO_EXISTE_EN_EL_CATALOGO") is None

    def test_includes_clause_location(self):
        text = ce._lookup_regulatory_text("21_CFR_11.10(d)")
        assert "§ 11.10, paragraph (d)" in text


class TestBuildPromptInjectsRegulatoryText:

    def test_part11_prompt_includes_canonical_text_for_every_checkpoint(self):
        meta = ce.load_prompt_meta(PROMPTS_DIR / "part11_prompts.yaml")
        prompt = ce.build_prompt(meta, "documento de prueba")
        for cp in meta["checkpoints"]:
            assert cp["req_id"] in prompt
        assert "Texto normativo canonico" in prompt
        # cita real y verificable del texto oficial, no una descripcion breve
        assert "Limiting system access to authorized individuals." in prompt

    def test_annex11_prompt_includes_canonical_text(self):
        meta = ce.load_prompt_meta(PROMPTS_DIR / "annex11_prompts.yaml")
        prompt = ce.build_prompt(meta, "documento de prueba")
        assert prompt.count("Texto normativo canonico") == len(meta["checkpoints"])

    def test_alcoa_prompt_includes_canonical_text(self):
        meta = ce.load_prompt_meta(PROMPTS_DIR / "alcoa_prompts.yaml")
        prompt = ce.build_prompt(meta, "documento de prueba")
        assert prompt.count("Texto normativo canonico") == len(meta["checkpoints"])

    def test_checkpoint_outside_catalog_is_excluded_from_prompt(self):
        """Gate 4 (2026-07-28): un req_id sin Evidence Pack NO viaja al
        modelo con solo label -- queda EXCLUIDO del prompt.

        Este test verificaba antes lo contrario ('falls back gracefully'):
        codificaba el fail-open que la auditoria identifico como defecto
        real. El gate declara 'FAIL: pack incompleto -> bloquea la llamada'
        y el codigo hacia lo opuesto."""
        meta = {
            "common_contract": "contrato de prueba",
            "checkpoints": [{"req_id": "REQ_INVENTADO_XYZ", "label": "checkpoint de prueba"}],
        }
        prompt = ce.build_prompt(meta, "doc")
        assert "REQ_INVENTADO_XYZ" not in prompt
        assert "checkpoint de prueba" not in prompt
        assert "Texto normativo canonico" not in prompt

    def test_governed_yaml_common_contract_and_checkpoints_untouched(self):
        """Decision explicita de Fase E (confirmada por Cesar): el texto
        regulatorio se inyecta en runtime desde requirements.yaml (Fase C),
        SIN modificar common_contract ni la lista de checkpoints de los
        YAML gobernados -- estos siguen siendo solo req_id+label."""
        for filename in ("part11_prompts.yaml", "annex11_prompts.yaml", "alcoa_prompts.yaml"):
            meta = yaml.safe_load((PROMPTS_DIR / filename).read_text(encoding="utf-8"))
            for cp in meta["checkpoints"]:
                assert set(cp.keys()) == {"req_id", "label"}, (
                    f"{filename}: checkpoint {cp} tiene campos fuera de req_id/label -- "
                    "Fase E no debia modificar el YAML gobernado"
                )

    def test_19_catalog_requirement_ids_all_resolve_to_real_text(self):
        """Cobertura completa: los 19 req_id de requirements.yaml (Fase C)
        deben producir texto normativo real, no None."""
        catalog = yaml.safe_load(
            Path("factory/regulatory/requirement_catalog/requirements.yaml").read_text()
        )
        missing = [rid for rid in catalog["requirements"] if ce._lookup_regulatory_text(rid) is None]
        assert missing == [], f"req_id del catalogo sin texto normativo resuelto: {missing}"


class TestLookupEvidenceMinCriteria:
    """W5 V2 Fase F, ampliación D (2026-07-25)."""

    def test_returns_real_criteria_for_known_requirement(self):
        criteria = ce._lookup_evidence_min_criteria("21_CFR_11.10(d)")
        assert criteria is not None
        assert "Cuentas humanas individuales (no compartidas)." in criteria

    def test_returns_none_for_unknown_requirement_id(self):
        assert ce._lookup_evidence_min_criteria("REQ_QUE_NO_EXISTE_EN_EL_CATALOGO") is None

    def test_interpreted_catalog_requirement_ids_all_resolve_to_real_criteria(self):
        """Los requisitos pendientes de interpretacion humana no tienen
        criterios todavia -- esa ausencia es lo que declara su estado, y el
        gate 4 impide que se evaluen. Se excluyen aqui y se comprueban aparte."""
        from tests.conftest import PENDING_HUMAN_INTERPRETATION_REQ_IDS
        catalog = yaml.safe_load(
            Path("factory/regulatory/requirement_catalog/requirements.yaml").read_text()
        )
        missing = [
            rid for rid in catalog["requirements"]
            if rid not in PENDING_HUMAN_INTERPRETATION_REQ_IDS
            and not ce._lookup_evidence_min_criteria(rid)
        ]
        assert missing == [], f"req_id interpretado sin evidence_min_criteria resuelto: {missing}"

    def test_pending_interpretation_requirements_have_no_criteria_yet(self):
        from tests.conftest import PENDING_HUMAN_INTERPRETATION_REQ_IDS
        for rid in PENDING_HUMAN_INTERPRETATION_REQ_IDS:
            assert not ce._lookup_evidence_min_criteria(rid), (
                f"{rid} ya tiene criterios: si hay interpretacion humana real, "
                "sacarlo de PENDING_HUMAN_INTERPRETATION_REQ_IDS"
            )


class TestBuildPromptInjectsEvidenceMinCriteria:

    def test_part11_prompt_includes_criteria_for_every_checkpoint(self):
        meta = ce.load_prompt_meta(PROMPTS_DIR / "part11_prompts.yaml")
        prompt = ce.build_prompt(meta, "documento de prueba")
        assert "Criterios minimos de evidencia" in prompt
        # criterio real y verificable del catalogo, no una descripcion breve
        assert "Cuentas humanas individuales (no compartidas)." in prompt

    def test_annex11_prompt_includes_criteria(self):
        meta = ce.load_prompt_meta(PROMPTS_DIR / "annex11_prompts.yaml")
        prompt = ce.build_prompt(meta, "documento de prueba")
        assert prompt.count("Criterios minimos de evidencia") == len(meta["checkpoints"])

    def test_alcoa_prompt_includes_criteria(self):
        meta = ce.load_prompt_meta(PROMPTS_DIR / "alcoa_prompts.yaml")
        prompt = ce.build_prompt(meta, "documento de prueba")
        assert prompt.count("Criterios minimos de evidencia") == len(meta["checkpoints"])

    def test_checkpoint_outside_catalog_gets_no_criteria_because_it_is_blocked(self):
        """Gate 4: sin pack no hay criterios PORQUE el checkpoint ni siquiera
        entra al prompt (antes entraba con solo label)."""
        meta = {
            "common_contract": "contrato de prueba",
            "checkpoints": [{"req_id": "REQ_INVENTADO_XYZ", "label": "checkpoint de prueba"}],
        }
        prompt = ce.build_prompt(meta, "doc")
        assert "REQ_INVENTADO_XYZ" not in prompt
        assert "Criterios minimos de evidencia" not in prompt

    def test_common_contract_asks_for_criterion_assessments(self):
        """El contrato de los 3 prompts gobernados debe instruir al modelo
        a clasificar los criterios via criterion_assessments (Fase F,
        contrato unificado) -- guardia contra remocion accidental futura
        del bloque."""
        for filename in ("part11_prompts.yaml", "annex11_prompts.yaml", "alcoa_prompts.yaml"):
            meta = yaml.safe_load((PROMPTS_DIR / filename).read_text(encoding="utf-8"))
            assert "criterion_assessments" in meta["common_contract"], filename
            assert "criterion_index" in meta["common_contract"], filename
            assert meta["schema_version"] == "checkpoint_llm_response_v1", filename

    def test_criteria_are_numbered_in_prompt(self):
        """El indice numerado en el prompt debe coincidir con
        criterion_index que el modelo debe usar (Fase F)."""
        meta = ce.load_prompt_meta(PROMPTS_DIR / "part11_prompts.yaml")
        prompt = ce.build_prompt(meta, "documento de prueba")
        assert "1. " in prompt
        assert "5. " in prompt  # 21_CFR_11.10(d) tiene 5 criterios minimos
