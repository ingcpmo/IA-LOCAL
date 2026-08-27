# PLAN DE VALIDACIÓN — ANALIZADOR GMP LOCAL V2

**Fecha:** 2026-08-27. **Autoridad:** Capa 9 = Cesar.
**Fuentes:** `ADR_ANALIZADOR_GMP_LOCAL_V2.md` §10, `ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md` FASE 10, skill `gmp-recall-pipeline`.
**Regla dura heredada:** el fixture de recall es el **único instrumento de medición**. **Prohibido aflojar validadores** (`evidence_verifier`, umbral fuzzy 0.93, exigencia de cita anclada, umbrales C/D) para inflar métricas. El problema de recall es del modelo, nunca de la estrictez del verificador.

---

## 1. Tres suites independientes

### Suite A — Regulatory (fixture existente, NO se cambia)

- **Instrumento:** `W5V2_RECALL_FIXTURE_SET_DRAFT.md` — 7 positivos + 2 negativos, verificados a mano (documento, página real, `requirement_id`, pasaje exacto).
- **Se conserva idéntico.** No se re-etiqueta, no se amplía para esta validación. Es el único punto de comparación con las 4 vías históricas (H1-H4, 14B, fusión, criterio de Cesar).
- **Ejecución:** flujo real de producción V2 (`corpus_runner` modo `judgment_v2`), bajo `PILOT_EXECUTION` firmada. Nunca por script ad hoc (lección estructural del skill: toda config ganadora se productiza y se re-mide por el flujo real).
- **Negativo obligatorio `ANNEX11_4`** (GAMP5 en lista de referencias): cualquier cambio que suba recall debe demostrar **simultáneamente** que este caso sigue rechazado.

### Suite B — Functional (fixture NUEVO — Golden Dataset, firma de Capa 9)

- **20 casos**, sobre pares de documentos reales de `GMPAI/source/Rockwell/` (URS v2.1, FS v1.2, DS, SAT-039/041):
  - 5 **fully traced** (URS→FS→DS→SAT completo) — el sistema debe NO emitir finding.
  - 5 **missing implementation** (URS req sin `implemented_by` en FS) — `FunctionalFinding: REQUIREMENT_NOT_IMPLEMENTED`.
  - 5 **missing tests** (req sin `Test` transitivo) — `TestCoverageFinding: REQUIREMENT_NOT_TESTED`.
  - 5 **contradictions** (dos documentos afirman comportamiento funcional opuesto sobre el mismo control) — `FunctionalFinding: CONTRADICTORY_FUNCTIONAL_BEHAVIOR`.
- Cada caso: documentos, secciones/páginas, ids de requisito/claim/test, y el finding esperado (clase, subtipo, evidencia anclada, provenance).
- **Construcción:** lectura directa de los PDFs por Capa 8; **revisión y firma de Capa 9** como cualquier artefacto gobernado antes de usarse como gate.

### Suite C — Technical (fixture NUEVO — Golden Dataset, firma de Capa 9)

- **20 casos conocidos**, distribuidos sobre: audit trail (diseño), access control, timestamp / time-sync, backup & recovery, interfaces entre sistemas, redundancia, data retention, seguridad.
  - ~13 **positivos** (el hueco técnico existe y está evidenciado en el documento) — `TechnicalFinding` del subtipo correspondiente, con cita anclada.
  - ~7 **negativos** (el control técnico SÍ está descrito adecuadamente, o el tema no aplica al tipo documental) — sin finding, o `TECHNICAL_COMPLIANT_EVIDENCE`.
- Mismo formato y circuito de firma que la Suite B.

---

## 2. Gates cuantitativos

```
# Suite A — Regulatory
REGULATORY_POSITIVE        >= 6/7    con cita anclada válida (evidence_verifier: exact|normalized|despaced|fuzzy>=0.93)
REGULATORY_NEGATIVE        =  2/2    (N1 reference-list, N2 TOC — ambos rechazados)
FABRICATED_CITATIONS       =  0      (ninguna cita que no ancle literalmente en el source_text)
SCHEMA_VALID_RATE          =  100%
LATENCIA_POR_LLAMADA       =  registrada (no es gate, es dato obligatorio)

# Suite B — Functional
FUNCTIONAL_RECALL          >= 90%   (findings esperados detectados / total esperados)
FUNCTIONAL_FALSE_POSITIVE  <= 5%    (findings emitidos no esperados / total emitidos)

# Suite C — Technical
TECHNICAL_RECALL           >= 90%
TECHNICAL_FALSE_POSITIVE   <= 5%

# Transversales (todas las suites)
TRACEABILITY_COMPLETE      =  YES   (todo Finding con provenance completo: document_id·page·section·source_text·source_hash·extraction_version; graph_path presente en findings cross-documento)
LOCAL_ONLY                 =  YES   (corrida completa con egress de red bloqueado — sin fallos)
DOCUMENT_EGRESS            =  0      (0 bytes de contenido de documento salen del servidor)
HUMAN_GATE_INTACT          =  YES   (ningún path convierte machine_state en QA_APPROVED / RELEASED / CAPA_CLOSED / FINAL_GMP_APPROVAL)
AUDIT_CHAIN                =  VERIFIED  o  ACCEPTED_WITH_DOCUMENTED_EXCEPTION  (sin nuevos forks respecto al baseline)
GATE_0_FACTORY             =  PASS   (factory_selfcheck.sh, sin regresión sobre CURRENT)
```

### 2.1 Interpretación de resultados de la Suite A

