# GATES HUMANOS E1–E5 — MECANISMO DE APROBACIÓN EN LA GOBERNANZA EXISTENTE

**Fecha:** 2026-08-31 · **Autoridad:** Capa 9 = Cesar · **Tipo:** survey + preparación READ-ONLY.
No se ejecutó ningún gate. No se creó ledger nuevo ni arquitectura nueva. `_EXT_VER`/`_CANON`/
`_GRAPH` sin tocar. `decisions_v2.jsonl` sin editar. QA40 sin tocar. Sin commit/push/flip.

---

## 0 · Cómo autentica la gobernanza (dos credenciales)

```
X-API-Key       = FACTORY_API_KEY  (compartida ; gatea el acceso a toda /api/v1/*)          -> factory/api/main.py::verify_api_key
X-Identity-Key  = clave por persona ; resuelta a nombre real contra el registro fuera de git  -> factory/api/auth.py::require_identity
                  registro: factory/config/identity_keys.yaml  (provisionado ; {Cesar, Andrea_Reviewer})
                  resolve: factory/core/identity_registry.resolve_identity(key)  ==  el mismo que valida identity_policy
```

`POST .../confirm` (firma humana) exige **ambas**. El nombre que firma NO viaja en el body —
lo pone `require_identity` desde `X-Identity-Key`. `factory-api` está arriba en `localhost:9000`
(`/health` = 200).

Mecanismo de decisión gobernada (append-only, Part 11): `factory/services/governance_service.py`
(`propose` → `confirm`) sobre `factory/services/decision_store_v2.py` ; cada `confirm` emite su
evento `layer9_decision_recorded` en la cadena de auditoría. **Es el mismo mecanismo con el que se
firmaron `ARTIFACT_VERSION-2026-019/020/021` (D-2, D-4).**

---

## 1 · Mapa gate → familia

| Gate | Familia de decisión | Por qué | ¿Requiere implementación? |
|---|---|---|---|
| **E1** revisión 77 relaciones H-10 | `ARTIFACT_VERSION` (target = el JSON de la muestra) ; los **77 veredictos individuales** van en `payload.verdicts[]` | No hay familia de "veredictos de arista". Un acto autenticado con los 77 veredictos enumerados en el payload registra cada uno individualmente sin inflar el ledger ni crear otra arquitectura. | **NO** — `decision_store_v2` ya acepta `payload` arbitrario. |
| **E2** aprobación R-PAR | `ARTIFACT_VERSION` (target = `docs_plan/R_PAR_DELTA_V1_V2_20260830.md`) | R-PAR es evidencia de validación de un cambio de versión → aceptación de versión de artefacto. Igual patrón que D-2/D-4. | **NO** |
| **E3-A** aceptación canonical CLEAN | `ARTIFACT_VERSION` (target = `canonical_store_v2` + `graph_store_v2`) | Aceptar `canonical-v1-2026-08+tests-v1` como **baseline candidata** (no cutover). | **NO** |
| **E4 / D-5** adjudicación QA40 | **ninguna** (la familia `D5` es "regeneración de paquetes QA", no la adjudicación) | La hoja QA40 se adjudica **editando 3 YAML en el host** (`:ro` en el runtime por H-5F). No hay endpoint ni UI a propósito: `TP`/`FP`/`COVERAGE_LIMITED`/ground truth/oportunidades/unidades negativas son trabajo humano y la IA no puede tocarlo. | **NO** (y no se debe) |
| **E5** firmas H-1…H-7 (D-2 ya firmado) | `ARTIFACT_VERSION` (target = los cierres) | Aceptación técnica humana de cierres ya cerrados técnicamente. | **NO** |

**Conclusión:** el soporte de gobernanza **ya existe** para E1/E2/E3-A/E5 (UI + endpoint + `decision_store_v2` + `identity_registry` + audit). **No se implementó nada.** E4/D-5 es humano-en-host por diseño.

---

## 2 · UI existente

`factory/ui/mission_control.html` → módulo `factory/ui/js/mission_control/governance.js` — **panel de
Gobernanza**: hace `propose` + `confirm` + `reject` para las familias `D1/D2/D4/AUDIT_EXCEPTION/`
`ARTIFACT_VERSION/APPLICABILITY_MATRIX/SOURCE_*/CORPUS_AUTHORIZATION/PILOT_EXECUTION/EMBED_EXECUTION`.
Usa `X-Identity-Key` (de `state.identityKey`) y el ciclo `GET /governance/state` →
`propose(family_state_hash)` → `confirm(family_state_hash devuelto por el propose)`.

