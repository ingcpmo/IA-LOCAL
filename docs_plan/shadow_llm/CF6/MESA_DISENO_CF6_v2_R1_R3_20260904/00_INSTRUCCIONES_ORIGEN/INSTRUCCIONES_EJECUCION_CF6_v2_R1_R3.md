# INSTRUCCIONES DE EJECUCIÓN — CF-6 v2.0 · FASES R1–R3

**Fecha:** 2026-09-04 · **Autoridad:** Capa 9 = Cesar · **Diseño de referencia:**
`CF6_v2_REDISENO_AUDITORIA_PROFESIONAL.md`. Reemplaza el plan de ejecución de v1.3 (absorbido en R1).
**Solo R1, R2 y R3 están autorizados en esta ronda.** R4-R6 se instruyen en un documento posterior,
tras el gate humano de R2. **D-ADJ, D-M4+ y D-REPORT-EXT no están autorizados — no se tocan.**

---

# PARTE A — CLAUDE CODE

## Régimen
Fases cortas, estado congelado por fase, gate humano entre fases. R1 y R3 **sin LLM en su mayor parte**
(R3 incluye un benchmark acotado con LLM, ver abajo). R2 ejecuta LLM y requiere el mismo régimen de
`PILOT_SCOPE_MATCH_CF6` que v1.2/v1.3.

## Invariantes (sin cambios respecto de v1.2/v1.3, más las nuevas de v2.0)
```
findings_fingerprint == 235f724a…  ·  L2_MUTATIONS = 0  ·  human_state sin cambios
G4d NO se re-ejecuta  ·  verificador de anclaje G2 intacto  ·  0 LLM después de Q-STATE
UNAUTHORIZED_CLIENT_DATA_EGRESS = 0 · LLM_PROVIDER = LOCAL · canal regulatorio externo sigue OFF
NO implementar el GMP Adjudication Expert Agent (§9 del diseño) — solo está DISEÑADO, no autorizado
NO implementar LoRA, case memory, dataset de entrenamiento, benchmark de modelo mayor (M3-M7)
NO implementar el renderer externo del ProfessionalReportModel — solo su esquema (R6, aún no autorizada)
NO activar `fusion` (BM25+embeddings) por defecto — solo medirlo en comparación acotada (R3)
```

## R1 · Relevance Model + contrato requirement-centric + ProfessionalAssessmentRecord (sin LLM)
1. Localizar `decomposition.yaml` v1.1 (leer, no modificar) y el `EvidenceBundle`/`evidence_bundle.py`
   existente (BM25, `bm25_score` ya disponible).
2. Implementar el **Requirement↔Evidence Relevance Model** (diseño §4): por cada `EvidenceBundle`,
   clasificar cada candidato en `RELEVANT / PARTIALLY_RELEVANT / IRRELEVANT / INCONCLUSIVE` contra el
   texto decompuesto y sinónimos gobernados del `requirement_id` correspondiente. Producir
   `relevant_evidence[]` y `excluded_evidence[]` (este último se conserva para auditoría, no se borra).
3. Extender el contrato del Composer (diseño §3): `requirement_text`/`requirement_intent` sourced de
   `decomposition.yaml` (nunca generados por el LLM); nuevos campos `technical_assessment` /
   `procedural_responsibility` / `gap_or_open_question` / `assessment_rationale` / `confidence`.
   **El paso de generación LLM (paso 2 del Composer, diseño §5) recibe SOLO `relevant_evidence[]`** —
   verificar en código que `excluded_evidence[]` nunca se serializa hacia el prompt del modelo.
4. Reorganizar el agrupamiento del render de por-sección a **por `requirement_id`** (clave primaria),
   conservando `section_type` como metadato de agrupación visual.
5. Q-STATE-7 (v1.3) se conserva íntegro como segunda verificación (defensa en profundidad), sin
   modificar su lógica.
6. Implementar `ProfessionalAssessmentRecord` (diseño §10) como esquema/artefacto interno versionado,
   poblado desde el contrato extendido — **sin renderer externo, sin cliente todavía.**
