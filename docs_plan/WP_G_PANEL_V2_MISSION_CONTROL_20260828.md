# WP-G — PANEL DEL ANALIZADOR V2 EN MISSION CONTROL (solo lectura)

**Fecha:** 2026-08-28 · **Autoridad:** Capa 9 = Cesar
**Baseline de código:** `fix/clon-local-validacion` @ `2bc8d97` (WP-F cerrado).
**Motiva:** D-6 (la UI existente tiene 23 módulos JS, 0 referencias a `/api/v1/v2-analyzer/*`).

---

## Qué entrega WP-G

Un módulo JS **añadido a la UI existente** (no una segunda UI) que consume los **6 endpoints GET ya
publicados** en `factory/api/routes/v2_analyzer.py`. **Sin backend nuevo.**

| Archivo | Cambio |
|---|---|
| `factory/ui/js/mission_control/v2_analyzer_view.js` | **NUEVO** — `refreshV2Analyzer()` + `openV2Run(runId)` |
| `factory/ui/mission_control.html` | +1 botón `data-v="v2analyzer"` en `#nav` · +1 `<section id="v-v2analyzer">` |
| `factory/ui/js/mission_control/refresh.js` | +import · +`TITLES.v2analyzer` · +`if(v==='v2analyzer') await refreshV2Analyzer()` |
| `factory/ui/js/mission_control/main.js` | +import · +`openV2Run` en `Object.assign(window, …)` |
| `factory/tests/test_wp_g_mission_control_panel.py` | **NUEVO** — 6 tests (estáticos + funcionales) |

---

## Read-only estricto (gate WP-G)

- **0 llamadas de escritura.** El módulo solo hace `fetch(V2 + path, {headers: headers()})` — `GET` por
  defecto. Verificado por test: ningún `method: 'POST'|'PUT'|'PATCH'|'DELETE'` en el archivo.
- **El front NO replica** adjudicación, riesgo, gobernanza ni cambio de estado. Banner visible:
  *"Panel de solo lectura. La adjudicación y toda decisión GMP se hacen en «Revisión humana» /
  «Gobernanza». Este panel no muta ningún estado."*
- El router V2 es 100% GET → una operación de escritura devuelve 404/405 (verificado por test).

---

## Muestra explícitamente (gate WP-G: "si no, la UI reintroduce la confusión que WP-B elimina")

| Dato | Fuente (endpoint existente) | Dónde en el panel |
|---|---|---|
| **Fingerprint de la corrida** (WP-A) | `GET /runs/{id}` → `audit_metadata.input_config_fingerprint` + `findings_fingerprint` + `run_attestation.active_engine` / `routing_source` | tarjeta «Fingerprint de la corrida (WP-A)» |
| **Adecuación de extracción por documento** (WP-B) | `GET /runs/{id}` → `audit_metadata.adequacy_verdicts` (por doc) + `coverage_would_degrade` + `analysis_coverage_mode` (OBSERVE) | tarjeta «Adecuación de extracción por documento» — tabla doc → verdict; would_degrade informativo con nota «0 supresiones» |
| **`evidence_basis` por finding** (WP-B) | `GET /runs/{id}/findings` → cada finding con `evidence_basis ∈ {PRESENCE, ABSENCE_DEPENDENT, INDETERMINATE}` | tarjeta «evidence_basis» — desglose por base + tabla de findings (clase, subtype, doc, pág, evidence_basis, machine_state, human_state) |
| Marcas / revisión humana | `GET /runs/{id}` → `manifest.mark` / `qa_status`, `human_review_state` | tarjeta «Estado» — `MACHINE GENERATED`, `NOT_QA_APPROVED`, `all_unreviewed`, `forbidden_states_present` |

Escape de HTML (`esc()`) en todo valor de API antes de `innerHTML` — mismo criterio que el resto de la UI.

---

## Endpoints consumidos (los 6, sin inventar ninguno)

```
GET /api/v1/v2-analyzer/runs                     -> lista (refreshV2Analyzer)
GET /api/v1/v2-analyzer/runs/{run_id}            -> manifest + audit_metadata + human_review_state (openV2Run)
GET /api/v1/v2-analyzer/runs/{run_id}/findings   -> findings por clase, con evidence_basis (openV2Run)
GET /api/v1/v2-analyzer/runs/{run_id}/evidence      \
GET /api/v1/v2-analyzer/runs/{run_id}/remediation    > enlazados desde el detalle; el router ya los sirve
GET /api/v1/v2-analyzer/runs/{run_id}/report        /
```

`test_wp_g_...` verifica estáticamente que el módulo no llama a ningún path fuera de `/runs*`.

---

## Estado

`MISSION_CONTROL_V2 = API_VISIBLE=YES · UI_VISIBLE=YES` (antes `UI_VISIBLE=NO`). D-6 cerrado.

El panel es **visualización**; no cambia `PRODUCTION_ENABLEMENT` / `REGULATORY_COMPLIANCE` /
`CORPUS_READY` ni ningún estado de gobernanza.

---

## Rollback

Eliminar `v2_analyzer_view.js` + `test_wp_g_...` y revertir las 3 ediciones aditivas (botón nav,
sección, import + dispatch). Sin efecto sobre el resto de la UI ni sobre el backend.

---

*Aditivo. Sin backend nuevo. Sin llamadas de escritura. Sin segunda UI. Regresión: 2891 passed / 5 EXC
aceptadas / exit 1 (NEW_REGRESSION_FAILURES = 0).*
