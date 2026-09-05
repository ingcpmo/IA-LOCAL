# CF-6 v1.2 · CF6-2.5 (v3) — HUMAN_QUALITY_GATE (paquete para Capa 9)

PROMPT_VERSION `shadow-cf6-composer-struct-v3` (SIGNED, tag cf6-G2-r1) · SAMPLE_MANIFEST `FROZEN@cf6-G2.5-manifest` (congelado en tag **cf6-G2.5-manifest**, commit e356b3f) · hash `7422faaf569430dbc8a19647a2d2b64ff6b53b5231fc4e7962b4486e3165f5a0` · scope ADDENDUM PILOT_EXECUTION-2026-039/-040 (tag cf6-G2G-r1). `cf6-G2G` fue el cierre de scope previo, no la congelación del manifest.

> **Regla §4.2:** PASS del conjunto solo si CADA sección pasa TODOS los umbrales; `Sobreafirmación regulatoria` = 0 por sección (cero tolerancia). PASS (todas) → autoriza CF6-3. FAIL (alguna) → STOP; reportar sección/dimensión; decisión de Capa 9.
>
> El revisor adjudica sobre los **findings L2** (columna A), nunca sobre la narrativa.

> Claude Code **no** puntúa ni declara PASS/FAIL. La rúbrica va vacía.

---

## Resumen comparativo v2 → v3 (factual)

| Sección | v2 | v3 | Cambio observado |
|---|---|---|---|
| sec-0004 | RENDERED | RENDERED | technical_findings corregidos + página inventada eliminada |
| sec-0005 | RENDERED | RENDERED | technical_findings corregidos |
| sec-0016 | RENDERED | RENDERED | technical_findings corregidos + página inventada eliminada |
| sec-0018 | RENDERED | RENDERED | technical_findings corregidos |
| sec-0026 | SAFE_MODE | RENDERED | modo seguro anterior superado (v3 pasa contrato v3 + Q-STATE) |
| sec-0042 | SAFE_MODE | RENDERED | modo seguro anterior superado (v3 pasa contrato v3 + Q-STATE) |
| sec-0062 | RENDERED | SAFE_MODE | v3 detiene antes de publicar (reviewer_action menciona cumplimiento/conformidad) — seguridad, no regresión |

> Los `SAFE_MODE` **nuevos** en v3 (v2 RENDERED → v3 SAFE_MODE) son el gate determinista deteniendo salida insegura del modelo — **mejor seguridad, no regresión**.

---

## sec-0004 · RW-0005 · 21_CFR_11.10(g)  (section_type CROSS_DOMAIN · regulatory_state INCONCLUSIVE · B = **RENDERED**)

`allowed_technical_findings` = ['ACCESS_CONTROL_GAP', 'AUTHORITY_CHECK_GAP'] · `technical_findings` (v3) = ['ACCESS_CONTROL_GAP', 'AUTHORITY_CHECK_GAP'] · `duplicate_quotes_raw` = []

**A — reporte determinista L2** (RW-0005 · 21_CFR_11.10(g) · 5 findings)

| finding | subtype | riesgo | machine_state | pág | cita anclada (L2, verbatim) |
|---|---|---|---|---|---|
| `98df1d69` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 13 | and analog input and output cards to meet the hardwired system I/O requirements. |
| `d90545c3` | ACCESS_CONTROL_GAP | HIGH | MACHINE_DEVIATION_CANDIDATE | 13 | Process interlocks may be overridden with appropriate access level. |
| `06d5ab42` | AUTHORITY_CHECK_GAP | HIGH | MACHINE_INCONCLUSIVE | 13 | Administrator and Maintenance login security levels. |
| `e6ae9f4b` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 40 | To ensure that only operators with the proper |
| `f5fe98d5` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 40 | To ensure that only operators with the proper |

Todos `human_state = UNREVIEWED`. Estado regulatorio determinista de la sección: **INCONCLUSIVE**.

**B — resultado CF6 v3**

