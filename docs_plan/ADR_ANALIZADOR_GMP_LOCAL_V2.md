# ADR — ANALIZADOR DOCUMENTAL GMP LOCAL V2

**ADR-ID:** ADR-ANALIZADOR-LOCAL-V2
**Estado:** PROPUESTO — pendiente de firma de Capa 9. No implementado.
**Fecha:** 2026-08-27. **Autoridad de decisión:** Capa 9 = Cesar.
**Fuentes:** `REDISENO_ANALIZADOR_GMP_LOCAL_V2.md`, `ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md`, `MATRIZ_GAP_CURRENT_VS_V2.md`, skill `gmp-recall-pipeline`, `PAQUETE_DECISION_ESTRATEGICA.md`.

---

## 1. Context

El Analizador Documental GMP (CURRENT) debe: analizar documentación GMP mediante IA **local**, identificar hallazgos **regulatorios, funcionales y técnicos**, detectar **desviaciones e inconsistencias entre documentos**, mantener **evidencia y trazabilidad completas**, **calcular riesgo**, generar **recomendaciones y correcciones**, producir **borradores corregidos/redline/manifest**, y hacerlo **sin enviar documentos del cliente a proveedores externos**.

Estado verificado (auditoría 2026-08-27, `VERIFICACION_OBJETIVO_ANALIZADOR_20260827.md`):

- `PRODUCTION_ENABLEMENT = BLOCKED`, `REGULATORY_COMPLIANCE = NOT_DETERMINED`, `CORPUS_READY = false`.
- Recall de juicio regulatorio: **1–2/7** contra gate **≥6/7**. Confirmado por 4 vías independientes (H1-H4; qwen2.5:14b; fusión RRF con pool perfecto; criterio pre-fijado de Cesar 1/6 ≤ 3/6).
- Causa raíz (FASE 1): `SEMANTIC_JUDGMENT_FAILURE` en 5/6 casos medibles — el 7B local no cruza pasaje técnico → criterio regulatorio abstracto sin eco léxico ("PARÁFRASIS").
- `FunctionalFinding` y `TechnicalFinding` **no existen** como clase. No hay conocimiento cross-documento. `requirements_traceability_agent` está en el catálogo pero desconectado del pipeline CURRENT.
- Hardware: 19 GB RAM, 12 CPU, **sin GPU**.
- Restricciones de Capa 9 para esta misión: `LOCAL_ONLY`, `DOCUMENT_EGRESS = FORBIDDEN`, `EXTERNAL_LLM_API = FORBIDDEN`, no aumentar infraestructura sin marcarla `OPTIONAL_INFRASTRUCTURE` + variante ejecutable.

## 2. Decision

Adoptar la **arquitectura V2 LOCAL-ONLY** de `ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md`, cuyo eje es **reducir el salto semántico exigido al 7B en cada llamada**, moviendo trabajo del LLM a estructura determinista y a contenido autorado una sola vez:

1. **Modelo canónico documental** (FASE 2): el LLM de juicio deja de leer páginas planas; recibe `Claim.normalized_statement` + sub-criterio concreto.
2. **Descomposición estática de requisitos** (FASE 4): `requirements.yaml` gana `decomposition[]` — sub-criterios atómicos autorados y gobernados. Cero LLM en runtime.
3. **Retrieval V2** (FASE 4): + reranker cross-encoder **local** (CPU, ~80 MB); salida = `EvidenceBundle` acotado, no un pool a re-chunkear.
4. **Juicio en 2 pasos** (FASE 6, = Palanca V2b): descripción operativa neutra → mapeo al sub-criterio. Guardián: la cita citable es **siempre** `Claim.source_text`.
5. **Critic + Adjudicator** (FASE 6): un segundo prompt local independiente intenta refutar; el Adjudicator (determinista) combina Hunter + Critic + `evidence_verifier` (sin cambios) con reglas fail-closed.
6. **Extracción estructurada de tablas** (FASE 9): objeto `Table` con headers/rows/celdas y provenance.
7. **Evidence/Knowledge graph local** (FASE 3): SQLite sobre el Postgres ya levantado o JSON en disco. **No Neo4j.** Habilita desviaciones e inconsistencias cross-documento.
8. **Taxonomía de 7 clases de Finding** (FASE 7): `Regulatory/Functional/Technical/Traceability/DataIntegrity/Security/TestCoverage`, cada una con campos mínimos y `machine_state`/`human_state` separados.
9. **Agentes FUNCTIONAL (4) y TECHNICAL (4)** (FASE 5): nuevos, sobre el mismo 7B local, operando contra el grafo — nunca contra texto crudo.
10. **Riesgo determinista** (FASE 7): tabla RPN gobernada, nunca un número del LLM.
11. **Migración en shadow mode** (FASE 11): CURRENT se conserva íntegro para rollback.

