# PROPUESTA — `decomposition[]` del catálogo de requisitos (V2, B3)

**Estado:** ✅ **FIRMADO por Capa 9 (Cesar) el 2026-08-27** — *"firmo con los cambios, siempre que estos ayuden a mejorar"*.
**Fecha:** 2026-08-27. **Autor:** Capa 8.

### Cambios aplicados respecto a la propuesta revisada (todos reducen riesgo / no tocan sustancia)

1. **Landing spot.** `requirement_catalog_entry_v1.json` es `additionalProperties:false`;
   añadir `decomposition:` a `requirements.yaml` rompería `load_requirements()` y CURRENT.
   → Los sub-criterios viven en un archivo gobernado HERMANO,
   `factory/regulatory/requirement_catalog/decomposition.yaml`
   (`decomposition_version: 1.0`), cargado por
   `requirement_decomposition_loader.py` solo en el camino V2. El catálogo v1 y su
   schema quedan **intactos**.
2. **Conteo.** El total de la propuesta decía 89; el real es **84** sub-criterios
   (error aritmético de la tabla resumen, no de las listas). Corregido en la tabla y en el YAML.
3. **Redacción de los sub-criterios (semántica): sin cambios.** `text` (español) va verbatim y
   sigue siendo el autoritativo. Cambiar el fraseo a ciegas antes de medir es el patrón que la
   skill `gmp-recall-pipeline` prohíbe.
4. **Glosas bilingües (`decomposition_version` 1.1, misma firma — "haz las glosas bilingües").**
   Motivo **medido** en Gate B3: los documentos del cliente están en inglés y el reranker
   léxico determinista no cruza el idioma — los 9 sub-criterios de `21_CFR_11.10(e)` devolvían
   el mismo candidato. Cada sub-criterio gana `text_en`, glosa en inglés **fiel** de `text`
   (misma sustancia, otro idioma — no es re-interpretación). El aid de recuperación pasa a ser
   `text + text_en`. Resultado medido tras la glosa: los tops distintos sobre el FS real pasan
   de 1 a ≥3 de 9. La diferenciación semántica completa sigue necesitando embeddings (B3.1).

---

## 1. Qué es y por qué

`docs_plan/REDISENO_ANALIZADOR_GMP_LOCAL_V2.md` FASE 1 confirmó la causa raíz del recall
(`SEMANTIC_JUDGMENT_FAILURE`, 5/6 casos medibles): **el 7B local no cruza de un pasaje técnico
a un criterio regulatorio abstracto en una sola llamada cuando el pasaje no repite el
vocabulario del requisito.**

`decomposition[]` descompone cada requisito del catálogo en **sub-criterios atómicos y
verificables**, de modo que la pregunta que se le hace al modelo pase de *"¿este documento
cumple 21 CFR 11.10(e)?"* (un salto grande) a *"¿esta afirmación normalizada satisface: 'cada
entrada del audit trail lleva fecha y hora'?"* (un salto de eco casi léxico).

**Es una re-expresión, no una re-interpretación.** Cada sub-criterio deriva del
`citation_text` (texto normativo literal) y de los `evidence_min_criteria` ya gobernados
(interpretados por Cesar en la Fase C de W5 V2). Donde un `evidence_min_criteria` es compuesto
(p. ej. *"Alta, cambio, revisión periódica y revocación de cuentas"*), la descomposición lo
parte en sus assertions atómicas. **No se añade ninguna exigencia nueva. No se elimina
ninguna.**

## 2. Reglas duras (no cambian con esta propuesta)

- **Cero LLM en runtime.** La descomposición es estática, autorada una vez, versionada.
- **El verificador no se toca.** `evidence_verifier` (validación A, umbral fuzzy 0.93,
  exigencia de cita anclada) sigue igual. La cita citable de cualquier `observed` sigue siendo
  el `Claim.source_text` literal, nunca el sub-criterio ni el `normalized_statement`.
- **El test negativo obligatorio `ANNEX11_4`** (GAMP5 en lista de referencias) debe seguir
  rechazándose. La descomposición de `ANNEX11_4` está redactada para que una entrada
  bibliográfica no pueda satisfacer ningún sub-criterio.
- **`decomposition[]` es contenido gobernado**: mismo régimen que `evidence_min_criteria` —
  `prompt_version`/versión de catálogo nueva y firma de Cesar por cada cambio. Nunca un ajuste
  silencioso para mover una métrica (skill `gmp-recall-pipeline`, prohibición central).
- **La descomposición NO es una checklist de cumplimiento.** Un requisito con todos sus
  sub-criterios `MET` sigue yendo a revisión humana. El sistema no declara cumplimiento final.

