# CF-6 v2.0 · R2 — HUMAN_QUALITY_GATE (preparación de datos, sin adjudicación)

**Fecha:** 2026-09-04 · **Instrucción aplicada:** Capa 9 acepta la reconciliación de cobertura
(`sec-0026`/`sec-0042` = fail-closed válido; `COVERAGE=PARTIAL` cerrado, no se reabre). R2
permanece abierto ÚNICAMENTE para completar AUDIT QUALITY. **Claude Code prepara y reporta
datos; NO adjudica la rúbrica, NO decide PASS/FAIL, NO tag `cf6-v2-R2`, NO R3, 0 llamadas LLM
nuevas, 0 cambios de threshold.**

Fuentes: `CF6_v2_R2_RUN.json` / `CF6_v2_R2_B_OUTPUTS.jsonl` (corrida real re-ejecutada, `76ab815`,
artefactos preservados) · `CF6_2_5_v3_B_OUTPUTS.jsonl` (línea base A, v3) ·
`CF6_v2_R2_LABELED_SAMPLE_CANDIDATE_POOL.json` (población completa de candidatos, este documento).

---

## 1 · SAFETY/GOVERNANCE por sección (determinista — ya adjudicado, no cambia)

| sección | Q-STATE | blacklist | evidence_basis ⊆ relevant_evidence | modo |
|---|---|---|---|---|
| sec-0004 | n/a (sin estructura — correcto, `relevant_evidence` vacío) | CLEAN | n/a | SAFE_MODE |
| sec-0005 | n/a (sin estructura — correcto) | CLEAN | n/a | SAFE_MODE |
| **sec-0016** | **PASS** | CLEAN | **SÍ** | **RENDERED** |
| sec-0018 | n/a (sin estructura — correcto) | CLEAN | n/a | SAFE_MODE |
| sec-0026 | n/a (fuera de alcance — sin decomposition.yaml) | CLEAN | n/a | SAFE_MODE |
| sec-0042 | n/a (fuera de alcance — sin regulación) | CLEAN | n/a | SAFE_MODE |
| sec-0062 | n/a (sin estructura — correcto, `relevant_evidence` vacío) | CLEAN | n/a | SAFE_MODE |

0 violaciones Q-STATE publicadas · 0 hits de blacklist · `L2_MUTATIONS=0` · `human_state` sin
cambios · `G4d` no re-ejecutado · 0 LLM post-Q-STATE. **Cerrado, no se reabre.**

---

## 2 · Métricas AUDIT QUALITY por sección — datos, sin veredicto

Convención: **determinista** = Claude Code puede calcularlo objetivamente (ya calculado abajo).
**rúbrica humana** = campo vacío, `PENDIENTE`, para que Capa 9/QA lo puntúe. `N/A` = la sección
no generó narrativa (SAFE_MODE fail-closed) — no hay texto del LLM que evaluar en esas
dimensiones, por diseño (esto en sí mismo es el dato de seguridad, no un vacío de calidad).

| sección | requirement_interpretation_accuracy | evidence_relevance_accuracy | gmp_assessment_accuracy | citation_fidelity | unsupported_conclusions | regulatory_overstatement | professional_clarity | audit_utility/value_added | cognitive_load_reduction |
|---|---|---|---|---|---|---|---|---|---|
| sec-0004 | N/A (sin narrativa) | rúbrica humana* | N/A | N/A | **0** (determinista) | **0** (determinista) | N/A | N/A | N/A |
| sec-0005 | N/A (sin narrativa) | rúbrica humana* — **ver §3, caso señalado** | N/A | N/A | **0** | **0** | N/A | N/A | N/A |
| **sec-0016** | PENDIENTE (rúbrica) | rúbrica humana* | PENDIENTE (rúbrica) | **1.0** (determinista — única cita, ancla Q-STATE-6 PASS) | **0** (determinista) | **0** (determinista) | PENDIENTE (rúbrica) | PENDIENTE (rúbrica) | PENDIENTE (rúbrica) |
| sec-0018 | N/A (sin narrativa) | rúbrica humana* | N/A | N/A | **0** | **0** | N/A | N/A | N/A |
| sec-0026 | N/A (fuera de alcance) | N/A (fuera de alcance, sin candidatos evaluados por el Relevance Model) | N/A | N/A | **0** | **0** | N/A | N/A | N/A |
| sec-0042 | N/A (fuera de alcance) | N/A (fuera de alcance) | N/A | N/A | **0** | **0** | N/A | N/A | N/A |
| sec-0062 | N/A (sin narrativa) | rúbrica humana* | N/A | N/A | **0** | **0** | N/A | N/A | N/A |

