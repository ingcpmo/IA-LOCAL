# W5 V2 — ARQ: Desbloqueo de firmas humanas (panel catalog-version G4c)

Reporte de cierre (§8) de la corrida `W5V2_ARQ_DESBLOQUEO_FIRMA_CATALOGO`.
Generado inicialmente post-hoc a partir de evidencia real (`git show`/`git
log`) de los commits `9a3cd51`, `b2c9f38`, `31cf42d` (2026-08-04), y
actualizado con el desenlace real de la firma y el apply (2026-08-05,
commits `32a60bc`, `f61c91b`, `d529e91`). **G4c queda CERRADO**: el bump
2.0→2.1 del catálogo de requisitos está aplicado, firmado y verificado.

```
W5_CURRENT_PHASE            = ARQ desbloqueo de firma (panel catalog-version G4c) — CERRADA COMPLETA (§0-§7, incluida la firma real y el apply)
W5_COMPLETED_GATES          = G1, G2, G3, G7 (roadmap A-P previo); G4c CERRADO (bump 2.0->2.1 aplicado, firmado por Cesar)
W5_OPEN_GATES               = G5/G6/G8 construidos sin firmar (bloqueados por V5 / decisiones de Cesar pendientes, ver project_w5_v2_regulatory_redesign.md); APPLICABILITY_MATRIX-2026-002 y ARTIFACT_VERSION-2026-004 siguen esperando firma humana (fuera del alcance de este panel)
CURRENT_BLOCKER              = Ninguno para G4c. El siguiente punto de decisión es de Cesar: qué de G5/G6/G8 retomar.

ROOT_CAUSE (sesión original 2026-08-04) = RC-5 (primaria) + RC-3 (secundaria), confirmadas con evidencia; RC-1 no-bug documentado; RC-2/RC-4/RC-6 descartados
  RC-5  uvicorn corría sin --reload: el bind-mount tenía código nuevo en disco pero el
        proceso servía lo cargado al arrancar. `docker restart factory-api` es la única
        forma real de que se recogiera el cambio -- este patrón SE REPITIÓ el 2026-08-05
        (ver incidente post-firma abajo), confirmando que sigue siendo el gap operativo
        más filoso de este servicio.
  RC-3  factory/ui/js/mission_control/governance.js:61 tenía "Autoriza el bump 1.0 -> 2.0"
        hardcodeado en el resumen del índice de paneles (el cuerpo del panel ya usaba
        datos reales; el índice no). Corregido en 31cf42d.
  RC-1  coverageBlock() genérico (6 paneles) muestra active_instances de toda la familia
        sin filtrar por artefacto — documentado desde G1.16 como comportamiento
        conocido, no un bug; mitigado por el bloque nuevo filtrado del panel.
  RC-2/RC-4/RC-6  descartados con evidencia: un solo store_file canónico, sin build/CDN,
        sin divergencia GET/POST confirmada.

LIVE_BACKEND_VERSION            = commit d529e91 (estado final, tras el apply)
LIVE_FRONTEND_VERSION           = governance.js sin cambios desde 31cf42d, servido con Cache-Control: no-cache vía _NoCacheStaticFiles (main.py) -- verificado byte a byte contra el proceso vivo el 2026-08-05
LIVE_ENDPOINT_PROPOSAL_ID       = ARTIFACT_VERSION-2026-006 APPLIED (verificado 2026-08-05 vía list_artifact_version_proposals() contra el proceso real reiniciado) -- -005 quedó WITHDRAWN (expiró por TTL, nunca se firmó), -001 APPLIED (bump histórico 1.0->2.0), -003 WITHDRAWN
LIVE_DOM_PROPOSAL_ID            = Coincide con LIVE_ENDPOINT_PROPOSAL_ID (lógica de validCatalogVersionProposal() en governance.js verificada campo a campo contra la respuesta real del endpoint, sin ejecutar un navegador real en esta sesión -- ver limitación abajo)
CACHE_OR_DEPLOYMENT_ISSUE       = Resuelto en 31cf42d (cache-busting estructural); RC-5 volvió a manifestarse el 2026-08-05 (ver incidente) y se resolvió operativamente con otro restart -- sigue sin resolverse ESTRUCTURALMENTE (uvicorn sigue sin --reload; cada deploy de código exige restart manual, disciplina humana, no una garantía del sistema)
STORE_SELECTION_ISSUE           = Ninguno confirmado — un solo store_file canónico (decisions_v2), sin legacy paralelo activo para este artefacto
PROPOSAL_FILTER_ISSUE           = Resuelto: GET /governance/artifact-version/proposals filtra por artifact_path exacto y status=PROPOSED/SIGNED/APPLIED/WITHDRAWN, ciclo de vida derivado, nunca declarado a mano
PROPOSAL_005_INTERNAL_CONSISTENCY = CASO A válido — confirmado con evidencia exacta en artifact_version_guard.py:83 Y en la práctica: el apply real de 2026-08-05 produjo sha256 idéntico antes/después (7ae4aaf2...), exactamente como predecía el diseño.

SOLUTION_DESIGN              = §3 completo: endpoint canónico de propuestas (artifact_version_signing.py) + UI que renderiza exclusivamente desde el endpoint (sin literales) + firma con echo-back de 6 campos byte a byte + cache-busting estructural (no-cache en /ui/**)
IMPLEMENTATION_FILES         = factory/services/artifact_version_signing.py (endpoint canónico)
                                factory/api/routes/layer9.py (2 endpoints: GET .../artifact-version/proposals, POST .../artifact-version/sign)
                                factory/ui/js/mission_control/governance.js (panel, datos vivos, echo-back)
                                factory/api/main.py (_NoCacheStaticFiles)
                                factory/scripts/ops/sign_artifact_version_proposal.py (fallback CLI)
                                factory/core/artifact_version_apply.py (propose_artifact_version_change() + apply_catalog_version_bump(), único punto de escritura de G4c)
                                factory/services/governance_service.py (fix 2026-08-05: equivalent_signed_decision() compara payload, ver incidente abajo)
                                factory/tests/test_artifact_version_signing.py, test_governance_catalog_version_playwright.py, test_governance_ui_deploy_consistency_live.py, test_sign_artifact_version_proposal_cli.py, test_governance_signature_flow_g21.py (regresión del incidente 2026-08-05)
SECURITY_CONTROLS            = Echo-back byte a byte de los 6 campos contra lo almacenado (409 proposal_mismatch), state_hash vigente (409 stale_state), identidad validada (422), duplicado (409 duplicate) -- guardia de duplicado corregida el 2026-08-05 para comparar también el payload, no solo family+type+target_set_hash
LIVE_STORE_TEST_ISOLATION    = Confirmado — todos los tests usan almacén temporal vía variable de entorno; ningún test escribió jamás en el almacén real
UI_SIGNING_PATH_READY        = Sí, y USADO: Cesar firmó por el panel real el 2026-08-05T14:37:27
SAFE_CLI_FALLBACK_READY      = Sí — cumple los 7 puntos de §6, no fue necesario usarlo (la UI funcionó tras el fix)

TESTS_FOCUSED                 = 2026-08-04: 43 tests nuevos (commit 31cf42d). 2026-08-05: +1 test de regresión (test_n14_same_target_set_different_payload_is_a_different_act, commit f61c91b) que reproduce el defecto exacto del incidente -- falla sin el fix, pasa con él
TESTS_FULL                    = 2026-08-05: 70 passed en la suite dirigida de gobernanza/firma tras el fix (2 fallos son gap de entorno preexistente del contenedor -- falta el binario `git`, sin relación con el código; el mismo gap bloqueó inicialmente el apply, resuelto ejecutándolo desde el host)
GATE_0                        = PASS
LIVE_BROWSER_VERIFICATION     = 5/5 escenarios Playwright OK el 2026-08-04 (commit 31cf42d). El 2026-08-05 NO se re-ejecutó Playwright real -- la verificación fue vía tests de integración contra el proceso HTTP real (test_governance_ui_deploy_consistency_live.py, 4/4 PASS) más comparación campo a campo de la lógica exacta de selección del panel contra la respuesta real del endpoint. Cesar mismo verificó visualmente en su navegador real y confirmó la firma.
COMMIT_SHA                    = 9a3cd51, b2c9f38, 31cf42d (2026-08-04, mecanismo) · 32a60bc (re-propuesta -006 tras expirar -005) · f61c91b (fix del defecto de idempotencia que se tragaba la firma) · d529e91 (apply real del bump 2.0->2.1)

SAFE_FOR_CESAR_TO_SIGN        = N/A -- ya firmó
EXACT_UI_ROUTE_OR_SAFE_COMMAND = N/A -- ciclo completo
NEXT_STEP_AFTER_SIGNATURE     = COMPLETADO. catalog_version = 2.1 en requirements.yaml, version_record ARTIFACT_VERSION-2026-007 aplicado, copia histórica de 2.0 congelada en versions/requirements-2.0-7ae4aaf2.yaml. Próximo paso (decisión de Cesar, no automática): evaluar G5/G6/G8 -- ver project_w5_v2_regulatory_redesign.md para el estado de cada uno.
```

