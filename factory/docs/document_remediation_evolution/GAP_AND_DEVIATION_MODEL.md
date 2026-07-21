# GAP_AND_DEVIATION_MODEL — Modelo de análisis por requisito

Diseño únicamente. No se modifica ningún schema ni código existente.

## 1. Taxonomía obligatoria (5 categorías, no intercambiables)

El sistema actual mezcla estos conceptos bajo un único campo
(`clasificacion_brecha` en `findings_completos_*.json`, `change_risk`/
`evidence_status` en `RemediationChange`). Se separan aquí explícitamente
porque el objetivo del usuario los distingue por nombre:

| Categoría | Definición | Quién la produce hoy | Dónde vive hoy |
|---|---|---|---|
| **HALLAZGO** | Observación objetiva sobre el contenido del documento frente a un requisito — puede ser positiva (evidencia encontrada) o negativa (ausencia/insuficiencia) | `chunked_engine.py` (por chunk), consolidado por `absence_consolidator.py` (documento) | `findings_completos_*.json`, campo `evidencia` + `estado_agente_original` |
| **GAP** | Ausencia confirmada de tratamiento de un requisito **con cobertura completa demostrada** — subconjunto estricto de HALLAZGO negativo | `absence_consolidator.consolidate()` (P3, `coverage_complete` obligatorio) | Hoy solo en el pipeline verificado (§2 de `CURRENT_STATE_AUDIT.md`), no en `chunked_engine.py` directamente |
| **DESVIACIÓN** | El documento SÍ trata el requisito pero de forma contradictoria, parcial-sin-evidencia-de-implementación, o inconsistente entre secciones | Parcialmente: `clasificacion_brecha=NOT_DEMONSTRATED_IN_DOSSIER` en los findings reales (ej. `FSV12-07`, `FSV12-11`) captura esto, pero **no existe como categoría propia separada de GAP** en ningún schema actual | — no formalizado |
| **RECOMENDACIÓN** | Texto en lenguaje natural sugiriendo qué agregar/corregir — no es todavía un cambio estructurado | Campo `recomendacion` de los findings reales (texto libre, ya validado como fuente real de `proposed_content` en `gap_assessment_finding_mapper.py`) | `findings_completos_*.json` |
| **CAMBIO_DOCUMENTAL** | Traducción de la recomendación a una unidad estructurada, ubicable, versionable — el `RemediationChange` | `gap_assessment_finding_mapper.py` (mapeo determinista) → `remediation_package_service.py` (persistencia) | `RemediationChange` (schema real, `remediation_package_schemas.py`) |

**Hallazgo de esta auditoría**: hoy **GAP y DESVIACIÓN colapsan en el mismo
campo** (`evidence_status` de `RemediationChange`: `ABSENCE_CONFIRMED` cubre
ambos). Esto es una simplificación real del sistema actual, no un error —
pero el objetivo del usuario exige distinguirlos, así que se diseña la
separación en §2.

## 2. Regla dura para declarar DOCUMENTATION_GAP (ya existe, se reutiliza — no se reinventa)

El objetivo dice: *"DOCUMENTATION_GAP solo puede declararse con cobertura
completa, sin registros rechazados, pendientes ni contradicciones abiertas"*.
**Esta regla ya existe y ya está endurecida por 2 incidentes reales de
producción** en `factory/regulatory/absence_consolidator.py` (W5.5 commit
`490fbf1`, W5.6 commit `fefe258`):

- `coverage_complete` es un parámetro **obligatorio, sin default** — el
  llamador debe declarar explícitamente que TODOS los chunks relevantes
  fueron evaluados.
- Ningún chunk puede haber quedado `rejected_by_verifier` — un chunk
  rechazado nunca "fue observado", así que no puede contar como evidencia de
  ausencia.
- Si cualquiera de las dos condiciones falla → la conclusión es
  `EVALUATION_INCOMPLETE`, **nunca** `DOCUMENTATION_GAP`.

**Decisión de diseño (no implementada aquí)**: `gap_assessment_finding_mapper.py`
(usado por BATCH_AND_EXCEPTION) debe **reutilizar `absence_consolidator.py`**
en vez de mantener su propia regla de `coverage_status` (hoy más simple: solo
mira si `paginas` es un rango único, o si existe
`resolucion_humana_incorporada.tipo_resolucion=='diferencia_de_alcance'` para
el caso multi-rango). Detalle de implementación en
`DOCUMENT_REMEDIATION_SPEC.md` §3.

## 3. Estructura de análisis por requisito (diseño de campos)

Cada fila del análisis por requisito debe registrar, en este orden de
dependencia (cada campo depende de que el anterior esté resuelto):

