# R3-T1.3 — Diagnóstico de viabilidad de F2 (antes de gastar 29 llamadas)

Autoridad: Capa 9 = Cesar. Claude Code = Capa 8.
Ejecutado por Claude Code, **0 llamadas LLM gastadas** en esta corrida. Toda
la evidencia de este informe viene de (a) el catálogo real
(`requirements.yaml`), (b) el checkpoint de F1 (`chunked-50534e75927c`) y
(c) un checkpoint histórico ya existente de una corrida completa anterior
sobre el mismo documento (`chunked-943a62bcbb85`, 29/29 chunks, mismo
`catalog_version=2.1`, mismo `model_digest`), reprocesado con el código
real de `semantic_evidence_verification.verify_sufficiency_aggregated()`
ejecutado dentro del contenedor `factory-api` — no un script ad hoc, la
función de producción tal cual.

**Resultado headline: F2 con el criterio original (F2.3.a, exige
CONFIRMED) es INALCANZABLE — no solo "difícil". No por B1 únicamente, y no
solo por lo que B2 anticipaba (el modelo deja criterios sin citar). Hay un
tercer factor (B3, sección 2) que hace que CONFIRMED vía agregación
multi-chunk sea estructuralmente inalcanzable para este tipo de requisito,
por diseño ya aprobado — no es un bug a arreglar. Con esto, F1.5 (sección
3-5 llamadas propuestas en el plan) queda resuelta por evidencia histórica
sin necesidad de ejecutarla — ejecutarla gastaría llamadas para reconfirmar
lo que el código ya demuestra.**

──────────────────────────────────────────────────────────────────────────
## 0. CHECKPOINT 0 — B1 y B2 (sin gastar una llamada)
──────────────────────────────────────────────────────────────────────────

### B1 — Elegibilidad de conclusión positiva

Verificado en el catálogo real (`factory/regulatory/requirement_catalog/requirements.yaml`,
línea 178 en adelante, bloque `21_CFR_11.10(e)`):

```
catalog_version: '2.1'
pack_version: 2.1-draft
evidence_pack_status: human_drafted_provisional
source_verification_status: PENDING_REVERIFICATION
pack_lifecycle_status: DRAFT
runtime_eligibility: ENABLED_REVIEW_ONLY
baseline_eligibility: PROVISIONAL_ONLY
positive_conclusion_eligibility: PROVISIONAL_ONLY   ← B1 confirmado
draft_remediation_eligibility: ENABLED_WITH_TRACEABILITY
clean_candidate_eligibility: BLOCKED
release_eligibility: BLOCKED
production_eligibility: BLOCKED
ready_for_regulatory_use: false
```

`positive_conclusion_eligibility = PROVISIONAL_ONLY` (no `true`/`ENABLED`).
**B1 confirmado exactamente como el plan lo predijo**: el pipeline no puede
emitir CONFIRMED para `21_CFR_11.10(e)` mientras este flag no se promueva.
F0.6 lo dejó así a propósito; sigue pendiente de `ARTIFACT_VERSION-2026-018`.

### B2 — ¿El chunk ancla es una propiedad del chunk o sistémica del modelo?

Leído el checkpoint de F1 (`chunked-50534e75927c.checkpoint.json`,
campo `_by_req_candidates`, sin reinterpretar nada — el propio detalle que
generó el pipeline):

```
chunk 0 (p.45-46, task-bf3897479d56):
  d_sufficiency: NOT_ASSESSABLE
  d_reason: "contrato de criterion_assessments violado: 2 problema(s)"
  d_detail.contract_violations:
    - "status=MET sin evidence_quote/evidence_location (criterion_index=2)"
    - "status=MET sin evidence_quote/evidence_location (criterion_index=3)"
```

Precisión sobre lo que RESUMEN.md de F1 ya reportó: revisando el campo
crudo, `evidence_quote` en idx=2 e idx=3 **sí venía lleno** (913 caracteres,
UR3.3.1/UR3.3.2); lo vacío era específicamente `evidence_location`. El
contrato exige ambos no-vacíos para `status=MET`; con uno vacío, viola
contrato igual — la capa D excluyó el chunk correctamente.

Desglose de los 9 criterios del chunk ancla:
- idx 1: NOT_MET
- idx 2: MET, con cita, **sin `evidence_location`** → excluido por violación de contrato
- idx 3: MET, con cita, **sin `evidence_location`** → excluido por violación de contrato
- idx 4: NOT_MET
- idx 5-9: NOT_ASSESSABLE (5 criterios, "no se mencionan mecanismos específicos...")

