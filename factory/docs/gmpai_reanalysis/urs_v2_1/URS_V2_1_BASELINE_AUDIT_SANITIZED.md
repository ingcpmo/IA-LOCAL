# Baseline URS v2.1 — auditoría de solo lectura (versión sanitizada, sin citas literales)

**Clasificación:** apta para repositorio (no contiene `evidence_quote`,
`rationale` ni ningún texto extraído del documento Rockwell — solo
identificadores, números de página/chunk y conclusiones agregadas). La
versión completa con citas literales vive en
`factory/regulatory/validation_evidence/URS_V2_1_BASELINE_AUDIT.md`
(gitignored, `INTERNAL_VALIDATION_EVIDENCE`, nunca commitear).

**Estado de la corrida:**

```
EXPLORATORY_VALIDATION_RUN
FORMAL_BASELINE_READY = false
REGULATORY_COMPLIANCE = NOT_DETERMINED
```

Resultados conservados intactos (no modificados, no reejecutados), pero
**no usados todavía como referencia formal** — pendientes de: (1) código
versionado y commiteado (ya cerrado, commit `1c16686`), (2) adjudicación de
`ANNEX11_4`, (3) resolución humana de los 25 `review_required` + 3
`rejected_by_verifier`. `REGULATORY_COMPLIANCE = NOT_DETERMINED` es una
constante de gobernanza (nunca calculada desde los resultados del
pipeline, ver `consolidated_evidence_report.py`) — ninguna corrida, sin
importar cuántos requisitos verifique, puede por sí sola declarar
cumplimiento regulatorio. Esa decisión es siempre humana.

## Identidad de la corrida (resumen no confidencial)

- Documento: `215115305 SCADA-PCS Misc PLC System URS v2.1.pdf`, SHA-256
  `d9e24467a66d52fb1a641b6de901ceff1dcdaf66af1ae80cb94a433c40c939c8`.
- run_id `w5v3-validation-2dbce2f4fb42`, 121 llamadas, 11 requisitos
  aplicables × 11 chunks.
- Modelo `qwen2.5:7b-instruct-q4_K_M`, digest
  `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`,
  Ollama `0.21.2`.
- Catálogo `v1.0` (19 requirement_id), matriz de aplicabilidad `v2.0`
  (aprobada, `MC-0001`, Cesar, 2026-07-17).
- **El runner ejecutado NO tiene commit propio todavía** (funcionalidad de
  checkpoint/resume/batch en working tree, ver informe de reproducibilidad
  para el detalle del diff y el commit propuesto).

## Conteos (ver detalle completo en el archivo confidencial)

- 11/19 requisitos aplicables a `URS`; 8/19 no mapeados
  (`APPLICABILITY_REVIEW_REQUIRED`, sin llamadas).
- 93 `verified` / 25 `review_required` / 3 `rejected_by_verifier` (121 total).
- 0 requisitos alcanzaron `DOCUMENTATION_GAP` en esta corrida.

## Adjudicación pendiente — ANNEX11_4

La conclusión `DOCUMENTED_AND_SUPPORTED` para `ANNEX11_4` (gestión de
riesgo del sistema computarizado) está **suspendida, no confirmada**. La
única cita que pasó verificación coincide literalmente con el texto fuente
(anclaje real, no fabricado) pero su relevancia temática pasó el umbral por
una única coincidencia léxica de baja especificidad, dentro de una lista de
estándares referenciados por el documento, no dentro de una descripción de
un proceso de gestión de riesgo del sistema en sí. **Regla aplicada en esta
auditoría: una coincidencia léxica marginal, aislada, dentro de un título
de estándar referenciado NO constituye evidencia suficiente de que el
proceso regulatorio exigido (gestión de riesgo) esté documentado.**
`DOCUMENTED_AND_SUPPORTED` para este requisito queda **revertido a
adjudicación pendiente** hasta que Cesar confirme o rechace explícitamente
si esa cita basta como evidencia.

## Registros pendientes/rechazados (25 + 3)

Ver tabla completa por `requirement_id`/chunk/página/causa en el archivo
confidencial (`URS_V2_1_BASELINE_AUDIT.md`, §5) y en
`URS_V2_1_PIPELINE_COMPARISON.json` (`review_required_pattern`,
`rejected_records`). Resumen: 24/25 `review_required` comparten causa raíz
(relevancia léxica insuficiente sobre 2 fragmentos genéricos reciclados,
páginas ~4-5 y ~21); los 3 `rejected_by_verifier` son citas cuyo texto no
ancla literalmente en el chunk real (posible paráfrasis del modelo),
concentradas en 2 chunks (páginas 8 y 17). Ninguno bloqueó una conclusión
de ausencia documental porque ningún requisito de esta corrida llegó a esa
rama de consolidación.

## Próximos pasos (gates, ver informe de reproducibilidad para el detalle)

No se repetirán las 121 llamadas hasta que: el runner esté commiteado y el
repositorio limpio, el driver no dependa del scratchpad, `ANNEX11_4` tenga
regla o adjudicación explícita, y el fingerprint de la corrida (documento +
commit + modelo + digest + prompt + schema + catálogo + matriz +
parámetros) se declare completo desde el inicio.
