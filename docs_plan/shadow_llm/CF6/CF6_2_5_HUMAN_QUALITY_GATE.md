# CF-6 v1.2 · CF6-2.5 — HUMAN_QUALITY_GATE (paquete para Capa 9)

SAMPLE_MANIFEST `FROZEN@cf6-G2G` · hash `7422faaf569430dbc8a19647a2d2b64ff6b53b5231fc4e7962b4486e3165f5a0` · CF6-2.G PASS — ADDENDUM PILOT_EXECUTION-2026-037/-038 human_confirmed (cesar); tag cf6-G2G

> **Regla de evaluación (§4.2):** el gate es **PASS del conjunto solo si CADA sección pasa TODOS los umbrales.** `Sobreafirmación regulatoria` debe ser **0 por sección**, sin excepción. Un promedio alto con una sección peligrosa escondida = **FAIL**.
>
> PASS (todas) → autoriza CF6-3. FAIL (alguna) → STOP; reportar qué sección y qué dimensión; decisión de Capa 9 (ajustar prompt → nuevo `composer_prompt_version` en CF6-2, o MODEL_QUALIFICATION).

El revisor humano adjudica sobre los **findings L2** (columna A), nunca sobre la narrativa. B es asistencia marcada.

---

## sec-0004 · RW-0005 · 21_CFR_11.10(g)  (section_type CROSS_DOMAIN · regulatory_state INCONCLUSIVE · B = **RENDERED**)

**A — reporte determinista L2** (RW-0005 · 21_CFR_11.10(g) · 5 findings)

| finding | subtype | riesgo | machine_state | pág | cita anclada (L2, verbatim) |
|---|---|---|---|---|---|
| `98df1d69` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 13 | and analog input and output cards to meet the hardwired system I/O requirements. |
| `d90545c3` | ACCESS_CONTROL_GAP | HIGH | MACHINE_DEVIATION_CANDIDATE | 13 | Process interlocks may be overridden with appropriate access level. |
| `06d5ab42` | AUTHORITY_CHECK_GAP | HIGH | MACHINE_INCONCLUSIVE | 13 | Administrator and Maintenance login security levels. |
| `e6ae9f4b` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 40 | To ensure that only operators with the proper |
| `f5fe98d5` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 40 | To ensure that only operators with the proper |

Todos `human_state = UNREVIEWED`. Estado regulatorio determinista de la sección: **INCONCLUSIVE**.

**B — narrativa CF6-2.5**

```
## RW-0005 · 21_CFR_11.10(g)

ESTADO REGULATORIO: permanece INCONCLUSIVE. No se concluye cumplimiento ni incumplimiento.

EVIDENCIA OBSERVADA:
- "and analog input and output cards to meet the hardwired system I/O requirements."
- "To ensure that only operators with the proper"

LIMITACIÓN DE EVIDENCIA:
- Se recuperaron pasajes potencialmente relevantes que requieren revisión humana; no se ancló eco léxico para los sub-criterios de 21 CFR 11.10(g) en el alcance revisado.

HALLAZGOS TÉCNICOS RELACIONADOS:
- CROSS_DOMAIN

ACCIÓN PARA EL REVISOR: Revisar en RW-0005 (pág. 2) si los pasajes recuperados cubren los requisitos de entrada y salida analógicas para cumplir con los requisitos de entrada/salida del sistema hardwired; verificar si los pasajes recuperados garantizan que solo los operadores con los permisos adecuados puedan acceder.
```

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

**B — narrativa CF6-2.5**

```
## RW-0005 · 21_CFR_11.50_11.70

ESTADO REGULATORIO: permanece INCONCLUSIVE. No se concluye cumplimiento ni incumplimiento.

EVIDENCIA OBSERVADA:
- "With the FactoryTalk View SE electronic signature feature, each entry into the FactoryTalk View"
- "Date and time stamps of the change"
- "record shall contain the following fields"
- "With the FactoryTalk View SE electronic signature feature, each entry into the FactoryTalk View"
- "With the FactoryTalk View SE electronic signature feature, each entry into the FactoryTalk View"

LIMITACIÓN DE EVIDENCIA:
- Se recuperaron pasajes potencialmente relevantes que requieren revisión humana, pero no se ancló eco léxico para todos los sub-criterios de 21_CFR_11.50_11.70 en el alcance revisado.

HALLAZGOS TÉCNICOS RELACIONADOS:
- REGULATORY

ACCIÓN PARA EL REVISOR: Revisar en RW-0005 si los pasajes recuperados cubren adecuadamente los requisitos de 21_CFR_11.50_11.70, especialmente en relación con la fecha y hora de los cambios, y la inclusión de campos necesarios.
```

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

