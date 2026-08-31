# PLAN — PRODUCTION ENABLEMENT · CUTOVER · POST-CUTOVER (preparación · NO ejecutar)

**Fecha:** 2026-08-31 · **Autoridad:** Capa 9 = Cesar · **Estado:** `PRODUCTION_ENABLEMENT = NOT_ENABLED`.
Documento de **preparación**. Ninguna acción de este plan se ejecuta sin la cadena de gates
humanos cerrada (E1…E6 + D-5 + D-6) y autorización explícita y posterior de Cesar.

```
HUMAN_FINAL_AUTHORITY = REQUIRED   ·   REGULATORY_COMPLIANCE = NOT_DETERMINED_BY_SYSTEM
NO flip  ·  NO cutover  ·  NO activación  ·  el sistema NO declara cumplimiento
```

---

## 1 · PRECONDICIONES (todas obligatorias antes de habilitar producción)

| # | Precondición | Estado hoy | Evidencia |
|---|---|---|---|
| P1 | E1 — 77 relaciones H-10 adjudicadas y registro `ARTIFACT_VERSION` firmado | 9/77 · sin firmar | `E_GATES_GOVERNED_PAYLOADS_20260831/E1_propose_body.json` |
| P2 | E2 — R-PAR revisado y aceptado (delta v1↔v2 sobre corpus compartido) | PENDING_HUMAN | `R_PAR_DELTA_V1_V2_20260831.md` · `E2_propose_body.json` |
| P3 | E3-A — paquete canónico CLEAN aceptado como base deseada (258 claims RW-0012, no 595) | PENDING_HUMAN | `PAQUETE_GATES_HUMANOS_POST_RPAR_20260831.md` · `E3A_propose_body.json` |
| P4 | QA40 — alineación de la 1/40 (`ADJ-34140454ec`) resuelta de forma determinista, sin re-muestreo | análisis listo · sin ejecutar | §QA40 del informe final · hoja 40/40 PENDING |
| P5 | D-5 — adjudicación humana H-8 (precisión/recall/especificidad) firmada por QA | NOT_OCCURRED | `PAQUETE_D5_ADJUDICACION_H8_20260830.md` |
| P6 | E6 — commit del arco autorizado y ejecutado; árbol limpio | PENDING_HUMAN + BLOCKED_BY colisión migración | `_gates_prep/E6_FILE_CLASSIFICATION_20260830.md` |
| P7 | D-6 — QUALIFIED declarado por humano (no por el sistema) | NOT_QUALIFIED | `PAQUETE_D6_QUALIFICATION_20260830.md` · `QC-*` contrato WP-F |
| P8 | Regresión pre-cutover: `NEW_REGRESSION = 0`, solo EXC de entorno documentados | 7 failed (6 EXC + 1 BLOCKED) | `_gates_prep/final_regr.log` |
| P9 | Backup verificado de `canonical_store/`, `graph_store/`, `decisions_v2.jsonl`, audit trail | script listo | `factory/scripts/ops/backup_factory_state.sh` + `factory_state_manifest.py` |

**Ninguna precondición P1–P7 está satisfecha.** El plan de abajo NO se inicia.

---

## 2 · PRODUCTION ENABLEMENT PLAN

Habilitar producción = permitir que el pipeline V2 `+tests-v1` sea la ruta que sirve informes
reales, con la config gobernada ENFORCE ya firmada (D-2) y la capacidad H-10 (Test/OCR/refers_to)
activa. **No** implica que el sistema emita juicio de cumplimiento.

### 2.1 · Orden
```
1. Confirmar P1–P8 verdes (checklist §1). Si alguna falla → ALTO, no continuar.
2. Congelar cambios de código del arco (rama del commit E6 sin diffs pendientes).
3. Tag de release candidato:  git tag v2-h10-candidate <sha del commit E6>   (solo tras E6)
4. Snapshot de estado con manifiesto:  bash factory/scripts/ops/backup_factory_state.sh
   → guarda md5 de canonical_store/, graph_store/, canonical_store_v2/, graph_store_v2/,
     decisions_v2.jsonl, audit trail. Registrar ruta y digests.
5. Registrar decisión de habilitación por gobernanza (familia ARTIFACT_VERSION o la que
   Capa 9 designe): propose → confirm con X-Identity-Key de Cesar. NO editar el ledger a mano.
6. Verificar egress lock del runtime endurecido (H-5F):
   docker exec factory-api <probe> → EgressBlocked esperado; red factory_isolated activa.
```

### 2.2 · Qué NO cambia en enablement
- Los ficheros `:ro` del runtime (qa40/opportunities/held_out) siguen `:ro`.
- El documento original sigue siendo fuente maestra; nunca se sobrescribe.
- Sin aprobación automática de documentos, sin cierre de CAPA, sin liberación de lote.

---

## 3 · CUTOVER PLAN  (el "flip")

### 3.1 · Punto exacto del flip
`factory/regulatory/validation_v2/v2_runtime.py` líneas **45–47** (hoy):
```python
_CANON  = Path("factory/regulatory/canonical_store")
_GRAPH  = Path("factory/regulatory/graph_store")
_EXT_VER = "canonical-v1-2026-08"
```
Cutover = repuntar a la base CLEAN + `+tests-v1`. **Dos variantes** (Capa 9 elige):

