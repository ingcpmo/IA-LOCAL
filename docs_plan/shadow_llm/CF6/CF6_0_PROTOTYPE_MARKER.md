# CF-6 v1.2 · CF6-0 — v1 marcado como PROTOTIPO — NO PRODUCTO

**Fecha:** 2026-09-03 · **Autoridad:** Capa 9 = Cesar · **Fase:** CF6-0 (sin LLM)
**Corrida:** implementación de CF-6 v1.2 §7, pasos CF6-0 y CF6-1. Sin commit hasta aprobación.

## Qué queda marcado como PROTOTIPO — NO PRODUCTO

| Artefacto | Marca aplicada |
|---|---|
| `docs_plan/shadow_llm/G4/INFORME_NARRATIVO_SHADOW_v1.md` | banner HTML al inicio + sufijo `⚠ PROTOTIPO — NO PRODUCTO` en el H1 |
| `factory/regulatory/shadow/render_narrative.py` | nota CF6-0 en el docstring del módulo |
| `factory/regulatory/shadow/experts.py` → `run_composer` (G4e) | docstring: pide prosa libre → PROTOTIPO; producción = estructura JSON + Q-STATE + render determinista |

## Por qué

La narrativa v1 (G4e) se generó con **prosa libre del LLM**. El criterio de aceptación de G4e
midió solo estructura, no seguridad semántica. Resultado medido (ver `CF6_1_BASELINE.md`):
la narrativa v1 eleva `INCONCLUSIVE` a incumplimiento, propone acción correctiva/CAPA,
filtra vocabulario interno y fuga identificadores `rec-…` y la marca `[[SHADOW`.

## Qué NO cambia

- El core determinista, L0–L5, los cuatro expertos, G0–G3, el `FINDINGS_FINGERPRINT`.
- Los 457 findings L2 y su `human_state = UNREVIEWED`.
- G4d **no** se re-ejecuta.
- Los artefactos v1 se conservan intactos (salvo la marca), como referencia de línea base.

## Siguiente

`CF6-1` (mismo commit): gate de estado Q-STATE-1..6, render determinista, blacklist Q1–Q5,
modo determinista seguro, normalización de G4d, y medición de la línea base v1
(`factory/regulatory/shadow/composer_gate.py`, `factory/tests/test_shadow_composer_gate.py`,
`CF6_1_BASELINE.{json,md}`).

`CF6-2` en adelante (nuevo `composer_prompt_version`, firma de Capa 9, tag `cf6-G2`,
`PILOT_SCOPE_MATCH_CF6`, `SAMPLE_MANIFEST`, HUMAN_QUALITY_GATE) **no** se ejecuta en esta
corrida: requiere firma humana y verificación de scope de la PILOT (§4, §6).
