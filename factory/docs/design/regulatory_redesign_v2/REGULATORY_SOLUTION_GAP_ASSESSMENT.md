# REGULATORY_SOLUTION_GAP_ASSESSMENT

Puente entre la corrida exploratoria URS v2.1 (baseline 3.1 del plan +
`CURRENT_AGENT_RUNTIME_AUDIT.md`) y el diseño objetivo W5 V2.

| Componente objetivo | Qué falta hoy | Agente responsable | Fase que la cierra | Riesgo si no se cierra |
|---|---|---|---|---|
| ModelProvider / abstracción de proveedor | No existe ninguna clase, 2 clientes Ollama duplicados y acoplados directamente | D (transversal) | D | Cambiar de modelo exige reescribir 6+ archivos; imposible portabilidad ni Model Qualification Gate real |
| Requirement Evidence Pack | El baseline solo pasó requirement_id + descripción breve (confirmado, 121 llamadas) | AGT-REP | C | Falsos positivos semánticos como ANNEX11_4 se repiten estructuralmente |
| Validación B (fuente regulatoria) | `evidence_verifier.py` valida anclaje en el documento (A), no existencia en copia canónica (B) | AGT-VER | F | Conclusiones positivas sin verificación real contra texto normativo |
| Regla determinista anti-ANNEX11_4 (exclusión de listas de referencias) | Hoy es heurística léxica (`RELEVANCE_THRESHOLD`) que solo marca revisión, no rechaza | AGT-VER (validación C) | F | Riesgo recurrente de falso positivo semántico no bloqueado automáticamente |
| Criterios deterministas de riesgo LOW/MEDIUM/HIGH | `risk_agent.py` calcula un score continuo, no bandas de gobernanza de autoaplicación | AGT-GAP | I | Sin bandas, no puede implementarse autoaplicación gobernada (R-2) de forma segura |
| AGT-REM (generación de correcciones) | No existe código, ninguna versión previa | AGT-REM | I | Núcleo del objetivo del plan (documentos corregidos) sin base alguna |
| AGT-QLT (calidad de documento completo) | No existe código | AGT-QLT | I/K | Candidatos sin control de coherencia/terminología automatizado |
| Motor de generación por formato (DOCX/PDF/XLSX/DOCM) | Solo scripts ad-hoc de una corrida puntual (FS_v1.2) | AGT-DOC | J | Sin generalización, cada documento requiere trabajo manual repetido |
| Los 9 artefactos del paquete profesional | Ninguno generado de forma estandarizada hoy | AGT-DOC | M | Entregables inconsistentes, sin manifest verificable |
| CORRECTED_DOCUMENT_GENERATION_GATE | No existe | Validador determinista | N | Sin gate, no hay forma objetiva de bloquear candidatos incompletos |
| AGT-RVL (revalidación independiente) | No existe ningún componente que compare original vs. candidato de forma independiente | AGT-RVL | O | Riesgo de que un cambio mal aplicado se autoconfirme |
| QA_FINAL_PACKAGE con 4 decisiones | No existe endpoint ni modelo de datos | QA-HUM | P | Sin punto de decisión formal, no hay cierre gobernado del ciclo |
| Catálogo regulatorio con schema completo | PDFs con hash existen, faltan `history`, `retrieved_by`, `reverification_due` versionados | AGT-RSG | B | Cambios de fuente no auditables por completo |
| Allowlist cerrada de Rockwell | No existe (solo inventario ad-hoc de esta corrida) | AGT-INV | A | Riesgo de omitir archivos silenciosamente en corridas futuras |
| Servicio de inferencia compartido (cola, circuit breaker) | Existe checkpoint/resume parcial (`1c16686`), falta cola compartida entre agentes y circuit breaker | Transversal | D/G | Sin cola compartida, 11 agentes competirían por Ollama sin control de concurrencia |
| Baseline formal (25 review_required + 3 rejected_by_verifier) | Pendiente de adjudicación humana (Cesar), confirmado en sanitización URS v2.1 | Humano (Cesar) | H | Ningún requisito relacionado puede declararse `DOCUMENTATION_GAP` mientras estén pendientes |

## Brechas críticas (bloquean todo el resto si no se resuelven primero)

1. **ModelProvider** (Fase D) — sin esto, todo agente híbrido nuevo se
   construiría de nuevo acoplado a Ollama, repitiendo la deuda actual.
2. **Requirement Evidence Pack + regla anti-ANNEX11_4** (Fases C/F) — sin
   esto, el riesgo de falso positivo semántico persiste estructuralmente,
   no solo como caso aislado corregido manualmente.
3. **Adjudicación humana de los 28 registros pendientes** (Fase H) — es la
   única brecha que depende de una decisión externa a Claude Code y
   bloquea declarar cualquier baseline formal.

## Es el puente hacia la corrida URS v2.1

Esta tabla conecta explícitamente los 10 puntos de baseline aceptado
(sección 3.1 del plan) con los componentes de diseño objetivo: el punto 4
(121 llamadas, descripciones breves) se cierra en AGT-REP/Fase C; el punto
7 (ANNEX11_4) se cierra en AGT-VER/Fase F; el punto 10 (25 review_required
+ 3 rejected_by_verifier, baseline formal pendiente) se cierra en Fase H
con adjudicación humana explícita, no automatizable.
