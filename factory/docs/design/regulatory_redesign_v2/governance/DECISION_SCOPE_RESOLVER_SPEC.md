# DECISION_SCOPE_RESOLVER_SPEC — §3 del plan

**Estado:** DISEÑO. No implementado.
**Cierra:** A-2, A-3 de `GOVERNANCE_STATE_AUDIT.md` — el hallazgo crítico
(*autorización sin enforcement*: 0 lectores de decisiones en los 5
consumidores).
**Depende de:** `EXTENSIBLE_DECISION_MODEL_SPEC.md`.

---

## 1. El problema en una frase

Hoy la fábrica sabe **qué está autorizado** y no lo consulta nunca. El
resolver es la respuesta a *"¿quién pregunta?"*. Si al terminar la
implementación el resolver existe pero nadie lo llama, el trabajo no sirvió
de nada — por eso el test de no-bypass (§6.4) es tan obligatorio como el
componente.

Módulo propuesto: **`factory/core/decision_scope_resolver.py`**, junto a
`path_policy.py`, del que copia el patrón: *una sola superficie, consultada
por todos, sin implementaciones paralelas*.

---

## 2. API

```python
@dataclass(frozen=True)
class ScopeResolution:
    authorized: bool
    decision_family: str
    target_id: str
    covering_instances: tuple[str, ...]        # decision_instance_id
    effective_snapshot_hash: str | None        # target_set_hash de la cobertura efectiva
    coverage_basis: CoverageBasis
    denial_reason: str | None                  # None ⟺ authorized
    resolved_at: str                           # ISO-8601 UTC
    families_registry_hash: str                # trazabilidad de con qué reglas se resolvió


def resolve(decision_family: str, target_id: str) -> ScopeResolution: ...

def resolve_many(decision_family: str, target_ids: Iterable[str]) -> dict[str, ScopeResolution]: ...

def coverage_report(decision_family: str) -> CoverageReport:
    """Cobertura de la familia frente al registry vigente. Read-only.
    Es lo que alimenta la UI de §9.B y el detector de drift."""
```

### 2.1 `CoverageBasis`

| Valor | Significado | ¿Habilita conclusión formal? |
|---|---|---|
| `HUMAN_CONFIRMED_EXPLICIT` | cubierto por `EXPLICIT_LIST` `human_confirmed` | **sí** |
| `HUMAN_CONFIRMED_SNAPSHOT` | cubierto por `ALL_SNAPSHOT` materializado en la firma | **sí** |
| `RECONSTRUCTED_PENDING_FORMAL_CORRECTION` | solo cubierto por un snapshot reconstruido (§7.2 del modelo) | **no** |
| `NOT_COVERED` | ningún registro `ACTIVE` `human_confirmed` lo incluye | no |
| `REVOKED` | cubierto y luego revocado | no |
| `SUPERSEDED_ONLY` | cubierto solo por registros `SUPERSEDED` | no |
| `PROPOSAL_ONLY` | solo hay una propuesta `agent_proposed` sin confirmar | no |
| `RESOLVER_UNAVAILABLE` | almacén ausente, ilegible o corrupto | no |
| `FAMILY_UNKNOWN` | familia no declarada en `decision_families.yaml` | no |
| `INVALID_RECORD` | el registro que cubriría viola una invariante (p. ej. `target_set_hash` no recomputa, o `resolved_target_ids` vacía) | no |

`authorized == True` **solo** para `HUMAN_CONFIRMED_EXPLICIT` y
`HUMAN_CONFIRMED_SNAPSHOT`. Todo lo demás es `False`.

`RECONSTRUCTED_PENDING_FORMAL_CORRECTION` merece énfasis: es
`authorized=False`. Un snapshot reconstruido permite **leer** el histórico,
nunca **autorizar**. Si permitiera autorizar, la Corrección D1 formal sería
decorativa y el ciclo entero perdería el sentido.

### 2.2 `INVALID_RECORD` y el estado real de D2–D5

`INVALID_RECORD` no es hipotético. Según §7.1 del modelo extensible, los
registros históricos `D2_evidence_packs`, `D3_T039`, `D4_corpus_execution` y
`D5_regenerate_qa_package` se firmaron **sin ningún objetivo**
(`resolved_target_ids` vacía, violando I-3). Tras la migración,
`resolve("D2", <cualquier requirement_id>)` devolverá:

