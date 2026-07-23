# Fase C — Criterios interpretativos (APROBADO Y PERSISTIDO)

**Estado: `APPROVED_AND_PERSISTED` (2026-07-23).** Cesar aprobó los 9
criterios ALCOA en bloque, incluidas las 2 correcciones de anclaje
(`ALCOA_COMPLETE`, `ALCOA_ENDURING` -> definición de p.8 en vez de la
palabra suelta de la intro) y dejando `ALCOA_CONTEMPORANEOUS`/
`ALCOA_ACCURATE` anclados a la palabra suelta (sin cambio, ya que el
documento no les da un descriptor adicional en la lista de p.8). Los 19
requisitos (CFR11 5 + ANNEX11 5 + ALCOA 9) ya están en
`requirements.yaml` con `evidence_pack_status: human_drafted_provisional`
— verificado por el loader (hash + schema) y por
`factory/tests/test_requirement_evidence_pack_context.py` (16 passed).
El contenido efectivamente escrito puede diferir en detalle de menor
alcance respecto a este borrador (p.ej. `typical_insufficient_evidence`
agregado a los 9 ALCOA para paridad con CFR11/ANNEX11); este archivo
queda como registro histórico del borrador, no como fuente viva —
`requirements.yaml` es la fuente de verdad.

Cada bloque está anclado a la **cita literal real** ya extraída y
verificada por hash en Fase C (`requirements.yaml`) — el criterio
propuesto se deriva directamente de esa cita y su contexto, sin agregar
obligaciones que el texto no sostiene. Donde el texto es ambiguo o
insuficiente para derivar un criterio con confianza, se marca
explícitamente en vez de inventar.

Campos por requisito: `governed_interpretation`, `evidence_min_criteria`,
`exclusion_criteria`, `typical_insufficient_evidence`, `weak_keywords`,
`expected_doc_types`.

---

## 21_CFR_11.10(a) — Validación del sistema (accuracy/reliability)

**Cita real**: *"Validation of systems to ensure accuracy, reliability,
consistent intended performance, and the ability to discern invalid or
altered records."* (§ 11.10(a))

- **governed_interpretation**: El requisito exige tanto un proceso de
  validación formal (protocolo + ejecución) como un mecanismo técnico
  específico para detectar registros inválidos o alterados; ninguno de
  los dos elementos puede inferirse del otro.
- **evidence_min_criteria**:
  - Existe un plan/protocolo de validación formal (IQ/OQ/PQ o
    equivalente) para el sistema.
  - El plan/protocolo cubre explícitamente accuracy, reliability y
    consistencia de desempeño previsto.
  - Existe un mecanismo descrito para discernir registros inválidos o
    alterados (checksums, validación de integridad, detección de
    edición).
- **exclusion_criteria**:
  - Mención genérica de "el sistema fue validado" sin describir método,
    alcance o criterios de aceptación.
  - Afirmación de que el sistema "cumple 21 CFR Part 11" sin describir el
    mecanismo real.
  - Mención del requisito solo en una lista de estándares/referencias.
- **typical_insufficient_evidence**: "Sistema validado" en portada o
  control de cambios sin protocolo asociado; cita del número de norma sin
  describir cómo se cumple.
- **weak_keywords**: `validado`, `validated`, `compliant`, `cumple`.
- **expected_doc_types**: `URS`, `FS`, `PROTOCOL`, `REPORT`.

## 21_CFR_11.10(d) — Limitar acceso a individuos autorizados

**Cita real**: *"Limiting system access to authorized individuals."*
(§ 11.10(d))

- **governed_interpretation**: Requiere evidencia de control de acceso
  específico al sistema evaluado (no genérico de red/dominio) y de un
  proceso de autorización, no solo la existencia de una pantalla de
  login.
- **evidence_min_criteria**:
  - Descripción de un mecanismo de control de acceso (login, roles,
    permisos) propio del sistema.
  - Identificación de quién está autorizado y cómo se gestiona esa
    autorización.
- **exclusion_criteria**:
  - "Acceso restringido" sin describir el mecanismo técnico.
  - Login genérico de red/dominio sin relación declarada con el sistema
    evaluado.
- **typical_insufficient_evidence**: "Usuario y contraseña" sin niveles
  de acceso ni gestión de autorización.
