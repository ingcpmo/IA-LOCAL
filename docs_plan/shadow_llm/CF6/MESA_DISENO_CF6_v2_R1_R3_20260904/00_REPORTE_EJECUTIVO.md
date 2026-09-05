# CF-6 v2.0 · Fases R1–R3 — Reporte ejecutivo completo

**Para:** mesa de diseño (Capa 9 / QA / arquitectura) · **Fecha de cierre de esta ronda:** 2026-09-04
**Rama:** `shadow/llm-interpretation-layer` · **Commits de este arco:** `7d74878` .. `d036711` (10 commits)
**Documentos de origen:** `00_INSTRUCCIONES_ORIGEN/CF6_v2_REDISENO_AUDITORIA_PROFESIONAL.md`
(diseño, Capa 9) y `00_INSTRUCCIONES_ORIGEN/INSTRUCCIONES_EJECUCION_CF6_v2_R1_R3.md` (plan de
ejecución, Capa 9).

**Autoridad:** Capa 9 = Cesar. Ejecución técnica: Claude Code (Capa 8). Toda decisión de scope,
gobernanza, adjudicación de calidad y remediación fue de Capa 9 — este reporte lo confirma con
evidencia, no la sustituye.

---

## 1 · Resumen de una línea por fase

| Fase | Estado | Resultado |
|---|---|---|
| **R1** — Relevance Model + contrato requirement-centric + `ProfessionalAssessmentRecord` | **CERRADO, PASS** | Tag `cf6-v2-R1`. Auditado externamente PASS. |
| **R2.1** — gate `PILOT_SCOPE_MATCH_CF6` | **CERRADO, PASS** (tras remediación) | 2 rondas de FAIL → remediación de gobernanza → PASS. |
| **R2.2** — regeneración con LLM real | **EJECUTADO** | 1/7 secciones RENDERED, 4/7 SAFE_MODE fail-closed, 2/7 fuera de alcance. |
| **R2.3** — HUMAN_QUALITY_GATE (AUDIT QUALITY) | **ABIERTO, FAIL** | `evidence_relevance_accuracy=0.0/0.0`; rúbrica `sec-0016` 3/5 < umbral 4/5. |
| **R3** | **NO EJECUTADO** | Explícitamente no autorizado en esta ronda. |

**Estado consolidado de R2: no cierra.** `SAFETY/GOVERNANCE = PASS` y `sec-0016 SCOPE_DRIFT
ausente = PASS`, pero `AUDIT QUALITY = FAIL` — el gate exige las tres condiciones. Sin tag
`cf6-v2-R2`. Sin remediación ejecutada todavía (decisión pendiente de Capa 9, ver §5).

---

## 2 · Qué se ejecutó, en orden, con qué resultado

### R1 (commit `7d74878`, tag `cf6-v2-R1`)
- **Relevance Model** (`04_CODIGO/relevance_model.py`): clasificador determinista
  `RELEVANT/PARTIALLY_RELEVANT/IRRELEVANT/INCONCLUSIVE` por solapamiento léxico ponderado con
  IDF local (calculado sobre los sub-criterios del propio requisito, sin lista de stopwords de
  dominio hecha a mano).
- **Contrato requirement-centric** (`04_CODIGO/requirement_centric.py`): agrupamiento por
  `requirement_id`, `requirement_text`/`requirement_intent` sourced de `decomposition.yaml`,
  filtro que arma el contexto del Composer con SOLO `relevant_evidence[]` (verificado en código
  que `excluded_evidence[]` nunca llega), `ProfessionalAssessmentRecord` (schema interno).
- **Resultado:** 15 tests, 0 regresiones. Confirmado retroactivo: el candidato irrelevante que
  contaminó `sec-0016` en CF6-1.3 (`rec-6b0c9965fd2f4e05`, "medición de parámetros críticos")
  cae en `excluded_evidence[]`. **Funcionó según diseño.**

### R2.1 — gate de scope (commits `bdb1a63`, `dd24c5c`, `7b907f6`, `c6b120a`)
- Verificación explícita (no asumida) de `PILOT_SCOPE_MATCH_CF6` para el nuevo tipo de
  ejecución → **FAIL** la primera vez (no existía ningún `composer_prompt_version` para el
  pipeline nuevo).
