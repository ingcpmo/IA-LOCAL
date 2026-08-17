# CONTINUACIÓN — VERIFICACIONES PREVIAS AL COMMIT DE M0 + CORRECCIÓN
# DE LA ENMIENDA ARQUITECTÓNICA CON EL RESULTADO REAL DE V0
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/CONTINUACION_V0_M0_VERIFICACION.md
Crea la carpeta docs_plan/CONTINUACION_V0_M0_VERIFICACION.md y copia todo este contenido en la carpeta creada
# Ejecutar: cd /home/ing_cpmo && claude (o en el entorno real donde vive
# el despliegue — ver bloque 0, verificar primero que es el mismo)
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
# V0 y M0 ya ejecutados y reportados. Esta corrida NO repite ninguno de
# los dos — cierra verificaciones pendientes antes de aprobar el commit
# de M0, y corrige la narrativa de la enmienda arquitectónica con el
# resultado real de V0.
#
# PRODUCTION_ENABLEMENT = BLOCKED. Sin cambio hasta cierre de este bloque.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 0 — CONFIRMAR IDENTIDAD DEL REPOSITORIO (antes de cualquier otra cosa)
──────────────────────────────────────────────────────────────────────────────

El reporte de V0 identifica el repositorio como `ingcpmo/hotelbot`, rama
`gmp-ai-factory-server`. Las reglas del proyecto marcan explícitamente
`hotelbot-*` como namespace de contenedores AJENO y prohibido de tocar.

0.1 Confirmar con evidencia que esto es una coincidencia de nombre
    histórico (el repo se llama `hotelbot` mais aloja el código real de
    GMP AI Factory bajo `factory/`, `app/`, etc. — ya verificado en el
    contenido) y NO una confusión de entorno o de checkout.
0.2 Confirmar que el commit `77cf8d6...` y la rama
    `gmp-ai-factory-server` son efectivamente los que corresponden al
    servidor real de producción (`ing_cpmo@ivr-ia`) — no un clon o fork
    en una VM de auditoría separada, salvo que esa separación sea
    intencional (en cuyo caso documentarla explícitamente: ¿este trabajo
    corrió en una VM de staging/auditoría distinta del servidor real?).
0.3 Si hay CUALQUIER ambigüedad sobre si esta VM es el servidor real:
    DETENERSE y reportarlo antes de continuar. No asumir.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 1 — VERIFICACIÓN OPERATIVA CRÍTICA: FAIL-CLOSED NO DEBE TUMBAR PRODUCCIÓN
──────────────────────────────────────────────────────────────────────────────

M0.1 cambia `verify_api_key`/arranque a fail-closed. Nadie verificó
todavía si el entorno de despliegue REAL tiene `FACTORY_API_KEY` y
`GMP_API_KEY` configuradas hoy. Si no lo están, el próximo restart tumba
el servicio.

1.1 En el entorno de despliegue real (no en la VM de auditoría si son
    distintos, ver Bloque 0): verificar que `FACTORY_API_KEY` y
    `GMP_API_KEY` están efectivamente definidas y no vacías en el
    `.env`/entorno que usan los contenedores `factory-api` y `gmp-api` en
    ejecución (`docker exec factory-api env | grep FACTORY_API_KEY`,
    equivalente para `gmp-api`).
1.2 Si AMBAS están configuradas: registrar la confirmación (sin exponer
    el valor) — el commit de M0 es seguro de desplegar.
1.3 Si ALGUNA falta: NO proponer el commit todavía. Reportar a Cesar
    como bloqueante — la variable debe configurarse en el entorno real
    ANTES de que este cambio se commitee y el servicio se reinicie, o el
    commit debe esperar a coordinarse con esa configuración.
1.4 Esta verificación es la única condición nueva para aprobar el commit
    de M0 — todo lo demás en el reporte ya está bien evidenciado.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 2 — DIFF COMPLETO DE LOS AJUSTES DE TESTS (transparencia total)
──────────────────────────────────────────────────────────────────────────────

El reporte M0.5 describe 35 monkeypatches ajustados en 5 archivos + 1
fingerprint legacy, con la afirmación "ninguna aserción de comportamiento
se modificó". Antes de aprobar el commit:

2.1 Mostrar el `git diff` completo (no el resumen) de los 5 archivos de
    test modificados por el ajuste de `show_digest`.
2.2 Confirmar línea por línea que el único cambio es el valor de retorno
    del monkeypatch (`None`→`"sha256:fake-digest"` o equivalente) y que
    ningún `assert` cambió de forma.
