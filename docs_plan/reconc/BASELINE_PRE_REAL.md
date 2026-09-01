# BASELINE_PRE_REAL — Fase F0 (Plan de reconciliación v1.1)

**Fecha:** 2026-09-01 · **Ejecutor:** Claude Code (Capa 8) · **Alcance:** SOLO descubrir y congelar. Cero cambios de producto.

---

## 1. HEAD real (descubierto, NO asumido)

| | valor |
|---|---|
| `HEAD_REAL` | **`90960059b609b5cd921d913e176888e1f9a6c248`** (`9096005`) |
| rama | `fix/clon-local-validacion` |
| ≠ baseline del plan v1.0 (`6be0626`) | **Sí** — HEAD avanzó 1 commit (`9096005`, docs de cierre) tras `6be0626`. Confirmado que el estado es POSTERIOR a la corrida de Devin. |
| ledger líneas / sha256 (disco) | **259** / `1b0c7cf82ed7b2b056aade48c7e7dfa41142b108f94dfda0d0dc9836206a4af4` |
| ledger líneas / sha256 (HEAD) | 255 / `42fa47f712e95732aac62fd4b53098e481ea31d554e67c1d38564535d4aaee92` |
| firmas E1 legítimas presentes | **`ARTIFACT_VERSION-2026-022..025`** (E1-3 + E1_ACCEPTANCE, Mission Control, 2026-09-01 15:57–16:00) — ver `F0_ledger_state.md` |
| `-026..-032` | **NO existen** en el ledger en disco |
| targeted v1.2 (real, honesto) | **124 passed** (working tree tal cual, stores en disco) — ver `F0_targeted_result.txt` |
| `test_document_structure_extractor.py` | 10 passed, 1 skipped (extractor con-cambio) |

Últimos commits (`git log --oneline -6`):
```
9096005  docs(cierre): REVISIÓN DE CIERRE H-1..H-10 + INSTRUCCIONES (docs)
6be0626  docs(mesa-diseno): FASE 2 CERRADA = PASS / PARKED (docs)
24549a3  feat(D5/v1.2): registrar H1 APPROVE_REMEDIATION_V1_2 + D5-D2 DEFERRED  <- toca producto/gobernado; disclosed; D6→F4
9d6c86f  feat(mesa-diseno): H-4 + prueba de recall (prototipo aislado)
647b710  feat(mesa-diseno): prototipo aislado + bake-off (prototipo aislado)
6891422  docs(mesa-diseno): reporte comparativo PRE vs POST-mejoras
```

---

## 2. Clasificación del working tree (cada entrada en EXACTAMENTE una categoría)

### GOBERNADO_PENDIENTE_DE_PERSISTIR (1)

| archivo | qué es | patch | fase |
|---|---|---|---|
| `factory/layer9/decisions/decisions_v2.jsonl` | +4 líneas del **servicio** Mission Control (`ARTIFACT_VERSION-2026-022..025`, E1-3 + E1_ACCEPTANCE, propose→confirm, `approved_by_id=Cesar`). NO hand-edit. | `F0_diffs/factory__layer9__decisions__decisions_v2.jsonl.diff` (12 líneas) · HEAD `42fa47f712e9` → WT `1b0c7cf82ed7` | **F4** (persistir por servicio + OK Capa 9; nunca hand-edit) |

### CODIGO_NO_GOBERNADO — en alcance de reconciliación (2)

| archivo | cambio | patch | fase |
|---|---|---|---|
| `factory/regulatory/document_structure_extractor.py` | `_HEADING_RE` y regex de TOC: `(\d{1,2})\s+` → `(\d{1,2})\.?\s+` (admite punto opcional tras el número, p.ej. "3.1 Foo"). D2. | `F0_diffs/…document_structure_extractor.py.diff` (16) · HEAD `285300c943b3` → WT `56236c1ace28` | **F1** |
| `factory/tests/test_document_structure_extractor.py` | tests del extractor. | `F0_diffs/…test_document_structure_extractor.py.diff` (55) · HEAD `49fbb8475fb9` → WT `26ca615b17bb` | **F1** |

### CODIGO_NO_GOBERNADO — PRE-EXISTENTE, FUERA del alcance de esta mesa (4)

Cambios de sesiones previas (arco H-1 / Causa B), no atribuibles a D1–D8. **F0 los deja
declarados y congelados como patches; NINGUNA fase de este plan los commitea.** Requieren su
propia decisión de Capa 9 aparte.

