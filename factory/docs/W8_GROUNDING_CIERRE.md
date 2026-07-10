# W8 Grounding — Bloque 1: CIERRE (2026-07-10)

Alcance ejecutado: `factory/docs/W8_GROUNDING_PLAN.md` §Bloque 1. Aprobado
por Cesar en chat ("apruebo arrancar W8 Grounding Bloque 1"), ejecución con
autonomía técnica pre-autorizada, sin nuevas rondas de planificación.
Reutiliza el pipeline W7/W7.1 sin ningún cambio de código.

## 0. Fix de seguridad previo (gate de entrada, cerrado antes de Bloque 1)

La contraseña temporal de Basic Auth de Mission Control (rotada en
`beb637e`) había quedado expuesta en texto claro en una sesión posterior.
Rotada de nuevo en esta sesión: hash bcrypt actualizado en `Caddyfile`,
reinstalado, Caddy reiniciado. Verificado: password vieja (expuesta) →
`401`; password nueva → `200`; sin credenciales → `401`; operación real
autenticada (Basic Auth + `x-api-key`, `/api/v1/status/full`) → `200`;
`verify_installed.sh` PASS 4/4; `factory_selfcheck.sh` PASS=4 FAIL=0;
`aria-*`/`hotelbot-*` sin tocar. La contraseña nueva **no se publicó en
ningún momento** (ni en chat ni en este documento): se entregó a Cesar en
un archivo fuera de git (`~/.secrets/`, mode 600, borrado por Cesar tras
copiarla). `.secrets/` añadido a `.gitignore`.

## 1. Casos seleccionados y justificación

De los 5 casos en `case_memory/cases.jsonl` (1 ya usado en W7 Fase D:
`openfda_enforcement:D-0554-2026`), se descartó el par
`D-0517-2026`/`D-0518-2026` por ser casi duplicados (mismo producto BD
PurPrep, mismo texto de `reason`, mismos tags — no aporta señal nueva
sobre generalización). Seleccionados:

| Caso | Producto | Misión | Motivo |
|---|---|---|---|
| `openfda_enforcement:D-0546-2026` | Cimzia (certolizumab pegol), jeringas precargadas — UCB Biosciences | `oos_hplc_investigator` (misma misión que W7 Fase D) | Producto/narrativa distintos al caso ya probado (biológico vs. sólido oral); confirma n=2 dentro de la misma misión |
| `openfda_enforcement:D-0525-2026` | Oasis Tears PF, colirio estéril — Oasis Medical, Inc. | `lab_qc_project` (**misión distinta**, requisito de cierre) | Narrativa distinta: hallazgo de inspección FDA en un tercero (Excelvision), "abundancia de precaución", no defecto propio declarado |

## 2. Resultado real de cada ejecución

`POST /api/v1/layer9/case-memory/{case_id}/analyze`, `trigger.mode=manual`,
`requested_by="Claude (autorizado por Cesar, W8 Bloque 1)"`.

| Caso → misión | HTTP | Latencia | Status final |
|---|---|---|---|
| D-0546-2026 → oos_hplc_investigator | 200 | 625.9s (~10.4 min) | v1 `accepted` |
| D-0525-2026 → lab_qc_project | 200 | 329.5s (~5.5 min) | v1 `accepted` |

Sin `format_retry` en ninguno (formato correcto al primer intento).
Persistencia inmutable:
`regulatory/case_analyses/oos_hplc_investigator/openfda_enforcement__D-0546-2026/v01.json`,
`regulatory/case_analyses/lab_qc_project/openfda_enforcement__D-0525-2026/v01.json`
(fuera de git, mismo patrón que `factory/validation/`).

## 3. Routing (determinista, W6.4)

Ambos casos rutearon a `qa_oos_profile` (agente por defecto para
`drug_recall`: ni `reason` ni `tags` contienen señales de integridad de
datos ni HPLC — solo `sterility`). En `lab_qc_project` el agente existe en
el diseño de la misión (`recommended_agent_in_mission: true`), igual que en
`oos_hplc_investigator` — el routing no depende de la misión, como espera
el diseño (perfil compartido `profiles/qa_profiles.yaml`).

## 4. Claims y flags

| Caso | Supported | Partially | Unsupported | Unverifiable | Flags | Verifier 2.2 findings |
|---|---|---|---|---|---|---|
| D-0546-2026 | 1 | 2 | 0 | 3 | `[]` | `[]` |
| D-0525-2026 | 2 | 2 | 0 | 2 | `[]` | `[]` |

