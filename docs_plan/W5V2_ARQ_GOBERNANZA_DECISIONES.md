# W5 V2 — ARQ GOBERNANZA DE DECISIONES: CIERRE DE BRECHAS PREVIAS AL CORPUS
# VERSIÓN CONSOLIDADA (reemplaza operativamente a
# W5V2_EVALUACION_COBERTURA_FUENTES.md en lo no ejecutado)
#
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/W5V2_ARQ_GOBERNANZA_DECISIONES.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
# Corrida de AUDITORÍA + DISEÑO en una sola ejecución. Sin pausas
# intermedias salvo: secretos detectados; riesgo de modificar originales o
# auditoría; contradicción técnica que impida un diseño coherente; decisión
# de alcance no resoluble desde el código.
#
# PRODUCTION_ENABLEMENT = BLOCKED. REGULATORY_COMPLIANCE = NOT_DETERMINED.
# CORPUS_READY = false durante toda esta corrida.

──────────────────────────────────────────────────────────────────────────────
0. CONTEXTO, FOCO Y RELACIÓN CON PLANES ANTERIORES
──────────────────────────────────────────────────────────────────────────────

## 0.1 Por qué esta corrida

El bloqueo del corpus NO es regulatorio: es de gobernanza del sistema de
decisiones. Hechos confirmados (aceptar; verificar solo lo indicado en §1):

1.  D1 original fue firmada con ALL cuando existían tres fuentes.
2.  Part 211 (ecfr_21cfr_part211) ingresó al registry después y NO está
    cubierta por D1.
3.  approved_source_ids no tiene consumidor operativo (autorización sin
    enforcement).
4.  La corrección D1 actual no puede almacenar snapshot explícito desde UI.
5.  D1-A no es registrable: DECISION_IDS es una tupla cerrada.
6.  Las cuatro fuentes continúan PENDING_REVERIFICATION.
7.  El pack de 21_CFR_211.68(b) está incompleto.
8.  La matriz v2.1 y los packs modificados NO están aprobados.
9.  El catálogo cambió de hash pero sigue declarando version 1.0.
10. La calificación del modelo está invalidada.
11. La cadena de auditoría presenta un fork histórico.
12. D4-A depende del número final de criterios del pack.

## 0.2 Camino crítico al corpus (el foco)

Todo lo diseñado aquí sirve a UNA secuencia; nada fuera de ella entra en
alcance:

```
[G1] Modelo extensible de decisiones + enforcement implementados
[G2] Corrección D1 (snapshot 3 fuentes) + D1-A (Part 211) registradas
[G3] Reverificación de las 4 fuentes → LOCAL_CANONICAL_COPY_VERIFIED
[G4] Pack 211 completo + matriz v2.1 aprobada + catálogo versionado
[G5] D2-A/MC-0002 unificada y registrada
[G6] Golden Dataset aprobado + recalificación del modelo
[G7] Excepción humana del fork histórico registrada
[G8] D4-A calculada sobre el pack final y registrada
 →  CORPUS_READY = true
```

Esta corrida DISEÑA G1–G8. No registra decisiones, no reverifica fuentes,
no llama a Ollama, no ejecuta corpus, no modifica auditoría histórica, no
cambia código ni estados.

## 0.3 Estado del plan anterior

W5V2_EVALUACION_COBERTURA_FUENTES.md se ejecutó parcialmente. Documentar en
el gap assessment: qué secciones se completaron (con evidencia) y cuáles se
absorben aquí. La pausa de efectos D1–D5 SE MANTIENE. Los borradores
D1-A/D2-A previos quedan supersedidos por el modelo de §2 (anotarlo en
ellos mediante nota nueva, sin borrarlos).

Entregables de esta corrida en:
factory/docs/design/regulatory_redesign_v2/governance/

──────────────────────────────────────────────────────────────────────────────
1. AUDITORÍA DE ESTADO REAL (solo lectura, con artefactos)
──────────────────────────────────────────────────────────────────────────────

Verificar con API (GET), código, auditoría y artefactos — cada valor con su
evidencia (archivo/endpoint/evento):

- evento que registró ecfr_21cfr_part211; herramienta y actor;
- decisión utilizada (o ausencia de decisión) para ese registro;
- estado real y elegibilidad de Part 211;
- consumidores reales de approved_source_ids (grep de lecturas efectivas
  en código de reverificación, packs, planner, baseline, release);
