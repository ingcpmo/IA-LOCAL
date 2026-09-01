# D5-D — DISEÑO DE REMEDIATION DEL ANALIZADOR (3 causas raíz)

**Fecha:** 2026-08-31 · **Estado:** DISEÑO — sin código, sin cambios de artefacto, sin commit.
**Origen:** `docs_plan/D5_D_DIAGNOSTIC_FAIL_20260831.md` (RCA read-only).
**Aprobación requerida antes de implementar:** Cesar (Capa 9) — hay cambios en un artefacto
GOBERNADO firmado (`technical_completeness_rules.yaml`) y en el motor determinista.

> Diseño únicamente. No toca ground truth held-out, ni thresholds, ni el expected de ningún caso.
> Los 5 casos HO-T-* están CONTAMINADOS para tuning: **no** son criterio de aceptación (§6).

---

## 0. Invariantes que la remediation NO puede violar

- **0 LLM, sin red.** El motor de completitud es determinista por diseño; se mantiene.
- **fail-closed** si `technical_completeness_rules.yaml` no está `SIGNED`.
- **No aflojar validadores para inflar métricas** (prohibición central `gmp-recall-pipeline`).
- **QA40 sample precision** no baja (hoy 1.0, Wilson [0.7008, 1.0]).
- **RW recall fixture 7P+2N (config H2H4)** no baja (hoy 2/7); 2 negativos siguen limpios.
- Cambiar `REQUIRED_BEHAVIOR` / `SOURCE_REQUIREMENT_ID` / alcance / `family_signals` /
  `topic_anchor` / `cross_reference_suppressors` ⇒ **nueva firma de Capa 9**
  (`version: "1.1"` → `"1.2"`, `supersedes_version: "1.1"`).

---

## 1. Causa raíz #1 — HO-T-002 FN · C03 `BACKUP_RECOVERY_GAP`

### Diagnóstico
`C03.topic_anchor = ["backup","back-up","back up","respaldo","copia de seguridad"]`.
El claim "System data is copied to a network share periodically" no contiene ninguno →
la regla no se ancla → la lógica `family:restore_verified` nunca se evalúa → FN.
El detector solo reconoce el tópico por **substring literal** de una lista corta.

### Diseño — tier de patrón compuesto (`topic_anchor_patterns`)

Añadir a C03 (y habilitar el mecanismo para cualquier regla) un segundo tier de anclaje
**además** del `topic_anchor` literal:

```yaml
# technical_completeness_rules.yaml  (C03.DETERMINISTIC_DETECTION_RULE)
topic_anchor: [...]                      # sin cambios (tier léxico)
topic_anchor_patterns:                   # NUEVO — regex deterministas, se OR-ean con topic_anchor
  # objeto de datos/registros  +  verbo de copia/replicación  +  (cadencia | destino externo)
  - '(?i)\b(data|records?|database|system state|configuration)\b.{0,60}\b(cop(y|ied|ies)|replicat|mirror|snapshot|dump)\b.{0,60}\b(daily|nightly|weekly|hourly|periodic|scheduled|to (an? )?(offsite|remote|network share|tape|external|secondary))\b'
  - '(?i)\b(cop(y|ied|ies)|replicat|snapshot|dump)\b.{0,40}\b(data|records?|database)\b.{0,60}\b(daily|nightly|weekly|periodic|scheduled|offsite|network share|tape)\b'
  - '(?i)\bdisaster recovery\b'
  - '(?i)\b(restore|recovery) (procedure|plan|process|capability)\b'
```

**Por qué compuesto y no "copied" suelto:** "copied" solo dispararía sobre "the report is
copied to the printer". El patrón exige *objeto de datos* + *verbo de copia* + *cadencia o
destino externo* — que es exactamente el concepto de respaldo, expresado sin la palabra "backup".

### Cambio de motor (contenido, pequeño)
`completeness_findings` (`technical_findings.py`, bucle de anclaje ~L235):

