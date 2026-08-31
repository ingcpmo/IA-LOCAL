# E1 — REVISIÓN HUMANA REGISTRADA + FALLO SEMÁNTICO MATERIAL + FIX DIRIGIDO H-10

**Fecha:** 2026-08-31 · **Autoridad:** Capa 9 = Cesar · **Gate:** E1 (verificación humana de la
muestra H-10). **Ámbito del fix:** exclusivamente H-10 (`refers_to` / entity linking). **NO** se
rediseñó H1–H9. **NO** commit / producción / cutover / QA40 en esta pasada.

---

## 1 · E1_REVIEW_RECORDED = YES

Adjudicación humana de las 77 filas de
`factory/regulatory/pilot_run/h10_extraction_v2_20260830/H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json`
(muestra `sample_sha256 = f56d4bab…`, 17 `tested_by` + 60 `refers_to`):

```
TOTAL            = 77
CORRECT          = 26   (34 %)
WRONG_NODE       = 30   (39 %)
SPURIOUS         = 11   (14 %)
AMBIGUOUS        = 10   (13 %)
verdict_set_sha256 = a533bf4aa11d58acf2dd881cd5abaf52f85175c90db3c50d0bb1a79b352de085
```

**E1 = COMPLETED_HUMAN_REVIEW.** El formato 77/77 válido en la UI **no** es un PASS de E1.

---

## 2 · Criterio de aceptación original (citado literal, no inventado)

`docs_plan/REVISION_CIERRE_H1_H10_Y_INSTRUCCIONES_20260830.md` §4:

> **E-1 · Verificación humana de la muestra H-10** (`H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json`, 77
> filas: 17 `tested_by` + 60 `refers_to`). **Es la que valida que las relaciones nuevas no son
> ruido.**

`REVISION_CIERRE…` §1, fila H-10:

> H-10 | habilitar Test extraction + `refers_to` **con nodos reales**

`docs_plan/CIERRE_H10_CAPACIDAD_20260830.md` §1 (criterio técnico, ya PASS antes de E1):

> `refers_to` backed by **real nodes/evidence** — 350; 100 % con destino
> `system_component`/`actor` real; 100 % con ancla; 0 dangling.

**Distinción clave:** `H10_TECHNICAL_ACCEPTANCE = PASS` se declaró sobre "destino = nodo real que
existe (no colgante)". E-1 es un criterio **distinto y posterior**: que el nodo destino sea el
**correcto** y que la relación **no sea ruido**. El propio `CIERRE_H10` §4 dice que
`H10_HUMAN_SAMPLE_VERIFICATION = PENDING` **impide la activación productiva**.

```
ORIGINAL_ACCEPTANCE_CRITERION = "E-1 valida que las relaciones nuevas NO SON RUIDO"
                                + "refers_to con NODOS REALES (correctos)"
                                (REVISION_CIERRE_H1_H10 §4 y §1 · CIERRE_H10_CAPACIDAD §1/§4)
NUMERIC_THRESHOLD_IN_PLAN      = NINGUNO  (no se inventa uno)
```

