# R1.5 — PRODUCTIZACIÓN DE H2+H4 EN EL FLUJO REAL DE PRODUCCIÓN
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/R1_5_PRODUCTIZACION_H2H4.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
# Corrida de CORRECCIÓN MÍNIMA + VALIDACIÓN POR FLUJO REAL.
#
# Reglas duras: no R2; no Piloto 2; no corpus formal; no MarkItDown; no
# cambiar modelo; no borrar artefactos ni decisiones; no commit sin diff +
# aprobación de Cesar.
#
# PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.

──────────────────────────────────────────────────────────────────────────────
0. DIAGNÓSTICO YA CONFIRMADO (no re-diagnosticar; verificar en código)
──────────────────────────────────────────────────────────────────────────────

Brecha R1.5: el smoke de R1 corrió por el flujo real
(run_pilot_sample_batch → chunked_engine) y P5 NO ancló, pese a que el
mismo caso SÍ ancló en el script experimental h2_experiment.py/
h4_experiment.py. Causa: H2 (1 requirement_id por llamada) y H4 (schema de
salida mínimo) vivieron solo en scripts ad hoc de scratchpad (nunca
versionados); el pipeline de producción sigue empaquetando N requirements
por llamada con el schema verboso (config baseline, 0/7 medido).

Verificar en código antes de tocar (con archivo/línea):
1. Cómo empaqueta hoy evaluate_chunked() los requirements por llamada
   (¿todos los del agente en un prompt? confirmar).
2. Qué schema de salida exige hoy (los campos verbosos: criterion_text,
   evidence_location, justification, limitations).
3. Dónde están h2/h4_experiment.py (si sobreviven en scratchpad) para
   extraer la config EXACTA que midió 2/7 — prompt, empaquetado, schema.
   Si ya no existen, reconstruir la config desde
   W5V2_RECALL_EXPERIMENTS_RESULTADOS.md (§H2/§H4), que la documenta.

──────────────────────────────────────────────────────────────────────────────
1. DISEÑO DE LA CORRECCIÓN (variante configurable, no reemplazo)
──────────────────────────────────────────────────────────────────────────────

Principio: H2+H4 entra como MODO CONFIGURABLE de evaluate_chunked, NO como
cambio de comportamiento por defecto de los llamadores existentes. Esto
protege el contrato (regla de Cesar) y permite regresión limpia.

1.1 Parámetro de modo (nombre a definir, p. ej. `evaluation_profile`):
    - BASELINE (default actual, sin cambios de comportamiento para quien no
      lo pida): empaquetado N-req/llamada + schema verboso;
    - H2H4: 1 requirement_id por llamada + schema mínimo
      (criterion_index/status/evidence_quote, sin los campos verbosos).
    El perfil se registra en cada checkpoint y en el fingerprint (es parte
    de prompt_version/schema_version — un cambio de perfil invalida cache
    por diseño, igual que cualquier cambio de prompt/schema).

1.2 Empaquetado 1-req/llamada (H2): implementar dentro de evaluate_chunked
    o en una función hermana que lo envuelva SIN romper el contrato de los
    llamadores actuales. La validación A (evidence_verifier) NO cambia; el
    contrato de chunk/checkpoint NO cambia; solo cambia cuántos requirements
    van por prompt.

1.3 Schema mínimo (H4): variante configurable del schema de salida, no
    hardcodeada. El parser debe aceptar el schema mínimo cuando el perfil
    es H2H4 y seguir aceptando el verboso en BASELINE.

1.4 PROHIBICIONES (sin excepción): no aflojar validación A/C/D; no aceptar
    evidencia_exacta vacía; no bajar el umbral fuzzy; no aceptar citas no
    ancladas. La productización sube recall replicando la config medida,
    NUNCA relajando el verificador. El fix de viñetas ya en producción
    (_strip_bullet_markers) permanece intacto.

──────────────────────────────────────────────────────────────────────────────
2. TESTS (almacén temporal; antes de tocar producción real)
──────────────────────────────────────────────────────────────────────────────

- Regresión: llamadores existentes de evaluate_chunked SIN pedir perfil ⇒
  comportamiento BASELINE idéntico al actual (byte a byte en la forma del
  prompt/schema). Este test es el guardián del contrato.
