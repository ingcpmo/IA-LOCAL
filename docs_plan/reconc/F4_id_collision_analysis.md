# F4 — ANÁLISIS DE COLISIÓN / REUSO DE ID (`ARTIFACT_VERSION-2026-022..032`)

**Plan de reconciliación v1.1 · FASE 4 · acción 1 (corrección 8) · obligatoria y primero.**
**READ-ONLY.** Fuentes: `factory/audit/factory_audit.jsonl` (append-only) · `factory/layer9/decisions/decisions_v2.jsonl` · `factory/services/decision_store_v2.py`.

---

## VEREDICTO: **ID_COLLISION** (probado)

`ARTIFACT_VERSION-2026-022`, `-023`, `-024`, `-025` fueron emitidos **DOS veces**, para
decisiones **materialmente distintas**, con ~21 h de diferencia.

---

## 1. Evidencia — cada id aparece 2× en el audit trail (append-only)

| id | evento 1 (audit trail) | evento 2 (audit trail) | ¿ledger en disco? |
|---|---|---|---|
| `-022` | 2026-08-31T15:10:59 · `agent_proposed` · `tsh 84c54618` | 2026-09-01T15:57:50 · `agent_proposed` · `tsh 84c54618` | sí (el de 09-01) |
| `-023` | 2026-08-31T15:11:04 · `human_confirmed` Cesar · `tsh 84c54618` | 2026-09-01T15:57:55 · `human_confirmed` Cesar · `tsh 84c54618` | sí (el de 09-01) |
| `-024` | 2026-08-31T16:36:05 · `agent_proposed` · **`tsh e10fc3a969e2`** | 2026-09-01T16:00:52 · `agent_proposed` · **`tsh 84c54618`** | sí (el de 09-01) |
| `-025` | 2026-08-31T16:36:13 · `human_confirmed` Cesar · **`tsh e10fc3a969e2`** | 2026-09-01T16:00:56 · `human_confirmed` Cesar · **`tsh 84c54618`** | sí (el de 09-01) |
| `-026`..`-028` | 2026-08-31 16:36–17:03 · `tsh 46758dfa79fa` | — | **no** |
| `-029`..`-032` | 2026-08-31 19:20–19:41 · `tsh 84c54618` | — | **no** |

### Prueba de que es COLISIÓN (no simple reuso benigno)

- **`-024`/`-025`: `target_set_hash` DISTINTO** entre los dos eventos
  (`e10fc3a969e22cea…` el 2026-08-31 → `84c54618241c…` el 2026-09-01).
  El **mismo `instance_id`** apunta a un **artefacto gobernado distinto** en cada evento.
- **`-022`/`-023`:** mismo `tsh` (`84c54618…` = `H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json`), pero
  distinta **revisión E1**: el evento 2026-08-31 corresponde a **E1-2** (así lo documenta
  `docs_plan/E1_SIGNATURE_HISTORY.md`: *"E1-2 · ledger = ARTIFACT_VERSION-2026-022 (propose) +
  ARTIFACT_VERSION-2026-023 (confirm, Cesar)"*); el evento 2026-09-01 corresponde a **E1-3**
  (`verdict_set_sha256 = 4e23a146…`, counts `{CORRECT:66, WRONG_NODE:1, SPURIOUS:0, AMBIGUOUS:0}`).

**El mismo `ARTIFACT_VERSION-2026-022` = E1-2 en el audit trail y E1-3 en el ledger.** Colisión.

---

## 2. Causa raíz — DEFECTO del generador de IDs

`factory/services/decision_store_v2.py:179-189`:

```python
def next_instance_id(family: str, *, year: int | None = None, store_file: Path | None = None) -> str:
    yr = year or datetime.now(timezone.utc).year
    prefix = f"{family}-{yr}-"
    used = [
        int(r["decision_instance_id"][len(prefix):])
        for r in read_all(store_file)                       # <-- lee decisions_v2.jsonl (MUTABLE, git-tracked)
        if r.get("decision_instance_id", "").startswith(prefix)
    ]
    return f"{prefix}{(max(used) + 1) if used else 1:03d}"  # <-- max() del ARCHIVO, no del audit trail
```

- El "siguiente id" = `max(secuencias presentes en decisions_v2.jsonl) + 1`.
- `decisions_v2.jsonl` es **mutable y versionado en git** → se puede **revertir**
  (`git checkout HEAD -- decisions_v2.jsonl`).
- El **audit trail** (`factory_audit.jsonl`, append-only) **NO se consulta**.

**Secuencia real:**
1. 2026-08-31: sesión de firma en Mission Control acuña `022..032` (E1-2, E1_ACCEPTANCE,
   artefactos `e10fc3a969e2`/`46758dfa79fa`, más firmas E1 posteriores). Se escriben al audit
   trail **y** a `decisions_v2.jsonl`.
2. En algún momento entre 2026-08-31 y 2026-09-01, ese estado de `decisions_v2.jsonl` (con
   `022..032`) se **revierte** — bien un `git checkout` (el de la fase E1 de esta mesa), bien
   uno anterior. `022..032` salen del archivo; **permanecen en el audit trail**.
3. 2026-09-01: nueva sesión de firma (E1-3 + E1_ACCEPTANCE). `next_instance_id` lee el
   `decisions_v2.jsonl` revertido → `max(used) = 021` → acuña **`022`** de nuevo, ahora para
   **E1-3**. Idem `023..025`.

> El defecto lo provoca **revertir registros que el contador esperaba conservar**
> (corrección 8, textual). No es aleatorización de hash; es `max()` sobre un archivo revertible.

---

## 3. Corrección PROPUESTA — gobernada, NO se aplica aquí

**F4 NO reescribe nada.** Se registra como hallazgo y se propone:

- **`next_instance_id` debe calcular `max()` sobre la UNIÓN de:**
  1. las secuencias en `decisions_v2.jsonl`, **y**
  2. las secuencias de eventos `layer9_decision_recorded` con esa familia en
     `factory_audit.jsonl` (append-only, no revertible).
  Alternativa equivalente: un **contador monótono en un archivo dedicado** (patrón de
  `factory/services/decision_legacy_adapter.py:70-78`, que usa `counters[key]` incremental
  y no `max()` del store) — nunca revertido, nunca derivado del JSONL.
- **Test de regresión propuesto:** revertir N líneas del final de `decisions_v2.jsonl` →
  `next_instance_id` NO debe regresar por debajo del máximo histórico del audit trail.
- **Los 022..032 del 2026-08-31 NO se re-escriben ni se borran** del audit trail (append-only,
  prohibido). Quedan como evidencia histórica; su clasificación está en
  `F4_ledger_reconciliation.md`.

Esta corrección es **código de servicio** (`decision_store_v2.py`) → fuera del alcance
editable de F4; requiere su propia fase / autorización de Capa 9.

---

## 4. Reproducibilidad (para Devin)

```
# 022..032 aparecen en el audit trail:
grep -oE "ARTIFACT_VERSION-2026-0(2[2-9]|3[0-2])" factory/audit/factory_audit.jsonl | sort | uniq -c
#  -> 022..025 x2 ; 026..032 x1

# el generador lee el JSONL, no el audit trail:
sed -n '179,189p' factory/services/decision_store_v2.py

# tsh distinto para -024 entre los dos eventos:
grep '"ARTIFACT_VERSION-2026-024"' factory/audit/factory_audit.jsonl | grep -oE '"target_set_hash": "[0-9a-f]{12}'
#  -> e10fc3a969e2 (2026-08-31) ; 84c54618241c (2026-09-01)
```
