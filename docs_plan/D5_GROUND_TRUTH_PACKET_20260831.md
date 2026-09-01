# D-5 — GROUND TRUTH HUMANO · PAQUETE CONSOLIDADO (STOP · 1 sola parada)

**Fecha:** 2026-08-31 · **Autoridad:** Capa 9 = Cesar / QA · **Gate:** D-5 (adjudicación humana H-8).

Edición **en el HOST** (no Mission Control). 3 ficheros:
`factory/regulatory/requirement_catalog/{qa40_adjudication_sheet,real_corpus_opportunities,held_out_technical_corpus}.yaml`

```
La IA NO asigna: TP · FP · COVERAGE_LIMITED · oportunidades · negative_units · held-out verdicts
QA40_SHA (inmutable) = 02b6d3d0b6fadb1f882c4e63b7f7421dd387268ddabe5b5f16abfa5d9d360d32
```
---

## A · `qa40_adjudication_sheet.yaml` — 40 casos (40/40 `label: PENDING`)

Por cada `case_id` rellena SÓLO: `label ∈ {TP, FP, COVERAGE_LIMITED}` · `human_evidence_anchor` (cita/página exacta que lo sustenta) · `adjudicator_note` (por qué) · `held_out_provenance_tag ∈ {REG, DOM, ADV}` o vacío.
`TP` = desviación real Y bien caracterizada · `FP` = no es desviación real, o caracterización incorrecta · `COVERAGE_LIMITED` = no evaluable sólidamente en ESTE corpus (sale del numerador Y denominador de precisión).
**PROHIBIDO** `FN`/`TN` aquí. Al terminar: `status: SIGNED` · `adjudicator: "<nombre real>"` · `adjudicated_at: "<ISO-8601>"`.

