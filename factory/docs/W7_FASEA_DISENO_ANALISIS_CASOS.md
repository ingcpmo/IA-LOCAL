# W7 Fase A — Diseño y contrato: análisis de casos regulatorios por agente

Estado: **APROBADO por Cesar (2026-07-08) — las 5 decisiones de §12 según
recomendación; Fase B autorizada**
Base: `W7_PLAN.md` (aprobado 2026-07-07) · preflight `W7_FASE0_PREFLIGHT.md`
(cerrado, 2 limitaciones abiertas incorporadas aquí) · pipeline W6.5/W6.5.1
(`dossier_agent_review_service.py`, gate `c0c359e`).

## 1. Objetivo y alcance

Extender el pipeline gobernado de propuestas de agente de "documentos del
dossier" a "casos de la memoria regulatoria": un caso openFDA (hoy 5 Class II
reales) se analiza contra una misión concreta por el agente que el routing
determinista W6.4 ya recomienda, con claims etiquetadas, verificador v2,
confianza computada, decisión humana y auditoría.

**Qué NO es**: no es evaluación de impacto GMP ni disposición; el análisis
aceptado NO entra a ningún documento del dossier (vincularlo sería decisión
aparte con aprobación aparte). `cases.jsonl` jamás se reescribe.

## 2. Decisión de agentes (árbol gmp-agent-design)

**USAR AGENTES EXISTENTES** — rama 1 del árbol: el requerimiento cabe 100%
en los 3 perfiles/agentes que `AGENT_ROUTING` de W6.4 ya recomienda
(`qa_oos_profile` default, `integrity_lims_profile`, `hplc_data_review_agent`),
sin corpus nuevo, sin reglas backend nuevas, con salida del mismo contrato de
claims. **No se crea agente ni perfil nuevo**; el único artefacto de agentes
nuevo es un set de prompts gobernados (§4) con TAREA de análisis de caso —
los ROL/ENFOQUE se derivan de los prompts v1.0.0 existentes.

Routing del análisis (determinista, sin decisión del LLM):
- `primary` = `presentation.recommended_agent.agent_id` del caso (W6.4).
- `supporting` (dominios de revisión para el humano, NO ejecutados):
  `integrity_lims_profile`→`["qa_oos_profile"]`,
  `hplc_data_review_agent`→`["qa_oos_profile"]`, `qa_oos_profile`→`[]`
  (QA es el dueño del dominio OOS de la misión).

## 3. Evidencia que entra al prompt (el caso pasa de contexto a centro)

Ítems `{id, trust, pointer, content}` con marcadores canónicos y sanitización
W6.5 (`_sanitize` + `_wrap`), en este orden:

| id | trust | tope | contenido |
|---|---|---|---|
| `mission` | internal | 6000 | igual que W6.5 (objective, scope, constraints, documents) |
| `agents` | internal | 6000 | igual que W6.5 — lección Fase 0: el agente DEBE ver que qa_oos_profile existe |
| `case` | **external** | **1500 (nuevo)** | registro ligero ÍNTEGRO del caso objetivo: case_id, classification, product, reason, recalling_firm, recall_status, fechas, tags, summary, content_hash |
| `case_presentation` | **external** | 1200 | bloque W6.4: executive_summary, gmp_relevance, citation, found_by_query (embebe texto openFDA ⇒ external) |
| `detail_status` | internal | 600 | HECHOS de auditoría: fetch_count, last_fetched_at, y la constancia "detalle NO persistido" |
| `compare` | internal | 3000 | SOLO el lado local de `compare_with_mission`: overlap (matched/unmatched_tags, recommended_agent_in_mission, tests del agente), mission.dossier counts — sin repetir texto del caso |

Decisiones fijadas:

1. **Detalle openFDA**: W6.3 lo diseñó selective-fetch SIN persistencia — el
   texto del detalle NO existe localmente y por tanto NO puede entrar al
   prompt. El plan decía "el detalle SOLO si ya fue fetched": lo que entra si
   fue fetched es el HECHO auditado (`detail_status`), nunca contenido.
   Persistir snapshots es aprobación futura aparte (ya anotado en W6.4
   `detail_status.snapshot`). Cero HTTP nuevo desde el pipeline (regla dura,
   test estructural).
