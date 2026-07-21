# IMPLEMENTATION_ROADMAP — Fases de implementación

Diseño únicamente. Ninguna fase se ejecuta en esta auditoría.
`PRODUCTION_ENABLEMENT` permanece `BLOCKED` en todas las fases — ninguna fase
de este roadmap lo desbloquea; el desbloqueo de release es una decisión
separada, futura, explícitamente humana, fuera del alcance de este roadmap.

## Principio de secuenciación

Cada fase solo empieza cuando la anterior pasa sus propios gates de
aceptación (`REGULATORY_VALIDATION_PLAN.md` §4) — no hay paralelismo que
comprometa esto. Cada fase reutiliza lo `VALIDATED`/`PARTIALLY_VALIDATED` ya
existente (`CURRENT_STATE_AUDIT.md`) antes de construir nada nuevo.

## Fase 0 — Cerrar huecos de higiene sin construir nada nuevo (bajo riesgo)

- Investigar el `known_issue` de `COR-2` hasta una conclusión verificable
  (hoy `EVALUATION_INCOMPLETE`, ver `CURRENT_STATE_AUDIT.md` §5) —
  probablemente requiere revisar si existe una versión del documento fuente
  posterior a v5, o confirmar que la causa es la regla de cobertura más
  débil del mapper (§6 de este análisis).
- Corregir la imprecisión de conteo "8 ALCOA+" → 9 en el comentario de
  `regulatory_catalog.py` (higiene documental, cero riesgo).
- Reverificar manualmente (una vez, no automatizado todavía) las 2 URLs
  rotas encontradas (Annex 11, MHRA) y decidir humanamente si se actualizan
  con una URL verificada — nunca inventada.

## Fase 1 — Verificación de vigencia de fuentes (`TARGET_REGULATORY_ARCHITECTURE.md` §2)

- `source_currency_checker`: job read-only, mismo patrón de rate-limit y
  auditoría que `regulatory_connector_service.py` ya usa.
