# TARGET_REGULATORY_ARCHITECTURE — Arquitectura objetivo de acceso y control de fuentes

Diseño únicamente. No añade fuentes nuevas ni URLs nuevas — solo diseña cómo
gobernar mejor las 3 que ya existen y cómo incorporar futuras sin romper el
patrón fail-closed ya validado.

## 1. Principio rector (ya vigente, se conserva)

`factory/regulatory/regulatory_catalog.py` ya declara el principio correcto:
**una única fuente de verdad** (`requirement_catalog_loader.py`), sin copias
derivadas silenciosas. La arquitectura objetivo extiende este mismo
principio a la verificación de vigencia y acceso, que hoy no lo tiene.

## 2. Componentes objetivo (nuevos, sobre lo ya validado)

```
                    ┌─────────────────────────────┐
                    │  sources/registry.json       │  ← YA EXISTE, VALIDATED
                    │  (3 fuentes, hash+URL+juris) │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
        NUEVO  →    │  source_currency_checker      │  verifica HEAD/GET real +
                    │  (job periódico, read-only,   │  compara hash del contenido
                    │  respeta robots.txt como el   │  descargado vs sha256_original
                    │  patrón ya usado en           │  → registra el resultado en
                    │  regulatory_connector_*)       │  source_currency_log.jsonl
                    └──────────────┬──────────────┘  (append-only, separado de
                                                       registry.json -- ese schema
                                                       fija regulatory_currency_status
                                                       a 'pending_reverification' por
                                                       diseño y nunca se reescribe)
                                   │
                    ┌──────────────▼──────────────┐
        NUEVO  →    │  broken_link_report           │  si 404/timeout repetido en N
                    │  (append-only, nunca auto-    │  intentos → REGULATORY_SOURCE_
                    │  reemplaza la URL)             │  UNVERIFIED, notifica humano,
                    └──────────────┬──────────────┘  nunca inventa URL nueva
                                   │
                    ┌──────────────▼──────────────┐
        NUEVO  →    │  human_source_update          │  único punto de escritura para
                    │  (requiere aprobación         │  cambiar una URL/versión de
                    │  explícita, mismo patrón que  │  fuente — análogo a
                    │  applicability_matrix.        │  applicability_matrix.approval,
                    │  approval.status)              │  MC-000X en decisions.jsonl
                    └───────────────────────────────┘
```

## 3. Por qué NO se automatiza la sustitución de URL rota

Las 2 URLs rotas encontradas en esta auditoría (Annex 11, MHRA — ver
`REGULATORY_SOURCE_ACCESS_AUDIT.md`) podrían "resolverse" fácilmente
buscando una URL alternativa y reemplazándola automáticamente. **Se rechaza
explícitamente ese diseño**: el objetivo del usuario prohíbe inventar
enlaces, y una URL de reemplazo encontrada por búsqueda automática no es
verificablemente la fuente oficial correcta sin juicio humano (dominios
gubernamentales rehacen URLs con frecuencia; una URL "parecida" puede
apuntar a una versión distinta del documento). El patrón ya usado en
`applicability_matrix.yaml.approval` (aprobación humana explícita,
registrada con `decided_by` real en `decisions.jsonl`) se reutiliza aquí
tal cual.

## 4. Extender el catálogo de conectores existente, no crear uno paralelo

`factory/regulatory/regulatory_connector_service.py` (drug, W6.3) y
`regulatory_connector_extra_service.py` (device/food, W9 Bloque 3) ya
implementan el patrón correcto para fuentes **consultables por API** (rate
limit duro, auditado, cupo compartido). El `source_currency_checker` (§2) es
conceptualmente el mismo patrón aplicado a fuentes **descargables por URL
fija** (Annex 11, MHRA, eCFR) en vez de API de consulta — reutiliza
`connector_state.json` como registro de cupo/última ejecución, no crea un
segundo mecanismo de rate-limiting.

## 5. Conexión con el motor de producción (cierra el gap DESIGN_ONLY)

Hallazgo central de `CURRENT_STATE_AUDIT.md` §2: `verified_pipeline.py`
(evidence_verifier + absence_consolidator + applicability matrix) existe,
está probado, pero **0 llamadores de producción**. La arquitectura objetivo
NO propone reemplazar `chunked_engine.py` — propone que
`chunked_engine.evaluate_chunked()` invoque `verified_pipeline` como un paso
de post-procesamiento por checkpoint, **detrás de un flag** (similar al
patrón `run_context` que ya usa `applicability.py` para exigir aprobación
antes de producción):

```
chunked_engine.evaluate_chunked(..., use_verified_pipeline: bool = False)
    si True:
        por cada finding crudo del chunk →
            evidence_verifier.verify_llm_output(...)   [YA EXISTE, YA TESTEADO]
        al consolidar documento →
            absence_consolidator.consolidate(..., coverage_complete=<medido>)
                                                         [YA EXISTE, YA TESTEADO]
```

Este diseño es deliberadamente el cambio de MENOR superficie posible: no
reescribe `chunked_engine.py`, no reescribe los prompts YAML — añade un
parámetro opcional que, cuando se active (requiere aprobación humana
explícita, igual que `applicability_matrix`), enruta la salida ya generada
por los prompts existentes a través del verificador ya validado. Detalle de
implementación en `IMPLEMENTATION_ROADMAP.md`.

## 6. Unificación de la regla de cobertura (cierra el gap de duplicación)

`GAP_AND_DEVIATION_MODEL.md` §2 ya señaló que
`gap_assessment_finding_mapper.py` reimplementa una versión más débil de
`absence_consolidator.coverage_complete`. Arquitectura objetivo: el mapper
deja de calcular `coverage_status` con su propia heurística de "rango único
vs. resolución humana" y en su lugar **consume el resultado real de
`absence_consolidator`** cuando el finding de origen proviene del motor
verificado (§5). Para findings que todavía provienen del motor no verificado
(mientras §5 no esté activo), el mapper mantiene su regla actual pero la
etiqueta explícitamente como `EVALUATION_INCOMPLETE`-prone en el `rules`
dict que ya expone (no requiere cambio de schema, solo de criterio interno).

## 7. Qué NO cambia (superficie protegida)

- `remediation_package_service.py` / schemas / endpoints: sin cambios. El
  flujo BATCH_AND_EXCEPTION ya es la capa correcta de revisión humana y no
  necesita saber de dónde viene el `RemediationChange`, solo que sea válido.
- `create_release_record()` sigue sin endpoint expuesto.
- El catálogo regulatorio (`requirement_catalog_loader.py`) sigue siendo la
  única fuente de verdad; nada de esto crea una segunda copia.
- Ningún conector nuevo se activa sin la misma aprobación humana explícita
  que ya exigieron W6.3/W9 Bloque 3 para los 3 conectores openFDA actuales.
