# 01 — Estado del Plan por Secciones (§0–§4)

Fuente del plan: `docs_plan/R4_T1_1v2_DESBLOQUEO_Y_VALIDACION_FRIA.md`
(1090 líneas, commiteado en `d224b24` — verificado tracked con
`git ls-files`, ver `06_GIT_STATUS_FINAL.md`).

## §0 — Frescura de despliegue

**Título en el plan:** "§0 — Frescura de despliegue: VERDE" (línea 183).

**Veredicto:** **PASA**

**Evidencia usada:**
- `curl http://localhost:9000/health` en vivo → `{"api":"ok","service":"factory","timestamp":1786657334}`.
- Contenedor `factory-api` con estado `Up` (`docker ps`).

## §1 — Desbloqueo de formato (re-selección de piloto)

**Título en el plan:** "§1 — Re-selección de piloto: CORRECCIÓN DE PREMISA +
RW-0005 confirmado" (línea 197).

**Veredicto:** **PASA**

**Evidencia usada:**
- `factory/layer9/decisions/decisions_v2.jsonl`: instancias
  `PILOT_EXECUTION-2026-017` (agent_proposed, tope 6 llamadas) y
  `PILOT_EXECUTION-2026-018` (human_confirmed por `cesar`, misma tarde del
  2026-08-12) confirman RW-0005 como target vigente, con
  `authorizes_corpus: false` y `authorizes_baseline: false` explícitos.

## §2 — Validación en frío de la cadena completa (0 llamadas LLM)

**Título en el plan:** "§2 — Validación en frío de la cadena completa:
COMPLETA, 0 llamadas LLM" (línea 304); criterios de aceptación en línea 350
(§2.3, 8 criterios con datos reales).

**Veredicto:** **PASA CON OBSERVACIÓN**

**Evidencia usada:**
- Commit `0796bb9` agrega
  `factory/tests/test_r4_t1_1v2_cold_chain_validation.py` (420 líneas, 7
  tests) — cadena completa directiva → paquete → candidato trazable, sin
  invocar LLM.
- Ejecución real dentro del contenedor `factory-api` durante esta auditoría
  (`docker exec factory-api python -m pytest
  factory/tests/test_r4_t1_1v2_cold_chain_validation.py -v`):

  | Test | Resultado |
  |---|---|
  | `test_synthetic_finding_isolated_never_touches_real_queue` | PASSED |
  | `test_directive_authored_by_cesar_is_accepted_and_dispatches_to_high_risk_change` | PASSED |
  | `test_full_cold_chain_rw0005_directive_to_traceable_candidate` | **FAILED** |
  | `test_delete_change_type_still_rejected` | PASSED |
  | `test_directive_without_citation_still_rejected` | PASSED |
  | `test_directive_with_non_anchoring_original_text_still_rejected` | PASSED |
  | `test_directive_with_stale_document_sha_still_rejected` | PASSED |

  **6 passed, 1 failed.** Causa raíz del fallo: el propio código del test
  (línea ~200) ejecuta `subprocess.run(["git", "rev-parse", "HEAD"], ...)`
  para obtener el commit actual como parte de su fixture de datos; el
  binario `git` no existe dentro de la imagen del contenedor `factory-api`
  (`docker exec factory-api which git` → sin salida). No es un defecto en
  `remediation_directive.py`, `candidate_document_generator.py` ni en
  ningún módulo de producción — es una dependencia de tooling del test
  ausente en el runtime del contenedor.
- 0 llamadas LLM confirmadas: ninguno de los 7 tests importa ni invoca
  `httpx` contra Ollama; el fallo es de infraestructura de test, no de
  juicio del modelo.

## §3 — Pre-vuelo (3.1–3.8)

**Título en el plan referenciado (commit `0796bb9`):** "Cierra §3.2 (panel
mínimo de adjudicación, bloqueante de pre-vuelo)".

**Veredicto:** **PASA (§3.2); §3.1 y §3.3–§3.8 no forman parte del alcance
de este cierre según los commits auditados — no se afirma su estado aquí.**

**Evidencia usada:**
- `factory/ui/mission_control.html` (+33 líneas), `main.js` (+3),
  `refresh.js` (+12/-1), `remediation.js` (+281 líneas nuevas) — panel de
  adjudicación de remediación sobre endpoints ya vivos:
  `/api/v1/layer9/remediation/directives`,
  `/api/v1/remediation-packages/{project_id}/{package_id}/{version}` y
  variantes (`exceptions`, `medium-risk-batch`, `decision`) — confirmados
  presentes en `curl http://localhost:9000/openapi.json` en vivo.
- Grep de `create_release_record` sobre
  `factory/services/candidate_document_generator.py` y
  `factory/api/routes/layer9.py`: **sin coincidencias** — confirma la
  afirmación del commit de que el panel "nunca invoca
  `create_release_record()`".

## §4 — Gobernanza

**Título en el plan:** familia nueva `REMEDIATION_DIRECTIVE_AUTHORSHIP` +
D6 (línea correspondiente al commit `d224b24`).

**Veredicto:** **PASA**

**Evidencia usada:**
- `factory/registry/decision_families.yaml` líneas 177–195: familia
  `REMEDIATION_DIRECTIVE_AUTHORSHIP` registrada, `target_kind:
  finding_rc_id`, `requires_human_confirmation: true`, con comentario
  inline que documenta por qué no reutiliza
  `REMEDIATION_PACKAGE_GENERATION` (verificado por lectura del módulo:
  `propose_remediation_directive()` no llamaba a ninguna familia de
  gobernanza antes de este commit).
- `factory/layer9/decisions/w5_human_decisions.jsonl`: registro
  `D6_pdf_generation_policy`, `decision: APPROVE`, `approved_by: cesar`,
  `decision_origin: human_confirmed`, `recorded_at:
  2026-08-13T20:53:34Z`.

## Resumen PASA/FALLA

| Sección | Veredicto |
|---|---|
| §0 Frescura de despliegue | PASA |
| §1 Desbloqueo de formato | PASA |
| §2 Validación en frío (8 criterios) | PASA CON OBSERVACIÓN (6/7 tests; 1 fallo de tooling del contenedor) |
| §3 Pre-vuelo (3.2, único ítem auditado) | PASA |
| §4 Gobernanza | PASA |
