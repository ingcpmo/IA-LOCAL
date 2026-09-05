# CF-6 v1.2 · CF6-2.5 (v3) — SMALL QUALITY PILOT · **run2 (corregido)**

**Fecha:** 2026-09-04 · **Autoridad:** Capa 9 = Cesar · **Alcance:** solo CF6-2.5 v3 — **no** CF6-3.
**Autorización LLM:** ADDENDUM `PILOT_EXECUTION-2026-039/-040` (human_confirmed `cesar`, tag `cf6-G2G-r1`).
**Prompt:** `shadow-cf6-composer-struct-v3` SIGNED (tag `cf6-G2-r1`).
**SAMPLE_MANIFEST:** `FROZEN@cf6-G2.5-manifest` (commit `e356b3f`, tag `cf6-G2.5-manifest`) ·
hash `7422faaf569430dbc8a19647a2d2b64ff6b53b5231fc4e7962b4486e3165f5a0` · mismas 7 secciones.
(`cf6-G2G` fue el cierre de scope previo, **no** la congelación del manifest.)

## Correcciones aplicadas (Fix A–D, aprobadas por Capa 9)

| Fix | Qué | Dónde |
|---|---|---|
| **A** | **UNA sola llamada LLM por sección** (CF-6 v1.2 §3.1) — eliminado el bucle de reintento | `cf6_pilot_runner_v3.py` |
| **B** | Orden `normalize_evidence_observed` (dedupe) **→** `validate_structure_contract` v3 **→** Q-STATE. La dedup corre **antes** de validar, para que el validador vea la estructura ya deduplicada | `cf6_pilot_runner_v3.py` |
| **C** | Tabla comparativa factual **v2 → v3** al inicio del `.md` (derivada de los artefactos, no escrita a mano); sin tocar A/B ni la rúbrica | `cf6_human_gate_v3.py` |
| **D** | Etiqueta del SAMPLE_MANIFEST: `FROZEN@cf6-G2.5-manifest` + `freeze_tag`. `sample_manifest_hash` **sin cambio** (no incluye `status`); tag `cf6-G2.5-manifest` **no movido** | `sample_manifest.py`, `CF6_2_5_SAMPLE_MANIFEST.json` |

La corrida v3 anterior (defectos de ejecución A+B) se conserva en `CF6_2_5_v3_run1_*` +
`CF6_2_5_v3_run1_NOTE.md` (`EXECUTION_STATUS: INVALID`). El piloto **v2** no se tocó.

Preflight reconfirmado antes de la 1ª llamada: `PILOT_SCOPE_MATCH_CF6=YES (vs v3) · REMAINING_BUDGET_SUFFICIENT=YES (250) · ACTIVE=YES · NOT_SUPERSEDED=YES · PROMPT_VERSION=shadow-cf6-composer-struct-v3 (SIGNED) · SAMPLE_MANIFEST_HASH=7422faaf…`.

---

## Resultado por sección (run2)

| sección | B | STRUCTURE_VALIDATION (v3) | QSTATE_RESULT | BLACKLIST | SAFE_MODE | technical_findings | allowed_technical_findings | duplicate_quotes (crudo del LLM) |
|---|---|---|---|---|---|---|---|---|
| **sec-0004** | RENDERED | OK | PASS | CLEAN | no | `[ACCESS_CONTROL_GAP, AUTHORITY_CHECK_GAP]` | `[ACCESS_CONTROL_GAP, AUTHORITY_CHECK_GAP]` | — |
| **sec-0005** | RENDERED | OK | PASS | CLEAN | no | `[]` | `[]` | `"With the FactoryTalk View SE electronic signature feature…"` (**deduplicada por Fix B** antes de validar) |
| **sec-0016** | RENDERED | OK | PASS | CLEAN | no | `[]` | `[]` | `"Process Automation Control Server System"`, `"The system shall implement the security and access control"` (**deduplicadas por Fix B**) |
| **sec-0018** | RENDERED | OK | PASS | CLEAN | no | `[ACCESS_CONTROL_GAP, AUTHORITY_CHECK_GAP]` | `[ACCESS_CONTROL_GAP, AUTHORITY_CHECK_GAP]` | — |
| **sec-0026** | RENDERED | OK | PASS | CLEAN | no | `[BACKUP_RECOVERY_GAP]` | `[BACKUP_RECOVERY_GAP]` | — |
| **sec-0042** | RENDERED | OK | PASS | CLEAN | no | `[IMPLEMENTATION_WITHOUT_REQUIREMENT, ORPHAN_DESIGN_ELEMENT]` | `[IMPLEMENTATION_WITHOUT_REQUIREMENT, ORPHAN_DESIGN_ELEMENT]` | — |
| **sec-0062** | **SAFE_MODE** | `reviewer_action menciona "cumplen"` | n/a (sin estructura) | CLEAN | **sí** | `[]` | `[]` | — |