- **weak_keywords**: `seguro`, `secure`, `restricted`, `protegido`.
- **expected_doc_types**: `URS`, `FS`, `DS`, `SOP`.

## 21_CFR_11.10(e) — Audit trail seguro con timestamp

**Cita real**: *"Use of secure, computer-generated, time-stamped audit
trails to independently record the date and time of operator entries and
actions that create, modify, or delete electronic records."* (§ 11.10(e))

- **governed_interpretation**: El audit trail debe ser generado por el
  sistema, con timestamp, y cubrir crear/modificar/eliminar — un "log"
  sin estos tres atributos no basta.
- **evidence_min_criteria**:
  - Audit trail generado por el sistema (no manual).
  - Registra fecha/hora y la acción (crear/modificar/eliminar).
  - Es independiente del operador (no editable por quien genera el
    registro).
- **exclusion_criteria**:
  - "Se registran cambios" sin especificar que es automático y con
    timestamp.
  - Bitácora en papel/manual como único mecanismo.
- **typical_insufficient_evidence**: "Historial de cambios" sin confirmar
  generación automática ni inmutabilidad.
- **weak_keywords**: `trazable`, `traceable`, `historial`, `log`.
- **expected_doc_types**: `FS`, `DS`, `PROTOCOL`, `REPORT`.

## 21_CFR_11.10(g) — Verificación de autoridad (authority checks)

**Cita real**: *"Use of authority checks to ensure that only authorized
individuals can use the system, electronically sign a record, access the
operation or computer system input or output device, alter a record, or
perform the operation at hand."* (§ 11.10(g))

- **governed_interpretation**: Distinto de 11.10(d): exige verificación
  de autoridad **por tipo de operación** (firmar, alterar, ejecutar), no
  solo acceso general al sistema.
- **evidence_min_criteria**:
  - Chequeo de autoridad específico por operación (no solo login
    general).
  - Niveles de autorización diferenciados según la operación (p.ej.
    firmar vs. solo ver).
- **exclusion_criteria**:
  - Solo mención de login general sin diferenciar autoridad por tipo de
    operación.
- **typical_insufficient_evidence**: Se asume que 11.10(d) ya cubre esto
  sin describir el chequeo por operación específica.
- **weak_keywords**: `autorizado`, `authorized`, `permiso`.
- **expected_doc_types**: `FS`, `DS`, `PROTOCOL`.

## 21_CFR_11.50_11.70 — Firma electrónica (manifestación y vínculo al registro)

**Cita real**: *"The printed name of the signer;"* (§ 11.50(a)(1); el
contexto real incluye (a)(2) fecha/hora y (a)(3) significado)

- **governed_interpretation**: Exige los 3 elementos de manifestación
  (nombre, fecha/hora, significado) Y el vínculo no transferible al
  registro (§11.70) — ambos aspectos, no solo uno.
- **evidence_min_criteria**:
  - Nombre impreso del firmante.
  - Fecha y hora de la firma.
  - Significado/propósito de la firma (revisión, aprobación, autoría).
  - Vínculo no transferible a otro registro.
- **exclusion_criteria**:
  - Solo un "checkbox" de aprobación sin nombre/fecha/significado.
  - Imagen escaneada de firma manuscrita sin los 3 componentes.
- **typical_insufficient_evidence**: "Firma electrónica" mencionada
  genéricamente sin describir sus 3 componentes obligatorios.
- **weak_keywords**: `firmado`, `signed`, `aprobado`.
- **expected_doc_types**: `FS`, `DS`, `SOP`, `PROTOCOL`.

## ANNEX11_4 — Gestión de riesgo del sistema computarizado

**Cita real**: *"The validation documentation and reports should cover
the relevant steps of the life[cycle]"* (Sección 4, Validation, párrafo
4.1)

- **governed_interpretation**: **Regla dura confirmada por adjudicación
  humana real (Fase H, 2026-07-23)**: una mención de "GAMP5"/"risk-based
  approach" dentro de una lista de referencias **nunca** basta como
  evidencia de gestión de riesgo. Se requiere un proceso de gestión de
  riesgo DESCRITO y aplicado, no solo referenciado.
