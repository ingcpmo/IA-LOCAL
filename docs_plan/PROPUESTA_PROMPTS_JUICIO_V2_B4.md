# PROPUESTA — Prompts de juicio V2 (B4): 2 pasos + Critic

**Estado:** PROPUESTA de contenido gobernado. **Pendiente de firma de Capa 9 (Cesar).**
Los 3 prompts se implementan como **borrador** (`prompts/v2_draft/`, marcados
`DRAFT_UNSIGNED`); el código de B4a los carga para tests por *replay offline* (LLM
mockeado), pero **ninguna corrida real de medición (B4b) arranca sin esta firma + una
`PILOT_EXECUTION` firmada**.
**Fecha:** 2026-08-27. **Autor:** Capa 8.
**Contexto:** `docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md` FASE 6; causa raíz
`SEMANTIC_JUDGMENT_FAILURE` (FASE 1).

---

## 1. Por qué 2 pasos + Critic

FASE 1 confirmó: el 7B local **no cruza de un pasaje técnico a un criterio regulatorio
abstracto en una sola pregunta**. La descomposición (B3, firmada) ya acortó el criterio; B4
acorta el **salto de razonamiento**:

```
Paso A — Descripción operativa neutra
   Entrada: el/los Claim candidatos (source_text literal).
   Tarea:   "describe en términos operativos qué hace / registra / controla / quién actúa /
            sobre qué componente — SIN mencionar ninguna norma ni ningún criterio".
   Salida:  texto libre corto (1–3 frases). NO es evidencia citable.

Paso B — Mapeo al sub-criterio
   Entrada: el sub-criterio (bilingüe, decomposition v1.1) + la descripción neutra del paso A.
            El JUICIO ("¿satisface?") se hace sobre la descripción neutra, no sobre el pasaje.
            La lista de Claims (id → texto literal) se incluye SOLO para que el modelo pueda
            devolver una cita literal — no para re-juzgar sobre el texto crudo.
   Tarea:   "¿esta descripción satisface el sub-criterio?" → {SATISFIES | PARTIAL | NO | UNCLEAR}
            + claim_id citado + evidence_quote (transcripción literal del Claim).
   Salida:  JSON.
   Guardián: `evidence_verifier` (sin cambios) comprueba INDEPENDIENTEMENTE que esa
            evidence_quote ancla literalmente en `Claim.source_text`. Si el modelo la
            parafrasea o la inventa, el verificador la rechaza y el candidato cae a
            MACHINE_REJECTED — el paso B no puede "colar" evidencia.

Critic — Segunda lectura adversarial (prompt distinto, temperatura 0)
   Entrada: el sub-criterio + el Claim.source_text + el veredicto del paso B.
   Tarea:   INTENTAR REFUTAR. "¿hay una lectura en la que esta evidencia NO satisface el
            sub-criterio? ¿la cita es sobre otro tema? ¿se está infiriendo de más?"
   Salida:  {AGREE | DISAGREE | CANNOT_CONFIRM} + razón.
```

Después, **determinista** (sin LLM): `evidence_verifier` (validación A/B/C/D, sin cambios) +
`adjudicator` combinan Hunter + Critic + Verifier con reglas fail-closed.

## 2. Guardarraíles (duros, no negociables)

- **La cita citable de cualquier `observed` es SIEMPRE `Claim.source_text` literal**, verificada
  por `evidence_verifier` sin cambios. El paso A (descripción neutra) es insumo de
  razonamiento, **nunca** evidencia.
- **El JUICIO del paso B se hace sobre la descripción neutra**, no sobre el pasaje crudo. El
  paso B recibe la lista de Claims solo para poder devolver una cita literal; esa cita la
  valida `evidence_verifier` de forma independiente contra `Claim.source_text`. Un paso B que
  parafrasee o invente la cita produce MACHINE_REJECTED, no un `observed`.
  (Alternativa más estricta —paso B sin ver ningún Claim, la cita se elige en un paso B2
  determinista— queda como pregunta 1 para tu firma.)
- **`evidence_verifier` intacto** — umbral fuzzy 0.93, exigencia de cita anclada, validación C.
  Ninguna de estas prompts las relaja.
- **El Critic no puede promover** — solo `AGREE`/`DISAGREE`/`CANNOT_CONFIRM`. Un `DISAGREE` o un
  `CANNOT_CONFIRM` degrada; nunca sube un veredicto.
- **`EVIDENCE_NOT_FOUND` nunca cierra `DOCUMENTATION_GAP`** por sí solo — eso es consolidación a
  nivel de requisito (B5), con las 4 condiciones de FASE 6.2. El adjudicator solo emite el
  estado por sub-criterio.
- **Sin declaración de cumplimiento final.** `MACHINE_CONFIRMED` de un sub-criterio no es
  aprobación; el `human_state` del Finding sigue iniciando `UNREVIEWED`.
- **Temperatura 0** en los tres prompts. Prohibido subirla "para que encuentre más" (skill
  `gmp-recall-pipeline`).
- **`ANNEX11_4` (negativo obligatorio):** el paso B debe devolver `NO`/`UNCLEAR` para una
  entrada bibliográfica; la nota de guardián de `decomposition.yaml` + el Critic lo refuerzan.

## 3. Los 3 prompts (borrador para tu revisión)

Archivos: `factory/engines/gmpai_integrity/prompts/v2_draft/{step_a_neutral_description.yaml,
step_b_criterion_mapping.yaml, critic.yaml}` — cada uno con `prompt_version: "0.1-draft"`,
`status: DRAFT_UNSIGNED`, `schema_version`.