2.3 Mostrar el diff del fingerprint legacy ajustado en
    `test_gmpai_chunked_engine.py` con la explicación de por qué preserva
    la intención original del test.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 3 — REGISTRAR EL TEST FLAKY (higiene de Gate 0)
──────────────────────────────────────────────────────────────────────────────

`test_new_managers.py::TestTestExecutionManager::{test_failing_tests,
test_passing_tests}` fue confirmado flaky (pasó en corrida directa, falló
en Gate 0 a la misma revisión). Documentarlo formalmente — no dejarlo como
observación de un solo reporte:

3.1 Añadir marca `@pytest.mark.flaky` o anotación equivalente del proyecto,
    o registrarlo en la documentación de Gate 0 como caso conocido, con
    la causa si es identificable (orden de ejecución, estado compartido,
    timing).
3.2 Sin esto, la próxima persona que audite Gate 0 redescubre el mismo
    misterio desde cero.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 4 — CORRECCIÓN DE LA ENMIENDA ARQUITECTÓNICA CON EL RESULTADO REAL DE V0
──────────────────────────────────────────────────────────────────────────────

Actualizar `GMP_AI_FACTORY_ENMIENDA_PALANCA_A_Y_PLAN_IMPLEMENTACION.md`
(o el documento vigente) con los hallazgos reales de V0 — esto lo redacta
Claude Code citando V0 directamente, no se re-deriva:

4.1 **Downgrade de confianza en P-1 dentro de este entorno.** El reporte
    debe decir explícitamente: *"P-1 (truncamiento) está documentado en el
    postmortem de la corrida `fsv12_reeval_20260727` y en el informe de la
    campaña de validación (L4), pero sus artefactos crudos no son
    verificables en este repositorio — los de L4 se perdieron con el
    reinicio de la VM (`/tmp`); los de fsv12 viven fuera del repo. Dentro
    de los 187 chunk-executions persistidos y auditados en V0: CERO
    truncamientos. La corrección de M1 (presupuesto de salida dimensionado)
    se mantiene porque es barata y correcta por diseño independientemente
    de su magnitud histórica — pero no se sostiene ya como 'confirmada
    dentro de este entorno', sino como 'documentada narrativamente,
    corrección preventiva de bajo costo'."*
4.2 **Upgrade de confianza en P-3 (techo semántico).** V0 aporta evidencia
    directa nueva: 158 respuestas reales completas (`stop`), la mayoría
    (140+104=244 en total BASELINE+H2H4) `evidencia_insuficiente` sin
    ningún corte de por medio. Esto refuerza — con datos de este mismo
    repo, no solo con Palanca A — que el problema dominante es de juicio
    semántico, no de presupuesto de salida. **V2b (rediseño de contrato en
    dos pasos) sube de prioridad relativa frente a M1.**