- **evidence_min_criteria**:
  - Documentación de validación que cubre las etapas relevantes del
    ciclo de vida (especificación, diseño, pruebas).
  - Evidencia de un proceso de evaluación de riesgo aplicado a la
    validación (no solo mención del término).
- **exclusion_criteria**:
  - Mención de "GAMP5" o "risk-based approach" dentro de una lista de
    estándares/referencias bibliográficas — **caso real confirmado**
    (corrida URS v2.1, adjudicado 2026-07-23): nunca constituye
    evidencia.
  - Cualquier mención de "riesgo" sin proceso, matriz o criterio de
    evaluación descrito.
- **typical_insufficient_evidence**: El documento cita "GAMP5 A
  Risk-Based Approach" como referencia bibliográfica sin describir cómo
  se aplicó ese enfoque al sistema evaluado.
- **weak_keywords**: `risk`, `riesgo`, `GAMP5`, `risk-based`.
- **expected_doc_types**: `DS`, `PROTOCOL`, `REPORT`.

## ANNEX11_7.1 — Almacenamiento y protección de datos

**Cita real**: *"Data should be secured by both physical and electronic
means against damage."* (Sección 7, Data Storage, párrafo 7.1)

- **governed_interpretation**: Requiere **ambos** medios (físico y
  electrónico) — uno solo no satisface el requisito según el texto
  literal ("by both").
- **evidence_min_criteria**:
  - Medios físicos de protección descritos (acceso restringido a
    sala de servidores/racks).
  - Medios electrónicos de protección descritos (backups, redundancia,
    checksums).
- **exclusion_criteria**: Solo uno de los dos medios presentado como si
  cubriera el requisito completo.
- **typical_insufficient_evidence**: "Los datos están seguros" sin
  mecanismo físico o electrónico concreto.
- **weak_keywords**: `seguro`, `protegido`, `secured`.
- **expected_doc_types**: `DS`, `SOP`.

## ANNEX11_9 — Audit trail

**Cita real**: *"Consideration should be given, based on a risk
assessment, to building into the system [the creation of a record of all
GMP-relevant changes and deletions]"* (Sección 9, Audit Trails)

- **governed_interpretation**: El texto condiciona el audit trail a una
  evaluación de riesgo previa ("based on a risk assessment") — la sola
  presencia de logging no basta sin esa base documentada.
- **evidence_min_criteria**:
  - Evaluación de riesgo documentada sobre la necesidad de audit trail.
  - El audit trail (si aplica según esa evaluación) registra cambios y
    eliminaciones GMP-relevantes con motivo documentado.
- **exclusion_criteria**: Audit trail presente sin evidencia de la
  evaluación de riesgo que lo sustente.
- **typical_insufficient_evidence**: Se menciona la existencia de audit
  trail sin conectarlo con una evaluación de riesgo previa.
- **weak_keywords**: `audit trail`, `trazabilidad`.
- **expected_doc_types**: `DS`, `REPORT`.

## ANNEX11_12 — Seguridad física y lógica

**Cita real**: *"Physical and/or logical controls should be in place to
restrict access to computerised system[s]"* (Sección 12, Security,
párrafo 12.1)

- **governed_interpretation**: A diferencia de ANNEX11_7.1 (que exige
  ambos), aquí el texto dice "and/or" — un solo tipo de control (físico
  O lógico), bien descrito, puede ser suficiente.
- **evidence_min_criteria**: Controles físicos (llaves, tarjetas) y/o
  lógicos (contraseñas, biometría) con mecanismo concreto descrito (no
  genérico).
- **exclusion_criteria**: "Acceso restringido" genérico sin especificar
  si es físico, lógico o ambos.
- **typical_insufficient_evidence**: "El acceso está controlado" sin
  mecanismo específico.
- **weak_keywords**: `restringido`, `restricted`, `controlado`.
- **expected_doc_types**: `DS`, `SOP`.

## ANNEX11_17 — Archivo y retención de registros

**Cita real**: *"Data may be archived. This data should be checked for
accessibility, readability and integrity."* (Sección 17, Archiving)

- **governed_interpretation**: El archivo por sí solo no basta — se
  exige verificación explícita y periódica de accesibilidad/legibilidad/
  integridad de esos datos archivados.
- **evidence_min_criteria**: Proceso de archivo descrito + verificación
  periódica de accesibilidad, legibilidad e integridad.
