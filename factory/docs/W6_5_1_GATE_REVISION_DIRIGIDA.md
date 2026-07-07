# Gate W6.5.1 — Revisión dirigida + Verificador v2 (OBLIGATORIO antes de W7)

Estado: **GATE CERRADO — implementado 2026-07-07, aprobado por Cesar
2026-07-07** · Definido: 2026-07-06 (cierre Fase D)
Fundamento: evidencia real v1–v6 en `W6_5_FASE_D_CIERRE_EXPERIMENTO.md`
Decisión de arquitectura aprobada por Cesar (delegada a Fable, sesión 2026-07-06).

## Regla del gate

**Ningún endpoint nuevo puede consumir el pipeline LLM de propuestas
(`dossier_agent_review_service`) — en particular el futuro
`POST /case-memory/{id}/analyze` de W7 — hasta que este gate esté CERRADO.**
El gate se cierra con las dos piezas implementadas, sus criterios de
aceptación en verde y aprobación humana de Cesar.

## Motivación (resumen; detalle en el cierre de Fase D)

El experimento v1–v6 demostró patrón whack-a-mole: cada `request_changes`
corrige lo instruido y rompe algo previamente correcto. Causa compuesta:
(1) capacidad del 7B — no retiene todas las restricciones simultáneas;
(2) **amplificador arquitectónico propio**: la regeneración es un borrador
desde cero — el texto de la versión anterior nunca entra al prompt y solo se
pasa la última guidance; (3) el verificador no cubre negaciones ni exactitud
de referencias — justo donde el modelo es más débil. Las capas 2 y 3 son
nuestras y se corrigen aquí; la capa 1 (modelo) queda condicionada a hardware.

## Pieza A — Modo revisión para request_changes

- El prompt de regeneración incluye la **respuesta anterior completa** en un
  bloque dedicado + instrucción de **edición mínima**: aplicar SOLO los
  cambios pedidos, conservar el resto textualmente.
- **Ledger de guidances**: el record acumula todas las guidances humanas de la
  cadena de versiones y el prompt las inyecta todas, no solo la última — las
  restricciones ya conquistadas no salen del prompt.
- Temperatura 0.0 en revisiones (0.2 solo en primera generación).
- Gobierno: template de prompt v1.1.0 + changelog + SHA recomputado; el modo
  (draft|revision) y el ledger quedan registrados en el record y en el evento
  de auditoría. Sin cambios de esquema de auditoría.

## Pieza B — Verificador v2 (determinista, sin LLM, flags advisory — nunca reescribe)

1. `unverified_reference`: whitelist de normas citables por documento/agente,
   derivada de las declaraciones de corpus existentes (profiles + regulatory
   scope de la misión). `[REF:]` fuera de whitelist → flag.
2. `negation_contradicted`: claim `[SE]`/negativa cuyos tokens de sujeto SÍ
   aparecen en la evidencia del prompt → flag.
3. `multi_claim_line`: más de una etiqueta `[E:]/[SE]/[REF:]` en una misma
   línea → flag (hoy el parser solo cuenta la primera silenciosamente).

## Criterios de aceptación (testables, con fixtures REALES)

Las propuestas archivadas
`validation/oos_hplc_investigator/agent_proposals/data_integrity_assessment/v01–v06.json`
son fixtures de regresión obligatorios:

- [x] Verificador v2 sobre v5 → flag `unverified_reference` en §11.30(a)/(c)
      y en "FDA Data Integrity Guidance 2018, §3.4"
      (`test_gate_v05_flags_unverified_references` — exactamente 3 findings).
- [x] Verificador v2 sobre v6 → flag `negation_contradicted` en el [SE]
      "no hay evidencia de aprobaciones humanas" (audit contiene
      validation_doc_approved) (`test_gate_v06_flags_negation_contradicted` —
      exactamente 1 finding; las demás negaciones de v6 no señalan).
