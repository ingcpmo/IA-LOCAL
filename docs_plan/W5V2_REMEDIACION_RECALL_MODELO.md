# W5 V2 — REMEDIACIÓN POST-PILOTO 1: RECALL DEL MODELO Y RECALIFICACIÓN
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/W5V2_REMEDIACION_RECALL_MODELO.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# ──────────────────────────────────────────────────────────────────────
# STATUS: ON_HOLD / PLAN DIFERIDO — 2026-08-09
# Autorizado por: Cesar (ARQ_REENFOQUE_ANALIZADOR_GMP, Parte A.2)
# Condición de reactivación: si R2 del roadmap del analizador
# (docs_plan/ROADMAP_ANALIZADOR_GMP.md) no alcanza el criterio de recall
# (≥6/7 positivos anclados), este plan se reactiva.
#
# Clasificación de los experimentos restantes de este plan:
#   - MarkItDown / H7 → mejora auxiliar posterior de entrada documental
#     (diferido, reactivable si R2 muestra que el ruido de entrada sigue
#     pesando).
#   - H5 (modelo alternativo) → experimento posterior de modelo
#     alternativo (diferido, reactivable si R2 no resuelve el recall).
#   - H6 (no-determinismo) → caracterización posterior de no-determinismo
#     (diferido, transversal a cualquier configuración ganadora futura).
#
# CONSERVADO EXPLÍCITAMENTE (no está pausado — es patrimonio del camino
# principal, en uso por el roadmap del analizador):
#   - Configuración H2+H4 (1 requirement/llamada + schema mínimo),
#     formalizada con hash de prompt_version.
#   - Fix de viñetas de evidence_verifier (factory/regulatory/
#     evidence_verifier.py, _strip_bullet_markers) — ya en producción.
#   - Fixture set de recall 7P+2N (docs_plan/W5V2_RECALL_FIXTURE_SET_DRAFT.md)
#     — es el instrumento de medición del analizador, no un experimento.
#   - Prohibición central de la Sección 0 de este documento (nunca aflojar
#     A/C/D para inflar métricas) — sigue vigente para todo el proyecto.
#   - Mecanismo de ejecución en background para diagnósticos aislados.
# ──────────────────────────────────────────────────────────────────────
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
# CONTEXTO: Piloto 1 confirmó — pipeline correcto (extracción, chunking,
# fail-closed, control negativo ANNEX11_4 OK) pero recall 0/7 sobre
# positivos verificados a mano, con no-determinismo a temperature=0.0.
# El modelo como está configurado NO califica (prioridad 3 del Model
# Qualification Gate: falsos negativos críticos = 100%). Corpus en NO-GO.
#
# PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.

──────────────────────────────────────────────────────────────────────────────
0. PROHIBICIÓN CENTRAL (leer antes que todo)
──────────────────────────────────────────────────────────────────────────────

El problema es de RECALL DEL MODELO, no de estrictez del verificador.
PROHIBIDO "mejorar" las métricas aflojando el lado determinista:

- NO relajar la exigencia de cita anclada (validación A);
- NO aceptar checkpoints con evidencia_exacta vacía;
- NO bajar umbrales de C/D ni eliminar criterios de los packs;
- NO convertir NOT_ASSESSABLE en observed por interpretación;
- NO subir temperature "para que encuentre más".

Todo ajuste va del lado del modelo/prompt/contrato de salida. El verificador
que descartó los falsos "cumple_parcialmente sin cita" es la parte del
sistema que FUNCIONÓ — se queda intacta. Cualquier cambio que suba recall
debe demostrar simultáneamente que ANNEX11_4 sigue rechazado.

──────────────────────────────────────────────────────────────────────────────
1. PRESERVAR EVIDENCIA Y CERRAR HALLAZGOS COLATERALES
──────────────────────────────────────────────────────────────────────────────

1.1 Commitear (docs) el reporte del Piloto 1 con: la tabla 8 llamadas, el
    hallazgo 0/7, la reproducción aislada (24 min, done_reason=stop,
    NOT_ASSESSABLE×9 con el texto delante), y el hallazgo de
    no-determinismo. Sanitizado (sin raw completo si contiene texto
    Rockwell extenso; citar lo mínimo necesario).
1.2 Cap de auditabilidad: _RAW_PERSIST_MAX_CHARS=8192 en chunked_engine.py
    impidió auditar el razonamiento en la corrida real. Corregir: persistir
    el raw completo en archivo aparte por llamada (gzip, ruta del run,
    hash en el checkpoint) manteniendo el extracto de 8192 en el
    checkpoint mismo. Test. El almacenamiento es barato; la auditabilidad
    no se recorta.
1.3 Investigar la 1/8 llamada con technical_execution_failures=1
    (run_id=chunked-04c431b29c1a): causa exacta, y si es reproducible o
    transitoria. Reportar.