4.3 Corregir la imprecisión terminológica ya señalada por el propio equipo:
    en toda mención futura, BASELINE = 0/7, H2H4 = 2/7 (nunca "BASELINE
    2/7").
4.4 Mantener M1 en el plan (sigue siendo correcto por diseño y muy barato)
    pero re-etiquetar su justificación de "elimina un defecto confirmado"
    a "corrección preventiva de bajo costo sobre un defecto documentado
    pero no reproducible en este entorno".

──────────────────────────────────────────────────────────────────────────────
BLOQUE 5 — SECUENCIA DE APROBACIÓN
──────────────────────────────────────────────────────────────────────────────

5.1 Presentar a Cesar: resultado del Bloque 0 (identidad del repo),
    resultado del Bloque 1 (env vars confirmadas o bloqueante), el diff
    del Bloque 2, y el registro del Bloque 3.
5.2 Si Bloque 1 confirma que las keys están configuradas Y Bloque 0 no
    encuentra ambigüedad de entorno: proponer el commit de M0 tal como
    está (sin cambios de código adicionales — los 4 bloques de arriba son
    verificación y documentación, no modificación del diff ya mostrado).
5.3 DETENERSE para la aprobación explícita de Cesar sobre el commit.
5.4 Tras el commit (y solo entonces): confirmar que
    `test_runtime_identity` pasa (era el único fallo "nuevo", esperado que
    se resuelva al commitear).
5.5 M1 no arranca en esta corrida — queda propuesto con su justificación
    ya recalibrada (Bloque 4.4), pendiente de autorización separada de
    Cesar, mismo protocolo de todas las fases anteriores.

──────────────────────────────────────────────────────────────────────────────
ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
REPO_IDENTITY_CONFIRMED =      (sí, coincidencia de nombre / hay ambigüedad)
ENV_VARS_PRODUCTION =          (FACTORY_API_KEY y GMP_API_KEY confirmadas
                               configuradas / bloqueante reportado)
TEST_DIFF_REVIEWED =           (5 archivos, línea por línea, sin cambios
                               de aserción confirmado)
FLAKY_TEST_DOCUMENTED =        (marca o registro añadido)
AMENDMENT_CORRECTED =          (P-1 downgrade, P-3 upgrade, terminología
                               BASELINE/H2H4 corregida)
M0_COMMIT =                    (pendiente de aprobación de Cesar / aprobado)
M1_STATUS =                    propuesto, no autorizado
CODE_CHANGED_THIS_RUN =        0 (solo verificación + documentación +
                               marca de test flaky)
PRODUCTION_ENABLEMENT =        BLOCKED
```

DETENERSE tras el Bloque 5.3. El commit de M0 y la autorización de M1 son
las dos decisiones que esperan a Cesar — ninguna se ejecuta sin su firma
explícita.

──────────────────────────────────────────────────────────────────────────────
ADENDA — RESULTADO REAL DE ESTA CORRIDA (2026-08-17)
──────────────────────────────────────────────────────────────────────────────

Corrida ejecutada por Claude Code (Capa 8) contra `/home/ing_cpmo`
(`ing_cpmo@ivr-ia`, rama `main` == `origin/gmp-ai-factory-server`,
commit `77cf8d6`, árbol limpio).

**BLOQUE 0 — CERRADO.** Sin ambigüedad de entorno: hostname `ivr-ia`,
contenedores `gmp-api`/`factory-api`/`gmp-postgres`/`gmp-redis`/`aria-*`/
`hotelbot-*` corriendo según lo esperado. `hotelbot` es solo el nombre
histórico del repo — confirmado, no confusión de checkout.

**BLOQUE 1 — CERRADO (verificación independiente, sin depender de M0).**
`FACTORY_API_KEY` (48 chars) y `GMP_API_KEY` (64 chars) confirmadas
definidas y no vacías en `factory-api` y `gmp-api` en ejecución. Si M0
llega a implementarse con fail-closed, no tumbaría el servicio con la
configuración actual.

**BLOQUES 2, 3, 4 — NO EJECUTABLES. El trabajo de M0/V0 se perdió.**
Búsqueda exhaustiva en este entorno (git log completo, reflog, stash,
branches remotas tras `fetch --prune`, worktrees, filesystem completo por
otros `.git`) no encontró el commit/diff de M0, el documento de enmienda
arquitectónica, ni los artefactos crudos de V0. Se localizó un segundo
checkout en `/home/ing_cpmo/hotelbot/.git`, pero pertenece a un proyecto
no relacionado (ARIA IVR/Asterisk, rama `claude/aria-ivr-local-ai-ESUTL`)
y está fuera de alcance (`hotelbot-*` prohibido de tocar). No hay sesión
de Claude Code alcanzable (`ListAgents` → ninguna). Cesar confirmó
explícitamente: el trabajo no fue empujado a ningún remoto y no es
recuperable — se da por perdido.

No se fabricó contenido para los Bloques 2-4 (diff de tests, marca de
test flaky, corrección de la enmienda con cifras de V0) porque hacerlo
sin la fuente real violaría la regla de evidencia anclada del proyecto.

**Nota de seguridad no relacionada:** al inspeccionar el checkout
`/home/ing_cpmo/hotelbot/`, su remote `origin` tenía un GitHub PAT en
texto plano embebido en la URL. Reportado a Cesar fuera de este documento;
pendiente de rotación por su parte.

```
ENTREGA FINAL DE ESTA CORRIDA
REPO_IDENTITY_CONFIRMED =      sí, coincidencia de nombre, sin ambigüedad
ENV_VARS_PRODUCTION =          confirmadas (FACTORY_API_KEY, GMP_API_KEY)
TEST_DIFF_REVIEWED =           N/A — artefactos de M0 no recuperables
FLAKY_TEST_DOCUMENTED =        N/A — artefactos de M0 no recuperables
AMENDMENT_CORRECTED =          N/A — artefactos de V0 no recuperables
M0_STATUS =                    BLOCKED — trabajo perdido, requiere re-run
                               completo en una sesión nueva
M1_STATUS =                    no arranca (dependía de M0)
CODE_CHANGED_THIS_RUN =        0
PRODUCTION_ENABLEMENT =        BLOCKED
```

Próximo paso: re-ejecutar V0 y M0 desde cero en una sesión que persista
sus cambios (commit local como mínimo, push recomendado) antes de cerrar
la sesión. Pendiente de que Cesar autorice ese re-run.
