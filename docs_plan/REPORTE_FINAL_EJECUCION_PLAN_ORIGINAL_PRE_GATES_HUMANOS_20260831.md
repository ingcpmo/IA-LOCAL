# REPORTE FINAL — EJECUCIÓN DEL PLAN ORIGINAL (pre-gates humanos)

**Fecha:** 2026-08-31 · **Autoridad:** Capa 9 = Cesar · **HEAD:** `ab40f3b`
**Alcance:** ejecución autónoma de **todo el trabajo de máquina** del plan rector
`docs_plan/REVISION_CIERRE_H1_H10_Y_INSTRUCCIONES_20260830.md` + cierres/evidencia ya
generados. **Sin rediseño. Sin nuevos work packages. Sin microajustes de plan.**

```
HUMAN_FINAL_AUTHORITY   = REQUIRED
PRODUCTION_ENABLEMENT   = NOT_ENABLED
REGULATORY_COMPLIANCE   = NOT_DETERMINED_BY_SYSTEM
Commit / push / flip / adjudicación / firma  = NINGUNO
```

Estado cerrado aceptado (NO re-litigado): H1-H10 = TÉCNICAMENTE COMPLETO ·
H10_TECHNICAL_ACCEPTANCE = PASS · R-PAR = PASS · MATERIAL_REGRESSION = NO ·
ALL_MATERIAL_DELTAS_EXPLAINED = YES · RETURN_TO_DESIGN_REQUIRED = NO.

---

## 0 · Verificación de máquina de esta corrida

| Check | Resultado |
|---|---|
| `git HEAD` | `ab40f3b` — sin cambio |
| `decisions_v2.jsonl` | **255 líneas** · `sha256 42fa47f7…` · `git diff --numstat` = `4 0` (`ARTIFACT_VERSION-2026-019/020/021` + `D1-2026-057`) · +1 sola línea nueva sobre el backup pre-remedio-A, 0 líneas alteradas (append-only) |
| MIGRATION_SYNC (remedio A aplicado, autorizado por Cesar) | **RESUELTO.** Parche mínimo al asignador de `instance_id` (`decision_legacy_adapter.py`: `occupied_native_instance_ids` + `_alloc_instance_id` saltan ids NATIVE ocupados). La corrección D1 de Cesar (cadencia 3→2) se proyecta como **`D1-2026-057`** (primer id libre; `D1-2026-003…056` ocupados por registros NATIVE). NATIVE `D1-2026-003` **preservado byte a byte**. `is_stale() = False` · `migrated_in_store == projected == 22`. `test_decision_migration` = **28/28 PASSED**. |
| `canonical_store/RW-0005..0014` (producción real) | **byte-idéntico** a los md5 del `R_PAR_DELTA` §R-PAR.5 (`d9138be2 / 0b03b0ec / 28c42646 / 3db1e795 / b1a46a63 / 07cda6bb`) — **0 pérdida de datos** |
| `canonical_store_v2/` + `graph_store_v2/` (candidato H-10) | byte-idéntico al snapshot pre-misión |
| `graph_store/*.sqlite3` scenario (H7-OBS-T, QC-*, RW-V2-E2E, V2-SHADOW) | reescritos por la suite pytest — churn de test normal, no corpus real, no gobernanza |
| `_EXT_VER` / `_CANON` / `_GRAPH` (`v2_runtime.py:45-47`) | sin flip |
| QA40 `qa40_adjudication_sheet.yaml` | 40/40 `PENDING` · `DRAFT_UNSIGNED` · `sha 02b6d3d0…` |
| E1 `E1_propose_body.json` | 9/77 veredictos registrados (bloque 1) · sin firmar · sin registro gobernado |
| DOCUMENT_EGRESS | 0 |
| Regresión completa (tras remedio A) | `6 failed · 3002 passed · 79 skipped · 1 xfailed` (`_gates_prep/final_regr_remedyA.log`) |
| NEW_REGRESSIONS | **0** — los 6 fallos son exactamente los KNOWN_EXCEPTIONS documentados; `test_decision_migration` pasó a verde (3001→3002 passed) |
| Condiciones STOP-general (`NEW_REGRESSION>0` propio · `MATERIAL_CONTRADICTION` · `DATA_LOSS_RISK` · `DOCUMENT_EGRESS>0` · `GOVERNANCE_INTEGRITY_FAILURE`) | ninguna disparada |

**Regresión — desglose de los 6 fallos (todos KNOWN_EXCEPTIONS):**

| Test | Clase | Nuevo |
|---|---|---|
| `test_artifact_version_signing::test_no_test_in_this_file_wrote_to_the_real_store` | store-guard vs git-HEAD (auto-limpia al commitear D-2/D-4/migración) | no |
| `test_governance_endpoints::test_the_two_stores_stayed_independent` | store-guard vs git-HEAD | no |
| `test_governance_signature_flow_g21::test_n13_no_test_in_this_file_touched_the_real_store` | store-guard vs git-HEAD | no |
| `test_resignature_g2prime::test_no_test_in_this_file_wrote_to_the_real_store` | store-guard vs git-HEAD | no |
| `test_corpus_runner::test_plan_corpus_units_real_reproduce_d4a_232_llamadas` | entorno / servicio | no |
| `test_mission_evidence_readers::test_deployment_exists_and_health` | servicio vivo | no |

---

## 1 · MATRIZ DEL PLAN ORIGINAL