El panel tiene **filas fijas** (`catalog-version`, `golden-dataset`, `prompt-version`,
`matrix-version` — todas `ARTIFACT_VERSION`). **No hay fila dedicada para E1/E2/E3-A.** Añadir una
fila por gate es **1 entrada en el array `PANELS` de `governance.js`** (mismo patrón que las
existentes) — extensión in-place, sin arquitectura nueva. Mientras no se añada, la ruta es el
endpoint (§4).

---

## 3 · Endpoints

| Método | Ruta | Auth | Para |
|---|---|---|---|
| `GET` | `/api/v1/layer9/governance/state` | `X-API-Key` | leer `family_state_hashes` (token para `propose`) |
| `POST` | `/api/v1/layer9/governance/decisions/ARTIFACT_VERSION/propose` | `X-API-Key` | crear la propuesta `agent_proposed` (no autoriza nada) |
| `POST` | `/api/v1/layer9/governance/decisions/{instance_id}/confirm` | `X-API-Key` **+ `X-Identity-Key`** | **firma humana** → `human_confirmed` + evento de auditoría |
| `POST` | `/api/v1/layer9/governance/decisions/{instance_id}/reject` | `X-API-Key` + `X-Identity-Key` | rechazo registrado (append-only, no borra) |
| `GET` | `/api/v1/layer9/decisions` | `X-API-Key` | leer el estado del store |

Body `propose`: `{target_ids, proposed_by_id, decision:"APPROVE", decision_type:"ORIGINAL",
selection_mode:"EXPLICIT_LIST", reason, payload, family_state_hash}`.
Body `confirm`: `{approved_by_display_name, reason, family_state_hash, expected_active_instance_id}`.

**Bodies listos para POST** (targets + payload pre-rellenados; el humano sólo edita veredictos /
`human_decision`): `docs_plan/E_GATES_GOVERNED_PAYLOADS_20260831/{E1,E2,E3A,E5}_propose_body.json`.
El de E1 trae las **77 filas con `verdict:""`** para rellenar.

---

## 4 · Comando exacto (servidor ; claves por variable de entorno, nunca impresas ni guardadas)

```bash
# --- una vez por sesión, en el shell del servidor (NO se guardan en disco) ---
export FACTORY_API_KEY="$(docker exec factory-api printenv FACTORY_API_KEY)"      # la key compartida, desde el .env del contenedor
export IDENTITY_KEY="<PEGAR AQUÍ la clave de identidad de Cesar>"                  # provisionada fuera de banda ; NO se escribe en ningún archivo
BASE=http://localhost:9000/api/v1/layer9

# --- helper: firmar un gate ARTIFACT_VERSION (propose -> confirm) ---
sign_gate() {           # $1 = ruta del *_propose_body.json ya editado por el humano
  local BODY="$1"
  # 1) token de estado de la familia
  local FSH=$(curl -sS -H "X-API-Key: $FACTORY_API_KEY" "$BASE/governance/state" \
              | python3 -c "import sys,json;print(json.load(sys.stdin)['family_state_hashes']['ARTIFACT_VERSION'])")
  # 2) propose (inyecta family_state_hash en el body)
  local PROP=$(python3 -c "import json,sys;b=json.load(open('$BODY'));b['family_state_hash']='$FSH';print(json.dumps(b))" \
              | curl -sS -X POST -H "X-API-Key: $FACTORY_API_KEY" -H "Content-Type: application/json" \
                     -d @- "$BASE/governance/decisions/ARTIFACT_VERSION/propose")
  local IID=$(echo "$PROP" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('proposal_id') or d['decision_instance_id'])")
  local FSH2=$(echo "$PROP" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('family_state_hash') or d['state_hash'])")
  echo "propuesta: $IID"
  # 3) confirm  (FIRMA HUMANA — exige X-Identity-Key)
  curl -sS -X POST -H "X-API-Key: $FACTORY_API_KEY" -H "X-Identity-Key: $IDENTITY_KEY" \
       -H "Content-Type: application/json" \
       -d "{\"approved_by_display_name\":\"Cesar\",\"reason\":\"GATE firmado por Capa 9\",\"family_state_hash\":\"$FSH2\"}" \
       "$BASE/governance/decisions/$IID/confirm" | python3 -m json.tool
}

# --- uso, en orden ---
# E1: primero rellenar los 77 verdict:"" en E1_propose_body.json, luego:
sign_gate docs_plan/E_GATES_GOVERNED_PAYLOADS_20260831/E1_propose_body.json
# E2:
sign_gate docs_plan/E_GATES_GOVERNED_PAYLOADS_20260831/E2_propose_body.json
# E3-A (sólo tras E1 y E2 confirmados):
sign_gate docs_plan/E_GATES_GOVERNED_PAYLOADS_20260831/E3A_propose_body.json
# E5:
sign_gate docs_plan/E_GATES_GOVERNED_PAYLOADS_20260831/E5_propose_body.json

unset IDENTITY_KEY FACTORY_API_KEY
```