```python
topics = [t.lower() for t in ddr["topic_anchor"]]
patterns = [re.compile(p) for p in ddr.get("topic_anchor_patterns", [])]   # NUEVO
...
anchor_rec = next(
    (r for r in recs_by_page if _anchorable(r) and (
        any(t in (r["source_text"] or "").lower() for t in topics)
        or any(p.search(r["source_text"] or "") for p in patterns)          # NUEVO
    )), None)
```

`re` (stdlib), sin red, determinista. Se compila una vez por regla.

### Riesgo / mitigación
Falsos positivos si el patrón es laxo. Mitigación: patrones anclados a *tres* componentes;
medir el delta de findings C03 sobre el dry-run RW completo y revisarlo con Cesar antes de firmar.

---

## 2. Causa raíz #2 — HO-T-003 FN · C05 `AUTHORITY_CHECK_GAP`

### Diagnóstico
Misma evidencia ("existen roles") ancla **C04** (token suelto `"role"`/`"roles"` en
`topic_anchor`) pero **no C05** (`topic_anchor` de C05 exige la frase `"role based access"`).
`C04.topic_anchor` (tokens) y `C05.topic_anchor` (frases) son asimétricos para el mismo dominio
regulatorio (21 CFR 11.10(g)).

### Diseño — C05 se acopla al ancla de C04 (bajo riesgo, no expande C05 document-wide)

**No** se amplía `C05.topic_anchor` con `"roles"` (eso dispararía C05 en cada mención de rol de
un FS de 1409 claims → riesgo de colapso de precisión). En su lugar, regla de acoplamiento
determinista, análoga al `related_finding` C01→C09 ya existente:

```
Si C04 se ancló en una Section S (tópico de acceso/rol presente)
   Y la family:authority_check_at_operation está AUSENTE en el scope de S
   Y no hay cross_reference_suppressor ni inconclusive_downgrader en el ancla
-> emitir también C05 (AUTHORITY_CHECK_GAP) anclado en el MISMO claim,
   como finding independiente (no related), machine_state por defecto de C05.
```

Formalización en el artefacto:

```yaml
# C05.DETERMINISTIC_DETECTION_RULE
anchor_coupling:
  from_case_id: C04                     # C05 hereda el ancla de C04 dentro de la misma Section
  emit_when: "authority_check_at_operation family ausente en scope"
  independent_finding: true             # subtype propio, severidad propia
```

Motor: tras evaluar C04 y registrar `(document, section) -> c04_anchor_rec`, en la pasada de C05
usar ese ancla si C05 no encontró la suya propia. ~15 líneas, contenidas, con guardas.

### Efecto sobre el ground truth
"Three named roles are available…" ⇒ C04 ancla ⇒ `per_operation_authorization` ausente ⇒
ACCESS_CONTROL_GAP (ya ocurría, HO-T-004 TP) **y ahora** `authority_check_at_operation`
ausente ⇒ AUTHORITY_CHECK_GAP (HO-T-003). Ambos, como espera el ground truth.

### Riesgo / mitigación
C05 pasa a emitirse en toda Section donde C04 emite y no se describe verificación de autoridad
en tiempo de operación. En RW esto **añadirá** findings AUTHORITY_CHECK_GAP. Son BORRADOR
ASISTIDO → revisión humana; muchos caerán COVERAGE_LIMITED como los actuales. **Gate:** medir el
delta sobre RW, confirmar que QA40 sample precision no baja (los nuevos C05 no deben crear FP
sobre los 40 casos muestreados) y que el recall fixture no baja. Sign-off de Cesar sobre el
volumen antes de firmar.

---

## 3. Causa raíz #3 — HO-T-N01 FP · C04 `ACCESS_CONTROL_GAP` sobre negativo conforme

### Diagnóstico
El token `"role"` en `"…cannot be modified or disabled by any role including administrators"`
(frase cuyo sujeto es la *inmutabilidad del audit trail*) ancla C04 de forma **incidental**.
`family:audit_trail_privileged_protection` **sí** suprime C01/C09 aquí (contiene
`["audit","cannot be modified or disabled"]`), pero **C04 no tiene ningún supresor equivalente**.

### Diseño — guarda de sujeto de ancla + supresor afirmativo (dos capas, ambas deterministas)

