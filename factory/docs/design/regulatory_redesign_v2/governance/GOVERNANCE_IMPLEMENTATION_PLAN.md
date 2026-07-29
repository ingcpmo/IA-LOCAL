# GOVERNANCE_IMPLEMENTATION_PLAN — §10 del plan

**Estado:** DISEÑO. Nada de lo aquí descrito se ha ejecutado.
**Requiere:** aprobación de Cesar del diseño completo antes de iniciar G1.

---

## 1. Camino crítico revisado

El plan proponía G1→G8. La auditoría obliga a **una fase nueva** y a
**reordenar una**:

```
[G1]  Modelo extensible + resolver + enforcement            ← implementación
[G2]  Corrección D1 (snapshot 3 fuentes) + D1-A (Part 211)  ← decisión humana
[G2'] RE-FIRMA de D2/D3/D4/D5 con alcance explícito         ← NUEVA. decisión humana
[G3]  Reverificación de las 4 fuentes                       ← ejecución
[G4a] Interpretación humana del pack 211                    ← decisión humana
[G4b] Aprobación de la matriz v2.1                          ← decisión humana
[G4c] Versionado del catálogo → 2.0    (DESPUÉS de G4a)     ← decisión humana
[G5]  D2-A: aprobación pack a pack                          ← decisión humana
[G6]  Golden Dataset aprobado + recalificación del modelo   ← decisión + ejecución
[G7]  Excepción humana del fork histórico                   ← decisión humana
[G8]  D4-A calculada sobre el pack final                    ← decisión humana
  →   CORPUS_READY = true
```

### 1.1 G2' — por qué es nueva

Los registros `D2_evidence_packs`, `D3_T039`, `D4_corpus_execution` y
`D5_regenerate_qa_package` del 2026-07-29 se firmaron **sin ningún objetivo**:
`approved_pack_ids` es opcional (`w5_human_decisions.py:301-302`) y no se
envió; D3/D4/D5 no tienen campo de objetivo. Los cuatro dicen `APPROVE` sin
decir sobre qué.

Bajo el modelo nuevo, `resolved_target_ids` vacía viola la invariante I-3 y el
registro queda como `INVALID_PENDING_RESIGNATURE`: **no autoriza nada**. No es
un tecnicismo — hoy figuran como "registradas" cuatro decisiones cuyo alcance
nadie puede enunciar.

**El plan asumía que solo D1 tenía problema de alcance. Son cinco de cinco.**

### 1.2 G4c reordenado

El plan ponía "catálogo versionado" en G4 sin orden interno. Debe ir
**después** de G4a: aprobar el pack 211 cambia `requirements.yaml` y por tanto
`catalog_sha256`. Versionar antes obligaría a versionar dos veces en 48 h.

### 1.3 Lo que el plan daba por pendiente y ya está resuelto

| Ítem del plan | Estado real |
|---|---|
| §6.3 — resolver alcance 210 vs. 211 | **YA DECIDIDO** por Cesar (`d5f72735`→`786464e0`, `fcf933e7`→`caa2421d`). Solo falta estructurarlo y corregir 2 documentos |
| §7.2 — causa raíz del fork | **ESTABLECIDA** en esta corrida: `stale_in_process_head_cache`, corregida por `8c033fa` 27 min después del fork |
| §9.A — backend para snapshot explícito | **YA EXISTE**: `record_correction()` acepta `approved_source_ids`. Solo falta UI |

---

## 2. Fases de implementación

### G1 — Modelo, resolver y enforcement

| # | Entregable | Archivos |
|---|---|---|
| G1.1 | Registro de familias | `factory/registry/decision_families.yaml` **(nuevo)** |
| G1.2 | Schema del registro | `factory/regulatory/schemas/decision_record_v1.json` **(nuevo)** |
| G1.3 | Servicio de decisiones v2 | `factory/services/decision_store_v2.py` **(nuevo)** |
| G1.4 | Adaptador de legado | `factory/services/decision_legacy_adapter.py` **(nuevo)** |
| G1.5 | Script de migración | `factory/scripts/ops/migrate_decisions_to_v2.py` **(nuevo)** |
| G1.6 | **Resolver** | `factory/core/decision_scope_resolver.py` **(nuevo)** |
| G1.7 | Consumidor 1 | `factory/regulatory/source_currency_checker.py` (mod) |
| G1.8 | Consumidor 2 | `factory/regulatory/requirement_catalog/requirement_catalog_loader.py`, `provisional_evidence_model.py` (mod) |
| G1.9 | Consumidor 3 | `factory/regulatory/verified_pipeline.py` (mod) |
| G1.10 | Consumidor 4 | `factory/regulatory/tools/build_source_baseline_allowlist.py` (mod) |
| G1.11 | Consumidor 5 | `factory/core/quality_gate_runner.py` (gate `G15_decision_coverage`), `factory/core/release_manager.py` (mod) |
| G1.12 | Estados de fuente | `factory/regulatory/source_lifecycle.py` **(nuevo)**, schema `source_registry_entry_v2.json` |
| G1.13 | Versionado | `factory/registry/artifact_versions.jsonl`, `factory/core/artifact_version_guard.py` **(nuevo)**, `bootstrap_artifact_versions.py` **(nuevo)** |
| G1.14 | Auditoría por dimensión | `factory/core/audit_writer.py` (mod: `part11_compliant` pasa a enum), `factory/audit/fork_baseline.json` **(nuevo)** |
| G1.15 | Endpoints de gobernanza | `factory/api/routes/layer9.py` (mod) |
| G1.16 | UI — seis paneles | `factory/ui/js/mission_control/governance.js` **(nuevo)**, `mission_control.html` (mod) |
| G1.17 | Gate 0 ampliado | `factory/scripts/ops/factory_selfcheck.sh` (mod) |