### `reviewer_action` emitido por el modelo (pre-render / pre-gate)

- **sec-0004**: *"Revisar en RW-0005 si los pasajes recuperados cubren los requisitos de interrupciones de procesos y niveles de seguridad de inicio de sesión de administradores y mantenimiento; no se ancló eco léxico para distinguir hueco real de límite de extracción."*
- **sec-0005**: *"Revisar en RW-0005 si los pasajes recuperados cubren los requisitos de registro de cambios y firmas electrónicas según 21 CFR 11.50 y 11.70; confirmar si se incluyen los campos de fecha y hora de los cambios."* — sin "cumplen" esta vez.
- **sec-0016**: *"Revisar en RW-0006 si los sub-criterios de 21 CFR 11.10(d) sobre seguridad y control de acceso, y medición de parámetros críticos quedan cubiertos por los pasajes recuperados; el motor automático no ancló evidencia léxica para ninguno."*
- **sec-0018**: *"Revisar en RW-0006 si los pasajes recuperados cubren los requisitos de control de acceso y verificación de autoridad para el sistema PLC; el motor automático no ancló evidencia léxica para ninguno."*
- **sec-0026**: *"Revisar en RW-0006 si el sistema de respaldo por batería (UPS) está descrito en el alcance documental y contrastarlo con el finding de trazabilidad técnica; no se confirmó automáticamente."*
- **sec-0042**: *"Revisar en RW-0012 si los claims de implementación y los elementos de diseño señalados trazan a un requisito o diseño aguas arriba; distinguir hueco real de trazabilidad de límite de extracción."*
- **sec-0062** (→ SAFE_MODE): *"Revisar en RW-0014 si los pasajes recuperados **cumplen** con los requisitos regulativos; …"* — rechazado por v3.

---

## Resumen comparativo v2 → v3 (factual — también en el paquete humano)

| Sección | v2 | v3 | Cambio observado |
|---|---|---|---|
| sec-0004 | RENDERED | RENDERED | technical_findings corregidos + página inventada eliminada |
| sec-0005 | RENDERED | RENDERED | technical_findings corregidos (citas duplicadas ahora deduplicadas por Fix B) |
| sec-0016 | RENDERED | RENDERED | technical_findings corregidos + página inventada eliminada (dedup por Fix B) |
| sec-0018 | RENDERED | RENDERED | technical_findings corregidos |
| sec-0026 | SAFE_MODE | RENDERED | modo seguro anterior (Q-STATE-4) superado |
| sec-0042 | SAFE_MODE | RENDERED | modo seguro anterior (Q-STATE-5) superado |
| sec-0062 | RENDERED | SAFE_MODE | v3 detiene "cumplen" antes de publicar — **seguridad, no regresión** (opción (a) de Capa 9) |

**6 RENDERED / 1 SAFE_MODE.** El único SAFE_MODE (sec-0062) es el gate deteniendo "cumplen"
que v2 publicaba — mejor seguridad. Persistencia de "cumplen" = limitación del 7B; Capa 9
eligió **opción (a)**: aceptar 5/7+ RENDERED con sec-0062 en SAFE_MODE documentado.

---

## Cierre

```
LLM_CALLS_TOTAL       = 7    (1 por sección — Fix A ; 7/250)
LLM_CALLS_BY_SECTION  = {sec-0004:1, sec-0005:1, sec-0016:1, sec-0018:1, sec-0026:1, sec-0042:1, sec-0062:1}
sections_rendered     = 6    sections_safe_mode = 1    SAFE_MODE_SECTIONS = [sec-0062]
POST_QSTATE_LLM_CALLS = 0
G4D_CALLS             = 0    (G4d NO re-ejecutado)
L2_MUTATIONS          = 0
HUMAN_STATE_CHANGES   = 0    (457 findings UNREVIEWED)
FINDINGS_FINGERPRINT  = 235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23
qstate_violations_in_published = 0 · blacklist_hits_in_published = 0
ledger decisions_v2.jsonl : sin cambios · artefactos del piloto v2 : sin cambios · SAMPLE_MANIFEST hash sin cambio
tags cf6-G1 … cf6-G2G-r1 : sin mover · NO se creó el tag cf6-G2.5
```

**HUMAN_QUALITY_GATE (v3) = PENDIENTE.** `CF6_2_5_v3_HUMAN_QUALITY_GATE.md` — tabla comparativa +
A vs B por sección + rúbrica §4.2 **vacía**. Claude Code **no** evalúa la rúbrica, **no** declara
PASS/FAIL. **STOP.** No se crea `cf6-G2.5`. No CF6-3.