**3a. Guarda de "ancla incidental" (motor + datos gobernados).**
Un `topic_anchor` de **un solo token corto** (`role`, `roles`, `login`, `access`) no ancla la
regla si TODAS sus ocurrencias en el claim caen tras un conector de subordinación/exclusión
y la cláusula principal contiene un `topic_anchor` fuerte de OTRA familia.

```yaml
# bloque nuevo, gobernado
incidental_anchor_guard:
  weak_single_tokens: ["role", "roles", "login", "access", "user"]
  subordinating_connectives: [" by ", " including ", " regardless of ", " except ",
                              " such as ", " other than ", " even ", " nor "]
  strong_foreign_anchors:                 # sujetos de otras familias gobernadas
    - "audit trail"
    - "audit log"
    - "backup"
    - "retention period"
    - "electronic signature"
```

Motor (`completeness_findings`, antes de aceptar `anchor_rec`):

```python
def _incidental(anchor_text, rule_tokens, guard):
    low = anchor_text.lower()
    weak = [t for t in rule_tokens if t in guard["weak_single_tokens"]]
    if not weak:
        return False
    # ¿todas las ocurrencias del/los token(s) están tras un conector?
    cut = min((low.find(c) for c in guard["subordinating_connectives"] if c in low), default=-1)
    if cut < 0:
        return False
    head, tail = low[:cut], low[cut:]
    if any(t in head for t in weak):
        return False                       # el token también está en la cláusula principal
    return any(s in head for s in guard["strong_foreign_anchors"])
```

Para HO-T-N01: head = "the audit trail records … cannot be modified or disabled",
tail = "by any role including administrators". `"role"` solo en tail; head contiene
`"audit trail"` ⇒ **incidental ⇒ C04 no ancla ⇒ FP eliminado.** Generaliza a cualquier
"[cosa de otro control] … by any role".

**3b. Supresor afirmativo `access_control_enforced` (datos, paralelo a los existentes).**
Nueva `family_signals` + wire como supresor adicional de C04 (como
`audit_trail_privileged_protection` suprime C01/C09):

```yaml
family_signals:
  access_control_enforced:               # NUEVO
    - ["cannot be", "by any role"]
    - ["regardless of", "role"]
    - ["no role", "permitted"]
    - ["no role", "can "]
    - ["enforced for", "every", "role"]
    - ["restricted for", "all", "role"]
```

Motor: generalizar el caso especial hardcodeado de C09 a un campo por regla
`additional_suppressor_families: [access_control_enforced]` para C04 (elimina el `if case_id ==
"C09"` especial y lo vuelve declarativo — mejora colateral de mantenibilidad).

### Riesgo / mitigación
3a podría suprimir un ancla legítima si un claim real menciona "roles" solo en una cláusula
subordinada pero SÍ es sobre control de acceso. Mitigación: `strong_foreign_anchors` es una
lista corta y explícita de *otros* sujetos gobernados; si el head no contiene uno de ellos, no
se suprime. Medir el delta de supresión C04 sobre RW; revisar cada supresión nueva con Cesar.

---

## 4. Resumen de cambios propuestos

| # | Artefacto gobernado (`technical_completeness_rules.yaml`) | Motor (`technical_findings.py`) |
|---|---|---|
| 1 | `C03.topic_anchor_patterns` (regex compuesto) | tier de patrón en el bucle de anclaje (~L235) |
| 2 | `C05.anchor_coupling {from_case_id: C04, …}` | C05 hereda ancla de C04 por Section si no tiene la propia |
| 3a | `incidental_anchor_guard {weak_single_tokens, connectives, strong_foreign_anchors}` | `_incidental()` antes de aceptar `anchor_rec` |
| 3b | `family_signals.access_control_enforced` + `C04.additional_suppressor_families` | generalizar el `if case_id=="C09"` a `additional_suppressor_families` declarativo |
| — | `version: "1.2"`, `supersedes_version: "1.1"`, `change_note`, nueva firma de Capa 9 | — |

Ningún `REQUIRED_BEHAVIOR`, `SOURCE_REQUIREMENT_ID` ni `CONTROL_OBJECTIVE` cambia.
`scope_policy` (context_scoped v1.1) se mantiene.