- ADDENDUM propuesto y `human_confirmed` (`PILOT_EXECUTION-2026-041/-042`, vía
  `governance_service`, sin edición manual del ledger) → **segundo FAIL** (el chequeo `c_cf6_3`
  exige el token literal `"CF6-3"`, y el ADDENDUM usó terminología de fases del diseño v2.0 en
  su lugar).
- ADDENDUM correctivo (`PILOT_EXECUTION-2026-043/-044`, mismas unidades de scope, añade el token
  legado) + firma del prompt `shadow-cf6-composer-v2.0-relevance-filtered` (status
  `DRAFT_UNSIGNED → SIGNED`, únicas 4 líneas cambiadas, contenido congelado byte-idéntico) →
  **PASS** (los 4 chequeos + presupuesto + activo + no-supersedido).
- **Funcionó, pero con 2 iteraciones de error propio no forzado** — ver diagnóstico §5.

### R2.2 — ejecución real con LLM (commits `216a280`, `76ab815`)
- Corrida real (`04_CODIGO/cf6_r2_runner.py`, modelo `qwen2.5:7b-instruct-q4_K_M`, 1 llamada
  LLM total) sobre las 7 secciones de `CF6_2_5_SAMPLE_MANIFEST.json` (hash `7422faaf…`, tag
  `cf6-G2.5-manifest`, sin cambios).
- **Defecto de integridad descubierto y corregido en el mismo arco**: los tests
  `dry_run=True` escribían sobre la MISMA ruta que la corrida real, y al correr la suite después
  de la corrida real (antes de comitear) los artefactos reales quedaron sobrescritos sin
  detectarse. Corregido (`76ab815`): rutas de salida separadas por defecto (`_REAL_OUT_DIR` /
  `_DRY_RUN_OUT_DIR`), re-ejecutado bajo exactamente el mismo prompt/hash/scope, artefactos
  reales preservados y verificados bit-idénticos tras la suite completa.
- **Resultado real:** `sec-0016` RENDERED (Q-STATE PASS, SCOPE_DRIFT confirmado ausente con
  salida real) — 1 de 5 secciones elegibles. 4 de 5 elegibles cayeron a `SAFE_MODE` fail-closed
  porque el Relevance Model dejó `relevant_evidence[]` vacío. 2 de 7 (`sec-0026`, `sec-0042`)
  fuera de alcance por construcción (sin `decomposition.yaml`).

### R2.3 — HUMAN_QUALITY_GATE (commits `5f4000f`, `d036711`)
- Preparación de datos (SAFETY/GOVERNANCE por sección, 9 métricas AUDIT QUALITY, paquete
  específico `sec-0005`, muestra etiquetada de 27 pares requisito×evidencia).
- Adjudicación de Capa 9: 2/27 pares = `RELEVANT` (2 falsos negativos confirmados del Relevance
  Model, en `sec-0005`); 25/27 = `INCONCLUSIVE` (incluye la única evidencia que sí entró al
  Composer en `sec-0016`, ahora adjudicada como no-relevante); rúbrica de `sec-0016`: 3/5 en las
  5 dimensiones humanas (umbral existente ≥4/5, sin cambio).
- **Resultado:** `evidence_relevance_accuracy = 0.0 precisión / 0.0 recall`.
  `AUDIT_QUALITY = FAIL`.

---

## 3 · Qué funcionó (sin reservas)

1. **Fail-closed en todos los niveles, sin una sola excepción medida.** 0 LLM tras Q-STATE en
   toda la ejecución. 0 mutaciones de L2/`human_state`/`decomposition.yaml` verificadas por hash
   en cada fase. 0 hits de blacklist. El sistema nunca fabricó evidencia ni declaró
   cumplimiento.
2. **El defecto original de `sec-0016` (SCOPE_DRIFT) está genuinamente resuelto** — confirmado
   dos veces con salida real de LLM (no solo con el filtro teórico), y sobrevivió a la
   re-ejecución completa tras el fix de integridad.
3. **El mecanismo de gobernanza (ADDENDUM vía `governance_service`, propose→confirm,
   append-only) funcionó exactamente como en el precedente v2→v3** — trazabilidad intacta en
   las 4 nuevas entradas del ledger, ninguna edición manual, ninguna entrada previa tocada.