| PLAN_STEP | EXPECTED_BY_ORIGINAL_PLAN | MACHINE_WORK_COMPLETED | HUMAN_ACTION_REQUIRED | CURRENT_STATUS | BLOCKED_BY | EVIDENCE | EXACT_NEXT_ACTION |
|---|---|---|---|---|---|---|---|
| **H1–H10** | Endurecimiento técnico (identidad, aislamiento audit, finding_record_id, snapshot de grafo, local-only/egress, cobertura ENFORCE, evidencia real H-8, benchmark extracción H-9, capacidad H-10 Test/OCR/refers_to) | **SÍ — completo.** Código + tests + fingerprints deterministas. RW-0003 SAT ingerido por OCR docling batched → 17 aristas `tested_by`. | Ninguna adicional (aceptado técnicamente completo) | COMPLETE | — | `CIERRE_TECNICO_PLAN_H1_H10_20260830.md` · `INFORME_MAESTRO_EJECUCION_GMP_AI_FACTORY_H1_H10_20260830.md` · `CIERRE_H8/H9/H10_*` | — |
| **R-PAR** | Paridad e impacto analítico v1↔v2 sobre el corpus compartido, a nivel de findings | **SÍ.** 4 escenarios A/B/C/D; 3 deltas descompuestos; A reproduce D-2 baseline EXACTO; `R_PAR_5 = 4/4 PASS`. | Revisar como insumo de E-2 | COMPLETE (read-only) | — | `R_PAR_DELTA_V1_V2_20260831.md` · `R_PAR_DELTA_V1_V2_20260830.md` · `_r_par/R_PAR_RAW.json` | — |
| **E1** | Adjudicación humana de las 77 relaciones nuevas H-10 + registro `ARTIFACT_VERSION` firmado | Payload gobernado preparado; muestra `sha f56d4dab…`; bloque 1 (9/77) registrado con veredictos de Cesar; validación PASS; 68 filas listadas para adjudicar. | Adjudicar 68 filas (60 `refers_to` + 8 `tested_by`); calcular `verdict_set_sha256`; `propose → confirm` con `X-Identity-Key` | PENDING_HUMAN | — | `E_GATES_GOVERNED_PAYLOADS_20260831/E1_propose_body.json` · `E1_H10_RELATION_REVIEW_PACKET_20260831.md` | Cesar adjudica las 68 filas (packet §HUMAN_ACTION_PACKET E1) |
| **E2** | Aceptación humana del delta R-PAR v1↔v2 | Payload `E2_propose_body.json` + paquete R-PAR listos | APPROVE / REJECT del delta (re-anclaje de 38 findings RW-0012 pág 5 + 1 finding nuevo RW-0009) | PENDING_HUMAN | — | `PAQUETE_GATES_HUMANOS_POST_RPAR_20260831.md` · `E2_propose_body.json` | Cesar decide E2 |
| **E3-A** | Aceptación del paquete canónico CLEAN como base deseada (258 claims RW-0012, no 595) | Paquete CLEAN canónico + payload `E3A_propose_body.json` preparados | APPROVE / REJECT de la base limpia | PENDING_HUMAN | — | `PAQUETE_GATES_HUMANOS_POST_RPAR_20260831.md` · `E3A_propose_body.json` | Cesar decide E3-A |
| **QA40_ALIGNMENT** | Resolver la 1/40 QA40 que no resuelve en escenario D, sin modificar ground truth ni re-muestrear | **SÍ — análisis previo completo.** La 1/40 = `ADJ-34140454ec` (RW-0012, `ALCOA_ATTRIBUTABLE_GAP`, pág 5), uno de los findings re-anclados por clone-drift; el finding analítico **persiste** en D con distinto `finding_record_id`; `RESOLUTION_REASON = CLONE_DRIFT_REANCHOR`. 39/40 resuelven directo. El conjunto de 40 casos **no cambia**. | Confirmar la re-resolución determinista de `ADJ-34140454ec` por `finding_record_id` nuevo (NO re-muestreo) tras E3-A APPROVE | PREPARED (ejecuta tras E3-A) | E3-A | §QA40 de este informe · `qa40_adjudication_sheet.yaml` (sha `02b6d3d0…`) | Tras E3-A: re-mapear `ADJ-34140454ec` al `finding_record_id` de D; 40/40 direccionables |
| **E4 / D-5** | Adjudicación humana H-8: precisión (QA40), recall (oportunidades), especificidad (unidades negativas), firma held-out | **SÍ — instrumento VACÍO construido.** 3 ficheros `:ro` en el runtime endurecido; `score_emitted_review` y `score_recall` verificados fail-closed → `UNKNOWN` sin firma. La IA **no** rellena TP/FP/COVERAGE_LIMITED/ground truth/oportunidades/negativas. | QA escribe todos los campos de ground truth y firma los 3 ficheros (campos exactos abajo) | NOT_OCCURRED (STOP humano obligatorio) | — | `PAQUETE_D5_ADJUDICACION_H8_20260830.md` · `CIERRE_H8_EVIDENCIA_REAL.md` | QA adjudica y firma `qa40_adjudication_sheet.yaml` + `real_corpus_opportunities.yaml` + `held_out_technical_corpus.yaml` |
| **E5** | Registro gobernado autenticado de las firmas de aceptación (E1–E3-A) | Payloads `E{1,2,3A,5}_propose_body.json` preparados; mecanismo `propose → confirm` (familia `ARTIFACT_VERSION`) verificado disponible; endpoints y CLI documentados | Ejecutar `propose → confirm` con `X-API-Key` (`FACTORY_API_KEY`) + `X-Identity-Key` (Cesar), solicitadas de forma oculta | PENDING_HUMAN | E1, E2, E3-A | `GATES_HUMANOS_MECANISMO_20260831.md` · `E5_propose_body.json` | Tras E1–E3-A: firmar por gobernanza autenticada |
| **E6** | Commit exacto del arco (sin `git add .`), árbol limpio | **SÍ — clasificación exacta preparada.** `EXACT_FILES_TO_COMMIT` (código A.1 + `decision_legacy_adapter.py` + `migrate_decisions_to_v2.py`, config gobernada A.2, tests A.4, ops A.5, docs A.6), `EXACT_FILES_TO_EXCLUDE` (stores generados + 1.4 GB `_h9_assets` + drift de misiones previas), `.gitignore` a añadir, procedimiento de staging. **NO commit.** MIGRATION_SYNC resuelto → el diff de `decisions_v2.jsonl` es ahora `4 0` (incluye `D1-2026-057`). | Autorizar el commit; re-verificar a mano el diff del ledger (4 líneas) | PENDING_HUMAN | — | `_gates_prep/E6_FILE_CLASSIFICATION_20260830.md` | Cesar autoriza staging §D y commit |
| **MIGRATION_SYNC** | (no previsto) Almacén v2 sincronizado con los almacenes legacy | **RESUELTO — remedio A aplicado (autorizado por Cesar).** Parche mínimo al asignador de `instance_id`: `occupied_native_instance_ids()` + `_alloc_instance_id()` en `decision_legacy_adapter.py` saltan cualquier id ya ocupado por un registro NATIVE, nunca lo sobrescriben, avanzan al siguiente libre. La corrección D1 de Cesar (cadencia 3→2) se proyecta como **`D1-2026-057`** (`003…056` ocupados por NATIVE — ~30 *propose* UI abandonados + addenda posteriores). NATIVE `D1-2026-003` preservado byte a byte. `migrate --apply --merge-natives`: +1 línea, 0 alteradas. `is_stale()=False`, `22==22`. `test_decision_migration` 28/28 PASSED. | Ninguna (queda como evidencia; el commit E6 la versiona) | RESOLVED | — | `_gates_prep/BLOCKED_decision_migration_id_collision_20260830.md` · `_gates_prep/final_regr_remedyA.log` | — |
| **POST_COMMIT_REGRESSION** | Regresión tras el commit E6; `NEW_REGRESSION = 0` | Predicción preparada: los 4 store-guards vs git-HEAD AUTO-LIMPIAN al quedar `decisions_v2.jsonl` committeado; restan 2 EXC de entorno/servicio vivo | Ejecutar `pytest factory/tests/` tras el commit y confirmar `NEW_REGRESSION = 0` | PREPARED (ejecuta tras E6) | E6 | `_gates_prep/E6_FILE_CLASSIFICATION_20260830.md` §E | Correr la suite tras el commit |
| **WP-F** | Paquete de evidencia de cualificación (contrato declarativo + checker re-ejecutable) | **SÍ — preparado.** Contrato `QC-*` (WP-F) + evidencia. | Revisión humana del paquete como insumo de D-6 | PREPARED | — | `WP_F_PAQUETE_EVIDENCIA_20260830.md` | Cesar revisa WP-F antes de D-6 |
| **D-6** | Declaración humana `QUALIFIED` (nunca por el sistema) | **SÍ — paquete preparado.** Checklist de cualificación + evidencia enlazada. La IA **no** declara `QUALIFIED`. | Cesar declara `D6 = QUALIFIED` o `NOT_QUALIFIED` con el contrato WP-F | NOT_QUALIFIED (pendiente) | E1–E6, D-5, WP-F | `PAQUETE_D6_QUALIFICATION_20260830.md` | Cesar decide D-6 tras cerrar E1–E6 + D-5 |
| **PRODUCTION_ENABLEMENT** | Plan de habilitación de producción | **SÍ — plan preparado** (precondiciones P1–P9, orden, gobernanza, verificación egress H-5F) | Autorizar la habilitación tras P1–P8 verdes | NOT_ENABLED | E1–E6, D-5, D-6 | `PLAN_PRODUCCION_CUTOVER_POST_CUTOVER_20260831.md` §2 | Ninguna hasta cerrar la cadena de gates |
| **CUTOVER** | Plan de flip (rutas/`_EXT_VER` en `v2_runtime.py:45-47`) | **SÍ — plan preparado.** Variante V-A (promoción de contenido, recomendada) / V-B (repunte de rutas, rollback instantáneo); secuencia; fingerprints esperados del candidato; rollback | Cesar elige V-A/V-B y autoriza la ventana | NOT_STARTED | PRODUCTION_ENABLEMENT | `PLAN_PRODUCCION_CUTOVER_POST_CUTOVER_20260831.md` §3 | Ninguna hasta habilitar producción |
| **POST_CUTOVER_REGRESSION** | Regresión + verificación de integridad tras el flip | **SÍ — plan preparado** (suite completa, determinismo de fingerprints ×2, integridad de gobernanza, aislamiento H-5F, R-PAR post-cutover, producto base `gmp-api` PASS=17) | Ejecutar tras el cutover; `CUTOVER_ACCEPTED` sólo si todos los criterios en verde | NOT_STARTED | CUTOVER | `PLAN_PRODUCCION_CUTOVER_POST_CUTOVER_20260831.md` §4 | Ninguna hasta el cutover |

