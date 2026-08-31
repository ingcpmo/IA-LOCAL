# REVISIÓN DE CIERRE H-1…H-10 + INSTRUCCIONES PARA CLAUDE CODE

**Fecha:** 2026-08-30 · **Autoridad:** Capa 9 = Cesar · **Objeto:** validar el cierre del diseño
H-1…H-10, no rediseñar. **Fuente única:** `INFORME_MAESTRO_EJECUCION_GMP_AI_FACTORY_H1_H10_20260830.md`.
**Intended use fijado por Capa 9:** `GMP_DECISION_SUPPORT_TOOL` · `SYSTEM_OF_RECORD = NO` ·
`HUMAN_FINAL_AUTHORITY = REQUIRED` · `PRODUCTION_ENABLEMENT = NOT_ENABLED` ·
`REGULATORY_COMPLIANCE = NOT_DETERMINED_BY_SYSTEM`.

**Nota de procedencia:** no he inspeccionado el código ni los artefactos. Reviso la **consistencia
interna** del informe y su suficiencia frente al diseño H-1…H-10 y a las invariantes. Donde una
afirmación del informe solo pueda confirmarse ejecutando, lo digo y va a las instrucciones como
verificación, no como hallazgo.

---

## VEREDICTO EN UNA LÍNEA

**El diseño H-1…H-10 está satisfecho; no hay contradicción material que obligue a volver a diseño; el
plan v1-vs-v2 es suficiente PERO le falta una prueba explícita de paridad que hoy no está en el
informe; y la evidencia humana mínima antes de producción/D-6 es exactamente la que el propio informe
declara bloqueada.** No propongo arquitectura nueva.

---

## 1 · ¿LA IMPLEMENTACIÓN FINAL SATISFACE EL DISEÑO H-1…H-10?

Sí, paquete por paquete, con la evidencia citada en el informe. Contraste directo contra el diseño
actualizado R0–R5:

| WP | Diseño exigía | Informe entrega | Veredicto |
|---|---|---|---|
| H-1 | identidad en los 7 mutadores rojos; `approved_by` derivado, no del body | `test_h1_identity_critical_mutators.py`; gap cerrado en los 7 | **SATISFECHO** (sujeto a §5-R1) |
| H-2 | ruta de auditoría inyectada; fixture autouse; conteo invariante | autouse; `AUDIT_TRAIL_CHANGED_BY_TESTS = NO` | **SATISFECHO** |
| H-3 | `finding_record_id` aditivo (M2+M3); `finding_id` intacto; fingerprint estable | `finding_record_id`; `b5196a71…` estable; sin requalification | **SATISFECHO** — coincide con C-1/C-2 |
| H-4 | snapshot de grafo por `run_id`; digest del **estado**, no del esquema | `GRAPH_SNAPSHOT_FINGERPRINT` solo topología, inmutable, overwrite→error | **SATISFECHO** con matiz (§5-R4) |
| H-5 | aislamiento de red real (no solo parche); Postgres/Redis; `ro`; CORS | H-5F: red aislada, iptables, CORS allowlist, corpus `:ro`. **Solo `factory-api`** | **SATISFECHO EN SU ALCANCE**; H-5B (base) fuera de alcance declarado |
| H-6 | respaldo + ensayo de restauración con `verify_chain` | H-6F: restore 14/14, fork preservado. `pg_dump` diferido a H-6B | **SATISFECHO EN SU ALCANCE** |
| H-7 | `coverage_mode` gobernado; riesgo consume `evidence_basis`; degrada 78 | ENFORCE firmado; `findings_degraded=78`, `suppressed=0` | **SATISFECHO** — exactamente los 78 |
| H-8 | instrumento vacío; la IA no rellena | instrumento listo; `score_* → UNKNOWN`; QA40 40/40 PENDING | **SATISFECHO** (por diseño queda a la espera de D-5) |
| H-9 | benchmark firmado antes de correr; menor superficie ante empate | 3 backends, RW-0003 204 pág, determinista, egress 0 | **SATISFECHO** (con una observación de criterio, §comentario) |
| H-10 | habilitar Test extraction + `refers_to` con nodos reales; agrupar salto de versión | 165 Test, `tested_by=17`, `refers_to=350`, 0 fabricado, rollback PASS | **SATISFECHO TÉCNICAMENTE** |