1.4 GOBERNANZA DEL CAMBIO DE MODELO: el piloto corrió con
    qwen2.5:7b-instruct-q4_K_M; la calificación/calibración histórica
    referencia mistral:7b-instruct-q4_K_M. Verificar en decisions_v2 y en
    los fingerprints: ¿cuándo y bajo qué decisión se cambió el modelo?
    - Si hubo decisión + recalificación: citarla.
    - Si NO la hubo: registrarlo como desviación de gobernanza (el cambio
      de modelo exige fingerprint nuevo + Golden Dataset + aprobación de
      perfil, por diseño §5/§19 de W5 V2). No revertir nada por cuenta
      propia; presentar el hallazgo a Cesar con las opciones.

──────────────────────────────────────────────────────────────────────────────
2. FIXTURE SET DE RECALL (el instrumento de medición)
──────────────────────────────────────────────────────────────────────────────

Formalizar como fixtures versionados del Golden Dataset (propuesta de
versión nueva, aprobación de Cesar como cualquier artefacto):

- POSITIVOS (7): los casos verificados a mano del Piloto 1 — audit trail
  p.45, control de acceso p.39, credenciales/calibración p.12 y p.13,
  retención de datos p.44, etc. — cada uno con: documento, página real,
  requirement_id, y el pasaje exacto que un evaluador competente debe
  anclar. Estos son los casos que el Golden Dataset NUNCA tuvo: hasta hoy
  solo había negativos (por eso la calificación previa no detectó el
  problema de recall).
- NEGATIVOS (mínimo 2): ANNEX11_4 (GAMP5 en lista de referencias) + al
  menos otro caso de weak_keyword/fuera de contexto.
- CRITERIO DE ÉXITO DE CUALQUIER CONFIGURACIÓN CANDIDATA:
  recall ≥ 6/7 positivos con cita anclada válida (A en verde)
  ∧ 2/2 negativos rechazados
  ∧ schema_valid_rate = 100%
  ∧ latencia por llamada registrada (insumo para D4-A).

Este fixture set es el instrumento único: todos los experimentos del
Bloque 3 se miden contra él, para que los resultados sean comparables.

──────────────────────────────────────────────────────────────────────────────
3. MATRIZ DE EXPERIMENTOS (una variable a la vez, en orden de costo/impacto)
──────────────────────────────────────────────────────────────────────────────

Ejecutar como diagnóstico aislado (run_context=pilot, fingerprint pilot-*,
en background según §2.5 del plan de piloto — sobrevive a SSH/Claude Code).
Presupuesto: proponer a Cesar PILOT_EXECUTION-2026-002 con tope de llamadas
(estimado: ~40-60 llamadas cortas; el fixture son 9 casos por
configuración). DETENERSE para esa firma antes de la primera llamada.

H1 — IDIOMA (la más barata; probar primero):
    El documento es inglés; el prompt/criterios/salida están en español, y
    el modelo justificó "no se menciona" sobre texto inglés presente.
    Experimento: mismo contrato pero prompt e instrucciones de evaluación
    en INGLÉS para documentos en inglés (la cita anclada es literal del
    documento, así que A no cambia). Medir recall contra el fixture.
    Nota de diseño: si H1 gana, la regla queda "el idioma de evaluación
    sigue al idioma del documento"; los artefactos de cara a Cesar/QA
    siguen en español (la reseña se redacta aparte, eso ya está separado
    en el diseño).

H2 — DESEMPAQUETADO (5 requirements/llamada → 1/llamada):
    Reduce carga cognitiva por llamada. Medir recall Y latencia total del
    fixture (multiplica llamadas; cada una debería ser mucho más corta —
    el neto puede ser favorable o no: MEDIRLO, no asumirlo).

H3 — DOS ETAPAS (extraer → evaluar):
    Etapa 1: "localiza y cita textualmente los pasajes del fragmento
    relevantes al requisito X" (tarea de extracción, fácil para un 7B).
    Etapa 2: evaluación de criterios SOLO sobre las citas ancladas de la
    etapa 1. La validación A se aplica a la cita de etapa 1. Este diseño
    además reduce el schema verboso por criterio en la llamada difícil.

H4 — SCHEMA SIMPLIFICADO:
    Reducir los campos por criterio al mínimo del diseño (MET/NOT_MET/
    NOT_ASSESSABLE + anclaje), moviendo la verbosidad explicativa a una
    llamada posterior solo para los criterios que lo requieran.

H5 — MODELO ALTERNATIVO (solo si H1-H4 no alcanzan el criterio de éxito):
    Candidatos DENTRO del hardware real (4 vCPU / ~16 GB RAM, CPU):
    mistral:7b-instruct (el calificado originalmente), llama3.1:8b-q4, u
    otro 7-8B disponible. Un 14B en q4 probablemente no cabe con los
    stacks corriendo — verificar RAM libre real antes de intentarlo.
    Cualquier candidato se mide contra el MISMO fixture. El cambio de
    modelo definitivo exige el circuito completo de gobernanza (1.4).