| archivo | cambio | patch |
|---|---|---|
| `factory/services/remediation_directive.py` | añade `fcntl` file-lock para supersede concurrente (Causa B, `CALIFICACION_FINAL_CURRENT_ENGINE.md` 2026-08-20). | `F0_diffs/…remediation_directive.py.diff` (189) · `59526a4122bf` → `49f391ffee11` |
| `factory/tests/test_remediation_directive.py` | tests de supersede/replacement. | (131) · `daa5286242c4` → `7f1eff5eaaae` |
| `factory/tests/test_r4_t1_1v2_cold_chain_validation.py` | ajuste de redacción del criterio (g). | (38) · `690957117dec` → `7d6c0360c14e` |
| `factory/tests/test_release_decision_coverage.py` | fixtures `real_audit_chain` / `identity_headers` (H-1 exige X-Identity-Key). Toca testing de cadena de auditoría → **contexto de D7**, no acción de F0. | (43) · `d503ad11ab82` → `ed0b30141cfd` |

### DOCUMENTO / CONFIG (modificados, trackeados) (7)

| archivo | nota |
|---|---|
| `.claude/settings.json` | config de tooling, no producto. Patch 46 líneas. `22886b7222c6` → `a0f44e9e9d26` |
| `GMP_AI_FACTORY_ARQUITECTURA_OBJETIVO.md` | doc. 205 líneas. |
| `docs_plan/M4_IMPLEMENTACION.md` | doc. 108 líneas. |
| `docs_plan/PAQUETE_DECISION_ESTRATEGICA.md` | doc. 433 líneas. |
| `factory/regulatory/pilot_run/dry_run_validation_r4_t1_1v2/v1_candidate_EXCLUDED_pending_exception.docx` | **BINARIO** (byte-diff sólo). `66f375631ffd` → `8237e6635f2a` |
| `…/v1_redline_EXCLUDED_pending_exception.docx` | BINARIO. `6ccdfa1e3a9b` → `a8d64bcb3be0` |
| `…/v2_candidate_INCLUDED.docx` | BINARIO. `e0dae16fa620` → `5da54a1e4841` |
| `…/v2_redline_INCLUDED.docx` | BINARIO. `875c85b84900` → `5c13d0f02bab` |

*(4 docx = evidencia generada de pilot_run; F0 sólo hashea, no interpreta.)*

### UNTRACKED (73)

Inventario completo en `F0_worktree.txt`. Resumen por tipo:
- **~55 docs** bajo `docs_plan/` (informes, planes, diseños de sesiones previas) — incl.
  `docs_plan/reconc/` (este trabajo), `DISENO_MODELO_HIBRIDO_DETERMINISTA_OLLAMA.md`,
  `INVENTARIO_ARQUITECTURA_REAL.md`, `R2_CONTAMINACION_AUDIT_TRAIL.md`, `R0..R5_*`.
- **~9 scripts** `factory/docs/design/regulatory_redesign_v2/*.py` (medición/juicio, no producto).
- **~8 dirs de stores/evidencia**: `factory/regulatory/corpus_run/`,
  `factory/regulatory/pilot_run/{adjudication,fase2_*,fase5_*,n2_isolated_*,paso_a_*}/`,
  `factory/remediation_packages/`, `factory/layer9/remediation_directives.jsonl`.
- `factory/tests/test_n2_isolated_candidate_pool.py`, `software_inventory.txt`,
  `.claude/daemon/`, `.claude/settings.local.json`, un `.~lock` de LibreOffice.

Ninguno se toca en F0. Los stores untracked se inventarían con doble hash en
`F0_stores_manifest.json`.

---

## 3. Stores no versionados — doble hash (byte + logical)

Ver `F0_stores_manifest.json`. Resumen:

| store | files | tree_byte_sha256 (16) | regenerable |
|---|---:|---|---|
| `canonical_store` (6 sqlite3) | 6 | `49d3bdec5245855c` | sí (hipótesis) |
| `canonical_store_v2` | 7 | `98528920ffd2d11d` | sí (gitignored) |
| `graph_store` | 16 | `43981f0f11945d23` | sí (hipótesis) |
| `graph_store_v2` | 1 | `fe50eb4a09d33f9b` | sí (gitignored) |
| `corpus_run` | 983 | `b3a81adb51cb128b` | UNKNOWN (mtime 2026-08-20) |
| `pilot_run` | 780 | `66ad32e363d57e53` | UNKNOWN (1 archivo trackeado; 4 docx modificados) |

`canonical_store` por documento (byte / logical / counts): en el manifest. `section` counts:
RW-0005=8, RW-0006=8, RW-0009=0, RW-0011=8, RW-0012=13, RW-0014=8. **Producidos por el árbol
ACTUAL (extractor con-cambio + stores en disco)** — F1 re-medirá HEAD-limpio vs con-cambio.

