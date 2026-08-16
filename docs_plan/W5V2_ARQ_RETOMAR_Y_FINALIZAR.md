# W5 V2 — ARQ: RETOMAR Y FINALIZAR LA EJECUCIÓN PENDIENTE
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/W5V2_ARQ_RETOMAR_Y_FINALIZAR.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
# Corrida de EJECUCIÓN GOBERNADA con checkpoints. Claude NO firma, NO
# confirma y NO impersona al aprobador bajo ninguna identidad (regla
# permanente post-incidente claude_probe). Toda prueba de firma va contra
# almacenes temporales.
#
# PRODUCTION_ENABLEMENT = BLOCKED. REGULATORY_COMPLIANCE = NOT_DETERMINED.

──────────────────────────────────────────────────────────────────────────────
0. VALIDACIÓN EN VIVO DEL ESTADO REAL (no UI, no memoria)
──────────────────────────────────────────────────────────────────────────────

Verificar contra artefactos y código, con evidencia por ítem:

1. Gates G1–G8: leer governance_service.py post-fix (a212b69/ea64fe5) y el
   cálculo real de blocked_by de cada gate. Confirmar que NINGÚN gate
   conserva valores decorativos/hardcodeados (grep de literales de estado).
2. decisions_v2.jsonl: decisiones vigentes por familia (D1, D2 ×14+,
   APPLICABILITY_MATRIX-2026-006, ARTIFACT_VERSION firmadas, golden
   dataset), y confirmación de que NO existe ARTIFACT_VERSION para
   applicability_matrix.yaml.
3. sources/registry.json: estado exacto de las 4 fuentes
   (2 VERIFIED_AGAINST_PRIOR_KNOWN_HASH; 2 FIRST_INGESTION_...).
4. guard_report()/evaluate_registry(): salida completa actual; confirmar
   VERSION_CHANGED_WITHOUT_DECISION de la matriz y cualquier otro FAIL.
5. Evidence Packs: 15/20 con D2 vigente; los 5 sin D2 y su V9; estado real
   de criterios de 21_CFR_211.68(b) (el reporte dice 0 aprobados como
   predicate — verificar qué significa exactamente en código y si contradice
   la D2-2026-009 previa; si hay contradicción, documentarla con evidencia).
6. Matriz 2.2, catálogo 2.1, Golden Dataset: versión + hash + decisión que
   los aprueba (invariante hash⇔versión⇔decisión).
7. Cron/vigilancias: confirmar 0 jobs (el watch b2015a57 murió con la
   sesión).
8. Suite + Gate 0 actuales como línea base de la corrida.

>>> CHECKPOINT 0: tabla de diagnóstico en cuatro columnas:
>>> CERRADO | BLOQUEADO | CAUSA RAÍZ | REQUIERE (corrección técnica vs.
>>> decisión/firma humana). Continuar sin pausa al Bloque 1.

──────────────────────────────────────────────────────────────────────────────
1. DESBLOQUEO DE LA CASCADA — SEGUNDA REVERIFICACIÓN DE FUENTES (G3)
──────────────────────────────────────────────────────────────────────────────

La cascada (G3 → 5 D2 → pack final → D4-A → G8) cuelga del ámbar de
ecfr_21cfr_part11 y ecfr_21cfr_part211.

1.1 EVALUAR SI ES ACCIONABLE HOY: una segunda re-ingesta gobernada —
    descarga desde la URL oficial primaria, fuera de inferencia, comparando
    el hash de la nueva descarga contra el hash de la primera ingesta —
    constituye la "segunda observación real" que source_lifecycle.py exige
    para VERIFIED_AGAINST_PRIOR_KNOWN_HASH. Verificar en código si existe
    impedimento de diseño real (intervalo mínimo, precondición, etc.):
    - SI EXISTE impedimento: citarlo (archivo/línea) y presentar a Cesar el
      paquete de decisión con las alternativas (esperar el plazo / decisión
      de diseño que lo ajuste, con pros/contras).
    - SI NO EXISTE impedimento: preparar el procedimiento de segunda
      re-ingesta como PAQUETE DE AUTORIZACIÓN para Cesar (DEC-B): fuentes,
      URLs oficiales, hash previo esperado, script gobernado a usar
      (reverify_governed_sources.py o el que corresponda — si ninguno de
      los 3 scripts existentes puede ejecutar esta transición, diseñar la
      extensión mínima del script gobernado, con test en almacén temporal,
      SIN tocar el campo a mano).
1.2 REGLA DURA: el estado de la fuente solo cambia por la re-ingesta real
    con hash coincidente. Hash divergente ⇒ PENDING_REVERIFICATION +
    reporte (el contenido oficial cambió; eso es hallazgo, no error).