## Cronología real del cierre (2026-08-05)

Lo que documentaba este reporte en su primera versión (commits del
2026-08-04) dejó `ARTIFACT_VERSION-2026-005` `agent_proposed`, esperando
la firma de Cesar. Entre esa fecha y el intento real de firma pasó lo
siguiente, en orden:

1. **`-005` expiró por TTL.** `governance_service.PROPOSAL_TTL_HOURS = 24`
   -- Cesar no llegó a firmar dentro de esa ventana y la propuesta quedó
   `WITHDRAWN` (append-only, nunca se reactiva). Sin drift real: el estado
   vivo del catálogo seguía siendo idéntico al de cuando se propuso.
2. **Re-propuesta `ARTIFACT_VERSION-2026-006`** (commit `32a60bc`), mismo
   payload exacto (2.0→2.1, mismos hashes), generada con
   `propose_artifact_version_change()` -- deriva todo del estado vivo, no
   copiado a mano. Validado en vivo (JS servido == disco, endpoint
   canónico, lógica exacta del panel) antes de avisar a Cesar.
3. **DEFECTO REAL descubierto**: Cesar intentó firmar `-006` cinco veces
   seguidas -- el endpoint respondió `201 Created` las cinco, pero el
   almacén nunca ganó un registro `human_confirmed` nuevo. Causa:
   `equivalent_signed_decision()` (el guardia que evita duplicar una firma
   por doble clic) comparaba solo `family + decision_type +
   target_set_hash`. Como `target_set_hash` solo depende del
   `artifact_path`, y ese path es el MISMO en cada bump sucesivo del
   catálogo, la firma histórica de `ARTIFACT_VERSION-2026-002` (bump
   1.0→2.0, 2026-08-01, sigue `ACTIVE`) se colaba como "vigente" para
   CUALQUIER transición posterior del mismo artefacto -- el sistema
   respondía `already_signed: true` apuntando a ella, y la firma real de
   Cesar de hoy nunca se escribía.