\* `evidence_relevance_accuracy` es la única métrica de esta lista que el diseño (§4) declara
**medible determinísticamente** — pero requiere la muestra etiquetada por humano de §4 abajo
para calcularse (precisión/recall del Relevance Model contra el `human_label`). Sin esa
etiqueta, hoy es dato pendiente, no un número que Claude Code pueda producir.

**`citation_fidelity`/`unsupported_conclusions`/`regulatory_overstatement` en las 6 secciones
SAFE_MODE son `0`/`N/A` por construcción** (sin narrativa generada, nada que pudiera fabricar
una cita, una conclusión no sustentada o una sobreafirmación) — es un resultado trivial pero
real, no una laguna.

---

## 3 · sec-0005 — paquete de evaluación humana específica

**Requisito:** `21_CFR_11.50_11.70`
```
requirement_text (ES): "cada firma electrónica muestra el nombre impreso del firmante · cada
  firma electrónica muestra la fecha y hora en que se ejecutó · cada firma electrónica muestra
  el significado asociado (revisión, aprobación, responsabilidad, autoría) · esos tres
  elementos son legibles y están asociados al registro firmado · los controles del registro
  electrónico (acceso, integridad, retención, disponibilidad) se extienden a los tres elementos
  de la firma · existe un mecanismo técnico protegido que ata la firma al registro específico ·
  hay prueba de que ese mecanismo impide extraer, copiar o transferir la firma por medios
  ordinarios"
requirement_intent (EN): "each electronic signature shows the printed name of the signer · each
  electronic signature shows the date and time it was executed · each electronic signature
  shows the associated meaning (review, approval, responsibility, authorship) · those three
  elements are human-readable and associated with the signed record · the electronic record
  controls (access, integrity, retention, availability) are extended to the three signature
  elements · there is a protected technical mechanism that binds the signature to the specific
  record · there is proof that this mechanism prevents excising, copying or transferring the
  signature by ordinary means"
```

**Los 3 candidatos "electronic signature" del pool (misma cita, 3 findings, 3 sub-criterios distintos):**

| finding_record_id | matched_subcriterion | sub-criterio (texto) | ratio | n_matched | model_relevance_state |
|---|---|---|---|---|---|
| rec-f2c131db4e52163d | sc1 | "cada firma electrónica muestra el nombre impreso del firmante" | 0.0909 | 3 | INCONCLUSIVE |
| rec-33acbc832665ade8 | sc2 | "cada firma electrónica muestra la fecha y hora en que se ejecutó" | 0.0811 | 3 | INCONCLUSIVE |
| rec-95102a2c01cbeb36 | sc6 | "existe un mecanismo técnico protegido que ata la firma al registro específico" | 0.033 | 1 | INCONCLUSIVE |

Cita completa (idéntica en los 3): *"With the FactoryTalk View SE electronic signature feature,
each entry into the FactoryTalk View..."*

**Pregunta para el humano** (no respondida aquí): ¿el candidato es genuinamente pertinente a
`sc1`/`sc2` (nombre del firmante / fecha-hora) — en cuyo caso el Relevance Model produjo un
falso negativo en 2 de 3 sub-criterios — o el `INCONCLUSIVE` es correcto porque el pasaje solo
anuncia la *existencia* de la función de firma electrónica sin mostrar sus 3 elementos
constitutivos (nombre/fecha-hora/significado) de forma verificable en el texto citado? Esta
distinción es exactamente lo que `evidence_relevance_accuracy` debe medir con una muestra
etiquetada, no con un juicio ad hoc de Claude Code. **No se cambió el umbral ni la
clasificación.**

---

## 4 · Muestra etiquetada requisito×evidencia (para `evidence_relevance_accuracy`)