```
## RW-0005 · 21_CFR_11.10(g)

ESTADO REGULATORIO: permanece INCONCLUSIVE. No se concluye cumplimiento ni incumplimiento.

EVIDENCIA OBSERVADA:
- "Process interlocks may be overridden with appropriate access level."
- "Administrator and Maintenance login security levels."

LIMITACIÓN DE EVIDENCIA:
- Se recuperaron pasajes potencialmente relevantes que requieren revisión humana; el comportamiento requerido no se localizó en el alcance documental revisado (no implica ausencia real).

HALLAZGOS TÉCNICOS RELACIONADOS:
- ACCESS_CONTROL_GAP
- AUTHORITY_CHECK_GAP

ACCIÓN PARA EL REVISOR: Revisar en RW-0005 si los pasajes recuperados cubren los requisitos de interrupciones de procesos y niveles de seguridad de inicio de sesión de administradores y mantenimiento; no se ancló eco léxico para distinguir hueco real de límite de extracción.
```

`reviewer_action` (v3, emitido por el modelo, pre-render): 'Revisar en RW-0005 si los pasajes recuperados cubren los requisitos de interrupciones de procesos y niveles de seguridad de inicio de sesión de administradores y mantenimiento; no se ancló eco léxico para distinguir hueco real de límite de extracción.'

**Rúbrica §4.2 — sec-0004 (POR SECCIÓN)**

| Dimensión | Umbral | Puntuación | ¿Pasa? |
|---|---|---|---|
| Fidelidad al finding | ≥ 4/5 |  |  |
| Precisión GMP | ≥ 4/5 |  |  |
| Claridad | ≥ 4/5 |  |  |
| Utilidad para revisión | ≥ 4/5 |  |  |
| Valor añadido vs determinista | ≥ 4/5 |  |  |
| Sobreafirmación regulatoria | = 0 (cero tolerancia) |  |  |
| Preferencia B sobre A | REQUERIDA |  |  |
| Reduce carga cognitiva vs leer L2 | SÍ |  |  |

`sec-0004` PASS de sección = TODAS las filas pasan. Sobreafirmación regulatoria DEBE ser 0.

---

## sec-0005 · RW-0005 · 21_CFR_11.50_11.70  (section_type REGULATORY · regulatory_state INCONCLUSIVE · B = **RENDERED**)

`allowed_technical_findings` = [] · `technical_findings` (v3) = [] · `duplicate_quotes_raw` = ['With the FactoryTalk View SE electronic signature feature, each entry into the FactoryTalk View']

**A — reporte determinista L2** (RW-0005 · 21_CFR_11.50_11.70 · 7 findings)

| finding | subtype | riesgo | machine_state | pág | cita anclada (L2, verbatim) |
|---|---|---|---|---|---|
| `aabae026` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 45 | record shall contain the following fields |
| `2665ade8` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 45 | With the FactoryTalk View SE electronic signature feature, each entry into the FactoryTalk View |
| `66d6ec5b` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 45 | Date and time stamps of the change |
| `175f856f` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 45 | record shall contain the following fields |
| `01cbeb36` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 45 | record shall contain the following fields |
| `d5568ec5` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 45 | With the FactoryTalk View SE electronic signature feature, each entry into the FactoryTalk View |
| `4e52163d` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 45 | With the FactoryTalk View SE electronic signature feature, each entry into the FactoryTalk View |

Todos `human_state = UNREVIEWED`. Estado regulatorio determinista de la sección: **INCONCLUSIVE**.

**B — resultado CF6 v3**

```
## RW-0005 · 21_CFR_11.50_11.70

ESTADO REGULATORIO: permanece INCONCLUSIVE. No se concluye cumplimiento ni incumplimiento.

EVIDENCIA OBSERVADA:
- "With the FactoryTalk View SE electronic signature feature, each entry into the FactoryTalk View"
- "Date and time stamps of the change"

LIMITACIÓN DE EVIDENCIA:
- Se recuperaron pasajes potencialmente relevantes que requieren revisión humana; no se ancló eco léxico para distinguir huecos reales de límites de extracción.

ACCIÓN PARA EL REVISOR: Revisar en RW-0005 si los pasajes recuperados cubren los requisitos de registro de cambios y firmas electrónicas según 21 CFR 11.50 y 11.70; confirmar si se incluyen los campos de fecha y hora de los cambios.
```

`reviewer_action` (v3, emitido por el modelo, pre-render): 'Revisar en RW-0005 si los pasajes recuperados cubren los requisitos de registro de cambios y firmas electrónicas según 21 CFR 11.50 y 11.70; confirmar si se incluyen los campos de fecha y hora de los cambios.'

**Rúbrica §4.2 — sec-0005 (POR SECCIÓN)**