| Resultado | Acción |
|---|---|
| `REGULATORY_POSITIVE >= 6/7` ∧ negativos 2/2 ∧ 0 fabricadas | V2 resuelve el recall regulatorio. Proceder a cutover (decisión de Capa 9). |
| `4/7 <= POSITIVE < 6/7` | Mejora real pero insuficiente. Presentar a Capa 9: ¿iterar (V2b + normalización más agresiva) o adoptar Tier-1 para Regulatory? |
| `POSITIVE <= 2/7` | El rediseño local no cruza el techo. **Adoptar Palanca C (Tier-1) permanente para la clase Regulatory.** No degradar validadores. Functional/Technical se evalúan por sus propios gates. |
| Cualquier `FABRICATED_CITATIONS > 0` o `N1` no rechazado | **FALLO duro.** El cambio se revierte. Una cita fabricada que pasa es peor que recall bajo. |

---

## 3. Procedimiento de ejecución

### 3.1 Prerrequisitos (firma de Capa 9)

1. `ADR_ANALIZADOR_GMP_LOCAL_V2.md` firmado.
2. `requirements.yaml` con `decomposition[]` firmado como contenido gobernado.
3. Suites B y C construidas y firmadas como Golden Dataset.
4. `PILOT_EXECUTION` firmada con presupuesto para: Suite A (~9–25 llamadas de juicio V2 según sub-criterios), Suite B/C (según nº de casos × sub-criterios).
5. `MODEL_QUALIFICATION` de `qwen2.5:7b` en modo `judgment_v2` (re-calificación contra el fixture antes de cualquier uso real) + calificación del reranker si se autorizó su pull.

### 3.2 Orden

```
0. Gate 0 factory baseline (registrar estado PRE-cambio):
   bash /home/ing_cpmo/scripts/status.sh   # o el status.sh del evidence pack más reciente
   (equivalente en este clon: los checks manuales de la skill gmp-status)

1. Suite A — replay OFFLINE primero (cero llamadas):
   .venv/bin/python -m pytest factory/tests/test_judgment_v2_replay.py -q
   # reusa raw_payloads persistidos de P1/P5; verifica guardián de anclaje y no-promoción de negativos

2. Suite A — corrida REAL bajo PILOT_EXECUTION (background, checkpoints):
   corpus_runner modo judgment_v2, fixture 7P+2N, evaluation_profile heredado
   Registrar por caso: machine_state, cita, match_type, sub-criterios satisfechos, wall_seconds

3. Suites B y C — corridas REALES bajo PILOT_EXECUTION:
   corpus_runner plan por clase (FUNCTIONAL, TECHNICAL) sobre los pares de documentos del fixture

4. Test LOCAL_ONLY:
   corrida completa de un documento con egress de red bloqueado (iptables DROP saliente salvo
   loopback + aria-ollama local). Si cualquier componente intenta salir → FALLO.
   Verificar contadores: 0 bytes de contenido de documento fuera del servidor.

5. Gate 0 factory POST-cambio: sin regresión respecto al baseline del paso 0.

6. Verificación de audit chain:
   curl -s -H "X-API-Key: <FACTORY_API_KEY>" http://localhost:9000/api/v1/audit/verify
   # esperado: hash_errors=0, sin new_forks_since_baseline
```

### 3.3 Reporte

`docs_plan/REPORTE_VALIDACION_V2_<fecha>.md` con:
- tabla por caso de las 3 suites (esperado vs obtenido, evidencia anclada, provenance);
- comparación Suite A contra las 4 vías históricas (H1-H4, 14B, fusión, criterio de Cesar);
- latencias medidas (FASE 12 real vs proyección);
- resultado de cada gate (verde/rojo) sin eufemismos;
- recomendación a Capa 9 (cutover / iterar / Tier-1), **sin recomendación sesgada** — mismo criterio que el paquete de decisión estratégica.

---

## 4. Validación de regresión (que V2 no rompa lo que CURRENT hace bien)

| Propiedad de CURRENT | Test de no-regresión |
|---|---|
| P1 (LEXICAL_ECHO) sigue anclando | Suite A caso P1 → `MACHINE_CONFIRMED` con cita `normalized 1.0` |
| N1/N2 siguen rechazados | Suite A → 2/2 |
| Ausencia nunca cierra gap sin cobertura completa | `test_adjudicator.py` + `test_absence_consolidator` (existente) sin cambios |
| `evidence_verifier` intacto | `test_evidence_verifier_v2.py` sin cambios, mismo resultado |
| Cola humana recibe todo lo no confirmado | `test_judgment_v2_replay.py` — P2/P5 → cola, no gap |
| Audit trail hash-chain | `api/v1/audit/verify` sin nuevos forks |
| Gate 0 factory | `factory_selfcheck.sh` PASS |
| CURRENT sigue ejecutable (rollback) | corrida CURRENT (modo actual) tras el cutover flag → mismo resultado que antes |

---

## 5. Qué NO valida este plan (límites declarados)

- **No demuestra que V2 alcanzará ≥6/7** — lo mide. El resultado puede ser negativo; el plan contempla esa rama (Palanca C).
- **No valida escala de corpus completo** — las suites son fixtures acotados. Una corrida de corpus formal es una decisión posterior de Capa 9 (como la W5 diferida).
- **No valida los agentes técnicos contra un inspector real** — los gates 90%/≤5% son objetivos de diseño contra un Golden Dataset construido por Capa 8 y firmado por Capa 9, no contra una auditoría regulatoria externa.
- **No cierra `REGULATORY_COMPLIANCE`** — eso sigue siendo decisión de Capa 9 tras Piloto 2 / R4-R5, fuera del alcance de esta validación técnica.