**La revisión humana NO se elimina.** `human_state` de todo Finding inicia `UNREVIEWED` y solo un humano lo cambia. La IA puede generar `MACHINE_CONFIRMED_FINDING`, `MACHINE_DEVIATION_CANDIDATE`, `MACHINE_REMEDIATION_PROPOSAL`, candidate/redline/manifest — **nunca** `QA_APPROVED / RELEASED / CAPA_CLOSED / FINAL_GMP_APPROVAL`. Esta separación no bloquea la ejecución del análisis ni la producción de resultados: el sistema corre y entrega artefactos sin esperar a un humano; lo que espera al humano es el cambio de estado a aprobado.

## 3. Alternatives considered

| Alternativa | Descripción |
|---|---|
| **A. Palanca A — modelo local ≥32B** | Reemplazar 7B por 32B/70B local en juicio |
| **B. Palanca B — proveedor externo (`AnthropicProvider`)** | Enrutar el juicio a una API externa |
| **C. Palanca C — Tier-1 alcance reducido, sin rediseño** | Operar CURRENT tal cual, alcance declarado a lo medido (eco léxico + rechazo de falsos positivos + recuperación al revisor), todo lo demás a revisión humana |
| **D. V2b sola** | Solo el juicio en 2 pasos, sin modelo canónico ni grafo ni clases nuevas |
| **E. Eliminar la revisión humana, reemplazarla por un agente** | Un agente "revisor" cierra los hallazgos automáticamente |
| **F. V2 completa LOCAL-ONLY** | La decisión de §2 |

## 4. Rejected alternatives

- **A (modelo local ≥32B):** RECHAZADA por hardware — no cabe en 19 GB RAM, requiere GPU (`OPTIONAL_INFRASTRUCTURE`, prohibido como base). Además 7B→14B ya se probó **sin mejora** (Palanca A, 2026-08-15). Puede reconsiderarse como opcional si Capa 9 autoriza GPU.
- **B (proveedor externo):** RECHAZADA — viola `DOCUMENT_EGRESS = FORBIDDEN` y `EXTERNAL_LLM_API = FORBIDDEN`. Enviaría chunks de documentos de cliente real (Mark Cuban Cost Plus Drug Company, per el propio documento) fuera del servidor. No se retoma bajo las restricciones de esta misión.
- **C (Tier-1 sin rediseño):** NO rechazada — se adopta como **piso operativo y como resultado de contingencia**. No cumple el objetivo completo (no da recall ≥6/7, no da findings funcionales/técnicos). Es lo correcto SI V2 no cruza el gate en FASE 10.
- **D (V2b sola):** RECHAZADA como solución completa — V2b ataca solo el contrato de juicio; no resuelve findings funcionales/técnicos, cross-documento, ni tablas. Se **incluye** dentro de V2 (punto 4).
- **E (agente que reemplaza la revisión humana):** RECHAZADA, sin margen. (1) Viola regla permanente no negociable de `CLAUDE.md` ("la IA no sustituye a QA", "sin aprobación automática", "mantiene revisión humana"). (2) No funciona: el agente revisor sería el mismo 7B con el mismo techo de recall — pediría a un modelo que falla el 83 % de los casos que sea la autoridad final, sin control compensatorio. Convierte incertidumbre honesta en error silencioso. (3) El objetivo declara mantener "evidencia y trazabilidad completas" y "revisión humana" — eliminar la revisión contradice el propio objetivo.

## 5. Consequences

**Positivas**
- Ataca la causa raíz confirmada (`SEMANTIC_JUDGMENT_FAILURE`) sin salir del servidor ni añadir hardware.
- Trazabilidad pasa a ser propiedad estructural (provenance obligatorio en todo objeto derivado).
- Habilita por primera vez findings funcionales, técnicos y cross-documento.
- CURRENT se conserva; rollback siempre disponible.
- El trabajo caro (descomposición de requisitos) es autoría única, no costo de runtime.

