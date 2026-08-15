# I. Registro de riesgos

**Estado**: consolidado de riesgos identificados en las Pistas A y B.
Ninguno de estos riesgos se ha materializado por esta auditoría misma
(auditoría = 0 código cambiado).

| # | Riesgo | Pista | Probabilidad | Impacto | Mitigación propuesta |
|---|---|---|---|---|---|
| R1 | Construir Table/EvidenceUnit completo para P6/P7 sin confirmar causalidad, y que no mueva el resultado (mismo patrón que P2/P5: evidencia perfecta, juicio sin cambio) | A | Media-alta — ya ocurrió una vez con recuperación perfecta | Medio (esfuerzo desperdiciado, no riesgo de gobernanza) | Secuencia obligatoria del `EXPERIMENT_PLAN.md`: no construir antes de medir (Fase 1 gratis, Fase 3 máximo 2 llamadas) |
| R2 | Asimetría furniture LLM/verificador seguir sin corregir, produciendo evaluaciones sobre texto con ruido que el verificador nunca ve | A | Baja impacto individual, pero sistemática (afecta a TODO chunk con furniture, no solo casos conocidos) | Bajo-medio | Fase 0 de `IMPLEMENTATION_PLAN.md`, barata, sin LLM |
| R3 | Confundir "el modelo no encontró evidencia" (recall bajo) con "un gate posterior descartó una cita que sí ancló" — patrón ya real una vez (R1.6, `_is_topically_relevant`) | A | Media — el pipeline sigue evolucionando, nuevo gate podría reintroducir el patrón | Alto si no se detecta (falso negativo silencioso) | Regla ya derivada en `gmp-recall-pipeline`: siempre revisar gates posteriores antes de atribuir a fallo del modelo |
| R4 | `agent-self-evaluation` (ECC) usado para autoevaluar la corrección de un hallazgo GMP en vez de solo proceso de Capa 8 | B | Baja si se documenta el control explícito; media si se adopta sin el control | **Alto** — viola directamente el filtro de gobernanza IA (§19), cerca de que la IA certifique su propio juicio | Control explícito ya incorporado en `CONTEXT_ENGINEERING_ARCHITECTURE.md` Componente 3: prohibido para hallazgos GMP, permitido solo para proceso |
| R5 | `hooks/memory-persistence` de ECC adoptado como segunda fuente de persistencia, sin la regla dura "productizar y revalidar por flujo real" que ya tiene el sistema de memoria propio | B | Baja (documento recomienda RECHAZAR explícitamente) | Alto si se adopta de todos modos — mismo patrón que causó el incidente real de R1 (config ganadora en script ad hoc nunca productizada) | Rechazo explícito en `ECC_ADOPTION_MATRIX.md`, no adoptar |
| R6 | Instalación mayorista de ECC (`/plugin install`) por accidente o atajo, inyectando 284 skills/68 agentes al contexto de un sistema GMP bajo control de cambios | B | Baja (prohibición explícita ya conocida) | **Crítico** — dependencia externa no auditada en entorno regulado, interferencia impredecible con skills propios | Prohibición dura ya declarada en el brief (§B.3), reafirmada en `ECC_ADOPTION_MATRIX.md`: adopción siempre por reescritura, nunca copia mayorista |
| R7 | Contrato formal (Componente 1, P1) implementado relajando el `common_contract_sha256` existente en vez de formalizarlo — riesgo de que "formalizar" se convierta en "debilitar" | B | Baja | Alto (tocaría contenido gobernado sin `prompt_version` nuevo) | El diseño explícitamente mantiene el contenido de los 3 YAML gobernados sin tocar; cualquier cambio de schema requiere `prompt_version` nuevo y aprobación de Cesar |
| R8 | **CERRADO (2026-08-14)** — P4 queda sin diagnóstico | A | — | — | Diagnosticado en `CONTINUACION_FASE0_P4_FASE1.md` Bloque 0: P4 comparte literalmente el mismo chunk que P6 (RW-0011 p.12, mismo texto, distinto `requirement_id`), confirmado por re-extracción real dentro de `factory-api`. Mismo bucket de hipótesis que P6 (dilución tabular, no confirmada causalmente), sin costo experimental adicional — ver `BOTTLENECK_DIAGNOSIS.md` actualización 2026-08-14 |
| R9 | **CERRADO (2026-08-15)** — Checkpoint exacto de la corrida P6/P7 del Piloto 1 no estaba preservado | A | — | — | Cumplido: la corrida real de P4/P6 (`PILOT_EXECUTION-2026-010`, 2 llamadas, `evaluation_profile=H2H4`) preservó ambos checkpoints completos en `factory/regulatory/pilot_run/checkpoints/chunked-5a439f3fde11.checkpoint.json` (P4) y `chunked-554544f4090f.checkpoint.json` (P6) — ver `BOTTLENECK_DIAGNOSIS.md` actualización 2026-08-15 |

## Actualización 2026-08-14 (Bloque 2, verificación mecánica)

**R9 parcialmente activo todavía**: el checkpoint de la corrida de
juicio original de P4/P6/P7 sigue sin preservarse (solo se re-extrajo el
texto plano vía `pdfplumber`, sin correr el LLM). R9 se cierra
completamente solo cuando una corrida real de Fase 3 preserve su
checkpoint, conforme a lo comprometido en `CONTINUACION_FASE0_P4_FASE1.md`
2.3.

**Hallazgo nuevo, no un riesgo previsto**: la verificación mecánica
mostró que P7 (a diferencia de P6/P4) NO tiene dilución tabular en su
página — su prosa vive en contexto limpio. La agrupación "P6/P7 = misma
hipótesis" de la auditoría original era incorrecta. Este hallazgo se
documenta como corrección, no como nuevo riesgo numerado — ver
`BOTTLENECK_DIAGNOSIS.md`.

## Actualización 2026-08-15 (corrida real de P4/P6 — 2 llamadas LLM, PILOT_EXECUTION-2026-010)

**R10 — CERRADO (2026-08-15)** | El fix de furniture (Bloque 1) por sí solo no resolvía P4/P6; el experimento C real quedó pendiente de construir | A | — | — | Cumplido: se construyó la representación aislada real (tabla + cabecera removidas, prosa en contexto limpio, 1670 chars, verificación mecánica previa sin costo) y se ejecutaron 2 llamadas reales más (`chunked-8e2b20bfa511`/`chunked-510444cedc9b`, mismo `PILOT_EXECUTION-2026-010`). **Resultado: idéntico al de la corrida sin aislar** — la hipótesis de dilución tabular queda REFUTADA por experimento directo, no solo sin confirmar. Ver `BOTTLENECK_DIAGNOSIS.md` conclusión final |

## Riesgo transversal más importante de todo el documento

**Sobregeneralizar el techo de juicio del modelo (confirmado para P2/P5,
evidencia parafraseada) a P6/P7 (dilución tabular, causa distinta y no
confirmada)** — o al revés, asumir que el DOM resolverá P6/P7 sin haberlo
medido. Ambas direcciones de sobregeneralización están explícitamente
descartadas en `BOTTLENECK_DIAGNOSIS.md`. Este es el riesgo que más
puede desviar la inversión de esfuerzo del proyecto si se ignora.