- **exclusion_criteria**: "Los datos se archivan" sin proceso de
  verificación periódica.
- **typical_insufficient_evidence**: Solo se menciona existencia de
  archivo/backup sin verificación de integridad.
- **weak_keywords**: `archivado`, `archived`, `backup`.
- **expected_doc_types**: `DS`, `SOP`.

## ALCOA_ATTRIBUTABLE — Attributable

**Cita real**: *"attributable to the person generating the data"* (p.8,
lista de definiciones ALCOA)

- **governed_interpretation**: Exige identificación **individual**, no de
  rol compartido — una cuenta genérica de operador no satisface
  "atribuible".
- **evidence_min_criteria**: El sistema/proceso identifica de forma única
  quién generó/modificó cada dato (usuario individual, no cuenta
  compartida).
- **exclusion_criteria**: Cuentas compartidas o genéricas ("operador",
  "admin") sin identificación individual.
- **typical_insufficient_evidence**: Se menciona "usuario" sin confirmar
  credenciales individuales.
- **weak_keywords**: `usuario`, `user`, `atribuible`.
- **expected_doc_types**: `FS`, `DS`, `SOP`.

## ALCOA_LEGIBLE — Legible

**Cita real**: *"legible and permanent"* (p.8, lista de definiciones
ALCOA)

- **governed_interpretation**: Cubre dos atributos distintos (legible +
  permanente) — ambos deben estar sustentados, no solo uno.
- **evidence_min_criteria**: Legibilidad durante todo el ciclo de vida
  (formato, resolución) + permanencia (no se borra/sobrescribe sin
  rastro).
- **exclusion_criteria**: Formatos propietarios sin garantía de
  legibilidad futura ni plan de migración.
- **typical_insufficient_evidence**: Se asume legibilidad sin considerar
  el ciclo de vida completo del dato.
- **weak_keywords**: `legible`, `readable`.
- **expected_doc_types**: `DS`, `SOP`.

## ALCOA_CONTEMPORANEOUS — Contemporaneous

**Cita real**: *"contemporaneous"* (p.5, expansión del acrónimo ALCOA)

- **governed_interpretation**: El timestamp debe corresponder al momento
  **real** de la actividad, no al momento de captura/carga tardía en el
  sistema.
- **evidence_min_criteria**: El dato se registra en el momento en que
  ocurre la actividad (timestamp real de captura).
- **exclusion_criteria**: Registro en papel/borrador transcrito
  posteriormente sin control documentado de esa demora.
- **typical_insufficient_evidence**: Se menciona timestamp sin confirmar
  que corresponde al momento real de la actividad.
- **weak_keywords**: `timestamp`, `fecha`.
- **expected_doc_types**: `FS`, `SOP`, `PROTOCOL`.

## ALCOA_ORIGINAL — Original

**Cita real**: *"original record (or certified true copy)"* (p.8, lista
de definiciones ALCOA)

- **governed_interpretation**: Una copia solo satisface este atributo si
  existe un proceso de certificación de fidelidad al original —
  documentado, no asumido.
- **evidence_min_criteria**: Registro original de primera captura, o
  copia certificada con proceso de certificación descrito.
- **exclusion_criteria**: Copias no certificadas presentadas como
  equivalentes al original.
- **typical_insufficient_evidence**: Se menciona "copia" sin proceso de
  certificación.
- **weak_keywords**: `original`, `copia`.
- **expected_doc_types**: `SOP`, `REPORT`.

## ALCOA_ACCURATE — Accurate