---

## 5. Gates de validación (TODOS deben pasar antes de firmar v1.2)

1. **Unit tests nuevos** (sintéticos, NO derivados de HO-T-*):
   - C03 ancla sobre "records are copied nightly to an offsite server", "database dump weekly to
     tape", "disaster recovery plan"; **no** ancla sobre "the report is copied to the printer".
   - C05 se emite junto a C04 cuando `authority_check_at_operation` ausente; **no** se emite si
     la family está presente en scope.
   - `_incidental`: "audit trail … cannot be disabled by any role" ⇒ C04 no ancla;
     "roles are defined for each operation" ⇒ C04 sí ancla.
   - `access_control_enforced` suprime C04 cuando aparece; regresión: no suprime C01/C09.
2. **QA40 sample precision** re-scored con `real_corpus_adjudication.score_emitted_review`
   sobre la misma muestra (seed 7): sigue `1.0` o su Wilson no empeora. Cero FP nuevos en los 40.
3. **RW recall fixture 7P+2N (H2H4)**: `>= 2/7` (idealmente sube); **2 negativos siguen 0 FP**.
4. **Determinismo**: `graph_technical_findings` / `completeness_findings` producen el mismo
   `FINDINGS_FINGERPRINT` en dos corridas; tests `test_wp_e_*`, `test_semantic_verification_*`,
   `test_technical_*` verdes.
5. **Dry-run RW completo**: diff de findings v1.1 → v1.2 (altas C03, altas C05, bajas C04 por
   supresión). Revisión y sign-off explícito de Cesar sobre el volumen y una muestra de cada clase.
6. **`document_egress_bytes == 0`** en el dry-run.

Si cualquiera falla ⇒ no se firma; se rediseña.

---

## 6. No-overfitting / contaminación

- Los 5 casos HO-T-001…HO-T-N01 **no** son criterio de aceptación de esta remediation.
  `CURRENT_HELD_OUT_REUSE_FOR_FINAL_GATE = PROHIBITED`.
- Aceptación = §5 (regresión RW + fixtures sintéticos nuevos independientes de HO-T).
- El cierre formal de D5 exige, **después** de firmar v1.2 y pasar regresión:
  **D5-D2 — FRESH INDEPENDENT HELD-OUT**: casos nuevos, no observados durante la remediation,
  definidos por Maria Torres (≠ Cesar), materializados como corpus canónico separado, con la
  secuencia de gate formal correcta (confirmación de materialización **antes** de la corrida).

---

## 7. Rollout propuesto (tras aprobación de Cesar)

1. Rama `fix/completeness-rules-v1.2`.
2. Implementar §1–§3 (datos + motor) + §5.1 unit tests.
3. Correr §5.2–§5.6; adjuntar el diff RW y los números.
4. Cesar revisa el diff y **firma** `v1.2` (identidad + timestamp) si los gates pasan.
5. Regresión post-firma (suite completa; los 8 fallos ambientales preexistentes siguen
   clasificados aparte, no cuentan como regresión — ver `D5_D_DIAGNOSTIC_FAIL_20260831.md` §3
   de la sesión y el reporte de suite).
6. Maria Torres define **D5-D2**; materialización canónica separada; corrida; scorer vs
   `0.90 / 0.05 / 0`.
7. Solo si D5-D2 pasa: `D5_D = SIGNED`, `D5_COMPLETE = YES`, luego E5.

**No E5 · No E6 · No commit · No production enablement** hasta que D5-D2 pase.

---

## 8. Estado

```
D5_A = SIGNED · D5_B = SIGNED · D5_C = SIGNED
D5_D = REMEDIATION_REQUIRED   (diseño listo; implementación pendiente de aprobación de Cesar)
ANALYZER_REMEDIATION = OPEN / DESIGNED
D5_COMPLETE = NO
NEXT_HUMAN_ACTION = Cesar (Capa 9) aprueba/ajusta este diseño y autoriza implementar v1.2 en rama,
                    con los gates de §5 como condición de firma.
```
