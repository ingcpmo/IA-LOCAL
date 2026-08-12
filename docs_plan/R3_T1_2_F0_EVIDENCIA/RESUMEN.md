# R3-T1.2 — Evidencia de Fase F0 (2026-08-12)

Plan de referencia: `docs_plan/R3_T1_2_PLAN_POR_FASES.md`.
Ejecutado por Claude Code (Capa 8) en sesión con Cesar (Capa 9), en esta misma
sesión de conversación. Ningún commit se hizo sin mostrar diff; ninguna firma
de gobernanza (D2/ARTIFACT_VERSION) fue confirmada por el agente — solo
propuesta (`agent_proposed`), pendiente de Cesar.

## Estado final

- **5 commits** en `master`, uno por causa raíz (ver `commits.txt`/`commits_full.txt`).
- **Gate 0**: corrido 2 veces completas (`gate0_run1_raw.log` antes de commitear,
  `gate0_run2_raw.log` después). Primera corrida: `PASS=5 WARN=2 FAIL=1`
  (8 failed, 2413 passed). Segunda corrida (post-commit): `PASS=5 WARN=2 FAIL=1`
  (4 failed, 2417 passed) — las 4 fallas que desaparecieron entre una corrida y
  la otra eran exactamente los guardianes "nadie escribió en el almacén real"
  (comparan `decisions_v2.jsonl` contra `git diff HEAD`); las 4 restantes son
  `TimeoutError`/rate-limit contra el servidor Mission Control vivo bajo carga
  sostenida de tests (Playwright/HTTP), en archivos que ningún commit de esta
  sesión toca (`governance.js`, `governance_service.py`) — no son regresión de
  este trabajo.
- **1 decisión de gobernanza propuesta, sin confirmar**: `ARTIFACT_VERSION-2026-018`
  (ver `decision_pendiente_ARTIFACT_VERSION-2026-018.json`). Requiere firma de
  Cesar antes de tener efecto real sobre `requirements.yaml`.

## F0.1 — Verificación del hallazgo

Confirmado con cita exacta: el run `chunked-943a62bcbb85` (RW-0005, informe
Tier-1) corrió con `evaluation_profile=BASELINE` (0/7 de recall en el fixture
set) por un default no declarado — `factory/regulatory/tier1_report.py`
llamaba a `chunked_engine.evaluate_chunked()` sin pasar `evaluation_profile`,
heredando en silencio el default de esa función (`chunked_engine.py:912`).
`PILOT_EXECUTION-2026-013/014` (aprobación real de Cesar, 2026-08-11) autorizó
el eje de cobertura de documento ("modo baseline"), nunca el parámetro
`evaluation_profile` — el default se aplicó por omisión, no por decisión
humana consciente.

## F0.2 — Enforcement del perfil de producto

`generate_tier1_report()` ahora exige `evaluation_profile` explícito (sin
default — omitirlo es `TypeError`). `'BASELINE'` queda bloqueado
(`Tier1ReportError`, cita el 0/7 de recall); solo se acepta `'H2H4'`. Alcance
acotado a Tier-1 (`tier1_report.py`) — `corpus_runner.py` queda fuera a
propósito (decisión explícita de Cesar durante la sesión: generalizar el
enforcement a `run_context='production'` rompería el runner formal del
corpus, que no puede evaluar el catálogo completo bajo H2H4 sin un rediseño
de alcance mayor, no estimado en el plan original).

Commit: `8a99b4e` (junto con F0.5). Tests: 4 actualizados + 2 nuevos en
`test_tier1_report.py`.

## F0.3 — Informe 943a marcado como superseded

Nueva función `human_review_queue.supersede_finding()` — marca una entrada
como `SUPERSEDED` por defecto técnico confirmado, nunca por juicio humano
(no reutiliza `mark_reviewed()`, que exige identidad de revisor real). El
registro original nunca se borra. Nuevo evento de auditoría
`finding_superseded` (allow-list de `audit_writer.py`).

Aplicado a las 3 entradas reales de cola del run 943a
(`finding-chunked-943a62bcbb85-21_CFR_11.10(d)/(e)/(g)`) + sidecar
`SUPERSEDED_BY_PROFILE_CORRECTION.json` junto al informe persistido
(`factory/regulatory/pilot_run/tier1_rw0005/`), sin tocar ni borrar los
artefactos originales.

Commit: `14ffbc4`. Tests: 5 nuevos en `test_finding_superseded.py`.

## F0.4 — UI de revisión humana

Hallazgo real: `POST /review/{rc_id}/approve|reject` llaman a
`get_rc()`/`confirm_rc()` (`release_candidate_builder.py`), que buscan un
`rc_manifest.json` real en disco — una entrada `finding_review`
(`rc_id` sintético `finding-{run_id}-{req_id}`) nunca tiene uno, así que esos
endpoints devolvían 404 siempre, antes de llegar a `mark_reviewed()`. No
existía ninguna forma de decidir sobre un hallazgo vía HTTP.

