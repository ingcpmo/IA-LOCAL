# SHADOW · G5 — CIERRE DEL ARCO "CAPA LLM DE INTERPRETACIÓN"

**Arco:** Capa LLM de interpretación sobre findings deterministas (diseño v1.1).
**Fase:** G5 — cierre: evidencia consolidada, atestación de invariantes de todo el arco,
**paquete para decisión humana de Capa 9**. Sin LLM, sin re-ejecución, L2 inmutable.
**Rama:** `shadow/llm-interpretation-layer` · **HEAD:** `393dfb6` (tag `shadow-G4.1`).
**Base del arco:** `reconc-acceptance-v1` → `0e1e88a` · baseline determinista `FINDINGS_FINGERPRINT
= 235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23`.

---

## 1 · Executive Summary

El arco construyó y ejecutó, fase a fase con auditoría externa por fase, una **capa L3/L4
aditiva** sobre los 457 findings deterministas L2 del corpus reconc:

- **G0–G3.1 (determinista, 0 LLM):** baseline congelada · router primario exclusivo (457) ·
  contratos de experto + verificador fail-closed + verificador de cobertura · post-pass
  cross-domain (15 relaciones) + spec del Regulatory Retrieval Gateway (no habilitado) ·
  Composer esqueleto determinista (66 secciones, cobertura 457/457).
- **G4 (LLM real, LOCAL):** `PILOT_EXECUTION-2026-035` firmada por Capa 9 (`-036`, `Cesar`) ·
  **481 llamadas reales** a `qwen2.5:7b-instruct-q4_K_M` (LOCAL) · 5 sub-agentes (Technical,
  Cross-domain, Functional/Traceability, Regulatory-triage, Composer) · **372 opiniones
  `SHADOW_ACCEPTED` / 43 `SHADOW_REJECTED`** por el verificador G2 fail-closed · narrativa
  borrador `[SHADOW / NO GOBERNADO]` en 63 de 66 secciones.
- **G4.1:** congelado en Git de la evidencia de gobernanza (`-035`/`-036`) que la auditoría de
  G4.PILOT pidió hacer auditable.

**Nada de esto cambió L2.** `FINDINGS_FINGERPRINT` idéntico de principio a fin. `human_state` de
los 457 = `UNREVIEWED`. 0 declaraciones de cumplimiento / aprobación / CAPA / release. La capa
LLM **asiste** al revisor humano; **no juzga cumplimiento** — el techo de recall del modelo no se
tocó (los 285 regulatorios siguen `REGULATORY_INCONCLUSIVE` en L2).

**Decisión que corresponde a Capa 9:** qué hacer con el reporte narrativo shadow (adoptarlo como
artefacto de asistencia al revisor, mantenerlo shadow-only pendiente de más evaluación, o
descartarlo). §8.

---

## 2 · Cadena de commits / tags del arco

```
0e1e88a  reconc-acceptance-v1   (baseline · FINDINGS 235f724a…)
3bacfd0  shadow-G0     consolidación/formalización de baseline — 457 findings congelados
3ccc485  shadow-G1     router determinista — routing primario exclusivo (457) + cross_domain_flag (15)
e5458d3  shadow-G2     contratos de experto + reutilización selectiva + G2.1 verificador fail-closed + G2.2 cobertura
62fbb44  shadow-G2-r1  related_finding_ids -> MUST_NOT_CHANGE (carry-forward CF-1 de la auditoría de G2)
bd79541  shadow-G3     post-pass cross-domain determinista + especificación del Regulatory Retrieval Gateway
9e819bf  shadow-G3.1   Composer esqueleto determinista (corrección de auditoría de G3)
8fceed5  shadow-G4     capa LLM de interpretación — G4a..G4e con LLM real (481 llamadas)
393dfb6  shadow-G4.1   freeze G4 pilot governance evidence (corrección de auditoría de G4.PILOT)
<este>   shadow-G5     cierre del arco (propuesto)
```

Historia lineal, sin merges. Ningún tag previo se movió en ninguna corrección.

---

## 3 · Evidencia consolidada por fase