7. Medir contra las 7 salidas de `run2`/v1.3 (sin regenerar todavía): verificar que el Relevance Model,
   aplicado retroactivamente al `EvidenceBundle` original de `sec-0016`, clasifica el candidato de
   "medición de parámetros críticos" como `IRRELEVANT` para `21_CFR_11.10(d)`.
**Aceptación:** clasificación reproducible (correr dos veces, mismo resultado); el candidato problemático
de `sec-0016` cae en `excluded_evidence[]`; ningún test existente de v1.2/v1.3 regresa; `decomposition.
yaml` con 0 escrituras. Tag `cf6-v2-R1`.

## R2 · Regeneración bajo el nuevo contrato + HUMAN_QUALITY_GATE bidimensional (LLM, PILOT-gated)
1. Repetir el gate `PILOT_SCOPE_MATCH_CF6` (4 chequeos) contra la PILOT vigente — el tipo de ejecución
   cambia (nuevo contrato, Relevance Model activo), así que **no asumir** que el scope firmado la cubre;
   verificarlo explícitamente. Si no cubre, STOP y reportar a Capa 9 (puede requerir ampliar scope o
   nueva PILOT — decisión de Capa 9, no de Claude Code).
2. Regenerar las 7 secciones de la muestra bajo el Composer de 4 pasos (diseño §5), con
   `relevant_evidence[]` ya filtrado. Aplicar Q-STATE-1..7 + render determinista + blacklist.
3. Entregar paquete A-vs-B al humano, **con las dos dimensiones separadas** (diseño §6): SAFETY/
   GOVERNANCE (heredado) y AUDIT QUALITY (nuevo — incluye `evidence_relevance_accuracy` medible
   determinísticamente contra una muestra pequeña de pares requisito×evidencia etiquetados por un
   humano, más las dimensiones de rúbrica existentes de CF-6 v1.2 §4.2). Claude Code no evalúa la
   rúbrica ni el `evidence_relevance_accuracy` — reporta los datos, el humano juzga.
**Gate:** PASS solo si SAFETY/GOVERNANCE se mantiene íntegro **y** AUDIT QUALITY cumple los umbrales
por sección de CF-6 v1.2 §4.2 **y** `sec-0016` ya no exhibe el error de `SCOPE_DRIFT` verificado en
`CF6_2_5_v3_PILOT_RUN.json`. Tag `cf6-v2-R2`.

## R3 · Exploración M1/M2 acotada — benchmark BM25 vs BM25+fusion (LLM acotado, PILOT-gated)
1. **No activar `fusion` por defecto.** Ejecutar el Relevance Model + Composer de R1/R2 dos veces sobre
   el mismo conjunto de prueba: una con `evidence_bundle` en modo `bm25` (actual), otra con `fusion`
   habilitado **solo para esta comparación** (100% local, sin nueva dependencia de red).
2. Medir el efecto sobre `evidence_relevance_accuracy` y sobre la tasa de `SAFE_MODE`.
3. Reportar la comparación. **No cambiar el modo por defecto** — esa decisión es de Capa 9, con los
   datos de esta comparación en mano.
**Aceptación:** comparación reproducible; 0 tráfico externo en ningún modo; informe con ambos conjuntos
de métricas, sin recomendación de activar `fusion` implícita en el código (el flag por defecto no
cambia). Tag `cf6-v2-R3`.

## Reporte por fase
```
FASE · PRE/POST_COMMIT · DIFF (prohibidos=VACÍO) · COMMANDS · TEST_RESULTS · FINGERPRINTS ·
LLM_CALLS · LLM_CALLS_AFTER_QSTATE (=0) · RELEVANCE_MODEL_OUTPUT_SAMPLE (incl. veredicto sec-0016) ·
EXCLUDED_EVIDENCE_NEVER_SENT_TO_LLM (verificación de código, no solo declaración) ·
PILOT_SCOPE_MATCH_CF6 · HUMAN_QUALITY_GATE_BY_SECTION (ambas dimensiones) ·
FUSION_COMPARISON (solo R3; modo por defecto sin cambio) · EXPECTED_VS_ACTUAL · PROPOSED_VERDICT
```

## No hacer
No implementar el Adjudicator (§9 del diseño — queda como especificación, no código). No iniciar M3-M7.
No construir el renderer del `ProfessionalReportModel`. No activar `fusion` por defecto. No modificar
`decomposition.yaml`. No avanzar a R4-R6 sin gate humano explícito sobre R2.