4. **Fix** (commit `f61c91b`): `equivalent_signed_decision()` gana un
   parámetro `payload` y exige que coincida con el de la firma vigente
   candidata (no solo family/type/target). Como D1/D2/... siempre proponen
   `payload={}`, su idempotencia sigue intacta; solo `ARTIFACT_VERSION`
   -- cuyo payload lleva la transición exacta -- deja de confundir bumps
   distintos del mismo artefacto. 1 test de regresión nuevo que reproduce
   el defecto exacto.
5. **RC-5 otra vez**: el fix en disco no bastaba -- `factory-api` corre sin
   `--reload`. Hubo que `docker restart factory-api` para que el proceso
   vivo lo recogiera (mismo patrón exacto que motivó esta corrida
   originalmente el 2026-08-04). Verificado después del restart contra el
   servidor real (4/4 tests de consistencia de despliegue en vivo).
6. **Firma real registrada**: `ARTIFACT_VERSION-2026-007`
   (`human_confirmed`, confirma `-006`, `approved_by_id=cesar`,
   `approved_by_display_name="cesar may"`, `2026-08-05T14:37:27`). Mensaje
   real del panel: *"Registrada ARTIFACT_VERSION-2026-007. No se ejecutó
   ningún efecto."* -- exactamente el texto de éxito esperado
   (`explicaFirma()`, rama `already_signed=false`): confirma que esta vez
   sí escribió, y que el apply es un paso separado y posterior, tal como
   exige §0 del plan original.
