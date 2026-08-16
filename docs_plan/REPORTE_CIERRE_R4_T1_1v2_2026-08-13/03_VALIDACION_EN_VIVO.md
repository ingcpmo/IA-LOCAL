# 03 — Validación en Vivo

Todas las verificaciones de esta sección se ejecutaron en vivo durante la
elaboración de este reporte (2026-08-13). Ningún comando invocó un LLM ni
disparó Tier-1.

## Endpoint de directivas en `/openapi.json` vivo

```
curl -s http://localhost:9000/openapi.json | python3 -c \
  "import json,sys; d=json.load(sys.stdin); [print(p) for p in d['paths'] \
   if 'remediation' in p or 'directive' in p]"
```

Salida real:

```
/api/v1/layer9/remediation/directives
/api/v1/remediation-packages/{project_id}/{package_id}/{version}
/api/v1/remediation-packages/{project_id}/{package_id}/{version}/exceptions/{change_id}
/api/v1/remediation-packages/{project_id}/{package_id}/{version}/medium-risk-batch
/api/v1/remediation-packages/{project_id}/{package_id}/{version}/decision
```

Los 5 endpoints que el panel de adjudicación de Mission Control
(`remediation.js`, commit `0796bb9`) consume ya existían en producción antes
de este commit — confirma la afirmación del commit de "sin backend nuevo".

## Health `factory-api`

```
curl -s http://localhost:9000/health
→ {"api":"ok","service":"factory","timestamp":1786662076}
```

`docker ps` confirma los 4 contenedores relevantes arriba en el momento de
la verificación:

```
gmp-api        Up About a minute
gmp-postgres   Up About a minute (healthy)
gmp-redis      Up About a minute (healthy)
factory-api    Up 2 minutes
```

## Panel UI

Verificado por código, no por clic en navegador (esta corrida es
documentación, no ejecución de UI — ver restricción explícita de la
instrucción de cierre):

- `factory/ui/mission_control.html` (+33 líneas) monta el panel.
- `factory/ui/js/mission_control/remediation.js` (+281 líneas, nuevo)
  implementa la lógica del panel de adjudicación.
- `factory/ui/js/mission_control/main.js` (+3) y `refresh.js` (+12/-1)
  cablean el panel al ciclo de refresco existente.

**Pendiente declarado:** clic real de Cesar en el panel — no verificado
visualmente en esta auditoría.

## Decisiones RECORDED

`factory/layer9/decisions/decisions_v2.jsonl` (213 líneas totales al momento
de esta auditoría). Las dos últimas instancias son las persistidas por el
commit `99f36c3`:

```
PILOT_EXECUTION-2026-017  agent_proposed    2026-08-12T21:17:09.751629+00:00
PILOT_EXECUTION-2026-018  human_confirmed   2026-08-12T21:17:21.223949+00:00  (approved_by_id: cesar)
```

Ambas apuntan a `RW-0005`, `authorizes_corpus: false`,
`authorizes_baseline: false` — explícito en el payload: esta firma **no**
autoriza corpus ni promueve `FORMAL_BASELINE_READY`.

`w5_human_decisions.jsonl` (7 líneas): D1–D5 más D6 y una corrección de D1
(cambio de `reverification_cadence_months` de 1 a 3, con
`correction_reason` explícito). D6 (`D6_pdf_generation_policy`) es la última
entrada, `APPROVE`, `approved_by: cesar`, `decision_origin:
human_confirmed`, `recorded_at: 2026-08-13T20:53:34Z` — corresponde al
commit `d224b24` auditado en esta corrida.

## Release no expuesto / no alcanzado

```
grep -rn "create_release_record" factory/services/candidate_document_generator.py factory/api/routes/layer9.py
→ sin coincidencias (exit 1)

grep -rln "create_release_record\|release_record\|/release" factory/ui/js/mission_control/
→ gmpai_artifacts.js  (línea 101: comentario "effective/released", no invocación)
→ remediation.js       (línea 167: comentario explícito)
```

Contenido de la única línea relevante en `remediation.js`:

```
Nunca ejecuta ni libera nada -- create_release_record() no está conectado
```

Confirma, por código y no solo por mensaje de commit, que el panel de
adjudicación de remediación nunca invoca `create_release_record()` — ni
directamente ni a través de ningún módulo de UI de Mission Control. No hay
release expuesto ni alcanzable desde el flujo auditado en R4-T1.1v2.