`sign_gate` usa el **mismo endpoint autenticado** que la UI. `propose` no autoriza nada;
`confirm` con `X-Identity-Key` es la firma. Ningún `echo`/redirección expone las claves.

---

## 5 · E4 / D-5 — NO tiene comando (humano en host)

```
Archivos (editar en el host ; el runtime los ve :ro por H-5F):
  factory/regulatory/requirement_catalog/qa40_adjudication_sheet.yaml      -> 40 casos: label ∈ {TP, FP, COVERAGE_LIMITED}
                                                                              + human_evidence_anchor + held_out_provenance_tag
                                                                              -> status: SIGNED · adjudicator: "<nombre real>" · adjudicated_at
  factory/regulatory/requirement_catalog/real_corpus_opportunities.yaml    -> enumerar opportunities[] (recall) + negative_units[] (especificidad)
                                                                              -> status: SIGNED · adjudicator · adjudicated_at
  factory/regulatory/requirement_catalog/held_out_technical_corpus.yaml    -> revisar 5 casos -> status: SIGNED · rules_author: "<nombre real ≠ autor del corpus semilla>"
```
La IA NO puede generar ni rellenar ninguno de esos valores. Tras firmar los 3, se puede registrar
la ACEPTACIÓN (no la adjudicación) como un `ARTIFACT_VERSION` con `sign_gate` apuntando a las 3 hojas.

---

## 6 · TABLA FINAL

| GATE | UI | UBICACIÓN | ENDPOINT | COMANDO | ESTADO | ACCIÓN HUMANA |
|---|---|---|---|---|---|---|
| **E1** revisión 77 relaciones H-10 | **PARCIAL** (panel Gobernanza hace propose/confirm ARTIFACT_VERSION ; sin fila dedicada — +1 entrada en `governance.js::PANELS`) | Mission Control → **Gobernanza** (`factory/ui/mission_control.html` · `js/mission_control/governance.js`) | `POST /api/v1/layer9/governance/decisions/ARTIFACT_VERSION/propose` → `.../{iid}/confirm` (`X-API-Key` + `X-Identity-Key`) | `sign_gate .../E1_propose_body.json` (tras rellenar los 77 `verdict`) | **PENDING** (0/77 veredictos ; sin registro) | Rellenar los 77 veredictos `CORRECT/WRONG_NODE/SPURIOUS/AMBIGUOUS` en `E1_propose_body.json` y firmar |
| **E2** aprobación R-PAR | **PARCIAL** (igual que E1) | Mission Control → Gobernanza | `POST .../ARTIFACT_VERSION/propose` → `.../confirm` | `sign_gate .../E2_propose_body.json` | **READY** (insumo `R_PAR_DELTA_V1_V2_20260830.md` ; R-PAR.5 = 4/4 PASS) | Poner `payload.human_decision = APPROVE` (o REJECT) y firmar |
| **E3-A** aceptación canonical CLEAN | **PARCIAL** | Mission Control → Gobernanza | `POST .../ARTIFACT_VERSION/propose` → `.../confirm` | `sign_gate .../E3A_propose_body.json` | **READY** (manifest `CANDIDATE_BASELINE_MANIFEST_20260831.json`) — **bloqueado hasta E1+E2 confirmados** | Confirmar que la base limpia (RW-0012 258 vs 595) es la deseada ; poner `human_decision = APPROVE` ; firmar. NO es cutover. |
| **E4 / D-5** adjudicación QA40 | **NO** (a propósito) | — (archivos `:ro` en runtime) | **NO** (a propósito) | — (editar 3 YAML en el host, §5) | **PENDING** (QA40 40/40 PENDING ; opportunities/negative_units vacíos ; held_out DRAFT_UNSIGNED) | Adjudicar y firmar las 3 hojas en el host (la IA no puede) ; opcional: registrar aceptación con `sign_gate` |
| **E5** firmas H-1…H-7 (D-2 ya firmado) | **PARCIAL** | Mission Control → Gobernanza | `POST .../ARTIFACT_VERSION/propose` → `.../confirm` | `sign_gate .../E5_propose_body.json` | **READY** (D-2 ya en `ARTIFACT_VERSION-2026-019/020`) | Revisar cierres H-1…H-7 ; poner `human_decision = APPROVE` ; firmar |