| Dimensión | Umbral | Puntuación | ¿Pasa? |
|---|---|---|---|
| Fidelidad al finding | ≥ 4/5 |  |  |
| Precisión GMP | ≥ 4/5 |  |  |
| Claridad | ≥ 4/5 |  |  |
| Utilidad para revisión | ≥ 4/5 |  |  |
| Valor añadido vs determinista | ≥ 4/5 |  |  |
| Sobreafirmación regulatoria | = 0 (cero tolerancia) |  |  |
| Preferencia B sobre A | REQUERIDA |  |  |
| Reduce carga cognitiva vs leer L2 | SÍ |  |  |

`sec-0005` PASS de sección = TODAS las filas pasan. Sobreafirmación regulatoria DEBE ser 0.

---

## sec-0016 · RW-0006 · 21_CFR_11.10(d)  (section_type REGULATORY · regulatory_state INCONCLUSIVE · B = **RENDERED**)

`allowed_technical_findings` = [] · `technical_findings` (v3) = [] · `duplicate_quotes_raw` = ['Process Automation Control Server System', 'The system shall implement the security and access control']

**A — reporte determinista L2** (RW-0006 · 21_CFR_11.10(d) · 8 findings)

| finding | subtype | riesgo | machine_state | pág | cita anclada (L2, verbatim) |
|---|---|---|---|---|---|
| `86d91b6d` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 6 | 3.4.1 The system shall implement the security and access control |
| `fd2f4e05` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 6 | 3.1.1 The system shall measure the critical process parameters for the |
| `590a270e` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 6 | 3.4.1 The system shall implement the security and access control |
| `09c5642f` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 6 | Process Automation Control Server System |
| `bad158fb` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 6 | 3.4.1 The system shall implement the security and access control |
| `cc5b4996` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 6 | Process Automation Control Server System |
| `eeb06071` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 6 | 3.4.1 The system shall implement the security and access control |
| `1bdfdeec` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 16 | 5.2.2 URS-PCS-SR-008 Control and privilege access shall be |

Todos `human_state = UNREVIEWED`. Estado regulatorio determinista de la sección: **INCONCLUSIVE**.

**B — resultado CF6 v3**

```
## RW-0006 · 21_CFR_11.10(d)

ESTADO REGULATORIO: permanece INCONCLUSIVE. No se concluye cumplimiento ni incumplimiento.

EVIDENCIA OBSERVADA:
- "The system shall implement the security and access control"
- "The system shall measure the critical process parameters for the"
- "Process Automation Control Server System"
- "Control and privilege access shall be"

LIMITACIÓN DE EVIDENCIA:
- Se recuperaron pasajes potencialmente relevantes que requieren revisión humana; no se ancló eco léxico para distinguir huecos reales de límites de extracción.

ACCIÓN PARA EL REVISOR: Revisar en RW-0006 si los sub-criterios de 21 CFR 11.10(d) sobre seguridad y control de acceso, y medición de parámetros críticos quedan cubiertos por los pasajes recuperados; el motor automático no ancló evidencia léxica para ninguno.
```

`reviewer_action` (v3, emitido por el modelo, pre-render): 'Revisar en RW-0006 si los sub-criterios de 21 CFR 11.10(d) sobre seguridad y control de acceso, y medición de parámetros críticos quedan cubiertos por los pasajes recuperados; el motor automático no ancló evidencia léxica para ninguno.'

**Rúbrica §4.2 — sec-0016 (POR SECCIÓN)**

| Dimensión | Umbral | Puntuación | ¿Pasa? |
|---|---|---|---|
| Fidelidad al finding | ≥ 4/5 |  |  |
| Precisión GMP | ≥ 4/5 |  |  |
| Claridad | ≥ 4/5 |  |  |
| Utilidad para revisión | ≥ 4/5 |  |  |
| Valor añadido vs determinista | ≥ 4/5 |  |  |
| Sobreafirmación regulatoria | = 0 (cero tolerancia) |  |  |
| Preferencia B sobre A | REQUERIDA |  |  |
| Reduce carga cognitiva vs leer L2 | SÍ |  |  |

`sec-0016` PASS de sección = TODAS las filas pasan. Sobreafirmación regulatoria DEBE ser 0.

---

## sec-0018 · RW-0006 · 21_CFR_11.10(g)  (section_type CROSS_DOMAIN · regulatory_state INCONCLUSIVE · B = **RENDERED**)

`allowed_technical_findings` = ['ACCESS_CONTROL_GAP', 'AUTHORITY_CHECK_GAP'] · `technical_findings` (v3) = ['ACCESS_CONTROL_GAP', 'AUTHORITY_CHECK_GAP'] · `duplicate_quotes_raw` = []