Población completa: **27 pares requisito×evidencia** (todos los candidatos del Relevance Model
en las 5 secciones dentro de alcance), `human_label: null` en los 27 — Claude Code no etiquetó
ninguno. Artefacto completo:
`docs_plan/shadow_llm/CF6/CF6_v2_R2_LABELED_SAMPLE_CANDIDATE_POOL.json`.

**Subconjunto de mayor valor informativo para una muestra pequeña** (ratio más cercano al
umbral `PARTIALLY_RELEVANT≥0.12` por cualquiera de los dos lados — ni elegido ni descartado,
solo ordenado por cercanía al umbral; el etiquetado real lo hace un humano):

| # | sección | requisito | ratio | n_matched | model_relevance_state | cita (recortada) |
|---|---|---|---|---|---|---|
| 1 | sec-0016 | 21_CFR_11.10(d) | **0.1231** | 2 | PARTIALLY_RELEVANT (el único candidato que SÍ cruzó el umbral) | "...security and access control" |
| 2 | sec-0005 | 21_CFR_11.50_11.70 | 0.0909 | 3 | INCONCLUSIVE | "...electronic signature feature..." (sc1) |
| 3 | sec-0004 | 21_CFR_11.10(g) | 0.087 | 1 | INCONCLUSIVE | "Process interlocks may be overridden with appropriate access level." |
| 4 | sec-0018 | 21_CFR_11.10(g) | 0.087 | 1 | INCONCLUSIVE | "access for level 1 and level 2 alarms only." |
| 5 | sec-0018 | 21_CFR_11.10(g) | 0.087 | 1 | INCONCLUSIVE | "Engineer security level privileges." |
| 6 | sec-0005 | 21_CFR_11.50_11.70 | 0.0811 | 3 | INCONCLUSIVE | "...electronic signature feature..." (sc2) |
| 7 | sec-0016 | 21_CFR_11.10(d) | 0.08 | 1 | INCONCLUSIVE | "Process Automation Control Server System" |
| 8 | sec-0016 | 21_CFR_11.10(d) | 0.08 | 1 | INCONCLUSIVE (misma cita, distinto finding/sub-criterio) | "Process Automation Control Server System" |
| 9 | sec-0016 | 21_CFR_11.10(d) | 0.0645 | 1 | INCONCLUSIVE (el candidato de `sec-0016` v1.3, ya excluido) | "...measure the critical process parameters..." |
| 10 | sec-0005 | 21_CFR_11.50_11.70 | 0.0545 | 3 | INCONCLUSIVE | "...electronic signature feature..." (sc6) |

Este subconjunto de 10 (de 27) concentra los casos más ambiguos por diseño: el único
`PARTIALLY_RELEVANT` real (control positivo) y los 9 `INCONCLUSIVE` con mayor señal léxica —
donde una discrepancia humano-vs-modelo sería más informativa para medir precisión/recall del
Relevance Model. **No es una selección definitiva** — Capa 9/QA decide el tamaño y composición
final de la muestra a etiquetar.

---

## 5 · A-vs-B completo, las 7 secciones (ya entregado, referenciado aquí para el gate)

Ver tabla A-vs-B completa en la reconciliación previa de esta sesión (turno anterior) — sin
cambios: `sec-0016` (A: 4 evidencias incl. la irrelevante / B: 1 evidencia, acotada);
`sec-0004/0005/0018` (A: RENDERED con 2-3 evidencias / B: SAFE_MODE, `relevant_evidence` vacío);
`sec-0026/0042` (A: RENDERED bajo v3 / B: fuera de alcance R2, SAFE_MODE); `sec-0062` (A: ya
SAFE_MODE en v3 / B: SAFE_MODE, `relevant_evidence` vacío).

---

## STOP

Datos preparados: SAFETY/GOVERNANCE por sección (§1, cerrado), métricas AUDIT QUALITY con lo
determinista calculado y lo de rúbrica marcado `PENDIENTE` (§2), paquete específico de
`sec-0005` con las 3 ocurrencias del candidato y la pregunta abierta sin responder (§3),
población completa + subconjunto de mayor valor informativo para la muestra etiquetada (§4). **No
se puntuó ninguna rúbrica. No se declaró PASS/FAIL de AUDIT QUALITY. No tag `cf6-v2-R2`. No R3.
0 llamadas LLM nuevas. 0 cambios de threshold.** Decisión humana de Capa 9 pendiente.
