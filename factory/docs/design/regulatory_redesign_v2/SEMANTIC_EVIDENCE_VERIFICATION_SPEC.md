# SEMANTIC_EVIDENCE_VERIFICATION_SPEC

## 1. Cuatro validaciones independientes

```
A. DOCUMENT_ANCHOR_VERIFICATION
   La cita existe literalmente en el documento original, anclada a
   página/sección/tabla/celda. (Evolución de evidence_verifier.py actual:
   comparación exact/normalized/despaced/fuzzy≥0.93, confirmado en
   evidence_verifier.py:1-11 de la sanitización del reporte URS v2.1.)

B. REGULATORY_SOURCE_VERIFICATION
   El requisito, numeral y texto invocados existen en la copia canónica
   verificada (match contra canonical_text + clause del Evidence Pack).

C. SEMANTIC_REQUIREMENT_VERIFICATION
   La evidencia responde realmente al requisito. La LLM asiste, pero
   reglas deterministas rechazan automáticamente:
   - weak_keywords aisladas;
   - menciones en listas de referencias/estándares (regla ANNEX11_4);
   - contenido fuera de contexto;
   - criterios de exclusión activados;
   - evidencia de otro documento;
   - inferencias sin soporte.
   Discrepancia regla-vs-LLM ⇒ SUPPORTING_EVIDENCE_UNDER_REVIEW (nunca
   aprobación).

D. SUFFICIENCY_VERIFICATION
   Cada evidence_min_criteria clasificado MET | NOT_MET | NOT_ASSESSABLE,
   con anclaje individual.
```

Evidencia sustantiva aceptada ⇔ A ∧ B ∧ C ∧ D.

## 2. Golden Dataset mínimo (pruebas negativas obligatorias)

| Caso | Entrada | Resultado esperado |
|---|---|---|
| ANNEX11_4 (real, confirmado en corrida URS v2.1) | "GAMP5 A Risk-Based Approach" en lista de referencias | FAIL en C; jamás `DOCUMENTED_AND_SUPPORTED` |
| Cita inventada | Texto que no existe literalmente en el documento | FAIL en A |
| Evidencia de otro archivo | Hash de documento no coincide | FAIL en A |
| Numeral inexistente | Clause no está en el `canonical_text` | FAIL en B |
| Evidencia parcial | Solo algunos `evidence_min_criteria` MET | FAIL en D ⇒ máximo `PARTIALLY_DOCUMENTED` |
| Contradicción entre secciones | Dos fragmentos del mismo documento se contradicen | contradicción abierta, bloquea conclusión positiva |
| Cobertura incompleta | No se procesaron todos los chunks relevantes | `EVALUATION_INCOMPLETE`, nunca `DOCUMENTATION_GAP` |
| Evidencia fuera de contexto | Fragmento correcto pero de sección no relacionada | FAIL en C |

Este Golden Dataset es también la base del Model Qualification Gate
(`MODEL_PROVIDER_AND_LOCAL_AI_RUNTIME_SPEC.md` sección 6) y debe ejecutarse
en cada cambio de modelo, prompt_version o schema_version.

## 3. Salida estructurada de la LLM

Toda llamada devuelve JSON validado por schema. Campos mínimos:
`assessment`, `evidence_quote`, `evidence_location`, `matched_criteria`,
`unmet_criteria`, `exclusion_criteria_triggered`,
`semantic_reasoning_summary`, `contradictions`, `confidence_band`,
`proposed_next_state`, `limitations`.

Reglas:
- No solicitar ni almacenar cadena privada de razonamiento (chain-of-
  thought oculto).
- `semantic_reasoning_summary`: breve, verificable, apto para auditoría.
- Salida inválida ⇒ `LLM_OUTPUT_INVALID` → **UN único** intento de
  reparación → `EXCEPTION_REQUIRED` si falla de nuevo.
- `proposed_next_state` es una **propuesta**; solo los validadores
  deterministas emiten estados terminales.

## 4. Estado actual reutilizable y brecha

`app/llm_integrity_engine.py:76-79,159-163` ya implementa el patrón de
"exigir anclaje literal o descartar" (validación A parcial). No implementa
B (verificación contra fuente regulatoria canónica — hoy no hay Evidence
Pack), ni la regla determinista explícita anti-ANNEX11_4 en C (hoy depende
de heurística léxica de relevancia, `RELEVANCE_THRESHOLD`, que solo marca
revisión, no rechaza), ni D por criterio individual. El motor más maduro,
`factory/engines/gmpai_integrity/chunked_engine.py:250`
(`evaluate_chunked()`), se acerca más al contrato pero no está wireado a
producción (confirmado: `verified_pipeline.py:16-30`).

## 5. Función determinista vs. función LLM (separación estricta)

Deterministas: A (comparación de caracteres), B (match contra texto
canónico), reglas de exclusión de C (listas fijas de weak_keywords y
patrones de "lista de referencias"). LLM: razonamiento semántico de C
cuando no hay regla de exclusión aplicable, y evaluación cualitativa de D
por criterio. Ninguna LLM emite el estado terminal por sí sola.