- consumidores de estados de fuentes;
- gates que consultan decisiones (cuáles, dónde, qué campo leen);
- UI y endpoints disponibles hoy para correcciones y adendos;
- estado real de verify_chain, chain_errors, is_fork, hash_errors.

Reportar:

```
PART211_REGISTRATION_EVENT =
PART211_REGISTERED_BY =
PART211_REGISTRATION_DECISION =
PART211_D1_COVERAGE =
PART211_REVERIFICATION_ALLOWED =
PART211_PACK_USE_ALLOWED =
PART211_FORMAL_USE_ALLOWED =
APPROVED_SOURCE_IDS_CONSUMERS =
D1_OPERATIONALLY_ENFORCED =
D1_CORRECTION_UI_SUPPORTS_EXPLICIT_SOURCE_IDS =
D1_A_REGISTRABLE =
D2_A_REGISTRABLE =
D4_A_REGISTRABLE =
```

──────────────────────────────────────────────────────────────────────────────
2. MODELO EXTENSIBLE DE DECISIONES (diseño autoritativo)
──────────────────────────────────────────────────────────────────────────────

## 2.1 Principio

Las familias de decisión se definen en un REGISTRO DE FAMILIAS (archivo de
datos versionado, p. ej. registry/decision_families.yaml), NO en una tupla
de código. Agregar una familia o un adendo jamás requiere tocar una
constante. Prohibido "resolver" el problema añadiendo nombres a la tupla.

## 2.2 Schema del registro de decisión

```yaml
decision_record:
  decision_family: D1 | D2 | D4 | AUDIT_EXCEPTION | <extensible por registro>
  decision_instance_id: "<familia>-<año>-<secuencia>"   # ej. D1-2026-002
  decision_type: ORIGINAL | CORRECTION | ADDENDUM | SUPERSESSION | REVOCATION
  amendment_sequence: <int>            # 0=original; incrementa por familia
  supersedes_event_id: <event_id | null>
  selection_mode: EXPLICIT_LIST | ALL_SNAPSHOT
  resolved_target_ids: [<ids>]         # SIEMPRE materializada; ver 2.3
  target_set_hash: <sha256 de resolved_target_ids ordenada>
  registry_hash_at_decision: <sha256 del registry al momento de la firma>
  decision_origin: human_confirmed
  approved_by_id: <identidad real>     # 422 para genéricas
  approved_by_display_name: <nombre>
  decision_date: <timestamp>
  reason: <texto>
  status: ACTIVE | SUPERSEDED | REVOKED
  payload: {<campos propios de la familia: cadencia, límites, etc.>}
```

## 2.3 Regla ALL → snapshot en la firma

selection_mode=ALL_SNAPSHOT resuelve el conjunto EN EL MOMENTO DE LA FIRMA
y lo persiste en resolved_target_ids + target_set_hash +
registry_hash_at_decision. "ALL" nunca queda almacenado como comodín
abierto. Consecuencia formal: un id incorporado al registry después de la
firma NO está cubierto — es exactamente el caso Part 211.

## 2.4 Correcciones, adendos, supersesiones, revocaciones

- CORRECTION: reemplaza el contenido de una decisión previa; referencia
  supersedes_event_id; la previa pasa a status=SUPERSEDED (nuevo evento;
  el histórico jamás se reescribe).
- ADDENDUM: amplía el conjunto autorizado sin tocar la decisión previa
  (amendment_sequence+1). Cobertura efectiva de una familia = unión de
  resolved_target_ids de sus registros ACTIVE.
- SUPERSESSION: nueva ORIGINAL que reemplaza toda la familia previa.
- REVOCATION: retira cobertura de ids específicos, gobernada
  (human_confirmed + reason); nunca borra eventos.

## 2.5 Compatibilidad con decisiones históricas

- Lectura: adaptador que proyecta los registros históricos al schema nuevo.
- La D1 histórica (ALL sin snapshot) se proyecta con
  selection_mode=ALL_SNAPSHOT y resolved_target_ids RECONSTRUIDOS desde el
  estado del registry a la fecha de la firma (evidencia: eventos de
  auditoría), marcados provenance=RECONSTRUCTED_SNAPSHOT. La
  reconstrucción NO sustituye a la Corrección D1 formal (§9.A): solo
  permite leer el histórico sin ambigüedad.