| Fase | Artefacto(s) clave (sha256) | Números |
|---|---|---|
| **G0** | `FINAL_GMP_CORPUS_FINDINGS.json` `95a79f9b6276ff2a7972100764b308fa4b09f0027c6679ea831b441eb880f02c` · `FINAL_GMP_CORPUS_ANALYSIS_REPORT.md` | 457 registros · 457 `finding_record_id` únicos · 457 `UNREVIEWED` · 342 `REGULATORY_INCONCLUSIVE` producidos por Tier-1 determinista (`LLM_CALLS=0`) |
| **G1** | `G1_routing.json` `212b5514c599728e83e22f7949cf6526fe948762eb0b1ab55ba084bc024826b1` · `factory/regulatory/shadow/router.py` | primario exclusivo: `REGULATORY` 285 · `FUNCTIONAL_TRACEABILITY` 98 · `TECHNICAL` 17 · `HUMAN_ONLY` 57 = **457** · `cross_domain_flag` = **15** (secundario) |
| **G2 + G2-r1** | `G2_contracts.json` `70bd594c5c142b595be6e03a92d0aef6d820bd5ea26be261c230863390aeb0b3` · `G2_verifier_report.json` `fe05c01afa6a6ce3c446528fe5675701c331e0ec3662888b0183cdf51c94d713` · `contracts.py` · `verifier.py` | 5 contratos de experto · `MUST_NOT_CHANGE` = **12 campos** (incl. `related_finding_ids`, CF-1) · `assessment` sin token de cumplimiento · **G2.1**: 4 fixtures adversariales → 100% `SHADOW_REJECTED` · **G2.2**: cobertura 457/457, omisión de 1 detectada · REUSE_EVALUATION `v2_judgment`: REUSE 5 / ADAPT 1 / DISCARD 5 |
| **G3** | `cross_domain_links.json` `11d99bf803ba571a1ff579089ada2b90242bb7cbefa184c2d293b436e08fcdd7` · `cross_domain.py` · Gateway spec (§4 de `G3_CROSS_DOMAIN_AND_GATEWAY.md`) | 15 relaciones `TECHNICAL_GAP_vs_REGULATORY_INCONCLUSIVE_SAME_RULE` (`cdl-0001..0015`) · **0** escritura en `related_finding_ids` · canal regulatorio externo **NO habilitado** (solo spec) |
| **G3.1** | `G3_1_composer_skeleton.json` `32572ad7a2123ae7441e76e8b5bb5b2f982176ac07bdd11058c28ff8a42cb885` · `composer.py` · `G3_1_report_v2_check.json` | 66 secciones (documento × regulación) · cobertura **457/457** · `no_rejudge_l2 = true` · `report_v2` verificado: `same_finding_record_id_set`, `l2_fact_mismatches = 0` |
| **G4** | `G4_SUMMARY.json` `5775b92d0073d3be0e91dd44789e7d6ac0ef685ead02c4602e51af6bd7870339` · `g4{a..e}.jsonl` · `g4_call_log.json` · `experts.py` | **481** llamadas LLM reales (ok 481 · failed 0) · `qwen2.5:7b-instruct-q4_K_M` digest `845dbda0ea48…` LOCAL · G2 verifier: **372 ACCEPTED / 43 REJECTED** · Composer 63 `NARRATIVE_DRAFTED` / 3 `NARRATIVE_BLOCKED` · cobertura narrativa **457/457** |
| **G4.1** | `G4_PILOT_AUDIT_RECONCILIATION.md` · ledger congelado `decisions_v2.jsonl` `d7a15efa461495cbd818110da6e32afa8ae86a12d41a9f57895db0542ea89f87` (266 líneas) | `PILOT_EXECUTION-2026-035` (`agent_proposed`) + `-036` (`human_confirmed`, `approved_by_id=Cesar`) auditables desde `shadow-G4.1`; append-only (+11 / -0) |

---

## 4 · Atestación de invariantes — TODO el arco