### 1. `ADJ-05837ed165` — RW-0005 p.13 · **IMPLEMENTATION_WITHOUT_REQUIREMENT**
- `finding_record_id`: `rec-ec4bea464032cbc8` · `finding_id`: `fnd-bb9c5086ccfd86f6` · `finding_class`: FunctionalFinding
- criterio: `—` · base: —
- `section`: sec-d2e8bd5d70ae783c · `source_hash`: `7126fb6c935c06de85863c9f…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **MEDIUM** · pre-ENFORCE: MEDIUM
- rationale máquina: Claim de un documento de implementación/diseño sin arista `implemented_by`/`designed_by` entrante: no traza a ningún requisito aguas arriba. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > UR4.6.1 [URS-PCS-HR-017] All indicator lights shall be suitable for operation on 24VDC.

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 2. `ADJ-4172aced07` — RW-0005 p.13 · **ACCESS_CONTROL_GAP**
- `finding_record_id`: `rec-339740a9d90545c3` · `finding_id`: `fnd-c9108665b1eda22c` · `finding_class`: SecurityFinding
- criterio: `21_CFR_11.10(g)` · base: 21_CFR_11.10(g)
- `section`: sec-d2e8bd5d70ae783c · `source_hash`: `bd6c2fa60ed4267b48490f09…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **HIGH** · pre-ENFORCE: HIGH
- rationale máquina: [C04] Cada operacion aplicable del sistema tiene un nivel de autorizacion definido. Fuente: 21_CFR_11.10(g). El documento describe el tema pero NO se encontro el comportamiento requerido: Se describe, para cada operacion aplicable del sistema, el nivel de autorizacion requerido -- en cualquier forma (prosa enumerada, lista, tabla). El artefacto llamado literalmente "matriz" NO es obligatorio. Regla determinista de completitud (artefacto gobernado v1.1). BORRADOR ASISTIDO -- revision humana requerida.
- **anchored_quote (texto exacto del documento):**

  > Process interlocks may be overridden with appropriate access level.

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 3. `ADJ-6e9cae87e0` — RW-0005 p.13 · **AUTHORITY_CHECK_GAP**
- `finding_record_id`: `rec-e50eb1f506d5ab42` · `finding_id`: `fnd-5b04c8582e40822c` · `finding_class`: SecurityFinding
- criterio: `21_CFR_11.10(g)` · base: 21_CFR_11.10(g)
- `section`: sec-d2e8bd5d70ae783c · `source_hash`: `036322553783cf6a8b22caba…`
- `evidence_basis`: INDETERMINATE · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **HIGH** · pre-ENFORCE: HIGH
- rationale máquina: [C05] El sistema verifica tecnicamente la autoridad del usuario en el momento de ejecutar cada operacion aplicable (no solo en el login inicial). Fuente: 21_CFR_11.10(g). El documento describe el tema pero NO se encontro el comportamiento requerido: Se describe un chequeo de autoridad ejecutado por el sistema en el momento de cada operacion aplicable. Regla determinista de completitud (artefacto gobernado v1.1). BORRADOR ASISTIDO -- revision humana requerida.
- **anchored_quote (texto exacto del documento):**

  > Administrator and Maintenance login security levels.

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 4. `ADJ-95040a50aa` — RW-0005 p.13 · **TECHNICAL_DESIGN_GAP**
- `finding_record_id`: `rec-9e664cfb5c0d6420` · `finding_id`: `fnd-fe16ab66a3339008` · `finding_class`: TechnicalFinding
- criterio: `ANNEX11_7 (Section 7.1) ; ANNEX11_17` · base: ANNEX11_7 (Section 7.1) ; ANNEX11_17
- `section`: sec-d2e8bd5d70ae783c · `source_hash`: `6bd974145ed0b3ef47e5c6dc…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **MEDIUM** · pre-ENFORCE: MEDIUM
- rationale máquina: [C08] Los registros siguen accesibles, legibles e integros durante todo el periodo de retencion declarado. Fuente: ANNEX11_7 (Section 7.1) ; ANNEX11_17. El documento describe el tema pero NO se encontro el comportamiento requerido: El periodo de retencion esta declarado Y hay verificacion documentada de que los registros permanecen accesibles / legibles / integros durante ese periodo. Regla determinista de completitud (artefacto gobernado v1.1). BORRADOR ASISTIDO -- revision humana requerida.
- **anchored_quote (texto exacto del documento):**

  > UR5.4.1 [URS-PCS-SR-035] The system shall provide for an interface for the collection and archival of

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 5. `ADJ-be3193e1f9` — RW-0005 p.13 · **BACKUP_RECOVERY_GAP**
- `finding_record_id`: `rec-31be76e58d138850` · `finding_id`: `fnd-b44979d8457f80b4` · `finding_class`: TechnicalFinding
- criterio: `ANNEX11_7 (Section 7.2)` · base: ANNEX11_7 (Section 7.2)
- `section`: sec-d2e8bd5d70ae783c · `source_hash`: `fb81b0dd9f1f40309876c48a…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **HIGH** · pre-ENFORCE: HIGH
- rationale máquina: [C03] Los datos se pueden recuperar tras una perdida: hay backups regulares Y se verifica la capacidad de restaurarlos. Fuente: ANNEX11_7 (Section 7.2). El documento describe el tema pero NO se encontro el comportamiento requerido: Se realizan backups regulares Y se verifica -- durante validacion y de forma periodica -- la capacidad de RESTAURAR los datos. Regla determinista de completitud (artefacto gobernado v1.1). BORRADOR ASISTIDO -- revision humana requerida.
- **anchored_quote (texto exacto del documento):**

  > UR4.3.4 [MCCPDC 3.2.2] The PCS Miscellaneous PLC panel shall have a UPS battery back-up system

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 6. `ADJ-ca963eedbe` — RW-0005 p.40 · **REGULATORY_INCONCLUSIVE**
- `finding_record_id`: `rec-f9f8810af5fe98d5` · `finding_id`: `fnd-63caabcb2bccea24` · `finding_class`: RegulatoryFinding
- criterio: `21_CFR_11.10(g)` · base: —
- `section`: None · `source_hash`: `7afacd9ea7a387bc2569ef03…`
- `evidence_basis`: INDETERMINATE · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **HIGH** · pre-ENFORCE: HIGH
- rationale máquina: Sin eco léxico anclado para 21_CFR_11.10(g)::sc1. Candidatos de RECUPERACIÓN (no evidencia validada): [clm-421c20ceb0f900eb p.40]; [clm-a205b909f698f80c p.51]; [clm-5592beb472896fc9 p.45]. A revisión humana. MODO TIER-1 (Palanca C). El análisis regulatorio automatizado se limita a: (a) confirmación de eco léxico anclado por el verificador determinista; (b) recuperación semántica de candidatos entregada al revisor. La detección automática de evidencia PARAFRASEADA NO está incluida — el modelo local no la resuelve (medido 6 veces). Todo sub-criterio sin eco léxico anclado va a revisión humana. NUNCA hay declaración de cumplimiento ni aprobación automática.
- **anchored_quote (texto exacto del documento):**

  > To ensure that only operators with the proper

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 7. `ADJ-24e294a87c` — RW-0005 p.45 · **AUDIT_TRAIL_INTEGRITY_GAP**
- `finding_record_id`: `rec-f7eff6b9be225492` · `finding_id`: `fnd-849265b0882684c8` · `finding_class`: DataIntegrityFinding
- criterio: `21_CFR_11.10(e)` · base: 21_CFR_11.10(e)
- `section`: sec-093b99ec7b7d30a8 · `source_hash`: `62d02b3a6118a2d53016a1e8…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **CRITICAL** · pre-ENFORCE: CRITICAL
- rationale máquina: [C09] Se puede detectar si el audit trail fue manipulado. Fuente: 21_CFR_11.10(e). El documento describe el tema pero NO se encontro el comportamiento requerido: El audit trail tiene capacidad de deteccion de manipulacion -- por CUALQUIER medio. El comportamiento requerido es "una alteracion no autorizada de los registros de auditoria es detectable"; el medio tecnico es libre. Regla determinista de completitud (artefacto gobernado v1.1). BORRADOR ASISTIDO -- revision humana requerida.
- **anchored_quote (texto exacto del documento):**

  > The Critical Alarm Threshold Change Audit Trail entry will contain the following information:

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 8. `ADJ-3911795970` — RW-0005 p.45 · **AUDIT_TRAIL_DESIGN_GAP**
- `finding_record_id`: `rec-41020224b0ac1d19` · `finding_id`: `fnd-d1f4bec631a26e74` · `finding_class`: TechnicalFinding
- criterio: `21_CFR_11.10(e)` · base: 21_CFR_11.10(e)
- `section`: sec-093b99ec7b7d30a8 · `source_hash`: `62d02b3a6118a2d53016a1e8…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **HIGH** · pre-ENFORCE: HIGH
- rationale máquina: [C01] El audit trail no puede ser alterado, borrado ni desactivado -- ni siquiera por usuarios privilegiados -- y toda modificacion silenciosa es imposible o detectable. Fuente: 21_CFR_11.10(e). El documento describe el tema pero NO se encontro el comportamiento requerido: Existe (a) control de acceso privilegiado sobre el propio audit trail y (b) un mecanismo -- de cualquier naturaleza -- que impide o hace detectable la modificacion o el borrado de sus entradas. Regla determinista de completitud (artefacto gobernado v1.1). BORRADOR ASISTIDO -- revision humana requerida.
- **anchored_quote (texto exacto del documento):**

  > The Critical Alarm Threshold Change Audit Trail entry will contain the following information:

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 9. `ADJ-42505f9e53` — RW-0005 p.54 · **ORPHAN_DESIGN_ELEMENT**
- `finding_record_id`: `rec-bb015a19fef0dae9` · `finding_id`: `fnd-1b445d1f35cd771b` · `finding_class`: TraceabilityFinding
- criterio: `—` · base: —
- `section`: sec-f96d78fd0640c05f · `source_hash`: `1b88194aec3345935b9b929d…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: LOW
- rationale máquina: Elemento de diseño con identificador propio, sin arista `tested_by` saliente y sin requisito/diseño aguas arriba: nadie lo pidió y nadie lo prueba. refs: ['5.2.20', 'F05.02', 'PCSSR026', 'UR5.2.20']. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > UR5.2.20 [URS-PCS-SR-026] The following colors shall be utilized when indicating states of dynamic objects…(see below)-F05.02,

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 10. `ADJ-9a9e84e8e2` — RW-0005 p.54 · **IMPLEMENTATION_WITHOUT_REQUIREMENT**
- `finding_record_id`: `rec-2fcf74a9418a658d` · `finding_id`: `fnd-e34477fdf4f5d2d9` · `finding_class`: FunctionalFinding
- criterio: `—` · base: —
- `section`: sec-f96d78fd0640c05f · `source_hash`: `aa5510da7a94feaff3f59e76…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **MEDIUM** · pre-ENFORCE: MEDIUM
- rationale máquina: Claim de un documento de implementación/diseño sin arista `implemented_by`/`designed_by` entrante: no traza a ningún requisito aguas arriba. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > UR4.10.1 [URS-PCS-HR-022] The field inputs and outputs to the PCS Miscellaneous PLC shall be hardwired I/O-F01.06, 15

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 11. `ADJ-c77d65ffb6` — RW-0005 p.54 · **IMPLEMENTATION_WITHOUT_REQUIREMENT**
- `finding_record_id`: `rec-87f4b9520c95085d` · `finding_id`: `fnd-40c59b1146635c9c` · `finding_class`: FunctionalFinding
- criterio: `—` · base: —
- `section`: sec-f96d78fd0640c05f · `source_hash`: `1d22b9ffa0d22c2c17a0a803…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **MEDIUM** · pre-ENFORCE: MEDIUM
- rationale máquina: Claim de un documento de implementación/diseño sin arista `implemented_by`/`designed_by` entrante: no traza a ningún requisito aguas arriba. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > with general purpose area classification.-F01.03, 13

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 12. `ADJ-2db49caa65` — RW-0006 p.5 · **AUTHORITY_CHECK_GAP**
- `finding_record_id`: `rec-d4644bc4e980d24f` · `finding_id`: `fnd-87da61c0074699cc` · `finding_class`: SecurityFinding
- criterio: `21_CFR_11.10(g)` · base: 21_CFR_11.10(g)
- `section`: sec-e32114a96b4cb3a5 · `source_hash`: `be74556350142909d9e5b46c…`
- `evidence_basis`: INDETERMINATE · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **HIGH** · pre-ENFORCE: HIGH
- rationale máquina: [C05] El sistema verifica tecnicamente la autoridad del usuario en el momento de ejecutar cada operacion aplicable (no solo en el login inicial). Fuente: 21_CFR_11.10(g). El documento describe el tema pero NO se encontro el comportamiento requerido: Se describe un chequeo de autoridad ejecutado por el sistema en el momento de cada operacion aplicable. Regla determinista de completitud (artefacto gobernado v1.1). BORRADOR ASISTIDO -- revision humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 21CFRP11 21 CFR Part 11 Electronic Records, Electronic Signatures

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 13. `ADJ-0a370c32b3` — RW-0006 p.6 · **REQUIREMENT_NOT_TESTED**
- `finding_record_id`: `rec-4e6f08779e6216df` · `finding_id`: `fnd-b1060f3083e1039a` · `finding_class`: TestCoverageFinding
- criterio: `—` · base: —
- `section`: sec-14bd4af9588d4f02 · `source_hash`: `d96500fa57fb572a2bb7b4ca…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: MEDIUM
- rationale máquina: Requisito de documento fuente con implementación aguas abajo pero SIN ningún `test` transitivo en el grafo. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 3.5.2 [MCCPDC 1.4.2.4] - The SI shall implement thin client architecture

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 14. `ADJ-772aa4b353` — RW-0006 p.6 · **AUDIT_TRAIL_INTEGRITY_GAP**
- `finding_record_id`: `rec-956eeeb5e5b98cbe` · `finding_id`: `fnd-1eadbe72ea101557` · `finding_class`: DataIntegrityFinding
- criterio: `21_CFR_11.10(e)` · base: 21_CFR_11.10(e)
- `section`: sec-14bd4af9588d4f02 · `source_hash`: `a34aa169b3516a586c58960d…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **CRITICAL** · pre-ENFORCE: CRITICAL
- rationale máquina: [C09] Se puede detectar si el audit trail fue manipulado. Fuente: 21_CFR_11.10(e). El documento describe el tema pero NO se encontro el comportamiento requerido: El audit trail tiene capacidad de deteccion de manipulacion -- por CUALQUIER medio. El comportamiento requerido es "una alteracion no autorizada de los registros de auditoria es detectable"; el medio tecnico es libre. Regla determinista de completitud (artefacto gobernado v1.1). BORRADOR ASISTIDO -- revision humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 3.3.3 Audit trail records shall be archived.

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 15. `ADJ-820001ac29` — RW-0006 p.6 · **TECHNICAL_DESIGN_GAP**
- `finding_record_id`: `rec-0c617339da88a074` · `finding_id`: `fnd-6e8f9a36b92148e0` · `finding_class`: TechnicalFinding
- criterio: `ANNEX11_7 (Section 7.1) ; ANNEX11_17` · base: ANNEX11_7 (Section 7.1) ; ANNEX11_17
- `section`: sec-14bd4af9588d4f02 · `source_hash`: `a9f42f6ad62881d58c57af55…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **MEDIUM** · pre-ENFORCE: MEDIUM
- rationale máquina: [C08] Los registros siguen accesibles, legibles e integros durante todo el periodo de retencion declarado. Fuente: ANNEX11_7 (Section 7.1) ; ANNEX11_17. El documento describe el tema pero NO se encontro el comportamiento requerido: El periodo de retencion esta declarado Y hay verificacion documentada de que los registros permanecen accesibles / legibles / integros durante ese periodo. Regla determinista de completitud (artefacto gobernado v1.1). BORRADOR ASISTIDO -- revision humana requerida.
- **anchored_quote (texto exacto del documento):**

  > locally before it is archived in an alternate location for safe keeping.

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 16. `ADJ-886b6747b3` — RW-0006 p.6 · **REQUIREMENT_NOT_TESTED**
- `finding_record_id`: `rec-957e59b5e43589d1` · `finding_id`: `fnd-21b0289a18c29e47` · `finding_class`: TestCoverageFinding
- criterio: `—` · base: —
- `section`: sec-14bd4af9588d4f02 · `source_hash`: `9e6adf9effd19784d83e0395…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: MEDIUM
- rationale máquina: Requisito de documento fuente con implementación aguas abajo pero SIN ningún `test` transitivo en el grafo. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 3.6.7 [MCCPDC 3.3.1] - The system shall interface with an OEM vendor

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 17. `ADJ-908473d5b1` — RW-0006 p.6 · **AUDIT_TRAIL_DESIGN_GAP**
- `finding_record_id`: `rec-f346c55d235c03e3` · `finding_id`: `fnd-c9c1b1b9a0f4ae75` · `finding_class`: TechnicalFinding
- criterio: `21_CFR_11.10(e)` · base: 21_CFR_11.10(e)
- `section`: sec-14bd4af9588d4f02 · `source_hash`: `a34aa169b3516a586c58960d…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **HIGH** · pre-ENFORCE: HIGH
- rationale máquina: [C01] El audit trail no puede ser alterado, borrado ni desactivado -- ni siquiera por usuarios privilegiados -- y toda modificacion silenciosa es imposible o detectable. Fuente: 21_CFR_11.10(e). El documento describe el tema pero NO se encontro el comportamiento requerido: Existe (a) control de acceso privilegiado sobre el propio audit trail y (b) un mecanismo -- de cualquier naturaleza -- que impide o hace detectable la modificacion o el borrado de sus entradas. Regla determinista de completitud (artefacto gobernado v1.1). BORRADOR ASISTIDO -- revision humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 3.3.3 Audit trail records shall be archived.

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 18. `ADJ-6356c53fa7` — RW-0006 p.11 · **BACKUP_RECOVERY_GAP**
- `finding_record_id`: `rec-634d962c7160732a` · `finding_id`: `fnd-3a3c186220f5b0e4` · `finding_class`: TechnicalFinding
- criterio: `ANNEX11_7 (Section 7.2)` · base: ANNEX11_7 (Section 7.2)
- `section`: sec-47734156bc4c11fc · `source_hash`: `68b516309372054e795f2f1c…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **HIGH** · pre-ENFORCE: HIGH
- rationale máquina: [C03] Los datos se pueden recuperar tras una perdida: hay backups regulares Y se verifica la capacidad de restaurarlos. Fuente: ANNEX11_7 (Section 7.2). El documento describe el tema pero NO se encontro el comportamiento requerido: Se realizan backups regulares Y se verifica -- durante validacion y de forma periodica -- la capacidad de RESTAURAR los datos. Regla determinista de completitud (artefacto gobernado v1.1). BORRADOR ASISTIDO -- revision humana requerida.
- **anchored_quote (texto exacto del documento):**

  > have a UPS battery back-up system

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 19. `ADJ-87255e81ae` — RW-0006 p.11 · **REQUIREMENT_NOT_TESTED**
- `finding_record_id`: `rec-d822fcc2267dde6a` · `finding_id`: `fnd-7c950abaeb6c5ac3` · `finding_class`: TestCoverageFinding
- criterio: `—` · base: —
- `section`: sec-47734156bc4c11fc · `source_hash`: `3de19c86c9ac91f6b465d2df…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: MEDIUM
- rationale máquina: Requisito de documento fuente con implementación aguas abajo pero SIN ningún `test` transitivo en el grafo. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 4.5.6 [MCCPDC 3.2.2] Completed, assembled panel shall be UL

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 20. `ADJ-e8776e1eb6` — RW-0006 p.11 · **REQUIREMENT_NOT_TESTED**
- `finding_record_id`: `rec-d8eee555b489b272` · `finding_id`: `fnd-5fe1e772d38e09e8` · `finding_class`: TestCoverageFinding
- criterio: `—` · base: —
- `section`: sec-47734156bc4c11fc · `source_hash`: `40d6f8c5ccfa407722798edb…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: MEDIUM
- rationale máquina: Requisito de documento fuente con implementación aguas abajo pero SIN ningún `test` transitivo en el grafo. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 4.2.4 System shall include three portable Microsoft Surface Pro wireless

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 21. `ADJ-f600892264` — RW-0006 p.11 · **REQUIREMENT_NOT_TESTED**
- `finding_record_id`: `rec-aa9b6df94e4a702e` · `finding_id`: `fnd-970cb0218559d467` · `finding_class`: TestCoverageFinding
- criterio: `—` · base: —
- `section`: sec-47734156bc4c11fc · `source_hash`: `91634647954d3f57c2f9c554…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: MEDIUM
- rationale máquina: Requisito de documento fuente con implementación aguas abajo pero SIN ningún `test` transitivo en el grafo. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 4.9.2 URS-PCS-HR-021 All switching and cabling shall be capable

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 22. `ADJ-0404376af9` — RW-0006 p.16 · **REQUIREMENT_NOT_TESTED**
- `finding_record_id`: `rec-a2a0c552f2c24730` · `finding_id`: `fnd-ab8cf4fc0bdd4ad6` · `finding_class`: TestCoverageFinding
- criterio: `—` · base: —
- `section`: sec-caa61dcd3e461fab · `source_hash`: `f3581149640adfcbee754996…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: MEDIUM
- rationale máquina: Requisito de documento fuente con implementación aguas abajo pero SIN ningún `test` transitivo en el grafo. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 5.4.5 URS-PCS-SR-039 The system shall monitor and alarm the

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 23. `ADJ-1a2f161797` — RW-0006 p.16 · **REQUIREMENT_NOT_TESTED**
- `finding_record_id`: `rec-5135a9f631e88e7a` · `finding_id`: `fnd-ae5ca98eb7c57254` · `finding_class`: TestCoverageFinding
- criterio: `—` · base: —
- `section`: sec-caa61dcd3e461fab · `source_hash`: `59323d2fbd44cb87a3612293…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: MEDIUM
- rationale máquina: Requisito de documento fuente con implementación aguas abajo pero SIN ningún `test` transitivo en el grafo. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 5.2.15 URS-PCS-SR-021 The system must be compatible with

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 24. `ADJ-1bbe528ea5` — RW-0006 p.16 · **REQUIREMENT_NOT_TESTED**
- `finding_record_id`: `rec-a35ef0d478eadef8` · `finding_id`: `fnd-5e23a1b4f8228b5a` · `finding_class`: TestCoverageFinding
- criterio: `—` · base: —
- `section`: sec-caa61dcd3e461fab · `source_hash`: `ee83b2dfd9682f66b483e14a…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: MEDIUM
- rationale máquina: Requisito de documento fuente con implementación aguas abajo pero SIN ningún `test` transitivo en el grafo. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 5.4.9 URS-PCS-SR-043 A secured level access manual override

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 25. `ADJ-1cf04a72ba` — RW-0006 p.16 · **REQUIREMENT_NOT_TESTED**
- `finding_record_id`: `rec-05a16f1db0e9b326` · `finding_id`: `fnd-57710f257981d3d6` · `finding_class`: TestCoverageFinding
- criterio: `—` · base: —
- `section`: sec-caa61dcd3e461fab · `source_hash`: `0498f1763ca852632472f75a…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: MEDIUM
- rationale máquina: Requisito de documento fuente con implementación aguas abajo pero SIN ningún `test` transitivo en el grafo. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 5.3.4 URS-PCS-SR-033 Alarms shall be classified into three

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 26. `ADJ-27c86ef081` — RW-0006 p.16 · **ACCESS_CONTROL_GAP**
- `finding_record_id`: `rec-9416222090670306` · `finding_id`: `fnd-1f93d95910fcc543` · `finding_class`: SecurityFinding
- criterio: `21_CFR_11.10(g)` · base: 21_CFR_11.10(g)
- `section`: sec-caa61dcd3e461fab · `source_hash`: `921d71faf8282901b4edcb26…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **HIGH** · pre-ENFORCE: HIGH
- rationale máquina: [C04] Cada operacion aplicable del sistema tiene un nivel de autorizacion definido. Fuente: 21_CFR_11.10(g). El documento describe el tema pero NO se encontro el comportamiento requerido: Se describe, para cada operacion aplicable del sistema, el nivel de autorizacion requerido -- en cualquier forma (prosa enumerada, lista, tabla). El artefacto llamado literalmente "matriz" NO es obligatorio. Regla determinista de completitud (artefacto gobernado v1.1). BORRADOR ASISTIDO -- revision humana requerida.
- **anchored_quote (texto exacto del documento):**

  > following operator access levels:

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 27. `ADJ-2b84522dc6` — RW-0006 p.16 · **REQUIREMENT_NOT_TESTED**
- `finding_record_id`: `rec-aa552232061efbef` · `finding_id`: `fnd-1e1aa6b5abfb4855` · `finding_class`: TestCoverageFinding
- criterio: `—` · base: —
- `section`: sec-caa61dcd3e461fab · `source_hash`: `97b6924cf47e529f95dbad19…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: MEDIUM
- rationale máquina: Requisito de documento fuente con implementación aguas abajo pero SIN ningún `test` transitivo en el grafo. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 5.4.3 URS-PCS-SR-037 All data communication shall be via

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 28. `ADJ-399f54e33a` — RW-0006 p.16 · **REQUIREMENT_NOT_TESTED**
- `finding_record_id`: `rec-d61477197db51b76` · `finding_id`: `fnd-29b99dbd603f84f5` · `finding_class`: TestCoverageFinding
- criterio: `—` · base: —
- `section`: sec-caa61dcd3e461fab · `source_hash`: `10739e4dc90ee5a932d0f232…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: MEDIUM
- rationale máquina: Requisito de documento fuente con implementación aguas abajo pero SIN ningún `test` transitivo en el grafo. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 5.2.6 URS-PCS-SR-012 The system must have an automatic

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 29. `ADJ-4c73f03606` — RW-0006 p.16 · **REQUIREMENT_NOT_TESTED**
- `finding_record_id`: `rec-53df6ca63f939637` · `finding_id`: `fnd-7e2a9275627ef922` · `finding_class`: TestCoverageFinding
- criterio: `—` · base: —
- `section`: sec-caa61dcd3e461fab · `source_hash`: `54630b70682e2628e76d3b5f…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: MEDIUM
- rationale máquina: Requisito de documento fuente con implementación aguas abajo pero SIN ningún `test` transitivo en el grafo. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 5.2.10 URS-PCS-SR-016 Alarm presentation shall be visual and

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 30. `ADJ-d2205cb7cd` — RW-0006 p.16 · **REQUIREMENT_NOT_TESTED**
- `finding_record_id`: `rec-c8ab28098ea26220` · `finding_id`: `fnd-39c063f3f8824484` · `finding_class`: TestCoverageFinding
- criterio: `—` · base: —
- `section`: sec-caa61dcd3e461fab · `source_hash`: `307f49e37ae8a56e0660ffff…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: MEDIUM
- rationale máquina: Requisito de documento fuente con implementación aguas abajo pero SIN ningún `test` transitivo en el grafo. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 5.4.8 URS-PCS-SR-042 The control system shall have a historian

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 31. `ADJ-d9ee1220fa` — RW-0006 p.16 · **REQUIREMENT_NOT_TESTED**
- `finding_record_id`: `rec-2da01b9db05de4cb` · `finding_id`: `fnd-8cb8d247673a516a` · `finding_class`: TestCoverageFinding
- criterio: `—` · base: —
- `section`: sec-caa61dcd3e461fab · `source_hash`: `f137fb00e9f66eeba3efd5af…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: MEDIUM
- rationale máquina: Requisito de documento fuente con implementación aguas abajo pero SIN ningún `test` transitivo en el grafo. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 5.2.4 URS-PCS-SR-010 The user identification must consist of

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 32. `ADJ-dbbd6a52b3` — RW-0006 p.16 · **REQUIREMENT_NOT_TESTED**
- `finding_record_id`: `rec-dd15186e2f57cebc` · `finding_id`: `fnd-58ddaf537112761c` · `finding_class`: TestCoverageFinding
- criterio: `—` · base: —
- `section`: sec-caa61dcd3e461fab · `source_hash`: `4ab1462cb582133725a3cb4d…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: MEDIUM
- rationale máquina: Requisito de documento fuente con implementación aguas abajo pero SIN ningún `test` transitivo en el grafo. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 5.1.2 URS-PCS-SR-002 Distinction shall be drawn between,

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 33. `ADJ-fbf0cbcf4e` — RW-0006 p.16 · **REQUIREMENT_NOT_TESTED**
- `finding_record_id`: `rec-ecefe24588a642ea` · `finding_id`: `fnd-e0b958f4781a6d58` · `finding_class`: TestCoverageFinding
- criterio: `—` · base: —
- `section`: sec-caa61dcd3e461fab · `source_hash`: `7efb698993c84bd248c76d04…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: MEDIUM
- rationale máquina: Requisito de documento fuente con implementación aguas abajo pero SIN ningún `test` transitivo en el grafo. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 5.4.1 URS-PCS-SR-035 The system shall provide for an interface

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 34. `ADJ-839496ed03` — RW-0006 p.23 · **REGULATORY_INCONCLUSIVE**
- `finding_record_id`: `rec-be5aba51fbd24d21` · `finding_id`: `fnd-5177e7d22eb230ef` · `finding_class`: RegulatoryFinding
- criterio: `ANNEX11_7.1` · base: —
- `section`: None · `source_hash`: `101e6515a347ccd69bb2c4b6…`
- `evidence_basis`: INDETERMINATE · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **HIGH** · pre-ENFORCE: HIGH
- rationale máquina: Sin eco léxico anclado para ANNEX11_7.1::sc2. Candidatos de RECUPERACIÓN (no evidencia validada): [clm-cd487a06d06fc548 p.23]; [clm-f8542442c6e9dabc p.6]; [clm-be683e057fa8dc3d p.6]. A revisión humana. MODO TIER-1 (Palanca C). El análisis regulatorio automatizado se limita a: (a) confirmación de eco léxico anclado por el verificador determinista; (b) recuperación semántica de candidatos entregada al revisor. La detección automática de evidencia PARAFRASEADA NO está incluida — el modelo local no la resuelve (medido 6 veces). Todo sub-criterio sin eco léxico anclado va a revisión humana. NUNCA hay declaración de cumplimiento ni aprobación automática.
- **anchored_quote (texto exacto del documento):**

  > SCADA Supervisory Control and Data Acquisition

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 35. `ADJ-1c2aa0e630` — RW-0011 p.4 · **ALCOA_ATTRIBUTABLE_GAP**
- `finding_record_id`: `rec-920e1c069c888afb` · `finding_id`: `fnd-abb5097dbc517700` · `finding_class`: DataIntegrityFinding
- criterio: `ALCOA_ATTRIBUTABLE ; 21_CFR_11.10(d)` · base: ALCOA_ATTRIBUTABLE ; 21_CFR_11.10(d)
- `section`: sec-7b6ab0b994c72e1c · `source_hash`: `75173e98eb1859b5a347abfc…`
- `evidence_basis`: INDETERMINATE · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **HIGH** · pre-ENFORCE: HIGH
- rationale máquina: [C10] Cada dato de accion humana es atribuible a un individuo unico. Fuente: ALCOA_ATTRIBUTABLE ; 21_CFR_11.10(d). El documento describe el tema pero NO se encontro el comportamiento requerido: Toda accion humana registrada queda atribuida a una identidad individual y unica, sostenida por un mecanismo tecnico (no un campo de texto libre), para crear / modificar / eliminar. Regla determinista de completitud (artefacto gobernado v1.1). BORRADOR ASISTIDO -- revision humana requerida.
- **anchored_quote (texto exacto del documento):**

  > previously, with the proper credentials, the input points can be simulated for calibration or other

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 36. `ADJ-34140454ec` — RW-0012 p.5 · **ALCOA_ATTRIBUTABLE_GAP**
- `finding_record_id`: `rec-8c79d376a707b7f3` · `finding_id`: `fnd-dda4452c2717e340` · `finding_class`: DataIntegrityFinding
- criterio: `ALCOA_ATTRIBUTABLE ; 21_CFR_11.10(d)` · base: ALCOA_ATTRIBUTABLE ; 21_CFR_11.10(d)
- `section`: sec-a82a30b1cff7d458 · `source_hash`: `721d38e3a1967615bb9b9a8f…`
- `evidence_basis`: INDETERMINATE · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **HIGH** · pre-ENFORCE: HIGH
- rationale máquina: [C10] Cada dato de accion humana es atribuible a un individuo unico. Fuente: ALCOA_ATTRIBUTABLE ; 21_CFR_11.10(d). El documento describe el tema pero NO se encontro el comportamiento requerido: Toda accion humana registrada queda atribuida a una identidad individual y unica, sostenida por un mecanismo tecnico (no un campo de texto libre), para crear / modificar / eliminar. Regla determinista de completitud (artefacto gobernado v1.1). BORRADOR ASISTIDO -- revision humana requerida.
- **anchored_quote (texto exacto del documento):**

  > with the proper credentials, the input points can be simulated for troubleshooting or other

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 37. `ADJ-5a1f8e2abd` — RW-0012 p.5 · **ORPHAN_DESIGN_ELEMENT**
- `finding_record_id`: `rec-8a4bbe1c1d01735b` · `finding_id`: `fnd-e80c46a27f404903` · `finding_class`: TraceabilityFinding
- criterio: `—` · base: —
- `section`: sec-344fdf1c11b59fd1 · `source_hash`: `746f1cbd965e6f61299ce90f…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: LOW
- rationale máquina: Elemento de diseño con identificador propio, sin arista `tested_by` saliente y sin requisito/diseño aguas arriba: nadie lo pidió y nadie lo prueba. refs: ['4.1.5.4']. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 4.1.5.4 Clean Steam Generator WFI Request

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 38. `ADJ-bd478d983a` — RW-0012 p.5 · **ORPHAN_DESIGN_ELEMENT**
- `finding_record_id`: `rec-da2dd36165ffbc37` · `finding_id`: `fnd-584c2d9c13ff5f76` · `finding_class`: TraceabilityFinding
- criterio: `—` · base: —
- `section`: sec-344fdf1c11b59fd1 · `source_hash`: `43386897c4d0a4fcac821269…`
- `evidence_basis`: ABSENCE_DEPENDENT · `coverage_status`: MISSING · `would_degrade`: True
- banda máquina (post-ENFORCE): **LOW** · pre-ENFORCE: LOW
- rationale máquina: Elemento de diseño con identificador propio, sin arista `tested_by` saliente y sin requisito/diseño aguas arriba: nadie lo pidió y nadie lo prueba. refs: ['4.1.3']. BORRADOR ASISTIDO -- revisión humana requerida.
- **anchored_quote (texto exacto del documento):**

  > 4.1.3 WFI Generation, Storage, and Distribution Signals

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 39. `ADJ-30649d4225` — RW-0014 p.5 · **REGULATORY_INCONCLUSIVE**
- `finding_record_id`: `rec-5ee41dfa43c9fe97` · `finding_id`: `fnd-c73cc58847d641e7` · `finding_class`: RegulatoryFinding
- criterio: `ALCOA_ATTRIBUTABLE` · base: —
- `section`: None · `source_hash`: `d45a85b60c80b2929dd6f5ee…`
- `evidence_basis`: INDETERMINATE · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **HIGH** · pre-ENFORCE: HIGH
- rationale máquina: Sin eco léxico anclado para ALCOA_ATTRIBUTABLE::sc1. Candidatos de RECUPERACIÓN (no evidencia validada): [clm-a5e567beed1f0f3a p.5]; [clm-9de770b2c52024e6 p.5]; [clm-64a38108e7af5e6f p.4]. A revisión humana. MODO TIER-1 (Palanca C). El análisis regulatorio automatizado se limita a: (a) confirmación de eco léxico anclado por el verificador determinista; (b) recuperación semántica de candidatos entregada al revisor. La detección automática de evidencia PARAFRASEADA NO está incluida — el modelo local no la resuelve (medido 6 veces). Todo sub-criterio sin eco léxico anclado va a revisión humana. NUNCA hay declaración de cumplimiento ni aprobación automática.
- **anchored_quote (texto exacto del documento):**

  > Since an Administrator or Maintenance person may put any input point in SIMULATE and

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

### 40. `ADJ-55a654a957` — RW-0014 p.5 · **ALCOA_ATTRIBUTABLE_GAP**
- `finding_record_id`: `rec-a3965dbc0f624005` · `finding_id`: `fnd-3416d726b78c9075` · `finding_class`: DataIntegrityFinding
- criterio: `ALCOA_ATTRIBUTABLE ; 21_CFR_11.10(d)` · base: ALCOA_ATTRIBUTABLE ; 21_CFR_11.10(d)
- `section`: sec-5fa50879acbbdf49 · `source_hash`: `721d38e3a1967615bb9b9a8f…`
- `evidence_basis`: INDETERMINATE · `coverage_status`: OK · `would_degrade`: False
- banda máquina (post-ENFORCE): **HIGH** · pre-ENFORCE: HIGH
- rationale máquina: [C10] Cada dato de accion humana es atribuible a un individuo unico. Fuente: ALCOA_ATTRIBUTABLE ; 21_CFR_11.10(d). El documento describe el tema pero NO se encontro el comportamiento requerido: Toda accion humana registrada queda atribuida a una identidad individual y unica, sostenida por un mecanismo tecnico (no un campo de texto libre), para crear / modificar / eliminar. Regla determinista de completitud (artefacto gobernado v1.1). BORRADOR ASISTIDO -- revision humana requerida.
- **anchored_quote (texto exacto del documento):**

  > with the proper credentials, the input points can be simulated for troubleshooting or other

- **A COMPLETAR** → `label: ____` · `human_evidence_anchor: ____` · `adjudicator_note: ____` · `held_out_provenance_tag: ____`

## B · `real_corpus_opportunities.yaml`  (`opportunities: []` · `negative_units: []` · DRAFT_UNSIGNED)

QA **lee el corpus** (RW-0005 FS · RW-0006 URS · RW-0009 SAT · RW-0011/0012/0014 DS), NO los findings.

### B.1 · `opportunities:` — recall real / FN. Una entrada por CADA desviación que DEBERÍA detectarse:

```yaml
opportunities:
  - opportunity_id: OPP-001
    expected_class: <DataIntegrityFinding|TraceabilityFinding|TechnicalDesignFinding|RegulatoryFinding>
    expected_subtype: <p.ej. AUDIT_TRAIL_INTEGRITY_GAP>
    document: RW-00XX
    page_band: [<int>, <int>]        # start<=end, ambos >0
    expected_topic_or_requirement: <texto|id de requisito>
    human_evidence_anchor: <cita/página EXACTA>
    basis: <REG|DOM|ADV>
    reviewer_note: <por qué DEBERÍA detectarse>
    # cuando adjudiques el match (la IA NO):
    matched_finding_id: <fnd-...>     # debe existir en la corrida candidata
    match_confirmed_by: <nombre>
    match_note: <texto>
