# PAQUETE 4/K2 — listado de paquetes + panel de candidatos NCR/CAPA

Fecha: 2026-08-19. Cierra K2 (docs_plan/PAQUETE_4_UI_Y_VOCABULARIO_DISENO.md)
y el panel de UI pendiente para `governance_candidate` (Paquete 1a).

## K2 — endpoint de listado

- `factory/services/remediation_package_service.py::list_packages(project_id)`:
  camina `REMEDIATION_PACKAGES_BASE/<project_id>/*`, lee la ÚLTIMA versión
  real de cada `package_id` (`_read_state`, ya existente), nunca inventa
  un campo — solo re-expone lo que `state.json` ya tiene: `status`,
  conteos de riesgo por bucket, `automatic_evaluation_complete`,
  `human_exception_review_complete`, y `package_decision` resumido
  (`decision`/`decided_by`/`decided_at`) si ya existe. Devuelve `[]` (no
  lanza) si el proyecto no tiene paquetes todavía.
- `GET /api/v1/remediation-packages/{project_id}` (nuevo, solo lectura,
  no exige `X-Identity-Key`) → `{"packages": [...]}`, mismo formato de
  envoltorio que `GET /remediation/directives`.

## UI — dos paneles nuevos

- `factory/ui/mission_control.html` + `remediation.js`: nueva card
  "Paquetes de remediación — listado por proyecto" (input `project_id` +
  botón "Listar paquetes"), sobre la card de búsqueda manual existente
  (que se conserva, ahora también alcanzable con un clic "Ver / adjudicar"
  desde la lista).
- `factory/ui/js/mission_control/review.js`: nuevo `renderCandidateCard()`
  + `submitCandidateDecision()` para `entry_type='governance_candidate'`
  (Paquete 1a) — antes excluido del todo del panel de revisión humana
  (solo decidible por API/Swagger). El humano elige la clasificación real
  en un `<select>` (NCR/CAPA/CHANGE_CONTROL, preseleccionado con la
  sugerencia de la máquina pero nunca enviado sin que el humano confirme)
  antes de poder confirmar — igual que backend, `human_classification` es
  obligatorio para `decision=confirmed`.

## Verificación

Router: `factory/tests/test_remediation_packages_router.py` — 5 tests
nuevos (`test_list_packages_*`), 14/14 pasan (9 existentes + 5 nuevos).

UI, contra el servidor vivo real (`localhost:9000`), todas las llamadas
de escritura mockeadas vía `page.route` (cero POST reales a producción):
`factory/tests/test_paquete4_k2_ui_playwright.py`, 2/2 pasan
individualmente — confirma render del candidato + confirmación con
`X-Identity-Key` real, y render del listado + clic "Ver / adjudicar"
rellenando correctamente el formulario de búsqueda manual.

## Resultado

```
K2_LIST_ENDPOINT =             SI (GET /api/v1/remediation-packages/{project_id})
K2_UI_PANEL =                  SI (listado + drill-down al detalle existente)
GOVERNANCE_CANDIDATE_UI_PANEL = SI (renderCandidateCard + submitCandidateDecision)
TESTS =                        7 nuevos (5 router + 2 Playwright), todos pasan
CODE_CHANGED =                 5 archivos de producción (service, router, html,
                                remediation.js, review.js, main.js) + 2 de test
PRODUCTION_ENABLEMENT =        BLOCKED
```

## Siguiente paso

Mostrar diff a Cesar y esperar aprobación antes de commit. Con esto el
Bloque 3 completo (I/J/D/H, Paquetes 1, 1a, 2, 4) queda sin pendientes
de diseño conocidos — solo CHANGE_CONTROL automático sigue bloqueado por
falta de una señal real en el pipeline (no es una tarea, es un límite de
los datos actuales).
