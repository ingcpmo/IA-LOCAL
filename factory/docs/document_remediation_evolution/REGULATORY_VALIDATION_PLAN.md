# REGULATORY_VALIDATION_PLAN — Golden Dataset y criterios de aceptación

Diseño únicamente. No se crea el dataset en esta auditoría — se especifica
su estructura y se ancla en los 2 casos reales ya existentes, tal como pidió
el usuario.

## 1. Casos de referencia ya reales (no hipotéticos)

| Caso | Rol en el Golden Dataset | Evidencia real |
|---|---|---|
| `PKG-FS-V1-2-MEDIUM-RISK-REAL` v1 | **Referencia positiva** — `classification=VALIDATED_REFERENCE_CASE` (registrado en `factory/audit/package_classification_log.jsonl`), ciclo completo `medium-risk-batch`→`APPROVE_CLEAN` probado en vivo, `COR-1`/`FSV12-11` con cita literal real, anclaje unívoco, `gxp_impact` derivado de `binding_status` real | Verificado en vivo contra factory-api, `PACKAGE_READY_FOR_RELEASE`, `RELEASE_RECORD_CREATED=false` |
| `PKG-FS-V1-2-REAL-CONTROLLED` v1 | **Caso negativo, no elegible como precedente** — `classification=VALIDATION_CASE_WITH_KNOWN_ISSUES`, `reference_eligible=false`, cuarentena declarada por 3 `known_issues` (COR-2 con `ABSENCE_CONFIRMATION` posiblemente desactualizado — investigado e INCONCLUSO en `CURRENT_STATE_AUDIT.md` §5; trazabilidad de aprobación a revisar; no usar como precedente regulatorio) | Registrado en el mismo log de clasificación |

Ambos casos usan contenido **real** (Rockwell FS_v1.2, sha256
`56095a7541fbb62e30d00e77308fde4c2ac0f4ec945adbf19a968b79debc82eb`) — no son
sintéticos, lo que los hace más valiosos como golden cases que el smoke test
sintético anterior (`PKG-LIVE-VALIDATION`, ya limpiado).

## 2. Taxonomía completa de casos exigida por el objetivo (diseño de cobertura)

| Categoría exigida | Caso real ya disponible | Caso pendiente de construir |
|---|---|---|
| Cumplimiento documental | — | No hay ningún caso real de "requisito ya cumplido, cita positiva" — los 19 findings de FS_v1.2 son todos brecha/desviación/insuficiencia (`distribucion_clasificacion_brecha`: 0 `DEMONSTRATED_NONCOMPLIANCE`, 0 casos de cumplimiento pleno) |
| Cobertura parcial | `COR-5`/`FSV12-07` (10 rangos evaluados, 5 con evidencia, 5 sin) | ya cubierto |
| Ausencia real | `COR-2`/`FSV12-13` (ausencia confirmada, `coverage_complete` en cuarentena) | Necesita un segundo caso con `coverage_complete` verificado por `absence_consolidator` real (no por la regla más débil del mapper) para servir de contraste explícito |
| Falsa ausencia (chunk rechazado que parecía ausencia) | El propio incidente histórico W5.5 (commit `490fbf1`) es el caso real documentado, pero no está empaquetado como `RemediationChange`/paquete BATCH_AND_EXCEPTION | Empaquetar ese incidente histórico como fixture negativo explícito |
| Cita correcta | `COR-1`/`FSV12-11` (auto-marcador "Page 40 of 58"/anclaje por chunk) | ya cubierto |
| Cita irrelevante | — | No existe caso real — construir con un finding donde `_is_topically_relevant` (chunked_engine) o `unverified_reference` (claim_verifier) ya detectó el patrón, si existe alguno en `factory/regulatory/case_memory/cases.jsonl` |
| Fuente desactualizada o inaccesible | **Ya real, encontrado en esta misma auditoría**: EU Annex 11 y MHRA GxP DI 2018 devuelven 404 ahora mismo (ver `REGULATORY_SOURCE_ACCESS_AUDIT.md`) | ya cubierto, con evidencia en vivo |
| Contradicción | El patrón de `chunked_engine.py` (`cumple_parcialmente + revision_humana_requerida=True` cuando hay contradicción entre chunks) | Buscar un finding real de los 19 con esa marca, o de otro documento ya procesado (`c8_alcoa_validator`, `oos_hplc_investigator`) |
| Requisito no aplicable | `applicability_matrix.yaml` ya define `out_of_document_scope` como valor válido | Ningún finding real de FS_v1.2 usa ese valor — construir caso sintético controlado, marcado explícitamente como tal (no mezclar con casos reales sin etiquetar) |
| Recomendación ilógica o mal redactada | — | No existe — requiere `LANGUAGE_AND_TECHNICAL_QUALITY_GATES.md` implementado primero para poder clasificar objetivamente qué cuenta como "mal redactada" |
| Cambio que inventa una capacidad | — | Construir caso sintético controlado (verbo de afirmación en vez de recomendación, ver §2 de `LANGUAGE_AND_TECHNICAL_QUALITY_GATES.md`), etiquetado explícitamente como sintético |
| Riesgos LOW/MEDIUM/HIGH | MEDIUM real (`COR-1`), HIGH real (`COR-5`, `COR-2`) | **Falta LOW_RISK real** — de los 19 findings de FS_v1.2, ninguno mapea hoy a `LOW_RISK` bajo las reglas actuales del mapper (verificado: los 3 findings mapeables dieron 2×HIGH + 1×MEDIUM). Requiere revisar otro documento del corpus (`c8_alcoa_validator`, `oos_hplc_investigator`) o ajustar deliberadamente un caso sintético etiquetado |
| Paquete válido | `PKG-FS-V1-2-MEDIUM-RISK-REAL` | ya cubierto |
| Paquete con known_issues | `PKG-FS-V1-2-REAL-CONTROLLED` | ya cubierto |

