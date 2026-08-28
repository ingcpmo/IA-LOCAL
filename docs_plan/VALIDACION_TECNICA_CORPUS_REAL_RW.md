# Validación TÉCNICA contra el corpus REAL Rockwell (RW)

**Fecha:** 2026-08-27 (corrida v1.1 2026-08-28). **Autoridad:** Capa 9 = Cesar. **Estado:** registro de evidencia — NO es un gate.

Este documento es **separado** del benchmark de Suite C
(`factory/regulatory/validation_v2/fixtures_draft/technical_suite_c.yaml`).
Los IDs `C01..C20` del benchmark **no** son una obligación de encontrar los mismos
defectos en Rockwell. Aquí sólo se registra lo que el análisis técnico determinista
(B6b v1 + v2) observa contra los documentos reales.

## 1. Canonical store (reconstruido 2026-08-27, `extract_document` vigente, B1.2)

| doc_id | tipo | PDF | claims | tablas |
|---|---|---|---:|---:|
| RW-0005 | FS  | `215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf` | 1409 | 89 |
| RW-0006 | URS | `215115305 SCADA-PCS Misc PLC System URS v2.1.pdf` | 515 | 35 |
| RW-0009 | SAT | `215115305-T-041 SAT3 Completed.pdf` | 62 | 2 |
| RW-0011 | DS  | `MCCPDC EMS Control Block Narrative revB.pdf` | 317 | 23 |
| RW-0012 | DS  | `MCCPDC PCS Signal Interface Control Block Narrative.pdf` | 595 | 39 |
| RW-0014 | DS  | `MCCPDC WFI Control Block Narrative revB.pdf` | 369 | 21 |

`meta.extraction_version = canonical-v1-2026-08` en los 6.

## 2. Hallazgos técnicos observados contra evidencia real

> OD-6 CERRADO: artefacto `technical_completeness_rules.yaml` v1.1 FIRMADO (context-scoped).
> §2.1 es la lectura manual de referencia; §4 es la corrida real del detector v1.1 sobre
> el corpus, que la reproduce sin falso-suprimir (v1.0 sólo emitía 1 de los 5 huecos).

### 2.1 Huecos confirmados presentes en el documento real

| # | Documento | Sección | Objetivo de control | Evidencia real | Fuente normativa |
|---|---|---|---|---|---|
| R-AT-PROT | RW-0005 | F12.00 Audit Trail (p45) | Audit trail no modificable por usuario privilegiado | F12.00 lista los campos registrados y el archivado; **no** describe protección contra modificación/borrado ni no-desactivación | 21 CFR 11.10(e)[4]/[6] |
| R-AT-INT | RW-0005 | F12.00 Audit Trail (p45) | Detección de manipulación del audit trail | F12.00 no describe ninguna capacidad de detección de manipulación (por cualquier medio) | 21 CFR 11.10(e)[5] |
| R-BR-VER | RW-0005 | F14.00 Backup and recovery (p47, p51) | Verificación de la capacidad de restaurar | "back-up ... shall be maintained to allow for the restoration"; **no** describe prueba/verificación del restore | EU GMP Annex 11 §7.2 |
| R-RET-VER | RW-0005 | F13.00 Long-Term Archiving (p47) | Verificación de accesibilidad/legibilidad/integridad en el periodo de retención | "MCCPDC will be responsible for archiving ... per their internal procedures"; **no** describe verificación | Annex 11 §7.1 / §17 |
| R-ATTR | RW-0011 | §4.4 Operator Interface (p13) | Atribución individual de la acción humana | "with the proper credentials, the input points can be simulated for calibration ... alarm limits ... available for review and adjustment"; sin identidad individual/única en el documento | MHRA ALCOA (Attributable); 21 CFR 11.10(d)[2] |

Severidad y estado los fija el analizador (`MACHINE_DEVIATION_CANDIDATE` /
`MACHINE_INCONCLUSIVE`) → **revisión humana**. Nunca auto-confirmado.

### 2.2 Registro de casos pedido por Capa 9 (2026-08-27)

```
C04 = EVALUACIÓN REAL PENDIENTE / INCONCLUSIVE SEGÚN EVIDENCIA
      RW-0005 F10.00/F10.01 (p40): describe el MECANISMO (5 niveles + códigos A-P por
      usuario; "runtime security restricts ... control system function access") pero NO
      enumera el mapeo operación -> nivel de autorización requerido. 11.10(g)[0] dice
      "según aplique". No se resuelve como hueco firme ni como conforme sin decisión.

C05 = POSIBLE EVIDENCIA CONFORME -- EVALUAR COMO HALLAZGO REAL, NO ALTERAR BENCHMARK
      RW-0005 F10.01 (p40): "FactoryTalk View SE runtime security restricts ... control
      system function access" + "before sanctioning an individual's electronic signature".
      El comportamiento (chequeo de autoridad en el punto de la operación) parece descrito
      -> en el corpus real esto probablemente NO es un defecto. El benchmark C05 (positivo
      determinista) NO se toca; aquí se registra que en Rockwell no hay hueco.

C06 = PATRÓN BENCHMARK NO OBSERVADO EN EL CORPUS REAL
      No existe un identificador de interfaz compartido entre dos documentos con un valor
      de parámetro divergente. El FS tiene tasas de logging por tipo de dato
      (15s / 60s / 5s) pero no un parámetro de interfaz PCS<->SCADA en conflicto entre
      docs. El benchmark C06 (constructo sintético 500ms/1000ms) mide la CAPACIDAD del
      detector; no obliga a un hallazgo en Rockwell.

C12 = DEFECTO REAL DISTINTO: OMISIÓN DE MANEJO DE FALLO DE COMUNICACIÓN, NO INTERFACE_INCONSISTENCY MODAL
      RW-0014 (WFI) p9-10 y RW-0012 (Signal Interface) p14 describen heartbeat logic para
      monitorear la comunicación con los skids. RW-0011 (EMS) NO describe ningún manejo de
      fallo/heartbeat de comunicación para su interfaz. Es una OMISIÓN de cobertura entre
      narrativos hermanos, no una contradicción modal/parámetro -> la regla de interfaz v1
      (modal-opuesto / valor divergente sobre id compartido) NO aplica. Candidato a
      TraceabilityFinding (cobertura desigual entre documentos hermanos) o a revisión
      humana; NO a INTERFACE_INCONSISTENCY.

C14 / C19 = CONTROLES BENCHMARK SIN CONTRAPARTE CONFORME REAL
      El benchmark C14 (audit trail con protección descrita) y C19 (retención con
      verificación descrita) son negativos sintéticos/conformes para medir falsos
      positivos. El FS real NO tiene una versión "conforme" de esas dos protecciones
      (ver R-AT-PROT, R-RET-VER arriba). No se busca contraparte real; los negativos
      sintéticos del benchmark cumplen su función de medir FP.
```