**Negativas / costo**
- **~2× latencia por requisito** (juicio en 2 pasos + Critic). Sobre ~250–600 s/llamada actuales en CPU, es material.
- Superficie de código nueva grande: modelo canónico, grafo, 8 agentes nuevos, reranker, Critic/Adjudicator, 2 suites de benchmark.
- **Sin garantía de éxito.** El rediseño es necesario, no demostrado suficiente. Ninguna palanca local previa movió el recall; ninguna, sin embargo, atacó estructura + contrato de juicio a la vez.
- La descomposición de requisitos es contenido gobernado nuevo — carga de mantenimiento con firma por cada versión.
- El reranker local añade un modelo más a descargar (`OPTIONAL`, requiere autorización de Capa 9 para el pull).

**Contingencia declarada:** si FASE 10 no alcanza `REGULATORY_POSITIVE ≥ 6/7` con V2 local, se adopta Palanca C permanente (Tier-1 alcance declarado). No se degrada ningún validador ni se habilita auto-aprobación para "cerrar" la brecha.

## 6. Security

- **Sin nueva superficie de red.** Ningún componente de V2 abre puertos ni hace egress. El reranker y el segundo prompt corren en el `aria-ollama` local ya existente / proceso local.
- **openFDA** se mantiene idéntico: 1–10 registros/consulta, ≤10/día, `run_by` humano, no alimenta decisiones GMP. No se amplía.
- **Secretos:** V2 no introduce credenciales nuevas (no hay API externa). Los pendientes I1/I2 (control.key versionado, secretos del origen) son deuda operativa **separada**, no bloquean ni son tocados por esta misión.
- **Audit trail** append-only con hash-chain (`audit_writer.py`) se conserva sin cambios; todo evento nuevo de V2 (extracción, normalización, juicio, adjudicación, finding, remediación) emite su evento.
- **Modelo de amenaza del juicio en 2 pasos:** el paso 1 (descripción neutra) podría ser canal para fabricar evidencia. Mitigación por diseño: la cita citable es **siempre** `Claim.source_text` verificado por `evidence_verifier` sin cambios; el paso 1 nunca es evidencia. El Critic añade una segunda lectura adversarial.

## 7. Privacy

- **`DOCUMENT_EGRESS = 0` es invariante de diseño**, verificable: ningún módulo de V2 tiene cliente HTTP hacia fuera del servidor. Test de FASE 10 (`LOCAL_ONLY = YES`, `DOCUMENT_EGRESS = 0`) lo comprueba (bloqueo de red saliente durante una corrida completa; si algo intenta salir, falla).
- Los documentos del cliente (Rockwell / MCCPDC) nunca dejan `ivr-ia`. El modelo canónico, el grafo, los índices y los checkpoints son todos locales en disco.
- Datos personales en documentos (nombres de operadores en tablas de audit trail): el objeto `Actor` guarda `nombre_rol`, y `Table.rows` puede contener nombres — se persisten local, con el mismo control de acceso del resto del `factory/`. No se exportan.

## 8. GMP impact

- **Refuerza**, no debilita: provenance obligatorio, evidencia anclada A/B/C/D sin cambios, fail-closed en ausencia (Critic añade una barrera más), audit trail intacto.
- **Sin declaración de cumplimiento final por el sistema** — se mantiene. `machine_state` nunca es `QA_APPROVED`.
- **Sin aprobación automática de documentos, sin cierre automático de CAPA, sin liberación de lote** — se mantiene. Los `candidate/redline/manifest` llevan marca obligatoria "MACHINE GENERATED — BORRADOR, NO APROBADO".
- El documento original nunca se sobrescribe (candidate es archivo nuevo).
- Riesgo GMP nuevo introducido: **findings funcionales/técnicos sin baseline de validación** — mitigado exigiendo las suites B y C (FASE 10) firmadas por Capa 9 antes de que esas clases se consideren operables.
- 21 CFR Part 11: el audit trail del analizador ya opera con excepción histórica documentada (`ACCEPTED_WITH_DOCUMENTED_EXCEPTION`); V2 no la altera.

## 9. Rollback