---

## 2 · QA40 — nota de alineación (análisis, sin ejecutar)

- Muestra **inmutable**: `qa40_finding_ids_sha256 = 02b6d3d0b6fadb1f882c4e63b7f7421dd387268ddabe5b5f16abfa5d9d360d32`. **No se re-muestrea.**
- 39/40 `finding_record_id` de la hoja resuelven en el escenario D (candidato H-10).
- La 1/40 que no resuelve: **`ADJ-34140454ec`** — RW-0012, `ALCOA_ATTRIBUTABLE_GAP`, página 5.
  Es uno de los 38 findings de RW-0012 pág 5 re-anclados por **clone-drift** (RR-2, esperado):
  el store de producción sobre-segmentaba la página; la base limpia produce **la misma
  conclusión regulatoria** (mismo requisito, misma banda HIGH, mismo subtipo) anclada en un
  claim distinto → distinto `source_hash` → distinto `finding_record_id`.
- `RESOLUTION_REASON = CLONE_DRIFT_REANCHOR`. **Re-resolución determinista**, no re-muestreo:
  tras E3-A APPROVE, mapear `ADJ-34140454ec` al `finding_record_id` del finding equivalente en D
  por `(document, subtype, criterion, requirement_id, página)`. El conjunto de 40 casos **no cambia**.