- Migración de datos: especificar script, verificación y rollback. Cero
  reescritura de eventos históricos; la proyección vive aparte.

──────────────────────────────────────────────────────────────────────────────
3. ENFORCEMENT OPERATIVO — DecisionScopeResolver
──────────────────────────────────────────────────────────────────────────────

Diseñar UN componente único y obligatorio (factory/core/
decision_scope_resolver.py propuesto) consumido por:

- reverificación de fuentes;
- elegibilidad de Evidence Packs;
- planificador de corpus;
- formal baseline;
- release gate.

API conceptual:

```
resolve(decision_family, target_id) →
  { authorized: bool,
    covering_instances: [decision_instance_id],
    effective_snapshot_hash: <hash> }
```

Reglas duras:
- Presencia en registry NO concede autorización.
- Fuente no cubierta ⇒ AUTHORIZED_BY_D1=false; REVERIFICATION_ALLOWED=
  false; PACK_USE_ALLOWED=false; FORMAL_CONCLUSION_ALLOWED=false.
- Ningún consumidor implementa su propia lectura de decisiones (una sola
  superficie; mismo patrón que path_policy).
- Fail-closed: resolver indisponible o registro corrupto ⇒ no autorizado.

Tests obligatorios (diseñar, listar en TESTS_TO_ADD):
- fuente posterior a un ALL histórico NO hereda cobertura (caso Part 211
  como fixture);
- ADDENDUM amplía cobertura solo para sus ids;
- SUPERSEDED/REVOKED retiran cobertura;
- los 5 consumidores llaman al resolver (test de no-bypass, análogo a
  test_refresh_readonly.py como guardia de Gate 0).

──────────────────────────────────────────────────────────────────────────────
4. CICLO DE VIDA DE FUENTES
──────────────────────────────────────────────────────────────────────────────

## 4.1 Estados inequívocos (máquina única)

```
REGISTERED_PENDING_AUTHORIZATION   (en registry, sin decisión que la cubra)
AUTHORIZED_PENDING_REVERIFICATION  (cubierta por D1/D1-A, sin verificar)
LOCAL_CANONICAL_COPY_VERIFIED
SOURCE_UNAVAILABLE
REVERIFICATION_EXPIRED
REVOKED
```

Transiciones y quién las dispara (humano vs. determinista) documentadas.
Estados actuales (PENDING_REVERIFICATION, etc.) mapeados a la máquina nueva
con tabla de migración.

## 4.2 Cinco dimensiones ortogonales (nunca colapsarlas en un solo flag)

```
COPY_HASH_INTEGRITY            (hash de la copia local intacto)
OFFICIAL_ORIGIN_VERIFICATION   (proviene de la URL oficial primaria)
REGULATORY_CURRENCY            (vigencia; reverification_due)
HUMAN_DECISION_COVERAGE        (resolver §3)
FORMAL_USE_ELIGIBILITY         (conjunción de las cuatro anteriores)
```

FORMAL_USE_ELIGIBILITY=true ⇔ las cuatro dimensiones en verde. Es la ÚNICA
condición que habilita conclusiones formales sobre esa fuente.

## 4.3 Desviación técnica Part 211

Documentar la incorporación anticipada de Part 211 como DESVIACIÓN TÉCNICA
formal (DEV-W5-001 propuesto): qué pasó, cuándo, por qué la gobernanza no
lo impidió, impacto, y corrección (D1-A + enforcement §3). NO borrar ni
reescribir nada; la desviación es evidencia de que el sistema ahora lo
detecta.

## 4.4 Secuencia obligatoria

El paso real de reverificación de las 4 fuentes ocurre DESPUÉS de registrar
Corrección D1 + D1-A y ANTES de D2-A. Reflejarlo en G2→G3→G5 del camino
crítico y en la UI (§9).

──────────────────────────────────────────────────────────────────────────────
5. EVIDENCE PACK: SUPERFICIE DE PROPUESTA/VALIDACIÓN/APROBACIÓN Y D2-A
──────────────────────────────────────────────────────────────────────────────

