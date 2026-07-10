# W9 Bloque 3 — Segunda y tercera fuente regulatoria (openFDA Device + Food Enforcement)

**Estado:** implementado y verificado en vivo (2026-07-10), CERRADO. Aprobado
por Cesar en chat: "Bloque 3 con segunda fuente openFDA Device/Food
Enforcement, arranca" — implementadas ambas (mismo esfuerzo, mismo patrón,
mismo endpoint openFDA), no solo una.

## Qué resuelve

Hasta W9 Bloque 2, la memoria regulatoria dependía de una sola fuente
(`openfda_enforcement`, drug recalls, W6.3). Bloque 3 añade dos fuentes más
del mismo proveedor oficial (openFDA), **sin tocar el conector original**:

- `openfda_device_enforcement` — recalls de dispositivos médicos.
- `openfda_food_enforcement` — recalls de alimentos.

Ambas relevantes para las misiones existentes: `lab_qc_project` cubre
`21 CFR Part 820` (dispositivos) además de Part 211, y HPLC/QC de
laboratorio se apoya en instrumentación (dispositivos) tanto como en
producto farmacéutico.

## Diseño (generalización sin regresión)

`factory/services/regulatory_connector_service.py` (W6.3, drug) queda
**completamente intacto** — cero riesgo sobre lo ya aprobado/probado en
W6.3/W6.4/W7/W8. Nuevo módulo hermano
`factory/services/regulatory_connector_extra_service.py` con el mismo
contrato (`query_recalls`, `fetch_case_detail`, `annotate_sources`),
parametrizado por `source_id` en vez de constantes de módulo:

- **Cupo compartido, no triplicado**: reutiliza `_base._rate_gate()` —
  mismo `connector_state.json`, mismo `MIN_INTERVAL_S`/`MAX_CALLS_PER_DAY`.
  El límite protege a openFDA de la fábrica **en conjunto**
  (drug+device+food), consistente con el propósito original de
  anti-saturación (no es una cuota por endpoint).
- **Selective fetch por endpoint correcto**: `fetch_case_detail` lee el
  `source_id` ya guardado en el case record y elige el endpoint — nunca
  asume drug ni un endpoint fijo.
- **Modelo de memoria ligera idéntico**: nunca `address`/`postal_code`/
  `openfda`, mismo `content_hash`/`freshness`/`retrieval_path`.
- **Mapeo de tags extendido, no reemplazado**: `TAG_MAP = {**base.GMP_TAG_MAP,
  **EXTRA}` — añade señales de dispositivo (`malfunction`, `software`,
  `battery`) y alimento (`allergen`, `undeclared`, `listeria`, `salmonella`)
  sin tocar el mapeo original.
- **Reutiliza los mismos 2 tipos de evento de auditoría** de W6.3
  (`regulatory_query_executed`/`case_detail_fetched`) — sin eventos nuevos,
  mismo pipeline aguas abajo (W6.4 presentación, W7 análisis de casos, W9
  Bloque 2 citación en dossier) funciona con estas fuentes **sin ningún
  cambio**: esos módulos ya eran genéricos por diseño (operan sobre el
  `case_id`/dict del caso, no hardcodean "drug").

## API (retrocompatible)

- `POST /regulatory/query` — `source_id` nuevo, **opcional**, default
  `openfda_enforcement` (drug): toda llamada anterior a este bloque sigue
  funcionando idéntica sin cambios.
- `POST /case-memory/{case_id}/fetch` — sin cambio de contrato; el router
  decide internamente el conector correcto leyendo el `source_id` del case
  guardado.
- `GET /regulatory-sources` — anexa los `connected_sources` de Bloque 3 sin
  pisar los de W6.3.

## `source_registry.yaml`

`version: 2 → 3`. 2 fuentes nuevas (`openfda_device_enforcement`,
`openfda_food_enforcement`), `status: connected`, con
`rate_limit_design` documentando explícitamente el cupo compartido. Las
demás fuentes (Warning Letters, 483, EudraGMDP, etc.) siguen
`not_connected` — conectarlas sigue requiriendo aprobación humana
explícita, sin cambios.

## Tests

`factory/tests/test_regulatory_connector_extra.py` (15 tests nuevos):
fuente desconocida → 404 sin salir a red; modelo de memoria correcto por
fuente (device_recall/food_recall); endpoint correcto por fuente; nombre
reservado → 422; dedupe; 404 sin resultados; auditoría con `source_id`
correcto; **cupo compartido con el conector base probado explícitamente**
(una llamada del módulo base agota el intervalo/cupo que ve este módulo, y
viceversa); fetch requiere caso conocido; **fetch de un caso de fuente
ajena (drug) → 404** (nunca usa el endpoint equivocado); fetch sin
persistir; detección de cambio de contenido; `annotate_sources` anota solo
las 2 fuentes de Bloque 3 sin pisar W6.3.

1 test pinneado actualizado (`test_design_mode.py::test_real_source_registry_single_connector`
→ `test_real_source_registry_connectors`): reflejaba el conteo real de
fuentes (7) y el único conector (openfda_enforcement); actualizado a 9
fuentes y 3 conectores — cambio esperado y correcto, no una regresión.

## Verificación en vivo (llamadas REALES a openFDA, no mockeadas)

1. `POST /regulatory/query` (`source_id=openfda_device_enforcement`,
   term=`software`) → 200, 3 recalls reales guardados (IPG Medical, Staar
   Surgical, Abiomed — Class I/II reales), tags `software_defect`
   correctos, sin PII/direcciones.
2. `GET /regulatory-sources` → los 3 conectores openFDA aparecen
   `connector_live: true` con **el mismo `quota`/`last_checked`** —
   confirma cupo compartido también en la vista agregada.
3. `POST /regulatory/query` (`source_id=openfda_food_enforcement`,
   term=`undeclared allergen`) → 200, 2 recalls reales (sésamo, soja),
   tag `allergen_undeclared` correcto.
4. `POST /case-memory/{case_id}/fetch` sobre un caso device real → detalle
   recuperado, **no persistido**, sin campos prohibidos, `content_changed:
   false` (mismo registro), endpoint usado: `device/enforcement.json`
   (confirma que el dispatcher no asumió drug).
5. Cupo final: `calls_today: 3` (compartido, muy por debajo del límite
   diario de 10) — 3 llamadas reales sin fricción con el cupo de W6.3.
6. `cases.jsonl`: 5 casos drug (intactos, sin tocar) + 3 device + 2 food
   nuevos = 10 líneas, sin corrupción.
7. Cadena de auditoría: 320 → 323 (+2 `regulatory_query_executed`, +1
   `case_detail_fetched`, todos con `source_id`/`case_id` correctos).
8. `factory_selfcheck.sh` → PASS=4 FAIL=0, pytest 466 passed (451+15
   nuevos, sin regresiones tras actualizar el test pinneado).
   `aria-*`/`hotelbot-*` intactos.

## Fuera de alcance de este bloque

FDA Warning Letters (desaconsejado explícitamente en el cierre de W6.3 por
ser scraping/HTML — fase propia). EudraGMDP/EMA. Ampliar el mapeo de tags
más allá de la extensión mínima entregada. Ejercitar estas 2 nuevas
fuentes end-to-end contra el pipeline de análisis de casos (W7) — el
pipeline ya es genérico (probado en Bloque 1 con `oos_hplc_investigator` y
`lab_qc_project`) pero no se corrió un caso device/food real contra un
agente en esta sesión; queda disponible sin cambios de código, gated por
aprobación de Cesar si se quiere demostrar.