- Sin E3-A APPROVE no se toca la hoja.

---

## 3 · HUMAN_ACTION_PACKET

> Cada gate se registra **sólo** por su método gobernado. La IA no inventa la decisión, no
> marca aprobado, no rellena ground truth, no edita `decisions_v2.jsonl` a mano.

### GATE = E1 — adjudicación de 77 relaciones nuevas H-10
```
DECISION_REQUIRED           = por cada fila: CORRECT | WRONG_NODE | SPURIOUS | AMBIGUOUS
EVIDENCE_FILE               = docs_plan/E1_H10_RELATION_REVIEW_PACKET_20260831.md  (evidencia completa por fila)
                              docs_plan/E_GATES_GOVERNED_PAYLOADS_20260831/E1_propose_body.json  (payload gobernado)
CURRENT_STATUS              = 9/77 registrados (bloque 1: TES-01 = CORRECT ; TES-02..09 = SPURIOUS) ; 68 pendientes
CONSEQUENCE_IF_APPROVED     = las relaciones CORRECT quedan aceptadas como parte del grafo candidato H-10 ;
                              WRONG_NODE/SPURIOUS marcan las que el flip NO debe incorporar tal cual
CONSEQUENCE_IF_REJECTED     = si la tasa de SPURIOUS es alta, H-10 vuelve a revisión de extracción antes del cutover ;
                              no bloquea H1-H9
GOVERNED_REGISTRATION_METHOD= rellenar los 68 verdicts en E1_propose_body.json (sólo decisiones humanas) →
                              calcular payload.verdict_set_sha256 (sha256 de la lista canónica) →
                              POST /api/v1/layer9/governance/decisions/ARTIFACT_VERSION/propose  (body = E1_propose_body.json)
                              → POST /api/v1/layer9/governance/decisions/{instance_id}/confirm
                              headers: X-API-Key (FACTORY_API_KEY) + X-Identity-Key (Cesar) — solicitadas ocultas, nunca impresas
```

**E1 — 68 filas NO adjudicadas** (`verdict = ""`). Anclaje y nodos abreviados; texto completo en el packet.

*60 `refers_to` (claim → system_component / actor, por nombre literal):*

