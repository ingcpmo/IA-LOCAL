# 02 — Commits y Archivos

Rango auditado: `d224b24` → `e8e8b2c` (5 commits, todos del 2026-08-13,
21:10–21:20 UTC, autor `ing_cpmo`). Verificado con `git log -1 --stat` sobre
cada hash y `git log -1 --format="%H %ci"` para las fechas exactas.

## `d224b24` — feat(r4-t1.1v2): familia REMEDIATION_DIRECTIVE_AUTHORSHIP + D6 política PDF

**Propósito:** cierra §4 de R4-T1.1v2 (gobernanza). Registra una familia de
decisión nueva para la autoría humana de una directiva de remediación
(distinta de `REMEDIATION_PACKAGE_GENERATION`, que cubre la generación
automática posterior porque una directiva no tiene `package_id` — existe
antes del paquete). Firma D6 (`D6_pdf_generation_policy`) como decisión
humana de Cesar, confirmando la política ya implementada de generación PDF
sin fuente editable.

**Archivos incluidos:**
- `docs_plan/R4_T1_1v2_DESBLOQUEO_Y_VALIDACION_FRIA.md` (+1090) — el plan que
  esta auditoría verifica.
- `factory/layer9/decisions/w5_human_decisions.jsonl` (+1) — registro
  `D6_pdf_generation_policy`.
- `factory/registry/decision_families.yaml` (+20) — familia
  `REMEDIATION_DIRECTIVE_AUTHORSHIP`.
- `factory/services/w5_human_decisions.py` (+23) — soporte de la decisión D6.

**Qué quedó excluido:** ningún cambio de código de negocio fuera de
gobernanza; sin cambios en Docker, endpoints HTTP nuevos ni en el pipeline
de evaluación.

**Tests asociados:** ninguno agregado en este commit específico; la
cobertura de la familia nueva se ejerce indirectamente por
`test_r4_t1_1v2_cold_chain_validation.py`, agregado en el commit siguiente.

## `0796bb9` — feat(r4-t1.1v2): panel de adjudicación de remediación + marca NO_APROBADO

**Propósito:** cierra §3.2 (panel mínimo de adjudicación, bloqueante de
pre-vuelo) y respalda §2.3.b (marca "BORRADOR — NO APROBADO — pendiente de
revisión QA") de R4-T1.1v2. UI de Mission Control sobre endpoints de
directivas/paquetes de remediación ya vivos — sin backend nuevo, y sin
invocar `create_release_record()` en ningún punto (verificado por grep, ver
`03_VALIDACION_EN_VIVO.md`).

**Archivos incluidos:**
- `factory/services/candidate_document_generator.py` (+18) — constante
  `NO_APROBADO_MARK` centralizada, aplicada a candidato y redline.
- `factory/tests/test_r4_t1_1v2_cold_chain_validation.py` (+420, nuevo) — 7
  tests de validación en frío de la cadena completa, 0 llamadas LLM.
- `factory/ui/js/mission_control/main.js` (+3)
- `factory/ui/js/mission_control/refresh.js` (+12/-1)
- `factory/ui/js/mission_control/remediation.js` (+281, nuevo) — panel de
  adjudicación.
- `factory/ui/mission_control.html` (+33)

**Qué quedó excluido:** ningún backend nuevo; el commit reutiliza
deliberadamente endpoints existentes de `factory/api/routes/layer9.py`.

**Tests asociados:** `factory/tests/test_r4_t1_1v2_cold_chain_validation.py`
— 7 tests, 8 criterios de aceptación declarados en el mensaje de commit.
Resultado de ejecución real dentro del contenedor: 6 passed, 1 failed (ver
`01_ESTADO_PLAN_SECCIONES.md`, §2, y `03_VALIDACION_EN_VIVO.md`).

## `c2c06bb` — feat(r2.2): familia EMBED_EXECUTION -- capa semántica local de embeddings

**Propósito:** autorización ligera para llamadas de embedding (vectores
deterministas, no juicio LLM) usadas para medir recuperación semántica —
BM25 + embeddings + fusión — sobre el caso de paráfrasis (P2/P4/P5/P6/P7,
R2.2 §3). Familia separada a propósito de `PILOT_EXECUTION` para que el
presupuesto de recall de juicio nunca se mezcle con el de recuperación
semántica.

**Archivos incluidos:**
- `docs_plan/R2_1_DECISION_PACKAGE.md` (+87/-24 netos sobre archivo
  existente)
- `factory/.gitignore` (+5, nuevo)
- `factory/registry/decision_families.yaml` (+22) — familia
  `EMBED_EXECUTION`.
- `factory/services/governance_service.py` (+2/-1)
- `factory/ui/js/mission_control/governance.js` (+88, nuevo) — panel de
  firma en Mission Control.
- `factory/ui/js/mission_control/main.js` (+4/-1)

**Qué quedó excluido:** no toca `PILOT_EXECUTION` ni el presupuesto de
llamadas de juicio LLM ya firmado.

**Tests asociados:** ninguno agregado en este commit; el estado declarado en
el mensaje es re-medición parcial (20/25 llamadas reales, P7 pendiente), no
verificado en esta auditoría (fuera del alcance de R4-T1.1v2).

## `99f36c3` — chore(r3-t1.8): persist audited pilot execution and review queue records

**Propósito:** persiste registros de ejecución piloto auditada (R3-T1.8) y
de la cola de revisión — commit de datos, no de código.

**Archivos incluidos:**
- `factory/layer9/decisions/decisions_v2.jsonl` (+2) — instancias
  `PILOT_EXECUTION-2026-017` (`agent_proposed`) y `PILOT_EXECUTION-2026-018`
  (`human_confirmed` por `cesar`), ambas apuntando a RW-0005 con
  `authorizes_corpus: false`, `authorizes_baseline: false`.
- `factory/layer9/review_queue.jsonl` (+7/-1) — la línea `-1`/`+1` marca la
  transición `pending` → `confirmed` de
  `finding-chunked-50534e75927c-21_CFR_11.10(e)` (revisado por `cesar`,
  `2026-08-12T21:13:14Z`, `human_confirmed_evidence.quote="mejora"`); las
  otras 6 líneas nuevas son entradas `pending` para RW-0005 sobre
  `21_CFR_11.10(e)` (runs `chunked-2678358a06b3`, `chunked-e6994ea8e953`,
  `chunked-d9b5bc77c9db`, `chunked-c2c7dff6900c`, `chunked-e8208618982a`) más
  la ya contada como confirmada.

**Qué quedó excluido:** ningún código de producción; commit puramente de
datos append-only (ver `04_GOBERNANZA_DATOS.md` para el detalle de qué es
append vs. mutación controlada).

**Tests asociados:** ninguno — es persistencia de artefactos de ejecución
real, no código bajo test.

## `e8e8b2c` — chore: ignorar .gnupg/ y private_reports/ en la raíz del home

**Propósito:** ambos directorios quedaron sueltos en el working tree (el
home es también el repo) sin regla que los cubriera — un `git add -A` los
habría commiteado por error. `.gnupg/` es un keyring GPG local;
`private_reports/` contiene auditorías internas. Ninguno debe entrar al
historial de git.

**Archivos incluidos:**
- `.gitignore` (+4)

**Qué quedó excluido:** no se tocó ningún archivo dentro de `.gnupg/` ni de
`private_reports/` — solo se agregó la regla de exclusión.

**Tests asociados:** ninguno aplicable (cambio de configuración de git).