### 2.3 NOT_APPLICABLE confirmados contra evidencia real

| caso | documento real | por qué |
|---|---|---|
| C02 time_sync | RW-0006 URS p4 | "interfaces with ... NTP servers, etc." es mención de alcance, no un "shall" de sincronización. URS-PCS-SR-038 es DST. Sin fuente normativa. |
| C11 physical_security | RW-0005 F09.00 (p40) | Sección de diseño sin Req-ID de cliente propio; Annex 11 §12.1 admite sólo-lógico justificado. |
| C13 state_persistence | RW-0006 URS p12 | UR4.3.4/UR4.3.5 (MCCPDC 3.2.2) exigen UPS + 15 min de ride-through, no persistencia de estado tras reinicio. |

### 2.4 C07 (SEMANTIC) contra evidencia real

`RW-0005` F19.00 (p52): **"Redundant PCS MISC PLC hardware is not present. Should a
significant enough failure occur to the PCS MISC PLC, the PLC will stop functioning and
cease to control the process."** La ausencia de redundancia del PLC de control crítico
está **declarada**. Que sea un hueco depende de un juicio de criticidad del proceso y de
si hay justificación de riesgo aceptada — lectura comprensiva, no atributo verificable.
El detector determinista NO lo detecta; NO se activa HYBRID/LLM.

## 3. Consecuencia

- La **validación real** confirma 5 huecos técnicos presentes (R-AT-PROT, R-AT-INT,
  R-BR-VER, R-RET-VER, R-ATTR) más C07 (declarado, semántico) — coherentes con el alcance
  normativo de las reglas firmadas.
- **Re-medido con el detector v1.1** (§4): los 5 huecos (más equivalentes en la URS) se
  emiten como candidatos a revisión humana. OD-6 cerrado.
- El **benchmark de Suite C** (20 casos, `technical_suite_c.yaml` v0.2) queda intacto y
  separado; su corpus sintético y sus negativos conformes miden la capacidad y los falsos
  positivos del analizador con ground truth fijo.

## 4. Corrida ejecutada (B6b v1 + v2, artefacto v1.1 context-scoped)

**Run:** `factory/regulatory/pilot_run/technical_real_corpus/rw-tech-20260828T030943Z/`
(`technical_findings.json` + `meta.json`). Determinista, `network_locked()`,
`document_egress_bytes = 0`, `local_only = true`.

| Métrica | Valor |
|---|---|
| grafo | implemented_by=1120, designed_by=204, regulated_by=20 |
| findings totales | 24 (todos `human_state=UNREVIEWED` → revisión humana) |
| `ALCOA_ATTRIBUTABLE_GAP` | 4 — RW-0005 p40, RW-0011 p4, RW-0012 p5, RW-0014 p5 (familia "proper credentials" para calibración; MACHINE_INCONCLUSIVE) |
| `AUDIT_TRAIL_DESIGN_GAP` / `AUDIT_TRAIL_INTEGRITY_GAP` | 2 + 2 — RW-0005 p45 (F12.00), RW-0006 p6 |
| `BACKUP_RECOVERY_GAP` | 2 — RW-0005 p13, RW-0006 p11 |
| `ACCESS_CONTROL_GAP` / `AUTHORITY_CHECK_GAP` | 2 + 2 — RW-0005 p13, RW-0006 p5/p16 |
| `TECHNICAL_DESIGN_GAP` (retención) | 2 — RW-0005 p13, RW-0006 p6 |
| `ORPHAN_DESIGN_ELEMENT` | 8 — encabezados de sección / claims ambiguos (LOW/INCONCLUSIVE). Filtradas 12 filas de índice de trazabilidad del FS (`-F##.##, NN`). |
| `INTERFACE_INCONSISTENCY` | 0 — coherente con OD-3/OD-4 (no hay contradicción modal ni divergencia de parámetro en el corpus real) |

Cada finding lleva: `finding_id, class/subtype, document, page, section, source_text,
source_hash, requirement, technical_basis, evidence.anchored_quote, risk, rationale,
provenance, confidence, machine_state, human_state`.

**Lectura:** el detector v1.1 context-scoped surface los 5 huecos reales de §2.1
(más equivalentes en la URS) como candidatos a revisión humana, sin falso-suprimirlos
(v1.0 sólo emitía 1). Las decisiones OD-1..OD-5 quedan como observaciones de este
documento y **no** modifican el benchmark de Suite C.