Cero `unsupported`, cero flags en ambos. Los dos declaran correctamente con
`[SE]` lo que no pueden evaluar (p. ej. "no hay evidencia de que el
producto del caso esté en el alcance del laboratorio"), y citan
`[E: id]`/`[REF: norma]` de forma trazable. Sin contaminación cruzada entre
casos ni con la misión equivocada: el análisis de `lab_qc_project` cita
correctamente sus propios agentes (`capa_inherited`, `qa_oos_profile`,
`integrity_lims_profile`, `hplc_data_review_agent`) y su propio dossier
(`exists: false, total_docs: 0`), no los de `oos_hplc_investigator`.

## 5. corpus_sufficiency

Ambos: `"partial"` — disponible: 21 CFR 211.160/165/192/194 y 21 CFR
820.198 (texto público); pendiente: FDA OOS Guidance 2022 completa. Fuente:
`profiles/qa_profiles.yaml` (perfil compartido, independiente de la
misión). Confianza resultante: `"media"` en los dos.

## 6. Auditoría

Cadena: 315 → 317 entradas tras generación (+2 `case_analysis_generated`)
→ 319 tras decisión (+2 `case_analysis_decision`, `decided_by: Cesar` en
ambos). 0 `hash_errors` nuevos (único fork sigue siendo el histórico ya
aceptado). `cases.jsonl` intacto; `factory/validation/` sin archivos
tocados — el pipeline no tocó dossier ni memoria de casos, como exige el
criterio de cierre del plan.

## 7. Regresiones, suite y selfcheck

`factory_selfcheck.sh` → **PASS=4 FAIL=0** en las 3 pasadas de la sesión
(pre, post-generación, post-decisión). Pytest: **441 passed** en las 3 —
mismo número que la línea base pre-sesión, cero regresiones.
`aria-*`/`hotelbot-*`: `Up`/`healthy` sin cambios en toda la sesión.

## 8. Decisión humana

Cesar, en chat (2026-07-10): **"Acepto los dos: D-0546 accept, D-0525
accept."** Registrado vía `POST /case-memory/{case_id}/analysis/decision`
con `decided_by="Cesar"` (nombre real, no firma electrónica — mismo patrón
que W7 Fase D). `accept` únicamente marca el registro versionado y audita:
no toca dossier, no toca `cases.jsonl`, no entra a ningún documento GMP
(mismo contrato que W7 Fase A, decisión 5).

## 9. Conclusión sobre generalización más allá de n=1

**El pipeline generaliza en esta muestra ampliada (n=3 casos, 2
misiones).** Los 3 análisis (el de W7 Fase D + estos 2) comparten el mismo
patrón sano: 0 `unsupported`, 0 flags, confianza `media`,
`corpus_sufficiency: partial` declarada explícitamente, y disciplina
estricta de etiquetado `[E]/[SE]/[REF]` incluyendo uso correcto de `[SE]`
para admitir lo que no puede evaluar. El caso cruzado a `lab_qc_project`
confirma que el agente heredado (`qa_oos_profile`) razona correctamente
sobre el contexto de una misión distinta sin arrastrar datos de la misión
anterior.

**Limitaciones de esta muestra (n=3):** un solo modelo
(`qwen2.5:7b-instruct-q4_K_M`), un solo agente ejercitado de los 3 del
routing — `integrity_lims_profile` y `hplc_data_review_agent` no tienen
ningún caso real en memoria que dispare sus señales (todos los 5 casos
disponibles comparten `reason` de esterilidad, sin señales de integridad
de datos ni HPLC). El modo revisión (`request_changes`, W6.5.1) no se
ejercitó en esta ronda — las 2 decisiones fueron `accept` directo. La
calibración de qwen 7B sobre guidance de borrado vs. reemplazo positivo
(hallazgo de W7 Fase D §4) sigue sin repetirse.

## 10. Estado de Bloque 1

**CERRADO.** Cumple los 5 criterios de `W8_GROUNDING_PLAN.md`: ≥2 casos
nuevos analizados end-to-end (draft → decisión humana) ✓; ≥1 en misión
distinta ✓; verificador v2.2 sin falsos positivos nuevos ✓; sin cambios a
dossier ni memoria de casos ✓; `factory_selfcheck.sh` PASS=4 FAIL=0 y
cadena de auditoría íntegra tras cada ejecución ✓.

## 11. Siguiente paso

Bloque 2 (conectar análisis de caso aceptado → dossier) y Bloque 3
(segunda fuente regulatoria) — ambos gated, requieren aprobación explícita
de Cesar antes de cualquier código (mismo patrón que este plan).