```
authorized     = False
coverage_basis = INVALID_RECORD
denial_reason  = "D2-2026-001 (migrado de D2_evidence_packs) no declara
                  resolved_target_ids: se firmó APPROVE sin decir sobre qué.
                  Requiere re-firma con alcance explícito."
```

Es el comportamiento correcto y es incómodo a propósito: cuatro decisiones
que hoy figuran como "registradas" pasarán a figurar como no autorizantes.
Eso no es una regresión del resolver — es el resolver diciendo la verdad
sobre lo que se firmó.

---

## 3. Reglas duras

| # | Regla |
|---|---|
| R-1 | **Presencia en un registry NO concede autorización.** Que `ecfr_21cfr_part211` esté en `registry.json` no dice nada sobre si D1 lo cubre. |
| R-2 | Fuente no cubierta ⇒ `AUTHORIZED_BY_D1=false` ∧ `REVERIFICATION_ALLOWED=false` ∧ `PACK_USE_ALLOWED=false` ∧ `FORMAL_CONCLUSION_ALLOWED=false`. |
| R-3 | **Ningún consumidor implementa su propia lectura de decisiones.** Una sola superficie, igual que `path_policy`. |
| R-4 | **Fail-closed.** Resolver indisponible, almacén ausente, JSON ilegible, invariante violada, familia desconocida ⇒ `authorized=False`. Nunca una excepción que un `try/except` de un llamador pueda convertir en "siga adelante". |
| R-5 | **Read-only absoluto.** `resolve()` no escribe auditoría, no promueve estados, no muta el almacén, no cachea en disco. Llamarla un millón de veces no cambia nada. Misma disciplina que `get_decisions_state()`. |
| R-6 | El resolver **no interpreta intenciones**. No infiere que "ALL" incluya lo que llegó después, no deduce cobertura por semejanza de ids, no aplica prefijos. Solo pertenencia a un conjunto materializado. |
| R-7 | El resolver **no conoce a sus consumidores**. No hay ramas `if caller == "release_gate"`. La política vive en el registro de familias; el resolver solo la aplica. |

### 3.1 Nota sobre R-4 y las excepciones

La forma de fallar importa. `resolve()` **no lanza** ante un almacén
corrupto: devuelve `ScopeResolution(authorized=False,
coverage_basis=RESOLVER_UNAVAILABLE, denial_reason=<causa concreta>)`.

Razón: un `raise` invita al llamador a envolverlo en `try/except` y seguir.
Un `authorized=False` obliga a tratarlo como lo que es —una denegación— y el
`denial_reason` viaja hasta el informe. La única excepción que sí se lanza es
`ResolverConfigurationError` cuando `decision_families.yaml` no existe: eso
es un fallo de despliegue, no de datos, y debe impedir el arranque.

---

## 4. Algoritmo

```
resolve(family, target_id):

  1. families := cargar decision_families.yaml
     si falla                        → RESOLVER_UNAVAILABLE, False
     si family ∉ families            → FAMILY_UNKNOWN,       False

  2. records := leer decisions_v2.jsonl, filtrar por decision_family == family
     si el almacén no existe o alguna línea no parsea
                                     → RESOLVER_UNAVAILABLE, False

  3. para cada record:
        recomputar target_set_hash y comparar con el almacenado
        validar I-1..I-12
        si falla                     → marcar el record INVALID (no descartarlo
                                        en silencio: se reporta)

  4. si TODOS los records de la familia son INVALID y alguno contenía target_id
     en intención → INVALID_RECORD, False

  5. proyectar status (ACTIVE / SUPERSEDED / REVOKED) recorriendo
     supersedes_instance_id — proyección derivada, nunca leída de disco

  6. cobertura := ⋃ resolved_target_ids de {ACTIVE ∧ human_confirmed ∧
                     tipo ∈ (ORIGINAL, CORRECTION, ADDENDUM, SUPERSESSION)}
     revocados  := ⋃ resolved_target_ids de {ACTIVE ∧ human_confirmed ∧
                     tipo == REVOCATION}

  7. si target_id ∈ revocados                  → REVOKED,        False
     si target_id ∈ cobertura:
          si alguna instancia cubridora tiene provenance=RECONSTRUCTED_SNAPSHOT
          y ninguna NATIVA la cubre            → RECONSTRUCTED_PENDING_FORMAL_CORRECTION, False
          si el modo de la cubridora es ALL_SNAPSHOT
                                               → HUMAN_CONFIRMED_SNAPSHOT,  True
          en otro caso                         → HUMAN_CONFIRMED_EXPLICIT,  True
     si target_id ∈ ⋃ de records SUPERSEDED    → SUPERSEDED_ONLY, False
     si target_id ∈ ⋃ de records agent_proposed→ PROPOSAL_ONLY,   False
     en otro caso                              → NOT_COVERED,     False

  8. effective_snapshot_hash := sha256("\n".join(sorted(cobertura − revocados)))
```

