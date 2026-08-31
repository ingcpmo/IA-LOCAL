# E1 — HISTORIAL DE FIRMAS (append-only)

Registro de las revisiones humanas del gate E1 (verificación de la muestra de relaciones
nuevas H-10). El almacén de gobernanza es append-only: **cada revisión se conserva**; una
revisión posterior no borra ni invalida la anterior — la contextualiza.

---

## E1-1 · 2026-08-31 · pre FIX-A · **FAIL**

```
sample_sha256       = f56d4babe7e8466368c9a6dbefe26e3716186f96e2658c68cf2f0469f5244f20
verdict_set_sha256  = a533bf4aa11d58acf2dd881cd5abaf52f85175c90db3c50d0bb1a79b352de085
TOTAL=77   CORRECT=26   WRONG_NODE=30   SPURIOUS=11   AMBIGUOUS=10
E1_ACCEPTANCE       = FAIL / REMEDIATION_REQUIRED
```
- Causa dominante: `_link_refers_to` sin resolución de especificidad → genérico = nodo equivocado.
- Los veredictos por fila no se registraron individualmente (sólo agregado + hash).
- Evidencia: `docs_plan/E1_REVIEW_Y_FIX_H10_REFERS_TO_20260831.md`.

## E1-2 · 2026-08-31 · post FIX-A · **FIRMADA (E1_ACCEPTANCE no declarado)**

```
sample_sha256       = c2ca5aaa36e9904b77cecf266cfa6645ab76949828074c857a360a5bf75ad3fd
verdict_set_sha256  = 7b3f23ff5b45082121dbeae6c87f5db0f3eff9992c9e26814a3e1f3f0fd0987a
TOTAL=77   CORRECT=60   WRONG_NODE=7   SPURIOUS=7   AMBIGUOUS=3
ledger              = ARTIFACT_VERSION-2026-022 (propose) + ARTIFACT_VERSION-2026-023 (confirm, Cesar)
meaning             = authenticated_confirmation_of_this_human_verdict_set
does_not_imply      = [E1_ACCEPTANCE=PASS, graph_incorporation, flip, qa40_adjudication, production]
```
- Desglose: `tested_by` = 7 CORRECT / 7 SPURIOUS / 3 AMBIGUOUS · `refers_to` = 53 CORRECT / 7 WRONG_NODE.
- Confirma que FIX-A resolvió materialmente `refers_to` (30→7 WRONG_NODE) pero **RC-3 de `tested_by`
  sigue siendo material** (10/17 ruido) y quedaban 7 `refers_to` WRONG_NODE residuales.
- **FIX-B (RC-3)** + **FIX-C (RC-2 alias)** aplicados sobre esos residuales → E1-3.

## E1-3 · post FIX-A + FIX-B (RC-3, endurecido) + FIX-C (RC-2 alias) · **PENDING**

```
sample_sha256       = 77e8324f333f08edb4115a1dcb65962c9daf61bc4c6b0c584af8668b783dd0a4
sample_size         = 67   (7 tested_by + 60 refers_to ; tested_by 17→7 por FIX-B)
verdict_set_sha256  = (pendiente — se calcula al completar 67/67)
E1_POST_FIX_ACCEPTANCE = PENDING
```

**Endurecimiento posterior a la revisión de Cesar (sin rediseño):**
- `_ref_is_only_crossref` clasifica "See 3.1.9, F05.05" como cross-referencia
  (los puntos de la sección ya no cortan la detección) → `specification (See …, F05.05)`
  NUNCA se convierte en `tested_by`.
- El emparejamiento estricto de RC-3 se limita a refs CORTAS/ambiguas
  (`3.2.3`, `F05.05`, `UR3.2.3`); un id FORMAL de requisito (`PCS-SR-037`,
  `UR-WD-001`) o una cita CFR/Annex mantiene su coincidencia literal
  (comportamiento pre-RC-3) → `wp_d` synthetic gate = PASS.
- FIX-C: las variantes de nombre (`FactoryTalk View Site Edition`,
  `FactoryTalk Runtime Security`, `FactoryTalk Alarms and Events`) NO son nodos
  propios → `_COMPONENT_ALIASES` las resuelve al canónico. `_link_refers_to`
  enlaza la variante al MISMO nodo canónico, sin crear duplicado semántico ni
  enlace simultáneo al genérico `FactoryTalk`.

**Composición E1-3:** `refers_to` con destino específico ; **sólo 1 `FactoryTalk`
genérico** (fila 18 = claim truncado en el OCR de RW-0012 p5, "…the FactoryTalk",
sin producto que resolver — límite de extracción, no defecto de modelo).
`system_component` 47→56→**53** (sin nodos de variante). `tested_by` 17→**7**.
- **FIX-B** (`_link_to_tests`): una coincidencia de token de ref corta (`3.2.3`, `F05.05`) ya no
  basta. Se exige que el claim pertenezca al ref (lo lidera / tag final) O comparta ≥2 palabras
  de contenido salientes con la descripción del Test; se descartan las cross-referencias
  (`[MCCPDC 3.2.3]`, `See 3.1.9, F05.05`, `reference number …`). Calibrado contra el veredicto
  E1-2: mantiene exactamente los 7 `tested_by` CORRECT, descarta los 7 SPURIOUS + 3 AMBIGUOUS.
- **FIX-C** (`_COMPONENT_TERMS`): +términos "FactoryTalk View Site Edition / Alarm and Events /
  Alarms and Events / Activation Manager / Runtime Security / Security". 6 de los 7 `refers_to`
  WRONG_NODE residuales pasan al nodo específico; **1/7 (fila 27) es un claim truncado en el
  OCR** ("…the FactoryTalk", sin producto que resolver) — límite de extracción, no defecto de modelo.
- Paquete de revisión: `docs_plan/E1_REVIEW_PACKET_E1_3_20260831.md` (67 filas; cada una con
  `SAME_RELATION_AS_E1_2` y `PREVIOUS_VERDICT (E1-2, referencia)`).
- Esqueleto: `docs_plan/E_GATES_GOVERNED_PAYLOADS_20260831/E1_3_verdicts_skeleton.json`.
- UI: panel `gate-e1`, `E1_SAMPLE_SHA = da11837a…`, `E1_SAMPLE_SIZE = 67`,
  `decision_ref = E1-3-H10-RELATIONS-20260831`, payload lleva `prior_reviews = [E1-1, E1-2]`.
- Registro: `propose → confirm` de `ARTIFACT_VERSION` con la Identity Key del humano.
