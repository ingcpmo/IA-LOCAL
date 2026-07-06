# W6.5 Fase D — Cierre técnico del experimento de calidad (Agent Expert Review con LLM real)

Fecha de cierre: 2026-07-06 · Decisión de cierre: Cesar (reject de v6 auditado)
Documento bajo prueba: `data_integrity_assessment` · Misión: `oos_hplc_investigator`
Prompt set gobernado: 1.0.1 · Template SHA-256: `f577ef530475dbf1c1be4207706429877ab83852f20a938bef3eb34330451d94`

## 1. Objetivo de Fase D

Ejecutar por primera vez el pipeline Agent Expert Review (W6.5 Fases B/C, hasta
entonces probado solo con httpx mockeado) contra un LLM real servido por Ollama
(CPU, host systemd), y evaluar si un modelo 7B local puede producir propuestas
de análisis experto QA/GMP que superen el contrato de formato, el verificador
determinista y la revisión humana.

## 2. Qué quedó demostrado end-to-end

Con 6 versiones de propuesta archivadas y 2 ciclos completos humano→agente:

- Generación real vía Ollama con gobierno completo por propuesta: modelo,
  options (num_predict/temperature/num_ctx), versiones de prompt, template y
  rendered SHA-256, trigger con principal humano, latencia, retry de formato.
- Fallo gobernado: timeouts y formato inválido quedan archivados (propuesta
  inutilizable visible, documento intacto) y auditados
  (`dossier_agent_proposal_failed`), incluido el guard anti-truncado 413
  `prompt_too_long` previo a la llamada.
- Verificador determinista clasificando claims contra el evidence bundle real
  (supported/partially/unsupported/unverifiable) y confianza SIEMPRE computada.
- Decisión humana con nombre real: `request_changes` con guidance que se
  inyecta como instrucción prioritaria y regenera nueva versión (v4→v5, v5→v6),
  y `reject` con motivo técnico (v6). Todo auditado
  (`dossier_agent_proposal_decision`).
- Aislamiento de configuración: cambio de modelo vía `FACTORY_OLLAMA_MODEL`
  solo en factory-api (env_file), verificado sin impacto en gmp-api,
  oos_hplc_investigator_api ni lab_qc_project_api (siguen en mistral).

## 3. Resultado de Mistral (`mistral:7b-instruct-q4_K_M`) — v1–v3

| Corrida | Fecha (UTC) | Condiciones | Resultado |
|---|---|---|---|
| (previas a v1) | 2026-07-03 21:25 y 22:12 | num_ctx default 4096 → truncado silencioso del inicio del prompt (contrato + anti-injection) | 2× `ollama_timeout` auditados, sin propuesta |
| v1 | 2026-07-03 22:44 | truncado aún presente | `format_invalid` |
| v2 | 2026-07-06 18:57 | fix activo: num_ctx 8192, sin truncado; prompt 1.0.0 | `format_invalid` — 0 claims etiquetados, plantilla vacía repetida ~8×, corte en num_predict; 17.7 min, 2 pasadas |
| v3 | 2026-07-06 19:46 | prompt 1.0.1 (few-shot + regla de brevedad) | `format_invalid` — copió el ejemplo few-shot VERBATIM 8× (incluido el placeholder), degeneró (perdió `[` de `[SE]`), repetición 0.79, truncado sin `## Limitaciones`; claims 0/2/6/11; 18.5 min, 2 pasadas |

Conclusión: mistral 7B q4 no puede con la tarea. Ni contexto completo ni
few-shot cambian el desenlace; el few-shot demostró que puede emitir la
sintaxis pero loretea en vez de analizar.

## 4. Resultado de Qwen (`qwen2.5:7b-instruct-q4_K_M`, id 845dbda0ea48) — v4–v6