Nuevo `POST /api/v1/layer9/review/findings/{rc_id}/decide` (404/409/422
reales). `review.js` renderiza por tipo (findings con evidencia/candidatos de
fusión, sin diff; RCs reales con su diff) y el fetch de diff de un RC real ya
no traga errores en silencio — tiene timeout (8s) + error visible.

Commit: `713f8a5`. Tests: 9 HTTP + 4 Playwright contra el Mission Control
real (todo el tráfico de escritura interceptado vía `page.route` — cero POSTs
reales con identidad inventada).

## F0.5 — Consistencia del informe Tier-1

- `NOT_OBSERVED_OPTIONAL` tiene bucket propio (`OPTIONAL_NOT_OBSERVED`) —
  antes cae en `NEEDS_HUMAN_REVIEW` con un mensaje que apuntaba a
  `governed_exceptions`, lista que **siempre** queda vacía para este caso
  (nunca pasa por ninguna de las 3 rutas de despacho reales de
  `chunked_engine.py`).
- `page_or_section` normalizado a un formato único (antes mezclaba
  "pag X-Y (chunk N)", "paginas 1-N (todo el documento)", etc.).
- `CROSS_REFERENCE` ahora declara el documento destino real
  (`applicability()` ya calculaba `evidence_expected_in`, se descartaba antes
  de llegar al informe).

Commit: `8a99b4e` (mismo que F0.2). Tests: 7 nuevos en `test_tier1_report.py`.

## F0.6 — Reverificación de fuentes G3

Verificado en vivo (`source_lifecycle.evaluate_registry()`, recalculando
hashes reales, no leyendo campos guardados): **la segunda reingesta
gobernada (G3) ya se había ejecutado el 2026-08-07** — las 4 fuentes
(incluyendo `ecfr_21cfr_part11`/`part211`) ya estaban
`LOCAL_CANONICAL_COPY_VERIFIED`. No había nada que descargar ni firmar en
ese eje.

Causa real de que el informe siguiera mostrando `SOURCE_PENDING_REVERIFICATION`:
`requirements.yaml` (`catalog_version: '2.1'`, generado 2026-07-17, **antes**
de la reingesta) seguía declarando `source_verification_status:
PENDING_REVERIFICATION` en las 20 entradas — nadie lo había vuelto a
sincronizar. Las 20 D2 de este catálogo ya estaban firmadas por Cesar
(2026-08-07) — pero el motivo registrado ("mejora") no cubre explícitamente
la promoción de `positive_conclusion_eligibility`, así que esa decisión NO
se tocó (elección conservadora explícita de Cesar durante la sesión).

`requirements.yaml` es un artefacto gobernado bajo `ARTIFACT_VERSION` — no se
edita a mano. La herramienta gobernada existente
(`apply_catalog_version_bump()`) solo soportaba un bump de versión SIN cambio
de contenido; se construyó una extensión angosta (no genérica, a propósito:
mismo criterio de "no fabricar código sin un caso real" citado en el propio
módulo) — `propose_catalog_source_verification_sync()` /
`apply_catalog_source_verification_sync()` — con guardia de drift de
`registry.json` entre proponer y aplicar.

**Propuesta real registrada, sin confirmar**: `ARTIFACT_VERSION-2026-018`
(`2.1 → 2.2`, sincroniza `source_verification_status` en las 20 entradas,
NO toca `positive_conclusion_eligibility`/`baseline_eligibility`/
`content_review_status`). Ver
`decision_pendiente_ARTIFACT_VERSION-2026-018.json`. **Pendiente de firma de
Cesar** — el agente nunca confirma sus propias propuestas.

Commit: `6d3584e`. Tests: 6 (función pura) + 4 (propose/confirm/apply
end-to-end).

## F0.7 — Suite + Gate 0 + commits

Ver sección "Estado final" arriba. Detalle completo en `gate0_run1_raw.log` /
`gate0_run2_raw.log`.

## Pendiente antes de F1

1. Firma de Cesar sobre `ARTIFACT_VERSION-2026-018` (F0.6) + aplicación
   (`apply_catalog_source_verification_sync("2.2", decision_instance_id="ARTIFACT_VERSION-2026-018")`).
2. Decisión de Cesar sobre si promover `positive_conclusion_eligibility` para
   las 20 requirements (eje distinto, explícitamente no cubierto por las D2
   ya firmadas).
3. Autorización de presupuesto separada para F1 (micro-validación del caso
   conocido, ~5-8 llamadas LLM) antes de ejecutar nada.
