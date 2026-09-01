# F0 — Estado real del ledger `factory/layer9/decisions/decisions_v2.jsonl`

**HEAD_REAL:** `90960059b609b5cd921d913e176888e1f9a6c248` (`9096005`) · rama `fix/clon-local-validacion`

| | líneas | sha256 |
|---|---:|---|
| **En disco (working tree)** | **259** | `1b0c7cf82ed7b2b056aade48c7e7dfa41142b108f94dfda0d0dc9836206a4af4` |
| **En HEAD (`9096005`)** | 255 | `42fa47f712e95732aac62fd4b53098e481ea31d554e67c1d38564535d4aaee92` |

## Diff HEAD → disco = exactamente 4 líneas añadidas

| instance_id | decision_origin | proposed_by_id | approved_by_id | decision_date (UTC) | gate | decision_ref | payload clave |
|---|---|---|---|---|---|---|---|
| `ARTIFACT_VERSION-2026-022` | `agent_proposed` | `mission_control_ui` | — | 2026-09-01T15:57:50 | E1 | `E1-3-H10-RELATIONS-20260831` | `verdict_set_sha256=4e23a1466ef12bc4286f25ba1700a768df0a794eb16a5d58c46e63d3d287bd97`, `sample_size=67`, counts `{CORRECT:66, WRONG_NODE:1, SPURIOUS:0, AMBIGUOUS:0}` |
| `ARTIFACT_VERSION-2026-023` | `human_confirmed` | — | `Cesar` (`cesar may`) | 2026-09-01T15:57:54 | E1 | `E1-3-H10-RELATIONS-20260831` | `confirms_instance_id=ARTIFACT_VERSION-2026-022` |
| `ARTIFACT_VERSION-2026-024` | `agent_proposed` | `mission_control_ui` | — | 2026-09-01T16:00:52 | E1 | `E1-ACCEPTANCE-20260831` | `e1_acceptance=PASS`, `based_on="ARTIFACT_VERSION-2026-030 (E1-3 verdict_set 7c905e2...)"`, `rc2=RESOLVED`, `rc3=RESOLVED` |
| `ARTIFACT_VERSION-2026-025` | `human_confirmed` | — | `Cesar` (`cesar may`) | 2026-09-01T16:00:56 | E1 | `E1-ACCEPTANCE-20260831` | `confirms_instance_id=ARTIFACT_VERSION-2026-024` |

Estas 4 líneas son **del servicio** (`proposed_by_id="mission_control_ui"`, par propose→confirm,
`approved_by_id="Cesar"`). Categoría F0: **GOBERNADO_PENDIENTE_DE_PERSISTIR**.

## Presencia de `ARTIFACT_VERSION-2026-022..032` en disco

| id | ocurrencias como registro | ocurrencias como referencia (`confirms_instance_id` / `based_on`) |
|---|---:|---:|
| `-022` | 1 (línea propia) | 1 (referida en `-023`) |
| `-023` | 1 | 0 |
| `-024` | 1 | 1 (referida en `-025`) |
| `-025` | 1 | 0 |
| `-026` … `-032` | **0** | 0 |

**`-026..-032` NO existen en el ledger en disco.**

## Observación para F4 (corrección 8 — colisión / reuso de IDs) — NO se resuelve en F0

Devin, el 2026-08-31, vio en el **audit trail** las líneas `ARTIFACT_VERSION-2026-022..032`
escritas por un **hand-edit no gobernado** (`recorded_by: null`, la mitad sin `approved_by_id`),
que en la corrida previa se **revirtió** con `git checkout HEAD -- decisions_v2.jsonl`.

Después de esa reversión, Mission Control asignó **de nuevo** los ids `022..025` a decisiones
**distintas**:

| id | hand-edit (audit trail 2026-08-31, revertido) | Mission Control (ledger disco 2026-09-01) |
|---|---|---|
| `-022` | E1 / `E1-2-H10-RELATIONS-20260831` (propose, `by=None`, `recorded_by=null`) | E1 / **`E1-3-H10-RELATIONS-20260831`** (propose, `mission_control_ui`) |
| `-023` | E1 / `E1-2-...` (confirm, `by=Cesar`, `recorded_by=null`) | E1 / **`E1-3-...`** (confirm, `Cesar`) |
| `-024` | E2 / `E2-RPAR-20260831` | E1 / **`E1-ACCEPTANCE-20260831`** |
| `-025` | E2 / `E2-RPAR-...` (confirm) | E1 / **`E1-ACCEPTANCE-...`** (confirm) |
| `-026..-032` | E3-A / `E3A-CLEANBASE`, E1 / `E1-3` (hash `7c905e2...`), E1 / `E1-ACCEPTANCE` | **no existen** |

**Mismo `instance_id`, distinto `decision_ref` / `payload` / `timestamp` / `verdict_set_sha256`.**
El `verdict_set_sha256` de la E1-3 del hand-edit era `7c905e256b25f2b01fc902fa7bed0dc0e6a1b2efdb119d09c01cb465f67a1f67`;
el de la E1-3 del servicio es `4e23a1466ef12bc4286f25ba1700a768df0a794eb16a5d58c46e63d3d287bd97`.
El `based_on` del registro `-024` del servicio cita `ARTIFACT_VERSION-2026-030` y el hash antiguo
`7c905e2...` — referencia a la numeración pre-reversión.

→ **F4 debe investigar** (F4_id_collision_analysis.md): NO_COLLISION | ID_REUSE | ID_COLLISION,
comparando audit trail vs access log vs ledger. F0 solo documenta la observación; **no la afirma
ni la descarta**.

## Contexto: commits de producto/gobernanza de ESTA sesión, previos a la mesa de reconciliación

Todos disclosed en `git log`; la mesa ya los tiene fichados (D6 → F4):

```
9096005  docs(cierre): REVISIÓN DE CIERRE H-1..H-10 + INSTRUCCIONES (docs; sin producto)
6be0626  docs(mesa-diseno): FASE 2 CERRADA = PASS / PARKED (docs; sin producto)
24549a3  feat(D5/v1.2): registrar H1 APPROVE_REMEDIATION_V1_2 + D5-D2 DEFERRED
         -> TOCA PRODUCTO/GOBERNADO: technical_completeness_rules.yaml (pending_approval),
            technical_findings.py, technical_completeness_loader.py, held_out_technical_corpus.yaml,
            real_corpus_opportunities.yaml, qa40_adjudication_sheet.yaml + tests v1.2 + docs D5.
         -> Hecho bajo AUTORIZACION Capa 9 explícita ("Apruebo formalmente H1"), NO bajo la
            disciplina fase-a-fase de este plan (que aún no existía).
         -> D6 (¿H1 requiere asiento gobernado?) está en F4. NO es un commit oculto.
9d6c86f  feat(mesa-diseno): H-4 + prueba de recall (prototipo aislado factory/prototypes/)
647b710  feat(mesa-diseno): prototipo aislado + bake-off (prototipo aislado)
```

**STOP F0 no se dispara:** no hay commits de producto **ocultos**; `24549a3` está completamente
disclosed y su reconciliación de gobernanza ya está agendada en F4 (D6).