- [x] Verificador v2 sobre v4 → flag `multi_claim_line`
      (`test_gate_v04_flags_multi_claim_line` — 3 viñetas agrupadas).
- [x] Verificador v2 sobre v6 → SIN flag en las citas §11.10(e)/(k) y
      Subparte C (`test_gate_v06_no_false_positives_on_correct_references`).
- [x] Modo revisión (con LLM mockeado): el prompt de revisión contiene la
      respuesta anterior íntegra y TODAS las guidances del ledger
      (`test_revision_mode_prompt_and_ledger`).
- [x] Confianza computada penalizada por los flags nuevos: regla definida —
      `negation_contradicted` | `unverified_reference` ⇒ baja (texto
      potencialmente falso); `multi_claim_line` ⇒ nunca alta (verificación
      incompleta) (`test_gate_confidence_penalized_by_v2_flags`).
- [x] Suite completa verde (393 passed) + selfcheck PASS=4 FAIL=0.
- [x] **Aprobación de Cesar** (2026-07-07) — gate CERRADO; W7 puede consumir
      el pipeline LLM de propuestas.

## Implementación (2026-07-07)

- `services/claim_verifier.py` (NUEVO, puro: sin HTTP/auditoría/escritura):
  verificador v2 + derivación de grants + `items_from_prompt` para
  re-verificar propuestas archivadas. Reutilizable por W7.
- **Decisión: la whitelist NO es un archivo nuevo** — se deriva de las
  declaraciones de corpus existentes (corpus_available + corpus_pending +
  regulatory_scope de la misión). Granularidad: sección CFR citable solo si
  enumerada; Parte declarada autoriza Parte/Subparte, nunca secciones;
  documentos citables a nivel documento (numeral ⇒ flag); corpus_pending
  otorga citabilidad de título.
- **Decisión: negaciones contrastadas SOLO contra evidencia operacional**
  (runs/audit/rc/deployment) — la intención (mission/agents/catalog) no
  contradice hechos; léxico ES→EN mínimo explícito (aprobaciones→approv…);
  regla ALL-tokens para precisión (un flag falso erosiona al revisor).
- `services/dossier_agent_review_service.py`: modo revisión (revision_of,
  ledger acumulado con fallback legado, temperatura 0.0, bloque
  [RESPUESTA_ANTERIOR] sanitizado anti-forgery), verifier v2 integrado,
  confianza penalizada, mode/ledger en record y evento (esquema aditivo).
- `agent_prompts/dossier_review_prompts.yaml` v1.1.0: `revision_contract`
  gobernado (+SHA, changelog); los 3 prompts de agente NO cambian.
- Fixtures v01–v06 archivados en `tests/fixtures/agent_proposals/` (los
  originales de factory/validation/ no están bajo git y los escribe el
  contenedor); grants de los tests derivadas de los perfiles y misión REALES
  — si una fase de corpus cambia las declaraciones, la suite lo hace visible.
- Sin endpoints nuevos y sin cambios de UI (los flags nuevos se muestran con
  el renderizado genérico de chips existente). La regla del gate sigue
  vigente: ningún endpoint nuevo consume el pipeline hasta el cierre formal.

## Disparadores de retoma anticipada (cualquiera reabre este trabajo antes de W7)

1. Decisión de escalar propuestas de agente a más documentos del dossier
   (p. ej. `test_strategy`) → implementar como mínimo la Pieza B antes.
2. Disponibilidad de GPU u hardware superior → reevaluar PRIMERO el nivel de
   modelo (14B+/estructurado); puede reducir el alcance necesario de la Pieza A.

## Fuera de alcance de este gate (decisiones ya tomadas)

- Modelo mayor en CPU: descartado (20–30 min/pasada rompe el lazo interactivo).
- Pipeline multi-etapa con 7B: descartado (la etapa crítica hereda la misma
  inestabilidad; 3× latencia para mover el problema de lugar).
- Calidad experta estable de primera generación: NO es objetivo de este gate
  (es capa de capacidad del modelo; ver limitación declarada en el cierre).
