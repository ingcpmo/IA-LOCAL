# CF-6 v1.2 · CF6-2.5 (v3) — SMALL QUALITY PILOT con `shadow-cf6-composer-struct-v3`

**Fecha:** 2026-09-04 · **Autoridad:** Capa 9 = Cesar · **Alcance:** solo CF6-2.5 v3 — **no** CF6-3.
**Autorización LLM:** ADDENDUM `PILOT_EXECUTION-2026-039/-040` (human_confirmed `cesar`, tag `cf6-G2G-r1`).
**Prompt:** `shadow-cf6-composer-struct-v3` SIGNED (tag `cf6-G2-r1`, sha `0f1ecd72c81ffbae…`).
**SAMPLE_MANIFEST:** `FROZEN@cf6-G2G` · hash `7422faaf569430dbc8a19647a2d2b64ff6b53b5231fc4e7962b4486e3165f5a0` · mismas 7 secciones.

Preflight reconfirmado antes de la 1ª llamada: `PILOT_SCOPE_MATCH_CF6=YES · REMAINING_BUDGET_SUFFICIENT=YES (250) · ACTIVE=YES · NOT_SUPERSEDED=YES · PROMPT_VERSION=shadow-cf6-composer-struct-v3 · SAMPLE_MANIFEST_HASH=7422faaf…`.

Artefactos v3 **separados**, sin sobrescribir el piloto v2:
`CF6_2_5_v3_B_OUTPUTS.jsonl` · `CF6_2_5_v3_PILOT_RUN.json` · `CF6_2_5_v3_HUMAN_QUALITY_GATE.md`.

---

## Resultado por sección

| sección | B | STRUCTURE_VALIDATION (v3) | QSTATE_RESULT | BLACKLIST | SAFE_MODE | technical_findings | allowed_technical_findings | duplicate_quotes |
|---|---|---|---|---|---|---|---|---|
| **sec-0004** | RENDERED | OK | PASS | CLEAN | no | `[ACCESS_CONTROL_GAP, AUTHORITY_CHECK_GAP]` | `[ACCESS_CONTROL_GAP, AUTHORITY_CHECK_GAP]` | — |
| **sec-0005** | SAFE_MODE | `evidence_observed: cita duplicada` + `reviewer_action menciona "cumplen"` | n/a (sin estructura) | CLEAN | **sí** | `[]` | `[]` | `"With the FactoryTalk View SE electronic signature feature, each entry into the FactoryTalk View"` |
| **sec-0016** | SAFE_MODE | `evidence_observed: 2 citas duplicadas` | n/a (sin estructura) | CLEAN | **sí** | `[]` | `[]` | `"Process Automation Control Server System"`, `"The system shall implement the security and access control"` |
| **sec-0018** | RENDERED | OK | PASS | CLEAN | no | `[ACCESS_CONTROL_GAP, AUTHORITY_CHECK_GAP]` | `[ACCESS_CONTROL_GAP, AUTHORITY_CHECK_GAP]` | — |
| **sec-0026** | RENDERED | OK | PASS | CLEAN | no | `[BACKUP_RECOVERY_GAP]` | `[BACKUP_RECOVERY_GAP]` | — |
| **sec-0042** | RENDERED | OK | PASS | CLEAN | no | `[IMPLEMENTATION_WITHOUT_REQUIREMENT, ORPHAN_DESIGN_ELEMENT]` | `[IMPLEMENTATION_WITHOUT_REQUIREMENT, ORPHAN_DESIGN_ELEMENT]` | — |
| **sec-0062** | SAFE_MODE | `reviewer_action menciona "cumplen"` | n/a (sin estructura) | CLEAN | **sí** | `[]` | `[]` | — |

### `reviewer_action` emitido por el modelo (pre-render / pre-gate)