```
Sin `matched_finding_id`+`match_confirmed_by`+`match_note` ⇒ esa oportunidad cuenta como **FN**. `recall = TP/(TP+FN)`. Uno-a-uno.

### B.2 · `negative_units:` — especificidad / TN. NO se inventan; unidad donde el hallazgo prohibido NO debe salir:

```yaml
negative_units:
  - unit_id: NEG-001
    analysis_unit: <section|document|page_range>
    document: RW-00XX
    scope: [<int>, <int>]              # start<=end, ambos >0
    expected_class: <FindingClass prohibido aquí>
    expected_subtype: <subtype prohibido aquí>
    human_evidence_anchor: <cita/página>
    basis: <REG|DOM|ADV>
    reviewer_note: <por qué NO debe haber hallazgo>
    human_verified: true
```
`TN` = el analizador NO emitió el hallazgo prohibido en esa unidad. Sin unidades ⇒ `SPECIFICITY = UNKNOWN`.

Al terminar B: `status: SIGNED` · `adjudicator` · `adjudicated_at`.

## C · `held_out_technical_corpus.yaml` — 5 casos (DRAFT_UNSIGNED · 0/5 revisado · `rules_author: null`)

### `HO-T-001` · provenance_tag: **REG**
- expected: `finding=True` · `finding_class=DataIntegrityFinding` · `subtype=AUDIT_TRAIL_INTEGRITY_GAP`
- match: `document=HO-FS` · `page_band=[10, 16]`
- `source_clause`: 21 CFR 11.10(e) -- audit trail: fecha/hora, quién, qué (valor anterior/nuevo)
- `human_approved`: (falta si provenance_tag=ADV)
- **A COMPLETAR** → confirmar/ajustar `expected` y `match` · `human_reviewed: true` · (si ADV) `human_approved: true`

### `HO-T-002` · provenance_tag: **REG**
- expected: `finding=True` · `finding_class=TechnicalFinding` · `subtype=BACKUP_RECOVERY_GAP`
- match: `document=HO-FS` · `page_band=[10, 16]`
- `source_clause`: EU GMP Annex 11 §7.2 -- backups: realización regular y verificación de restauración
- `human_approved`: (falta si provenance_tag=ADV)
- **A COMPLETAR** → confirmar/ajustar `expected` y `match` · `human_reviewed: true` · (si ADV) `human_approved: true`

### `HO-T-003` · provenance_tag: **DOM**
- expected: `finding=True` · `finding_class=SecurityFinding` · `subtype=AUTHORITY_CHECK_GAP`
- match: `document=HO-FS` · `page_band=[10, 16]`
- `source_clause`: **FALTA** (obligatorio si provenance_tag=REG)
- `human_approved`: (falta si provenance_tag=ADV)
- **A COMPLETAR** → confirmar/ajustar `expected` y `match` · `human_reviewed: true` · (si ADV) `human_approved: true`

### `HO-T-004` · provenance_tag: **ADV**
- expected: `finding=True` · `finding_class=SecurityFinding` · `subtype=ACCESS_CONTROL_GAP`
- match: `document=HO-FS` · `page_band=[10, 16]`
- `source_clause`: **FALTA** (obligatorio si provenance_tag=REG)
- `human_approved`: True
- **A COMPLETAR** → confirmar/ajustar `expected` y `match` · `human_reviewed: true` · (si ADV) `human_approved: true`

### `HO-T-N01` · provenance_tag: **DOM**
- expected: `finding=False` · `finding_class=None` · `subtype=None`
- match: `document=HO-FSOK` · `page_band=[1, 10]`
- `source_clause`: **FALTA** (obligatorio si provenance_tag=REG)
- `human_approved`: (falta si provenance_tag=ADV)
- **A COMPLETAR** → confirmar/ajustar `expected` y `match` · `human_reviewed: true` · (si ADV) `human_approved: true`

Al terminar C: `status: SIGNED` · `rules_author: "<nombre real>"` (≠ autor del corpus semilla — ver `excluded_authors`) · `signed_at: "<ISO-8601>"`.

---
## Entrega
1. Editar los 3 ficheros en el host (o darme las decisiones y yo las escribo EXACTAS).
2. Firmar cada uno (`status: SIGNED` + identidad real + timestamp).
3. Responder con las decisiones o "D5 escrito". La máquina valida fail-closed y calcula `QA40_SAMPLE_PRECISION` / `REAL_RECALL` / `REAL_SPECIFICITY`.
