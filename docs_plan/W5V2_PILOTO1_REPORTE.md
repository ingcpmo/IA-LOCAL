# W5 V2 — Piloto 1 (Representatividad): reporte de resultado

AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
Fecha: 2026-08-08. Ejecución: `pilot-2026-08-08-001` (`factory/regulatory/pilot_run/`).

`PILOT1_ROOT_CAUSE = MODEL_RECALL_LIMITATION` (pipeline verificado correcto).
`CORPUS_READY = false`. `PRODUCTION_ENABLEMENT = BLOCKED`.

## 1. Qué se ejecutó

8 llamadas reales (`run_context=pilot`, familia de decisión `PILOT_EXECUTION`
separada de `CORPUS_AUTHORIZATION`/D4, checkpoints/manifests aislados en
`factory/regulatory/pilot_run/`), 4 agentes × 2, contenido real (sin
sintético), modelo `qwen2.5:7b-instruct-q4_K_M`.

| # | documento | agente | requirement_id | página real (0-based) | motivo |
|---|---|---|---|---|---|
| 1 | RW-0005 (FS_v1.2) | fda_part11_agent | 21_CFR_11.10(e) | 45 | Audit trail records shall be archived / logins-logouts-login attempts registrados |
| 2 | RW-0005 (FS_v1.2) | fda_part11_agent | 21_CFR_11.10(g) | 39 | Sección 4 Security / F09.00 Physical Security, control de acceso |
| 3 | RW-0005 (FS_v1.2) | eu_annex11_agent | ANNEX11_4 | 1 | Caso CONOCIDO de falso positivo: "GAMP5" en lista de referencias numeradas |
| 4 | RW-0005 (FS_v1.2) | eu_annex11_agent | ANNEX11_12 | 44 | UR3.3.6 Data retention — 1 año, archivado en ubicación alterna |
| 5 | RW-0011 (EMS Control Block Narrative) | alcoa_plus_agent | ALCOA_ATTRIBUTABLE | 12 | Acción atada a credenciales/identidad real |
| 6 | RW-0005 (FS_v1.2) | alcoa_plus_agent | ALCOA_CONTEMPORANEOUS | 45 | Mismo pasaje de audit trail (#1), contemporaneidad |
| 7 | RW-0011 | fda_cgmp_211_agent | 21_CFR_211.68(b) | 12 | Mismo pasaje de credenciales/calibración (#5) |
| 8 | RW-0012 (PCS Signal Interface) | fda_cgmp_211_agent | 21_CFR_211.68(b) | 13 | Pasaje casi idéntico a #7 en documento REAL DISTINTO (SHA-256 distinto) |

## 2. Resultado técnico

`8/8` llamadas `COMPLETED`, `stop_reason=CORPUS_COMPLETE`, 7778s (~2h10min)
de wall time. `1/8` (#2, page 39) con `technical_execution_failures=1`.

## 3. Resultado sustantivo — recall 0/7

De los 40 registros de requirement verificados en las 7 llamadas exitosas,
**0 salieron `observed`** — el pipeline verificado nunca reportó una cita
anclada para ninguno de los 7 casos POSITIVOS seleccionados a mano
(evidencia sustantiva confirmada por lectura directa del PDF).

**El control NEGATIVO sí funcionó** (`ANNEX11_4`, #3): correctamente
rechazado como `not_observed_in_chunk` en ambas corridas del agente
`eu_annex11_agent` — confirma que `detect_reference_list_context` sigue
rechazando bien el falso positivo conocido (GAMP5 en lista de referencias)
contra contenido real, no solo contra el Golden Dataset.

## 4. Descarte de causas de infraestructura

- **Extracción de página**: verificada byte a byte. La página 45 (0-based)
  de RW-0005 contiene exactamente el texto esperado ("UR3.3.3 Audit trail
  records shall be archived... Logins, logouts, and login attempts must be
  recorded..."), `text_chars=2300` — coincide EXACTO con el checkpoint real.
  No hay error de indexación de página.
- **`page_start: 1` en el checkpoint**: no es un bug — `build_page_chunks()`
  numera localmente dentro del extracto corto que recibe (una sola página),
  así que la página real 45 se etiqueta "1" del extracto. Cosmético, no
  afecta el contenido evaluado.
- **Truncamiento por `num_predict`** (la hipótesis del post-mortem previo,
  `W5v2_POSTMORTEM_TRUNCAMIENTO_NUM_PREDICT.md`): descartada mediante
  reproducción aislada (ver §5) — `done_reason=stop`, `eval_count=3059/4096`,
  no se agotó el presupuesto.

## 5. Reproducción aislada (diagnóstico, fuera de piloto/corpus)

Llamada de diagnóstico contra Ollama directo (mismo prompt real construido
por `build_prompt()`, misma página 45, mismo modelo, `num_predict=4096`
derivado de `output_token_budget()`), sin checkpoint, sin contar como
llamada de piloto/corpus.

```
done_reason=stop, eval_count=3059, prompt_eval_count=3203
wall_seconds=1428.7 (~24 min)
parseo: OK, schema válido
21_CFR_11.10(e): estado=cumple_parcialmente, evidencia_exacta=""
  9/9 criterion_assessments = NOT_ASSESSABLE, justificación tipo
  "no se menciona en el documento proporcionado"
```

El modelo tuvo el texto correcto delante y no lo conectó con los criterios
pedidos — marcó los 9 criterios como no evaluables con la página completa
en el prompt. `evidencia_exacta` vacía ⇒ el pipeline verificado no puede
anclar cita ⇒ se descarta como `not_observed_in_chunk`, igual que en la
corrida real. **Es una limitación de recall del modelo, no del pipeline.**

**No-determinismo observado**: la corrida real dio `not_observed_in_chunk`
en los 5 requirements de esta llamada; la reproducción aislada (mismo
prompt, mismo modelo, `temperature=0.0`) dio `cumple_parcialmente` en los 5
(igual sin cita). A `temperature=0.0` no debería haber variación — sugiere
no-determinismo del runtime cuantizado en CPU (orden de threads/batching).
Queda como hallazgo abierto para H6 del plan de remediación.

## 6. Fallo técnico 1/8 (llamada #2, página 39)

`run_id=chunked-04c431b29c1a`, `failure_reason=schema_validation_failed`.
No fue truncamiento (`raw_response_truncated_in_log=False`, 3902 caracteres
completos, JSON bien formado). El modelo generó un JSON válido pero
**estructuralmente incorrecto**: en vez de anidar `criterion_assessments`
dentro de cada uno de los 5 checkpoints, generó un 6º objeto separado que
solo contiene `criterion_assessments` sin `req_id`/`estado`.
`_validate_checkpoint_schema()` lo rechazó correctamente — el fail-closed
funcionó como debía. Consistente con el no-determinismo del §5: es
inestabilidad estructural del modelo al generar JSON anidado complejo, no
un bug del motor.

## 7. Gobernanza del modelo (cambio qwen/mistral)

Verificado contra `decisions_v2.jsonl`, `qualification_record.json` y
`git log`: **no hay swap de modelo sin gobernanza**. `qwen2.5:7b-instruct-
q4_K_M` es el único modelo que ha existido en la historia de git de
`ollama_client.py` y de `qualification_record.json` para este pipeline
(W5V2/chunked_engine); nunca hubo mistral configurado aquí. Las menciones
de mistral en el repo pertenecen a un experimento distinto
(`W6_5_FASE_D_CIERRE_EXPERIMENTO.md`, misión `oos_hplc_investigator`,
2026-07-06), donde Cesar aprobó formalmente abandonar mistral por qwen tras
una comparación objetiva desfavorable a mistral — precedente documentado,
no desviación.

**La brecha de gobernanza real es otra**: la calificación `QUALIFIED` de
qwen (2026-08-07T21:36:24Z, Golden Dataset 17/17) midió
`false_negative_rate=0.0` sobre **1 solo caso sintético**
(`incomplete_coverage_never_gap`) — nunca hubo un caso de recall contra
evidencia positiva real de un documento del corpus. Por eso el gate no
detectó el problema de recall que el Piloto 1 sí encontró (0/7). Esto
confirma la necesidad del fixture set de recall (Bloque 2 del plan de
remediación) y de un piso de recall bloqueante en el gate de calificación
(§4.1 del mismo plan).

## 8. Conclusión

`PILOT1_ROOT_CAUSE = MODEL_RECALL_LIMITATION`. Pipeline (extracción,
chunking, fail-closed, verificador determinista, control negativo)
verificado correcto en cada punto. El modelo 7B cuantizado, con 5
requirements empaquetados por llamada y un schema verboso por criterio, no
reconoce evidencia textual explícita incluso cuando está literalmente en el
prompt, y muestra variabilidad entre corridas idénticas. Corpus formal en
NO-GO hasta remediación — ver `W5V2_REMEDIACION_RECALL_MODELO.md`.