1.3 Ejecutar la re-ingesta SOLO tras la autorización de Cesar (firma
    DEC-B). Después: verificar que registry.json refleja
    VERIFIED_AGAINST_PRIOR_KNOWN_HASH para ambas y que V9 de los 5 packs
    pasa a verde.

>>> CHECKPOINT 1: DETENERSE con el paquete DEC-B listo para Cesar (o el
>>> impedimento demostrado). No continuar Bloques 2–3 hasta su decisión,
>>> EXCEPTO el Bloque 4 (fixes técnicos independientes), que puede avanzar.

──────────────────────────────────────────────────────────────────────────────
2. COBERTURA ARTIFACT_VERSION DE LA MATRIZ (G6) — PAQUETE DEC-A
──────────────────────────────────────────────────────────────────────────────

2.1 Presentar a Cesar las tres opciones del hallazgo, con evidencia,
    esfuerzo y riesgo de cada una, y UNA recomendación fundamentada:
    (a) agregar applicability_matrix.yaml como target válido de la familia
        ARTIFACT_VERSION;
    (b) declarar target_registry para esa familia (targets extensibles por
        datos — consistente con el principio "sin tuplas cerradas");
    (c) que G4/G6 lean fail_count directamente.
    Nota de diseño: (b) es la opción alineada con el modelo extensible de
    decisiones ya adoptado; justificar si la recomendación difiere.
2.2 Tras la decisión de Cesar: implementar el mecanismo elegido (tests en
    almacén temporal) y preparar la propuesta de REGULARIZACIÓN del bump
    2.1→2.2 que ENLACE la firma ya existente
    (APPLICABILITY_MATRIX-2026-006) como fundamento humano del cambio —
    sin re-firmar contenido ya firmado, sin reescribir históricos, dejando
    el episodio documentado como hallazgo de diseño corregido.
2.3 La propuesta de regularización la firma Cesar en el panel correcto
    (echo-back completo). Tras la firma: G6 debe pasar a verde por cálculo
    real del guard, no por excepción manual.

>>> CHECKPOINT 2: DETENERSE con DEC-A listo. Tras firma de Cesar, verificar
>>> sincronía (Bloque 5) y continuar.

──────────────────────────────────────────────────────────────────────────────
3. CADENA POST-DESBLOQUEO: 5 D2 → PACK FINAL → D4-A → G8
──────────────────────────────────────────────────────────────────────────────

Ejecutar EN ORDEN, solo cuando el Bloque 1 esté cerrado (fuentes verdes):

3.1 Proponer las 5 D2 restantes (21_CFR_11.10(a)/(d)/(e)/(g),
    21_CFR_11.50_11.70) con V9 en verde. Firma: Cesar, una a una o en el
    lote que el panel soporte, con echo-back. DETENERSE para cada firma.
3.2 Cerrar el estado de criterios de 21_CFR_211.68(b) según lo hallado en
    0.5: si faltan criterios por aprobar, preparar el paquete de revisión
    para Cesar; si la contradicción era de reporte, corregir el reporte.
3.3 Con el pack final congelado: calcular D4-A con
    corpus_budget_formula.py (max_calls, runtime min/likely/max, hard
    stops, checkpoint_mode=per_document, resume_fingerprint_required=true).
    Presentar D4-A como paquete de firma. DETENERSE.
3.4 G8 — retirada de escritores legacy (w5_human_decisions.py /
    w5_decisions.js): SOLO después de D4-A calculada y firmada (checkpoint
    humano intencional del diseño). Retirar con: tests de que ninguna ruta
    de escritura legacy queda alcanzable; decisions_v2 como único
    escritor; commit separado.

──────────────────────────────────────────────────────────────────────────────
4. CORRECCIONES TÉCNICAS INDEPENDIENTES (pueden avanzar en paralelo)
──────────────────────────────────────────────────────────────────────────────

4.1 VIGILANCIA PERSISTENTE del origen: recrear el watch de
    official_origin_status de Part 11/Part 211 como tarea PERSISTENTE
    (cron del sistema o systemd timer, no session-only), fail-closed, que
    solo LEE y alerta (jamás escribe estados). Documentar en scripts/ops/.
4.2 status.sh del GMP Copilot base: corregir para que envíe X-API-Key
    leyéndola del entorno/archivo de config con permisos 600 — NUNCA
    hardcodeada en el script ni impresa en la salida. Resultado esperado:
    PASS=17 reflejando el estado real. (Es el único cambio permitido en el
    stack base: un script de diagnóstico; cero cambios a app/ o
    contenedores.)