H6 — CARACTERIZACIÓN DE NO-DETERMINISMO (transversal):
    Para la configuración ganadora: repetir el fixture completo 3 veces
    idénticas (mismo seed si el provider lo soporta; fijar num_thread si
    aplica). Reportar tasa de acuerdo entre corridas por caso. Si la
    variabilidad persiste (esperable en CPU cuantizado): documentarla como
    limitación conocida del perfil del modelo y evaluar si el diseño
    necesita mitigación (p. ej. los casos frontera inestables caen a
    SUPPORTING_EVIDENCE_UNDER_REVIEW en vez de a un estado firme) — eso es
    consistente con el principio "la LLM propone, el determinista decide",
    y es preferible a fingir reproducibilidad que el hardware no da.

Disciplina: UNA variable por experimento; combinar solo lo que
individualmente demostró ganancia; registrar cada corrida con su
configuración exacta (prompt_version nueva por variante, hash del prompt).

──────────────────────────────────────────────────────────────────────────────
4. CIERRE DEL CICLO: RECALIFICACIÓN Y RECÁLCULO
──────────────────────────────────────────────────────────────────────────────

Cuando una configuración alcance el criterio de éxito del Bloque 2:

4.1 RECALIFICACIÓN FORMAL: correr el Golden Dataset completo (negativos
    históricos + los nuevos positivos de recall) con la configuración
    ganadora. El gate de calificación ahora incluye PISO DE RECALL como
    métrica bloqueante — corregir el gate para que una configuración con
    recall bajo no pueda volver a calificar (el hueco por el que pasó la
    actual).
4.2 RECÁLCULO DE D4-A: la configuración ganadora cambia llamadas y/o
    latencia (especialmente H2/H3). Recalcular compute_d4a() con el ritmo
    medido de la configuración final (p50/p95 del fixture + calibración) y
    preparar la propuesta D4-A que corresponda. Las propuestas previas
    (D4-2026-003 vigente, D4-2026-004 propuesta) quedan como historia; la
    nueva referencia su motivo ("configuración de modelo/prompt cambió
    tras hallazgo de recall del Piloto 1").
4.3 FINGERPRINT: prompt_version/schema/modelo nuevos ⇒ fingerprint nuevo;
    cache del piloto anterior inválido por diseño. Verificar.
4.4 RE-CORRER EL PILOTO 1 con la configuración final (las mismas 8 llamadas
    de composición, ahora con la configuración calificada) — el criterio
    GO/NO-GO original del plan de piloto se evalúa recién ahí. Piloto 2
    (cadena completa) queda EN ESPERA hasta que Piloto 1 pase.

──────────────────────────────────────────────────────────────────────────────
5. REPORTE Y DECISIÓN DE CESAR
──────────────────────────────────────────────────────────────────────────────

Entregable: RECALL_REMEDIATION_REPORT.md con:
- tabla de experimentos H1-H6: configuración, recall X/7, negativos 2/2,
  schema_valid, latencia p50/p95, acuerdo entre corridas;
- recomendación de configuración final con su justificación;
- hallazgo de gobernanza 1.4 (cambio de modelo) con opciones;
- D4-A recalculada (borrador de propuesta, sin registrar hasta que Cesar
  la pida);
- costo total del ciclo de remediación en llamadas/horas vs. el ahorro
  (80-94h de corpus que habría fallado).

Bloque de estado:

```
PILOT1_ROOT_CAUSE = MODEL_RECALL_LIMITATION (pipeline verificado correcto)
DETERMINISTIC_VALIDATORS_UNCHANGED = true
RAW_AUDIT_CAP_FIXED =
TECH_FAILURE_1OF8_EXPLAINED =
MODEL_CHANGE_GOVERNANCE =            (decisión citada | desviación registrada)
RECALL_FIXTURE_SET_VERSION =
PILOT_EXECUTION_2026_002_SIGNED =
EXPERIMENTS_RUN =                    (H1..Hn con resultados)
WINNING_CONFIGURATION =              (o NINGUNA_ALCANZA_CRITERIO)
RECALL_FINAL =                       X/7
NEGATIVES_STILL_REJECTED =           2/2
NONDETERMINISM_CHARACTERIZED =
REQUALIFICATION_STATUS =
D4A_RECALC_DRAFT_READY =
PILOT1_RERUN_RESULT =                (pendiente hasta recalificación)
PILOT2_STATUS = ON_HOLD
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

Si NINGUNA configuración 7-8B en CPU alcanza el criterio de éxito:
reportarlo con honestidad como límite de hardware — la decisión entre
esperar GPU (Llama 3.1 70B ya era el objetivo de upgrade), aceptar un
alcance reducido, o usar un proveedor externo autorizado, es de Cesar y
de nadie más. No maquillar un recall insuficiente para avanzar.

DETENERSE: tras la firma de PILOT_EXECUTION-2026-002 los experimentos
corren en background; el reporte final espera la decisión de Cesar.