**Complejidad:** lineal sobre el almacén. Con 14 registros hoy y un
crecimiento de unidades por mes, no hay caso para cachear. **Cachear en disco
está prohibido por R-5**; un `functools.lru_cache` en memoria por proceso es
aceptable siempre que se invalide por `mtime` del almacén, y aun así la
recomendación es no hacerlo hasta que exista un problema medido.

---

## 5. `coverage_report` — la detección del drift

Es lo que habría cazado el caso Part 211 en el momento:

```python
@dataclass(frozen=True)
class CoverageReport:
    decision_family: str
    registry_ids: tuple[str, ...]            # lo que hay HOY en el target_registry
    covered_ids: tuple[str, ...]
    uncovered_ids: tuple[str, ...]           # ← Part 211 aparecería aquí
    revoked_ids: tuple[str, ...]
    reconstructed_only_ids: tuple[str, ...]
    registry_hash_now: str
    registry_hash_at_last_decision: str
    registry_drift_since_decision: bool      # hash_now != hash_at_last_decision
    active_instances: tuple[str, ...]
```

Salida esperada hoy para `coverage_report("D1")`:

```
registry_ids                    = (ecfr_21cfr_part11, ecfr_21cfr_part211,
                                   eu_gmp_annex11, mhra_gxp_di_guidance_2018)
covered_ids                     = ()          # ninguno: el único registro D1 es
                                              # RECONSTRUCTED_SNAPSHOT
reconstructed_only_ids          = (ecfr_21cfr_part11, eu_gmp_annex11,
                                   mhra_gxp_di_guidance_2018)
uncovered_ids                   = (ecfr_21cfr_part211,)
registry_drift_since_decision   = True
```

Ese bloque es exactamente el contenido del panel §9.B de la UI. Y muestra
algo que conviene no suavizar: **tras la migración, ninguna fuente estará
formalmente cubierta** hasta que se registre la Corrección D1. Las tres
antiguas quedan en `reconstructed_only`, que no autoriza. Es correcto y es
justamente el estado que el sistema debía haber reportado desde el principio.

---

## 6. Consumidores obligatorios

| # | Consumidor | Archivo real | Qué pregunta | Qué hace si `authorized=False` |
|---|---|---|---|---|
| C-1 | Reverificación de fuentes | `factory/regulatory/source_currency_checker.py` | `resolve("D1", source_id)` | **no reverifica**; devuelve `REVERIFICATION_NOT_AUTHORIZED` con `denial_reason` |
| C-2 | Elegibilidad de Evidence Packs | `factory/regulatory/requirement_catalog/requirement_catalog_loader.py` + `provisional_evidence_model.py` | `resolve("D2", requirement_id)` ∧ `resolve("D1", entry.source_id)` | `PACK_USE_ALLOWED=false`; el requisito sale **NO EVALUADO**, nunca incumplido |
| C-3 | Planificador de corpus | `factory/regulatory/verified_pipeline.py` | `resolve("D4", run_scope)` ∧ C-2 por requisito | excluye el requisito del plan y lo **declara excluido con motivo** (no lo omite en silencio) |
| C-4 | Baseline formal | `factory/regulatory/tools/build_source_baseline_allowlist.py` | `resolve("D1", source_id)` ∧ `resolve("D3", document_id)` | el documento/fuente no entra a la baseline formal; entra a la provisional con limitación declarada |
| C-5 | Release gate | `factory/core/quality_gate_runner.py` + `factory/core/release_manager.py` | `coverage_report(f).uncovered_ids == ()` para D1..D5 ∧ `resolve("AUDIT_EXCEPTION", <fork_event_id>)` | **BLOCKED** con el listado de ids no cubiertos |

### 6.1 Punto de integración de cada uno

- **C-1:** al inicio de la función que compara hashes contra la fuente
  oficial, antes de cualquier acceso a red. Una fuente no autorizada no debe
  ni siquiera generar tráfico saliente.
