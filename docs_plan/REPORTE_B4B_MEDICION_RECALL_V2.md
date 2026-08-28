# Reporte B4b — medición real del recall V2 (fixture 7P+2N)

**Fecha:** 2026-08-27. **Autoridad:** Capa 9 = Cesar.
**Autorización:** `PILOT_EXECUTION-2026-032` (`human_confirmed` por Cesar, `max_calls` 280).
**Run:** `b4b-20260827T201816Z`. **Prompts:** juicio V2 firmados (`prompt_version 1.0`, variante estricta).
**Instrumento:** fixture 7P+2N (`W5V2_RECALL_FIXTURE_SET_DRAFT.md`), sin re-etiquetar, sin relajar ningún validador.

---

## 1. Resultado

```
stop_reason:          COMPLETE   (203 / 280 llamadas)
DOCUMENT_EGRESS:      0 bytes    (corrida completa bajo network_locked)
REGULATORY_POSITIVE:  0/7        ← ningún positivo anclado
REGULATORY_NEGATIVE:  2/2        (N1 GAMP5 y N2 TOC correctamente NO anclados)
FABRICATED_CITATIONS: 0
SCHEMA_VALID_RATE:    9/9 = 100%
LATENCIA:             registrada (56 s – 190 s por unidad)
```

**Interpretación (`gates.interpret_regulatory`, criterio pre-fijado, PLAN_VALIDACION §2.1):**
> `TECHO_NO_CRUZADO` — adoptar Palanca C (Tier-1) permanente para la clase Regulatory; no degradar validadores.

## 2. Desglose por sub-criterio (56 en total)

| Estado | # | Significado |
|---|---|---|
| `EVIDENCE_NOT_FOUND` | 30 | el paso B respondió `NO` |
| `INCONCLUSIVE` | 20 | el paso B respondió `UNCLEAR` |
| `MACHINE_CONFIRMED` | **0** | — |
| `MACHINE_PARTIAL` | **0** | — |
| `MACHINE_REJECTED` | **0** | — |

`rejected_count = 0` en las 9 unidades: **el verificador nunca rechazó una cita, porque el paso
B nunca dijo `SATISFIES` ni `PARTIAL` ni una sola vez.** Ni siquiera en P1 (LEXICAL_ECHO, el
pasaje de audit trail casi verbatim — el único caso que ancló en H2/H4 y R2).

| unidad | req | sub-crit | anclado | estados |
|---|---|---|---|---|
| P1 | 21_CFR_11.10(e) | 9 | NO | 5 UNCLEAR, 4 NO |
| P2 | 21_CFR_11.10(g) | 3 | NO | 2 UNCLEAR, 1 NO |
| P3 | ANNEX11_17 | 4 | NO | 2 NO, 2 UNCLEAR |
| P4 | ALCOA_ATTRIBUTABLE | 5 | NO | 5 NO |
| P5 | ALCOA_CONTEMPORANEOUS | 3 | NO | 3 NO |
| P6 | 21_CFR_211.68(b) | 7 | NO | 5 NO, 2 UNCLEAR |
| P7 | 21_CFR_211.68(b) | 7 | NO | 5 NO, 2 UNCLEAR |
| N1 | ANNEX11_4 (negativo) | 3 | NO ✓ | 2 UNCLEAR, 1 NO |
| N2 | 21_CFR_11.10(e) (negativo) | 9 | NO ✓ | 5 UNCLEAR, 4 NO |

## 3. Comparación con las mediciones previas

| Vía | Recall positivos |
|---|---|
| Baseline Piloto 1 | 0/7 |
| H1 (idioma) | 0/7 |
| H2 / H4 (desempaquetado + schema mínimo) | **2/7** |
| Palanca A (qwen2.5:14b) | 2/7 |
| V2 fusión (top_k) | 2/7 |
| R2 (fusión, pool perfecto) | 1/6 |
| **B4b — V2 completo (canónico + decomposition + juicio 2 pasos + Critic + reranker)** | **0/7** |

**El rediseño V2, medido por su propio instrumento, no cruzó el techo — lo empeoró.**

## 4. Causa (evidencia directa del run)

El fallo es íntegramente del **paso B en variante estricta**: juzga SOLO sobre la descripción
operativa neutra del paso A, sin ver nunca el pasaje. La descripción neutra del 7B pierde los
detalles específicos que mapean al sub-criterio; el paso B, con solo eso, responde `NO`/`UNCLEAR`.
El paso A (ver el pasaje) + paso B (no verlo) resultó **más lesivo** que el contrato de 1 sola
llamada de CURRENT, donde el modelo al menos veía el chunk completo. El Critic (solo degrada)
no pudo aportar porque no hubo veredicto positivo que evaluar.

Cinco vías independientes (H1-H4 · 14B · fusión · R2 · B4b) coinciden: **el 7B local no hace el
juicio semántico de paráfrasis**, y ninguna palanca de arquitectura probada lo mueve.

## 5. Qué SÍ quedó demostrado (positivo)

- **`DOCUMENT_EGRESS = 0`** en una corrida real de ~2 h con 203 llamadas a Ollama — el
  invariante central del rediseño LOCAL-ONLY se sostiene bajo carga real.
- **`FABRICATED_CITATIONS = 0`** — la variante estricta cumple: cero evidencia inventada.
- **`REGULATORY_NEGATIVE = 2/2`** — los negativos obligatorios se rechazan (GAMP5, TOC).
- **`SCHEMA_VALID_RATE = 100%`** — los 3 prompts firmados producen salida bien formada.
- El pipeline corrió de punta a punta, con checkpoints, dentro de presupuesto, sin errores.
- La infraestructura determinista de V2 (modelo canónico, grafo, taxonomía de 7 clases de
  finding, cadena de remediación verificada, harness de gates) es independiente de este
  resultado y sigue en pie.