**A — reporte determinista L2** (RW-0006 · 21_CFR_11.10(g) · 5 findings)

| finding | subtype | riesgo | machine_state | pág | cita anclada (L2, verbatim) |
|---|---|---|---|---|---|
| `4e9ae107` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 4 | PLC System implementation and operation. |
| `93dd83b5` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 6 | A list of software settings or suitable configuration file(s) for each device |
| `de7cf255` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 16 | access for level 1 and level 2 alarms only. |
| `c5d66df9` | AUTHORITY_CHECK_GAP | HIGH | MACHINE_INCONCLUSIVE | 16 | Engineer security level privileges. |
| `90670306` | ACCESS_CONTROL_GAP | HIGH | MACHINE_DEVIATION_CANDIDATE | 16 | following operator access levels: |

Todos `human_state = UNREVIEWED`. Estado regulatorio determinista de la sección: **INCONCLUSIVE**.

**B — resultado CF6 v3**

```
## RW-0006 · 21_CFR_11.10(g)

ESTADO REGULATORIO: permanece INCONCLUSIVE. No se concluye cumplimiento ni incumplimiento.

EVIDENCIA OBSERVADA:
- "PLC System implementation and operation."
- "A list of software settings or suitable configuration file(s) for each device"
- "access for level 1 and level 2 alarms only."

LIMITACIÓN DE EVIDENCIA:
- Se recuperaron pasajes potencialmente relevantes que requieren revisión humana; el comportamiento requerido no se localizó en el alcance documental revisado (no implica ausencia real).

HALLAZGOS TÉCNICOS RELACIONADOS:
- ACCESS_CONTROL_GAP
- AUTHORITY_CHECK_GAP

ACCIÓN PARA EL REVISOR: Revisar en RW-0006 si los pasajes recuperados cubren los requisitos de control de acceso y verificación de autoridad para el sistema PLC; el motor automático no ancló evidencia léxica para ninguno.
```

`reviewer_action` (v3, emitido por el modelo, pre-render): 'Revisar en RW-0006 si los pasajes recuperados cubren los requisitos de control de acceso y verificación de autoridad para el sistema PLC; el motor automático no ancló evidencia léxica para ninguno.'

**Rúbrica §4.2 — sec-0018 (POR SECCIÓN)**

| Dimensión | Umbral | Puntuación | ¿Pasa? |
|---|---|---|---|
| Fidelidad al finding | ≥ 4/5 |  |  |
| Precisión GMP | ≥ 4/5 |  |  |
| Claridad | ≥ 4/5 |  |  |
| Utilidad para revisión | ≥ 4/5 |  |  |
| Valor añadido vs determinista | ≥ 4/5 |  |  |
| Sobreafirmación regulatoria | = 0 (cero tolerancia) |  |  |
| Preferencia B sobre A | REQUERIDA |  |  |
| Reduce carga cognitiva vs leer L2 | SÍ |  |  |

`sec-0018` PASS de sección = TODAS las filas pasan. Sobreafirmación regulatoria DEBE ser 0.

---

## sec-0026 · RW-0006 · ANNEX11_7  (section_type TECHNICAL · regulatory_state NOT_APPLICABLE · B = **RENDERED**)

`allowed_technical_findings` = ['BACKUP_RECOVERY_GAP'] · `technical_findings` (v3) = ['BACKUP_RECOVERY_GAP'] · `duplicate_quotes_raw` = []

**A — reporte determinista L2** (RW-0006 · ANNEX11_7 · 1 finding)

| finding | subtype | riesgo | machine_state | pág | cita anclada (L2, verbatim) |
|---|---|---|---|---|---|
| `7160732a` | BACKUP_RECOVERY_GAP | HIGH | MACHINE_DEVIATION_CANDIDATE | 11 | have a UPS battery back-up system |

Todos `human_state = UNREVIEWED`. Estado regulatorio determinista de la sección: **NOT_APPLICABLE**.

**B — resultado CF6 v3**

```
## RW-0006 · Hallazgos técnicos (sin conclusión regulatoria)

Esta sección no emite un estado regulatorio; agrupa hallazgos deterministas para el revisor.

EVIDENCIA OBSERVADA:
- "have a UPS battery back-up system"

LIMITACIÓN DE EVIDENCIA:
- El comportamiento requerido no se localizó en el alcance documental revisado; no implica ausencia real.

HALLAZGOS TÉCNICOS:
- BACKUP_RECOVERY_GAP

ACCIÓN PARA EL REVISOR: Revisar en RW-0006 si el sistema de respaldo por batería (UPS) está descrito en el alcance documental y contrastarlo con el finding de trazabilidad técnica; no se confirmó automáticamente.
```

