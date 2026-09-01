# F3 — `r_par_delta_v1_v2.py`: diff y verificación

**Plan de reconciliación v1.1 · FASE 3 · discrepancia D1 (script) · precondición F1 PASS + F2-r1 PASS.**
Tocado: `factory/scripts/ops/r_par_delta_v1_v2.py` + `docs_plan/reconc/F3_*` + 1 clave declarativa
en `VALIDATION_BASELINE_MANIFEST.json` (`rw0003_store`, ver §5).

---

## 1. Ruta efímera ELIMINADA

**Antes:**
```python
_RW0003_DET = Path(
    "/tmp/claude-1000/-home-cmay-ivr-ia/423688da-e9c9-4275-8d88-332774529715/"
    "scratchpad/RW-0003_ingested.sqlite3")
```
→ escenario D abortaba con `FileNotFoundError` en cualquier entorno que no fuera esa sesión.

**Ahora:** el store de RW-0003 se resuelve del **manifest**
(`VALIDATION_BASELINE_MANIFEST.json::rw0003_store`). Si `status != AVAILABLE` (hoy
`NO_DISPONIBLE`) → `_resolve_rw0003_store()` devuelve `None` → escenario D =
**`SKIPPED_NO_STORE`**. Cero rutas de sesión en el código (verificado por `--check`).

## 2. `_build_canon` — fail-closed, sin abortar a mitad

- **Escenario A (`source="PROD"`):** además de copiar `canonical_store/{did}.sqlite3`, ahora
  **verifica el `LOGICAL_CONTENT_HASH` de cada store contra el baseline del manifest**
  (`canonical_store_manifest.per_doc.{did}.logical_hash_clean`). Si un store falta o
  drifteó → `RuntimeError` con mensaje claro ("rematerializar antes de correr R-PAR").
  Usa **la misma función de hash que `materialize_stores.py`** (importada, no reimplementada)
  para comparar contra el mismo algoritmo del manifest.
- **Escenario D (`include_rw0003`):** si el store no está declarado/AVAILABLE →
  `raise _RW0003Unavailable()` (excepción tipada), capturada por `run_scenario` →
  `_skipped_scenario("D", ...)`. **Nunca** copia una ruta efímera; **nunca** aborta a
  mitad dejando artefactos vacíos.

## 3. `main()` — A/B/C siempre, D condicional, output siempre

- `A, B, C = run_scenario(..., manifest=manifest)` — siempre.
- `D`: si `--dry-run-abc` **o** RW-0003 `NO_DISPONIBLE` → `_skipped_scenario("D", ...)`;
  `d_skipped = True`.
- Todas las secciones dependientes de D (`C_vs_D_rw0003_additive`, `graph_delta_cd`, `cd`,
  `RR1`, `D_fps`, `D_n`, `CD_*`) → `"SKIPPED_NO_STORE"` cuando `d_skipped`. No hay
  `KeyError`/`TypeError`.
- `result["D_status"]` explícito.
- **Siempre** escribe `docs_plan/_r_par/R_PAR_RAW.json` + `findings_{A,B,C}.json`;
  `findings_D.json` = `{"status": "SKIPPED_NO_STORE"}` si D no corrió.

## 4. Nuevos flags

| flag | efecto |
|---|---|
| `--check` | selfcheck: 0 rutas efímeras hardcodeadas en el propio archivo → exit 0/1 |
| `--dry-run-abc` | corre **solo A/B/C** (D siempre SKIPPED); produce `docs_plan/_r_par/` no vacío. **NO** es el R-PAR completo (eso es F6). |
| `--manifest` (implícito) | lee `docs_plan/reconc/VALIDATION_BASELINE_MANIFEST.json` |

## 5. `rw0003_store` en el manifest (declaración explícita — F3 acción 1)

`VALIDATION_BASELINE_MANIFEST.json` gana:
```json
"rw0003_store": {
  "status": "NO_DISPONIBLE",
  "reason": "RW-0003 (SAT, 204 pág imagen) requiere OCR docling + salto de EXTRACTION_VERSION -> BLOQUEADO EN GOBERNANZA (qualification_contract.yaml CT-WP-D-REAL, D-4-H9 no ejecutado). F2 NO lo materializó.",
  "path": null,
  "effect_on_r_par": "escenario D = SKIPPED_NO_STORE. Para habilitar D: status=AVAILABLE + path a un store RW-0003 gobernado (F6)."
}
```
*(Toque de 1 clave declarativa fuera del set editable estricto de F3, exigido por F3 acción 1
"declarado NO_DISPONIBLE explícitamente". Documentado.)*

---

## Verificación

```
$ r_par_delta_v1_v2.py --check
SELFCHECK OK: sin rutas efimeras hardcodeadas          exit=0

$ grep -nE "/tmp/claude-|scratchpad/|claude-1000/-home" r_par_delta_v1_v2.py
(sólo dentro de _selfcheck, compuesto de fragmentos -> no es una ruta real)

$ r_par_delta_v1_v2.py --dry-run-abc
WROTE docs_plan/_r_par/R_PAR_RAW.json   (D_status = SKIPPED_NO_STORE )   exit=0
  A_n=457  B_n=457  C_n=458  D_n=SKIPPED_NO_STORE
  determinism: {A: True, B: True, C: True}
  AB_only_A=0  AB_only_B=0   (clone-drift 0: PROD == FRESH tras F2-r1)
  BC_only_C=1  BC_refers_to={B:0, C:201}   (efecto H-10)
  rw0012 prod/clean claims: 258 / 258   (RW-0012 des-contaminado, consistente)

$ r_par_delta_v1_v2.py           # camino completo, sin flag
WROTE ...   (D_status = SKIPPED_NO_STORE )   exit=0     # D auto-skip, sin abortar

$ ls -s docs_plan/_r_par/
R_PAR_RAW.json (15 KB)  findings_A.json (280 KB)  findings_B.json (280 KB)
findings_C.json (281 KB)  findings_D.json (102 B = {"status":"SKIPPED_NO_STORE"})
```

`docs_plan/_r_par/` es gitignored → no va a git. Copia de evidencia:
`docs_plan/reconc/F3_dryrun_ABC.json`.
