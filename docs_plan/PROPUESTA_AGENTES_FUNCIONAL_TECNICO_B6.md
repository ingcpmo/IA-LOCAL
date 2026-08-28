# PROPUESTA — Agentes FUNCTIONAL/TECHNICAL con LLM + corpus (B6)

**Estado:** PROPUESTA de diseño de agentes. **Pendiente de firma de Capa 9 (Cesar).**
**Fecha:** 2026-08-27. **Autor:** Capa 8.
**Contexto:** `docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md` FASE 5; skill `gmp-agent-design`.

---

## 1. Qué ya está hecho sin firma (B6a) y qué necesita firma (B6b)

**B6a — determinista, ya commiteado** (`findings/functional_findings.py`): recorre el evidence
graph (B2) y emite, con aristas literales y anclaje real:
- `FunctionalFinding: CONTRADICTORY_FUNCTIONAL_BEHAVIOR` (aristas `contradicts`)
- `TestCoverageFinding: TEST_WITHOUT_REQUIREMENT` (test sin `verifies`/`tested_by`)
- `TraceabilityFinding: REQUIREMENT_NOT_TRACED` (claim de doc fuente sin `implemented_by`/`tested_by`)

**B6b — necesita firma:** lo que exige juicio semántico local (LLM) + corpus RAG citable:
- `functional_consistency_agent` (modo semántico): contradicciones sin eco léxico, y
  `REQUIREMENT_NOT_IMPLEMENTED` linkeando un requisito **del catálogo** a claims (el linkeo
  determinista requisito→claim es débil en corpus real — deuda declarada de B2).
- `technical_design_agent`, `data_integrity_agent`, `security_architecture_agent`,
  `automation_controls_agent` — huecos de diseño técnico (audit trail design, time-sync,
  backup/recovery, redundancia, interfaces, control de acceso a nivel de arquitectura).

## 2. Árbol de decisión aplicado (skill `gmp-agent-design`)

| Agente propuesto | Decisión | Justificación |
|---|---|---|
| `functional_consistency_agent` | **AGENTE NUEVO** | dominio nuevo (coherencia funcional cross-documento), salida distinta (`FunctionalFinding`), opera sobre el grafo + `Claim.normalized_statement`, no cabe 100% en ningún agente base |
| `requirements_traceability_agent` | **CABLEAR el existente** | ya está en `agents_catalog.yaml` (6 findings legacy) pero desconectado; B6a ya lo usa determinista, B6b le añade el modo semántico |
| `test_coverage_agent` | **AGENTE NUEVO** ligero | mayormente determinista (grafo); LLM solo para clasificar cobertura parcial |
| `technical_design_agent` | **AGENTE NUEVO** | dominio técnico de diseño, corpus propio, `TechnicalFinding` |
| `data_integrity_agent` | **PERFIL DERIVADO de `integrity`** | el agente base cubre ~75% (ALCOA+, Part 11); solo prompt + corpus especializado a arquitectura de datos |
| `security_architecture_agent` | **PERFIL DERIVADO de `audit`** o agente nuevo | controles de acceso/segregación a nivel de arquitectura; decidir según solapamiento con `fda_part11_agent` |
| `automation_controls_agent` | **PERFIL DERIVADO de `automation`** | el agente base cubre ISA-88/95, GAMP5 Cat 4/5, PLC/SCADA; corpus especializado a listas de I/O y alarmas |

## 3. Checklist obligatorio por agente nuevo (skill) — a completar antes de firmar

Para `functional_consistency_agent`, `test_coverage_agent`, `technical_design_agent`:

```
[ ] agent_id (snake_case) + nombre visible
[ ] descripción de alcance y límites
[ ] system_prompt (idioma dinámico, formato de salida = Finding V2, temperatura 0)
[ ] colección RAG propia con >= 60 chunks de fuentes citables (audit trail design guidance,
    GAMP5, ISA-88/95, EEMUA 191, backup/recovery best practice, time sync guidance)
[ ] reglas asociadas (extensión del adjudicador V2 si aplica)
[ ] >= 5 preguntas de prueba con criterios de aceptación verificables
[ ] entrada en manifest + agents_catalog.yaml
[ ] evidencia de validación (respuestas reales archivadas)
[ ] aprobación humana registrada
```

Para los perfiles derivados (`data_integrity`, `automation_controls`):

```
[ ] perfil_id, agente base, % de cobertura estimado + justificación
[ ] system_prompt especializado (delta sobre el base)
[ ] colección RAG propia o compartida (declararlo)
[ ] >= 3 preguntas de prueba con criterios
[ ] entrada en profiles/<base>_profiles.yaml + manifest
```

## 4. Reglas duras (no cambian)

- Los agentes B6b corren sobre el **mismo `qwen2.5:7b` local** — "agente" = configuración
  gobernada, no instancia de modelo. Sin egress.
- Salida = `Finding` V2 (taxonomía B5): `human_state` nace `UNREVIEWED`, la IA nunca lo cambia.
- El `Risk` sigue siendo determinista (`risk_matrix.yaml`), nunca del LLM.
- Anti-redundancia: `technical_design_agent` / `security_architecture_agent` **no** re-evalúan
  requisitos regulatorios; si un hueco técnico también incumple una norma, el
  `RegulatoryFinding` lo cubre y el `TechnicalFinding` lo referencia (`related_finding_ids`).
- Cada agente nuevo necesita su fixture en la **Suite C** (B8) y su gate propio
  (`TECHNICAL_RECALL ≥ 90%`, `FP ≤ 5%`) firmado antes de considerarse operable.

## 5. Preguntas para tu firma

1. ¿`security_architecture_agent` como agente nuevo o como perfil de `audit`?
2. ¿El corpus RAG de los agentes técnicos se arma de fuentes que ya tienes gobernadas
   (`gmp_automation`, `gmp_data_integrity`, …) o hay que ingerir fuentes nuevas (GAMP5,
   ISA-88/95, EEMUA 191) por el circuito de `human_source_registration`?
3. ¿Firmas el diseño para que Capa 8 complete los checklists (system_prompts + corpus +
   fixtures) y te los presente como paquete de release por agente?

Hasta tu firma: B6b no arranca. B6a (determinista) ya opera.