`reviewer_action` (v3, emitido por el modelo, pre-render): 'Revisar en RW-0006 si el sistema de respaldo por batería (UPS) está descrito en el alcance documental y contrastarlo con el finding de trazabilidad técnica; no se confirmó automáticamente.'

**Rúbrica §4.2 — sec-0026 (POR SECCIÓN)**

| Dimensión | Umbral | Puntuación | ¿Pasa? |
|---|---|---|---|
| Fidelidad al finding | ≥ 4/5 |  |  |
| Precisión GMP | ≥ 4/5 |  |  |
| Claridad | ≥ 4/5 |  |  |
| Utilidad para revisión | ≥ 4/5 |  |  |
| Valor añadido vs determinista | ≥ 4/5 |  |  |
| Sobreafirmación regulatoria | = 0 (cero tolerancia) |  |  |
| Preferencia B sobre A | REQUERIDA |  |  |
| Reduce carga cognitiva vs leer L2 | SÍ |  |  |

`sec-0026` PASS de sección = TODAS las filas pasan. Sobreafirmación regulatoria DEBE ser 0.

---

## sec-0042 · RW-0012 · (trazabilidad — sin regulación directa)  (section_type FUNCTIONAL_TRACEABILITY · regulatory_state NOT_APPLICABLE · B = **RENDERED**)

`allowed_technical_findings` = ['IMPLEMENTATION_WITHOUT_REQUIREMENT', 'ORPHAN_DESIGN_ELEMENT'] · `technical_findings` (v3) = ['IMPLEMENTATION_WITHOUT_REQUIREMENT', 'ORPHAN_DESIGN_ELEMENT'] · `duplicate_quotes_raw` = []

**A — reporte determinista L2** (RW-0012 · (trazabilidad — sin regulación directa) · 4 findings)

| finding | subtype | riesgo | machine_state | pág | cita anclada (L2, verbatim) |
|---|---|---|---|---|---|
| `1d01735b` | ORPHAN_DESIGN_ELEMENT | LOW | MACHINE_INCONCLUSIVE | 5 | 4.1.5.4 Clean Steam Generator WFI Request |
| `e9e911b3` | IMPLEMENTATION_WITHOUT_REQUIREMENT | MEDIUM | MACHINE_INCONCLUSIVE | 5 | 4.1.5.4 Clean Steam Generator WFI Request |
| `34788d60` | IMPLEMENTATION_WITHOUT_REQUIREMENT | MEDIUM | MACHINE_INCONCLUSIVE | 5 | 4.1.3 WFI Generation, Storage, and Distribution Signals |
| `65ffbc37` | ORPHAN_DESIGN_ELEMENT | LOW | MACHINE_INCONCLUSIVE | 5 | 4.1.3 WFI Generation, Storage, and Distribution Signals |

Todos `human_state = UNREVIEWED`. Estado regulatorio determinista de la sección: **NOT_APPLICABLE**.

**B — resultado CF6 v3**

```
## RW-0012 · Trazabilidad (sin regulación directa)

Esta sección no emite un estado regulatorio; agrupa hallazgos deterministas para el revisor.

EVIDENCIA OBSERVADA:
- "4.1.5.4 Clean Steam Generator WFI Request"
- "4.1.3 WFI Generation, Storage, and Distribution Signals"

LIMITACIÓN DE EVIDENCIA:
- Se observaron ausencias de diseño sin traza aguas arriba y claims de implementación sin requisito asociado; no se ancló eco léxico para distinguir hueco real de trazabilidad de límite de extracción.

HALLAZGOS TÉCNICOS RELACIONADOS:
- IMPLEMENTATION_WITHOUT_REQUIREMENT
- ORPHAN_DESIGN_ELEMENT

ACCIÓN PARA EL REVISOR: Revisar en RW-0012 si los claims de implementación y los elementos de diseño señalados trazan a un requisito o diseño aguas arriba; distinguir hueco real de trazabilidad de límite de extracción.
```

`reviewer_action` (v3, emitido por el modelo, pre-render): 'Revisar en RW-0012 si los claims de implementación y los elementos de diseño señalados trazan a un requisito o diseño aguas arriba; distinguir hueco real de trazabilidad de límite de extracción.'