**Orden interno:** G1.1→G1.6 antes que G1.7→G1.11 (el resolver debe existir
antes que sus llamadores). G1.16 al final: la UI se construye sobre endpoints
que ya funcionan.

**Checkpoint humano G1:** Cesar revisa el diff completo **sin que nada se
haya migrado**. La migración (`--apply`) es lo primero de G2.

### G2 — Corrección D1 + D1-A

1. `migrate_decisions_to_v2.py --apply` (evento único).
2. Panel A: Corrección D1 con snapshot de las 3 fuentes.
3. Panel B: D1-A para `ecfr_21cfr_part211`.
4. Verificar: `coverage_report("D1").uncovered_ids == ()`.

**Checkpoint humano G2:** dos decisiones firmadas por Cesar en la UI.

### G2' — Re-firma de D2/D3/D4/D5

Cuatro decisiones nuevas con `resolved_target_ids` explícita. **No son
correcciones**: los registros originales se conservan como
`INVALID_PENDING_RESIGNATURE` y las nuevas son `SUPERSESSION` de familia.

**Checkpoint humano G2':** cuatro decisiones firmadas.

### G3 — Reverificación

`check_all_governed_sources(run_by=<identidad real>)` sobre las 4 fuentes,
ahora con `resolve("D1", …)` como puerta previa (C-1). Salida esperada: las 4
a `LOCAL_CANONICAL_COPY_VERIFIED`, o las que no pasen con su motivo.

**Checkpoint humano G3:** Cesar lanza la reverificación con su nombre y
revisa el resultado.

### G4 — Contenido y versiones

- **G4a** — Panel C: PROPONE (Claude) → VALIDA (10 validadores) → APRUEBA
  (Cesar). **Primera inferencia sobre Part 211** ⇒ exige G3 cerrada.
- **G4b** — Panel D: aprobación de la matriz v2.1
  (`APPLICABILITY_MATRIX-2026-002`); `MC-0001` queda con
  `covers_matrix_version: "2.0"` y `authoritative: false`.
- **G4c** — Panel D: catálogo `1.0 → 2.0`, copia histórica congelada,
  corrección de los 2 documentos con "210/211".

**Checkpoints humanos: tres** (uno por subfase).

### G5 — D2-A

Un `ADDENDUM` de familia `D2` por `requirement_id`, 20 en total. `D2_A_READY`
calculado, nunca declarado.

**Checkpoint humano G5.**

### G6 — Golden Dataset + recalificación

1. Revisar los 14 casos; decidir si se añade cobertura de Part 211
   (recomendado, §3 de `MODEL_REQUALIFICATION_AND_D4A_SPEC.md`).
2. Aprobar y versionar; añadir `golden_dataset_sha256` al fingerprint.
3. Recalificar con `run_context="model_requalification"` — **primera
   inferencia autorizada**; mide las 4 métricas `NOT_MEASURED`.

**Checkpoints humanos: dos** (aprobación del dataset; aceptación de la
calificación).

### G7 — Excepción de auditoría

Las 5 medidas preventivas implementadas **antes** de pedir la aceptación.
Panel E: aceptar o rechazar.

**Checkpoint humano G7.**

### G8 — D4-A

Fórmula ejecutada sobre el pack final con la latencia medida en G6. Panel F.
Retirada de los escritores legacy y de la vista `w5_decisions.js`.

**Checkpoint humano G8.**

---

## 3. Tests a añadir