**Cita real**: *"accurate"* (dentro de "data is complete, consistent and
accurate in all its forms")

- **governed_interpretation**: Requiere un **mecanismo** verificable de
  exactitud, no solo la afirmación de que el dato es correcto.
- **evidence_min_criteria**: Mecanismo de verificación de exactitud
  (segundo chequeo, validación automática, control de rango).
- **exclusion_criteria**: "Los datos son precisos" sin mecanismo de
  verificación descrito.
- **typical_insufficient_evidence**: Ausencia de cualquier control de
  calidad de dato (rango, formato, doble entrada).
- **weak_keywords**: `preciso`, `accurate`, `correcto`.
- **expected_doc_types**: `FS`, `DS`, `SOP`.

## ALCOA_COMPLETE — Complete

**Cita real**: *"Complete"* (dentro de la introducción de atributos
ALCOA+)

- **governed_interpretation**: Completo incluye **todos** los datos
  generados, incluidos los no favorables o reintentos — no solo el
  resultado final aceptado.
- **evidence_min_criteria**: El proceso captura todos los datos
  relevantes, incluidos reintentos/reprocesamientos y resultados fuera de
  especificación; sin eliminación selectiva de datos no favorables.
- **exclusion_criteria**: Proceso que permite descartar o no registrar
  resultados "de prueba"/"fallidos" antes del registro final.
- **typical_insufficient_evidence**: Se documenta solo el resultado final
  sin registro de intentos previos o desviaciones.
- **weak_keywords**: `completo`, `complete`.
- **expected_doc_types**: `SOP`, `PROTOCOL`, `REPORT`.

## ALCOA_CONSISTENT — Consistent

**Cita real**: *"Consistent - the data must be self-consistent"* (p.8,
lista de definiciones ALCOA+)

- **governed_interpretation**: Exige AUTO-consistencia interna de los
  datos (secuencia lógica, sin contradicciones), no solo consistencia de
  formato.
- **evidence_min_criteria**: Los datos siguen una secuencia lógica y
  cronológica consistente (orden de timestamps, numeración de lotes) sin
  contradicciones internas.
- **exclusion_criteria**: Discrepancias entre metadatos y datos (p.ej.
  timestamp de un evento posterior a otro que depende de él).
- **typical_insufficient_evidence**: No se verifica consistencia
  cronológica/lógica entre registros del mismo proceso.
- **weak_keywords**: `consistente`, `consistent`.
- **expected_doc_types**: `SOP`, `REPORT`.

## ALCOA_ENDURING — Enduring

**Cita real**: *"Enduring"* (durable; lasting throughout the data
lifecycle)

- **governed_interpretation**: Debe cubrir explícitamente el **período de
  retención regulatorio completo**, no solo el almacenamiento inmediato.
- **evidence_min_criteria**: El medio de almacenamiento y formato
  garantizan durabilidad durante todo el período de retención
  regulatorio requerido.
- **exclusion_criteria**: Medios de almacenamiento sin plan de migración
  o con riesgo conocido de obsolescencia dentro del período de retención.
- **typical_insufficient_evidence**: No se especifica el período de
  retención ni el plan para garantizar accesibilidad durante ese período.
- **weak_keywords**: `duradero`, `enduring`, `permanente`.
- **expected_doc_types**: `SOP`, `DS`.

## ALCOA_AVAILABLE — Available

**Cita real**: *"Available – readily available for review or inspection
purposes"* (p.8, lista de definiciones ALCOA+)

- **governed_interpretation**: "Disponible" implica recuperación
  **práctica y oportuna** para inspección — no solo que el dato exista en
  algún medio.
- **evidence_min_criteria**: Los datos pueden recuperarse y presentarse
  para revisión/inspección dentro de un plazo razonable, sin dependencia
  de personal específico o sistemas descontinuados.
- **exclusion_criteria**: Datos que requieren un proceso de recuperación
  excesivamente largo o dependiente de un único experto/sistema legado
  sin plan de contingencia.
- **typical_insufficient_evidence**: No se demuestra un proceso real de
  recuperación de datos para inspección (solo se afirma que "están
  disponibles").
- **weak_keywords**: `disponible`, `available`.
- **expected_doc_types**: `SOP`, `REPORT`.

---

## Cierre

Estos 19 borradores quedan `DRAFT_NOT_APPROVED`. Ninguno se escribe en
`requirements.yaml` hasta que Cesar apruebe explícitamente — por
requisito, por lote, o en bloque. Una vez aprobado, el paso siguiente es
código: extender `build_requirement_evidence_pack_context.py` (o un
script nuevo) para escribir estos campos en `requirements.yaml` y
actualizar `evidence_pack_status` a un valor nuevo (p.ej.
`human_approved`, todavía no definido en el schema a propósito — Fase C
lo dejó así deliberadamente) más el test correspondiente que verifique
que los campos aprobados están presentes y coinciden con lo aprobado
aquí.
