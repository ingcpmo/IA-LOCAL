# PAQUETE 4 — cierre parcial: E (glosario) + K1 (regresión de identidad en la UI viva)

Fecha: 2026-08-19. Autorizado por Cesar: ejecutar E y K1 ahora; K2
(listado de paquetes) queda para después.

## E — glosario de vocabulario

`docs_plan/GLOSARIO_VOCABULARIO_CLASIFICACION.md` — documenta las 4
taxonomías reales (`conclusion`, `bucket`, `status` ×3 conceptos
distintos), su dueño canónico, y la relación `conclusion`→`bucket`.
**Cero cambios de código** — el propio hallazgo E lo pide así.

## K1 — la UI viva quedó rota por mi propio cambio de Paquete 2

Confirmado en la investigación: `factory/ui/mission_control.html` (con
`factory/ui/js/mission_control/`) es la UI real, servida en `/` y
`/mission-control` (`factory/api/main.py:166-219`). `factory/ui/index.html`
es un prototipo viejo, no wireado a ninguna ruta — no es el punto de
entrada real, no se tocó.

Paquete 2 (`9f07d95`) migró 18 endpoints a exigir `X-Identity-Key`
resuelta server-side, quitando los campos de identidad del body. Nadie
actualizó la UI viva en ese momento: **si Cesar hubiera clickeado
cualquier botón de decisión en producción, habría recibido 401**.

### Fix

**`factory/ui/mission_control.html`**: nuevo campo de sesión "IDENTITY
KEY" junto a la API key existente, mismo patrón (en memoria, sin
`localStorage`).

**`factory/ui/js/mission_control/state.js`**: `state.identityKey` +
`headers()` ahora manda `X-Identity-Key` en cada petición.

**`factory/ui/js/mission_control/refresh.js`**: `connect()` lee el nuevo
input; mensaje de sesión expirada menciona ambas keys.

**Auditados y corregidos TODOS los módulos que llamaban a un endpoint
migrado en Paquete 2** (no solo `remediation.js`):

| Módulo | Endpoint(s) | Campo removido del body |
|---|---|---|
| `remediation.js` | `.../remediation-packages/.../decision` | `decided_by` |
| `missions.js` | mission approve/reject/return | `approved_by`/`rejected_by`/`returned_by` |
| `w5_decisions.js` | `POST /w5-decisions/{id}` | `approved_by` |
| `intel_views.js` | case-analysis `/decision` | `decided_by` |
| `review.js` | RC approve/reject, finding `/decide` | `approved_by`, `reviewer` |
| `validation_view.js` | doc approve, agent-proposal `/decision` | `approved_by`, `decided_by` |
| `governance.js` | confirm/reject/sign (7+ paneles vía `confirmarPropuestaExistente`/`proponerYConfirmar`/sign directo) | `approved_by_id`/`rejected_by_id` (se conserva `*_display_name`, cosmético) |

**Explícitamente NO tocados** (fuera del alcance de Paquete 2, sus
endpoints no cambiaron): `pipeline.js` (`/api/v1/layer8/headless/config`,
router distinto), `w5_decisions.js::submitW5Correction`
(`W5CorrectionBody.corrected_by`, deliberadamente fuera de Paquete 2),
`intel_views.js::runCaseAnalysis`/`promptCaseFetch` (`requested_by`/`run_by`,
no son actos de decisión), `remediation.js` directivas (solo lectura, no
crea directivas desde la UI).

Los inputs de "nombre real" que quedaron vestigiales se reemplazaron por
una nota explicando que la identidad ahora se resuelve de la IDENTITY
KEY de sesión. En `governance.js`, el campo "FIRMA — id" se simplificó a
un único campo cosmético ("nombre para mostrar") — la identidad
autorizante ya no es texto libre en ningún panel.

### Verificación

`factory/tests/test_review_queue_finding_ui_playwright.py` (Playwright,
`requires_live_ui`, todas las llamadas interceptadas con `page.route` —
cero POST reales llegan al servidor) actualizado para reflejar el nuevo
contrato: llena `#identitykey` en vez de `#finding-reviewer-*`, verifica
401 visible cuando falta la key, verifica que el body ya no lleva
`reviewer`. Se agregó un fixture separado (`pagina_sin_identidad`) para
el caso sin identidad en vez de reconectar una página ya conectada (eso
dispara `refresh('dash')` y pierde la vista + repite ~10 fetches
simultáneos).

Corrido contra el servidor vivo real (`localhost:9000`), **4/4 pasan
individualmente**. De paso se encontró y corrigió un defecto preexistente
del propio archivo de test (no de mi cambio): el fixture usa
`conclusion="PROVISIONAL_GAP"`, que cae en
`FINDING_QUOTE_NOT_APPLICABLE_CONCLUSIONS` — el botón real que renderiza
`review.js` para ese caso es "Confirmar bloqueo/ausencia", no "Confirmar
evidencia" (el texto que buscaban los 2 tests de identidad desde su
redacción original, 2026-08-12). Corriendo las 4 pruebas seguidas se
repite el rate-limit ya documentado en la cabecera del archivo desde esa
misma fecha ("espaciar las corridas") — no relacionado con el código
probado, confirmado corriendo cada test por separado.

## Resultado

```
E_GLOSSARY_WRITTEN =          SI, sin cambios de codigo
K1_REGRESSION_FIXED =         SI -- 7 modulos JS + 1 HTML corregidos
K1_ALL_MIGRATED_ENDPOINTS_AUDITED = SI (18/18 endpoints de Paquete 2,
                               verificado por grep exhaustivo de campos
                               de identidad removidos)
K1_LIVE_UI_VERIFIED =         SI -- 4/4 tests Playwright contra servidor
                               vivo real (individualmente; rate-limit
                               preexistente del servidor al correrlos
                               seguidos, no relacionado con el codigo)
K2_STATUS =                   DIFERIDO (listado de paquetes, backend+UI nuevo)
K3_STATUS =                   SIGUE PENDIENTE -- accion humana de Cesar,
                               ahora YA NO bloqueada por 401 (K1 la desbloqueo)
CODE_CHANGED =                9 archivos (1 HTML + 7 JS + 1 test) + 2 docs
PRODUCTION_ENABLEMENT =       BLOCKED
```

## Siguiente paso

Mostrar diff a Cesar y esperar aprobación antes de commit. K2 sigue en
`docs_plan/PAQUETE_4_UI_Y_VOCABULARIO_DISENO.md`, sin empezar.