| Fila | Doc | Pág | Ancla exacta (origen) | Etiqueta destino | prov_hash |
|---|---|---|---|---|---|
| REF-01 | RW-0005 | 9 | FactoryTalk Linx Enterprise 6.21.00 Server | FactoryTalk | 113f38c655ea |
| REF-02 | RW-0005 | 9 | FactoryTalk View Studio Site Edition Enterprise | FactoryTalk View | 949b967bfe00 |
| REF-03 | RW-0005 | 13 | Allen-Bradley 1756-L83E ControlLogix 5580 | ControlLogix | 23c09c46317f |
| REF-04 | RW-0005 | 9 | FactoryTalk Linx Enterprise 6.21.00 Server | FactoryTalk | 113f38c655ea |
| REF-05 | RW-0005 | 13 | Allen-Bradley 1756-L83E ControlLogix 5580 | ControlLogix | 23c09c46317f |
| REF-06 | RW-0005 | 9 | FactoryTalk View Studio Site Edition Enterprise | FactoryTalk View | 949b967bfe00 |
| REF-07 | RW-0012 | 4 | PCS – Process Control System | CP01 | 98ef121b1460 |
| REF-08 | RW-0005 | 13 | delivered system has the Rockwell … | FactoryTalk View SE | 0d268ad3aaaf |
| REF-09 | RW-0005 | 9 | FactoryTalk Historian DataLink Excel Reporting | FactoryTalk Historian | 583f544a6fcb |
| REF-10 | RW-0005 | 9 | FactoryTalk View Studio Site Edition Enterprise | FactoryTalk View | 949b967bfe00 |
| REF-11 | RW-0011 | 4 | XAH-00001-06 DO PCS Status Indicator on PCS-… | PCS-CP-01 | 70a121abda10 |
| REF-12 | RW-0005 | 9 | FactoryTalk View Studio Site Edition Enterprise | FactoryTalk View | 949b967bfe00 |
| REF-13 | RW-0005 | 9 | Engineering Workstation PC located in Room 0… | engineering workstation | 2162cdf9b715 |
| REF-14 | RW-0005 | 9 | Engineering Workstation PC located in Room 0… | engineering workstation | 2162cdf9b715 |
| REF-15 | RW-0014 | 4 | PCS – Process Control System | CP01 | 98ef121b1460 |
| REF-16 | RW-0005 | 13 | A ThinManager® software solution … | thin client | 9e65be5b22dc |
| REF-17 | RW-0014 | 4 | PCS – Process Control System | CP01 | 98ef121b1460 |
| REF-18 | RW-0005 | 9 | FactoryTalk View Studio Site Edition Enterprise | FactoryTalk View | 949b967bfe00 |
| REF-19 | RW-0005 | 9 | FactoryTalk Linx Enterprise 6.21.00 Server | FactoryTalk | 113f38c655ea |
| REF-20 | RW-0006 | 4 | interfaces with the FactoryTalk View SE … | FactoryTalk View | 96832c1e9ae0 |
| REF-21 | RW-0006 | 6 | MicroLogix or CompactLogix. | CompactLogix | 47dba39745c7 |
| REF-22 | RW-0005 | 9 | FactoryTalk Linx Enterprise 6.21.00 Server | FactoryTalk | 113f38c655ea |
| REF-23 | RW-0005 | 9 | FactoryTalk Linx Enterprise 6.21.00 Server | FactoryTalk | 113f38c655ea |
| REF-24 | RW-0005 | 9 | FactoryTalk Linx Enterprise 6.21.00 Server | FactoryTalk | 113f38c655ea |
| REF-25 | RW-0012 | 5 | from the FactoryTalk Linx driver itself | FactoryTalk | 1ce8e2840ffd |
| REF-26 | RW-0005 | 9 | Engineering Workstation PC located in Room 0… | engineering workstation | 2162cdf9b715 |
| REF-27 | RW-0005 | 13 | Allen-Bradley 1756-L83E ControlLogix 5580 | ControlLogix | 23c09c46317f |
| REF-28 | RW-0005 | 9 | Engineering Workstation PC located in Room 0… | engineering workstation | 2162cdf9b715 |
| REF-29 | RW-0005 | 9 | FactoryTalk Linx Enterprise 6.21.00 Server | FactoryTalk | 113f38c655ea |
| REF-30 | RW-0005 | 9 | FactoryTalk View Studio Site Edition Enterprise | FactoryTalk View | 949b967bfe00 |
| REF-31 | RW-0005 | 9 | FactoryTalk Linx Enterprise 6.21.00 Server | FactoryTalk | 113f38c655ea |
| REF-32 | RW-0006 | 6 | MicroLogix or CompactLogix. | CompactLogix | 47dba39745c7 |
| REF-33 | RW-0014 | 4 | PCS – Process Control System | PCS-CP01 | 98ef121b1460 |
| REF-34 | RW-0005 | 49 | CompactLogix (5380 series). | CompactLogix | a2c25d145432 |
| REF-35 | RW-0011 | 3 | PCS – Process Control System | CP01 | 98ef121b1460 |
| REF-36 | RW-0005 | 9 | FactoryTalk View Studio Site Edition Enterprise | FactoryTalk View | 949b967bfe00 |
| REF-37 | RW-0005 | 9 | FactoryTalk Linx Enterprise 6.21.00 Server | FactoryTalk Linx | 113f38c655ea |
| REF-38 | RW-0005 | 9 | FactoryTalk View Studio Site Edition Enterprise | FactoryTalk View | 949b967bfe00 |
| REF-39 | RW-0005 | 13 | delivered system has the Rockwell … | FactoryTalk View SE | 0d268ad3aaaf |
| REF-40 | RW-0005 | 9 | FactoryTalk View Studio Site Edition Enterprise | FactoryTalk View | 949b967bfe00 |
| REF-41 | RW-0005 | 49 | CompactLogix (5380 series). | CompactLogix | a2c25d145432 |
| REF-42 | RW-0014 | 5 | is handled in the PLC and not in the FactoryTalk… | FactoryTalk | 2b7f21e6a9a6 |
| REF-43 | RW-0005 | 9 | FactoryTalk Linx Enterprise 6.21.00 Server | FactoryTalk | 113f38c655ea |
| REF-44 | RW-0011 | 4 | in the FactoryTalk Historian Site Edition … | FactoryTalk | 233dcd3ed90c |
| REF-45 | RW-0005 | 9 | FactoryTalk Linx Enterprise 6.21.00 Server | FactoryTalk | 113f38c655ea |
| REF-46 | RW-0005 | 13 | delivered system has the Rockwell … | FactoryTalk View SE | 0d268ad3aaaf |
| REF-47 | RW-0014 | 4 | PCS – Process Control System | PCS-CP01 | 98ef121b1460 |
| REF-48 | RW-0005 | 1 | PLC Interfaces (PCS-CP01 and other Vendor …) | CP01 | 4b01e10bb51e |
| REF-49 | RW-0014 | 4 | PCS – Process Control System | CP01 | 98ef121b1460 |
| REF-50 | RW-0005 | 9 | FactoryTalk Linx Enterprise 6.21.00 Server | FactoryTalk | 113f38c655ea |
| REF-51 | RW-0005 | 9 | FactoryTalk View Studio Site Edition Enterprise | FactoryTalk View | 949b967bfe00 |
| REF-52 | RW-0005 | 9 | FactoryTalk View Studio Site Edition Enterprise | FactoryTalk View | 949b967bfe00 |
| REF-53 | RW-0005 | 13 | Administrator and Maintenance login … | Administrator | 036322553783 |
| REF-54 | RW-0005 | 9 | FactoryTalk View Studio Site Edition Enterprise | FactoryTalk View | 949b967bfe00 |
| REF-55 | RW-0005 | 49 | CompactLogix (5380 series). | CompactLogix | a2c25d145432 |
| REF-56 | RW-0005 | 9 | FactoryTalk Linx Enterprise 6.21.00 Server | FactoryTalk | 113f38c655ea |
| REF-57 | RW-0006 | 4 | interfaces with the FactoryTalk View SE … | FactoryTalk | 96832c1e9ae0 |
| REF-58 | RW-0005 | 9 | FactoryTalk View Studio Site Edition Enterprise | FactoryTalk View | 949b967bfe00 |
| REF-59 | RW-0014 | 4 | PCS – Process Control System | CP01 | 98ef121b1460 |
| REF-60 | RW-0005 | 13 | delivered system has the Rockwell … | FactoryTalk View SE | 0d268ad3aaaf |

