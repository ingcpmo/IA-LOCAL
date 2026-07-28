"""Orquestador L -> M -> AGT-QLT -> O -> N -> paquete QA.

Cierra el hallazgo estructural de la auditoria maestra de W5 V2
(2026-07-28): cuatro fases implementadas y probadas sin ningun llamador de
produccion, de modo que los 9 artefactos nunca se habian generado juntos.
"""
from __future__ import annotations

import json

import pytest
from docx import Document

from factory.services import regulatory_document_package_pipeline as pipe
from factory.services.corrected_document_generation_gate import _is_heading_for


def _structure() -> dict:
    return {
        "documento": "DOC_TEST",
        "secciones": [
            {"numero": "1", "titulo": "Introduction", "pagina_inicio": 1,
             "parrafos": ["El sistema gestiona registros electronicos."]},
            {"numero": "2", "titulo": "Data", "pagina_inicio": 10,
             "parrafos": ["Los datos se almacenan en el servidor."]},
        ],
        "texto_previo_a_primera_seccion": ["Portada."],
        "toc_anchored": True,
    }


def _package_state() -> dict:
    return {
        "package": {"package_id": "PKG-TEST", "package_version": 1},
        "changes": {
            "CH-1": {
                "change_id": "CH-1",
                "requirement_id": "ANNEX11_7.1",
                "change_type": "CONTENT_ADDITION",
                "proposed_content": "Se define un periodo de retencion de 10 anos.",
                "document_location": "seccion 2",
                "original_content": None,
                "change_reason": "El documento no declara periodo de retencion.",
                "change_risk": "LOW_RISK",
                "schema_validation_status": "PASSED",
                "citation_anchor_status": "VERIFIED",
                "citations": [{
                    "citation_id": "CIT-1",
                    "regulatory_source": "eu_gmp_annex11",
                    "regulatory_catalog_entry_id": "ANNEX11_7.1",
                    "regulatory_source_sha256": "a" * 64,
                    "requirement_catalog_sha256": "b" * 64,
                    "run_id": "run-test", "record_id": "REC-1",
                    "document_role": "CANDIDATE_DOCUMENT", "document_sha256": "c" * 64,
                    "page_start": 10,
                }],
                "evidence_status": "DOCUMENTATION_GAP",
            },
        },
        "exceptions": {},
        "medium_risk_batch_decisions": {},
    }


@pytest.fixture
def resultado():
    return pipe.build_document_package(
        structure=_structure(), package_state=_package_state(),
        run_id="run-test", package_id="PKG-TEST", package_version=1,
        original_document_sha256="0" * 64,
    )


def test_genera_los_nueve_artefactos(resultado):
    """Fase M exige los 9 simultaneos y consistentes."""
    assert len(resultado.artifacts) == 9
    assert set(resultado.artifacts) == set(
        pipe.REQUIRED_MANIFEST_ARTIFACTS + [pipe.ARTIFACT_MANIFEST])
    for nombre, data in resultado.artifacts.items():
        assert data, f"{nombre} vacio"


def test_todos_los_artefactos_estan_hasheados_en_el_manifest(resultado):
    hashes = resultado.manifest["artifact_hashes"]
    for nombre in pipe.REQUIRED_MANIFEST_ARTIFACTS:
        assert nombre in hashes
        assert len(hashes[nombre]) == 64


def test_sin_run_fingerprint_el_manifest_sigue_incompleto():
    """Comportamiento historico intacto: sin los componentes de identidad de
    corrida, el manifest NUNCA se declara completo."""
    r = pipe.build_document_package(
        structure=_structure(), package_state=_package_state(),
        run_id="r", package_id="P", package_version=1,
        original_document_sha256="0" * 64)
    assert r.manifest["fingerprint_complete"] is False
    assert r.manifest["fingerprint_missing_components"]


def test_con_run_fingerprint_completo_el_manifest_se_declara_completo():
    fp = {
        "model_digest": "d" * 64, "prompt_version": {"a.yaml": "1.1.0"},
        "schema_version": "checkpoint_llm_response_v1",
        "catalog_version_hash": "c" * 64,
        "applicability_matrix_version_hash": "m" * 64,
        "agent_versions": {"AGT-DOC": "1.0.0"},
    }
    r = pipe.build_document_package(
        structure=_structure(), package_state=_package_state(),
        run_id="r", package_id="P", package_version=1,
        original_document_sha256="0" * 64, run_fingerprint=fp)
    assert r.manifest["fingerprint_complete"] is True
    assert r.manifest["fingerprint_missing_components"] == []


