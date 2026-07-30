# OQ — Operational Qualification

> **BORRADOR GENERADO POR LA FACTORY — sin valor regulatorio hasta revisión y aprobación humana.**
> Revisión humana: verifique cada afirmación contra la fuente citada antes de aprobar; las secciones "SIN EVIDENCIA" requieren aporte humano previo.
> Misión: `oos_hplc_investigator` · Generado: 2026-07-03T14:37:48Z · Por: Cesar

## Ejecuciones funcionales registradas (W4)

- Ejecuciones registradas: 26
- Con al menos un PASS: 26
- Operadores (nombre real): Cesar, cesar

*Fuente: test_results/oos_hplc_investigator.jsonl*

## Resultados por prueba — última ejecución con aserción y operador

| Prueba | Último resultado | Aserción (json_path: esperado → recibido) | ms | Operador | UTC |
|---|---|---|---|---|---|
| alcoa_all_present | PASS | `$.compliant`: true → true | 8.7 | cesar | 2026-07-01T03:45:22 |
| alcoa_missing_attributes | PASS | `$.compliant`: false → false | 8.5 | cesar | 2026-07-01T03:45:22 |
| audit_stamp_basic | PASS | `$.alcoa_validation.compliant`: true → true | 8.8 | cesar | 2026-07-01T03:45:22 |
| oos_create_in_spec | PASS | `$.is_oos`: false → false | 9.7 | cesar | 2026-07-02T03:39:55 |
| oos_create_out_of_spec | PASS | `$.is_oos`: true → true | 11.6 | cesar | 2026-07-01T03:42:50 |
| peaks_negative_area_anomaly | PASS | `$.count`: 1 → 1 | 11.2 | cesar | 2026-07-01T03:43:44 |
| peaks_no_anomalies | PASS | `$.count`: 0 → 0 | 10.7 | cesar | 2026-07-01T03:43:44 |
| rsd_four_values | PASS | `$.n`: 4 → 4 | 11.4 | cesar | 2026-07-01T03:43:44 |
| sst_fail_low_plates | PASS | `$.pass`: false → false | 9.4 | cesar | 2026-07-01T03:43:44 |
| sst_pass_within_criteria | PASS | `$.pass`: true → true | 9.7 | cesar | 2026-07-01T03:43:44 |

*Fuente: test_results/oos_hplc_investigator.jsonl (última ejecución por prueba)*

## Trazabilidad de pruebas

URS-01 = objetivo de la misión (verbatim en el documento URS). Evidencia exacta de cada fila: la entrada con ese `run_at` en `test_results/oos_hplc_investigator.jsonl` (cronológico, append-only).

| Requisito | Agente | Prueba (catálogo W4) | Endpoint | Último resultado | Ejecutado por · UTC | Documento |
|---|---|---|---|---|---|---|
| URS-01 | qa_oos_profile | oos_create_in_spec | `POST /api/v1/oos/records` | PASS | cesar · 2026-07-02T03:39:55 | OQ |
| URS-01 | qa_oos_profile | oos_create_out_of_spec | `POST /api/v1/oos/records` | PASS | cesar · 2026-07-01T03:42:50 | OQ |
| URS-01 | hplc_data_review_agent | sst_pass_within_criteria | `POST /api/v1/hplc/sst/validate` | PASS | cesar · 2026-07-01T03:43:44 | OQ |
| URS-01 | hplc_data_review_agent | sst_fail_low_plates | `POST /api/v1/hplc/sst/validate` | PASS | cesar · 2026-07-01T03:43:44 | OQ |
| URS-01 | hplc_data_review_agent | peaks_no_anomalies | `POST /api/v1/hplc/peaks/anomalies` | PASS | cesar · 2026-07-01T03:43:44 | OQ |
| URS-01 | hplc_data_review_agent | peaks_negative_area_anomaly | `POST /api/v1/hplc/peaks/anomalies` | PASS | cesar · 2026-07-01T03:43:44 | OQ |
| URS-01 | hplc_data_review_agent | rsd_four_values | `POST /api/v1/hplc/rsd` | PASS | cesar · 2026-07-01T03:43:44 | OQ |
| URS-01 | integrity_lims_profile | alcoa_all_present | `POST /api/v1/audit/alcoa/validate` | PASS | cesar · 2026-07-01T03:45:22 | OQ |
| URS-01 | integrity_lims_profile | alcoa_missing_attributes | `POST /api/v1/audit/alcoa/validate` | PASS | cesar · 2026-07-01T03:45:22 | OQ |
| URS-01 | integrity_lims_profile | audit_stamp_basic | `POST /api/v1/audit/stamp` | PASS | cesar · 2026-07-01T03:45:22 | OQ |

*Fuente: misión + agent_design_proposal + catálogo W4 + test_results*
