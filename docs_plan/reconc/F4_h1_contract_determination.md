# F4 — D6: ¿`technical_completeness_rules.yaml` es clase `ARTIFACT_VERSION`?

**Plan de reconciliación v1.1 · FASE 4 · acción 3 · determinación POR CONTRATO, citando el código.**

## La pregunta

D6: la aprobación H1 (`APPROVE_REMEDIATION_V1_2`) de `technical_completeness_rules.yaml` se
registró en `reconc-F1..` / commit `24549a3` por **metadata + commit** (campo
`pending_approval.approved` en el propio YAML). ¿Era ese el mecanismo correcto, o el artefacto
debía firmarse por la **familia de gobernanza `ARTIFACT_VERSION`** (proposal → sign)?

## El contrato (código)

### `factory/core/artifact_version_guard.py:76-77`

```python
ARTIFACT_CLASSES = ("catalog", "applicability_matrix", "evidence_pack",
                    "prompt", "golden_dataset")
```

### `factory/core/artifact_version_guard.py:187-...` — `enumerate_artifacts()`

Enumera **exactamente** estas rutas (líneas 197-233):

| clase | ruta enumerada | ¿incluye `technical_completeness_rules.yaml`? |
|---|---|---|
| `catalog` | `factory/regulatory/requirement_catalog/requirements.yaml` | no |
| `evidence_pack` | cada `requirements[req_id]` **dentro** de `requirements.yaml` | no |
| `applicability_matrix` | `factory/regulatory/applicability_matrix.yaml` | no |
| `prompt` | `factory/engines/gmpai_integrity/prompts/*_prompts.yaml` (glob) | no |
| `golden_dataset` | `factory/regulatory/golden_dataset/semantic_verification_golden_dataset.py` | no |

`technical_completeness_rules.yaml` **NO aparece** en `ARTIFACT_CLASSES` ni en
`enumerate_artifacts()`. Tampoco hay ningún `ARTIFACT_VERSION` proposal para él en
`decisions_v2.jsonl` (verificado en F0/F1: los `ARTIFACT_VERSION-2026-0XX` cubren
`analysis_coverage_mode.yaml`, `extraction_adequacy_thresholds.yaml`, `gxp_criticality.yaml`,
`extract_document.py`+`model.py`, la muestra de relaciones H-10 — nunca
`technical_completeness_rules.yaml`).

## Determinación

**`technical_completeness_rules.yaml` NO es una clase `ARTIFACT_VERSION`.**

→ El servicio `artifact_version_signing` / el panel de Mission Control / el CLI
`sign_artifact_version_proposal.py` **no aplican** a este artefacto (no lo enumeran, no hay
proposal posible).

→ El mecanismo usado en `24549a3` (**metadata `pending_approval.approved` + commit**, con
`approved_by: "Capa 9 (Cesar)"`, `approved_at`, `approval_authorization`, `downstream_condition`)
es **el correcto** para este gate a la medida — idéntico al precedente D5-A/B/C
(`qa40_adjudication_sheet.yaml`, `real_corpus_opportunities.yaml`, firmados por metadata).

## VEREDICTO D6

**D6 CERRADO.** H1 NO requiere asiento en la familia `ARTIFACT_VERSION`. El registro por
metadata + commit es conforme al contrato de gobernanza (`artifact_version_guard.py`).

**Nota:** si en el futuro Capa 9 quisiera someter `technical_completeness_rules.yaml` a
`ARTIFACT_VERSION` (versionado gobernado formal), habría que **añadir una clase nueva** a
`ARTIFACT_CLASSES` + `enumerate_artifacts()` (cambio de código de `factory/core/`), no es algo
que "faltara" hoy.