**Sobre H-9 / selección de docling.** El diseño declaraba el sesgo "ante empate, menor superficie de
validación" (favorecía OCRmyPDF/rapidocr). El informe selecciona **docling** y justifica que el empate
se rompe en el criterio 3 (reconstrucción de tabla: 199 vs 0), no en el criterio de superficie. Es una
aplicación **correcta** de la regla, no una violación: la regla solo operaba *ante empate*, y en tablas
no hay empate. Lo registro como decisión bien fundada, no como desviación. Consecuencia aceptada: mayor
footprint (peak 4.5 GB por lotes), que el informe gestionó y midió.

**Conclusión del punto 1:** la implementación satisface el diseño. No encuentro ningún WP incumplido.

---

## 2 · ¿HAY CONTRADICCIÓN MATERIAL QUE OBLIGUE A VOLVER A DISEÑO?

**No.** Reviso las cinco tensiones que un cierre de este tipo suele esconder:

1. **`D-5 = APPROVED` vs `NOT_OCCURRED`.** El informe **detecta y corrige** su propia contradicción
   histórica (§5, §FINAL_MACHINE_VERIFICATION): lo que se autorizó fueron las *firmas del gate*, no la
   *adjudicación de contenido*; QA40 sigue 40/40 PENDING. La corrección es correcta y la dirección es
   la segura (no reivindica adjudicación inexistente). **No es contradicción viva.**

2. **`H10 = PARTIAL / tested_by=0` vs `PASS / tested_by=17`.** También corregida explícitamente, con
   evidencia nueva (RW-0003 ingerido). El cambio de veredicto está **causado por evidencia nueva**, no
   por reinterpretación. **No es contradicción viva.**

3. **`VERIFIES = 0`.** Declarado `N/A` porque el SAT cita referencias de proyecto/función
   (`3.2.3`, `F05.05`), no IDs del catálogo regulatorio. Esto es coherente con el modelo: la traza a
   regulación va por `tested_by → implemented_by → regulated_by`. **Es una propiedad del corpus, no un
   fallo.** Queda como DEV-2. Correcto.

4. **`TESTS_WITHOUT_REQUIREMENT_REF = 162` de 165.** El informe lo declara DEV-3: son Tests reales
   extraídos con evidencia anclada, sin ID de requisito recuperable en el OCR, por tanto sin arista de
   traza. **No es fabricación** (el objeto tiene provenance real). Pero **sí es material para el punto
   4 y 5**: significa que solo 3 de 165 objetos Test enlazan a un requisito, y `tested_by=17` descansa
   sobre esos pocos anclajes. No obliga a rediseño; obliga a que la verificación humana de H-10 mire
   con lupa la tasa de recuperación de referencias, no solo las 77 aristas emitidas (§5).

5. **Fingerprints v2 no comparables con la baseline D-2.** El informe lo explica por dos causas
   legítimas (código nuevo cambia `source_attestation_digest`; `canonical_store_v2` es re-extracción
   limpia mientras producción arrastra clone-drift). **Es una explicación válida, pero es también la
   raíz del único hueco real del plan de validación** — ver punto 3.

Ninguna de las cinco es una contradicción material que invalide el diseño. **No se vuelve a diseño.**

Un único punto que **debe registrarse como corrección de alcance, no de diseño:** el informe usa
"H-2 aisló el audit trail" y "`AUDIT_TRAIL_CHANGED_BY_TESTS = NO`", pero los blockers listan
`EXC-6..9 LEDGER_GUARD_FAILURES` porque el ledger está sin commitear. Son cosas distintas (aislamiento
de escritura de auditoría ≠ estado git del ledger de decisiones) y el informe las mantiene separadas
correctamente. No hay contradicción; lo señalo para que nadie lea los 4 guards como una regresión de
H-2. Lo son de DEV-5, no de H-2.

---

## 3 · ¿ES SUFICIENTE EL PLAN DE VALIDACIÓN v1 vs v2?

**Casi. Falta una prueba explícita que el informe implica pero no demuestra: la paridad v1↔v2 sobre el
corpus compartido.**