| Archivo | Tests | Cubre |
|---|---|---|
| `test_decision_model_v2.py` | I-1…I-12 (12) | schema e invariantes |
| `test_decision_migration.py` | V-1…V-6 (6) | migración, idempotencia, rollback |
| `test_decision_scope_resolver.py` | T-01…T-19 (19) | cobertura, fail-closed, read-only |
| `test_decision_resolver_no_bypass.py` | T-20…T-24 (5) | **guardia de Gate 0** |
| `test_source_lifecycle.py` | L-01…L-10 (10) | 5 dimensiones, máquina de estados |
| `test_evidence_pack_governance.py` | P-01…P-12 (12) | validadores, grano de aprobación |
| `test_artifact_versioning.py` | VZ-01…VZ-11 (11) | invariante triple, canonicalización |
| `test_audit_fork_governance.py` | F-01…F-13 (13) | dimensiones, baseline, excepción |
| `test_model_requalification_and_d4a.py` | Q-01…Q-14 (14) | fingerprint, guardia de inferencia, fórmula |
| **total** | **102** | |

Suite actual: 1 396. Objetivo tras G1: **≈ 1 498**.

### 3.1 Los tres tests que no pueden faltar

| Test | Por qué |
|---|---|
| `test_source_registered_after_all_snapshot_is_not_covered` (T-01) | reproduce el defecto que originó todo el trabajo, con Part 211 como fixture real |
| `test_all_five_consumers_call_resolve` (T-21) + `test_consumer_list_matches_families_registry` (T-24) | sin ellos, el resolver puede existir y no llamarse nunca — que es el estado de hoy |
| `test_no_collapsed_source_verified_flag` (L-09) | impide que las 5 dimensiones vuelvan a colapsarse en un booleano |

### 3.2 Prueba por mutación

Antes de declarar G1 cerrada, misma disciplina que la auditoría J–P
(`bfe11ba`): cada mutación de §7.5 de `DECISION_SCOPE_RESOLVER_SPEC.md` debe
hacer fallar al menos un test nombrado. Si alguna pasa, el test es decorativo
y se rehace.

---

## 4. Rollback

| Fase | Rollback | Coste |
|---|---|---|
| G1 | `git revert` del rango. Ningún dato migrado aún | bajo |
| G2 (migración) | `rm decisions_v2.jsonl _projection_v2.json`. Las entradas nunca se tocaron | trivial |
| G2 (decisiones) | **no se revierte**: una decisión firmada es un hecho. Se le superpone una `CORRECTION` o `REVOCATION` firmada | — |
| G2' | ídem | — |
| G3 | `source_currency_log.jsonl` es append-only; el estado se recalcula. `registry_v2.json` derivado se borra | bajo |
| G4a | el pack aprobado se revoca con una decisión `REVOCATION`; `requirements.yaml` vuelve por `git revert` | medio |
| G4b/G4c | `git revert` + `REVOCATION` de la decisión de versión | medio |
| G5 | `REVOCATION` por pack | bajo |
| G6 | `qualification_record.json` se regenera; el anterior queda en `previous_fingerprint` | medio (una corrida de inferencia) |
| G7 | `REVOCATION` de la excepción ⇒ `PART11_COMPLIANCE` vuelve a `NOT_DETERMINED` | trivial |
| G8 | `REVOCATION` de D4-A | trivial |

**Principio:** el código se revierte con git; las decisiones **no se
revierten, se superponen**. Los datos derivados se borran y se regeneran. Los
almacenes append-only nunca se tocan.

### 4.1 Punto de no retorno

**No hay ninguno antes de G6.** La recalificación es la primera acción cuyo
deshacer cuesta tiempo de máquina (una corrida contra el Golden Dataset). Todo
lo anterior es reversible en minutos.

---

## 5. Checkpoints humanos

| # | Gate | Qué firma Cesar | Panel |
|---|---|---|---|
| 1 | G1 | diff de implementación, **sin migrar** | — (revisión de código) |
| 2 | G2 | Corrección D1 (snapshot de 3) | A |
| 3 | G2 | D1-A (Part 211) | B |
| 4 | G2' | re-firma de D2/D3/D4/D5 con alcance | D + genéricos |
| 5 | G3 | lanzamiento y resultado de la reverificación | B |
| 6 | G4a | criterios interpretativos del pack 211 | C |
| 7 | G4b | matriz v2.1 | D |
| 8 | G4c | catálogo 2.0 | D |
| 9 | G5 | D2-A, pack a pack | D |
| 10 | G6 | Golden Dataset (¿casos de Part 211?) | — |
| 11 | G6 | aceptación de la calificación | — |
| 12 | G7 | excepción de auditoría | E |
| 13 | G8 | D4-A | F |

**Trece checkpoints, mínimo uno por G.** Ninguno es delegable a Capa 8: los
trece son actos de Capa 9.

---

## 6. Esfuerzo estimado