**¿Es esto del chunk o del modelo?** Encontré la respuesta sin gastar
llamadas: existe un checkpoint histórico completo (`chunked-943a62bcbb85`,
29/29 chunks, **mismo documento** — `document_sha256` idéntico al de F1 —,
mismo `catalog_version=2.1`, mismo `model_digest`, perfil `BASELINE`) que
ya evaluó `21_CFR_11.10(e)` contra el chunk 20 (páginas 45-46, el mismo
pasaje exacto que F1 usó como ancla). En esa corrida anterior:

```
chunk 20 (p.45-46), 21_CFR_11.10(e):
  idx 2: MET, evidence_quote lleno, evidence_location="Page 45-46"  ← SIN violación
  idx 3: MET, evidence_quote lleno, evidence_location="Page 45-46"  ← SIN violación
  idx 1,4-9: NOT_MET (consistentes, sin evidencia)
  d_sufficiency: PARTIALLY_MET
  d_reason: "2/9 criterios confirmados"
  operational_result: EVALUATION_COMPLETE
  substantive_evidence_accepted: False
```

**Esto responde B2 directamente: el modelo SÍ puede citar
`evidence_location` correctamente para este chunk/requisito exacto — ya lo
hizo una vez.** No es una incapacidad sistémica de citar. Es variabilidad
de muestreo entre corridas (mismo chunk, mismo prompt, mismo modelo, dos
resultados distintos en el campo `evidence_location`). Un nuevo intento
(F1.5) tiene una probabilidad real de repetir el éxito de la corrida
`943a62bcbb85` — pero ese no es el bloqueador real, ver sección 2.

Además, escaneando **las 29 chunk_executions completas** de esa corrida
histórica para `21_CFR_11.10(e)`: **ningún chunk del documento completo
logra MET para los criterios 1, 4, 5, 6, 7, 8 o 9** — ni siquiera en
chunks donde aparecen keywords relacionados (`access control` en chunk 17,
`retention` en chunks 20/25, `privileg` en chunks 11/17/18/27): el modelo
los evaluó y los marcó `NOT_MET`/`NOT_ASSESSABLE` consistentemente (no es
que no se hayan buscado). El documento (Rockwell FS v1.2, SCADA/PCS) trata
el audit trail de forma funcional-técnica (timestamp, campos del registro)
pero **no discute en ningún punto** controles de acceso privilegiado sobre
el propio audit trail, detección de manipulación, generación
automática/independiente del operador, retención comparada, ni exportación
— al menos no de forma que el modelo reconozca. Esto ya es un techo de
**2/9 criterios**, agregando el documento completo, con o sin el defecto
de `evidence_location`.

──────────────────────────────────────────────────────────────────────────
## 1. B3 (nuevo) — El bloqueador real: la agregación misma, no el modelo
──────────────────────────────────────────────────────────────────────────

Section 2 del plan original pedía correr F1.5 (3-5 llamadas) para decidir
si CONFIRMED es alcanzable. Encontré la respuesta ejecutando el código real
de producción (`verify_sufficiency_aggregated()`, dentro de
`factory-api`, sin tocar nada) contra los datos históricos ya existentes —
**cero llamadas nuevas**:

```python
# agregando las 29 chunk_executions de chunked-943a62bcbb85 para 21_CFR_11.10(e):
verify_sufficiency_aggregated('21_CFR_11.10(e)', per_chunk)
→ ('NOT_ASSESSABLE',
   'contradiccion real entre chunks en 2 criterio(s): MET anclado en un '
   'chunk y NOT_MET en otro -- nunca resuelto en silencio',
   {'contradicted': ['Registro de entradas y acciones...', 'Timestamp de fecha/hora.'],
    'met': [...2 criterios...], 'not_met': [...9 apariciones NOT_MET, incluyendo
    los 2 mismos criterios en otros chunks...]})
```

