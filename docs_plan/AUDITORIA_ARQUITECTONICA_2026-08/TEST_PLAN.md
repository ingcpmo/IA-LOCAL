# H. Plan de pruebas

**Estado**: propuesta. Ninguno de estos tests existe todavía — son
requisitos para cualquier implementación futura derivada de esta
auditoría, no trabajo ya hecho.

## Regla general heredada del proyecto

Todo test nuevo corre contra el corpus real cuando sea posible (patrón ya
validado repetidamente en W5 V2: "un gate real contra el corpus
verdadero, no solo fixtures sintéticos"), y Gate 0 (`factory_selfcheck.sh`,
14 checks) debe seguir PASS=5/5 (o el conteo vigente) después de
cualquier cambio.

## Tests requeridos por fase de `IMPLEMENTATION_PLAN.md`

### Fase 0 (fix de furniture simétrico)

- Test de que `_PAGE_FURNITURE_RE` produce el MISMO texto limpio tanto en
  la ruta de verificación como en la ruta que construye el prompt del
  LLM — hoy son asimétricas, el test debe fallar contra el código actual
  y pasar después del fix (test-first).
- Test de regresión: el fixture set 7P+2N completo debe mantener el mismo
  resultado de recall que antes del fix, o mejorar — nunca empeorar sin
  explicación.

### Fase 1 (experimento C)

- Test mecánico (Fase 1 del experimento, 0 llamadas LLM): dado un chunk
  real de P6/P7, `pdfplumber.extract_tables()` separa correctamente la
  tabla de la prosa circundante — verificar contra el texto real ya
  extraído en `BOTTLENECK_DIAGNOSIS.md` (la oración de 110 caracteres
  debe quedar completamente fuera de cualquier `Table.rows`).
- Sin test de juicio del LLM predefinido de antemano — el resultado del
  experimento es la medición, no algo que se pueda "pasar/fallar" como
  test convencional.

### Fase 2 (Table/EvidenceUnit, condicionada)

- Invariante dura: `EvidenceUnit.citation_text` es siempre un substring
  exacto (o normalizado por los mismos fixes de kerning/furniture/
  viñetas) de `chunk['text']` en `source_location`. Si no lo es, se
  rechaza en construcción — test explícito con un caso sintético de
  desalineación forzada.
- Test de que `evidence_verifier.match_citation()` sigue funcionando
  IDÉNTICO cuando se le pasa el mismo `chunk['text']` de siempre, sin
  importar si existe o no una capa `EvidenceUnit` por encima — no
  modificar su firma ni su comportamiento.
- Gate real contra el corpus verdadero (P6/P7 específicamente), mismo
  patrón que Fase 4/5 del roadmap `document_remediation_evolution`.

### Fase 3 (contrato formal)

- Test de contrato: dado el JSON Schema versionado del
  `common_contract_sha256`, validar que `evidence_verifier.py` y
  `chunked_engine.py` construyen/consumen estructuras conformes al mismo
  schema. Debe fallar deliberadamente si se introduce un drift sintético
  (mismo patrón que `test_deploy_freshness_all_source_routes_are_live`
  ya usado para detectar drift código-vs-servido).
- Test de que cambiar el schema sin bump de `prompt_version` falla el
  gate (fuerza la disciplina de gobernanza, no solo la mecánica).

### Fase 4 (disciplina Capa 8)

- Fuera del alcance de tests automatizados de producto — son procesos de
  sesión, no código. Verificación manual/checklist, no suite pytest.

## Negativos obligatorios en cada fase que toque juicio o recall

N1 (ANNEX11_4) y N2 (weak keyword) DEBEN seguir rechazándose en cada
cambio — repetir el golden dataset de 8 casos negativos
(`factory/regulatory/golden_dataset/semantic_verification_golden_dataset.py`)
como parte del gate de cualquier fase que toque `chunked_engine.py`,
`evidence_verifier.py` o `semantic_evidence_verification.py`.

## Qué NO se prueba (fuera de alcance, honesto)

- No se escriben tests que asuman que el DOM mejora el recall — el
  resultado del experimento C es la medición, no una expectativa
  codificada de antemano en un test.
- No se escriben tests de "cumplimiento regulatorio automático" — viola
  la regla permanente de `CLAUDE.md` (sin declaración de cumplimiento
  final por parte del sistema).
