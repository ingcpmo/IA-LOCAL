# Piloto A — Informe de cierre parcial

**Documento:** `215115305 SCADA-PCS Misc PLC System URS v2.1.pdf`
**SHA-256:** `d9e24467a66d52fb1a641b6de901ceff1dcdaf66af1ae80cb94a433c40c939c8`
**Run:** `chunked-2620c651fe29` (agente `alcoa_plus_agent`)

## 1. Resultado por agente

| Agente | Chunks OK | Findings | Contradicciones |
|---|---|---|---|
| fda_part11_agent | 10/10 | 5 | 0 |
| eu_annex11_agent | 10/10 | 5 | 0 |
| alcoa_plus_agent | **8/10** | 9 | 0 |

## 2. Gap de cobertura — alcoa_plus_agent

- **Chunks fallidos:** 5 (pág 12-13), 8 (pág 19-21)
- **Intentos por chunk:** 2 (ejecución original + 1 reintento selectivo, sin repetir los 7 chunks ya OK del run inicial)
- **Error:** `invalid_json_model_output` — el modelo (`qwen2.5:7b-instruct-q4_K_M`) no devolvió JSON parseable en ninguno de los 2 intentos para esos 2 chunks
- **Cobertura ALCOA+ efectiva:** 80% (8/10 chunks)
- **Causa:** `technical_execution_failure` — fallo de ejecución del modelo, no una conclusión regulatoria

Estado del checkpoint actualizado de `completed: true` a `completed: "completed_with_failures"`, con metadata explícita de chunks fallidos, páginas no evaluadas, intentos y causa. Esto impide que el motor lo trate como resumible-desde-cero pero deja constancia de que no es una corrida limpia.

## 3. Tratamiento del finding ALCOA_LEGIBLE

El finding original clasificaba `ALCOA_LEGIBLE` como `evidencia_insuficiente` (estado regulatorio). Esto conflaba un fallo técnico de ejecución con una conclusión de cumplimiento — **se corrigió**:

- `estado` se mantiene en `evidencia_insuficiente` solo porque es el enum más cercano disponible en el esquema, pero se agregó:
  - `classification: "analysis_incomplete_due_to_model_error"`
  - `is_regulatory_finding: false`
- La `brecha` fue reescrita para dejar explícito que el análisis está incompleto por fallo técnico (chunks 5 y 8 nunca produjeron JSON válido), no por ausencia real de evidencia en el documento.
- Las otras 8 findings de `alcoa_plus_agent` (Attributable, Contemporaneous, Original, Accurate, Complete, Consistent, Enduring, Available) están ancladas a chunks 0 (pág 1-2) y 9 (pág 22-24), **ambos exitosos** — no dependen del gap y se mantienen sin cambios.

## 4. Clasificación del documento

**`PARTIALLY_DRAFT_READY`** (ver `urs_v2_1_status.json`)

Existen 8 findings de `alcoa_plus_agent` + 10 de `fda_part11_agent` + 10 de `eu_annex11_agent` sustentados en páginas efectivamente evaluadas — suficiente para generar correcciones parciales. El gap (páginas 12-13 y 19-21) queda excluido de generación de correcciones hasta reanálisis exitoso.

**Restricción explícita:** no generar correcciones para páginas 12-13 y 19-21, ni usar el finding `ALCOA_LEGIBLE` (marcado `analysis_incomplete_due_to_model_error`) como base de corrección regulatoria.

## 5. Auditoría

Evento `gmpai_chunked_analysis_gap_registered` escrito en `factory/audit/factory_audit.jsonl` (proyecto `gmpai_document_validation`) con el detalle de chunks fallidos, páginas no evaluadas, error y causa.

## 6. Próximo paso

Pendiente decisión de Cesar: reintentar los chunks 5/8 con otro enfoque (p.ej. prompt más corto o parseo más tolerante) o aceptar el gap documentado y avanzar. No se relanza automáticamente.