**El motivo**: el modelo, al evaluar `21_CFR_11.10(e)` contra chunks que NO
tratan el audit trail (ej. chunk 11 "páginas 24-25", chunk 17 "páginas
39-40"), devuelve `status=NOT_MET` para **los 9 criterios**, incluyendo
"Timestamp de fecha/hora" — el mismo criterio que el chunk 20 sí ancla como
MET. La regla de agregación (`R2.1 Opción C`, diseño ya firmado por
Cesar, `docs_plan/R2_1_C_DISENO_AGREGACION_D.md`) trata esto,
correctamente por diseño, como una **contradicción dura, nunca resuelta en
silencio** → fuerza `NOT_ASSESSABLE`.

Esto **no es un bug**: es la consecuencia correcta y ya aprobada de dos
decisiones de diseño independientes que interactúan mal para este patrón
de evidencia (positiva en 1 chunk de 29, ausente en el resto):
1. El modelo no distingue "este chunk no trata el tema" de "el requisito
   no se cumple" — devuelve `NOT_MET` en ambos casos.
2. La capa D, correctamente, no resuelve en silencio un MET-en-un-chunk
   vs NOT_MET-en-otro — lo escala a `NOT_ASSESSABLE` en vez de promediar
   o de dejar que el MET "gane".

**Repetí el experimento con el escenario real de F2** (top-5 candidatos de
fusión, exactamente los 5 chunks que F1 usó, no el documento completo):

```python
verify_sufficiency_aggregated('21_CFR_11.10(e)', [F1's 5 chunks as-is])
→ ('NOT_MET', 'ningun criterio minimo confirmado con anclaje real')
# (chunk 0 excluido por violación de contrato — B2 — los otros 4 son negativos limpios)

verify_sufficiency_aggregated('21_CFR_11.10(e)', [F1's 5 chunks, con chunk 0
                                reemplazado por la versión SIN violación de
                                contrato de la corrida histórica])
→ ('NOT_ASSESSABLE', 'contradiccion real entre chunks en 2 criterio(s)...')
```

**Conclusión dura**: aun si B2 se resolviera (el modelo cita
`evidence_location` correctamente esta vez), el resultado agregado de F2
sobre `21_CFR_11.10(e)` sería `NOT_ASSESSABLE` por contradicción, no
CONFIRMED — porque F2 evalúa el requisito contra ~29 chunks del documento,
y basta que UNO de los chunks negativos devuelva `NOT_MET` en el mismo
criterio que el chunk positivo ancla para que la contradicción se dispare.
Verifiqué que el mismo patrón ocurre con `21_CFR_11.10(d)` en la misma
corrida histórica (`NOT_ASSESSABLE` por la misma razón) — no es exclusivo
de `11.10(e)`.

**Esto responde F1.5 sin ejecutarla.** El criterio pre-fijado de F1.5 (§2.3
del plan original) pedía "al menos un chunk logra A∧B∧C∧D completos" —
pero esa pregunta, aislada a un solo chunk, no captura el bloqueador real:
el problema no es si UN chunk puede lograr A∧B∧C∧D (probablemente sí, con
suerte de muestreo, como ya pasó en `943a62bcbb85`), sino que la
**agregación entre chunks** convierte ese éxito aislado en
`NOT_ASSESSABLE` en cuanto se combina con el resto del documento — que es
exactamente lo que F2 hace. Gastar 3-5 llamadas para confirmar que un chunk
aislado puede citar bien no habría revelado esto; solo la réplica de la
agregación real (gratis, con datos ya existentes) lo revela.

──────────────────────────────────────────────────────────────────────────
## 2. Redefinición de F2 (RAMA B, más justificada que en el plan original)
──────────────────────────────────────────────────────────────────────────

El plan original planteaba RAMA A (éxito, criterio original) vs RAMA B
(fracaso, redefinir). Con la evidencia de B3, **RAMA B es la única
viable**, y con más fundamento del anticipado: no es que el modelo "a veces
no cite" — es que la combinación (ya aprobada, correcta por diseño) de
"modelo no distingue ausencia-de-tema de incumplimiento" + "contradicción
nunca resuelta en silencio" hace que CONFIRMED vía agregación sea
esencialmente inalcanzable para cualquier requisito cuya evidencia esté
concentrada en pocos chunks de un documento largo — que es el patrón
típico de specs técnicas (FS/DS) contra requisitos regulatorios amplios.

**Criterio nuevo propuesto, F2.3.a' (sin aflojar nada)**:
`21_CFR_11.10(e)` cierra `SUPPORTING_EVIDENCE_UNDER_REVIEW` cuando:
- (A) al menos un chunk ancla evidencia real (cumplido, chunk p.45-46);
- entra a cola de revisión humana con: el chunk ancla, los criterios
  específicos que quedaron sin resolver (2-9), y la nota explícita de que
  la agregación produjo `NOT_ASSESSABLE` por contradicción — el humano
  decide si esos "NOT_MET" de chunks irrelevantes son ruido o señal real.

Esto es exactamente la Opción B del plan original, pero ahora con una
razón de código verificada, no solo un riesgo anticipado.

**Decisión adicional para Cesar (no anticipada en el plan original)**: la
regla de contradicción de `verify_sufficiency_aggregated()` (R2.1 Opción C)
es correcta y deliberada, pero su interacción con el prompt actual (que no
permite al modelo decir "este chunk no trata el tema" en vez de `NOT_MET`)
genera falsos positivos de contradicción sistemáticamente. Dos caminos, sin
aflojar el validador D:
  (i) dejarlo así — cada contradicción real o espuria va a revisión humana
      (más conservador, más carga de cola);
  (ii) agregar un tercer valor al schema del modelo (ej.
      `NOT_APPLICABLE_TO_CHUNK`, distinto de `NOT_MET`) para que la capa D
      no trate "tema ausente en este chunk" como evidencia negativa real —
      esto es un cambio de contrato/prompt, no un aflojamiento de
      validación, pero es una decisión de diseño que solo Capa 9 aprueba,
      y requeriría re-versionar `prompt_version` (impacta el fingerprint
      congelado de F1).
No se implementó ninguna de las dos — se presenta para decisión.

──────────────────────────────────────────────────────────────────────────
## 3. Pendientes de F0/F1 (los baratos, ya verificados sin llamadas)
──────────────────────────────────────────────────────────────────────────

- **4.1 Gate 0 Playwright/HTTP**: ya documentado como ambiental en
  `docs_plan/R3_T1_2_F0_EVIDENCIA/RESUMEN.md` (`TimeoutError`/rate-limit
  contra Mission Control vivo bajo carga de tests). Sin cambios — no se
  tocó nada nuevo en esta corrida.
- **4.2 `part11_prompts.yaml` fantasma**: confirmado que sigue existiendo
  en `factory/workspaces/gmpai_document_validation/prompts/` (v1.0.0, no
  cargado por producción). Sin acción — decisión de Cesar pendiente, igual
  que F1 la dejó.
- **4.3 Fingerprint**: con B1 sin resolver, `catalog_version` sigue en
  `2.1` — el fingerprint de F1 sigue vigente sin cambios. Si Cesar promueve
  B1, `catalog_version` probablemente sube a `2.2` y el fingerprint de F1
  deja de coincidir (F2 no reutilizaría cache de F1/F1.5). Dado que RAMA B
  no depende de B1 para su criterio nuevo (F2.3.a' no exige
  `positive_conclusion_eligibility`), **recomendación de orden**: resolver
  primero si Cesar acepta RAMA B (no cuesta nada, es solo criterio), y
  recién ahí decidir si vale la pena promover B1 para los requisitos donde
  sí haya margen real de alcanzar CONFIRMED (no es el caso de `11.10(e)`
  en este documento).

──────────────────────────────────────────────────────────────────────────
## 4. ENTREGA
──────────────────────────────────────────────────────────────────────────

```
B1_FLAG_STATE =               positive_conclusion_eligibility = PROVISIONAL_ONLY (bloqueado)
B2_F1_CRITERION_BREAKDOWN =   2 MET (con cita, sin evidence_location) / 2 NOT_MET /
                              5 NOT_ASSESSABLE, sobre 9 criterios (chunk ancla, F1)
B2_RESOLUCION =               NO sistémico del modelo (corrida histórica 943a62bcbb85
                              muestra el MISMO chunk citando evidence_location
                              correctamente) -- es variabilidad de muestreo, no
                              incapacidad
B3_NUEVO =                    la agregación multi-chunk (verify_sufficiency_aggregated,
                              diseño ya aprobado R2.1 Opción C) convierte el éxito de
                              un chunk aislado en NOT_ASSESSABLE por "contradicción"
                              en cuanto se agregan chunks negativos del resto del
                              documento -- verificado ejecutando el código real contra
                              29/29 chunks históricos y contra los 5 chunks reales de F1
F1_5_BUDGET =                 NO CONSUMIDO -- resuelto sin llamadas (ver B3)
F1_5_RESULT =                 FRACASO, con evidencia de código+datos históricos, sin
                              gastar el margen de PILOT_EXECUTION-2026-016
F1_5_FAILING_CRITERIA_PATTERN = sistémico a nivel de AGREGACIÓN (no de citación aislada):
                              cualquier requisito con evidencia concentrada en pocos
                              chunks de un documento largo choca con la regla de
                              contradicción -- confirmado también en 21_CFR_11.10(d)
F2_VIABLE =                   RAMA B (criterio original F2.3.a inalcanzable, no solo
                              para 11.10(e) -- patrón probablemente general)
F2_REDEFINED_CRITERION =      F2.3.a': SUPPORTING_EVIDENCE_UNDER_REVIEW con ancla (A)
                              + cola de revisión humana con criterios sin resolver
FINGERPRINT_ORDER_ADVICE =    decidir RAMA B primero (no depende de B1); promover B1
                              después, solo si hay requisitos con margen real de
                              CONFIRMED
GATE0_TIMEOUT_TESTS =         ya documentados como ambientales en F0, sin cambios
PHANTOM_PROMPT =              decisión de Cesar pendiente, sin cambios
NEXT_SIGNATURES =             (i) aceptar/rechazar RAMA B (F2.3.a') como criterio de F2;
                              (ii) decidir sobre B3 (agregar NOT_APPLICABLE_TO_CHUNK al
                              schema, o dejar la contradicción como está);
                              (iii) ARTIFACT_VERSION-2026-018 y elegibilidad de B1 solo
                              si hay requisitos donde CONFIRMED sí tenga margen real
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

**DETENERSE.** No se ejecutó F2 ni F1.5. No se gastó ninguna llamada LLM en
esta corrida — toda la evidencia viene de datos ya pagados (checkpoint
histórico `chunked-943a62bcbb85`) y del código real de agregación
ejecutado sin llamadas al modelo. El hallazgo central (B3) es más
importante que B1/B2 para la decisión de F2 y requiere una decisión de
Cesar que el plan original no anticipaba.

──────────────────────────────────────────────────────────────────────────
## 5. Addendum (2026-08-12) — firma (i) recibida, (ii) diferida, hallazgo en (iii)
──────────────────────────────────────────────────────────────────────────

**(i) RAMA B — ACEPTADA por Cesar.** F2.3.a' (`SUPPORTING_EVIDENCE_UNDER_REVIEW`
con ancla + cola de revisión humana) queda como criterio de F2, en vez del
original F2.3.a (exige CONFIRMED). Sin costo — es solo criterio, no toca
código ni catálogo.

**(ii) B3 — DIFERIDA por decisión explícita de Cesar** ("decidamos B3
después"). Nota importante para cuando se retome: el bloqueador B3 ya
tiene un fix técnico diseñado, validado por replay y **commiteado**
(`e823015`, ver `docs_plan/R3_T1_4_FIX_AGREGACION_B3.md`) — no fue la
opción "agregar NOT_APPLICABLE_TO_CHUNK al schema" que este documento
proponía en §4, sino una tercera vía (reusar el campo `estado` ya emitido
por el modelo, sin cambio de schema). El fix está en el árbol de
`master`; lo que queda diferido no es la implementación sino la decisión
de habilitarlo/usarlo formalmente en una corrida de F2.

**(iii) ARTIFACT_VERSION-2026-018 — HALLAZGO: el ID ya está tomado.**
Verificado en `factory/layer9/decisions/decisions_v2.jsonl`: existe una
entrada `ARTIFACT_VERSION-2026-018` de una sesión anterior (R3-T1.2/F0.6,
2026-08-12T01:50), `decision_origin=agent_proposed`, **nunca confirmada
por un humano** (`approved_by_id: null`), y **no aplicada** —
`requirements.yaml` en disco sigue en `catalog_version: '2.1'`, no `2.2`
como esperaba esa propuesta. Esa entrada cubre únicamente la
sincronización mecánica de `source_verification_status` (20 entradas,
`PENDING_REVERIFICATION` → `LOCAL_CANONICAL_COPY_VERIFIED`) y **excluye
explícitamente** `positive_conclusion_eligibility` (cita literal del
`reason` de esa entrada: *"NO toca positive_conclusion_eligibility/
baseline_eligibility/content_review_status... sin firma nueva que los
cubra explicitamente"*). Conclusión: promover B1 no puede reutilizar el
ID 018 — necesitará una instancia nueva (previsiblemente
`ARTIFACT_VERSION-2026-019`) cuando se decida.

Estado tras este addendum: `NEXT_SIGNATURES` (i) cumplida, (ii) diferida
por decisión explícita, (iii) sigue pendiente y su numeración de ID debe
corregirse cuando se retome. `CORPUS_READY = false` y
`PRODUCTION_ENABLEMENT = BLOCKED` no cambian.