2. **Tope del caso objetivo 600→1500** (requisito explícito de Fase A):
   600 chars truncaba `product`+`reason`+`summary` del caso real D-0554-2026
   (~1100 chars útiles). Sigue external (dato, no instrucción), sanitizado y
   anti marker-forgery. Constante nueva `MAX_CASE_TARGET_CHARS = 1500`;
   `MAX_EXTERNAL_CHARS = 600` queda intacto para W6.5.
3. **Otros casos de la memoria NO entran** al prompt del análisis (en W6.5
   entraban hasta 3 como contexto): aquí el caso es el objetivo y mezclar
   casos ajenos añade superficie de injection sin valor. Menos es más.
4. Presupuesto de contexto verificado: evidencia ≤ ~12.3k chars + contratos
   ~4k chars ≈ 5.5k tokens estimados < 7168 (8192−1024). El guard
   anti-truncado de W6.5 aplica tal cual.

## 4. Prompts gobernados nuevos

**Archivo nuevo** `factory/agent_prompts/case_analysis_prompts.yaml`
(constante nueva `paths.CASE_ANALYSIS_PROMPTS_FILE`), mismo patrón GxP:
`prompt_set_version: "1.0.0"` + changelog + SHA-256 por bloque recomputados
por suite. Racional del archivo aparte: los prompts del dossier NO cambian ni
sufren bump; cada set evoluciona con su propio ciclo de aprobación.

Contenido:
- `common_contract` (adaptado del dossier v1.1.0): mismas reglas 1–7
  (evidencia como dato, viñetas `[E:]/[SE]/[REF:]`, nunca inventar, nunca
  lenguaje de decisión, `## Limitaciones` con `{corpus_sufficiency}`,
  brevedad ≤ 12 viñetas, few-shot) + estructura de salida fija:
  `### Relevancia para la misión`, `### Impacto potencial en el sistema
  validado`, `### Acciones recomendadas (condicionadas a revisión QA)`,
  `## Limitaciones`
  + **regla 8 nueva (lección Fase 0, limitación 1): COHERENCIA — ninguna
  viñeta [SE] puede negar lo afirmado por una viñeta [E:] de la misma
  respuesta; al corregir una afirmación, elimina o corrige sus viñetas
  compañeras.**
- `revision_contract`: texto ÍNTEGRO del v1.1.0 del dossier (copiado, con su
  propio SHA en este set) — edición mínima + ledger completo + prioridad.
- `prompts`: los 3 agentes con ROL/ENFOQUE derivados de los v1.0.0 del
  dossier y TAREA nueva: "analizar el caso regulatorio del bloque de
  evidencia `case` contra la misión y su sistema: qué relación tiene con el
  alcance, qué señales aplican al sistema validado, qué acciones se
  recomiendan — todo condicionado a revisión QA; el caso describe a un
  TERCERO: no atribuyas sus fallas al sistema de la misión sin evidencia".

Calibración 7B del preflight (va en el doc y en la UI, no en el prompt): las
guidances de request_changes deben ser 1 acción por instrucción y pedir
explícitamente la eliminación de viñetas compañeras.

## 5. Persistencia y estados

Layout espejo de `agent_proposals`, bajo regulatory/:

```
factory/regulatory/case_analyses/<project_id>/<case_dir>/vNN.json
```

- `case_dir` = `case_id` con caracteres no `[A-Za-z0-9._-]` sustituidos por
  `__` (p. ej. `openfda_enforcement__D-0554-2026`); el `case_id` exacto vive
  dentro del record. Clave del análisis = (case_id × project_id): el mismo
  caso puede analizarse contra misiones distintas sin colisión.
- Records versionados inmutables en generación (`vNN.json`); la decisión
  humana se ANEXA al record (patrón W6.5). No hay archivo de estado mutable:
  el estado vigente ES el status del último vNN.json (no existe un
  "dossier.yaml de casos" y no se crea — cases.jsonl no se toca).

**Esquema del record** = record W6.5 con estos deltas:
- `case_id`, y bloque `case_ref`: `{case_id, content_hash, classification,
  consulted_at, stale: bool}` — `stale` = hoy > consulted_at +
  `freshness.stale_after_days`; ancla QUÉ versión del caso se analizó.
