# R3-T1.2 — Reporte de Gate F1 (micro-validación, 2026-08-12)

Plan de referencia: `docs_plan/R3_T1_2_PLAN_POR_FASES.md`, sección F1.
Ejecutado por Claude Code (Capa 8), proceso en segundo plano desacoplado de
la sesión SSH (`ppid=1, systemd session-41.scope` — sobrevivió sin problema
a la corrida completa). Ningún gate se autoconfirma en este reporte: es
insumo para la firma de Cesar.

## F1.1 — Autorización

- `PILOT_EXECUTION-2026-015` (`agent_proposed`, 2026-08-12T02:49:59Z) →
  `PILOT_EXECUTION-2026-016` (`human_confirmed` por `cesar`, 2026-08-12T02:52:35Z).
- Tope firmado: **8 llamadas**. Alcance: `21_CFR_11.10(e)` × top-5 candidatos
  de fusión de RW-0005 (caso P1, evidencia conocida p.45-46). Perfil H2H4.
- `authorizes_corpus: false`, `authorizes_baseline: false` — esta firma NO
  habilita F2/F3.
- Registro completo: `autorizacion.jsonl`.

## F1.2 — Ejecución

- Flujo real de producto: `judgment_candidate_pool.build_fusion_candidate_pool()`
  + `judgment.run_judgment_batch()` (no script ad hoc de recuperación —
  la recuperación ya estaba confirmada en R2.1/R2.2, este run mide juicio).
- `run_id`: `chunked-50534e75927c`. `document_sha256`:
  `56095a7541fbb62e30d00e77308fde4c2ac0f4ec945adbf19a968b79debc82eb`.
- **5 de 5 llamadas completadas, todas `ok: true`, sin errores técnicos.**
  Dentro del tope de 8 firmado (usó 5, 3 de margen sin consumir).
- Candidatos evaluados (top-5 de fusión, `candidatos_top5.log`):

  | chunk_index | páginas | bm25_rank | embedding_rank | resultado |
  |---|---|---|---|---|
  | 20 (→0 en el run) | 45-46 | 1 | 2 | **observed**, cita anclada |
  | 21 (→1) | 47-48 | 5 | 1 | not_observed_in_chunk |
  | 25 (→2) | 55-55 | 3 | 3 | not_observed_in_chunk |
  | 26 (→3) | 56-56 | 4 | 12 | not_observed_in_chunk |
  | 18 (→4) | 41-42 | 10 | 6 | not_observed_in_chunk |

- Evidencia completa: `checkpoint_raw.json` (incluye `raw_response` crudo de
  cada llamada, hash sha256 de cada respuesta completa, y
  `verified_records_by_req`).

## F1.3 — Criterio pre-fijado: evaluación

**a) 11.10(e) ancla (observed con cita verificada) en ≥1 candidato: CUMPLE.**
Candidato de la página 45-46 (`task-bf3897479d56`), `chunk_observation:
observed`, `status: verified`, cita de 913 caracteres (UR3.3.1/UR3.3.2 —
timestamps, performer/approver, alarm log). Coincide con el caso P1
conocido del fixture set de recall.

**b) Registro por llamada completo (fingerprint, perfil, validación A/B/C/D):
CUMPLE.** Las 5 llamadas comparten fingerprint fijo:

```json
{
  "prompt_version": "1.1.1",
  "schema_version": "checkpoint_llm_response_v1",
  "model_digest": "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e",
  "agent_version": "v1-pilot-2026-08",
  "catalog_version": "2.1",
  "use_verified_pipeline": true,
  "evaluation_profile": "H2H4"
}
```

Modelo: `qwen2.5:7b-instruct-q4_K_M`, Ollama `0.21.2`. La validación A
(anclaje)/B (fuente)/C (semántica)/D (suficiencia) está presente y calculada
para el candidato ancla.

**c) Latencia p50/p95 medida (insumo D4-A): CUMPLE.** Ver `latencias.json`.

- p50 ≈ 593.5s (~9.9 min/llamada)
- p95 ≈ 838.0s (~14.0 min/llamada)
- Total pared para 5 llamadas: ~51 min (secuencial, sin paralelismo)

## Hallazgo secundario (no invalida el criterio F1.3, pero condiciona F2)

El propio candidato ancla (chunk 0, p.45-46) tiene su capa D marcada
`d_sufficiency: NOT_ASSESSABLE`, `operational_result: EVALUATION_INCOMPLETE`,
`substantive_evidence_accepted: false` — por violación de contrato en
`criterion_assessments`: los criterios `criterion_index=2` (timestamp) y
`criterion_index=3` (registro de acciones) vienen `status: MET` con
`evidence_quote`/`evidence_location` vacíos.

**Investigado y descartado como bug de gobernanza**: el prompt real en uso
(`factory/engines/gmpai_integrity/prompts/part11_prompts.yaml`, `PROMPTS_DIR`
resuelto por `corpus_plan.py`) está en `v1.1.1`, con la regla 6 exigiendo
explícitamente `evidence_quote` y `evidence_location` no vacíos para
`status=MET` desde la Fase F (2026-07-25) y el fix de R2.1 (2026-08-10,
aprobado por Cesar) que cerró el mismo hueco a nivel de `estado`/
`evidencia_exacta`. El texto del contrato es correcto y completo. La
violación observada es **incumplimiento real de instrucción por parte del
modelo** (`qwen2.5:7b`), no un hueco de prompt — exactamente el riesgo
central ya documentado del proyecto (recall/cumplimiento de instrucciones,
`ROADMAP_ANALIZADOR_GMP.md` R2). La capa D (`semantic_evidence_verification.py`)
actuó correctamente: excluyó el chunk de la agregación en vez de aceptar un
MET sin evidencia — el guardián funcionó, no falló.

Hallazgo colateral sin impacto en este run: existe un archivo
`part11_prompts.yaml` fantasma en
`factory/workspaces/gmpai_document_validation/prompts/` (v1.0.0, sin
`criterion_assessments`, resto de la Fase A original) que no lo carga
ningún flujo de producción (`PROMPTS_DIR` apunta a `factory/engines/
gmpai_integrity/prompts/`). No se tocó — queda como candidato a limpieza,
pendiente de decisión de Cesar.

## F1.4 — Recomendación

**F1 PASA el criterio pre-fijado.** El ancla de la evidencia conocida (caso
P1) se demostró bajo H2H4 con el runner real de producto, con registro
completo y latencia medida. El hallazgo secundario (violación de contrato
del modelo en 2/9 criterios del propio chunk ancla) no es un defecto de
código o de prompt — es un dato más sobre el comportamiento real del modelo
bajo H2H4, y se recomienda llevarlo explícitamente a la decisión de F2/F3:
con ~29 llamadas por requisito en F2, es esperable que esta clase de
violación aparezca de nuevo y siga siendo excluida correctamente por la
capa D (no es necesario ni deseable "arreglarla" aflojando el validador).

**Pendiente de Cesar, no decidido por el agente:**

1. Confirmar el congelamiento de la configuración (regla de congelamiento
   del plan): `prompt_version=1.1.1`, `schema_version=checkpoint_llm_response_v1`,
   `model_digest=845dbda0...`, `catalog_version=2.1`, `evaluation_profile=H2H4`,
   chunking tal como corrió — este fingerprint regirá F2/F3.
2. Autorización de presupuesto separada para F2 (~35 llamadas, tope con
   margen) — no incluida en esta firma.
3. Decisión sobre el archivo `part11_prompts.yaml` fantasma en
   `factory/workspaces/gmpai_document_validation/prompts/` (limpiar o dejar).
