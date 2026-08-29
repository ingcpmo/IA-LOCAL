# QA40 — Plantilla de instrucciones de adjudicación (WP-E.4, conjunto A: precisión real) — SANITIZADA

> ✅ **Versionable.** Esta plantilla describe el **método**. **No** contiene texto de los
> documentos del cliente. El paquete operativo con los 40 casos y sus `anchored_quote`
> verbatim (`QA40_INSTRUCCIONES_ADJUDICACION_<fecha>.md`) y el worksheet
> (`factory/regulatory/pilot_run/adjudication/wpe4-qa-<fecha>.yaml`) son **LOCALES —
> no se versionan ni se hace push** (contienen `DOCUMENT_EGRESS` de contenido del cliente).

**Autoridad:** Capa 9 = Cesar · **Ejecuta:** QA / Validation humano (nunca la IA / un LLM).

---

## 0. Qué mide esta muestra y qué NO mide

- Es una muestra de **findings YA EMITIDOS** por el analizador V2 sobre el corpus real.
  `sample_type = EMITTED_FINDINGS_REVIEW`, `sample_size = 40`.
- Mide **`QA40_SAMPLE_PRECISION` / PPV** = TP / (TP + FP) sobre los casos evaluables de la
  muestra, más la proporción `COVERAGE_LIMITED`.
- **NO** mide `recall`, `FN` ni `TN`. Eso requiere el conjunto independiente
  `real_corpus_opportunities.yaml` (conjunto B) y, para especificidad, `negative_units`.

## 1. Alcance estadístico — declararlo correctamente

- `QA40_ESTIMAND = SAMPLE_PRECISION`. **No** es `GLOBAL_REAL_CORPUS_PRECISION`.
- La muestra es **determinista, estratificada por `(finding_class, subtype)` y sobre-muestrea**
  los findings `would_degrade` y los subtipos de población pequeña (se toman completos).
  Los subtipos de población grande quedan sub-representados.
- Por tanto: `SAMPLING_IS_REPRESENTATIVE = NO`, `WEIGHTING_REQUIRED = YES`. Extrapolar al corpus
  completo exige **ponderación por post-estratificación** con las frecuencias reales de cada
  `(class, subtype)` en la corrida, más un tratamiento explícito del sesgo de `would_degrade`.
- `FIRST_QA40_RUN = POST_HARDENING_MEASUREMENT_BASELINE`. **No** es prueba comparativa PRE/POST:
  no hay muestra adjudicada equivalente del estado pre-hardening →
  `HARDENING_IMPROVEMENT_NOT_YET_DETERMINED`.

## 2. Umbral de aceptación

`REAL_PRECISION_ACCEPTANCE_THRESHOLD = NOT_PREDEFINED`. No hay un umbral de precisión sobre
corpus real fijado en `PLAN_HARDENING_ANALIZADOR_GMP_LOCAL_V2.md`, `ADR_HARDENING_V2.md` ni
`WP_E_INDEPENDENCIA_MEDICION_20260828.md`. Los gates `*_FALSE_POSITIVE ≤ 5 %` de
`PLAN_VALIDACION` son `SYNTHETIC_ONLY` y no transfieren. El gate de WP-E («umbrales fijados
antes de los resultados») aplica al held-out firmado (WP-E.3). **No inventar un umbral.**
El resultado se entrega en `metric_envelope` (Wilson + `contamination_statement`) y **Capa 9
decide** sobre el rango.

## 3. Esquema de cada caso (worksheet YAML — campos)

| Campo | Origen | Rol en la adjudicación |
|---|---|---|
| `case_id` | analizador | id determinista del caso (`ADJ-…`) |
| `finding_id` | analizador | id del finding emitido |
| `document` | analizador | id interno del documento (p. ej. `RW-00xx`) |
| `page` | analizador | página del documento |
| `finding_class` | analizador | clase del finding |
| `subtype` | analizador | subtipo del finding |
| `anchored_quote` | analizador | **texto verbatim del documento** (por eso el paquete es local) |
| `evidence_basis` | analizador | `PRESENCE` \| `ABSENCE_DEPENDENT` \| `INDETERMINATE` (contexto) |
| `coverage_status` | analizador | `OK` \| `MISSING` (contexto) |
| `would_degrade` | analizador | `true` \| `false` (contexto; WP-B) |
| `label` | **QA** | `TP` \| `FP` \| `COVERAGE_LIMITED` — nace `PENDING` |
| `adjudicator_note` | **QA** | justificación breve; sección/frase citada |

`evidence_basis`, `coverage_status`, `would_degrade` son **contexto**, no la decisión de QA
(pero `MISSING` / `would_degrade=true` suelen ser candidatos a `COVERAGE_LIMITED` — verificar,
no asumir).

## 4. Etiquetas permitidas (exactamente una por caso)

| Etiqueta | Cuándo |
|---|---|
| `TP` | El finding es correcto: el documento en esa página realmente presenta la condición que afirma y la cita anclada la respalda. |
| `FP` | El finding es incorrecto: el control sí está, la cita no respalda la afirmación, o se malinterpreta el pasaje. |
| `COVERAGE_LIMITED` | El finding no es sólidamente evaluable en este corpus (depende de la mitad de prueba vacía / documento `NOT_ANALYZABLE`). Se excluye del numerador y del denominador; se reporta aparte. |

**Prohibido:** `FN` o `TN` (el scorer `score_emitted_review()` falla cerrado). Dejar casos sin
etiqueta al firmar. Usar IA/LLM para decidir `TP`/`FP`/`COVERAGE_LIMITED`.

## 5. Procedimiento

1. Verificar la integridad de la muestra (SHA de los 40 `finding_id`, `sample_type`,
   `sample_size = 40`, `label_options = [TP, FP, COVERAGE_LIMITED]`, `PENDING = 40`,
   `adjudicator = null`). Si el SHA no coincide → **detenerse**, la muestra fue alterada.
2. Por cada caso: abrir `document` en `page`, localizar el pasaje de `anchored_quote` y su
   contexto, decidir si el finding es correcto **en ese punto**, escribir `label` y
   `adjudicator_note`.
3. Al terminar los 40: `adjudicator: "<nombre/rol>"`, `adjudicated_at: <fecha>`,
   `status: SIGNED`.

### Ejemplo de caso (con el texto del cliente REDACTADO)

```yaml
- case_id: ADJ-XXXXXXXXXX
  finding_id: fnd-XXXXXXXXXXXXXXXX
  finding_class: <Clase>Finding
  subtype: <SUBTYPE>
  document: RW-00XX
  page: <n>
  evidence_basis: ABSENCE_DEPENDENT        # contexto
  would_degrade: false                     # contexto
  coverage_status: OK                      # contexto
  anchored_quote: "<REDACTED — texto verbatim del documento; ver paquete local>"
  label: PENDING                           # <- QA: TP | FP | COVERAGE_LIMITED
  adjudicator_note: ""                     # <- QA: justificación; sección/frase citada
```

## 6. Al completar la adjudicación

`score_emitted_review("<worksheet local>.yaml")` → `PRECISION_REPORTABLE`
(= `QA40_SAMPLE_PRECISION`, Wilson o `UNKNOWN`), `proportion_coverage_limited`,
`metric_envelope`. `RECALL_REPORTABLE` queda `UNKNOWN` por diseño de esta muestra.
Para una precisión global del corpus: aplicar ponderación por post-estratificación (fuera del
alcance de esta corrida).

No activar WP-B ENFORCE. No firmar WP-F. No OCR. No tocar los archivos de drift.