| Invariante | Resultado (G0 → G5) |
|---|---|
| **CRIT-0** — baseline determinista sin tocar | ✅ `FINDINGS_FINGERPRINT = 235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23` idéntico en cada atestación (re-corrida final de `run_v2_pipeline` desde el código del worktree con TODO el paquete shadow presente) · `INPUT_CONFIG 3fcb3ae8…` · `GRAPH_SNAPSHOT 2fdda0e2…` · counts 342/90/25 · `report_v2.py` / `findings/` / `validation_v2/` byte-idénticos al baseline |
| **CRIT-H** — gate humano intacto | ✅ `human_state` de los 457 = `UNREVIEWED` en todas las fases · `human_gate_intact = True` · nada auto-concluido: los 15 cross-domain `DISAGREEMENT_PERSISTS` → revisión humana; las 63 narrativas son borrador `[SHADOW]` |
| **CRIT-L2** — inmutabilidad de L2 | ✅ `L2_MUTATIONS = 0` en cada fase · `FINAL_GMP_CORPUS_FINDINGS.json` sha `95a79f9b…` sin cambio de G0 a G5 · el verificador G2 rechaza toda envoltura que altere `MUST_NOT_CHANGE` (12 campos, incl. `related_finding_ids`) — demostrado en G4 (43 rechazos) |
| **CRIT-E1** — `UNAUTHORIZED_CLIENT_DATA_EGRESS = 0` | ✅ único tráfico saliente en G4 = Ollama LOCAL (`localhost:11434`); 0 bytes de PDF/canonical/finding/graph a Internet |
| **CRIT-E2** — consultas externas auditadas | ✅ N/A — **0** consultas externas en todo el arco |
| **CRIT-E3** — sin contenido de cliente a Internet | ✅ |
| **CRIT-E4** — (G0–G5) `LLM_PROVIDER = LOCAL`, canal regulatorio externo NO habilitado | ✅ `LLM_PROVIDER = LOCAL` en G4 · Gateway solo especificado (G3 §4), nunca implementado ni activado |
| **Gobernanza** | ✅ `PILOT_EXECUTION-2026-035` (`agent_proposed`, `mission_control_ui`) → `PILOT_EXECUTION-2026-036` (`human_confirmed`, `approved_by_id = Cesar`, `confirms_instance_id = -035`), ambos `ACTIVE`, no superseded, en el ledger canónico y **congelados en Git** en `shadow-G4.1` (`git show shadow-G4.1:factory/layer9/decisions/decisions_v2.jsonl` → contiene `-035`/`-036`). Confirmación `01:26:05Z` < 1ª llamada LLM `~01:34Z`. Presupuesto **481 / 1000**. `authorizes_corpus/baseline = false` |
| **0 declaraciones prohibidas** | ✅ 0 tokens `COMPLIANT/APPROVED/OBSERVED/PASS/SATISFIES/CAPA_CLOSED/RELEASED` en las 481 salidas LLM · 0 `INCONCLUSIVE → observed` (los 285 findings L2 siguen `REGULATORY_INCONCLUSIVE`) |
| **Salidas solo bajo shadow/** | ✅ todo el output del arco vive bajo `docs_plan/shadow_llm/` (+ código nuevo bajo `factory/regulatory/shadow/` y sus tests) |
| **Tests** | ✅ `pytest test_shadow_{router,contracts,verifier,cross_domain,composer,experts}` → **70 passed** |

---

## 5 · Qué entregó la capa LLM (G4) — sin sobre-afirmar

| Sub-agente | Volumen | Resultado real | Lectura honesta |
|---|---|---|---|
| **G4a Technical** | 17 findings, 17 llamadas | `BEHAVIOR_NOT_FOUND_IN_SCOPE` ×17 · 17/17 `SHADOW_ACCEPTED` | El 7B **no encontró** el comportamiento requerido parafraseado en el alcance de ninguna de las 17 reglas de completitud → **concuerda con el gap determinista**; no aporta señal nueva más allá de confirmar la ausencia. |
| **G4b Cross-domain** | 15 relaciones, 15 llamadas | `DISAGREEMENT_PERSISTS` ×15 · 15/15 `SHADOW_ACCEPTED` | El modelo consideró que las 15 señales "gap técnico" ↔ "INCONCLUSIVE regulatorio" **no se reconcilian solas** → **las 15 a revisión humana**. Conservador (fail-toward-human), sin resolver ninguna. |
| **G4c Functional/Traceability** | 98 findings, 98 llamadas | `LIKELY_REAL_GAP` ×64 · `LIKELY_EXTRACTION_LIMIT` ×34 · 98/98 `SHADOW_ACCEPTED` | **Señal diferenciada real:** el modelo separa "hueco de trazabilidad real" (64) de "límite de extracción, el id existe pero la arista no se trazó" (34). Es la contribución de asistencia más sustantiva del arco — **priorización para el revisor**, no conclusión. |
| **G4d Regulatory-triage** | 285 findings, 285 llamadas | `CANDIDATE_RANKING_PROVIDED` ×278 · `NO_USEFUL_CANDIDATE` ×7 · **242 `SHADOW_ACCEPTED` / 43 `SHADOW_REJECTED`** (todas por anclaje) | Ordena los ≤5 candidatos de recuperación para el revisor. **43 opiniones rechazadas** porque el modelo citó texto que no ancla literalmente — el verificador fail-closed es indispensable como gate duro. **0 `INCONCLUSIVE → observed`**: los 285 findings L2 no se tocan. |
| **G4e Composer** | 66 secciones, 66 llamadas | 63 `NARRATIVE_DRAFTED` · 3 `NARRATIVE_BLOCKED` · cobertura 457/457 · 0 citas fuera de sección · marca `[SHADOW / NO GOBERNADO]` en las 63 | Borrador narrativo por documento × regulación, cada afirmación anclada a `finding_record_id`. Es un **borrador asistido para revisión humana**, nunca un informe aprobado. |

**Coste:** ~13469 s de wall LLM (~3,7 h), `qwen2.5:7b-q4` en CPU local.

---

## 6 · Qué NO cambió

- **El techo de recall del modelo.** La capa LLM no intenta detección automática de paráfrasis
  regulatoria; el bloque Regulatory es **triage**, no juicio. Los 285 findings siguen
  `REGULATORY_INCONCLUSIVE` en L2. Coherente con `CLAUDE.md` y con las 6 vías previas que
  midieron recall 0–2/7.
- **L2 / `human_state` / `related_finding_ids`.** Byte-idénticos de G0 a G5.
- **El pipeline determinista.** `run_v2_pipeline` / `report_v2` / `findings/` / `validation_v2/`
  sin tocar; `FINDINGS_FINGERPRINT` sin mover.
- **El canal regulatorio externo.** Especificado (Gateway), nunca abierto.

---

## 7 · Correcciones de auditoría aplicadas durante el arco

| # | Fase | Hallazgo externo | Corrección | Tag |
|---|---|---|---|---|
| CF-1 | G2 | `MUST_NOT_CHANGE_FIELDS` omitía `related_finding_ids` | +`related_finding_ids` (11→12 campos) + 4º fixture adversarial → `SHADOW_REJECTED` | `shadow-G2-r1` (`62fbb44`) — CERRADO |
| CF-2 | G3 | faltaba el Composer esqueleto determinista del plan | `composer.py` — 66 secciones documento × regulación, cobertura 457/457, `no_rejudge_l2`, `report_v2` verificado | `shadow-G3.1` (`9e819bf`) — CERRADO |
| CF-3 | G2 (G2.1/G2.2) | faltaba demostrar los verificadores deterministas | `verifier.py` — G2.1 fail-closed (3 fixtures adversariales obligatorios → 100% `SHADOW_REJECTED`) + G2.2 cobertura (457/457, omisión detectada) | incluido en `shadow-G2` / `-r1` — CERRADO |
| CF-4 | G4.PILOT | el tag `shadow-G4` congeló una copia antigua del ledger sin `-035`/`-036` | copia verbatim (append-only, +11/-0) del ledger autoritativo vivo al worktree + `G4_PILOT_AUDIT_RECONCILIATION.md` (reconcilia también el draft histórico `03_PROPUESTA_PILOT_EXECUTION_035.md`, cap≤20 ≠ instancia oficial `max_calls=1000`) | `shadow-G4.1` (`393dfb6`) — CERRADO |

---

## 8 · Paquete para la decisión de Capa 9

El arco entregó lo que el diseño v1.1 especificó, con L2 intacto y gate humano intacto. **La
decisión sobre qué hacer con el reporte narrativo shadow es humana** (`CLAUDE.md`; diseño v1.1:
"La decisión final es humana"). Opciones, sin recomendación sesgada:

| Opción | Qué implica | A favor | En contra |
|---|---|---|---|
| **A · Adoptar como artefacto de asistencia al revisor** | El revisor humano recibe, junto a los 457 findings L2 (fuente maestra), el borrador narrativo shadow por documento × regulación como ayuda de lectura/priorización — marcado `[SHADOW / NO GOBERNADO]`, nunca sustituye el juicio. | La señal de G4c (64 gap real / 34 límite de extracción) prioriza de verdad; la cobertura 457/457 y el anclaje a `finding_record_id` están verificados; el verificador fail-closed descartó el 10% de opiniones no ancladas. | 63/66 narrativas emitidas por un 7B q4 local; requiere que el revisor entienda que es borrador y verifique cada cita; coste ~3,7 h/corrida. |
| **B · Mantener shadow-only, pendiente de más evaluación** | Se conserva todo el paquete pero no se presenta al revisor; se define una métrica de utilidad (p. ej. concordancia con la adjudicación humana sobre una muestra) antes de decidir A. | No compromete el flujo de revisión hasta tener evidencia de utilidad medida; el fixture 7P+2N sigue siendo el instrumento de recall. | El paquete queda sin uso; requiere una fase de evaluación adicional (¿G6?). |
| **C · Descartar la vía LLM para este alcance** | Se archiva la capa L3/L4; el reporte al revisor sigue siendo el factual determinista (`report_v2`). | Coherente con "el techo es del modelo" si Capa 9 concluye que el triage no aporta suficiente; cero coste operativo. | Se pierde la señal diferenciada de G4c; el arco queda como evidencia negativa documentada. |

---

## 9 · Riesgos y límites declarados

- **Modelo:** `qwen2.5:7b-q4` local. El arco no lo cualifica (`MODEL_QUALIFICATION` es familia de
  gobernanza aparte). Un modelo mayor podría cambiar los resultados de G4c/G4d — no medido.
- **43 opiniones regulatorias rechazadas** por anclaje: el modelo parafrasea/inventa cita con
  frecuencia no despreciable; el verificador fail-closed es el único gate que lo detiene.
- **G4b uniformemente `DISAGREEMENT_PERSISTS`:** el modelo no discrimina entre relaciones
  cross-domain; posible límite del prompt o del modelo. Todas van a humano (fail-safe).
- **No re-medición de recall:** el arco no vuelve a correr el fixture 7P+2N; el techo 0–2/7
  previo sigue vigente como referencia.
- **Determinismo:** las salidas LLM de G4 **no son reproducibles byte-a-byte** (temp 0 no lo
  garantiza en Ollama). Los artefactos `g4{a..e}.jsonl` son la evidencia de ESTA corrida
  (`PILOT_EXECUTION-2026-035`, 481 llamadas).

---

## 10 · REPORTE DE FASE — G5 (formato v1.1)

```
FASE                    = G5 (cierre del arco — evidencia consolidada + atestación + paquete de decisión)
PRE_COMMIT              = 393dfb6  (tag shadow-G4.1)
POST_COMMIT            = <pendiente — cierre para el gate humano de Capa 9>
WORKTREE               = /home/cmay/ivr-ia/.claude/worktrees/shadow-llm  (git status --porcelain vacío)
DIFF (prohibidos)      = VACÍO — 0 modificaciones a ficheros existentes; solo NUEVO
                         docs_plan/shadow_llm/G5_ARC_CLOSURE.md
COMMANDS               = PYTHONHASHSEED=random python <atestación run_v2_pipeline>
                         pytest factory/tests/test_shadow_{router,contracts,verifier,cross_domain,composer,experts}.py -q
                         git show HEAD:factory/layer9/decisions/decisions_v2.jsonl | grep -c PILOT_EXECUTION-2026-035/-036
TEST_RESULTS           = 70 passed
FINGERPRINTS           = INPUT_CONFIG 3fcb3ae8… · GRAPH_SNAPSHOT 2fdda0e2… · FINDINGS 235f724a…  (== baseline, sin mover)
LLM_CALLS (fase G5)    = 0   (G4 = 481, sin cambio)
CLIENT_DATA_EGRESS     = 0   ·  external regulatory calls = 0
LLM_PROVIDER           = LOCAL
HUMAN_STATE_CHANGES    = 0   ·  L2_MUTATIONS = 0  ·  related_finding_ids sin cambios
GOVERNANCE             = PILOT_EXECUTION-2026-035/-036 auditables desde shadow-G4.1 (ledger congelado 266 líneas, sha d7a15efa…)
CRIT                   = CRIT-0 ✅ · CRIT-H ✅ · CRIT-L2 ✅ · CRIT-E1 ✅ · CRIT-E2 ✅ · CRIT-E3 ✅ · CRIT-E4 ✅
CORRECCIONES DE AUDITORÍA = CF-1 (shadow-G2-r1) · CF-2 (shadow-G3.1) · CF-3 (G2.1/G2.2) · CF-4 (shadow-G4.1)  — todas CERRADAS
DEVIATIONS             = ninguna
PROPOSED_VERDICT       = PASS — arco completo, L2 intacto, gate humano intacto, gobernanza auditable.
                         La adopción del reporte narrativo shadow (§8) es DECISIÓN DE CAPA 9.
```

---

## 11 · Cierre

El arco "Capa LLM de interpretación sobre findings deterministas" está **completo**: G0–G4.1
ejecutadas y auditadas (4 correcciones de auditoría cerradas), con una capa L3/L4 que **asiste**
al revisor humano sin tocar la fuente maestra L2, sin declarar cumplimiento, con la autorización
de Capa 9 (`PILOT_EXECUTION-2026-035/-036`) auditable en Git. El `FINDINGS_FINGERPRINT` es
idéntico al baseline. La capa LLM no movió el techo de recall del modelo — por diseño.

Lo que queda es una **decisión humana** (§8) sobre el uso del reporte narrativo shadow. Capa 8
no la toma.

*G5 · cierre del arco. Sin LLM, sin re-ejecución, sin tocar L2/human_state, sin mover el
fingerprint. Detenido en el gate de Capa 9.*