def test_fingerprint_parcial_nunca_se_declara_completo():
    r = pipe.build_document_package(
        structure=_structure(), package_state=_package_state(),
        run_id="r", package_id="P", package_version=1,
        original_document_sha256="0" * 64,
        run_fingerprint={"model_digest": "d" * 64})
    assert r.manifest["fingerprint_complete"] is False
    assert "agent_versions" in r.manifest["fingerprint_missing_components"]


def test_la_revalidacion_se_ejecuta_de_verdad(resultado):
    """Fase O dejaba de existir operativamente sin este eslabon: sin
    revalidacion, cada resena declara REVALIDATION_NOT_EXECUTED."""
    assert "revalidation_passed" in resultado.revalidation_report
    for narrativa in resultado.change_review:
        assert narrativa["resultado_revalidacion"] != "REVALIDATION_NOT_EXECUTED"


def test_la_matriz_lleva_el_veredicto_de_revalidacion(resultado):
    for fila in resultado.traceability_matrix:
        assert fila["revalidation_status"] != "REVALIDATION_NOT_EXECUTED"


def test_un_cambio_excluido_aparece_en_el_paquete_de_excepciones():
    """Gate 21: ninguna excepcion puede quedar fuera del paquete QA."""
    estado = _package_state()
    estado["changes"]["CH-2"] = {
        **estado["changes"]["CH-1"], "change_id": "CH-2",
        "change_risk": "HIGH_RISK",     # sin excepcion revisada -> excluido
    }
    r = pipe.build_document_package(
        structure=_structure(), package_state=estado, run_id="r",
        package_id="P", package_version=1, original_document_sha256="0" * 64)

    assert "CH-2" in r.excluded_change_ids
    excluidos = [e for e in r.exception_package
                 if e["tipo"] == "change_excluido_del_candidato"]
    assert [e["change_id"] for e in excluidos] == ["CH-2"]


def test_excepciones_reales_del_estado_entran_al_paquete():
    estado = _package_state()
    estado["exceptions"] = {
        "EXC-1": {"exception_id": "EXC-1", "change_id": "CH-1",
                  "human_review_decision": "ACCEPTED_WITH_JUSTIFICATION"},
    }
    r = pipe.build_document_package(
        structure=_structure(), package_state=estado, run_id="r",
        package_id="P", package_version=1, original_document_sha256="0" * 64)
    assert any(e.get("exception_id") == "EXC-1" for e in r.exception_package)


def test_nunca_declara_qa_ready_si_el_gate_no_paso(resultado):
    """El orquestador no libera nada: si el gate no llega a
    CORRECTED_DOCUMENT_GENERATED, qa_package_ready es False con motivo."""
    if resultado.gate_result.final_state != "CORRECTED_DOCUMENT_GENERATED":
        assert resultado.qa_package_ready is False
        assert resultado.blocking_reasons
    else:
        assert resultado.qa_package_ready is True


def test_persiste_los_artefactos_a_disco(resultado, tmp_path):
    escritos = pipe.persist_package(resultado, tmp_path / "pkg")
    assert len(escritos) == 10          # 9 artefactos + package_summary.json
    for ruta in escritos.values():
        assert ruta.exists() and ruta.stat().st_size > 0
    resumen = json.loads((tmp_path / "pkg" / "package_summary.json").read_text())
    assert resumen["artifact_count"] == 9


# --- el criterio de estructura del gate de Fase N, sobre el paquete real ----

def test_estructura_completa_pasa_el_criterio(resultado):
    """Con las 2 secciones presentes, el criterio debe estar en verde. Con
    la logica anterior fallaba en cuanto un parrafo de cuerpo coincidia."""
    criterio = next(c for c in resultado.gate_result.checks
                    if c.criterion == "conserva_estructura_requerida")
    assert criterio.passed is True, criterio.detail