**B — narrativa CF6-2.5**

```
## RW-0006 · 21_CFR_11.10(d)

ESTADO REGULATORIO: permanece INCONCLUSIVE. No se concluye cumplimiento ni incumplimiento.

EVIDENCIA OBSERVADA:
- "3.4.1 The system shall implement the security and access control"
- "3.1.1 The system shall measure the critical process parameters for the"
- "3.4.1 The system shall implement the security and access control"
- "Process Automation Control Server System"
- "3.4.1 The system shall implement the security and access control"
- "Process Automation Control Server System"
- "3.4.1 The system shall implement the security and access control"
- "5.2.2 URS-PCS-SR-008 Control and privilege access shall be"

LIMITACIÓN DE EVIDENCIA:
- Se recuperaron pasajes potencialmente relevantes que requieren revisión humana, pero no se ancló eco léxico anclado para los sub-criterios de 21 CFR 11.10 en el alcance revisado.

HALLAZGOS TÉCNICOS RELACIONADOS:
- REGULATORY_INCONCLUSIVE

ACCIÓN PARA EL REVISOR: Revisar en RW-0006 (pág. 1-8) si los pasajes recuperados cubren adecuadamente los sub-criterios de 21 CFR 11.10, especialmente en lo que respecta a la implementación de seguridad y control de acceso.
```

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

**A — reporte determinista L2** (RW-0006 · 21_CFR_11.10(g) · 5 findings)

| finding | subtype | riesgo | machine_state | pág | cita anclada (L2, verbatim) |
|---|---|---|---|---|---|
| `4e9ae107` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 4 | PLC System implementation and operation. |
| `93dd83b5` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 6 | A list of software settings or suitable configuration file(s) for each device |
| `de7cf255` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 16 | access for level 1 and level 2 alarms only. |
| `c5d66df9` | AUTHORITY_CHECK_GAP | HIGH | MACHINE_INCONCLUSIVE | 16 | Engineer security level privileges. |
| `90670306` | ACCESS_CONTROL_GAP | HIGH | MACHINE_DEVIATION_CANDIDATE | 16 | following operator access levels: |

Todos `human_state = UNREVIEWED`. Estado regulatorio determinista de la sección: **INCONCLUSIVE**.

**B — narrativa CF6-2.5**

```
## RW-0006 · 21_CFR_11.10(g)

ESTADO REGULATORIO: permanece INCONCLUSIVE. No se concluye cumplimiento ni incumplimiento.

EVIDENCIA OBSERVADA:
- "PLC System implementation and operation."
- "A list of software settings or suitable configuration file(s) for each device"
- "access for level 1 and level 2 alarms only."
- "Engineer security level privileges."
- "following operator access levels:"

LIMITACIÓN DE EVIDENCIA:
- Se recuperaron pasajes potencialmente relevantes que requieren revisión humana; el comportamiento requerido no se localizó en el alcance documental revisado (no implica ausencia real).

HALLAZGOS TÉCNICOS RELACIONADOS:
- CROSS_DOMAIN

ACCIÓN PARA EL REVISOR: Revisar en RW-0006 si los pasajes recuperados cubren adecuadamente los requisitos de seguridad y acceso para el nivel de ingeniería y los alarmas de nivel 1 y 2; verificar si la implementación y operación del sistema PLC y la configuración de alarmas están correctamente documentadas.
```

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

## sec-0026 · RW-0006 · ANNEX11_7  (section_type TECHNICAL · regulatory_state NOT_APPLICABLE · B = **SAFE_MODE** — qstate_reject)

**A — reporte determinista L2** (RW-0006 · ANNEX11_7 · 1 finding)

| finding | subtype | riesgo | machine_state | pág | cita anclada (L2, verbatim) |
|---|---|---|---|---|---|
| `7160732a` | BACKUP_RECOVERY_GAP | HIGH | MACHINE_DEVIATION_CANDIDATE | 11 | have a UPS battery back-up system |

Todos `human_state = UNREVIEWED`. Estado regulatorio determinista de la sección: **NOT_APPLICABLE**.

**B — narrativa CF6-2.5**