4. **El defecto de integridad de artefactos (test dry-run sobrescribiendo la corrida real) se
   detectó, se diagnosticó con precisión y se corrigió dentro del mismo arco**, sin necesidad de
   repetir fases ya cerradas ni de perder ninguna decisión de gobernanza ya tomada.
5. **La reconciliación de `sec-0026`/`sec-0042` como "fail-closed válido"** resolvió
   correctamente una contradicción real del plan original (regenerar 7 secciones vs. no inventar
   `decomposition.yaml`) sin comprometer ninguna regla.

## 4 · Qué falló / qué quedó abierto

1. **`evidence_relevance_accuracy = 0.0/0.0`** — de 27 candidatos, el único que el modelo dejó
   pasar (`PARTIALLY_RELEVANT`, la evidencia de `sec-0016`) fue adjudicado por Capa 9 como
   `INCONCLUSIVE` (falso positivo); los 2 candidatos que Capa 9 confirmó como genuinamente
   relevantes (`sec-0005`, "electronic signature", sub-criterios sc1/sc2) el modelo los excluyó
   (falsos negativos).
2. **Cobertura real de la corrida: 1 de 7 secciones produjo una narrativa.** 4 de 5 secciones
   elegibles no llegaron ni a invocar el LLM (relevancia vacía). Es una caída drástica frente a
   v3 (6 RENDERED / 1 SAFE_MODE sobre las mismas 7 secciones).
3. **Calidad de la única narrativa producida: 3/5 en las 5 dimensiones de rúbrica humana**,
   por debajo del umbral ≥4/5 ya vigente desde v1.2 — "adecuada pero no publicable", no un
   fallo catastrófico, pero tampoco un PASS.
4. **2 iteraciones de error propio (no del diseño) en el gate de scope** — el primer ADDENDUM
   fue redactado con terminología de fases del diseño v2.0 en vez del token literal que el
   chequeo heredado de v1.2/v1.3 exige, causando una remediación adicional evitable.
5. **1 defecto de integridad de artefactos** (tests dry-run sobrescribiendo la corrida real) —
   detectado y corregido, pero significa que la primera versión reportada de los resultados de
   R2.2 fue, brevemente, incorrecta (reportaba `SAFE_MODE`/0 LLM en `sec-0016` cuando la corrida
   real había dado `RENDERED`/1 LLM) antes de la corrección.

## 5 · Decisión ya tomada sobre el camino de remediación (no ejecutada)

Determinación técnica registrada en esta sesión (sin ejecutar, pendiente de autorización): **no
tocar el Relevance Model ni el prompt del Composer todavía** — la muestra es demasiado pequeña
(n=3 puntos de discrepancia sobre 27 pares, n=1 narrativa evaluada) para diagnosticar cuál de
los dos componentes es la causa, y ajustar cualquiera de los dos ahora sería sobreajustar a 1-3
casos. Camino recomendado: ejecutar **R4** (fixture de benchmark expandido, diseño §12 —
"evidencia irrelevante pero semánticamente similar" es exactamente el patrón de
`sec-0016`/`sec-0005`), preferiblemente con autor independiente, antes de tocar código. Ver
`01_DIAGNOSTICO_COMPLETO.md` §4 para el detalle.

## 6 · Contenido de esta carpeta

```
00_INSTRUCCIONES_ORIGEN/   documentos de diseño y de ejecución (Capa 9), tal como se recibieron
01_ARTEFACTOS_R1/          reporte + verificación retroactiva de R1
02_ARTEFACTOS_R2_GATE/     scope check, ADDENDA (propose + resultado), firma del prompt, gate recheck
03_ARTEFACTOS_R2_EJECUCION/ corrida real, HUMAN_QUALITY_GATE, muestra etiquetada, veredicto final
04_CODIGO/                 los 7 módulos nuevos de esta ronda (Relevance Model, contrato
                           requirement-centric, ADDENDA, prompt v2.0, runner de R2)
05_TESTS/                  los 6 archivos de test nuevos/modificados
01_DIAGNOSTICO_COMPLETO.md  análisis de causa raíz de cada hallazgo, para la mesa de diseño
```

Todo el código y los artefactos permanecen también en su ubicación original
(`factory/regulatory/shadow/`, `factory/tests/`, `docs_plan/shadow_llm/CF6/`) — esta carpeta es
una copia de trabajo consolidada para la mesa de diseño, no reemplaza la fuente de verdad del
repositorio.