## 3. Forma en `decomposition.yaml` (archivo gobernado hermano, firmado)

```yaml
21_CFR_11.10(e):
  # ... campos existentes sin cambios ...
  decomposition:
    - id: "sc1"
      text: "existe un audit trail generado automáticamente por el sistema, sin intervención del operador"
      derived_from: ["evidence_min_criteria[0]", "citation_text"]
    - id: "sc2"
      text: "cada entrada del audit trail registra fecha y hora"
      derived_from: ["evidence_min_criteria[1]", "citation_text"]
    # ...
```

`id` es estable (`<requirement_id>::<id>`) — retrieval, juicio y findings lo referencian.
`derived_from` es trazabilidad de autoría (qué `evidence_min_criteria`/`citation_text` origina
el sub-criterio), para que la revisión de Cesar sea verificable línea a línea.

---

## 4. Descomposición propuesta — 21 CFR Part 11

### 21_CFR_11.10(a) — Validación del sistema
1. existe un enfoque de validación documentado, basado en riesgo y uso previsto
2. los criterios de aceptación se definieron antes de ejecutar la validación
3. hay evidencia real de ejecución: protocolo ejecutado, resultados registrados, desviaciones documentadas si las hubo
4. existe trazabilidad requisito ↔ prueba ↔ resultado
5. el sistema puede discernir registros inválidos o alterados, por algún mecanismo técnico demostrado

### 21_CFR_11.10(d) — Acceso limitado a individuos autorizados
1. existe un mecanismo de control de acceso al sistema (propio o federado), descrito
2. hay un proceso de alta de cuentas
3. hay un proceso de cambio de privilegios de cuentas
4. hay revisión periódica de cuentas y accesos
5. hay un proceso de revocación de cuentas
6. las cuentas humanas son individuales, no compartidas
7. las cuentas técnicas no interactivas, si existen, tienen propietario, propósito y privilegio mínimo declarados, y no pueden firmar electrónicamente
8. hay evidencia de prueba de acceso permitido y de acceso denegado

### 21_CFR_11.10(e) — Audit trail seguro con timestamp
1. existe un audit trail generado automáticamente por el sistema, sin intervención del operador
2. cada entrada del audit trail registra fecha y hora
3. el audit trail registra las acciones de crear, modificar y eliminar registros electrónicos
4. al modificar un registro, el audit trail preserva el valor o la información previa (no solo el nuevo valor)
5. el acceso para modificar el propio audit trail está restringido a usuarios privilegiados
6. el audit trail permite detectar manipulación / es trazable
7. la modificación silenciosa del audit trail está impedida y es detectable
8. el audit trail se retiene por un periodo igual o mayor al del registro asociado
9. el audit trail se puede exportar o copiar para inspección

### 21_CFR_11.10(g) — Verificación de autoridad (authority checks)
1. existe una matriz de operaciones del sistema con el nivel de autorización requerido por cada una
2. el sistema ejecuta un chequeo técnico de autoridad en el momento de cada operación aplicable (firmar, alterar un registro, acceder a E/S, ejecutar la operación)
3. hay evidencia de prueba negativa: un intento de operación sin autoridad suficiente resulta bloqueado

### 21_CFR_11.50 / 11.70 — Firma electrónica: manifestación y vínculo al registro
1. cada firma electrónica muestra el nombre impreso del firmante
2. cada firma electrónica muestra la fecha y hora en que se ejecutó
3. cada firma electrónica muestra el significado asociado (revisión, aprobación, responsabilidad, autoría)
4. esos tres elementos son legibles y están asociados al registro firmado
5. los controles del registro electrónico (acceso, integridad, retención, disponibilidad) se extienden a los tres elementos de la firma
6. existe un mecanismo técnico protegido que ata la firma al registro específico
7. hay prueba de que ese mecanismo impide extraer, copiar o transferir la firma por medios ordinarios

---

## 5. Descomposición propuesta — EU GMP Annex 11

### ANNEX11_4 — Gestión de riesgo del sistema computarizado
1. existe documentación de validación que cubre las etapas relevantes del ciclo de vida del sistema
2. existe una evaluación de riesgo real y documentada del sistema computarizado
3. hay una conexión explícita y trazable entre esa evaluación de riesgo y las decisiones de validación tomadas (alcance, protocolos, criterios de aceptación, procedimientos, registros)

> Nota de guardián (negativo obligatorio): una entrada bibliográfica que solo nombra "GAMP5"
> u otro estándar no satisface ninguno de estos tres — ninguno se cumple por la mención de un
> nombre; los tres exigen documentación/evaluación/conexión sustantiva del sistema evaluado.

