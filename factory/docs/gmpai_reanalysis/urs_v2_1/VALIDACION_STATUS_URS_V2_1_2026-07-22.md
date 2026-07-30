# Validación de status — corrida exploratoria URS v2.1

**Fecha:** 2026-07-22
**Alcance:** verificación línea por línea del status recibido contra código y
evidencia real del repo (no contra memoria/supuestos).

## Veredicto general

**CONFIRMADO — las 8 afirmaciones son correctas**, sustentadas en evidencia
verificable. Ninguna requiere corrección.

## Verificación por afirmación

| # | Afirmación | Veredicto | Evidencia |
|---|---|---|---|
| 1 | Ollama no tiene acceso directo a internet | ✅ Confirmado | `factory/engines/gmpai_integrity/ollama_client.py`: único cliente es `httpx` hacia `OLLAMA_BASE_URL` (local, `/api/generate`, `/api/tags`, `/api/version`). Sin `requests`/`urllib`/fetch externo en el motor. |
| 2 | Ollama no busca ni descarga regulaciones | ✅ Confirmado | Mismo archivo: el modelo solo recibe texto ya extraído del chunk (`chunk["text"]`) vía prompt; no hay ninguna llamada de red saliente distinta a la API local de inferencia. |
| 3 | Fuentes regulatorias gestionadas por componentes separados | ✅ Confirmado | `factory/regulatory/sources/sha256/...` (PDFs oficiales con hash), `evidence_verifier.py` (anclaje), `applicability_matrix` (mapeo requisito↔tipo doc) — todos módulos independientes del cliente Ollama. |
| 4 | 121 llamadas, principalmente `requirement_id`/descripciones breves, no texto regulatorio canónico completo | ✅ Confirmado | `URS_V2_1_BASELINE_AUDIT_SANITIZED.md:32-37`: run `w5v3-validation-2dbce2f4fb42`, "121 llamadas, 11 requisitos aplicables × 11 chunks". Catálogo v1.0 usa `requirement_id` + descripción corta, no el texto íntegro de 21 CFR/Annex 11. |
| 5 | `evidence_verifier` verifica anclaje en el documento analizado, no que responda al requisito regulatorio | ✅ Confirmado | `evidence_verifier.py:1-11`: comparación de caracteres literal (exact/normalized/despaced/fuzzy≥0.93) contra el chunk fuente — es integridad de cita, no juicio de suficiencia regulatoria. La "relevancia temática" es heurística léxica separada (`RELEVANCE_THRESHOLD`) que solo marca revisión (`RELEVANCE_REVIEW_REQUIRED`), nunca certifica cumplimiento. |
| 6 | Pipeline v2 más profundo, calidad solo mejoró parcialmente | ✅ Confirmado | `URS_V2_1_BASELINE_AUDIT.md:322-332`: 2 mejoras sustantivas confirmadas (`21_CFR_11.10(d)`, `ANNEX11_9`), 6 mejoras de disciplina de proceso, 1 falso positivo probable (`ANNEX11_4`), 1 limitación compartida por ambas versiones (`21_CFR_11.10(e)`). `PIPELINE_QUALITY_IMPROVED = PARTIAL` (línea 391, literal en el archivo). |
| 7 | `ANNEX11_4` — falso positivo semántico: "Risk" en título de GAMP 5 interpretado como evidencia de gestión de riesgo | ✅ Confirmado | `URS_V2_1_BASELINE_AUDIT.md:178-183` cita textual verificada: `"...GAMP5 A Risk-Based Approach to Compliant GXP Computerized Systems"` — es un título de estándar referenciado, no una descripción de proceso de gestión de riesgo. Línea 388: `LIKELY_V2_FALSE_POSITIVES = 1 # ANNEX11_4 (fundado en coincidencia lexica marginal, no en evidencia sustantiva de riesgo)`. Estado revertido explícitamente a "adjudicación pendiente" hasta decisión de Cesar. |
| 8 | Baseline formal y documento corregido, pendientes | ✅ Confirmado | `URS_V2_1_BASELINE_AUDIT_SANITIZED.md:13-16`: `FORMAL_BASELINE_READY = false`, `REGULATORY_COMPLIANCE = NOT_DETERMINED`. Línea 392 del archivo confidencial: `SAFE_TO_USE_AS_BASELINE = NO`. No existe todavía generación de documento corregido para esta corrida (distinto del ciclo FS_v1.2, que sí llegó a v1.4 aprobado). |

## Notas adicionales encontradas durante la validación (no contradicen el status, lo refuerzan)

- Además de `ANNEX11_4`, quedan **25 `review_required` + 3 `rejected_by_verifier`** sin adjudicación humana — el status no los menciona explícitamente pero son parte del mismo bloqueo de "baseline formal pendiente".
- `REGULATORY_COMPLIANCE = NOT_DETERMINED` es una constante de gobernanza fija en `consolidated_evidence_report.py` (nunca calculada desde resultados del pipeline) — ninguna corrida futura, por bien que ejecute, puede autodeclarar cumplimiento. La decisión es siempre humana, consistente con el punto 8.
- El runner que ejecutó esta corrida (`w5v3-validation-2dbce2f4fb42`) no tenía commit propio al momento de la corrida; el checkpoint/resume/batch se commiteó después (`1c16686`, ver `URS_V2_1_BASELINE_AUDIT_SANITIZED.md:19-20`).

## Conclusión

El status es preciso y está respaldado 1:1 por evidencia real (código +
archivos de corrida, incluyendo el archivo confidencial con citas
literales). No se requiere ninguna corrección. Pendiente de decisión humana
(Cesar): adjudicar `ANNEX11_4` + los 25/3 registros antes de fijar esta
corrida como baseline formal.