Lo que el plan **sí** cubre bien:
- Producción intacta y byte-idéntica (`canonical_store/RW-*` md5 antes/después; `_EXT_VER` sin flipar).
- Rollback real y verificado (flag OFF reproduce v1; `implemented_by`/`designed_by` idénticos).
- Determinismo v2 (RUN1==RUN2 en los tres fingerprints).
- Egress 0 medido en todos los flujos.
- Clone-drift explicado y aislado como preexistente (RW-0012: 595 prod vs 258 fresh, mismo sha, mismo
  code path flag-OFF → no causado por H-10).

Lo que **falta** para que el plan v1-vs-v2 sea suficiente para autorizar la activación:

> **No hay una comparación lado a lado, sobre los mismos 6 documentos, entre lo que v1 produce hoy en
> producción y lo que v2 (`+tests-v1`, re-extracción limpia) produce — a nivel de findings, no solo de
> conteo de aristas.** El informe demuestra que v2 *añade* 165 Test, 17 `tested_by`, 350 `refers_to`,
> y que no *regresa* `implemented_by`/`designed_by`. Pero la pregunta de un revisor de cambio es la
> inversa: **¿v2 elimina, mueve o cambia de banda algún finding que v1 emitía?** El salto de
> `EXTRACTION_VERSION` re-deriva canonical y graph; el clone-drift demuestra que la re-extracción
> limpia produce **menos claims** que el store de producción (258 vs 595 en RW-0012). Si producción se
> activa con re-extracción limpia, **el conjunto de findings cambiará respecto al v1 vigente**, y ese
> delta no está caracterizado en el informe.

Esto no es un defecto de H-10 (que corrió sobre stores v2 paralelos, correctamente). Es un **paso de
validación de activación** que hoy no existe y que debe existir **antes** del flip de `_EXT_VER`. Va a
las instrucciones como R-PAR (read-only, sobre stores paralelos).

Con esa pieza añadida, el plan v1-vs-v2 es suficiente. Sin ella, la activación sería un cambio de
comportamiento no caracterizado, que es exactamente lo que el intended use `DECISION_SUPPORT_TOOL` con
autoridad humana no puede permitirse sin que el humano vea el delta.

---

## 4 · EVIDENCIA HUMANA MÍNIMA ANTES DE PRODUCCIÓN Y D-6

El informe ya la enumera (BLK-1…5, §24). La ordeno por lo que **bloquea qué**, y separo lo que bloquea
*activación productiva* de lo que bloquea *D-6/qualification* — porque bajo `SYSTEM_OF_RECORD=NO` no
son lo mismo y el intended use permite desacoplarlas.

**Mínimo para ACTIVACIÓN PRODUCTIVA de v2 (`+tests-v1`):**
- **E-1 · Verificación humana de la muestra H-10** (`H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json`, 77
  filas: 17 `tested_by` + 60 `refers_to`). Es la que valida que las relaciones nuevas no son ruido.
- **E-2 · Revisión humana del delta de paridad v1↔v2** (R-PAR, punto 3). Sin esto, activar cambia el
  comportamiento sin que nadie haya visto en qué. **Esta es la que el informe no lista y yo añado.**
- **E-3 · Confirmación de que la re-extracción limpia es la base deseada** (el clone-drift implica que
  activar "limpio" reduce claims frente al prod actual; alguien humano debe aceptar esa base).

**Mínimo adicional para D-6 / QUALIFICATION:**
- **E-4 · Adjudicación humana de H-8 (D-5):** QA40 (40 casos → TP/FP/COVERAGE_LIMITED),
  `real_corpus_opportunities.yaml` (recall), unidades negativas (especificidad), firma del held-out
  con `rules_author`. Es el blocker dominante y **no falsificable**: sin ground truth humano no hay
  métricas reales, y sin métricas reales no hay qualification. La IA no puede tocarlo.
- **E-5 · Firmas humanas de Capa 9 / QA sobre H-1…H-7 y D-2.**
- **E-6 · Commit del ledger gobernado** (`ARTIFACT_VERSION-2026-019/020/021`) → limpia los 4 guards
  `store==git-HEAD` (DEV-5). Es mecánico pero es humano (implica push autorizado).