## 6. Decisión requerida de Capa 9

Por el criterio pre-fijado (0/7 ≤ 2/7):

**(A) Adoptar Palanca C (Tier-1 de alcance reducido) permanente para la clase Regulatory** —
confirmación automática solo del eco léxico + rechazo de falsos positivos + recuperación
semántica al revisor; todo lo demás a revisión humana con cobertura declarada. Nunca
auto-aprobación. **Sin degradar ningún validador.** Es la contingencia ya escrita en el ADR §10.

**(B) Un experimento diagnóstico más, si lo autorizas** — re-correr B4b con la variante
**NO estricta** del paso B (el paso B ve los claims para citar, ya implementada en B4a antes de
la elección de B4a.1). Coste: otra `PILOT_EXECUTION` de ~200 llamadas. **Expectativa honesta:**
el juicio del paso B sigue anclado a la descripción neutra del paso A como insumo primario, así
que la ganancia esperada es baja; y cinco vías ya convergen en el techo del 7B. Es un last-ditch,
no una vía prometedora.

**(C) Las clases FUNCTIONAL / TECHNICAL (B6a) NO dependen de este resultado** — sus findings
salen del grafo determinista y de la taxonomía, no del juicio de paráfrasis. Su validación
(suites B/C, B8b) sigue abierta y separada.

---

*Ningún validador se relajó en esta corrida. El resultado se reporta tal cual.*

---

## 7. Experimento diagnóstico — variante NO ESTRICTA del paso B (autorizado por Cesar)

`PILOT_EXECUTION-2026-034` (`human_confirmed` por Cesar, `max_calls` 240).
Run `b4b-nonstrict-20260827T205418Z`, 205 llamadas, `COMPLETE`.
Prompt `step_b_criterion_mapping_nonstrict.yaml` firmado (`prompt_version 1.0`).
Diferencia: el paso B **sí ve la lista de claims** para poder producir una cita literal
(el juicio sigue sobre la descripción neutra del paso A; `evidence_verifier` valida la cita).

```
REGULATORY_POSITIVE:  0/7        ← igual que la variante estricta
REGULATORY_NEGATIVE:  2/2
FABRICATED_CITATIONS: 0
SCHEMA_VALID_RATE:    9/9 = 100%
DOCUMENT_EGRESS:      0 bytes
sub-criterios (56):  40 INCONCLUSIVE (paso B = UNCLEAR), 10 EVIDENCE_NOT_FOUND (paso B = NO)
                     0 SATISFIES · 0 PARTIAL · 0 rechazos del verificador
```

**Único efecto de dar los claims al paso B:** las respuestas se movieron de `NO` hacia
`UNCLEAR` (40 vs 20 en la estricta), pero **ni un solo `SATISFIES`/`PARTIAL`**. El mecanismo
de cita (estricto vs no estricto) **no es la causa** — la causa es que el 7B, juzgando sobre
la descripción operativa neutra del paso A, no compromete que ninguna descripción satisfaga
ningún sub-criterio regulatorio.

## 8. Conclusión consolidada — 6 vías independientes

| Vía | Recall positivos |
|---|---|
| H1-H4 (desempaquetado + schema mínimo) | 2/7 |
| Palanca A (qwen2.5:14b) | 2/7 |
| V2 fusión (top_k) | 2/7 |
| R2 (fusión, pool perfecto) | 1/6 |
| **B4b V2 estricto** | **0/7** |
| **B4b V2 no estricto** | **0/7** |

**El rediseño V2, cuyo objetivo era cruzar el techo, lo empeoró en ambas variantes.** El techo
del juicio semántico de paráfrasis del 7B local está confirmado por seis instrumentos distintos.
Ninguna palanca de arquitectura local probada lo mueve.

## 9. Decisión (contingencia pre-fijada, ADR §10 + R2.2 §1)

`REGULATORY_POSITIVE ≤ 2/7` ⇒ **Palanca C (Tier-1 de alcance reducido) PERMANENTE para la clase
Regulatory.** No es una propuesta nueva — es la contingencia ya firmada por Cesar. La medición
está hecha; la rama se toma:

- El analizador **no automatiza el juicio regulatorio de paráfrasis**. Para la clase Regulatory:
  confirmación automática solo de eco léxico anclado + rechazo de falsos positivos +
  recuperación semántica al revisor + **todos los sub-criterios `INCONCLUSIVE`/`EVIDENCE_NOT_FOUND`
  a revisión humana con cobertura declarada.** Nunca auto-aprobación. **Sin degradar ningún
  validador.**
- Lo que V2 SÍ aporta a ese Tier-1 asistido (todo determinista, todo commiteado): modelo
  canónico + claims normalizados, descomposición de requisitos firmada, `EvidenceBundle` por
  sub-criterio entregado al revisor, taxonomía de 7 clases de Finding, cadena de remediación
  verificada, `DOCUMENT_EGRESS = 0` verificado bajo carga real (2 corridas de ~40 min, 410
  llamadas, cero egress).
- Las clases **FUNCTIONAL / TECHNICAL** son independientes de este resultado (salen del grafo
  determinista y de la taxonomía, no del juicio de paráfrasis). Su validación (suites B/C, B8b)
  sigue abierta.

*Ningún validador se relajó en ninguna de las dos corridas.*