| Variante | Cambio | Nota |
|---|---|---|
| **V-A (promoción de contenido)** | Regenerar `canonical_store/` + `graph_store/` reales desde HEAD con `V2_TEST_EXTRACTION=ON` sobre el corpus RW-6+RW-0003; `_EXT_VER → "canonical-v1-2026-08+tests-v1"`. Rutas 45-46 SIN cambio. | La base de producción pasa a 258 claims RW-0012 (E3-A). Requiere P3 firmado. |
| **V-B (repunte de rutas)** | `_CANON → canonical_store_v2`, `_GRAPH → graph_store_v2`, `_EXT_VER → "…+tests-v1"`. | Más rápido; deja `canonical_store_v2/` como store de producción (sacarlo del `.gitignore` y versionarlo, o mantener política de regenerable). |

Recomendación: **V-A** — mantiene una sola raíz de store de producción y evita ambigüedad de rutas a largo plazo. V-B sirve como rollback instantáneo.

### 3.2 · Secuencia de cutover
```
1. Ventana de mantenimiento anunciada. Sin corridas en vuelo.
2. Backup fresco (§2.1 paso 4) + verificar que restaura (dry-run de restore_factory_state.py).
3. Aplicar la variante elegida (V-A: regenerar; V-B: editar 3 líneas).
4. Reconstruir contenedor factory-api SOLO si cambió código Python (CLAUDE.md regla 4).
   Esperar 90 s tras el rebuild antes de verificar.
5. Corrida de verificación sobre el corpus de referencia:
   - fingerprints esperados (candidato H-10):
     INPUT_CONFIG   = 0de04225362a6f863617d63717e5da82a7e829a2594f95e53f8f36cd5d07598f
     GRAPH_SNAPSHOT = 8ce23f30202991d87f6d867525306e50be1cdf191a40d57b6bd191a2d7b327f4
     FINDINGS       = 2b1a300ae26f76cbf09c6c7fac84053c7edf8603e893bcf75244e161127c834f
   - si NO coinciden → ROLLBACK inmediato (§3.3).
6. Registrar el cutover por gobernanza (propose → confirm, identidad de Cesar).
```

### 3.3 · Rollback
```
V-B:  revertir las 3 líneas 45-47 → estado previo ; rebuild ; 90 s ; re-verificar D-2 baseline
      (GRAPH 88f15b69… / FINDINGS fdc29721…).
V-A:  restaurar canonical_store/ + graph_store/ desde el backup del paso 2
      (factory/scripts/ops/restore_factory_state.py <ruta_backup>) ; rebuild ; re-verificar D-2.
Criterio de disparo: fingerprints ≠ esperados, o NEW_REGRESSION > 0, o cualquier condición
STOP (DATA_LOSS_RISK, DOCUMENT_EGRESS, GOVERNANCE_INTEGRITY_FAILURE).
```

---

## 4 · POST-CUTOVER REGRESSION PLAN

```
1. Suite completa:  python -m pytest factory/tests/ -q -p no:cacheprovider
   Baseline aceptable = SOLO EXC de entorno/servicio vivo:
     - test_corpus_runner::…_d4a_232_llamadas         (servicio)
     - test_mission_evidence_readers::…_health        (servicio vivo)
     - test_governance_ui_deploy_consistency_live      (servicio vivo, intermitente)
     - test_new_managers::test_passing/failing_tests   (servicio vivo, intermitente)
   Los 4 store-guards vs git-HEAD deben estar EN VERDE (post-commit E6).
   test_decision_migration debe estar EN VERDE (colisión D1-2026-003 resuelta).
   NEW_REGRESSION = 0  → si > 0, ROLLBACK.

2. Verificación de fingerprints determinista (2 corridas back-to-back, mismo run distinto run_id):
   GRAPH_SNAPSHOT y FINDINGS idénticos entre corridas → OK.

3. Verificación de integridad de gobernanza:
   - decisions_v2.jsonl: cadena append-only intacta, is_stale() = False.
   - audit trail: _walk_chain sin chain_errors / hash_errors.
   - families_state_hash estable.

4. Verificación de aislamiento (H-5F):
   - probe de egress desde factory-api → bloqueado.
   - ficheros :ro siguen :ro.

5. Verificación de no-regresión analítica (R-PAR post-cutover):
   - re-derivar findings del corpus compartido y comparar contra el paquete E3-A aceptado
     por finding_record_id: 0 findings perdidos por causa distinta a clone-drift ya explicado,
     0 band_changed no explicado.

6. Verificación de producto base intacto (CLAUDE.md):
   - gmp-api :8000 /health OK ; gmp-postgres/redis healthy ; contenedores aria-*/hotelbot-* sin tocar.
   - skill gmp-status: PASS=17 WARN=0 FAIL=0.

7. Registrar el resultado de la regresión post-cutover por gobernanza y en el informe maestro.
```

### 4.1 · Criterios de aceptación del cutover
```
CUTOVER_ACCEPTED = YES  sii:
  fingerprints == esperados (candidato H-10)          AND
  NEW_REGRESSION == 0                                  AND
  gobernanza íntegra (is_stale False, audit sin errores) AND
  aislamiento H-5F verificado                          AND
  R-PAR post-cutover sin pérdida no explicada          AND
  producto base gmp-api intacto (PASS=17)
Cualquier fallo → ROLLBACK + informe + nueva decisión de Capa 9.
```

---

## 5 · LO QUE ESTE PLAN NO AUTORIZA
- No autoriza el flip: es descripción, no ejecución.
- No declara D-6 = QUALIFIED (lo hace un humano, con el contrato WP-F).
- No sustituye E1…E6 ni D-5.
- No habilita liberación de lote, cierre de CAPA ni aprobación de documentos.