- `broken_link_report`: append-only, nunca auto-reemplaza.
- Gate de salida: existe un log append-only (`source_currency_log.jsonl`)
  con verificación real y timestamp de última ejecución para las 3 fuentes.
  **`registry.json` y su schema (`source_registry_entry_v1.json`) NUNCA se
  modifican para esto** -- `regulatory_currency_status` queda fijo en
  `pending_reverification` por diseño (el propio schema lo declara: "NUNCA
  'verified_current'/'current' en este ciclo"); escribirle un timestamp
  real habría exigido migrar un schema ya endurecido a propósito y
  debilitar esa garantía fail-closed. El resultado de cada verificación
  vive únicamente en el log separado.

## Fase 2 — Unificar la regla de cobertura (`GAP_AND_DEVIATION_MODEL.md` §2, `TARGET_REGULATORY_ARCHITECTURE.md` §6)

- `gap_assessment_finding_mapper.py` deja de reimplementar su propia regla
  de `coverage_status` para el caso multi-rango y consume
  `absence_consolidator.consolidate()` real cuando aplica.
- Gate de salida: los tests existentes del mapper (17) siguen pasando +
  nuevos tests que confirman que un finding con `coverage_complete=False`
  real nunca puede llegar a `ABSENCE_CONFIRMED` vía el mapper (hoy es
  posible, es el hueco que probablemente explica el `known_issue` de COR-2).

## Fase 3 — Cablear el pipeline verificado al motor de producción (`TARGET_REGULATORY_ARCHITECTURE.md` §5)

- Flag opcional `use_verified_pipeline` en `chunked_engine.evaluate_chunked()`,
  detrás de aprobación humana explícita (mismo patrón `run_context` de
  `applicability.py`).
- Gate de salida: correr el pipeline verificado sobre `FS_v1.2.pdf` (mismo
  documento ya usado en toda esta sesión) y comparar sus 19 findings contra
  los ya existentes en `findings_completos_FS_v1_2_v5.json` — cualquier
  divergencia se documenta, no se oculta.

## Fase 4 — Representación intermedia con estructura preservada (`DOCUMENT_REMEDIATION_SPEC.md` §2)

- Extractor nuevo sobre `pdfplumber` (ya validado, reutilizado) que produce
  jerarquía de secciones/numeración, no solo texto plano por página.
- Gate de salida: la extracción de `FS_v1.2.pdf` reproduce la numeración de
  secciones real del documento (verificable a ojo contra el PDF real, sin
  automatizar el criterio de aceptación de esta fase — es humano por
  naturaleza).

## Fase 5 — Documento candidato completo + redline real + reseña final (`DOCUMENT_REMEDIATION_SPEC.md` §2-6)

- Aplicación de `RemediationChange` ya validados (`COR-5`, `COR-2`, `COR-1`
  de los paquetes reales existentes) sobre la representación de Fase 4,
  generando el candidato DOCX completo y el redline real.
- Gate de salida: `DOCUMENT_CONFORMANCE` automatizado (§5 de
  `DOCUMENT_REMEDIATION_SPEC.md`) en 100% de los 3 cambios reales ya
  aprobados por Cesar en esta sesión.

## Fase 6 — Quality gates de redacción (`LANGUAGE_AND_TECHNICAL_QUALITY_GATES.md`)

- Detector de capacidad inventada (§2), gates deterministas de redacción
  (§3), coherencia con el resto del documento (§4, depende de Fase 4).
- Gate de salida: los 3 `proposed_content` reales ya existentes pasan los 6
  controles sin ningún `CHANGE_NOT_APPLIED` — si alguno falla, es señal
  real de que el gate está mal calibrado o de que el cambio real tenía un
  problema no detectado hasta ahora (cualquiera de los dos es información
  válida, no se fuerza un resultado).

## Fase 7 — Golden Dataset completo (`REGULATORY_VALIDATION_PLAN.md`)

- Recolectar los 8 casos reales faltantes antes de construir sintéticos.
- Ejecutar los 12 criterios de aceptación contra el dataset completo.
- Gate de salida: 12/12 criterios en verde, con evidencia real (no
  inferida) para cada uno.

## Fase 8 — Revisión de arquitectura final y decisión de habilitación

- Consolidar evidencia de Fases 0–7 en un informe único.
- **Decisión explícitamente fuera de este roadmap**: si/cuándo/cómo se
  habilita un endpoint de release — requiere aprobación humana de QA
  autorizado, nunca una consecuencia automática de completar las fases
  anteriores. Completar todas las fases mejora la conformidad documental y
  la trazabilidad — no constituye, por sí solo, autorización de liberación.

## Resumen de dependencias entre fases

```
Fase 0 (higiene) ─┬─→ Fase 1 (vigencia de fuentes) ─┐
                   └─→ Fase 2 (unificar cobertura) ──┼─→ Fase 3 (cablear verificado)
                                                       │
Fase 4 (extracción estructurada) ─────────────────────┴─→ Fase 5 (candidato completo)
                                                              │
                                              Fase 6 (quality gates) ←─┘
                                                              │
                                              Fase 7 (golden dataset) ─→ Fase 8 (decisión humana)
```

## Confirmación final de esta auditoría

```
CURRENT_CAPABILITY              = análisis de gaps por chunk (VALIDATED, producción real,
                                   sin pipeline verificado cableado) + flujo de revisión
                                   humana de cambios documentales sin release (VALIDATED,
                                   probado en vivo 2× esta sesión) + generación de memo de
                                   remediación independiente (VALIDATED, pero no es
                                   documento completo)
VALIDATED_COMPONENTS            = chunked_engine.py; evidence_verifier.py (aislado);
                                   absence_consolidator.py (aislado); applicability.py+matriz
                                   (aprobada, restringida a validation); regulatory_catalog.py
                                   (19 entradas, no cableado a prompts de producción);
                                   remediation_package_service.py+schemas+API (94+ tests,
                                   2 paquetes reales verificados en vivo); 
                                   gap_assessment_finding_mapper.py (17 tests, 3 casos reales
                                   en vivo); conectores openFDA (3, reales); audit_writer.py
                                   (cadena hash, WARN preexistente sin regresión)
MANUAL_COMPONENTS               = mapeo finding→RemediationChange para findings fuera de los
                                   3 ya cubiertos; automatic_evaluation_basis (construido a
                                   mano en los 2 paquetes reales, sin adaptador real desde
                                   chunked_engine); reverificación de hashes/artefactos entre
                                   paquetes (scripts ad hoc de esta sesión); reverificación de
                                   acceso/vigencia de fuentes regulatorias (ejecutada
                                   manualmente en esta auditoría)
REGULATORY_ACCESS_STATUS        = REGULATORY_SOURCE_UNVERIFIED para las 3 fuentes (vigencia
                                   nunca reverificada); 2 de 3 URLs oficiales declaradas
                                   devuelven 404 ahora mismo (Annex 11, MHRA GxP DI 2018),
                                   verificado en vivo en esta auditoría; hash local íntegro
                                   en las 3
GAPS                            = generación de documento candidato completo (no existe);
                                   redline real (no existe, solo resumen); matriz de
                                   trazabilidad como artefacto (no existe, modelo disperso);
                                   reseña de cambios y fundamento regulatorio (no existe);
                                   quality gates de redacción/coherencia (no existen);
                                   reverify automatizado de artefactos (manual hoy);
                                   verificación automatizada de vigencia/acceso de fuentes
                                   (manual hoy); unificación de la regla de cobertura entre
                                   absence_consolidator y gap_assessment_finding_mapper (no
                                   unificadas — huecos independientes)
DEVIATIONS                      = verified_pipeline.py DESIGN_ONLY pese a estar probado y
                                   haber corregido 2 incidentes reales de producción (W5.5,
                                   W5.6) — el motor de producción no lo usa; 
                                   gap_assessment_finding_mapper.py reimplementa una regla de
                                   cobertura más débil que la ya endurecida de
                                   absence_consolidator.py; known_issue de COR-2 declarado
                                   pero no confirmado ni descartado con la evidencia
                                   disponible (EVALUATION_INCOMPLETE)
DOCUMENT_GENERATION_CAPABILITY  = NOT_VALIDATED — no existe generación de documento
                                   candidato completo; existe generación de memo de
                                   remediación independiente (gmpai_docx_draft.py) y de
                                   dossier de validación de la propia fábrica
                                   (dossier_generator_service.py), ninguno resuelve el
                                   objetivo pedido
LANGUAGE_QUALITY_CAPABILITY     = NOT_VALIDATED — no existe ningún control de redacción,
                                   coherencia o afirmaciones no demostradas hoy
REGULATORY_VALIDATION_GAPS      = 8 de 14 categorías del Golden Dataset exigido no tienen
                                   caso real todavía; 6 de 12 criterios de aceptación
                                   dependen de componentes que no existen (ver
                                   REGULATORY_VALIDATION_PLAN.md §4)
BLOCKERS                        = ReleaseRecord sin endpoint (por diseño, confirmado);
                                   verified_pipeline.py sin llamador de producción;
                                   2 fuentes regulatorias con URL oficial rota (Annex 11,
                                   MHRA); ausencia de representación estructurada del
                                   documento (bloquea Fase 4-6 completas)
TARGET_CAPABILITY               = análisis por requisito con distinción formal
                                   HALLAZGO/GAP/DESVIACIÓN/RECOMENDACIÓN/CAMBIO_DOCUMENTAL;
                                   fuentes regulatorias con vigencia y acceso reverificados
                                   activamente; documento candidato completo con estructura
                                   preservada, redline real, matriz de trazabilidad y reseña
                                   de cambios; quality gates deterministas de redacción;
                                   revalidación separando DOCUMENT_CONFORMANCE /
                                   IMPLEMENTATION_VERIFICATION / REGULATORY_COMPLIANCE;
                                   Golden Dataset con las 14 categorías cubiertas y 12/12
                                   criterios en verde — decisión de cumplimiento y
                                   liberación permanece siempre humana
IMPLEMENTATION_PHASES           = 9 (Fase 0 a Fase 8, ver arriba), secuenciales con gates
                                   propios, ninguna desbloquea release por sí sola
ACCEPTANCE_GATES                = definidos por fase arriba; consolidados en
                                   REGULATORY_VALIDATION_PLAN.md §4 (12 criterios) y
                                   GAP_AND_DEVIATION_MODEL.md (taxonomía + regla de
                                   cobertura dura)
PRODUCTION_ENABLEMENT           = BLOCKED
```

**Detenido para revisión y aprobación antes de modificar código**, tal como
se pidió. No se implementó código, no se llamó a Ollama, no se modificaron
paquetes/decisiones/auditoría histórica, no se generó ningún `ReleaseRecord`.