**Hallazgo de esta auditoría**: de las 14 categorías exigidas por el
objetivo, **5 tienen un caso real ya disponible sin construir nada nuevo**,
1 tiene evidencia real recién encontrada en esta misma sesión (fuentes
rotas), y **8 no tienen todavía ningún caso real** — quedan como trabajo de
recolección/construcción explícita, nunca inventados como si fueran reales.

## 3. Regla de higiene del dataset (no negociable)

Todo caso que no provenga de un documento/finding real debe llevar una
marca explícita `SYNTHETIC_TEST_CASE=true` visible en el propio caso —
mismo principio ya aplicado en esta sesión a los datos sintéticos del smoke
test (`[VALIDACION SINTETICA]` en cada campo de texto). Nunca se mezcla un
caso sintético con un caso real sin esa marca.

## 4. Criterios mínimos de aceptación (los 12 exigidos por el objetivo, con mecanismo de verificación)

| Criterio | Mecanismo de verificación (reutiliza lo ya existente) |
|---|---|
| 100% salidas válidas contra schema | `remediation_package_schemas.validate_remediation_change()` — ya existe, ya se ejecuta como test (`test_mapped_change_passes_real_schema_validation`) |
| 100% requisitos con aplicabilidad trazable | `applicability.py` + matriz aprobada — ya existe, restringido a `run_context=validation` |
| 100% referencias con fuente oficial | `regulatory_catalog.known_entry_ids()` — ya existe, fail-closed |
| 100% enlaces y citas verificadas | **Gap real**: hoy la verificación de enlace es manual (como en esta auditoría); requiere el `source_currency_checker` de `TARGET_REGULATORY_ARCHITECTURE.md` §2 |
| 0 citas inventadas | `citation_text_sha256` recalculado — ya existe, fail-closed |
| 0 `DOCUMENTATION_GAP` con cobertura parcial | `absence_consolidator.coverage_complete` obligatorio — ya existe; **requiere la unificación de `TARGET_REGULATORY_ARCHITECTURE.md` §6** para aplicar también dentro de BATCH_AND_EXCEPTION |
| 0 cambios sin requisito, evidencia y justificación | Ya forzado por schema (`_CHANGE_REQUIRED_FIELDS`) — sin cambios necesarios |
| 0 cambios con redacción inválida | **Gap real**: requiere `LANGUAGE_AND_TECHNICAL_QUALITY_GATES.md` implementado |
| 0 afirmaciones de implementación sin evidencia | **Gap real**: mismo documento, §5 |
| 0 divergencias entre artefactos | Hoy verificado manualmente (scripts ad hoc de esta sesión); requiere el reverify automatizado de `DOCUMENT_REMEDIATION_SPEC.md` §5 |
| 0 HIGH_RISK pendientes al aprobar paquetes | Ya forzado por `record_package_decision()`: `IncompleteExceptionCoverageError` si `high_risk_exception_ids` no cubre exactamente `changes.high_risk` — verificado en vivo dos veces esta sesión |
| 0 liberaciones automáticas | Ya garantizado: sin endpoint de release, verificado en cada paquete de esta sesión (`RELEASE_ENDPOINT_PRESENT=false`, 404 real) |

**Resumen**: de los 12 criterios, **5 ya están satisfechos por código
existente y probado**, **1 está parcialmente satisfecho pendiente de
unificación de reglas**, y **6 dependen de componentes de este diseño que
todavía no existen** (verificación de enlaces automatizada, quality gates de
redacción, reverify automatizado de artefactos).

## 5. Ejecución del plan (fases, sin código todavía)

1. Recolectar los 8 casos reales faltantes de §2 sobre el corpus ya
   existente (`c8_alcoa_validator`, `oos_hplc_investigator`, otros
   documentos de `GMPAI/source/`) antes de construir ningún caso sintético.
2. Construir los casos sintéticos estrictamente necesarios (recomendación
   ilógica, capacidad inventada, requisito no aplicable) con la marca
   `SYNTHETIC_TEST_CASE=true`.
3. Ejecutar los 12 criterios de §4 contra el dataset completo una vez
   recolectado — no antes, para no medir contra un conjunto incompleto.
4. Cualquier fallo de un criterio bloquea el avance de fase en
   `IMPLEMENTATION_ROADMAP.md` — no se marca como aceptado con excepciones.
