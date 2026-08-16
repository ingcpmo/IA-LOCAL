# W5 V2 — FIX: FALLO SILENCIOSO EN FIRMA DE DECISIONES (PANEL GOBERNANZA)
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/W5V2_FIX_FIRMA_SILENCIOSA.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
# Corrida de CORRECCIÓN DE UI + VERIFICACIÓN. Cambios solo en frontend/JS
# y, si aplica, en mensajes de error de endpoints (sin cambiar semántica).
#
# REGLA ABSOLUTA POST-INCIDENTE: Claude Code NO firma, NO registra y NO
# revoca ninguna decisión con ninguna identidad, ni siquiera "de prueba".
# Toda prueba contra endpoints de firma usa un entorno/flag de dry-run o
# identidades del fixture de tests, JAMÁS el backend de producción con una
# identidad inventada. El incidente claude_probe no puede repetirse.

──────────────────────────────────────────────────────────────────────────────
0. HIPÓTESIS PRIORIZADAS (verificar en este orden)
──────────────────────────────────────────────────────────────────────────────

H1 — 409 SILENCIOSO POR STATE_HASH OBSOLETO (probabilidad alta).
La sesión de Cesar quedó abierta desde antes de la revocación D2-2026-005 y
de los fixes; su state_hash quedó viejo. Cada clic → POST con hash obsoleto
→ 409 del backend (comportamiento correcto) → la rama 409 del handler JS no
renderiza nada → "el clic no hace nada". Playwright no lo reproduce porque
cada corrida carga página fresca con hash vigente.
Verificación: revisar en governance.js el handler de respuesta del POST de
firma; confirmar si la rama 409 (y la de error de red) tiene render visible
o solo console/return.

H2 — GUARD MUDO POR DRIFT "NO DETERMINABLE".
El panel muestra "drift del registry: NO DETERMINABLE". Si existe un guard
que aborta la firma cuando el drift no es determinable y hace early-return
sin feedback, el POST nunca sale. Verificación: buscar en panelPack211() y
helpers cualquier return condicionado a drift/estado sin render de mensaje.

H3 — EXCEPCIÓN JS PREVIA AL POST EN EL ENTORNO REAL.
Algo del estado real (p. ej. el bloque INCIDENTE renderizado junto al panel
normal: IDs duplicados entre panelPack211 y el panel de revocación,
listener adjuntado antes de inyectar el DOM, overlay capturando el clic)
rompe solo cuando ambos paneles coexisten — condición que quizá las pruebas
de Playwright no recrearon. Verificación: reproducir con el MISMO estado de
datos que ve Cesar (incidente visible + revocada + 4 propuestas sin firmar)
y revisar duplicidad de IDs/selectores y orden de bind de listeners.

H4 — BOTÓN DISABLED SIN INDICACIÓN VISUAL. Verificar atributo/clase.

Si Cesar aporta consola (F12) o Network del clic, priorizar esa evidencia
sobre las hipótesis.

──────────────────────────────────────────────────────────────────────────────
1. REPRODUCCIÓN DIRIGIDA (antes de cambiar nada)
──────────────────────────────────────────────────────────────────────────────

1. Test Playwright NUEVO — escenario de estado obsoleto (H1):
   a) cargar el panel (capturar state_hash A);
   b) mutar el estado por API en una segunda sesión de prueba (usar un
      cambio inocuo de fixture/entorno de test — NO firmar decisiones
      reales; si no existe mutación inocua en producción, ejecutar este
      test contra el entorno de tests);
   c) hacer clic en "Registrar aprobación" con la página vieja;
   d) EXPECTATIVA ACTUAL: el POST devuelve 409 y la UI no muestra nada →
      el test debe FALLAR hoy (documentando el bug) y PASAR tras el fix.
2. Test Playwright NUEVO — panel con incidente coexistente (H3): renderizar
   el panel con el mismo estado de datos de la captura de Cesar (incidente
   + revocada + propuestas) y verificar que el clic dispara el POST.
3. Reproducir H2 forzando drift NO DETERMINABLE y verificando si el POST
   sale o hay early-return.

Registrar cuál hipótesis se confirmó, con evidencia (archivo/línea).

──────────────────────────────────────────────────────────────────────────────
2. FIX OBLIGATORIO — CERO FALLOS SILENCIOSOS
──────────────────────────────────────────────────────────────────────────────

Independientemente de la causa raíz confirmada, aplicar TODO lo siguiente
al flujo de firma (D1, D1-A, D2/pack, revocaciones — mismo patrón):