- **C-2:** dentro de `requirement_catalog_loader`, que ya es fail-closed y ya
  valida cruzadamente contra el source registry. Es el sitio natural: el
  loader **ya** se niega a servir datos inconsistentes; se le añade
  "inconsistente" = "no autorizado".
- **C-3:** en la construcción del plan, no en la ejecución. Un requisito no
  autorizado no debe consumir presupuesto de inferencia ni aparecer en
  `max_calls`.
- **C-4:** en la clasificación formal/provisional, que ya existe.
- **C-5:** como gate propio, `G15_decision_coverage`, añadido a los 14
  actuales de `quality_gate_runner.py`.

### 6.2 Lo que NO cambia

`provisional_evidence_model.py` conserva su decisión deliberada de **no**
bloquear la ejecución provisional por `PENDING_REVERIFICATION` (l.193-194).
El resolver **no revierte** eso: sigue permitiéndose trabajo provisional
sobre fuentes pendientes. Lo que el resolver añade es la separación entre
*pendiente de verificar* (estado técnico, no bloquea lo provisional) y *no
autorizada por un humano* (estado de gobernanza, que sí bloquea incluso lo
provisional, porque nadie firmó que se pudiera tocar).

---

## 7. Tests obligatorios → `TESTS_TO_ADD`

Archivo: `factory/tests/test_decision_scope_resolver.py`

### 7.1 Cobertura y snapshot

| id | Test | Aserción |
|---|---|---|
| T-01 | `test_source_registered_after_all_snapshot_is_not_covered` | **fixture Part 211 real**: D1 `ALL_SNAPSHOT` firmada a las 00:15:15Z con 3 ids; `resolve("D1","ecfr_21cfr_part211")` ⇒ `authorized=False`, `coverage_basis=NOT_COVERED` |
| T-02 | `test_all_snapshot_covers_exactly_the_three_signed_ids` | los 3 ⇒ `HUMAN_CONFIRMED_SNAPSHOT`; un cuarto id inventado ⇒ `NOT_COVERED` |
| T-03 | `test_addendum_extends_coverage_only_for_its_ids` | ADDENDUM con `[part211]` ⇒ part211 autorizado, y los 3 originales **siguen** autorizados por el ORIGINAL |
| T-04 | `test_addendum_does_not_supersede_original` | tras el ADDENDUM, el ORIGINAL sigue `ACTIVE` |
| T-05 | `test_correction_supersedes_and_replaces_set` | CORRECTION con `[a,b]` sobre ORIGINAL `[a,b,c]` ⇒ `c` deja de estar cubierto |
| T-06 | `test_revocation_removes_coverage` | REVOCATION de `b` ⇒ `b` ⇒ `REVOKED` |
| T-07 | `test_revocation_wins_over_later_addendum` | ADDENDUM posterior que re-incluye `b` ⇒ `b` sigue `REVOKED` |
| T-08 | `test_superseded_only_is_not_authorized` | id cubierto solo por un registro `SUPERSEDED` ⇒ `SUPERSEDED_ONLY` |

### 7.2 Fail-closed

| id | Test | Aserción |
|---|---|---|
| T-09 | `test_missing_store_denies` | almacén ausente ⇒ `RESOLVER_UNAVAILABLE`, `authorized=False`, **sin excepción** |
| T-10 | `test_corrupt_json_line_denies` | una línea truncada ⇒ `RESOLVER_UNAVAILABLE` |
| T-11 | `test_tampered_target_set_hash_denies` | mutar `resolved_target_ids` sin recalcular `target_set_hash` ⇒ `INVALID_RECORD` |
| T-12 | `test_unknown_family_denies` | familia no declarada ⇒ `FAMILY_UNKNOWN` |
| T-13 | `test_empty_target_ids_denies` | registro con `resolved_target_ids: []` (los D2–D5 reales) ⇒ `INVALID_RECORD` |
| T-14 | `test_agent_proposed_alone_denies` | solo propuesta sin confirmar ⇒ `PROPOSAL_ONLY` |
| T-15 | `test_reserved_identity_record_denies` | `approved_by_id="human"` ⇒ `INVALID_RECORD` (I-8) |
| T-16 | `test_reconstructed_snapshot_does_not_authorize` | `provenance=RECONSTRUCTED_SNAPSHOT` ⇒ `authorized=False` |

