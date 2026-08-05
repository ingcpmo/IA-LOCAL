# W5 V2 — ARQ: Desbloqueo de firmas humanas (panel catalog-version G4c)

Reporte de cierre (§8) de la corrida `W5V2_ARQ_DESBLOQUEO_FIRMA_CATALOGO`.
Reconstruido post-hoc a partir de evidencia real (`git show`/`git log`) de
los commits `9a3cd51`, `b2c9f38`, `31cf42d` (2026-08-04) y de
`project_w5_v2_regulatory_redesign.md`. El archivo de instrucciones
original de este plan se ejecutó directamente desde el prompt de la
sesión; este documento es el entregable §8 que esa corrida no dejó por
escrito como archivo independiente.

```
W5_CURRENT_PHASE            = ARQ desbloqueo de firma (panel catalog-version G4c) — CERRADA hasta la barrera de parada (§0-§6 completos)
W5_COMPLETED_GATES          = G1, G2, G3, G7 cerrados (roadmap A-P previo); G4c: mecanismo de firma desbloqueado y verificado, DECISIÓN aún sin firma humana
W5_OPEN_GATES               = G4c (firma real pendiente de Cesar), G5/G6/G8 construidos sin firmar (bloqueados por V5 / decisiones de Cesar, ver project_w5_v2_regulatory_redesign.md)
CURRENT_BLOCKER             = Firma personal de Cesar sobre ARTIFACT_VERSION-2026-005 — barrera de parada explícita del plan (§0), no un defecto técnico

ROOT_CAUSE                  = RC-5 (primaria) + RC-3 (secundaria), confirmadas con evidencia; RC-1 no-bug documentado; RC-2/RC-4/RC-6 descartados
  RC-5  uvicorn corría sin --reload: el bind-mount tenía código nuevo en disco pero el
        proceso servía lo cargado al arrancar. Evidencia: `docker restart factory-api`
        fue la única forma real de que se recogiera el cambio.
  RC-3  factory/ui/js/mission_control/governance.js:61 tenía "Autoriza el bump 1.0 -> 2.0"
        hardcodeado en el resumen del índice de paneles (el cuerpo del panel ya usaba
        datos reales; el índice no).
  RC-1  coverageBlock() genérico (6 paneles) muestra active_instances de toda la familia
        sin filtrar por artefacto — documentado desde G1.16 como comportamiento
        conocido, no un bug; mitigado por el bloque nuevo filtrado del panel.
  RC-2/RC-4/RC-6  descartados con evidencia: un solo store_file canónico, sin build/CDN,
        sin divergencia GET/POST confirmada.

LIVE_BACKEND_VERSION            = commit 31cf42d (efectivo tras `docker restart factory-api`, confirmado por evidencia del propio commit)
LIVE_FRONTEND_VERSION           = governance.js del commit 31cf42d, servido con Cache-Control: no-cache vía _NoCacheStaticFiles (main.py)
LIVE_ENDPOINT_PROPOSAL_ID       = ARTIFACT_VERSION-2026-005 (FROM 2.0 -> TO 2.1), confirmado por test de consistencia de despliegue en vivo del commit 31cf42d — no re-verificado en esta sesión de auditoría (requiere API key de sesión no disponible)
LIVE_DOM_PROPOSAL_ID            = ARTIFACT_VERSION-2026-005, verificado por Playwright real (Chromium) contra el backend vivo en el commit 31cf42d
CACHE_OR_DEPLOYMENT_ISSUE       = Resuelto: RC-5 (falta de --reload) corregido operativamente vía restart obligatorio tras cada cambio de código; cache-busting estructural agregado (_NoCacheStaticFiles)
STORE_SELECTION_ISSUE           = Ninguno confirmado — un solo store_file canónico (decisions_v2), sin legacy paralelo activo para este artefacto
PROPOSAL_FILTER_ISSUE           = Resuelto: GET /governance/artifact-version/proposals filtra por artifact_path exacto y status=PROPOSED; ciclo de vida derivado (PROPOSED/SIGNED/APPLIED/WITHDRAWN), nunca declarado a mano
PROPOSAL_005_INTERNAL_CONSISTENCY = CASO A válido — confirmado con evidencia exacta en artifact_version_guard.py:83: catalog_version está excluido del hash canónico por diseño; hash_before == hash_after es el comportamiento esperado de un bump de solo-etiqueta. Leyenda añadida al panel para que Cesar firme sabiéndolo.

SOLUTION_DESIGN              = §3 completo: endpoint canónico de propuestas (artifact_version_signing.py) + UI que renderiza exclusivamente desde el endpoint (sin literales) + firma con echo-back de 6 campos byte a byte + cache-busting estructural (no-cache en /ui/**)
IMPLEMENTATION_FILES         = factory/services/artifact_version_signing.py (nuevo)
                                factory/api/routes/layer9.py (+2 endpoints: GET .../artifact-version/proposals, POST .../artifact-version/sign)
                                factory/ui/js/mission_control/governance.js (panel reescrito: datos vivos, bloque "PROPUESTA SELECCIONADA" con 6 campos + STATE_HASH + leyenda CASO A, RC-3 corregido)
                                factory/api/main.py (_NoCacheStaticFiles)
                                factory/scripts/ops/sign_artifact_version_proposal.py (nuevo, fallback CLI)
                                factory/tests/test_artifact_version_signing.py (353 líneas, 27 tests unitarios/HTTP)
                                factory/tests/test_governance_catalog_version_playwright.py (260 líneas, 5 tests Playwright aislado)
                                factory/tests/test_governance_ui_deploy_consistency_live.py (111 líneas, 4 tests de consistencia de despliegue en vivo)
                                factory/tests/test_sign_artifact_version_proposal_cli.py (131 líneas, 7 tests CLI)
SECURITY_CONTROLS            = Echo-back byte a byte de los 6 campos contra lo almacenado (409 proposal_mismatch), state_hash vigente (409 stale_state), identidad validada contra lista única de principales (422), duplicado (409 duplicate); CLI exige re-tipear proposal_id + to_version + palabra de confirmación "FIRMAR"; ningún apply ejecutado en ningún camino
LIVE_STORE_TEST_ISOLATION    = Confirmado — todos los tests (unitarios, HTTP, Playwright, CLI) usan almacén temporal vía variable de entorno; interceptación de red en Playwright registra que ningún POST llegó al almacén real
UI_SIGNING_PATH_READY        = Sí — botón de firma deshabilitado hasta bloque completo cargado y verificado; motivo siempre visible; verificado en vivo con Chromium real
SAFE_CLI_FALLBACK_READY      = Sí — cumple los 7 puntos de §6 (carga exacta por proposal_id, muestra 8 campos, identidad validada, re-tipeo de confirmación, mismo validador echo-back que la UI, sin apply, sin flags de fuerza, probado con almacén temporal)

TESTS_FOCUSED                 = 43 tests nuevos en el commit 31cf42d (27 unitarios/HTTP + 7 CLI + 5 Playwright aislado + 4 consistencia de despliegue en vivo), todos verificados pasando individualmente
TESTS_FULL                    = 2133 passed, 2 failed (los 2 de siempre: bump del catálogo pendiente de firma real de Cesar — sin relación con este commit); git diff --check limpio
GATE_0                        = PASS (consistente con Gate 0 PASS=5/5 reportado en toda la serie de commits del roadmap W5 V2)
LIVE_BROWSER_VERIFICATION     = 5/5 escenarios OK vía Playwright con Chromium real contra el backend vivo (mismo que sirve la URL pública, confirmado por Caddyfile): render correcto de -005, botón deshabilitado sin propuesta válida, firma con echo-back completo, 409 mismatch renderizado, 409 stale renderizado
COMMIT_SHA                    = 9a3cd51 (fix estructural ARTIFACT_VERSION), b2c9f38 (6 campos exactos), 31cf42d (desbloqueo completo de firma)

SAFE_FOR_CESAR_TO_SIGN        = Sí — flujo listo para firma personal
EXACT_UI_ROUTE_OR_SAFE_COMMAND = https://mission-control.35-243-160-0.sslip.io/#gobierno/catalog-version (recargar con Ctrl+Shift+R) — fallback: factory/scripts/ops/sign_artifact_version_proposal.py --proposal-id ARTIFACT_VERSION-2026-005
NEXT_STEP_AFTER_SIGNATURE     = apply del bump 2.0->2.1 vía factory/core/artifact_version_apply.py bajo su propio procedimiento gobernado (fuera de esta corrida) → luego evaluar G5/G6/G8 según camino crítico
```

