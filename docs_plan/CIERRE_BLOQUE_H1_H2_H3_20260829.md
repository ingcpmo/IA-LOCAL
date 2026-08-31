# CIERRE DEL PRIMER BLOQUE — H-1 · H-2 · H-3

**Fecha:** 2026-08-29 · **Autoridad:** Capa 9 = Cesar · **Baseline:** HEAD `ab40f3b`.
**Diseño de referencia:** `docs_plan/DISENO_H1_H10_ACTUALIZADO_R0_R5_20260829 (1).md`.
**D-1 establecida para esta fase:**
```
CURRENT_INTENDED_USE      = GMP_DECISION_SUPPORT_TOOL
SYSTEM_OF_RECORD          = NO
HUMAN_FINAL_AUTHORITY     = REQUIRED
REGULATORY_COMPLIANCE     = NOT_DETERMINED_BY_SYSTEM
PRODUCTION_ENABLEMENT     = NOT_ENABLED
```
⇒ H-1 = **atribución autenticada**, NO firma electrónica Part 11 formal (11.50/11.70).

Sin commit, sin push. Drift preexistente (18 tracked + 4 `.docx` + docs) **preservado intacto**.
QA40 sin adjudicar. WP-B ENFORCE / OCR / V2_TEST_EXTRACTION **no activados**. `qualified_version`
sin firmar. D-2…D-6 sin decidir.

---

## H-1 · Identidad en los 7 mutadores críticos

**Cambio.** `Depends(require_identity)` (header `X-Identity-Key`, resuelto contra el
`identity_registry` existente) en los 7 "rojos" de R-3. El actor se **DERIVA** de la identidad
autenticada, nunca del cuerpo.

| # | Endpoint | Antes | Ahora |
|---|---|---|---|
| 1 | `POST /api/v1/approvals/{pid}/confirm` | `approved_by` texto libre del body | `approved_by = recorded_by =` identidad resuelta; `ConfirmBody` **ya no expone** `approved_by`/`recorded_by`; header `X-Change-Reason` registrado |
| 2 | `POST /api/v1/approvals/{pid}/reject` | `rejected_by = body.approved_by` | `rejected_by = recorded_by =` identidad resuelta |
| 3 | `POST /api/v1/layer8/missions/{pid}/deploy-if-authorized` | solo clave compartida | + `require_identity` (401 sin `X-Identity-Key`) |
| 4 | `POST /api/v1/layer9/review/{rc}/mark-canonical` | `body.marked_by` + `validate_identity` | `marked_by =` identidad resuelta (header); `MarkCanonical.marked_by` opcional e ignorado |
| 5 | `POST /api/v1/layer9/w5-decisions/{id}/correct` | `body.corrected_by` | `corrected_by =` identidad resuelta; `W5CorrectionBody.corrected_by` opcional e ignorado |
| 6 | `POST /api/v1/releases/{pid}/{version}` | solo clave compartida | + `require_identity` (gate de auth; `create_release` no cambia) |
| 7 | `DELETE /api/v1/workspaces/{pid}` | solo clave compartida | + `require_identity` (destructivo) |

**Archivos:** `factory/api/routes/{approvals,layer8,layer9,releases,workspaces}.py`.
**Tests que se ajustaron** (dejaron de mandar el actor en el body): `test_w5_human_decisions.py`
(`.../correct`), `test_release_decision_coverage.py` (`test_endpoint_returns_423_not_409`).
**NO se implementó** firma electrónica formal (D-1 = herramienta de apoyo).

### Tests específicos de H-1

`factory/tests/test_h1_identity_critical_mutators.py` (nuevo):
- test **paramétrico** sobre los 7 rojos: sin `X-Identity-Key` ⇒ **401**; con clave no registrada ⇒ **401**.
- `confirm` deriva `approved_by == "Cesar"` (identidad resuelta), **no** `"Atacante"` aunque el
  cliente lo intente colar en el body; `change_reason` registrado.