### 7.3 Read-only

| id | Test | Aserción |
|---|---|---|
| T-17 | `test_resolve_writes_no_audit_event` | `log_count` de `verify_chain()` idéntico antes y después de 1 000 `resolve()` |
| T-18 | `test_resolve_does_not_mutate_store` | sha256 del almacén idéntico antes y después |
| T-19 | `test_resolve_is_idempotent` | 100 llamadas ⇒ resultados iguales salvo `resolved_at` |

### 7.4 No-bypass — **la guardia de Gate 0**

Modelado sobre `factory/tests/test_refresh_readonly.py`, que ya es la guardia
análoga para el read path.

`factory/tests/test_decision_resolver_no_bypass.py`

| id | Test | Método |
|---|---|---|
| T-20 | `test_all_five_consumers_import_the_resolver` | AST de los 5 módulos de §6: cada uno importa `decision_scope_resolver` |
| T-21 | `test_all_five_consumers_call_resolve` | AST: cada uno contiene una llamada a `resolve` o `coverage_report` |
| T-22 | `test_no_consumer_reads_the_decision_store_directly` | ningún módulo fuera de `decision_scope_resolver.py`, `decision_legacy_adapter.py`, `decision_log.py`, `w5_human_decisions.py` y `factory/tests/` menciona `decisions_v2.jsonl`, `decisions.jsonl` ni `w5_human_decisions.jsonl` |
| T-23 | `test_no_parallel_coverage_logic` | ningún módulo fuera del resolver define una función cuyo nombre case `r"(coverage|authoriz|approved_source|covered_by)"` |
| T-24 | `test_consumer_list_matches_families_registry` | los `consumers` declarados en `decision_families.yaml` coinciden exactamente con los 5 módulos verificados — si alguien añade una familia con un consumidor nuevo, este test **falla hasta que ese consumidor llame al resolver** |

> T-24 es el que impide que el diseño se degrade con el tiempo. T-22 y T-23
> son negativos —prueban la **ausencia** de algo— y por eso deben ejecutarse
> por AST y no por `grep`: un `grep` se esquiva con una concatenación de
> cadenas.

### 7.5 Prueba por mutación (obligatoria antes de declarar la fase cerrada)

Misma disciplina que la auditoría J–P de `bfe11ba`. Cada mutación debe hacer
fallar **al menos un** test nombrado; si alguna pasa, el test es decorativo:

| Mutación | Debe romper |
|---|---|
| `resolve()` devuelve `authorized=True` incondicionalmente | T-01, T-09…T-16 |
| Se elimina la comprobación de `provenance` | T-16 |
| `REVOCATION` se ignora | T-06, T-07 |
| Se quita el `import` del resolver en `source_currency_checker.py` | T-20, T-21 |
| Un consumidor abre `decisions_v2.jsonl` directamente | T-22 |
| `ALL_SNAPSHOT` se reinterpreta como "todo el registry actual" | **T-01** |

La última es la mutación clave: reproduce exactamente el bug conceptual que
originó todo este trabajo. Si T-01 no la caza, el diseño no está protegido.

---

## 8. Integración con Gate 0

`factory/scripts/ops/factory_selfcheck.sh` gana un paso:

```
6/6  decision coverage
     - resolver importable y decision_families.yaml válido
     - test_decision_resolver_no_bypass.py PASS
     - coverage_report(f).registry_drift_since_decision para f ∈ familias con target_registry
       → WARN si True (no FAIL: el drift es información, no corrupción)
     - registros INVALID_PENDING_RESIGNATURE > 0 → WARN con el listado
```

`WARN` y no `FAIL` es deliberado: hoy el drift **es** `True` y los registros
inválidos **son** cuatro. Hacerlo `FAIL` dejaría Gate 0 en rojo permanente
hasta G2, y un gate que está siempre en rojo deja de leerse. Pasa a `FAIL`
en G8, cuando `CORPUS_READY` exige que ambos sean cero.

---

## 9. Lo que este componente NO hace

- No registra decisiones ni las modifica.
- No promueve estados de fuente (eso es `SOURCE_LIFECYCLE_SPEC.md`).
- No decide si un pack está completo (eso es el validador de §5).
- No verifica la cadena de auditoría (eso es `audit_writer.verify_chain`).
- No sabe qué es Part 211: solo sabe si un id pertenece a un conjunto que un
  humano firmó.