```
requisito_id                    → regulatory_catalog_entry_id (19 reales hoy, ver catálogo)
aplicabilidad                   → applicability.py + applicability_matrix.yaml (ya existe,
                                   restringido a run_context=validation, ver auditoría §2)
cita_y_enlace_oficial            → catalog_entry.citation + sources/registry.json.official_source_url
                                   (con el estado REGULATORY_SOURCE_UNVERIFIED si aplica,
                                   ver REGULATORY_SOURCE_ACCESS_AUDIT.md)
evidencia_encontrada             → HALLAZGO (positivo o negativo), con locator verificable
                                   (page_start/page_end/chunk_id — regla de anclaje única,
                                   ver gap_assessment_finding_mapper._derive_page_anchor)
cobertura_evaluada               → coverage_complete real (booleano, de absence_consolidator,
                                   NUNCA inferido de un solo campo de texto)
clasificacion                    → HALLAZGO | GAP | DESVIACIÓN (excluyentes, ver §1 y §4)
impacto_y_criticidad             → gxp_impact (derivado de binding_status real, ya
                                   implementado en b975ad7) × requirement_criticality
                                   (severidad) × evidence_status → change_risk
                                   (compute_change_risk(), ya existe y se reutiliza)
recomendacion                    → texto libre del analista/agente (ya existe)
cambio_documental_propuesto      → RemediationChange (ya existe)
ubicacion_exacta                 → citation_locator (ya existe, con la regla de anclaje único
                                   — nunca un rango ambiguo, ver hallazgo de FSV12-19)
limitaciones                     → campo `limitations` de RemediationChange — HOY SIEMPRE
                                   VACÍO en los 3 casos reales de esta sesión (hallazgo de
                                   auditoría: el campo existe en el schema pero nada lo
                                   completa con contenido real todavía)
validacion_posterior             → NUEVO campo, no existe hoy — ver §5 (revalidación)
```

## 4. Regla de exclusión mutua GAP vs. DESVIACIÓN (diseño nuevo)

```
si evidence_status == ABSENCE_CONFIRMED
   y coverage_complete == True (regla absence_consolidator)
   y ningún chunk relevante quedó rejected_by_verifier
   y el requisito es aplicable (applicability != out_of_document_scope)
        → GAP

si evidence_status in (PARTIAL_EVIDENCE, LITERAL_EVIDENCE_CONFIRMED)
   y existe evidencia parcial/contradictoria (ej. cumple_parcialmente,
     NOT_DEMONSTRATED_IN_DOSSIER: descripción presente, sin evidencia de
     implementación)
        → DESVIACIÓN (nunca GAP — el requisito SÍ está tratado, de forma
          incompleta o no verificable, no ausente)

si coverage_complete == False, o algún chunk rejected_by_verifier,
   o hay contradicción abierta entre chunks (cumple vs no_cumple sin resolver)
        → ni GAP ni DESVIACIÓN. EVALUATION_INCOMPLETE. Requiere
          revisión_humana_requerida=True (ya existe como campo real en los
          findings, reutilizado).
```

Esto formaliza —sin reescribir código— una distinción que hoy vive
implícita en el texto de `clasificacion_brecha_rationale` de los findings
reales (ej. `FSV12-13`: *"El FS no documenta el control... no implica que
el control no exista en el sistema real"* → GAP legítimo por ausencia total;
`FSV12-07`: *"Existe descripción parcial... pero el dossier no incluye
evidencia de implementación"* → DESVIACIÓN, no GAP, aunque el sistema actual
lo etiquete con el mismo `evidence_status=PARTIAL_EVIDENCE`).

## 5. `validacion_posterior` — campo nuevo, sin implementación hoy

Ningún artefacto actual registra si un `GAP`/`DESVIACIÓN` fue efectivamente
resuelto por el `CAMBIO_DOCUMENTAL` correspondiente en una revisión
posterior. Se diseña en `DOCUMENT_REMEDIATION_SPEC.md` §5 (revalidación) como
parte del ciclo completo, separando (según exige el objetivo del usuario):

```
DOCUMENT_CONFORMANCE      — el texto del documento candidato ahora trata el
                             requisito (verificable automáticamente:
                             ¿el texto propuesto está presente en el
                             candidato final?)
IMPLEMENTATION_VERIFICATION — el control descrito realmente opera en el
                             sistema (NUNCA automatizable por este sistema —
                             requiere evidencia de prueba/IQ-OQ-PQ externa)
REGULATORY_COMPLIANCE     — determinación final de cumplimiento (SIEMPRE
                             humana, QA autorizado — el sistema nunca la
                             declara, por instrucción explícita del objetivo
                             y por diseño ya vigente: `create_release_record()`
                             sin endpoint, `PRODUCTION_ENABLEMENT=BLOCKED`)
```

## 6. Aplicación retroactiva a los 2 paquetes reales (auditoría, sin modificarlos)

| Change | evidence_status actual | Reclasificación bajo este modelo |
|---|---|---|
| `COR-5` (`FSV12-07`, `ANNEX11_7.1`) | `PARTIAL_EVIDENCE` | **DESVIACIÓN** (descripción parcial presente, sin evidencia de implementación) — coincide con el sistema actual |
| `COR-2` (`FSV12-13`, `ALCOA_CONTEMPORANEOUS`) | `ABSENCE_CONFIRMED` | **GAP**, condicionado a que `coverage_complete` se verifique con la regla real de `absence_consolidator` (hoy se aceptó vía la regla más débil del mapper, ver `CURRENT_STATE_AUDIT.md` §4) — coherente con el `known_issue` declarado por Cesar, sin resolverlo |
| `COR-1` (`FSV12-11`, `ALCOA_ATTRIBUTABLE`) | `PARTIAL_EVIDENCE` | **DESVIACIÓN**, no GAP — mismo patrón que COR-5 |

Ningún change de los 2 paquetes reales es hoy un `GAP` bajo la regla dura de
`absence_consolidator` sin volver a correr esa verificación — se registra
como límite conocido de este análisis retroactivo, no se re-decide.
