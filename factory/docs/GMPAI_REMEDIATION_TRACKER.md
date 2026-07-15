# GMPAI — Tracker de remediaciones documentales

Registro formal de hallazgos que requieren acción fuera del alcance del
software (remediación documental del cliente), separado del ciclo normal de
Release Candidates. Un ítem aquí **no bloquea** la aprobación de un RC — el
RC certifica que el *análisis* es correcto y trazable, no que la
documentación fuente esté completa.

---

## REM-GMPAI-001

| Campo | Valor |
|---|---|
| **ID** | REM-GMPAI-001 |
| **Proyecto** | `gmpai_document_validation` |
| **Sistema** | `Rockwell::MCCPDC-215115305` (automatización PLC/SCADA-PCS) |
| **RC relacionado** | v1.4 (`gmpai_document_validation-rc-v1.4-20260715T031540`, approved por Cesar) |
| **Finding original** | `requirements_traceability_agent`, familia documental `Rockwell::MCCPDC-215115305`, `estado=cumple_parcialmente`, `confianza=media` — ver `pipeline_pilot_llm.json` del RC v1.4 |
| **Hallazgo** | Protocolo IQ/OQ/PQ (o protocolo previo bajo el cual se ejecutó y aprobó el SAT) no disponible en el material entregado |
| **Estado** | `open` |
| **Clasificación** | Gap documental confirmado en el material entregado (no es limitación del pipeline ni del agente) |
| **Severidad** | mayor (conservada del análisis original — ver finding) |
| **Impacto** | No puede verificarse contra qué protocolo y criterios de aceptación se ejecutó/aprobó el SAT de `215115305 SCADA-PCS Misc PLC SAT3 Scanned-1.pdf` / `215115305-T-041 SAT3 Completed.pdf`. Rompe la cadena de trazabilidad GAMP 5 URS→FS→DS→IQ/OQ/PQ→SAT en la etapa `PROTOCOL_TEMPLATE`. |
| **Responsable propuesto** | Rockwell / Validación |
| **Fecha objetivo** | pendiente de asignación humana |

### Evidencia revisada (búsqueda de remediación, 2026-07-15)

Antes de confirmar el gap como real se buscó el protocolo faltante en 4
fuentes, sin encontrarlo en ninguna, y **sin modificar el RC v1.4**:

1. **Los 32 archivos del manifiesto** (`GMPAI/manifests/SHA256SUMS.txt`) — confirma que el corpus del piloto es el 100% del material entregado, no un subconjunto.
2. **`GMPAI/incoming/Rockwell.zip`** (archivo original, pre-curación de versiones vigentes) — mismos 14 archivos que `source/Rockwell/`, ninguno adicional.
3. **Búsqueda completa en `/home/ing_cpmo`** por nombre (`protocol`, `IQ`, `OQ`, `215115305`, `MCCPDC`) — sin resultado relevante. Único archivo tipo `PROTOCOL_TEMPLATE` encontrado (`SCADA/ETG_ET_[System Name]_IQ w appendices.pdf`) es una plantilla genérica de **otro** sistema, no de Rockwell/MCCPDC. Los archivos `Rockwell (1).zip` / `Rockwell (1)_(1).zip` en el home están corruptos (sin directorio central); los 3 encabezados locales recuperables no aportan documentos nuevos.
4. **`GMPAI/reports/matriz_trazabilidad_documental_full.json`** (corrida de scope completo, no del piloto) — reporta el mismo hallazgo con texto idéntico, corroborando que no es un artefacto del recorte del piloto.

### Acción requerida

1. Localizar y aportar el protocolo original bajo el cual se ejecutó el SAT; **o**
2. Generar una justificación formal de no aplicabilidad, aprobada por QA/Validación.

### Criterio de cierre

- El protocolo se incorpora al expediente y se reevalúa la trazabilidad afectada (sin reprocesar los 32 documentos completos, solo la familia `Rockwell::MCCPDC-215115305`); **o**
- La justificación formal de no aplicabilidad queda aprobada y auditada.

**No modificar silenciosamente el RC v1.4. No cerrar automáticamente este finding** — el cierre requiere una de las dos condiciones anteriores, confirmada por un humano.