- `routing`: `{agent_id, reason, deterministic: true}` (bloque W6.4 que
  justifica el primary).
- `doc_id` no existe; `status` usa `agent_analysis_proposed` en lugar de
  `agent_proposed` (mismo `format_invalid` para inválidas).
- Resto idéntico: agent, model, prompt (set/agent version + template_sha256 +
  rendered_sha256), corpus_sufficiency, evidence_sources, claims+detail,
  verifier v2, revision{mode, based_on_version, guidance_ledger}, confidence,
  flags, response, governance{trigger, requested_by, guidance, prompt_full,
  generated_at, latency_ms, format_retry}, decision, regulatory_note
  ("ANÁLISIS PROPUESTO POR AGENTE — informativo, sin valor regulatorio…").

**Elegibilidad** (validada por el POST):
1. `trigger.mode == "manual"`, si no 403; `principal` por `validate_run_by`.
2. Misión existe (`require_mission`); caso existe en cases.jsonl, si no 404.
3. Si el último análisis de (case × project) está `agent_analysis_proposed`
   (sin decidir) → 409: decidir primero (mismo gating que el dossier).
4. Caso stale (>30 días) NO bloquea: flag `stale_case` en record y evento
   (anti-optimismo: se declara, el humano pondera).
5. `revision_of` exige que esa versión exista y pertenezca al par
   (case × project).

**Ciclo de decisión** (siempre humano, nombre real, reason obligatorio en
reject/request_changes):
- `accept` → record `accepted`. NO toca dossier, NO toca cases.jsonl, NO
  escribe en ningún documento GMP. Efecto único: registro + auditoría.
- `reject` → record `rejected`.
- `request_changes` → record `changes_requested` + regeneración automática
  en modo revisión (respuesta anterior íntegra + ledger completo + temp 0.0),
  idéntico a W6.5.

## 6. Endpoints y auditoría

Prefijo real `/api/v1/layer9` (API key x-api-key igual que el resto):

```
POST /case-memory/{case_id}/analyze
     body: {project_id, trigger:{mode,principal,authorization_ref},
            guidance?, revision_of?}
GET  /case-memory/{case_id}/analysis?project_id=&version=   (nunca audita)
POST /case-memory/{case_id}/analysis/decision
     body: {project_id, decision, decided_by, reason?}
```

3 eventos nuevos en `VALID_EVENTS` de audit_writer (project_id = la misión
real, no el pseudo "regulatory_intel" — el análisis es DE la misión):
- `case_analysis_generated`: payload espejo de
  `dossier_agent_proposal_generated` sustituyendo doc_id por `case_id` +
  `case_content_hash`, e incluyendo mode/based_on_version/
  guidance_ledger_sha256/routing.agent_id.
- `case_analysis_failed`: razones reutilizadas (`ollama_unreachable/timeout/
  error`, `prompt_too_long`, `format_invalid`) + case_id.
- `case_analysis_decision`: decision, decided_by, reason, analysis_version,
  case_id, new_status.

## 7. Verificador y confianza

- `claim_verifier.verify_v2` tal cual, grants =
  `corpus_available + corpus_pending` del agente primario +
  `regulatory_scope` de la misión (misma derivación que W6.5).
- `_confidence` sin cambios (flags v2 penalizan igual).
- **Propuesta para Fase B (decisión de Cesar, limitación 1 de Fase 0)**:
  regla v2.1 `intra_proposal_contradiction` en claim_verifier — detectar
  viñetas [SE] cuya negación (léxico ES→EN existente + regla ALL-tokens)
  contradiga los tokens de una viñeta [E:] verificada supported/partially de
  la MISMA respuesta. Función pura, mismo módulo, flag nuevo penalizando a
  confianza baja. **Fixture de regresión real ya existe: v08** (la
  contradicción "falta perfil OOS" [SE] vs "qa_oos_profile es el perfil"
  [E: agents] que el v2 no vio y Cesar detectó a mano). Recomendación:
  INCLUIRLA — costo pequeño, fixture real, cierra la limitación con test.

