"""Bloque 3 (docs_plan/CONTINUACION_FASE0_P4_FASE1.md, aprobado por Cesar,
2026-08-15) -- contrato formal entre el checkpoint real de
chunked_engine.evaluate_chunked() (schema checkpoint_llm_response_v1) y el
`finding_llm_v1` que evidence_verifier.verify_llm_output() consume, vía el
único traductor real activo en producción:
verified_pipeline_adapter.candidate_to_llm_output() (Ruta B verificada,
`chunked_engine.evaluate_chunked(use_verified_pipeline=True)`).

Corrección al diagnóstico original de la auditoría
(docs_plan/AUDITORIA_ARQUITECTONICA_2026-08/CONTEXT_ENGINEERING_ARCHITECTURE.md
Componente 1): el contrato formal YA EXISTE como JSON Schema versionado
(factory/regulatory/schemas/checkpoint_llm_response_v1.json,
finding_llm_v1.json), validado vía schema_loader.validate_against() --
NO había que construirlo desde cero. El gap real, cerrado aquí:

1. candidate_to_llm_output() construye el dict `llm_output` A MANO en
   Python (no vía generación forzada de Ollama) y su salida NUNCA se
   valida contra finding_llm_v1 antes de pasarla a verify_llm_output() --
   exactamente la clase de defecto "no parchear el segundo sitio" que
   causó B3->B4->B5 (docs_plan/R3_T1_7_SUPERFICIE_UNICA_CANDIDATO.md),
   pero en el sitio real, no uno hipotético.
2. Ningún test fijaba (schema_sha256) el contenido de los 2 schemas -- un
   edit silencioso a cualquiera de los dos no rompía nada.

Este archivo cierra ambos, reutilizando integramente la infraestructura
ya existente (schema_loader, los 2 schemas reales) -- no inventa una
representación nueva ni relaja ningún schema."""
from __future__ import annotations

import hashlib

import pytest

from factory.engines.gmpai_integrity.chunked_engine import _VALID_ESTADOS
from factory.regulatory import verified_pipeline_adapter as vpa
from factory.regulatory.schema_loader import SCHEMAS_DIR, schema_sha256, validate_against

# ---------------------------------------------------------------------------
# 3.3 -- pin de hash: cualquier cambio a estos 2 schemas (agregar/quitar un
# campo, cambiar un enum, etc.) DEBE romper este test explícitamente. La
# convención de versionado del propio directorio es el nombre de archivo
# (_v1/_v2, ver source_registry_entry_v1.json/v2.json) -- un cambio real de
# contrato exige un archivo _v2 nuevo, nunca editar el _v1 en su sitio.
# ---------------------------------------------------------------------------

_PINNED_SCHEMA_SHA256 = {
    "checkpoint_llm_response_v1": "00ccc255e3b6397f42ab2ff0bbe516eb487f90a8a4530603d631f92f8c40a8bf",
    "finding_llm_v1": "aef8f84a57474ea983e9326b1d07ab83a36ecf0c3388db4c4821723d9186ae1e",
}


@pytest.mark.parametrize("schema_name,expected", _PINNED_SCHEMA_SHA256.items())
def test_schema_file_hash_is_pinned(schema_name, expected):
    """Si este test falla, el schema cambió de verdad -- crear
    <schema_name>_v2.json (nunca editar el _v1 en su sitio) y actualizar
    todos los call-sites/tests que lo referencian explícitamente, no solo
    este pin."""
    assert schema_sha256(schema_name) == expected, (
        f"{schema_name}.json cambió sin que se creara una versión _v2 nueva "
        "-- contrato editado en su sitio, exactamente lo que este pin existe "
        "para bloquear."
    )


def test_pinned_schema_hash_matches_manual_recompute():
    """Doble verificación independiente de schema_sha256() (no confiar solo
    en la función bajo prueba para probarse a sí misma)."""
    for name, expected in _PINNED_SCHEMA_SHA256.items():
        path = SCHEMAS_DIR / f"{name}.json"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected


# ---------------------------------------------------------------------------
# 3.2 -- test de contrato real: la salida de candidate_to_llm_output() (el
# traductor real activo en producción) debe validar SIEMPRE contra
# finding_llm_v1, para cada estado real que chunked_engine puede producir.
# ---------------------------------------------------------------------------

# Misma forma real que chunked_engine.py construye en producción (Ruta B
# verificada, ver chunked_engine.py ~L1417-1421: v_candidate).
def _real_candidate(estado: str, evidencia: str = "") -> dict:
    return {
        "page_start": 12,
        "page_end": 12,
        "estado": estado,
        "evidencia_exacta": evidencia,
    }


@pytest.mark.parametrize("estado", sorted(_VALID_ESTADOS))
def test_candidate_to_llm_output_conforms_to_finding_llm_v1(estado):
    """Round-trip real: cualquier estado que el motor puede emitir hoy
    (_VALID_ESTADOS, chunked_engine.py) debe traducirse a un finding_llm_v1
    válido -- si alguien agrega un estado nuevo al motor sin actualizar el
    adaptador, o cambia la forma del dict que arma
    candidate_to_llm_output(), este test lo detecta antes de que llegue a
    producción."""
    evidencia = "cita real anclada de ejemplo" if estado in ("cumple", "cumple_parcialmente") else ""
    candidate = _real_candidate(estado, evidencia)
    llm_output = vpa.candidate_to_llm_output(candidate, "21_CFR_11.10(e)")
    ok, errors = validate_against(llm_output, "finding_llm_v1")
    assert ok, f"estado={estado!r}: {errors}"


def test_candidate_to_llm_output_real_production_shape_is_contract_valid():
    """Fixture literal idéntica a la que chunked_engine.py construye en
    producción real (v_candidate) -- no una aproximación sintética."""
    v_candidate = {
        "page_start": 45, "page_end": 46,
        "estado": "cumple_parcialmente",
        "evidencia_exacta": "Audit trail records shall be archived.",
    }
    llm_output = vpa.candidate_to_llm_output(v_candidate, "21_CFR_11.10(e)")
    ok, errors = validate_against(llm_output, "finding_llm_v1")
    assert ok, errors


# ---------------------------------------------------------------------------
# Contraparte de control: el test de contrato debe FALLAR de verdad ante un
# drift sintético -- confirma que finding_llm_v1 realmente detecta una
# violación, no que el test pasa por casualidad (mismo patrón que
# test_deploy_freshness_all_source_routes_are_live, R3-T1.8).
# ---------------------------------------------------------------------------

def test_contract_test_detects_synthetic_field_drift():
    """Si candidate_to_llm_output() empezara a omitir 'evidence_page' (bug
    real hipotético: alguien borra esa línea del adaptador), este test
    demuestra que finding_llm_v1 lo rechaza -- no un ejercicio vacío."""
    llm_output = vpa.candidate_to_llm_output(_real_candidate("cumple"), "21_CFR_11.10(e)")
    del llm_output["evidence_page"]
    ok, errors = validate_against(llm_output, "finding_llm_v1")
    assert ok is False
    assert any("evidence_page" in e for e in errors)


def test_contract_test_detects_synthetic_extra_field_drift():
    """additionalProperties:false de finding_llm_v1 (metadata de pipeline no
    puede colarse aquí, por diseño) -- confirma que un campo espurio se
    rechaza, no se ignora en silencio."""
    llm_output = vpa.candidate_to_llm_output(_real_candidate("cumple"), "21_CFR_11.10(e)")
    llm_output["pipeline_debug_note"] = "esto no deberia estar aqui"
    ok, errors = validate_against(llm_output, "finding_llm_v1")
    assert ok is False
