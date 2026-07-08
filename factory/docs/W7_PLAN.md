# W7 — Análisis de casos regulatorios por agente experto

Estado: **PLAN APROBADO por Cesar (2026-07-07) — Fase 0 CERRADA
(2026-07-07, ver W7_FASE0_PREFLIGHT.md; 2 limitaciones abiertas registradas)**
Precondición cumplida: gate W6.5.1 CERRADO (`c0c359e`, aprobado 2026-07-07)
— la regla "ningún endpoint nuevo consume el pipeline LLM" queda levantada.

Base documental: flujo diseñado en W6.4 (panel "Analizar con agente · DISEÑO"
de `intel_views.js`: selective fetch → prompt al perfil → respuesta con cita →
revisión QA → auditoría), gate `W6_5_1_GATE_REVISION_DIRIGIDA.md` y lista
"Qué NO existe" del checkpoint W6.

## Objetivo

Cerrar el lazo de inteligencia regulatoria: que un caso de la memoria
regulatoria (openFDA; hoy 5 casos Class II reales) pueda ser analizado por el
agente experto que el routing determinista de W6.4 ya recomienda, contra la
misión y su corpus declarado, con propuesta verificada (verificador v2),
decisión humana y auditoría — extender el pipeline gobernado de W6.5 de
"documentos del dossier" a "casos regulatorios". El agente conecta el mundo
exterior (recalls FDA) con la misión concreta; el humano decide qué hacer.

## Fases

### Fase 0 — Preflight (sin código): corrida real de request_changes
Cesar dispara desde la UI de Validación una propuesta nueva sobre
`data_integrity_assessment` (v07, draft con qwen) y le pide un ajuste
(v08, primera revisión real con modo W6.5.1: respuesta anterior íntegra +
ledger + temperatura 0.0). Se mide:
- ¿conserva TEXTUALMENTE lo no cuestionado? (diff v07→v08)
- ¿aplica solo lo pedido? ¿desaparece el patrón whack-a-mole de v4→v6?
- ¿qué flags levanta el verificador v2 en vivo?
Entregable: mini-informe que alimenta el diseño de Fase A. Costo ~15 min de
qwen. Es acto humano (trigger manual); NO reabre el experimento cerrado de
Fase D ni es criterio del gate W6.5.1 (que se cerró con criterios mockeados
por diseño): es **preflight de W7**.
Guidance sugerida: reusar una instrucción de las de Fase D (p. ej. disciplina
de citas) para comparar directamente contra el comportamiento v5/v6 sin modo
revisión.

### Fase A — Diseño y contrato (doc + aprobación humana)
- Evidencia que entra al prompt del análisis: registro del caso +
  `presentation` W6.4 + misión + compare read-only; el detalle openFDA SOLO
  si ya fue fetched (sin HTTP nuevo desde el pipeline LLM).
- Producto: registro versionado inmutable análogo a `agent_proposals`, en
  `regulatory/case_analyses/`.
- Prompts gobernados nuevos (mismo patrón SHA + changelog + suite).
- Elegibilidad de caso y estados; revisar topes de sanitización (el caso
  externo pasa de contexto a centro del prompt).

### Fase B — Backend
`POST /api/v1/layer9/case-memory/{id}/analyze` + GET + POST decisión.
Trigger manual con nombre real (403 al resto, igual que W6.5). Eventos
nuevos en VALID_EVENTS: `case_analysis_generated/failed/decision`.
Verificador v2 y confianza computada tal cual. `cases.jsonl` NO se reescribe.

### Fase C — UI
Convertir el panel DISEÑO de la vista Inteligencia en flujo real (mismo
patrón que Fase C de W6.5: gobierno completo, claims coloreadas, decisión
humana con motivo).

### Fase D — Ejecución real gated
Análisis de 1 caso real con Cesar, ciclo de decisión completo, cierre con
informe.