**Rúbrica §4.2 — sec-0042 (POR SECCIÓN)**

| Dimensión | Umbral | Puntuación | ¿Pasa? |
|---|---|---|---|
| Fidelidad al finding | ≥ 4/5 |  |  |
| Precisión GMP | ≥ 4/5 |  |  |
| Claridad | ≥ 4/5 |  |  |
| Utilidad para revisión | ≥ 4/5 |  |  |
| Valor añadido vs determinista | ≥ 4/5 |  |  |
| Sobreafirmación regulatoria | = 0 (cero tolerancia) |  |  |
| Preferencia B sobre A | REQUERIDA |  |  |
| Reduce carga cognitiva vs leer L2 | SÍ |  |  |

`sec-0042` PASS de sección = TODAS las filas pasan. Sobreafirmación regulatoria DEBE ser 0.

---

## sec-0062 · RW-0014 · ALCOA_ORIGINAL  (section_type REGULATORY · regulatory_state INCONCLUSIVE · B = **SAFE_MODE** — no_structured_input)

`allowed_technical_findings` = [] · `technical_findings` (v3) = [] · `duplicate_quotes_raw` = []

**A — reporte determinista L2** (RW-0014 · ALCOA_ORIGINAL · 2 findings)

| finding | subtype | riesgo | machine_state | pág | cita anclada (L2, verbatim) |
|---|---|---|---|---|---|
| `583037f5` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 5 | actively being sent to a user for process use or sampling. |
| `62d17de6` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 18 | The only current copy of this document is maintained electronically. |

Todos `human_state = UNREVIEWED`. Estado regulatorio determinista de la sección: **INCONCLUSIVE**.

**B — resultado CF6 v3**

```
## RW-0014 · ALCOA_ORIGINAL

[NARRATIVA LLM NO DISPONIBLE — no superó el control]
ESTADO REGULATORIO: permanece INCONCLUSIVE. No se concluye cumplimiento ni incumplimiento.

EVIDENCIA ANCLADA (L2, verbatim):
- "actively being sent to a user for process use or sampling." (pág. 5)
- "The only current copy of this document is maintained electronically." (pág. 18)

ACCIÓN PARA EL REVISOR: revisar directamente los findings L2 de esta sección.
```

_structure_contract_violations (v3): ["reviewer_action menciona cumplimiento/conformidad: 'cumplen'"]_

`reviewer_action` (v3, emitido por el modelo, pre-render): 'Revisar en RW-0014 si los pasajes recuperados cumplen con los requisitos regulativos; se requiere revisión humana de los pasajes recuperados.'

**Rúbrica §4.2 — sec-0062 (POR SECCIÓN)**

| Dimensión | Umbral | Puntuación | ¿Pasa? |
|---|---|---|---|
| Fidelidad al finding | ≥ 4/5 |  |  |
| Precisión GMP | ≥ 4/5 |  |  |
| Claridad | ≥ 4/5 |  |  |
| Utilidad para revisión | ≥ 4/5 |  |  |
| Valor añadido vs determinista | ≥ 4/5 |  |  |
| Sobreafirmación regulatoria | = 0 (cero tolerancia) |  |  |
| Preferencia B sobre A | REQUERIDA |  |  |
| Reduce carga cognitiva vs leer L2 | SÍ |  |  |

`sec-0062` PASS de sección = TODAS las filas pasan. Sobreafirmación regulatoria DEBE ser 0.

---

## Veredicto del HUMAN_QUALITY_GATE (v3)

```
HUMAN_QUALITY_GATE (v3) = PENDIENTE   (evaluación de Capa 9, por sección)
por_seccion:
  sec-0004: PASS | FAIL  (si FAIL: dimensión(es) = ____)
  sec-0005: PASS | FAIL  (si FAIL: dimensión(es) = ____)
  sec-0016: PASS | FAIL  (si FAIL: dimensión(es) = ____)
  sec-0018: PASS | FAIL  (si FAIL: dimensión(es) = ____)
  sec-0026: PASS | FAIL  (si FAIL: dimensión(es) = ____)
  sec-0042: PASS | FAIL  (si FAIL: dimensión(es) = ____)
  sec-0062: PASS | FAIL  (si FAIL: dimensión(es) = ____)
resultado_conjunto = PASS solo si TODAS las secciones = PASS
firma: ____________  fecha: __________
```