1. TODA rama de respuesta renderiza feedback visible:
   - 2xx → confirmación con decision_instance_id/event_id;
   - 409 (state_hash/duplicado) → mensaje explícito: "El estado cambió
     desde que cargaste esta página. Recarga para ver el estado vigente y
     vuelve a revisar antes de firmar." + botón "Recargar estado" que
     refetch-ea el snapshot y el state_hash SIN recargar toda la página, y
     re-renderiza el panel. NUNCA reintentar la firma automáticamente con
     el hash nuevo: la re-firma tras un 409 es siempre un acto humano
     explícito sobre el estado ya revisado.
   - 422 (identidad) → mostrar el motivo del rechazo;
   - error de red/timeout → mensaje y estado del botón restaurado;
   - excepción JS → try/catch alrededor del handler completo con render
     del error (no solo console.error).
2. Todo guard que impida firmar (drift NO DETERMINABLE, precondiciones,
   cobertura) muestra POR QUÉ está bloqueado y qué falta, en el panel —
   prohibido el early-return mudo. Si el drift es NO DETERMINABLE,
   explicar la causa (p. ej. registry_hash no disponible) y el remedio.
3. Botón con estados visibles: habilitado / en vuelo (spinner + disabled) /
   deshabilitado con motivo en tooltip y texto.
4. Línea de estado de última acción en el panel (timestamp + acción +
   resultado), persistente en pantalla — permite depurar con Cesar a
   distancia sin abrir la consola.
5. Auto-detección de obsolescencia: al recuperar foco la pestaña (evento
   visibilitychange/focus), refetch ligero del state_hash (GET, solo
   lectura); si difiere del cargado, banner "El estado cambió — recarga
   antes de firmar" y botón de firma bloqueado con motivo hasta recargar.
6. Verificar IDs/selectores únicos entre panelPack211 y el panel de
   incidente; listeners adjuntados tras inyección del DOM; sin overlays
   capturando el clic.

Backend (solo si aplica, sin cambiar semántica): el cuerpo del 409 debe
distinguir stale_state_hash de duplicate_approval en un campo `reason`,
para que la UI muestre el mensaje correcto. GET siguen sin escribir
auditoría; POST siguen emitiendo exactamente un evento.

──────────────────────────────────────────────────────────────────────────────
3. GOBERNANZA DEL INCIDENTE claude_probe (verificar cierre)
──────────────────────────────────────────────────────────────────────────────

1. Confirmar en la suite el test de regresión de identity_policy.py:
   rechazo por PREFIJO de toda identidad reservada (claude*, capa8*,
   capa9*, agent*, system*, human*, admin*), case-insensitive, con
   variantes (claude_probe, Claude-2, CAPA9_x). Añadir las que falten.
2. Confirmar que D2-2026-003 está SUPERSEDED/REVOKED por D2-2026-005 y que
   el resolver NO le otorga cobertura (test con el caso real como fixture).
3. Confirmar que el panel ya no ofrece "Revocar" sobre cobertura no
   vigente (fix del punto 4 previo) con test.
4. Verificar que existe registro formal del incidente (RECORD_ANNOTATION-
   2026-005 o desviación DEV): agente firmó con identidad no rechazada,
   causa (match exacto vs. prefijo), corrección, prevención. Si falta
   algún elemento, completar el documento (sin tocar eventos históricos).
5. Añadir a esta política: los flujos de prueba end-to-end de firma van
   contra entorno de tests o dry-run; prohibido probar firmas reales en
   producción. Documentarlo en el spec de gobernanza UI.

──────────────────────────────────────────────────────────────────────────────
4. VERIFICACIÓN CON CESAR Y CIERRE DE TAREAS ABIERTAS
──────────────────────────────────────────────────────────────────────────────

1. Backup de frontend a backups/frontend/ antes de aplicar cambios de UI
   (los cambios de index.html/JS aplican sin restart; si se tocó
   factory-api: docker compose restart api, sin rebuild).
2. Suite completa + Gate 0 en verde. Commits separados por causa raíz:
   - fix(ui): feedback visible en todas las ramas de firma + detección de
     estado obsoleto;
   - test(ui): escenarios stale-state e incidente coexistente;
   - (si aplica) fix(api): reason en 409.
3. PROTOCOLO DE VERIFICACIÓN EN NAVEGADOR REAL (con Cesar):
   a) Cesar recarga con Ctrl+Shift+R;
   b) verifica la línea de estado del panel y el state_hash mostrado;
   c) intenta la firma real del pack 211 — si el estado está vigente, debe
      completarse con confirmación visible; si algo bloquea, el panel debe
      DECIR exactamente qué;
   d) si aún falla: la línea de estado de última acción (punto 2.4) captura
      el resultado — Cesar lo copia tal cual, sin necesidad de F12.
4. Tras la firma exitosa de Cesar, retomar las tareas abiertas EN ORDEN:
   a) cerrar fix de comparabilidad G3 (Gate 0 + commit);
   b) re-evaluar las 4 fuentes reverificadas con el fix aplicado;
   c) continuar el camino crítico (G4→G8) según el roadmap vigente, con
      checkpoint humano por cada G.