7. **Apply ejecutado** (commit `d529e91`):
   `apply_catalog_version_bump('2.1', decision_instance_id='ARTIFACT_VERSION-2026-007')`.
   Único punto de escritura de G4c, fail-closed en cada paso. Gap de
   entorno encontrado: el contenedor `factory-api` no tiene el binario
   `git`, necesario para `_freeze_historical_copy()` (congela la copia
   histórica SOLO desde `HEAD`, nunca desde el archivo vivo). Ejecutado en
   su lugar desde el host (que sí tiene `git`), contra el mismo almacén y
   los mismos archivos vía bind-mount compartido. Resultado verificado
   después dentro del contenedor: `-006` deriva a `status: APPLIED`.

## Estado final verificado

- `factory/regulatory/requirement_catalog/requirements.yaml`:
  `catalog_version: '2.1'`, hash `7ae4aaf2...` (idéntico al de 2.0 -- CASO
  A confirmado en la práctica, no solo en diseño).
- `factory/registry/artifact_versions.jsonl`: nuevo `version_record`,
  `approved_by_decision: ARTIFACT_VERSION-2026-007`.
- `factory/regulatory/requirement_catalog/versions/requirements-2.0-7ae4aaf2.yaml`:
  copia histórica de la versión 2.0 congelada desde HEAD.
- `factory/layer9/decisions/decisions_v2.jsonl`: cadena completa y
  auditable `-005 (WITHDRAWN) → -006 (agent_proposed) → -007
  (human_confirmed, confirma -006)`, sin borrar ni reescribir nada.

## Pendientes explícitos NO resueltos por esta corrida

- **G5/G6/G8** — construidos y commiteados, ninguno cerrado. G5/G6
  bloqueados además por el hallazgo de diseño de V5 (anclaje literal de
  criterios interpretativos) pendiente de decisión de Cesar.
- **`APPLICABILITY_MATRIX-2026-002`** (matriz 2.1) y
  **`ARTIFACT_VERSION-2026-004`** (golden dataset) — decisiones separadas,
  también esperando firma humana, fuera del alcance de este panel
  específico (G4c).
- **`factory-api` sin el binario `git`** — gap de entorno real que bloqueó
  el apply dentro del contenedor; se resolvió ejecutando desde el host,
  no instalando nada en el contenedor. Si se quiere que el apply corra
  siempre dentro del contenedor, hace falta decidir agregar `git` a esa
  imagen (cambio de infraestructura, no de código de la fábrica).
- **`uvicorn` sigue sin `--reload`** — RC-5 se repitió una vez más. Sigue
  siendo disciplina humana (`docker restart factory-api` tras cada cambio
  de código), no una garantía automática del sistema.
- No se ejecutó Playwright real de extremo a extremo en la sesión del
  2026-08-05 (la verificación fue por tests de integración HTTP reales +
  comparación exacta de la lógica del panel); Cesar sí verificó
  visualmente en su propio navegador y confirmó la firma real.