---

# PARTE B — AUDITOR EXTERNO (DEVIN)

## Invariantes críticos
```
CRIT-0       findings_fingerprint == 235f724a… · fingerprints de input_config/graph_snapshot intactos
CRIT-L2      0 mutaciones de L2   ·   CRIT-H  0 cambios de human_state
CRIT-G4D     0 llamadas a G4d   ·   CRIT-NORET  0 llamadas LLM después de Q-STATE
CRIT-FILTER  excluded_evidence[] nunca serializado hacia el prompt del Composer (verificación de código)
CRIT-SCOPE   ningún componente de §9 (Adjudicator), M3-M7, o renderer externo introducido
CRIT-E1      client-data egress = 0 · canal regulatorio externo sigue OFF · fusion no activado por defecto
```

## Claims
```
R1.1  "el Relevance Model clasifica el candidato de sec-0016 como IRRELEVANT para 11.10(d),
       reproducible, usando decomposition.yaml sin modificarlo"
  TEST: correr el modelo dos veces sobre el EvidenceBundle original de sec-0016 desde clon limpio;
        diff de decomposition.yaml antes/después
  EXPECTED: mismo veredicto; 0 diff · CRIT
R1.2  "excluded_evidence[] nunca llega al LLM"
  TEST: inspección estática del código que arma el prompt del Composer; confirmar que solo serializa
        relevant_evidence[]
  EXPECTED: 0 referencias a excluded_evidence en la construcción del prompt · CRIT-FILTER
R1.3  "ProfessionalAssessmentRecord es un esquema interno, sin renderer externo ni distribución a cliente"
  TEST: buscar cualquier ruta de exportación/envío externo del artefacto
  EXPECTED: 0 · CRIT-SCOPE (GOVERNANCE)
R2.1  "PILOT_SCOPE_MATCH_CF6 verificado explícitamente para el nuevo tipo de ejecución, no asumido"
  TEST: leer el scope firmado; contrastar contra el Composer de 4 pasos y el Relevance Model
  EXPECTED: los 4 chequeos con evidencia citable, o STOP documentado (GOVERNANCE)
R2.2  "sec-0016 regenerada ya no exhibe SCOPE_DRIFT; SAFETY y AUDIT QUALITY reportadas por separado"
  TEST: correr Q-STATE-7 sobre la sec-0016 regenerada; verificar que el registro humano trae ambas
        dimensiones, no un PASS/FAIL único
  EXPECTED: SCOPE_DRIFT ausente; dos dimensiones visibles y separadas en el registro
R3.1  "comparación bm25 vs fusion ejecutada 100% local, 0 tráfico externo, modo por defecto sin cambio"
  TEST: monitoreo de red durante la corrida; verificar el flag de configuración tras R3
  EXPECTED: 0 tráfico externo; `evidence_bundle` sigue en modo bm25 por defecto · CRIT-E1
R_ALL "ningún componente de §9 (Adjudicator/AdjudicationPolicy), M3-M7, ni renderer de
       ProfessionalReportModel aparece en el código de esta ronda"
  TEST: búsqueda de módulos/dependencias/nombres relacionados
  EXPECTED: 0 · CRIT-SCOPE — cualquier indicio es FAIL inmediato, sin excepción
```

## Reglas de veredicto
```
todos los CRIT-* + criterios de la fase = YES → PASS
MATCH=NO no-crítico, con causa, sin impacto → PARTIAL (decisión humana)
MATCH=NO en cualquier CRIT-*, o aparece código de §9/M3-M7/renderer externo, o fusion quedó activado
  por defecto → FAIL = STOP
Devin sin certeza → STOP + reconciliación por evidencia
```

Devin reporta; la mesa compara; **Capa 9 decide.** Esta ronda cubre exclusivamente R1–R3. R4–R6 requieren
instrucciones nuevas tras el gate humano de R2. D-ADJ, D-M4+ y D-REPORT-EXT permanecen sin programar y
sin autorización — su ejecución requeriría una decisión de Capa 9 completamente separada de este ciclo.