**El plan NO contiene ningún criterio que permita continuar a E2 con este resultado.** §4 lista
E-1, E-2 y E-3 como conjuntamente necesarias para activación ("E-1 y E-2 y E-3 habilitan
activación"); ninguna cláusula habilita omitir E-1 ni aceptar una muestra mayoritariamente
incorrecta. RR-1 (§5) ya anticipaba que el revisor de E-1 debía "mirar con lupa" la calidad.

---

## 3 · MATERIAL_SEMANTIC_FAILURE = YES

`26/77` correctas (34 %). `41/77` = **53 %** de las relaciones nuevas emitidas son **nodo
equivocado o ruido**. Contra el criterio literal "no son ruido" / "nodos reales (correctos)", esto
es un **fallo semántico material**. No requiere un umbral numérico: la mayoría de la muestra falla
el criterio cualitativo.

`E1_ACCEPTANCE_STATUS = FAIL / REMEDIATION_REQUIRED`

---

## 4 · Análisis por relación y por patrón de veredicto

### 4.1 · `tested_by` (17 filas)
Las 17 son cross-documento (`RW-0006`/`RW-0005` → `RW-0003`) vía las refs literales `3.2.3`
(requisito URS) y `F05.05` (función FS). Varias apuntan al **mismo** `Test` destino desde anclas
casi idénticas (4 filas → `UR3.2.3` desde `RW-0005 p192`; 2 → `F05.05` desde `RW-0005 p158`).
El emparejador de refs (`build.py` loop `verifies`/`_link_chain`) casa por **token literal corto**
(`3.2.3` son 5 caracteres) → riesgo de coincidencia promiscua y de duplicados semánticos.
**Este emparejador es PRE-H-10** (`CIERRE_H10` §3: "`_link_to_tests` / `verifies` **sin cambios de
lógica**"). Corregirlo tocaría H1–H9 → **fuera del ámbito estricto de esta remediación**. Se
registra como causa y se deja a decisión de Capa 9 si entra en un fix separado. El fix de esta
pasada **no altera ninguna arista `tested_by`** (las 17 sobreviven idénticas).

### 4.2 · `refers_to` (60 filas) — causa sistemática dominante
`build.py::_link_refers_to` emitía **una arista por CADA término del diccionario de entidades que
casaba literalmente** en el texto del claim, **sin resolución de especificidad**. El diccionario
(`extract_entities._COMPONENT_TERMS`) contiene términos que son prefijo/subcadena de otros:

```
"FactoryTalk"  ⊂  "FactoryTalk View"  ⊂  "FactoryTalk View SE"
"FactoryTalk"  ⊂  "FactoryTalk Historian"
"FactoryTalk"  ⊂  "FactoryTalk Linx"
"CP01"         ⊂  "PCS-CP01"  /  "PCS-CP-01"
```

Un claim con "…the FactoryTalk **Historian** SE server…" generaba **dos** aristas: a `FactoryTalk`
(genérica, **NODO EQUIVOCADO**) y a `FactoryTalk Historian` (correcta). La muestra (60 primeras por
`edge_id`) quedó cargada de las genéricas.

Distribución de `destination_label` en las 60 filas `refers_to` de la muestra original:

| destino | filas | lectura |
|---|---|---|
| `FactoryTalk` (genérico) | 16 | casi todas WRONG_NODE (el claim nombra View/Historian/Linx) |
| `FactoryTalk View` | 14 | mixto (WRONG_NODE cuando el claim dice "…View **SE**") |
| `CP01` (genérico) | 7 | WRONG_NODE (el claim nombra "PCS-CP01") |
| `FactoryTalk View SE` | 4 | correcto |
| `CompactLogix` / `ControlLogix` / `engineering workstation` | 12 | correcto |
| `PCS-CP01` / `PCS-CP-01` | 3 | correcto |
| `FactoryTalk Historian` / `FactoryTalk Linx` | 2 | correcto |
| `thin client` / `Administrator` | 2 | revisión |

`16 + 7 = 23` filas son WRONG_NODE por esta única causa; sumando las `FactoryTalk View` sobre
claims que dicen "SE", se cubren ~30 → **la resolución de especificidad ausente explica
prácticamente todos los 30 WRONG_NODE**.

### 4.3 · Patrones SPURIOUS (11) y AMBIGUOUS (10)
- **SPURIOUS** — probables: (a) prosa de descripción de proyecto genérica
  ("PCS – Process Control System (This project's purpose…)") que menciona un tag de equipo de
  pasada; (b) el tag suelto `_CP_TAG_RE = \bCP-?0\d\b` (bare "CP01") casando texto de tabla / ruido
  OCR; (c) `tested_by` por `3.2.3` sobre ruido.
- **AMBIGUOUS** — probables: (a) claims donde dos entidades distintas aplican de verdad
  ("MicroLogix or CompactLogix"); (b) claims tipo encabezado/lista.
- El fix de especificidad (§5) también **retira** las aristas SPURIOUS que eran genéricas sobre un
  claim con mención más específica. El resto de SPURIOUS/AMBIGUOUS (prosa genérica, tag suelto,
  `3.2.3`) queda **caracterizado, no corregido** en esta pasada — corregir la extracción de
  entidades (`_CP_TAG_RE`) o el emparejador de `3.2.3` requiere una decisión de alcance de Capa 9.

```
ROOT_CAUSES =
  RC-1 (dominante, refers_to, H-10)  _link_refers_to enlaza a TODO término que casa,
                                      sin resolución de especificidad -> el genérico
                                      (prefijo/subcadena de uno específico) es NODO EQUIVOCADO.
                                      Casos: FactoryTalk ⊂ {View, View SE, Historian, Linx} ;
                                             CP01 ⊂ {PCS-CP01, PCS-CP-01}.
  RC-2 (secundaria, extract_entities, H-10)  _CP_TAG_RE crea el nodo "CP01" suelto aunque el
                                      tag real sea "PCS-CP01" -> nodo de baja señal.
  RC-3 (fuera de ámbito, PRE-H-10)   emparejador de refs cortas (3.2.3 / F05.05) en el loop
                                      verifies/_link_chain: token literal de 5 chars, promiscuo,
                                      produce tested_by duplicados/dudosos.
```

---

## 5 · FIX DIRIGIDO — sólo H-10, sólo `refers_to`

`H10_TARGETED_FIX_REQUIRED = YES` → aplicado **FIX-A** (RC-1). RC-2/RC-3 **no** tocadas
(caracterizadas para decisión de Capa 9).

### FIX-A · `factory/regulatory/graph/build.py::_link_refers_to`
Resolución de especificidad por **contención de span**: para cada claim se recogen todas las
menciones `(entidad, [inicio, fin))`; si el span de una mención está **estrictamente contenido**
en el de otra más larga, esa entidad (la genérica) **no recibe arista** para ese claim. Sólo se
enlaza la mención más específica. Una mención genérica **autónoma** (sin forma larga que la
contenga en el mismo claim, p.ej. "the FactoryTalk platform") **sí** se enlaza.

- +test `test_graph_build_and_trace::test_h10_refers_to_specificity_resolution`.
- **No** toca extracción canónica, `tested_by`, `implemented_by`, `designed_by`, `contradicts`,
  ni los findings.

---

## 6 · rerun H10 · rerun R-PAR · regen muestra · antes/después

`H10_RW0003_STORE` fijado a copia local (RW-0003 OCR ya ingerido; **sin re-OCR**).

### 6.1 · rerun H10 (`h10_execute_version_jump.py`, run1 + run2)
```
                         ANTES (f56d4bab)      DESPUÉS (fix-A)      Δ
refers_to (grafo total)  350                   202                  −148  (−42 %)
tested_by                17                    17                   0
implemented_by           1120                  1120                 0
designed_by              190                   190                  0
regulated_by             20                    20                   0
system_component / actor 47 / 13               47 / 13              0   (canónico intacto)
test nodes               166                   166                  0

GRAPH_SNAPSHOT_FINGERPRINT   8ce23f30…  ->  29fd9064…   CAMBIA (esperado: cambió el set de aristas)
FINDINGS_FINGERPRINT        2b1a300a…  ->  2b1a300a…   IDÉNTICO  ← 0 impacto analítico
INPUT_CONFIG_FINGERPRINT    0de04225…  ->  fc0c55b4…   CAMBIA (editar build.py cambia el AST import digest)

determinism_2x = PASS (run1 == run2 en los 3 fingerprints)
v1_stores_preserved = YES     document_egress_bytes = 0     human_gate_intact = true
```

### 6.2 · rerun R-PAR (`r_par_delta_v1_v2.py`, 4 escenarios × 2)
```
                              ORIGINAL R-PAR        DESPUÉS (fix-A)      lectura
A_vs_B clone-drift            38 CLONE_DRIFT        38 CLONE_DRIFT       SIN CAMBIO
                              0 UNEXPLAINED         0 UNEXPLAINED
B_vs_C only_C (efecto H-10)   +1 finding LOW        +1 finding LOW      SIN CAMBIO
B_vs_C band_changed           0                     0                  SIN CAMBIO
B_vs_C refers_to (C)          350                   201                 −149  (el fix)
C_vs_D tested_by añadidas     17                    17                 SIN CAMBIO
C_vs_D test añadidos          165                   165                SIN CAMBIO
RW-0012 claims (clean/prod)   258 / 595             258 / 595          SIN CAMBIO (clone-drift)
D findings_fingerprint        2b1a300a…             2b1a300a…          IDÉNTICO
determinism A/B/C/D           PASS                  PASS               SIN CAMBIO
document_egress               0                     0                  SIN CAMBIO
```

**R-PAR confirma: el fix cambia ÚNICAMENTE el conteo de `refers_to`. Ningún finding se añade,
elimina ni cambia de banda.**

### 6.3 · Muestra E1 regenerada (`H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json`)
```
sample_sha256   f56d4bab…   ->   c2ca5aaa36e9904b77cecf266cfa6645ab76949828074c857a360a5bf75ad3fd
relation_totals refers_to 350 -> 202 ; tested_by 17 -> 17
sample_size     77 (17 tested_by + 60 refers_to, misma política: TODAS tested_by + 60 primeras refers_to por edge_id)
H10_HUMAN_SAMPLE_VERIFICATION = PENDING   (todas las filas HUMAN_VERDICT = "")
```

**Supervivencia de las 60 filas `refers_to` que el humano ya adjudicó:**
```
32 RETIRADAS por FIX-A:  13 "FactoryTalk View"  +  12 "FactoryTalk"  +  7 "CP01"
                          = exactamente el patrón genérico-sobre-específico (WRONG_NODE)
28 CONSERVADAS:           destino ya era el nodo específico/correcto (CompactLogix, View SE,
                          engineering workstation, ControlLogix, PCS-CP01, Historian, Linx,
                          Administrator, thin client) + 4 "FactoryTalk" autónomo genuino
17 tested_by:             TODAS conservadas sin cambio (FIX-A no toca tested_by)
```
Las 32 retiradas mapean 1:1 con los 30 WRONG_NODE + 2 SPURIOUS genéricos del veredicto humano.

**Composición `destination_label` de las 60 `refers_to` de la muestra NUEVA:**
```
FactoryTalk View SE 14 (era 4)   ·  PCS-CP01 8 (era 2)   ·  FactoryTalk (autónomo) 6 (era 16)
FactoryTalk Historian 5 (era 1)  ·  CompactLogix 5  ·  engineering workstation 5  ·  Administrator 4
ControlLogix 3  ·  FactoryTalk Linx 2 (era 1)  ·  OPC server 2  ·  FactoryTalk View 1 (era 14)
PCS-CP-01 1  ·  thin client 1  ·  Stratix 1  ·  Active Directory 1  ·  GuardLogix 1
```
El genérico "CP01" **desaparece** del top-60. "FactoryTalk" genérico baja 16→6 (los 6 restantes son
menciones autónomas legítimas). Los específicos (View SE, Historian, Linx, PCS-CP01) dominan.

---

## 7 · Regresión

Suite completa tras FIX-A: **`2 failed · 3007 passed · 80 skipped · 1 xfailed`**
(`_gates_prep/…` → `scratchpad/regr_after_fixA.log`). Los 2 fallos son los KNOWN_EXCEPTIONS de
entorno / servicio vivo (`test_corpus_runner…232`, `test_deployment_exists_and_health`).
`test_h4_graph_snapshot` (`b5196a71…`) y `test_h3_finding_record_id`: PASS — el fingerprint de
findings no se movió. `+1 passed` = el test nuevo `test_h10_refers_to_specificity_resolution`.

```
NEW_REGRESSIONS = 0
```

---

## 8 · Estado y siguiente paso

```
E1_REVIEW_RECORDED             = YES  (COMPLETED_HUMAN_REVIEW ; verdict_set_sha256 a533bf4a…)
E1_ACCEPTANCE_STATUS          = FAIL / REMEDIATION_REQUIRED
ORIGINAL_ACCEPTANCE_CRITERION = "E-1 valida que las relaciones nuevas NO SON RUIDO ; refers_to con
                                 nodos reales (correctos)"  (REVISION_CIERRE_H1_H10 §4/§1 ;
                                 CIERRE_H10_CAPACIDAD §1/§4) — sin umbral numérico
MATERIAL_SEMANTIC_FAILURE     = YES  (53 % de la muestra = WRONG_NODE ∨ SPURIOUS ∨ AMBIGUOUS)
ROOT_CAUSES                   = RC-1 (dominante, H-10): _link_refers_to sin resolución de
                                       especificidad -> genérico = nodo equivocado
                                       (FactoryTalk ⊂ View/View SE/Historian/Linx ; CP01 ⊂ PCS-CP01)
                                RC-2 (secundaria, H-10): _CP_TAG_RE crea "CP01" suelto
                                RC-3 (fuera de ámbito, PRE-H-10): emparejador de 3.2.3/F05.05 promiscuo
H10_TARGETED_FIX_REQUIRED     = YES  — FIX-A aplicado (RC-1) ; RC-2/RC-3 caracterizadas, no tocadas
                                (RC-2/RC-3 requieren decisión de alcance de Capa 9)
NEXT_PLAN_STEP                = NUEVA REVISIÓN HUMANA E1 sobre la muestra regenerada
                                (sample_sha256 c2ca5aaa…). NO avanzar a E2 hasta que E1 pase.
```

`REGENERATED_SAMPLE = factory/regulatory/pilot_run/h10_extraction_v2_20260830/H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json`
(sha `c2ca5aaa…`). `H10_HUMAN_SAMPLE_VERIFICATION = PENDING`. Sin commit, sin flip, sin QA40, sin
activación. **Detenido para revisión humana E1.**