──────────────────────────────────────────────────────────────────────────────
5. CIERRE
──────────────────────────────────────────────────────────────────────────────

Bloque de estado:

```
ROOT_CAUSE_CONFIRMED = NO_CONFIRMADA_UNICAMENTE -- H2 descartada con evidencia
  (ningun guard de drift hace early-return silencioso). H1 (409/422 real
  pero el UNICO aviso era un toast que se desvanece en 2.2s) es la
  explicacion mas plausible con la evidencia disponible, no confirmada de
  forma aislada: el mecanismo funciono en 3 reproducciones independientes
  (contenedor directo, URL publica con Basic Auth real, clic Playwright) sin
  poder reproducir "clic real -> cero red" bajo control. Se aplico el fix
  de §2 completo independientemente de cual sea la causa exacta.
SILENT_FAILURE_PATHS_REMAINING = 0 (todas las ramas -- 2xx/409/422/red/excepcion
  JS -- escriben en una linea persistente ademas del toast; ver
  proponerYConfirmar/govSubmitExcepcion en governance.js)
STALE_STATE_DETECTION = implemented (checkStaleness() en focus/visibilitychange,
  banner + boton "Recargar estado", bloquea la firma ANTES del POST)
PLAYWRIGHT_STALE_STATE_TEST = passing (test_governance_ui_stale_state_playwright.py,
  2 tests, red interceptada por completo -- cero POSTs reales)
IDENTITY_PREFIX_REJECTION_TESTED = true (claude/capa8/capa9/layer8/layer9/agent(e)
  ya en 04868eb; human/admin/system añadidos hoy, 705dd44 -- 21 tests)
D2_2026_003_COVERAGE = revoked_not_resolvable (verificado con el resolver real
  sobre fixture del caso exacto, test_g3_claude_probe_incident_closure.py)
INCIDENT_FORMALLY_DOCUMENTED = true (RECORD_ANNOTATION-2026-005/006 en el
  almacen real + GOVERNANCE_UI_SPEC.md §1.2/U-9)
CESAR_REAL_BROWSER_SIGNATURE = pendiente -- protocolo §4.3 abajo
GATE_0 = PASS=4 WARN=1 FAIL=2 (ambos esperados y documentados: almacen real
  vs HEAD anterior al commit de este fix -- se resuelve al commitear, ya
  resuelto; y CONTENT_CHANGED_VERSION_SAME del catalogo por G4c pendiente,
  ajeno a este documento)
SUITE = 2036 passed, 2 skipped, 1 xfailed, 0 failed (incluye los tests nuevos
  de este documento)
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

**Commits de esta corrida** (`705dd44`, `76436ce`, `cfb262a`, `82564c0`), todos
sobre `04868eb` (el commit del incidente original). Ninguno toca
`requirements.yaml`/`conftest.py`/tests del borrador de `21_CFR_211.68(b)`,
que sigue sin commitear, pendiente de la revisión de contenido de Cesar
(sin relación con este documento).

## Hallazgo adicional tras la primera ronda (commit `a228182`)

Cesar aplicó el fix, recargó, y al intentar la aprobación real recibió "Ya
estaba firmada: D2-2026-003 por claude_probe" — la firma FABRICADA que él
ya había revocado. Dos causas reales, no una:

1. `governance_service.equivalent_signed_decision()` declaraba "vigente" a
   D2-2026-003 mirando solo `status: ACTIVE` de ESE registro — una
   REVOCATION nunca reescribe el `status` del registro que revoca (es
   append-only; la resta la hace `effective_coverage` en otro lugar).
   Corregido restando `revoked_ids` antes de declarar vigencia.
2. Con eso corregido, el resolver SEGUÍA sin autorizar un `ORIGINAL` liso
   — no es un bug, es `test_t07_revocation_wins_over_a_later_addendum`
   (`test_decision_scope_resolver.py`), una regla dura y deliberada:
   revocar domina sobre cualquier grant posterior que no la mencione, a
   propósito. La vía gobernada real es que la aprobación nueva
   **supersede la REVOCATION misma** (`CORRECTION` con
   `supersedes_instance_id: D2-2026-005`), no un `ORIGINAL` que la ignore.
   `govSubmitPack211()` ahora detecta `revoked_ids` y elige el tipo
   correcto solo.

Verificado con un test negativo dedicado que T-07 sigue protegiendo
(`test_a_plain_original_still_cannot_reclaim_a_revoked_target`). Suite
2041 passed, Gate 0 PASS=5 WARN=1 FAIL=1 (solo el G4c ya documentado — los
tests de "almacén vs HEAD" ya no aparecen).

**Estado real:** el panel ya debería permitir la firma real de Cesar sin
el falso "ya estaba firmada". Pendiente de que él lo confirme en su
navegador — mismo protocolo §4.3 de arriba.

Detenerse tras el protocolo del punto 4.3: la firma del pack es de Cesar,
no del agente.