| Corrida | format_valid | Claims (sup/parc/unsup/unverif) | Confianza | Flags | Duración |
|---|---|---|---|---|---|
| v4 (sin guidance) | SÍ, 1ª pasada | 3 (0/3/0/0) | media | — | 6.7 min |
| v5 (request_changes #1) | SÍ, 1ª pasada | 8 (0/1/1/6) | baja | unsupported_claims | 7.0 min |
| v6 (request_changes #2) | SÍ, 1ª pasada | 8 (0/2/0/6) | media | — | 7.1 min |

Las tres versiones: sin retry, repetición 0.00, sin truncado, cierre con
`## Limitaciones`, uso real de la evidencia citada. v6 rechazada por Cesar
(motivo técnico auditado: regresiones semánticas, ver §7).

## 5. Comparación objetiva Mistral vs Qwen (misma tarea, mismo prompt 1.0.1, mismo verificador)

| Métrica | Mistral v3 | Qwen v4 |
|---|---|---|
| format_valid | NO (2 pasadas) | SÍ (1 pasada) |
| Duración | 18.5 min | 6.7 min (2.8× más rápido) |
| Repetición (1−únicas/líneas) | 0.79 | 0.00 |
| Truncado | Sí | No |
| unsupported | 6 | 0 |
| Uso de evidencia | nulo (copia del ejemplo) | real (catalog, runs, audit) |
| Confianza computada | baja | media |
| Evento auditado | proposal_failed | proposal_generated |

## 6. Correcciones aplicadas por cada request_changes

**v4→v5** (guidance: 3 puntos de Cesar):
1. Firmas electrónicas ya no se afirman: pasan a `[SE]` sin evidencia ✓
2. Distinción catálogo-de-pruebas vs evidencia-de-cumplimiento corregida ✓
   (la claim negativa verdadera quedó `unsupported` — artefacto del verificador
   con negaciones, no invento del modelo)
3. Una afirmación etiquetada por viñeta ✓ (8 claims parseables vs 3)

**v5→v6** (guidance: disciplina de citas de Cesar):
1. Desapareció §11.30 (cita errónea: es sistemas abiertos) ✓
2. §11.10(e) y §11.10(k) usados correctamente ✓
3. Subparte C citada sin numeral específico ✓
4. FDA Data Integrity Guidance 2018 sin numeral inventado ✓ (aunque no añadió
   la marca literal "SIN REFERENCIA VERIFICABLE" pedida)
5. Sin referencias nuevas fuera del contexto autorizado ✓

## 7. Regresiones aparecidas tras cada corrección

- **v5** (tras corregir contenido): citas normativas erróneas/inventadas —
  §11.30(a)/(c) no aplican; "§3.4" de la guía 2018 inventado (fuente ni
  siquiera disponible en corpus).
- **v6** (tras corregir citas): (a) reafirma que "los atributos ALCOA+ están
  presentes en la mayoría de las ejecuciones" citando el catálogo — la
  conflación que v5 ya había corregido; (b) `[SE]` factualmente FALSO: "no hay
  evidencia de aprobaciones humanas" cuando el bloque `audit` del propio prompt
  contiene 7 eventos `validation_doc_approved · por Cesar`.

## 8. Evidencia del patrón de inestabilidad semántica

Cada iteración corrigió el 100% de lo instruido y rompió algo previamente
correcto (patrón whack-a-mole):

```
dimensión           v4        v5        v6
formato             ✓         ✓         ✓
e-firma como [SE]   ✗         ✓         ✓
catálogo≠cumplim.   ✗         ✓         ✗   ← regresión
1 claim/viñeta      ✗         ✓         ✓
citas normativas    n/a       ✗         ✓
[SE] factuales      ✓         ✓         ✗   ← regresión nueva
```

Tres iteraciones bastan para establecer el patrón: el conjunto de restricciones
simultáneas (formato + evidencia + citas + negaciones factuales + distinciones
GMP finas) excede la capacidad de retención del modelo 7B cuando la guidance
enfoca su atención en un subconjunto.

## 9. Limitación conocida (declarada)

**Qwen 7B puede producir propuestas estructuralmente válidas y usar evidencia
real, pero no demostró estabilidad suficiente para mantener simultáneamente
todas las restricciones QA/GMP bajo iteraciones sucesivas.**

## 10. Estado declarado de los componentes

- **Pipeline** (generación→verificación→decisión→regeneración): **FUNCIONAL**
- **Gobierno** (prompts versionados SHA-256, options registradas, trigger
  humano, guard anti-truncado, aislamiento de modelo por env): **FUNCIONAL**
- **Auditoría** (generated/failed/decision, cadena SHA-256 append-only):
  **FUNCIONAL**
- **Verificador**: **FUNCIONAL con limitaciones conocidas** — (a) claims
  negativas verdaderas pueden quedar `unsupported` (no ancla negaciones);
  (b) `[SE]`/`[REF:]` son `unverifiable` por diseño: no detecta negaciones
  factualmente falsas ni citas normativas erróneas — eso permanece en el
  revisor humano; (c) si el modelo agrupa claims en una línea solo cuenta la
  primera.
- **Calidad experta estable**: **NO DEMOSTRADA** con modelos 7B locales en CPU.

## Consecuencia arquitectónica

El análisis post-cierre (aprobado por Cesar 2026-07-06) identificó que el
patrón del §8 tiene un amplificador arquitectónico propio (regeneración desde
cero sin el texto anterior ni ledger de guidances) además del techo de
capacidad del modelo. La corrección queda formalizada como **gate obligatorio
previo a W7**: `W6_5_1_GATE_REVISION_DIRIGIDA.md` (modo revisión + verificador
v2, con las propuestas v01–v06 como fixtures de regresión).

## Registro

- Propuestas archivadas: `factory/validation/oos_hplc_investigator/agent_proposals/data_integrity_assessment/v01–v06.json`
- Decisiones auditadas: v4 `request_changes`, v5 `request_changes`, v6 `reject`
  (todas por Cesar, con motivo)
- Estado final del documento: `needs_human_review`, contenido intacto (ninguna
  propuesta fue aceptada)
- Baseline y comparativa de la sesión: `baseline_mistral_v3.json`,
  `comparativa_mistral_vs_qwen_dia.md` (scratchpad de sesión; este documento
  es el registro permanente)