- Perfil H2H4: empaqueta 1 req/llamada y emite/parsea el schema mínimo.
- El perfil se propaga al checkpoint y al fingerprint (cache invalida al
  cambiar de perfil).
- El fixture set 7P+2N sigue siendo el instrumento: preparar el arnés que
  permita correrlo por el FLUJO REAL con perfil H2H4 (no por script ad
  hoc) — la ejecución real de las llamadas se hace en el Bloque 3 bajo
  autorización, aquí solo el arnés y los tests deterministas.
- Gate 0 verde.

>>> CHECKPOINT 1: mostrar diff (motor + tests), sin commit. Suite + Gate 0.

──────────────────────────────────────────────────────────────────────────────
3. VALIDACIÓN POR FLUJO REAL — CASO P5 (la prueba mínima de Cesar)
──────────────────────────────────────────────────────────────────────────────

3.1 Presupuesto: usar la PILOT_EXECUTION que la selección determinista
    (ya implementada, _select_pilot_execution_instance) elija para RW-0005
    con presupuesto disponible. NO proponer una autorización nueva
    (aumentaría el conflicto ya conocido). Confirmar en el reporte cuál
    instancia y cuánto se consume (1 llamada).
3.2 Ejecutar EXACTAMENTE el caso P5 por el FLUJO REAL, no script ad hoc:
    RW-0005 / alcoa_plus_agent / ALCOA_CONTEMPORANEOUS / p.45, vía
    run_pilot_sample_batch, con evaluation_profile=H2H4.
3.3 Registrar todo lo estándar por llamada (run_id, model+digest,
    prompt/schema version = perfil H2H4, validación A/B/C/D, duración,
    raw_response completo persistido — el fix del cap ya aplicado o
    aplicarlo si sigue pendiente).
3.4 COMPARAR con H2+H4 experimental:
    - si ANCLA (esperado): el flujo real ahora reproduce el 2/7 medido;
      la brecha R1.5 queda cerrada; documentar la cita anclada y su página.
    - si NO ancla: NO maquillar. Investigar la diferencia residual entre
      el flujo real y el script (¿el arnés experimental normalizaba algo
      que producción no? ¿num_predict/num_ctx distinto? ¿el no-determinismo
      del modelo, ya documentado?). Reportar la causa con evidencia; la
      corrección de esa diferencia residual es el verdadero cierre de
      R1.5. Recordar el hallazgo previo: el modelo mostró no-determinismo
      a temperature=0.0 — si es eso, caracterizarlo (2-3 repeticiones del
      mismo caso) antes de concluir, dentro del presupuesto autorizado.

──────────────────────────────────────────────────────────────────────────────
4. IMPACTO EN D4-A (documentar, no ejecutar)
──────────────────────────────────────────────────────────────────────────────

H2+H4 cambia el ritmo de llamadas (más llamadas, cada una más corta — H2
midió 60 min/9 fixtures vs ~2h10m baseline; H4 2.4x más rápido aún). Anotar
que, cuando se retome cualquier corrida presupuestada, D4-A debe
recalcularse con el ritmo del perfil H2H4 (con las latencias reales del
Bloque 3). No recalcular ni proponer D4-A en esta corrida — solo dejar la
nota para no olvidarlo.

──────────────────────────────────────────────────────────────────────────────
5. ACTUALIZACIÓN DE MEMORIA DEL PROYECTO
──────────────────────────────────────────────────────────────────────────────

Actualizar la memoria del proyecto (RETOMAR AQUÍ) para reflejar:
- R1 CLOSED; R1.5 en curso/cerrado según resultado del Bloque 3;
- config H2H4 productizada como evaluation_profile (ya no en scratchpad);
- la lección estructural: NUNCA medir en script ad hoc y asumir que
  producción hereda la config — toda config ganadora se productiza y se
  valida por el flujo real ANTES de construir encima;
- dependencia registrada: R2 NO arranca hasta que R1.5 cierre con P5
  anclando por el flujo real;
- selección determinista de PILOT_EXECUTION ya implementada;
- limpieza superseding de -002/-007/-008 sigue pendiente (no urgente).
No borrar historia previa de memoria; añadir/actualizar.