- `reject` deriva `rejected_by == "Cesar"`.
- `ConfirmBody` ya **no** tiene los campos `approved_by`/`recorded_by`.
- `.../correct` con identidad ⇒ pasa el gate (404/422 por decisión inexistente, **nunca 401**).

Resultado: **117 passed / 1 xfailed** en el conjunto H-1 + tests colindantes
(`test_h1_*`, `test_w5_human_decisions`, `test_release_decision_coverage`,
`test_decision_resolver_no_bypass`, `test_finding_review_decision_endpoint`).
Regresión dirigida (`-k "layer9 or layer8 or approval or release or workspace or governance or
identity or endpoint or api or deploy"`): **538 passed / 2 failed** — los 2 fallos son
EXC-2/EXC-3 (servicios en vivo). **NEW_REGRESSIONS_H1 = 0.**

**`H1 = PASS`**

---

## H-2 · Aislamiento del audit trail productivo respecto de la suite

**Cambio.**
1. `factory/core/audit_writer.py`: la ruta del audit trail es **INYECTABLE**.
   `_DEFAULT_AUDIT_FILE = factory/audit/factory_audit.jsonl`;
   `AUDIT_FILE = Path(os.environ["FACTORY_AUDIT_FILE"]) if FACTORY_AUDIT_FILE else _DEFAULT_AUDIT_FILE`.
   Sin env var → comportamiento productivo idéntico.
2. `factory/tests/conftest.py`: `isolated_audit` pasa a **`autouse=True`**. **Ningún** test escribe
   en `factory_audit.jsonl` productivo por defecto.
3. Nuevo fixture `real_audit_chain` (solo lectura): para los tests que verifican propiedades de la
   **cadena PRODUCTIVA** (forks históricos, `part11_compliant` real). Restaura `aw.AUDIT_FILE` al
   default para lecturas y **redirige `write_event` a un sink tmp** (en `audit_writer`,
   `decision_store_v2` y `governance_service`) para que una escritura transitiva de esos tests
   NUNCA toque el fichero productivo.
4. **El histórico NO se reescribe.** La contaminación pasada (R-2: 41,9 %) se **declara** (D-7).

**Guard-test** (`factory/tests/test_h2_audit_trail_isolated_from_tests.py`, nuevo):
- en CUALQUIER test, `aw.AUDIT_FILE` **no resuelve bajo el repositorio** (prueba que la autouse está activa).
- escribir 25 eventos desde un test **no cambia** el conteo de líneas del audit trail productivo;
  los eventos sí se escriben, en el fichero aislado.
- `_DEFAULT_AUDIT_FILE` apunta al fichero productivo.
- `FACTORY_AUDIT_FILE` inyecta la ruta (recarga del módulo).

**Tests que se ajustaron** (leen la cadena real ⇒ ahora piden `real_audit_chain`):
`test_audit_fork_governance.py` (`test_f01/f02/f04/f06/f08_*_the_real_chain*`),
`test_g7_audit_exception_readiness.py` (`test_the_state_resolves_exceptions_...`),
`test_release_decision_coverage.py` (`test_an_unbacked_fork_blocks_and_is_named`,
`test_chain_break_ids_are_real_on_the_production_chain`),
`test_status_risks.py` (`test_audit_chain_risk_severity_distinguishes_fork_from_corruption`),
`test_gate0_extended.py` (`test_the_real_chain_dimensions_land_on_warn_not_fail`).

### Verificación del invariante

| | Líneas del audit trail productivo |
|---|---|
| Antes de cualquier corrida de esta sesión H | 100 974 → (corridas previas a H-2 lo movieron a 101 071) |
| Antes de la regresión completa final | **101 071** |
| Después de la regresión completa final (`pytest factory/tests/`, 2945 passed) | **101 071** |

`AUDIT_TRAIL_PRODUCTIVE_CHANGED_BY_TESTS = NO`. Verificado en 4 corridas sucesivas.

**`H2 = PASS`**

---

## H-3 · `finding_record_id` (modelo M2+M3) — sin rehash de `finding_id`