---

## 7 · QUÉ DEBE HACER CAPA 9 PARA CERRAR E1→E5 Y PODER SEGUIR CON E6/D-6

```
0.  En el shell del servidor:
       export FACTORY_API_KEY="$(docker exec factory-api printenv FACTORY_API_KEY)"
       export IDENTITY_KEY="<tu clave de identidad>"            # nunca a disco
       BASE=http://localhost:9000/api/v1/layer9 ; y pegar la función sign_gate (§4)

1.  E1 — abrir docs_plan/E_GATES_GOVERNED_PAYLOADS_20260831/E1_propose_body.json
       Rellenar los 77 "verdict": "" con CORRECT | WRONG_NODE | SPURIOUS | AMBIGUOUS
       (usar docs_plan/E1_H10_RELATION_REVIEW_PACKET_20260831.md como hoja de trabajo).
       Recalcular verdict_set_sha256 (sha256 de la lista verdicts serializada canónica).
       Ejecutar:  sign_gate docs_plan/E_GATES_GOVERNED_PAYLOADS_20260831/E1_propose_body.json
       -> queda ARTIFACT_VERSION-2026-0XX con los 77 veredictos + firma Cesar + evento de auditoría.

2.  E2 — en E2_propose_body.json poner "human_decision": "APPROVE" (o "REJECT" y parar).
       Ejecutar:  sign_gate .../E2_propose_body.json

3.  E3-A — sólo si E1 y E2 quedaron human_confirmed.
       En E3A_propose_body.json poner "human_decision": "APPROVE" (aceptas la base limpia).
       Ejecutar:  sign_gate .../E3A_propose_body.json
       (Esto NO activa producción, NO flipa _EXT_VER/_CANON/_GRAPH.)

4.  E4 / D-5 — en el host, adjudicar y firmar:
       qa40_adjudication_sheet.yaml (40 casos)  +  real_corpus_opportunities.yaml  +  held_out_technical_corpus.yaml
       (status: SIGNED + adjudicator/rules_author reales). La IA NO puede hacerlo.
       Después, la máquina calcula QA40_SAMPLE_PRECISION / REAL_RECALL / REAL_SPECIFICITY con metric_envelope.
       Nota de alineación: 1/40 direccionamiento (ADJ-34140454ec) se re-resuelve de forma determinista
       contra la versión candidata tras E3-A ; el conjunto de 40 casos NO cambia ; SIN remuestreo.

5.  E5 — revisar los cierres H-1…H-7 ; en E5_propose_body.json poner "human_decision": "APPROVE".
       Ejecutar:  sign_gate .../E5_propose_body.json

Con E1..E5 = human_confirmed:
  E6 (commit gobernado) — Capa 9 define el alcance exacto del commit
     (ver docs_plan/PAQUETE_GATES_HUMANOS_POST_RPAR_20260831.md §5) ,
     añade .gitignore para los stores generados, hace stage archivo-por-archivo,
     revisa git diff --cached, y commitea (autorización explícita de Capa 9).
     -> limpia los 4 guards store==git-HEAD.
  Post-commit: pytest factory/tests/  -> NEW_REGRESSIONS=0 esperado ; LEDGER_GUARD_FAILURES=0.
  D-6 (qualification) — decisión humana autenticada tras E4(D-5)+E5+E6 y con E1..E3-A resueltos.

Producción (separada de D-6): incluso con D6=QUALIFIED, PRODUCTION_ENABLEMENT sigue NOT_ENABLED
hasta decisión humana específica -> luego CUTOVER (flip) -> re-derivación limpia -> post-cutover regression.
```

**Ningún paso lo ejecuta un agente.** E4/D-5 no es falsificable ni rellenable por IA.
`decisions_v2.jsonl` sólo se toca por `propose`/`confirm`, nunca a mano.