## 5.1 Superficie de edición gobernada (sin YAML manual)

Diseñar flujo de tres actores sobre los campos:
evidence_min_criteria; exclusion_criteria; weak_keywords;
typical_insufficient_evidence; governed_interpretation; expected_doc_types.

```
PROPONE  (Claude/LLM): borrador estructurado por campo, con justificación.
VALIDA   (deterministas): schema completo; sin campos vacíos; sin
         duplicados; weak_keywords ⊄ evidence_min_criteria; anclaje del
         canonical_text a la fuente verificada; hash del pack.
APRUEBA  (humano, UI §9.C): aprobar / devolver con comentario / rechazar.
```

Cada aprobación produce pack_version nueva + hash + referencia a la
decisión. El usuario nunca edita YAML a mano; la UI presenta campos.

## 5.2 Unificación D2-A / MC-0002

Regla: UNA SOLA decisión autoritativa. Diseño requerido:
- Auditar qué es MC-0002 hoy (Mission Control) y qué registra.
- Definir: la aprobación de packs se registra como decisión de familia D2
  (decision_type=ADDENDUM o CORRECTION según el caso) mediante el modelo
  §2; MC-0002 queda como VEHÍCULO DE UI que emite ese único evento, o se
  retira. Sin doble fuente de verdad: un evento, un registro, una lectura
  vía resolver. Documentar la relación elegida y su migración.

## 5.3 Precondiciones de D2-A (READY solo cuando TODAS)

- fuente del pack en LOCAL_CANONICAL_COPY_VERIFIED (incluida Part 211 tras
  G3);
- pack 21_CFR_211.68(b) COMPLETO (todos los campos, validadores en verde);
- matriz v2.1 APROBADA (decisión propia, no "PROPUESTA");
- catálogo con VERSIÓN NUEVA (§6).

D2_A_READY es calculado por el resolver + validadores, nunca declarado a
mano.

──────────────────────────────────────────────────────────────────────────────
6. VERSIONADO INMUTABLE Y TRAZABLE
──────────────────────────────────────────────────────────────────────────────

## 6.1 Corregir la inconsistencia actual

catalog_sha256 cambió con catalog_version=1.0 intacta. Diseñar la
corrección: nueva versión de catálogo (propuesta: 2.0 si el cambio es
material por Part 211; justificar la elección semántica), referenciando
hash anterior, hash nuevo y la decisión humana que lo aprueba. El catálogo
1.0 histórico queda inmutable y direccionable.

## 6.2 Regla general para catálogo, matriz, packs, prompts, Golden Dataset

```
version_record:
  artifact: catalog | applicability_matrix | evidence_pack | prompt | golden_dataset
  artifact_id: <id>
  version: <semver>
  sha256: <hash del contenido>
  previous_version: <semver | null>
  previous_sha256: <hash | null>
  approved_by_decision: <decision_instance_id>
  created_at: <timestamp>
```

Invariante verificable por test: hash cambia ⇔ versión cambia ⇔ existe
decisión que lo aprueba. Guardia de Gate 0: detector de "hash cambiado con
versión igual" en los cinco artefactos.

## 6.3 Alcance 210 vs. 211 — resolución definitiva

Determinar desde los artefactos reales qué se registró y qué exige el
alcance W5 (fichas de cobertura previas + matriz + allowlist):
- Si solo Part 211 sustenta requisitos aplicables a los documentos
  Rockwell analizables: alcance = Part 211 únicamente; corregir TODOS los
  documentos y planes que digan "210/211" (listarlos con ruta y línea).
- Si Part 210 sustenta algún requisito aplicable concreto: alcance =
  210+211; entonces Part 210 requiere su propio registro + cobertura D1-A
  + verificación (añadir al camino crítico).
Presentar la evidencia y la recomendación; la decisión es de Cesar (queda
como campo del paquete D1-A en §9.B).

──────────────────────────────────────────────────────────────────────────────
7. AUDITORÍA: FORK HISTÓRICO Y PREVENCIÓN
──────────────────────────────────────────────────────────────────────────────

## 7.1 Reporte separado (corrige el colapso actual)