──────────────────────────────────────────────────────────────────────────────
6. SKILL NUEVO — gmp-recall-pipeline
──────────────────────────────────────────────────────────────────────────────

Crear un skill de proyecto en .claude/skills/gmp-recall-pipeline/ que
encapsule el conocimiento operativo de este subsistema, para que ninguna
sesión futura repita la divergencia script-vs-producción. Contenido mínimo
del SKILL.md:
- QUÉ es el pipeline de evaluación (chunked_engine → Ollama → verificador),
  la separación 8000/9000, y dónde vive cada pieza (rutas reales).
- La config H2+H4 como evaluation_profile: qué es, por qué gana, cómo se
  invoca por el flujo real (nunca por script ad hoc).
- El fixture set 7P+2N como ÚNICO instrumento de medición; su ruta; el
  criterio de éxito (≥6/7 ∧ 2/2 ∧ schema 100%).
- La PROHIBICIÓN CENTRAL: subir recall solo del lado modelo/entrada, jamás
  aflojando A/C/D, umbral fuzzy, ni aceptando citas no ancladas. Listar
  ANNEX11_4 como test negativo obligatorio.
- La regla de gobernanza: PILOT_EXECUTION requiere firma de Cesar; usar
  la selección determinista; no proponer autorizaciones que aumenten
  conflicto.
- El estado del roadmap R0-R5 y las dependencias (R2 depende de R1.5).
- Qué está diferido (H5/H6/H7, MarkItDown, corpus formal) y su condición
  de reactivación.
Descripción del skill orientada a activarse cuando una sesión toque:
recall, chunked_engine, corpus_runner, evidence_verifier, fixture set,
evaluation_profile, PILOT_EXECUTION, o el roadmap del analizador GMP.

──────────────────────────────────────────────────────────────────────────────
7. ENTREGA
──────────────────────────────────────────────────────────────────────────────

Mostrar diffs (motor + tests + skill + memoria), sin commit. Reportar SOLO:

```
PROBLEMA CONFIRMADO:
CAUSA RAÍZ:                (H2+H4 solo en scripts ad hoc; producción en baseline)
DISEÑO DE CORRECCIÓN:      (evaluation_profile configurable, default BASELINE)
QUÉ CAMBIA:                (motor: modo H2H4; parser: schema mínimo)
QUÉ NO CAMBIA:             (validadores A/C/D, umbral, contrato baseline,
                           fix de viñetas)
VALIDACIÓN EJECUTADA:      (P5 por flujo real, instancia PILOT usada, 1 llamada)
RESULTADO COMPARADO CON H2+H4:  (ancló / no ancló + causa residual si aplica)
RIESGOS:
GIT STATUS:
DIFF RESUMEN:
MEMORY_UPDATED:
SKILL_CREATED:            (.claude/skills/gmp-recall-pipeline/)
D4A_RECALC_NOTED:         (pendiente, no ejecutado)
PENDIENTE DE APROBACIÓN:  (diff para commit; cierre de R1.5; habilitación
                          de R2 solo si P5 ancló)
```

DETENERSE. No commit hasta aprobación de Cesar. R2 NO arranca hasta que
R1.5 cierre con P5 anclando por el flujo real (o hasta que Cesar decida
explícitamente el camino si la causa residual resulta ser el
no-determinismo del modelo y no la config).

──────────────────────────────────────────────────────────────────────────────
NOTA DE EJECUCIÓN (agregada por Claude Code al guardar este archivo)
──────────────────────────────────────────────────────────────────────────────

Los dos ARQ anteriores de esta serie (ARQ_REENFOQUE_ANALIZADOR_GMP.md,
Parte B → docs_plan/ROADMAP_ANALIZADOR_GMP.md; ARQ_RESOLVER_BLOQUEO_R1.md)
declaraban el mismo patrón "Destino: docs_plan/X.md" pero nunca se
guardaron efectivamente en esa ruta -- solo se actuó sobre sus
instrucciones. Corregido aquí para R1.5. Si Cesar quiere los dos
anteriores también respaldados en disco con ese nombre, es una acción
aparte, no ejecutada todavía.