| Fase | Trabajo | Estimación |
|---|---|---|
| G1.1–G1.6 | modelo, adaptador, migración, resolver | 3–4 sesiones |
| G1.7–G1.11 | 5 consumidores + gate nuevo | 2–3 sesiones |
| G1.12–G1.14 | ciclo de vida, versionado, auditoría por dimensión | 2–3 sesiones |
| G1.15–G1.17 | endpoints, UI de 6 paneles, Gate 0 | 3–4 sesiones |
| G1 tests | 102 tests + mutación | 2–3 sesiones |
| **G1 total** | | **12–17 sesiones** |
| G2 + G2' | migración + 6 decisiones | 1 sesión + tiempo de Cesar |
| G3 | reverificación real (4 accesos HTTP) | < 1 sesión |
| G4a | PROPONE/VALIDA/APRUEBA del pack 211 | 1–2 sesiones + juicio de Cesar |
| G4b + G4c | matriz, catálogo, copia histórica, 2 documentos | 1 sesión |
| G5 | 20 decisiones | 1 sesión + tiempo de Cesar |
| G6 | dataset + **recalificación real** | 1 sesión + **corrida de inferencia** |
| G7 | 5 medidas preventivas + paquete | 1–2 sesiones |
| G8 | fórmula + D4-A | < 1 sesión |
| **Total** | | **20–27 sesiones** |

Coste de máquina: **una sola** corrida de inferencia antes de `CORPUS_READY`
(la recalificación de G6, contra el Golden Dataset de 14 casos — minutos, no
horas). Las ~34 h del corpus vienen **después** de `CORPUS_READY` y las
gobierna D4-A.

### 6.1 Qué NO está estimado

- El **juicio regulatorio humano** de G4a (redactar `evidence_min_criteria`
  para la regla predicado de 6 requisitos). Es trabajo de Cesar y no lo
  estima Capa 8.
- El tiempo de decisión de los 13 checkpoints.

---

## 7. Riesgos

| Riesgo | Mitigación |
|---|---|
| El resolver se implementa y nadie lo llama | T-20…T-24 en Gate 0; T-24 falla si se añade una familia con consumidor no conectado |
| G2' se percibe como burocracia ("ya las aprobé") | el informe muestra literalmente que los 4 registros dicen `APPROVE` sin objeto; se firman con alcance en una sola sesión |
| Versionar el catálogo dos veces | G4c **después** de G4a, explícito en el orden |
| La UI acumula lógica propia y diverge del backend | los paneles muestran objetos del backend (`d2a_ready()`, `CoverageReport`), no recalculan |
| Aceptar la excepción de auditoría sin prevención | `Aceptar` deshabilitado hasta las 5 medidas en ✓ |
| Se fija D4-A con la cifra de calibración (34,3 h) | los campos no son editables a mano; los calcula el backend |
| Retirar los escritores legacy antes de tiempo rompe la única UI existente | retirada en G8, no antes |

---

## 8. Criterio de cierre — `CORPUS_READY = true`

Las **once** condiciones, simultáneamente:

```
 1. coverage_report("D1").uncovered_ids == ()
 2. las 4 fuentes en LOCAL_CANONICAL_COPY_VERIFIED
 3. FORMAL_USE_ELIGIBILITY == true para las 4
 4. los 20 packs con d2a_ready() == true y decisión D2 ACTIVE
 5. matriz v2.1 con decisión APPLICABILITY_MATRIX ACTIVE
 6. catálogo con version_record consistente y decisión que lo aprueba
 7. registros INVALID_PENDING_RESIGNATURE == 0
 8. qualification_record.status == QUALIFIED (13/13 métricas medidas)
 9. NEW_FORKS_SINCE_BASELINE == 0 ∧ excepción AUDIT_EXCEPTION ACTIVE
10. D4-A registrada con todos sus campos resueltos
11. Gate 0 PASS con los 7 pasos, incluidos no-bypass y versionado
```

`DEV-W5-001` pasa a `CLOSED` con la 1, y **conservando** el test T-01 en
verde: cerrar la desviación no es hacer que el test deje de aplicar.

---

## 9. Lo que esta corrida entrega y lo que no

**Entrega:** diez documentos de diseño en
`factory/docs/design/regulatory_redesign_v2/governance/`, una auditoría con
evidencia archivo:línea de cada valor, 11 hallazgos numerados, la causa raíz
del fork establecida, el alcance 210/211 verificado como ya decidido, y 102
tests especificados.

**No entrega, y no debía:** ninguna decisión registrada, ninguna fuente
reverificada, ninguna llamada a Ollama, ninguna corrida de corpus, ninguna
modificación de auditoría histórica, ningún cambio de código ni de estado.