## Pendientes explícitos NO resueltos por esta corrida

- **Firma real de ARTIFACT_VERSION-2026-005** por Cesar — sigue `agent_proposed`.
  Es la barrera de parada del plan, no un defecto.
- **APPLICABILITY_MATRIX-2026-002** (matriz 2.1) y **ARTIFACT_VERSION-2026-004**
  (golden dataset) — decisiones separadas, también esperando firma humana,
  fuera del alcance de este panel específico (G4c).
- **G5/G6/G8** — construidos y commiteados, ninguno cerrado; G5/G6 bloqueados
  además por el hallazgo de diseño de V5 (anclaje literal de criterios
  interpretativos) pendiente de decisión de Cesar.
- Re-verificación en vivo de `LIVE_ENDPOINT_PROPOSAL_ID` en esta sesión de
  auditoría no se ejecutó (requiere API key de sesión no disponible aquí);
  el valor reportado hereda la verificación del propio commit `31cf42d`.

## Procedimiento para Cesar (§7 — dejar escrito, no ejecutar)

**H. FIRMA** (acto de Cesar, no del agente):
1. Recargar con Ctrl+Shift+R.
2. Verificar el bloque completo de la propuesta y que el `proposal_id` sea
   `ARTIFACT_VERSION-2026-005`.
3. Verificar la leyenda de hash (idéntico esperado — CASO A, bump de
   solo-etiqueta).
4. Completar motivo e identidad.
5. Firmar.
6. Confirmar el evento generado (id visible).

Si falla: copiar la línea de última acción del panel.

**I. APPLY** (posterior y separado, fuera de esta corrida): tras la firma,
el apply del bump 2.0→2.1 se ejecuta con
`factory/core/artifact_version_apply.py` bajo su propio procedimiento
gobernado, con verificación de hash posterior y evento propio.