- **sec-0004** (RENDERED): *"Revisar en RW-0005 si los pasajes recuperados cubren los requisitos de interrupciones de procesos y niveles de seguridad de inicio de sesión de administradores y mantenimiento; no se ancló eco léxico para distinguir hueco real de límite de extracción."* — sin páginas, sin "cumple", sin CAPA.
- **sec-0005** (→ SAFE_MODE): *"Revisar en RW-0005 si los pasajes recuperados **cumplen** con los requisitos regulativos de 21 CFR 11.50 y 11.70; …"* — rechazado por v3 (`cumplen`).
- **sec-0016** (→ SAFE_MODE): *"Revisar en RW-0006 si los sub-criterios de 21 CFR 11.10(d) … quedan cubiertos por los pasajes recuperados; el motor automático no ancló evidencia léxica para ninguno."* — el texto es limpio; el rechazo fue por **citas duplicadas en `evidence_observed`**.
- **sec-0018** (RENDERED): *"Revisar en RW-0006 si los pasajes recuperados cubren los requisitos de control de acceso y verificación de autoridad para el sistema PLC; el motor automático no ancló evidencia léxica para ninguno."*
- **sec-0026** (RENDERED): *"Revisar en RW-0006 si el sistema de respaldo por batería (UPS) está descrito en el alcance documental y contrastarlo con el finding de trazabilidad técnica; no se confirmó automáticamente."*
- **sec-0042** (RENDERED): *"Revisar en RW-0012 si los claims de implementación y los elementos de diseño señalados trazan a un requisito o diseño aguas arriba; distinguir hueco real de trazabilidad de límite de extracción."*
- **sec-0062** (→ SAFE_MODE): *"Revisar en RW-0014 si los pasajes recuperados **cumplen** con los requisitos regulativos; …"* — rechazado por v3 (`cumplen`).

---

## Observación (para el gate humano; Claude Code NO puntúa)

- **v3 corrigió el defecto principal de v2 en `technical_findings`:** en las 4 secciones RENDERED, `technical_findings == allowed_technical_findings` (subtypes técnicos reales); **cero** `CROSS_DOMAIN` / `REGULATORY` / `REGULATORY_INCONCLUSIVE`. En las 3 REGULATORY con `allowed = []`, el modelo devolvió `[]`.
- **Las 3 SAFE_MODE** fueron rechazos legítimos del validador v3 (no del renderer): `reviewer_action` con "cumplen" (sec-0005, sec-0062) y citas textualmente duplicadas en `evidence_observed` (sec-0005, sec-0016). El modelo 7B sigue emitiendo esos patrones; v3 los detiene antes de Q-STATE. B en esas 3 = plantilla determinista conservadora (`[NARRATIVA LLM NO DISPONIBLE — no superó el control]`).
- **Sin páginas fabricadas** en ningún `reviewer_action` (defecto de v2 en sec-0004/sec-0016: no reapareció).
- `POST_QSTATE_LLM_CALLS = 0` · `qstate_violations_in_published = 0` · `blacklist_hits_in_published = 0`.

---

## Cierre

```
LLM_CALLS_TOTAL       = 10   (sec-0004/0018/0026/0042 = 1 ; sec-0005/0016/0062 = 2, con reintento; 10/250)
LLM_CALLS_BY_SECTION  = {sec-0004:1, sec-0005:2, sec-0016:2, sec-0018:1, sec-0026:1, sec-0042:1, sec-0062:2}
sections_rendered     = 4   sections_safe_mode = 3   SAFE_MODE_SECTIONS = [sec-0005, sec-0016, sec-0062]
POST_QSTATE_LLM_CALLS = 0
G4D_CALLS             = 0    (G4d NO re-ejecutado)
L2_MUTATIONS          = 0
HUMAN_STATE_CHANGES   = 0    (457 findings UNREVIEWED)
FINDINGS_FINGERPRINT  = 235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23
ledger decisions_v2.jsonl : sin cambios   ·   artefactos del piloto v2 : sin cambios
tests: test_shadow_cf6_pilot_runner_v3.py + test_shadow_composer_prompt_v3.py = 44 passed
```

**HUMAN_QUALITY_GATE (v3) = PENDIENTE.** `CF6_2_5_v3_HUMAN_QUALITY_GATE.md` — A vs B por sección,
rúbrica §4.2 **vacía**. Claude Code **no** evalúa la rúbrica, **no** declara PASS/FAIL.
**STOP.** No se crea el tag `cf6-G2.5`. No se ejecuta CF6-3.