```
## RW-0006 · Hallazgos técnicos (sin conclusión regulatoria)

[NARRATIVA LLM NO DISPONIBLE — no superó el control]
ESTADO REGULATORIO: no aplica; la sección no emite estado regulatorio.

EVIDENCIA ANCLADA (L2, verbatim):
- "have a UPS battery back-up system" (pág. 11)

ACCIÓN PARA EL REVISOR: revisar directamente los findings L2 de esta sección.
```

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

## sec-0042 · RW-0012 · (trazabilidad — sin regulación directa)  (section_type FUNCTIONAL_TRACEABILITY · regulatory_state NOT_APPLICABLE · B = **SAFE_MODE** — qstate_reject)

**A — reporte determinista L2** (RW-0012 · (trazabilidad — sin regulación directa) · 4 findings)

| finding | subtype | riesgo | machine_state | pág | cita anclada (L2, verbatim) |
|---|---|---|---|---|---|
| `1d01735b` | ORPHAN_DESIGN_ELEMENT | LOW | MACHINE_INCONCLUSIVE | 5 | 4.1.5.4 Clean Steam Generator WFI Request |
| `e9e911b3` | IMPLEMENTATION_WITHOUT_REQUIREMENT | MEDIUM | MACHINE_INCONCLUSIVE | 5 | 4.1.5.4 Clean Steam Generator WFI Request |
| `34788d60` | IMPLEMENTATION_WITHOUT_REQUIREMENT | MEDIUM | MACHINE_INCONCLUSIVE | 5 | 4.1.3 WFI Generation, Storage, and Distribution Signals |
| `65ffbc37` | ORPHAN_DESIGN_ELEMENT | LOW | MACHINE_INCONCLUSIVE | 5 | 4.1.3 WFI Generation, Storage, and Distribution Signals |

Todos `human_state = UNREVIEWED`. Estado regulatorio determinista de la sección: **NOT_APPLICABLE**.

**B — narrativa CF6-2.5**

```
## RW-0012 · Trazabilidad (sin regulación directa)

[NARRATIVA LLM NO DISPONIBLE — no superó el control]
ESTADO REGULATORIO: no aplica; la sección no emite estado regulatorio.

EVIDENCIA ANCLADA (L2, verbatim):
- "4.1.5.4 Clean Steam Generator WFI Request" (pág. 5)
- "4.1.5.4 Clean Steam Generator WFI Request" (pág. 5)
- "4.1.3 WFI Generation, Storage, and Distribution Signals" (pág. 5)
- "4.1.3 WFI Generation, Storage, and Distribution Signals" (pág. 5)

ACCIÓN PARA EL REVISOR: revisar directamente los findings L2 de esta sección.
```

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

## sec-0062 · RW-0014 · ALCOA_ORIGINAL  (section_type REGULATORY · regulatory_state INCONCLUSIVE · B = **RENDERED**)

**A — reporte determinista L2** (RW-0014 · ALCOA_ORIGINAL · 2 findings)

| finding | subtype | riesgo | machine_state | pág | cita anclada (L2, verbatim) |
|---|---|---|---|---|---|
| `583037f5` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 5 | actively being sent to a user for process use or sampling. |
| `62d17de6` | REGULATORY_INCONCLUSIVE | HIGH | MACHINE_INCONCLUSIVE | 18 | The only current copy of this document is maintained electronically. |

Todos `human_state = UNREVIEWED`. Estado regulatorio determinista de la sección: **INCONCLUSIVE**.

**B — narrativa CF6-2.5**

```
## RW-0014 · ALCOA_ORIGINAL

ESTADO REGULATORIO: permanece INCONCLUSIVE. No se concluye cumplimiento ni incumplimiento.

EVIDENCIA OBSERVADA:
- "actively being sent to a user for process use or sampling."
- "The only current copy of this document is maintained electronically."

LIMITACIÓN DE EVIDENCIA:
- No se ancló eco léxico para los sub-criterios de ALCOA_ORIGINAL en el alcance revisado; solo hay pasajes de recuperación pendientes de verificación humana.

HALLAZGOS TÉCNICOS RELACIONADOS:
- REGULATORY_INCONCLUSIVE

ACCIÓN PARA EL REVISOR: Verificar en RW-0014 si los pasajes recuperados cumplen con los requisitos de la regulación ALCOA_ORIGINAL; el motor automático no ancló evidencia léxica para ninguno.
```

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

## Veredicto del HUMAN_QUALITY_GATE

```
HUMAN_QUALITY_GATE = PENDIENTE   (evaluación de Capa 9, por sección)
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