**Cambio.**
- `factory/regulatory/findings/taxonomy.py`: nuevo `_det_record_id(finding_id, subcriterion_ref,
  requirement_id) = "rec-" + sha256(finding_id \x1f subcriterion_ref \x1f requirement_id)[:16]`.
  Campo **aditivo** `Finding.finding_record_id` (default `""`); si viene vacío se **deriva** en
  `__post_init__` de `finding_id` + `provenance.subcriterion_ref` + `requirement_id`.
  **Discriminante 100 % semántico y estable — SIN ordinal de emisión.**
- `factory/regulatory/validation_v2/v2_runtime.py::_finding_row`: serializa `finding_record_id`
  en `regulatory/functional/technical_findings.json`.
- `_det_id` (fórmula de `finding_id`) **NO se toca**. `findings_fingerprint` **NO** incorpora el
  campo nuevo (whitelist `_FINDING_SEMANTIC_FIELDS` en `run_fingerprint.py`).

### Verificación E2E (corrida `v2_runtime` sobre los 6 documentos RW)

| Métrica | Valor | Veredicto |
|---|---|---|
| `finding_id` — fórmula y valores | idénticos (`_det_id` sin cambios) | **UNCHANGED** |
| colisiones de `finding_id` | 456 findings / 260 únicos (196 colisiones, todas RegulatoryFinding) | preservadas (M2) |
| `finding_record_id` presente | 456 / 456 | **YES** |
| `finding_record_id` únicos | **456 / 456** | **UNIQUE** |
| caso QA40 duplicado `fnd-63caabcb2bccea24` | 2 registros → `rec-50552b00e6ae9f4b` y `rec-f9f8810af5fe98d5` (`::sc1` vs `::sc3`) | **resoluble sin ambigüedad** |
| `findings_fingerprint` | `b5196a71…` (antes) → `b5196a71…` (ahora) | **UNCHANGED** |
| Muestra QA40 (SHA de los 40 `finding_id`) | `02b6d3d0…` → `02b6d3d0…` | **UNCHANGED** |
| Determinismo (2 corridas frescas) | fingerprints idénticos entre corridas | **preservado** |

### Tests específicos de H-3

`factory/tests/test_h3_finding_record_id.py` (nuevo, 6 tests):
- fórmula de `finding_id` sin cambio;
- dos sub-criterios del mismo requisito ⇒ mismo `finding_id`, **distinto** `finding_record_id`;
- `finding_record_id` determinista y semántico (mismo `(finding_id, subcriterion_ref, requirement_id)`
  ⇒ mismo `rec-…`, independiente del orden de construcción);
- los findings no regulatorios también reciben `finding_record_id`;
- `as_dict` serializa el campo;
- **mutar `finding_record_id` a mano NO cambia `findings_fingerprint`** y el campo **no** está en
  `_FINDING_SEMANTIC_FIELDS`.

Regresión dirigida (findings / taxonomy / fingerprint / v2_runtime / validation_v2 / WP-A/B/E):
**356 passed / 0 failed.**

**`H3 = PASS`**

---

## COMPARACIÓN BEFORE / AFTER (los 3 paquetes juntos)

| Elemento | BEFORE (HEAD `ab40f3b`) | AFTER (H-1+H-2+H-3) | ¿Cambió? |
|---|---|---|---|
| findings count (6-doc run) | 342 / 90 / 24 | 342 / 90 / 24 | **NO** |
| `findings_fingerprint` | `b5196a7177c92a913de638637a071d2027a78eb1b9f1233d814812d3ff6dc21e` | idéntico | **NO** |
| `INPUT_CONFIG_FINGERPRINT` | `c46fbe67cecbac45c289e8472432c29368302c7baa17abf0a22a9a27f9c6656b` | `979296571fec5001cb846eb6551747811eab0662d58db9b89147c1a8f2fd072f` | **SÍ** — ver nota ⚠ |
| Muestra QA40 (SHA 40 `finding_id`) | `02b6d3d0b6fadb1f882c4e63b7f7421dd387268ddabe5b5f16abfa5d9d360d32` | idéntico | **NO** |
| audit trail — líneas productivas | 101 071 | 101 071 (invariante en 4 corridas) | **NO** (por tests) |
| tests de autenticación/identidad | pasaban (identidad en ~22/60 mutadores) | pasan + 14 casos nuevos (7 rojos × 2) | mejora, 0 rotos |
| fallos de regresión aceptados (EXC) | 5 (EXC-1..EXC-5) | **5, mismos ids** | **NO** |
| suite global | `5 failed / ~2917 passed / exit 1` | `5 failed / 2945 passed / 79 skipped / 1 xfailed / exit 1` | +28 passed (tests H nuevos + fixtures); **0 fallos nuevos** |