**Orden de dependencia:** E-1 y E-2 y E-3 habilitan activación. E-4 es independiente y puede correr en
paralelo, pero D-6 exige E-4 **y** E-5 **y** E-6 **y** que la activación (E-1..E-3) esté resuelta.
Ninguna la ejecuta un agente.

---

## 5 · RIESGOS RESIDUALES A REGISTRAR

Los DEV-1…DEV-10 del informe son correctos y deben quedar en el registro. Añado o elevo cinco que el
cierre trata de pasada y que, bajo el intended use declarado, merecen estatus de riesgo residual
formal:

- **RR-1 · Cobertura de traza real muy baja: 3 de 165 Test enlazan a requisito** (de DEV-3). `tested_by=17`
  es honesto pero descansa sobre una tasa de recuperación de referencias del ~2 % de los Test. No es
  fabricación ni bloquea, pero el revisor humano de E-1 debe saber que la traza de prueba del sistema
  es **escasa por limitación de OCR/corpus**, no rica. Registrar para que nadie sobreinterprete
  `tested_by>0` como "cobertura de prueba resuelta".
- **RR-2 · Activación limpia ≠ producción actual** (de §12/§17). La base limpia produce menos claims
  (RW-0012: 258 vs 595). Activar corrige el clone-drift pero **cambia el conjunto de hallazgos
  visible**. Riesgo: que se lea como "el sistema dejó de detectar cosas". Debe declararse que el drift
  previo era el defecto y la reducción es la corrección — respaldado por E-2/E-3.
- **RR-3 · `verifies=0` estructural.** Mientras los SAT del cliente citen referencias de proyecto y no
  IDs del catálogo regulatorio, `verifies` seguirá en 0 por corpus. No es transitorio; es una
  propiedad del tipo de documento. Registrar para no re-abrirlo como bug en cada corrida futura.
- **RR-4 · `factory-api` endurecido, `gmp-api` no** (H-5B/H-6B fuera de alcance). El producto base
  sigue con la exposición Postgres/Redis y sin `pg_dump` programado. Bajo `SYSTEM_OF_RECORD=NO` es
  tolerable, pero es un riesgo residual **abierto y explícito**, no cerrado. Su cierre requiere
  autorización de scope separada de Capa 9.
- **RR-5 · Secret-backup bloqueado** (DEV-10). `GOVERNED_STATE_RESTORABLE=YES` mitiga (la atribución
  vive en claro en los ledgers; las claves se re-aprovisionan), pero la decisión de mecanismo de
  backup cifrado de secretos sigue pendiente de humano. No bloquea H-1…H-10; se registra.

Riesgo de proceso, no técnico, que conviene fijar: **el ledger sin commitear (DEV-5) mantiene 4 tests
en rojo.** Mientras no se commitee (E-6), cualquier corrida de regresión futura seguirá mostrando
6 fallos, y existe el riesgo operativo de que alguien "arregle" los guards en vez de commitear. El
guard está haciendo su trabajo: **no tocar los guards; commitear el ledger.**

---

## SÍNTESIS PARA CAPA 9

```
DESIGN_SATISFIED                 = YES (H-1…H-10, en su alcance declarado)
MATERIAL_CONTRADICTION           = NONE (las 2 correcciones históricas son evidencia nueva, no conflicto vivo)
RETURN_TO_DESIGN_REQUIRED        = NO
V1_V2_VALIDATION_SUFFICIENT      = NO_UNTIL_R-PAR (falta el delta de findings v1↔v2 sobre corpus compartido)
HUMAN_EVIDENCE_FOR_ACTIVATION    = E-1 (muestra H-10) + E-2 (delta paridad) + E-3 (aceptar base limpia)
HUMAN_EVIDENCE_FOR_D6            = E-4 (adjudicación D-5) + E-5 (firmas H-1…H-7/D-2) + E-6 (commit ledger)
RESIDUAL_RISKS                   = DEV-1..10 (informe) + RR-1..5 (esta revisión)
PRODUCTION_ACTIVATION            = permanece NOT_AUTHORIZED
NEW_ARCHITECTURE_PROPOSED        = NONE
```