---

## 4. Chequeo de STOP F0

> STOP si `git status` revela que algo del **producto** se commiteó **sin pasar por la mesa** (pérdida de trazabilidad).

**NO se dispara.** El único commit de esta sesión que toca producto/gobernado es `24549a3`
(H1 + v1.2 + D5), **completamente disclosed** en `git log` con mensaje detallado, y su
reconciliación de gobernanza (D6: ¿H1 requiere asiento gobernado?) **ya está agendada en F4**.
No hay commits de producto ocultos.

---

## 5. REPORTE FORMATO OBLIGATORIO — F0

```
FASE            = F0 (descubrir y congelar el estado real)
PRE_COMMIT      = 90960059b609b5cd921d913e176888e1f9a6c248  (HEAD_REAL descubierto)
POST_COMMIT     = <tag reconc-F0, apunta a HEAD_REAL + empaqueta F0_* como docs>
WORKTREE_PRE    = 15 M / 73 ??  (git status --porcelain -> F0_worktree.txt)
WORKTREE_POST   = 15 M / 73 ??  + docs_plan/reconc/F0_* añadidos (solo docs de F0)
DIFF            = solo docs_plan/reconc/**  (cero cambios de código/YAML/ledger/stores/prompts)
COMMANDS        = git rev-parse HEAD ; git status --porcelain ; wc -l/sha256sum ledger ;
                  git diff HEAD -- <cada M> ; find+sha256sum por store ; sqlite logical dump ;
                  pytest -q (set v1.2) ; pytest -q (test_document_structure_extractor)
TEST_RESULTS    = set v1.2: 124 passed, 24 warnings, 34.41s (número REAL)
                  test_document_structure_extractor: 10 passed, 1 skipped
INPUT_HASHES    = ledger disco 1b0c7cf8… / HEAD 42fa47f7… ; stores en F0_stores_manifest.json
OUTPUT_HASHES   = (F0 no produce artefactos de producto; los .diff y el manifest van al tag)
FINGERPRINTS    = no recomputados en F0 (F5)
ARTIFACTS       = docs_plan/reconc/{F0_worktree.txt, F0_diffs/*.diff (11 textuales + 4 binarios
                  como --stat), F0_stores_manifest.json, F0_ledger_state.md,
                  F0_targeted_result.txt, BASELINE_PRE_REAL.md}
GOVERNANCE_EVENTS = ninguno escrito por Claude. (El ledger en disco tiene 4 líneas del servicio
                  Mission Control, pre-existentes a F0; F0 no las commitea — es F4.)
DEVIATIONS      = ninguna. sqlite3 CLI no disponible en el host -> logical hash vía python
                  sqlite3 (documentado en F0_stores_manifest.json::hash_method).
EXPECTED_VS_ACTUAL:
  EXPECTED: HEAD_REAL capturado ; patches aplicables ; stores doble-hash ; targeted real ;
            presencia/ausencia de 022..032 documentada.
  ACTUAL:   HEAD_REAL = 9096005 (posterior a 6be0626) ; 11 patches textuales + 4 binarios
            capturados con hash HEAD y WT ; 6 sqlite + 6 dirs de store con byte+logical ;
            targeted = 124 (real) ; 022..025 presentes (servicio), 026..032 ausentes ;
            observación de reuso de id 022..025 (hand-edit revertido vs servicio) -> F4.
PROPOSED_VERDICT = PASS
  Justificación: el manifest F0 lista TODOS los modificados como patches con hash HEAD+WT y
  TODOS los stores con doble hash; el nº targeted real está registrado; la presencia/ausencia
  de 022..032 está documentada; no hay commit de producto oculto (STOP no aplica).
  Devin (F0) debe verificar: (a) HEAD == el del tag ; (b) cada patch de F0_diffs aplica limpio
  sobre HEAD_REAL y produce el WT-hash declarado ; (c) los byte/logical hashes de stores
  coinciden con el disco de origen (vía hash, no copia) ; (d) targeted desde clon limpio.
```

---

## 6. Para F1 (no se ejecuta aquí)

- Ground truth humano de headings/hierarchy de **RW-0011 / RW-0012 / RW-0014**, leído del
  DOCUMENTO REAL (no sólo del TOC), congelado por hash ANTES de correr el extractor.
- Medir HEAD-limpio (`285300c943b3`) vs con-cambio (`56236c1ace28`) contra ese ground truth:
  precisión/recall de headings, jerarquía, nº de claims.
- Baseline actual (con-cambio, en disco): section counts RW-0011=8, RW-0012=13, RW-0014=8.