- CURRENT permanece **desplegado e íntegro** durante todo el desarrollo de V2 (shadow mode). No se borra código, prompts, índices ni checkpoints de CURRENT.
- V2 corre en paralelo con salidas a rutas separadas (`pilot_run/v2_shadow/…`) y **sin efectos** (no encola, no emite directivas reales, no escribe audit de producción) hasta el cutover.
- Cutover = cambio de un flag de routing en `corpus_runner`, reversible en 1 commit.
- Post-cutover: CURRENT queda como fallback seleccionable por Capa 9 (mismo flag) mientras exista al menos una corrida V2 con incidente abierto.
- Los artefactos gobernados nuevos (`decomposition[]` en `requirements.yaml`) se versionan; revertir = volver a la versión previa del catálogo.

## 10. Acceptance gates

Ninguna fase de V2 se promueve a producción sin **todos** los gates de su alcance en verde. Detalle y comandos en `PLAN_VALIDACION_ANALIZADOR_GMP_LOCAL_V2.md`.

```
# Regulatory (fixture 7P+2N conservado, instrumento único)
REGULATORY_POSITIVE        >= 6/7   con cita anclada A/B/C/D
REGULATORY_NEGATIVE        = 2/2    (N1 reference-list, N2 TOC — rechazados)
FABRICATED_CITATIONS       = 0

# Functional (fixture nuevo, 20 casos, firma de Capa 9 como Golden Dataset)
FUNCTIONAL_RECALL          >= 90%
FUNCTIONAL_FALSE_POSITIVE  <= 5%

# Technical (fixture nuevo, 20 casos, firma de Capa 9)
TECHNICAL_RECALL           >= 90%
TECHNICAL_FALSE_POSITIVE   <= 5%

# Transversales
TRACEABILITY_COMPLETE      = YES   (todo Finding con provenance completo + graph_path si aplica)
LOCAL_ONLY                 = YES   (corrida completa con egress bloqueado, sin fallos)
DOCUMENT_EGRESS            = 0
AUDIT_CHAIN                = VERIFIED / ACCEPTED_WITH_DOCUMENTED_EXCEPTION  (sin nuevos forks)
HUMAN_GATE_INTACT          = YES   (ningún path convierte machine_state en QA_APPROVED)
GATE_0_FACTORY             = PASS  (factory_selfcheck.sh, sin regresión)
```

**Si `REGULATORY_POSITIVE < 6/7` tras V2 completa:** no se promueve el juicio automático regulatorio; se adopta Palanca C (Tier-1) para la clase Regulatory y se evalúa por separado si Functional/Technical alcanzan sus gates (son independientes).

---

## Firma

```
DECISION           = PROPUESTA
FIRMA_CAPA_9        = PENDIENTE
IMPLEMENTACION      = NO INICIADA
CODIGO_MODIFICADO   = 0
LLAMADAS_LLM        = 0
DESCARGAS           = 0
COMMIT              = NO
```

---

## ADDENDUM — Cierre del plan original V2 (2026-08-28)

El plan original del Analizador GMP LOCAL V2 se completó de FASE 0 a FASE 12.
Acta consolidada fase por fase, con evidencia:
**`docs_plan/ACTA_CIERRE_ANALIZADOR_GMP_LOCAL_V2.md`**.

Puntos firmes:
- Arquitectura V2 **congelada** en su diseño actual.
- REGULATORY_GATE = **FAIL** (recall LLM 0/7) — contingencia determinista aceptada:
  **Regulatory Tier-1 / Palanca C**. NO se reinterpreta como PASS.
- FUNCTIONAL_GATE = **PASS** (16/16 recall, 0 FP — fixture de inyección de defectos).
- TECHNICAL_GATE = **PASS** (benchmark Suite C: TP=9, FN=C07 semántico, FP=0, recall 0.90;
  transversales LOCAL_ONLY / DOCUMENT_EGRESS=0 / FABRICATED_CITATIONS=0 / TRACEABILITY=YES).
- `technical_completeness_rules.yaml` **v1.1 SIGNED** (OD-6: alcance context-scoped).
- REPORTING_GAP **cerrado**: runtime V2 E2E (`v2_runtime.py`) persiste bajo
  `GMPAI/reports/gmpai_document_validation/<run_id>/`; Mission Control lo expone vía `/api/v1/v2-analyzer/*` (API). La UI
  `mission_control.html` aún NO consume esos endpoints (no se construye UI nueva). Shadow mode ejecutado, CURRENT retenido, cutover NO ejecutado.
- Regresión: 2779 passed / **5 failed** (deuda de clon/servicio-en-vivo, EXC-1..EXC-5,
  0 tocan V2) — `docs_plan/DEUDA_REGRESION_EXCEPCION_CAPA9.md`. **pytest exit code real = 1.**