### ANNEX11_7.1 — Almacenamiento y protección de datos
1. hay medios físicos de protección de datos descritos (acceso restringido a sala de servidores / racks)
2. hay medios electrónicos de protección descritos (redundancia, checksums, control de integridad)
3. hay verificación documentada, con evidencia real, de accesibilidad, legibilidad y exactitud de los datos almacenados
4. existe una frecuencia de reverificación definida según riesgo y procedimiento, cuando el riesgo lo justifica
5. el periodo de retención está declarado y hay evidencia de que el acceso a los datos se mantiene durante ese periodo

### ANNEX11_9 — Audit trail (Annex 11)
1. existe una evaluación de riesgo documentada sobre la necesidad y el alcance del audit trail
2. el sistema genera un audit trail que registra los cambios y las eliminaciones GMP-relevantes
3. para cada cambio o eliminación GMP-relevante, el motivo queda documentado (no solo el hecho del cambio)
4. el audit trail está disponible y es convertible a una forma generalmente inteligible (exportable / legible por humano)
5. hay evidencia de revisión periódica real del audit trail (no solo de su existencia)

### ANNEX11_12 — Seguridad física y lógica
1. hay controles físicos y/o lógicos descritos con un método concreto (llaves, tarjetas, códigos + contraseñas, biometría, acceso restringido a equipos / áreas de almacenamiento)
2. la combinación elegida (físico, lógico o ambos) está justificada según riesgo, arquitectura y entorno del sistema
3. hay evidencia de restricción efectiva a personas autorizadas: lista de autorizados verificada contra el control real, o prueba de acceso denegado a no autorizados

### ANNEX11_17 — Archivo y retención de registros
1. existe un proceso de archivo de datos descrito
2. hay verificación documentada de accesibilidad, legibilidad e integridad de los datos archivados
3. existe una frecuencia de verificación definida según riesgo y procedimiento, cuando el riesgo lo justifica
4. ante cambios relevantes al sistema, hay evidencia de que la capacidad de recuperar los datos archivados fue asegurada y probada

---

## 6. Descomposición propuesta — MHRA GxP DI / ALCOA+

### ALCOA_ATTRIBUTABLE — Atribuible
1. (acción humana) cada dato se identifica de forma única e individual con la persona que lo generó
2. (acción humana) hay un mecanismo técnico que sostiene esa atribución de forma confiable (no solo un campo de texto libre)
3. (acción humana) la atribución se sostiene para crear, modificar y eliminar — no solo para crear
4. (dato autogenerado) hay un identificador específico y trazable del instrumento / sistema / fuente técnica que generó el dato (no una categoría genérica de equipo)
5. (dato autogenerado) hay trazabilidad de que ese instrumento / sistema fue el que efectivamente generó el dato

### ALCOA_LEGIBLE — Legible
1. la legibilidad de los datos está garantizada durante todo el ciclo de vida
2. los datos son permanentes: no hay sobrescritura silenciosa
3. existe un criterio de continuidad de legibilidad cuando el riesgo de obsolescencia del formato es real

### ALCOA_CONTEMPORANEOUS — Contemporáneo
1. como regla general, el registro se hace en el momento de la actividad
2. (caso escribiente) el escribiente registra en el momento de la actividad, no retrospectivamente, e identifica al ejecutor real
3. (caso contrafirma) existe un procedimiento gobernado que define cuándo una contrafirma tardía del ejecutor es aceptable, con motivo real, plazo máximo y revisión

### ALCOA_ORIGINAL — Original
1. el original de primera captura está identificado y preservado, o existe una copia certificada con un proceso real descrito
2. hay evidencia de que la certificación de la copia se ejecutó realmente

### ALCOA_ACCURATE — Exacto
1. hay un mecanismo de verificación de exactitud del dato descrito
2. ese mecanismo cubre todas las formas del dato que pertenecen al proceso y alcance evaluados

### ALCOA_COMPLETE — Completo
1. se capturan todos los datos relevantes del proceso evaluado, incluidos reintentos, reprocesamientos, exclusiones y desviaciones cuando forman parte de ese proceso
2. no hay eliminación selectiva de datos desfavorables que formen parte del proceso evaluado
3. es posible reconstruir completamente la actividad a partir de los datos
4. cuando aplica OOS al proceso evaluado, el tratamiento y registro de los resultados OOS está descrito

### ALCOA_CONSISTENT — Consistente
1. existe una secuencia cronológica consistente (timestamps, numeración de lotes)
2. hay un mecanismo gobernado que detecta inconsistencias reales (humano, técnico/automatizado o equivalente), definido y con registro de ejecución