## Qué reutiliza de W6.5/W6.5.1 (el núcleo completo)

`_ollama_generate` + sanitización + marcadores canónicos + guard
anti-truncado + retry de formato · `claim_verifier.py` completo (grants
derivadas por agente+misión sirven tal cual) · modo revisión + ledger +
temp 0.0 · routing determinista `_recommend_agent` (W6.4) ·
`validate_run_by` · persistencia versionada inmutable · auditoría hash
chain · patrón UI de Validación.

## Componentes nuevos (y nada más)

Set de prompts de análisis de caso · persistencia `case_analyses/` ·
3 endpoints layer9 · 3 eventos de auditoría · elegibilidad de caso · UI real
del panel. Sin servicios paralelos ni abstracciones nuevas.

## Ollama/Qwen

qwen2.5:7b-instruct-q4_K_M: único modelo viable demostrado (línea
FACTORY_OLLAMA_MODEL en factory/.env, aislado del resto de consumidores).
CPU ~7 min/pasada. Temp 0.2 borrador / 0.0 revisión. num_ctx 8192 + guard.
Si llega GPU: reevaluar modelo ANTES de escalar alcance (disparador escrito
en el gate W6.5.1).

## Decisiones: agente vs humano

- **Agente (solo redacta)**: propuesta de análisis con claims etiquetadas
  [E:]/[SE]/[REF:] verificadas por el verificador determinista; confianza
  siempre computada, jamás autodeclarada.
- **Humano (todo lo demás)**: disparar el análisis, accept/reject/
  request_changes con motivo, cualquier uso regulatorio del resultado,
  aprobaciones del dossier. El análisis aceptado NO entra automáticamente a
  ningún documento GMP — vincularlo al dossier sería decisión aparte con
  aprobación aparte.

## Criterios de éxito

1. Preflight: la revisión real conserva lo no cuestionado y aplica lo pedido
   (o se documenta que el 7B no puede, y eso re-dimensiona W7).
2. Análisis e2e de 1 caso real: generado, verificado (v2), decidido por
   Cesar, auditado — cadena íntegra.
3. Suite verde + selfcheck PASS; cero regresiones del flujo de dossier.
4. UI con gobierno completo (modelo, prompt version, SHAs, flags, confianza).

## Riesgos

- Calidad del 7B en dominio nuevo (texto externo corto y ruidoso) →
  verificador + humano; el preflight da la primera medida.
- Timeout HTTP en pasadas ~7 min → ya resuelto en W6.5 (read 1200 s), pero
  la vista Inteligencia debe manejar la espera.
- Confusión regulatoria (análisis de caso ≠ evaluación de impacto GMP) →
  disclaimers default-deny como W6.4, informational_only.
- Prompt injection desde contenido openFDA → mitigado (trust=external, tope
  600 chars, marcadores), pero revisar topes en Fase A al cambiar el rol del
  caso en el prompt.

## Pruebas

Unit + e2e con LLM mockeado (patrón review_env) · fixtures del caso real
"sterility" existente · reutilización de los tests de claim_verifier (sin
duplicar) · test estructural anti-approve/anti-HTTP-extra · ejecución real
gated de Fase D como validación viva.

## Qué NO se hace todavía (requiere aprobación futura explícita)

Ejecutor/scheduler automático · conectores nuevos (Warning Letters, etc.) ·
embeddings/búsqueda semántica · consolidación multiagente · escalar
propuestas de agente a más documentos del dossier (la Pieza B lo permitiría;
es decisión de Cesar aparte) · vincular análisis aceptados al dossier ·
descargar modelos nuevos · tocar gmp-api / aria-* / hotelbot-*.

## Arranque recomendado (aprobado)

Fase 0 primero, antes de escribir una línea de Fase A: evidencia viva del
modo revisión con qwen por ~15 minutos de cómputo. Con el mini-informe en
mano se aprueba Fase A con datos reales.