4.3 Panel D2-A "devolver con comentario"/"rechazar": es brecha de modelo
    de datos (registro de propuesta por-pack inexistente). NO implementar
    ahora: documentar como ítem W6 con su diseño mínimo, SALVO que el flujo
    de los 5 packs restantes (3.1) lo requiera — en ese caso, presentar a
    Cesar la disyuntiva antes de implementar.
4.4 Pendientes del plan FIX_FIRMA_SILENCIOSA no ejecutados: dado que Cesar
    ya firmó 14 D2 reales (2026-08-05), auditar qué puntos de ese plan
    siguen sin aplicar (feedback en todas las ramas, línea de última
    acción, detección de estado obsoleto en TODOS los paneles de firma) y
    aplicarlos a los paneles que se usarán en 3.1/3.3 — que las próximas
    firmas de Cesar ocurran con el estándar completo de cero fallos
    silenciosos.

──────────────────────────────────────────────────────────────────────────────
5. VERIFICACIÓN DE SINCRONÍA TRAS CADA FIRMA HUMANA
──────────────────────────────────────────────────────────────────────────────

Después de CADA firma de Cesar, verificar la cadena completa y reportarla:

```
UI (panel muestra la decisión con su event_id)
→ backend (POST emitió exactamente 1 evento)
→ decision store (decisions_v2 contiene el registro con approved_by real)
→ resolver (otorga la cobertura esperada; test puntual)
→ gate (el gate dependiente recalcula y cambia de estado por cálculo real)
```

Si cualquier eslabón no refleja la decisión: DETENER la secuencia de
firmas, corregir el flujo con test de regresión, y solo entonces continuar.
Prohibido "compensar" a mano un eslabón roto.

──────────────────────────────────────────────────────────────────────────────
6. SECUENCIA HACIA CORPUS Y DOCUMENTOS FINALES (aclaración de alcance)
──────────────────────────────────────────────────────────────────────────────

Los "documentos finales" (candidato corregido, redline, informe de
hallazgos, trazabilidad, reseña con fuente regulatoria exacta) NO se
generan al cerrar gates: son PRODUCTO de la corrida gobernada del corpus.
Orden inviolable:

  gates G1–G8 verdes por cálculo real
  → D4-A firmada
  → AUTORIZACIÓN DE CORPUS de Cesar (decisión separada, con fingerprint)
  → corrida gobernada (batches, checkpoints, fail-closed, A/B/C/D)
  → hallazgos/gaps/desviaciones consolidados
  → remediación y generación del paquete completo por documento
    (candidato, redline, informe, matriz, reseña, excepciones, manifest,
    revalidación, calidad — según el diseño W5 V2)
  → paquete final a QA-HUM.

En ESTA corrida: llegar hasta dejar todo listo para la autorización de
corpus. La corrida del corpus y la generación de documentos ocurren tras
esa firma, bajo el plan de corridas vigente. PROHIBIDO generar "documentos
finales" sin corrida real detrás (sería fabricación).

──────────────────────────────────────────────────────────────────────────────
7. CIERRE
──────────────────────────────────────────────────────────────────────────────

Suite + Gate 0 verdes tras cada commit; commits separados por causa raíz;
entregables sanitizados. Reportar:

```
GATES_FINAL =                    (G1–G8 con estado por cálculo real)
PENDING_HUMAN_SIGNATURES =       (lista exacta: DEC-A reg., DEC-B, 5×D2,
                                  criterios 211.68(b) si aplica, D4-A)
BACKEND_SIGNATURE_SYNC =         (resultado Bloque 5 por cada firma)
GUARD_STATUS =                   (guard_report sin FAIL reales)
SOURCES_STATUS =                 (4/4 VERIFIED o impedimento demostrado)
LEGACY_WRITERS_RETIRED =         (G8)
PERSISTENT_ORIGIN_WATCH =
STATUS_SH_FIXED =
CORPUS_READY =                   (true solo con todo lo anterior + D4-A)
CORPUS_AUTHORIZATION =           PENDING_CESAR
FINAL_DOCUMENTS_GENERATED = false (se generan tras la corrida de corpus)
FINAL_DOCUMENT_PATHS = N/A_UNTIL_CORPUS_RUN
REGULATORY_COMPLIANCE = NOT_DETERMINED
PRODUCTION_ENABLEMENT = BLOCKED
```

DETENERSE en cada checkpoint de firma. La última parada de esta corrida:
todo verde + D4-A lista para firma + paquete de autorización de corpus
preparado. Firmar y autorizar es de Cesar.