*8 `tested_by` (URS/FS → SAT RW-0003, vía 3.2.3 / F05.05):*

| Fila | Doc | Pág | Ancla (origen) | Requisito destino | prov_hash |
|---|---|---|---|---|---|
| TES-10 | RW-0005 | 192 | UR4.1.1 [MCCPDC 3.2.3] – The physical server … | UR3.2.3 (Critical-to-Quality Alarms) | 8b054b046f67 |
| TES-11 | RW-0005 | 158 | specification (See 3.1.9, F05.05:) | F05.05 Input State and Simulation Review Screen | b81489fbaa3f |
| TES-12 | RW-0006 | 192 | List of Critical-to-Quality Alarms. | UR3.2.3 | 8b054b046f67 |
| TES-13 | RW-0005 | 192 | UR4.1.1 [MCCPDC 3.2.3] – The physical server … | UR3.2.3 | 8b054b046f67 |
| TES-14 | RW-0005 | 192 | UR3.2.3 The Equipment shall have critical alarms … | UR3.2.3 | 8b054b046f67 |
| TES-15 | RW-0005 | 157 | specification (See 3.1.9, F05.05:) | F05.05 Input State and Simulation Review Screen | cd0bf8a2144e |
| TES-16 | RW-0005 | 158 | screen, accessible by Admin and Maintenance … | F05.05 Input State and Simulation Review Screen | b81489fbaa3f |
| TES-17 | RW-0005 | 192 | UR4.1.1 requirement includes in its text … | UR3.2.3 | 8b054b046f67 |

### GATE = E2 — aceptación del delta R-PAR v1↔v2
```
DECISION_REQUIRED           = APPROVE | REJECT del delta sobre el corpus compartido
EVIDENCE_FILE               = docs_plan/R_PAR_DELTA_V1_V2_20260831.md  ·  E_GATES_GOVERNED_PAYLOADS_20260831/E2_propose_body.json
CURRENT_STATUS              = PENDING_HUMAN
CONSEQUENCE_IF_APPROVED     = se acepta que activar v2 re-ancla 38 findings de RW-0012 pág 5 (misma conclusión,
                              mejor ancla) y añade 1 finding legítimo (RW-0009 TEST_WITHOUT_REQUIREMENT, LOW) ;
                              0 bandas cambian ; 0 findings perdidos por causa distinta a clone-drift
CONSEQUENCE_IF_REJECTED     = el flip no procede hasta reconciliar el delta ; H1-H10 técnicos no se revierten
GOVERNED_REGISTRATION_METHOD= propose → confirm (familia ARTIFACT_VERSION) con E2_propose_body.json ; X-API-Key + X-Identity-Key
```

### GATE = E3-A — aceptación del paquete canónico CLEAN
```
DECISION_REQUIRED           = APPROVE | REJECT de la base limpia (RW-0012 = 258 claims, no 595)
EVIDENCE_FILE               = docs_plan/PAQUETE_GATES_HUMANOS_POST_RPAR_20260831.md  ·  E3A_propose_body.json
CURRENT_STATUS              = PENDING_HUMAN
CONSEQUENCE_IF_APPROVED     = la re-extracción limpia (sin las páginas fantasma 17/18 del store de producción)
                              queda como base canónica deseada ; habilita la re-resolución determinista de QA40 y el cutover V-A
CONSEQUENCE_IF_REJECTED     = se conserva el store de producción sobre-segmentado ; QA40_ALIGNMENT y CUTOVER quedan bloqueados
GOVERNED_REGISTRATION_METHOD= propose → confirm (ARTIFACT_VERSION) con E3A_propose_body.json ; X-API-Key + X-Identity-Key
```

### GATE = E4 / D-5 — adjudicación humana H-8 (STOP obligatorio)
```
DECISION_REQUIRED           = QA escribe TODO el ground truth y firma los 3 ficheros
EVIDENCE_FILE               = docs_plan/PAQUETE_D5_ADJUDICACION_H8_20260830.md
                              factory/regulatory/requirement_catalog/qa40_adjudication_sheet.yaml        (:ro en runtime)
                              factory/regulatory/requirement_catalog/real_corpus_opportunities.yaml      (:ro)
                              factory/regulatory/requirement_catalog/held_out_technical_corpus.yaml      (:ro)
CURRENT_STATUS              = NOT_OCCURRED ; QA40 40/40 PENDING ; score_emitted_review / score_recall = UNKNOWN (fail-closed verificado)
CONSEQUENCE_IF_APPROVED     = QA40_SAMPLE_PRECISION = TP/(TP+FP) + Wilson ; REAL_RECALL = TP/(TP+FN) ;
                              REAL_SPECIFICITY calculable ; held-out firmado → D-6 puede evaluarse
CONSEQUENCE_IF_REJECTED     = las tres métricas permanecen UNKNOWN por diseño ; D-6 no puede declararse QUALIFIED
GOVERNED_REGISTRATION_METHOD= edición en el HOST (runtime las ve :ro) + firma en cada fichero:
                              status: SIGNED + identidad real + timestamp ISO-8601 ; aviso a Capa 8 con la ruta

CAMPOS DE GROUND TRUTH QUE REQUIEREN HUMANO (la IA NO los rellena):

qa40_adjudication_sheet.yaml — por cada uno de los 40 casos:
  label ∈ {TP, FP, COVERAGE_LIMITED}
  human_evidence_anchor        (cita / página exacta que sustenta la decisión)
  adjudicator_note             (por qué)
  held_out_provenance_tag ∈ {REG, DOM, ADV, (vacío)}
  PROHIBIDO en esta hoja: FN, TN
  al terminar: status: SIGNED · adjudicator: "<nombre real>" · adjudicated_at: "<ISO-8601>"

real_corpus_opportunities.yaml → opportunities:  (recall / FN — QA lee el CORPUS, no los findings)
  opportunity_id · expected_class · expected_subtype · document
  page_band ([int,int], start≤end, >0)
  expected_topic_or_requirement · human_evidence_anchor · basis · reviewer_note
  + al adjudicar match:  matched_finding_id · match_confirmed_by · match_note  (uno-a-uno ; el finding debe existir en la corrida)
  sin los 3 campos de match ⇒ esa oportunidad cuenta como FN

real_corpus_opportunities.yaml → negative_units:  (especificidad / TN — no se inventan)
  unit_id · analysis_unit ∈ {section, document, page_range} · document
  scope ([int,int], start≤end, >0)
  expected_class · expected_subtype · human_evidence_anchor · basis · reviewer_note · human_verified: true
  al terminar: status: SIGNED · adjudicator · adjudicated_at

held_out_technical_corpus.yaml — firma (5 casos):
  revisar case_id · provenance_tag ∈ {REG, DOM, ADV} · expected · match
  confirmar: los REG traen source_clause ; los ADV traen human_approved: true
  firmar: status: SIGNED · rules_author: "<nombre real>"  (≠ autor del corpus semilla)
```