PROHIBIDO declarar part11_compliant=true mientras verify_chain=false,
chain_errors=1, is_fork=true. Este criterio SUPERSEDE la regla operativa
anterior ("fork = WARN con part11_compliant=true"); documentar la
supersesión y su motivo. Reporte separado por dimensión:

```
CONTENT_HASH_INTEGRITY =        (hash_errors)
CHAIN_CONTINUITY =              (verify_chain / chain_errors)
HISTORICAL_FORK_PRESENT =       (is_fork del evento conocido)
NEW_FORKS_SINCE_BASELINE =      (debe ser 0)
PART11_COMPLIANCE = NOT_DETERMINED   (hasta excepción humana registrada)
```

## 7.2 Diseño requerido

- PREVENCIÓN de forks nuevos: single writer (proceso único de escritura o
  lock transaccional sobre la cadena — evaluar contra el fcntl.flock
  existente de audit_writer.py y cerrar la ventana de concurrencia real
  que produjo el fork; diseñar con evidencia del mecanismo actual).
- BASELINE del fork histórico: identificar el evento exacto, congelarlo
  como referencia (event_id + posición + hashes) para distinguir histórico
  de nuevo.
- ALERTA fail-closed: NEW_FORKS_SINCE_BASELINE > 0 ⇒ bloqueo de corridas y
  de registro de decisiones + alerta; integrar a Gate 0.
- PAQUETE DE EXCEPCIÓN HUMANA (UI §9.E): fork, causa raíz, riesgo
  evaluado, medidas preventivas implementadas, aceptación o rechazo por
  Cesar (human_confirmed). Solo con la excepción ACEPTADA puede la
  dimensión CHAIN_CONTINUITY reportarse como
  ACCEPTED_WITH_DOCUMENTED_EXCEPTION (nunca como "sin errores").
- CERO reescritura de eventos históricos.

──────────────────────────────────────────────────────────────────────────────
8. RECALIFICACIÓN DEL MODELO Y D4-A
──────────────────────────────────────────────────────────────────────────────

## 8.1 Precondiciones de recalificación (orden estricto)

Solo ejecutable después de: fuentes verificadas (G3); pack aprobado (G4);
matriz aprobada (G4); catálogo versionado (G4); Golden Dataset aprobado
(G6, versionado según §6). La calificación previa queda INVALIDATED con
referencia a qué cambio la invalidó.

Distinguir en el diseño: CONSULTA DE METADATA del modelo (nombre, digest,
context window — permitida siempre, no es inferencia) vs. INFERENCIA
(prohibida hasta la recalificación misma, que es la primera inferencia
autorizada y va contra el Golden Dataset).

## 8.2 D4-A (calcular DESPUÉS del pack final)

```
max_calls =
estimated_runtime_min =
estimated_runtime_likely =
estimated_runtime_max =
hard_stop_calls =                 # tope duro > max_calls con margen definido
hard_stop_wall_time =
checkpoint_mode = per_document
resume_fingerprint_required = true
```

PROHIBIDO usar 40,0 h (u otra cifra) como definitiva hasta conocer el
número final de criterios del pack. En esta corrida: diseñar la fórmula
(docs analizables × requisitos aplicables × chunks filtrados × criterios ×
latencia medida p50/p95 de la calificación) y dejar el cálculo
parametrizado; D4-A se llena en G8.

──────────────────────────────────────────────────────────────────────────────
9. DISEÑO DE INTERFAZ — Gobierno → Decisiones W5
──────────────────────────────────────────────────────────────────────────────

Diseñar (mockup + rutas + endpoints; sin implementar) seis paneles. Reglas
transversales: todo GET de solo lectura (jamás escribe auditoría); cada
POST genera exactamente UN evento; 422 identidad inválida/genérica; 409
duplicación; NINGUNA decisión ejecuta automáticamente sus efectos (registrar
≠ ejecutar); UI vía app estática existente + factory-api (respetar
registry/ports.yaml; backup de index.html a backups/frontend/ antes de
cualquier cambio futuro).

A. CORRECCIÓN D1: tres source_id originales explícitos (snapshot visible);
   cadencia; motivo; identidad completa (id + display name); evento
   supersedido mostrado.
B. D1-A: ecfr_21cfr_part211 únicamente (más Part 210 SOLO si §6.3 lo
   concluye, como ítem separado); cadencia; autoridad; leyenda visible de
   ausencia de efectos automáticos.