---

# INSTRUCCIONES PARA CLAUDE CODE

Régimen y prohibiciones idénticos a la Fase R previa. **Todo lo que sigue es READ-ONLY sobre stores
paralelos y artefactos ya existentes. No hay implementación nueva. No se toca producción, ni el flag,
ni `_EXT_VER`, ni el ledger, ni QA40, ni la muestra H-10.**

```
NO commit · NO push · NO flip de _EXT_VER/_CANON/_GRAPH · NO activar producción
NO adjudicar QA40 · NO rellenar la muestra H-10 · NO firmar nada · NO tocar los ledger-guards
NO modificar canonical_store/ ni graph_store/ (v1) ni los v2 · NO re-extraer producción
```

## Tarea única: **R-PAR — caracterizar el delta de findings v1 ↔ v2** (cierra el hueco del punto 3)

Objetivo: producir, sin cambiar nada, la comparación lado a lado que hoy falta, para que el humano de
E-2 vea exactamente qué cambia al activar v2.

**R-PAR.1 · Corpus compartido, no el SAT nuevo.** Compara **solo los 6 documentos RW que ya existían en
v1** (RW-0005/0006/0009/0011/0012/0014). RW-0003 es capacidad nueva y no tiene contraparte v1; se
reporta aparte, no dentro del delta de paridad.

**R-PAR.2 · Tres conjuntos de findings, todos ya materializados o regenerables read-only:**
```
A = findings de producción v1 vigente        (canonical_store/ + graph_store/, tal como están)
B = findings de re-extracción limpia v1       (flag OFF, código HEAD, store temporal en /tmp — NO sobrescribir producción)
C = findings de v2 +tests-v1                   (canonical_store_v2/ + graph_store_v2/, ya existentes)
```
El par (A vs B) aísla el efecto del **clone-drift** (mismo código, distinto estado de store).
El par (B vs C) aísla el efecto real de **H-10** (misma extracción limpia, con y sin capacidad nueva).
Separarlos es el punto: el informe mezcla ambos efectos bajo "no comparable".

**R-PAR.3 · Métrica del delta, por documento y agregada:**
```
findings_only_in_A   (v1 prod los emite, la base limpia no)   ← el riesgo RR-2, cuantificado
findings_only_in_C   (v2 los emite, v1 no)
findings_in_both_same_band
findings_in_both_band_changed   (por evidence_basis/ENFORCE)
finding_record_id como clave de emparejamiento (no finding_id)
```

**R-PAR.4 · Entregable:** `docs_plan/R_PAR_DELTA_V1_V2_20260830.md` con la tabla por documento, los
tres pares comparados, y una frase por cada `findings_only_in_A` que explique si desaparece por
clone-drift (esperado, RR-2) o por otra causa (a investigar). **Ninguna conclusión de activación** — el
documento es insumo para E-2/E-3, decisión humana.

**R-PAR.5 · Verificaciones de consistencia del informe que conviene confirmar de paso** (read-only,
reportar PASS/FAIL, sin corregir):
```
- canonical_store/RW-* sigue byte-idéntico al md5 citado en el informe (producción intacta)
- flag V2_TEST_EXTRACTION OFF sobre HEAD reproduce implemented_by=1120 / designed_by=190 y 0 test/refers_to
- los 3 fingerprints v2 (0de04225… / 8ce23f30… / 2b1a300a…) se reproducen desde canonical_store_v2/graph_store_v2
- RW-0012 re-extracción limpia = 258 claims (confirma el clone-drift declarado)
```

Si cualquiera de R-PAR.5 falla, **detente y repórtalo**: sería la primera contradicción material real y
cambiaría el veredicto del punto 2.

## Lo que NO se hace en esta pasada

No se ejecuta E-1…E-6 (son humanas). No se prepara el flip. No se toca el ledger. R-PAR es lo único
pendiente del lado máquina antes de que Capa 9 tenga todo para decidir activación y, por separado, D-6.

---

*Revisión de cierre para decisión humana. Sin rediseño, sin arquitectura nueva, sin work packages
nuevos. R-PAR es verificación read-only, no implementación.*