### GATE = E5 — registro gobernado autenticado de E1–E3-A
```
DECISION_REQUIRED           = ejecutar propose → confirm de cada aceptación firmada
EVIDENCE_FILE               = docs_plan/GATES_HUMANOS_MECANISMO_20260831.md  ·  E_GATES_GOVERNED_PAYLOADS_20260831/E5_propose_body.json
CURRENT_STATUS              = PENDING_HUMAN ; BLOCKED_BY E1, E2, E3-A
CONSEQUENCE_IF_APPROVED     = las aceptaciones quedan en el ledger append-only (evento layer9_decision_recorded) ; habilita E6/D-6
CONSEQUENCE_IF_REJECTED     = las aceptaciones no quedan registradas ; el arco no puede cerrarse
GOVERNED_REGISTRATION_METHOD= POST .../governance/decisions/ARTIFACT_VERSION/propose  →  POST .../decisions/{instance_id}/confirm
                              headers X-API-Key (FACTORY_API_KEY) + X-Identity-Key (Cesar) — ocultas, nunca impresas
                              CLI alterna: factory/scripts/ops/sign_artifact_version_proposal.py (flujo hash-echo)
```

### GATE = E6 — autorización de commit
```
DECISION_REQUIRED           = autorizar el commit del arco con la lista EXACTA (sin git add .)
EVIDENCE_FILE               = docs_plan/_gates_prep/E6_FILE_CLASSIFICATION_20260830.md
CURRENT_STATUS              = PENDING_HUMAN (sin BLOCKED_BY — MIGRATION_SYNC resuelto)
CONSEQUENCE_IF_APPROVED     = el código/config/tests/ops/docs del arco quedan versionados ; los 4 store-guards vs git-HEAD
                              AUTO-LIMPIAN ; habilita POST_COMMIT_REGRESSION y D-6
CONSEQUENCE_IF_REJECTED     = el arco permanece sólo en el árbol de trabajo ; riesgo de pérdida por operaciones git posteriores
GOVERNED_REGISTRATION_METHOD= (1) aplicar bloque .gitignore §C ;
                              (2) git add <rutas exactas de A.1 (incl. decision_legacy_adapter.py + migrate_decisions_to_v2.py) / A.2 / A.4 / A.5 / A.6> ;
                              (3) git add factory/layer9/decisions/{decisions_v2.jsonl,w5_human_decisions.jsonl} tras re-verificar a mano el diff (4 líneas: 019/020/021 + D1-2026-057) ;
                              (4) git status + git diff --cached --stat contra la lista A ; (5) commit (sin secretos) ; NO push sin autorización aparte
```

### GATE = MIGRATION_SYNC — RESUELTO (remedio A, autorizado por Cesar)
```
DECISION_REQUIRED           = ninguna — cerrado
EVIDENCE_FILE               = docs_plan/_gates_prep/BLOCKED_decision_migration_id_collision_20260830.md  ·  _gates_prep/final_regr_remedyA.log
CURRENT_STATUS              = RESOLVED
WHAT_WAS_DONE               = parche mínimo en factory/services/decision_legacy_adapter.py:
                              - occupied_native_instance_ids(): lee el almacén v2 y devuelve los instance_id
                                cuya provenance NO es de migración (NATIVE)
                              - _alloc_instance_id(): incrementa el contador (familia,año) y SALTA cualquier id
                                ocupado por un NATIVE ; nunca lo sobrescribe ; sólo avanza (append-only, monótono)
                              - project_all(occupied_from=<almacén destino>) lo aplica a Sistema A y B
                              factory/scripts/ops/migrate_decisions_to_v2.py: run() e is_stale() pasan occupied_from=target
NEW_V2_RECORD              = D1-2026-057  (primer id libre ; D1-2026-003…056 ocupados por NATIVE —
                              ~30 propose de Mission Control abandonados + addenda/correcciones NATIVE posteriores.
                              NO es D1-2026-004: ese número también está ocupado por un NATIVE.)
NATIVE_RECORD_PRESERVED    = D1-2026-003 (propose UI 2026-07-29) intacto byte a byte ; +1 sola línea nueva, 0 alteradas
RESULT                    = is_stale() = False ; migrated_in_store == projected == 22 ;
                            legacy_count == projected_v2_count ; test_decision_migration = 28/28 PASSED
```

