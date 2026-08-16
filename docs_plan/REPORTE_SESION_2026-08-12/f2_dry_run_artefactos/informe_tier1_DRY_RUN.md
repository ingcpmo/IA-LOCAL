# Informe Tier-1 asistido — RW-0005

Agente: `fda_part11_agent` · Run: `chunked-943a62bcbb85` · Generado: 2026-08-12T17:37:36.613923+00:00

> Este informe es un BORRADOR ASISTIDO, no una declaración de cumplimiento. CONFIRMED significa que el verificador ancló una cita textual real -- sigue pendiente de sign-off humano final. Ningún requisito de este informe cierra CAPA, libera lote, ni constituye aprobación automática de documento (CLAUDE.md, sin excepción).

> Candidatos de recuperación semántica (cuando aplican): Estos candidatos son RECUPERACION (BM25 + embeddings semanticos, fusionados por RRF), NO evidencia validada -- ningun candidato tiene anclaje A/B/C/D. La medicion 7/7 en recall_at_5 es del fixture de referencia (docs_plan/R2_2_CIERRE_Y_CAPA_SEMANTICA.md §4.4); en un documento nuevo la recuperacion NO garantiza que la evidencia real este dentro de este top-k. Revisa los pasajes, no los asumas correctos.
> **DRY_RUN_FROM_HISTORICAL_CHECKPOINT (R3-T1.5 bloque 1, replay acotado, 2026-08-12)** -- este informe NO es un producto entregable. Se generó reconstruyendo la consolidación A/B/C/D con las mismas funciones de producción (absence_consolidator.consolidate, apply_conclusion_preconditions, semantic_evidence_verification.verify_sufficiency_aggregated con el fix B3 -- commit `e823015`) sobre los datos ya guardados del checkpoint histórico `chunked-943a62bcbb85` (perfil BASELINE, 2026-08-11). evaluate_chunked() no soporta reabrir un checkpoint completed=True (guardia deliberada, ver docs_plan/R3_T1_5_F2_DRY.md bloque 1), así que este informe NO pasó por esa función -- es una reconstrucción fiel de su tramo de consolidación, no una corrida nueva del motor. No reemplaza una corrida H2H4 real ni constituye un informe Tier-1 válido para revisión de producto.

## Resumen por bucket

- **Confirmado (anclado, pendiente de sign-off humano)**: 1
- **Necesita revisión humana**: 2
- **No aplica**: 0
- **Remite a otro documento**: 1
- **Opcional, no observado (sin acción requerida)**: 1

## Detalle por requisito

| Requisito | Estado | Conclusión | Cita / referencia |
|---|---|---|---|
| 21_CFR_11.10(a) | Remite a otro documento | CROSS_REFERENCE_MISSING | evidencia esperada en: RA, IQ, OQ, PQ |
| 21_CFR_11.10(d) | Necesita revisión humana | EVALUATION_INCOMPLETE | cola de revisión: `finding-chunked-943a62bcbb85-21_CFR_11.10(d)` (p. 43-44) |
| 21_CFR_11.10(e) | Confirmado (anclado, pendiente de sign-off humano) | PROVISIONALLY_PARTIALLY_DOCUMENTED | «[headline derivado de citas por criterio verificadas] UR3.3.1 Every time a critical alarm threshold is modified and audit trail record shall be generated. The record shall contain the following fields
1. Date and time stamps of the change
2. Original threshold value
3. Threshold value after change
4. User ID of the individual who has changed the threshold value (performer)
5. Full name of the individual who has changed the threshold value (performer)
6. Meaning of signature (performer)
7. User ID of the individual who has approved the change (approver)
8. Full name of the individual who has approved the change (approver)
9. Meaning of signature (approver).» (p. 45-46) [fuente pendiente de reverificación] |
| 21_CFR_11.10(g) | Necesita revisión humana | PROVISIONAL_GAP | cola de revisión: `finding-chunked-943a62bcbb85-21_CFR_11.10(g)` (p. 13-14, p. 39-40, p. 49-50) |
| 21_CFR_11.50_11.70 | Opcional, no observado (sin acción requerida) | NOT_OBSERVED_OPTIONAL | aplicabilidad opcional para este tipo documental, sin evidencia observada (p. 13-14, p. 39-40, p. 49-50) |