### ALCOA_ENDURING — Duradero
1. el medio o formato garantiza durabilidad durante todo el periodo de retención
2. existe un criterio de reevaluación según el riesgo de obsolescencia o degradación

### ALCOA_AVAILABLE — Disponible
1. los datos se recuperan sin demora indebida, directamente accesibles cuando se solicitan, y en forma legible para revisión o inspección
2. la recuperación no depende de personal específico ni de sistemas legados sin contingencia

---

## 7. Descomposición propuesta — 21 CFR Part 211

### 21_CFR_211.68(b) — Controles sobre sistemas computarizados
1. hay un mecanismo técnico (no solo una política) que restringe quién puede modificar los registros maestros de producción y control
2. el sistema identifica que la modificación la realizó personal con autorización vigente para ese registro
3. hay un mecanismo descrito de verificación de exactitud de los datos de entrada y salida del sistema
4. el grado o la frecuencia de esa verificación de exactitud está justificado por la complejidad o confiabilidad del sistema
5. hay un mecanismo de respaldo de los datos ingresados, con evidencia de que es exacto y completo
6. hay protección descrita del respaldo contra alteración, borrado accidental o pérdida
7. (caso excepcional) si algún dato se elimina por diseño del proceso automatizado, existe un registro escrito del programa más datos de validación que lo sustenten, en lugar del respaldo

---

## 8. Resumen y preguntas para Capa 9

| Requisito | # sub-criterios | fuente |
|---|---|---|
| 21_CFR_11.10(a) | 5 | citation_text + 5 EMC |
| 21_CFR_11.10(d) | 8 | 5 EMC (2 compuestos desdoblados) |
| 21_CFR_11.10(e) | 9 | 9 EMC (1:1) |
| 21_CFR_11.10(g) | 3 | 3 EMC (1:1) |
| 21_CFR_11.50_11.70 | 7 | 4 EMC (desdoblados) |
| ANNEX11_4 | 3 | 3 EMC (1:1) + nota de guardián |
| ANNEX11_7.1 | 5 | 5 EMC (1:1) |
| ANNEX11_9 | 5 | 5 EMC (1:1) |
| ANNEX11_12 | 3 | 3 EMC (1:1) |
| ANNEX11_17 | 4 | 4 EMC (1:1) |
| ALCOA_ATTRIBUTABLE | 5 | 5 EMC (1:1) |
| ALCOA_LEGIBLE | 3 | 3 EMC (1:1) |
| ALCOA_CONTEMPORANEOUS | 3 | 3 EMC (1:1) |
| ALCOA_ORIGINAL | 2 | 2 EMC (1:1) |
| ALCOA_ACCURATE | 2 | 2 EMC (1:1) |
| ALCOA_COMPLETE | 4 | 4 EMC (1:1) |
| ALCOA_CONSISTENT | 2 | 2 EMC (1:1) |
| ALCOA_ENDURING | 2 | 2 EMC (1:1) |
| ALCOA_AVAILABLE | 2 | 2 EMC (1:1) |
| 21_CFR_211.68(b) | 7 | 7 EMC (1:1) |
| **Total** | **84 sub-criterios** sobre 20 requisitos | |

**Impacto en costo de juicio:** hoy 1 llamada por (chunk × requisito). Con descomposición, el
juicio pasa a ser por (EvidenceBundle × sub-criterio). No es ×84: el retrieval V2 (B3) acota
el EvidenceBundle por sub-criterio a ≤5 candidatos, y solo los sub-criterios cuyo bundle trae
candidatos plausibles llegan al modelo. Estimación a validar en FASE 10, no comprometida aquí.

**Preguntas para tu firma:**
1. ¿Aceptas la descomposición como **re-expresión fiel** de `citation_text` + `evidence_min_criteria`, sin exigencias nuevas ni eliminadas?
2. ¿Los desdoblamientos de los EMC compuestos (11.10(d): 5→8; 11.50/11.70: 4→7) preservan la intención?
3. ¿La nota de guardián de `ANNEX11_4` es suficiente para mantener el negativo obligatorio, o quieres un sub-criterio explícito de exclusión?
4. ¿Firmas esto como versión nueva del catálogo (mismo circuito que `evidence_min_criteria`), habilitando el código de B3 que lo consume?

**Firmado 2026-08-27.** `requirements.yaml` no se tocó. Los sub-criterios viven en
`decomposition.yaml` (hermano gobernado). El código de B3 que lo consume procede a partir de aquí.