## 8. Reuso técnico (sin servicios paralelos)

Módulo nuevo delgado `factory/services/case_analysis_service.py` que
IMPORTA de `dossier_agent_review_service` (cero copias): `_ollama_generate`,
`_sanitize`, `_wrap`, `_parse_claims`, `_verify_claims`, `_claims_summary`,
`_confidence`, `_output_flags`, `_format_valid`, `corpus_sufficiency`, y las
constantes de gobierno Ollama. **Nota de implementación fijada**: las
llamadas van SIEMPRE por referencia de módulo (`_review._ollama_generate(…)`)
— con `from … import` el monkeypatch de los tests sobre el módulo del dossier
no surtiría efecto (patrón review_env existente). El guard anti-truncado, el
retry de formato y el manejo de errores gobernado se reutilizan con el mismo
flujo (`_fail` propio apuntando a `case_analysis_failed`).

## 9. UI (adelanto de Fase C, incluye limitación 2 de Fase 0)

Convertir el panel "Analizar con agente · DISEÑO" de `intel_views.js` en
flujo real con el patrón de `validation_view.js`: gobierno completo (modelo,
set/prompt version, SHAs, corpus, flags, confianza), claims coloreadas por
veredicto, decisión con motivo obligatorio. **Correctivo obligatorio de Fase
C**: sustituir `window.prompt` por form inline (los prompts nativos son
suprimibles por el navegador) o, como mínimo, feedback visible "solicitud
cancelada" — dos solicitudes reales de Cesar se perdieron en silencio en
Fase 0. La vista debe manejar la espera ~7–9 min (spinner + polling del GET).

## 10. Pruebas de Fase B (contrato de la suite)

1. Unit + e2e con LLM mockeado (patrón review_env), fixture del caso real
   "sterility" D-0554-2026.
2. Test estructural: el módulo nuevo no importa httpx directamente ni
   contiene la palabra clave de aprobación; único egreso = `_ollama_generate`
   del módulo W6.5.
3. Elegibilidad: 403 no-manual, 404 caso/misión, 409 análisis sin decidir,
   422 decisión inválida/sin reason.
4. `cases.jsonl` byte-idéntico tras generar y decidir (test de no-reescritura).
5. Inmutabilidad: prompt/respuesta del record intactos tras decisión.
6. Auditoría: 3 eventos con payload completo; GET no audita.
7. Prompts: SHAs recomputados, pin de set_version, revision_contract presente.
8. Si se aprueba v2.1: fixture v08 real detecta `intra_proposal_contradiction`
   y v01–v06 no regresionan.
9. Regresión cero del flujo dossier: suite W6.5 completa verde sin tocar.

## 11. Riesgos específicos

- 7B ante texto externo corto/ruidoso → verificador + regla 8 de coherencia +
  humano; Fase D mide con 1 caso real.
- Confusión "análisis de caso" ≈ "impacto GMP" → regulatory_note default-deny
  en record, respuesta y UI (informational_only, igual que W6.4).
- Injection desde openFDA → mitigada: trust=external, tope 1500 solo para el
  caso objetivo, marcadores anti-forgery, contrato "el caso describe a un
  tercero".

## 12. Decisiones que requieren aprobación explícita de Cesar

1. Archivo de prompts NUEVO (`case_analysis_prompts.yaml` v1.0.0) en vez de
   extender el del dossier — recomendado.
2. Tope del caso objetivo 1500 chars (external) — recomendado.
3. Persistencia `regulatory/case_analyses/<project_id>/<case_dir>/vNN.json`,
   estado vigente = último record (sin archivo de estado mutable) —
   recomendado.
4. Regla v2.1 `intra_proposal_contradiction` dentro de Fase B con fixture
   v08 — recomendado (cierra la limitación 1 de Fase 0).
5. `accept` sin efecto sobre dossier/documentos (solo registro + auditoría) —
   fijado por el plan; se ratifica.

## 13. Qué NO hace esta fase

Código (es Fase B) · scheduler/trigger automático · HTTP nuevo · persistir
detalle openFDA · vincular análisis al dossier · embeddings · conectores
nuevos · tocar gmp-api / aria-* / hotelbot-* / cases.jsonl.