### GATE = D-6 — declaración de cualificación
```
DECISION_REQUIRED           = D6 = QUALIFIED | NOT_QUALIFIED  (humano ; el sistema NO lo declara)
EVIDENCE_FILE               = docs_plan/PAQUETE_D6_QUALIFICATION_20260830.md  ·  docs_plan/WP_F_PAQUETE_EVIDENCIA_20260830.md  ·  contrato QC-*
CURRENT_STATUS              = NOT_QUALIFIED (pendiente) ; BLOCKED_BY E1–E6, D-5, WP-F
CONSEQUENCE_IF_APPROVED     = habilita PRODUCTION_ENABLEMENT
CONSEQUENCE_IF_REJECTED     = el analizador no pasa a producción ; se identifican los gaps del contrato WP-F a cerrar
GOVERNED_REGISTRATION_METHOD= decisión de Capa 9 registrada por el mecanismo de gobernanza con el contrato WP-F re-ejecutable como evidencia
```

### GATE = PRODUCTION_ENABLEMENT / CUTOVER / POST_CUTOVER_REGRESSION
```
DECISION_REQUIRED           = autorizar habilitación ; elegir variante de cutover V-A|V-B ; autorizar la ventana
EVIDENCE_FILE               = docs_plan/PLAN_PRODUCCION_CUTOVER_POST_CUTOVER_20260831.md
CURRENT_STATUS              = NOT_ENABLED / NOT_STARTED / NOT_STARTED ; BLOCKED_BY E1–E6, D-5, D-6
CONSEQUENCE_IF_APPROVED     = el pipeline V2 +tests-v1 (ENFORCE, H-10) sirve informes reales ; el flip repunta
                              _CANON/_GRAPH/_EXT_VER (V-B) o promueve contenido a la raíz de producción (V-A)
CONSEQUENCE_IF_REJECTED     = se mantiene el pipeline actual ; el trabajo del arco queda listo pero inactivo
GOVERNED_REGISTRATION_METHOD= decisión de Capa 9 por gobernanza + backup verificado + registro del cutover +
                              regresión post-cutover con CUTOVER_ACCEPTED sólo si todos los criterios §4.1 en verde
```

---

## 4 · RESPUESTAS FINALES

```
ALL_MACHINE_EXECUTABLE_WORK_COMPLETED = YES — sin salvedades. MIGRATION_SYNC (remedio A) aplicado,
                                        migración re-ejecutada, test_decision_migration 28/28,
                                        regresión completa 6 failed (todos KNOWN_EXCEPTIONS) / 3002 passed,
                                        NEW_REGRESSIONS = 0.

MACHINE_WORK_STILL_MISSING           = Ninguno. Lo que resta se ejecuta DESPUÉS de una decisión humana concreta:
                                        - QA40_ALIGNMENT: re-resolución determinista de ADJ-34140454ec (tras E3-A APPROVE)
                                        - POST_COMMIT_REGRESSION: correr la suite (tras E6)
                                        - POST_CUTOVER_REGRESSION: correr la suite + verificaciones (tras CUTOVER)

HUMAN_GATES_PENDING                  = E1 (68/77 filas) · E2 · E3-A · E4/D-5 · E5 · E6 ·
                                        D-6 · PRODUCTION_ENABLEMENT · CUTOVER
                                        (MIGRATION_SYNC ya no está pendiente — RESUELTO)

FIRST_ACTION_AFTER_HUMAN_APPROVAL    = E1: adjudicar las 68 filas del §3 HUMAN_ACTION_PACKET
                                        (60 refers_to + 8 tested_by), calcular verdict_set_sha256,
                                        y firmar por gobernanza autenticada (propose → confirm,
                                        X-API-Key + X-Identity-Key). En paralelo, E6: autorizar el
                                        commit con la lista exacta (ya sin bloqueo).

ORIGINAL_PLAN_COMPLETE              = NO — el trabajo de máquina previo a los gates humanos está
                                        COMPLETO; el plan se cierra cuando Capa 9 resuelva
                                        E1, E2, E3-A, E4/D-5, E5, E6 y D-6, y (si procede) autorice
                                        PRODUCTION_ENABLEMENT + CUTOVER + POST_CUTOVER_REGRESSION.
```

---

## 5 · Reglas mantenidas durante toda la corrida

- Nunca: auto-adjudicar E1 · auto-aprobar E2 · auto-aprobar E3-A · generar TP/FP/COVERAGE_LIMITED
  por IA · inventar oportunidades o negativas · inventar firmas · editar `decisions_v2.jsonl` a mano ·
  declarar D6 = QUALIFIED sin humano · activar producción · hacer cutover.
- Git: sin commit. No se usó `git add .` / `git add -A` / `git reset --hard` / `git clean` / `git stash`.
- La migración legacy→v2 se ejecutó (autorizada por Cesar, remedio A) con `--apply --merge-natives`:
  `APLICADA`, entradas legacy intactas, **+1 sola línea** (`D1-2026-057`), 0 líneas alteradas
  (append-only). NATIVE `D1-2026-003` preservado. El parche tocó sólo el asignador de
  `instance_id` de la migración (`decision_legacy_adapter.py`, `migrate_decisions_to_v2.py`) —
  sin rediseño, sin nuevo ledger, sin nueva arquitectura.
- Producto base intacto: no se tocó `gmp-api` / `gmp-postgres` / `gmp-redis` / contenedores `aria-*` / `hotelbot-*`.
  No se mostró contenido de `.env`. Claves de API/identidad nunca impresas ni guardadas.