### 3.1 Paso A — `step_a_neutral_description`

> System: Eres un analista técnico. Se te dará uno o más fragmentos LITERALES de un documento
> de ingeniería de un sistema OT (PLC/SCADA/HMI). Tu única tarea es DESCRIBIR, en términos
> operativos y en 1 a 3 frases, qué hace / registra / controla / verifica el sistema según ese
> fragmento, y quién o qué actúa. NO menciones ninguna norma, regulación, ni criterio de
> cumplimiento. NO evalúes si algo "cumple". NO inventes: si el fragmento no permite describir
> algo, dilo. Responde solo con la descripción, sin JSON.
>
> User: FRAGMENTO(S):\n{claims_source_text}\n\nDescripción operativa neutra:

### 3.2 Paso B — `step_b_criterion_mapping`

> System: Se te dará (1) un SUB-CRITERIO regulatorio concreto y (2) una DESCRIPCIÓN OPERATIVA
> NEUTRA de lo que hace un sistema. Decide si la descripción satisface el sub-criterio.
> Reglas: responde SOLO en JSON con las claves `verdict` (uno de SATISFIES, PARTIAL, NO,
> UNCLEAR), `rationale` (1–2 frases), `evidence_claim_id` (el id del claim que sustenta, o
> null), `evidence_quote` (transcripción LITERAL del claim que sustenta, o cadena vacía).
> `SATISFIES`/`PARTIAL` EXIGEN `evidence_quote` no vacía. No parafrasees la cita. Si dudas,
> usa `UNCLEAR`. No consideres nada fuera de la descripción dada.
>
> User: SUB-CRITERIO:\n{subcriterion_text}\n\nDESCRIPCIÓN OPERATIVA NEUTRA:\n{neutral_description}
> \n\nCLAIMS DISPONIBLES (id → texto literal):\n{claims_index}\n\nJSON:

### 3.3 Critic — `critic`

> System: Eres un revisor CRÍTICO e independiente. Se te dará un SUB-CRITERIO regulatorio, un
> FRAGMENTO LITERAL de un documento, y un VEREDICTO previo de otro evaluador. Tu tarea es
> intentar REFUTAR ese veredicto: ¿existe una lectura razonable en la que el fragmento NO
> satisface el sub-criterio? ¿la cita habla de otro tema? ¿se está infiriendo más de lo que el
> texto dice? Responde SOLO en JSON con `assessment` (uno de AGREE, DISAGREE, CANNOT_CONFIRM)
> y `reason` (1–2 frases). AGREE = el veredicto previo se sostiene. DISAGREE = hay una lectura
> en la que no se sostiene. CANNOT_CONFIRM = el fragmento no alcanza para confirmar ni refutar.
> No propongas un veredicto nuevo, solo evalúa el dado.
>
> User: SUB-CRITERIO:\n{subcriterion_text}\n\nFRAGMENTO LITERAL:\n{claim_source_text}\n\n
> VEREDICTO PREVIO: {hunter_verdict}\n\nJSON:

## 4. Estados de salida del Adjudicator (determinista, FASE 6.1)

```
MACHINE_CONFIRMED       paso_B=SATISFIES ∧ Critic=AGREE ∧ Verifier∈{verified, verified_with_deviation}
MACHINE_PARTIAL         paso_B=PARTIAL   ∧ Critic≠DISAGREE ∧ Verifier ok           (evidencia parcial)
MACHINE_REJECTED        Verifier=rejected_by_verifier  (cita no ancla / incoherente)
INCONCLUSIVE            Hunter y Critic no coinciden, o Verifier=review_required, o paso_B=UNCLEAR
EVIDENCE_NOT_FOUND      paso_B=NO ∧ Critic∈{AGREE, CANNOT_CONFIRM}   (nunca => gap por sí solo)
CONTRADICTORY_EVIDENCE  el grafo (B2) tiene una arista `contradicts` para el control/claim
```

## 5. Costo (para dimensionar la `PILOT_EXECUTION` de B4b, no se gasta aquí)

Por (sub-criterio × candidato que llega a juicio): 1 llamada paso A + 1 paso B + (Critic solo
si paso B ∈ {SATISFIES, PARTIAL}). El `EvidenceBundle` (B3) ya acota a ≤5 candidatos y solo
los sub-criterios con candidatos plausibles llegan al modelo. Estimación fina en el
`PLAN_VALIDACION` de FASE 10; **B4b no arranca sin tu firma de estos prompts + `PILOT_EXECUTION`**.

## 6. Preguntas para tu firma

1. ¿El paso B juzgando sobre la descripción neutra, con la lista de Claims disponible SOLO para
   citar (y `evidence_verifier` validando la cita de forma independiente), es aceptable — o
   prefieres la variante estricta (paso B sin ver ningún Claim + un paso B2 determinista que
   elige la cita)? La variante estricta añade robustez anti-fabricación a costa de que el
   modelo no puede señalar un span concreto.
2. ¿El Critic como degradador-solo (nunca promueve) es suficiente, o quieres que un `DISAGREE`
   fuerce además una entrada explícita a la cola de revisión con la razón del Critic?
3. ¿Los estados del Adjudicator (§4) están bien, o falta/sobra alguno?
4. ¿Firmas los 3 prompts como contenido gobernado (`prompt_version` 1.0), habilitando B4b
   cuando exista la `PILOT_EXECUTION`?

Hasta tu firma: los prompts quedan `DRAFT_UNSIGNED`, B4a corre solo con LLM mockeado, **0
llamadas reales**.