C. REVISIÓN DEL PACK 211: texto canónico (de la copia verificada);
   criterios propuestos; exclusiones; ejemplos; botones
   aprobar / devolver con comentario / rechazar.
D. D2-A/MC-0002 (unificada según §5.2): packs; versiones; hashes; matriz
   v2.1; catálogo versionado; D2_A_READY calculado visible con sus
   precondiciones en checklist.
E. EXCEPCIÓN DE AUDITORÍA HISTÓRICA: fork; causa; riesgo; medidas
   preventivas; aceptación o rechazo humano.
F. D4-A: llamadas; rango de tiempo (min/likely/max); límites duros;
   fingerprint; ventana de ejecución.

Para cada panel: ruta UI; endpoints GET/POST con schemas; validaciones;
evento de auditoría emitido; estados de error.

──────────────────────────────────────────────────────────────────────────────
10. ENTREGABLES Y CIERRE
──────────────────────────────────────────────────────────────────────────────

## 10.1 Entregables (en .../regulatory_redesign_v2/governance/)

1. GOVERNANCE_STATE_AUDIT.md                (§1, con evidencias)
2. EXTENSIBLE_DECISION_MODEL_SPEC.md        (§2 + migración + compat)
3. DECISION_SCOPE_RESOLVER_SPEC.md          (§3 + tests)
4. SOURCE_LIFECYCLE_SPEC.md                 (§4 + DEV-W5-001)
5. EVIDENCE_PACK_GOVERNANCE_AND_D2A_SPEC.md (§5)
6. ARTIFACT_VERSIONING_SPEC.md              (§6 + resolución 210/211)
7. AUDIT_FORK_REMEDIATION_SPEC.md           (§7)
8. MODEL_REQUALIFICATION_AND_D4A_SPEC.md    (§8)
9. GOVERNANCE_UI_SPEC.md                    (§9)
10. GOVERNANCE_IMPLEMENTATION_PLAN.md       (fases, tests, rollback,
    checkpoints humanos, esfuerzo)

Todos sanitizados (greps estándar de secretos/raw responses/texto Rockwell).

## 10.2 Bloque de presentación final (valores reales)

```
ROOT_CAUSES =
GOVERNANCE_GAPS =
REGULATORY_STATE_GAPS =
UI_GAPS =
VERSIONING_GAPS =
AUDIT_GAPS =

TARGET_DECISION_MODEL =
TARGET_SOURCE_LIFECYCLE =
TARGET_APPROVAL_SEQUENCE =        (G1→G8 con dependencias verificadas)
TARGET_UI_ROUTES =
TARGET_API_ENDPOINTS =
DATA_MIGRATION_REQUIRED =
BACKWARD_COMPATIBILITY_PLAN =

FILES_TO_CHANGE =
TESTS_TO_ADD =
IMPLEMENTATION_PHASES =
CHECKPOINTS_HUMANOS =             (uno por G del camino crítico, mínimo)
ROLLBACK_PLAN =
ESTIMATED_EFFORT =

SCOPE_210_VS_211_RESOLVED =       (recomendación + evidencia; decisión de Cesar)
PART211_DEVIATION_DOCUMENTED =    (DEV-W5-001)
PART11_COMPLIANCE = NOT_DETERMINED
CONTENT_HASH_INTEGRITY =
CHAIN_CONTINUITY =
HISTORICAL_FORK_PRESENT =
NEW_FORKS_SINCE_BASELINE =

D1_CORRECTION_REGISTRATION_READY =
D1_A_REGISTRATION_READY =
D2_A_REGISTRATION_READY =
AUDIT_EXCEPTION_READY =
D4_A_REGISTRATION_READY =
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

## 10.3 Confirmaciones de cierre

- No se registraron decisiones; no se reverificaron fuentes; no se llamó a
  Ollama; no se ejecutó corpus; no se modificó auditoría histórica; no se
  cambió código ni estados; `git status` solo con .md nuevos; Gate 0 PASS.
- Proponer (no ejecutar) un único commit de documentación del diseño.

DETENERSE para aprobación de Cesar del diseño completo. La implementación
(G1 en adelante) es el ciclo siguiente, por fases con checkpoint humano
por cada G del camino crítico.