### ⚠ Nota sobre `INPUT_CONFIG_FINGERPRINT` (requiere reconocimiento de Capa 9)

`INPUT_CONFIG_FINGERPRINT` incorpora `source_attestation_digest` = digest del cierre estático de
imports `factory.*` alcanzable desde `v2_runtime` (WP-A). H-1/H-2/H-3 editaron módulos **dentro** de
ese cierre (`taxonomy.py`, `audit_writer.py`, `v2_runtime.py`), así que el digest cambia **por
diseño** — es exactamente el mecanismo que WP-A existe para detectar. Consecuencias:

- **`findings_fingerprint` (identidad del RESULTADO) NO cambia** — la salida semántica es idéntica.
- **El determinismo se preserva**: dos corridas frescas post-cambio producen fingerprints idénticos
  (`979296571f…` / `b5196a71…`).
- Es una **nueva línea base de `INPUT_CONFIG_FINGERPRINT`**, prevista por el diseño (§11, nota N-5).
  No bloquea H-4; **Capa 9 debe registrar el nuevo valor como línea base** antes de firmar
  `qualified_version` (D-6, que de todos modos no se toca hasta después de H-4/H-5).
- Ningún test fija el literal `c46fbe67…` (`test_run_fingerprint.py` solo comprueba
  igualdad entre dos corridas y longitud 64) ⇒ 0 regresiones por este cambio.

---

## RESIDUAL (no bloquea H-4; fuera del alcance de H-1/H-2/H-3)

- **`factory/layer9/review_queue.jsonl`** se ensucia al correr la suite: el test
  `test_r2_3_judgment_relabel_consistency.py` **hardcodea la ruta productiva**
  (`Path(__file__).parent.parent / "layer9" / "review_queue.jsonl"`) y reescribe 3 entradas con un
  `reviewed_at` nuevo en cada corrida. **Es un defecto de aislamiento preexistente** (clase G-7,
  no causado por H-1/H-2/H-3). Se **restauró a HEAD**. Debería recibir el mismo tratamiento que
  `isolated_audit` (fixture autouse) en un paquete futuro — anótese como `G-7b`.

---

## RESULTADO

```
H1 = PASS
H2 = PASS
H3 = PASS

NEW_REGRESSIONS = 0
  (suite global: 5 failed = EXC-1..EXC-5, ids idénticos; 2945 passed; exit 1 por las 5 EXC aceptadas)

FINDING_ID_CHANGED                     = NO
FINDING_RECORD_ID_UNIQUE              = YES   (456/456 en la corrida de referencia)
FINDINGS_FINGERPRINT_CHANGED          = NO    (b5196a71… intacto)
QA40_CHANGED                          = NO    (SHA 02b6d3d0… intacto; sin re-muestreo)
AUDIT_TRAIL_PRODUCTIVE_CHANGED_BY_TESTS = NO  (101 071 líneas, invariante en 4 corridas)

INPUT_CONFIG_FINGERPRINT_CHANGED      = SÍ    (c46fbe67… -> 979296571f…; por edición de código en el
                                              cierre de imports de v2_runtime; determinismo preservado;
                                              nueva línea base a registrar por Capa 9)

READY_FOR_H4 = YES
```

**STOP OBLIGATORIO.** No se ejecutan H-4…H-10 ni WP-F. No se toman decisiones D-2…D-6. WP-B ENFORCE,
OCR y V2_TEST_EXTRACTION siguen inactivos. QA40 sin adjudicar. `qualified_version` sin firmar.
Sin commit, sin push.
