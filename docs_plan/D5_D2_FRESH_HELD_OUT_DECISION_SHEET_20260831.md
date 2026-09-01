# D5-D2 — FRESH INDEPENDENT HELD-OUT · HOJA DE DECISIÓN (autora independiente)

**Autora independiente:** Maria Torres (QA Validation Engineer) — validez nominal/repo-level.
**Fecha de emisión:** 2026-08-31 · **Estructura:** Capa 8 · **Ground truth:** exclusivamente Maria.
**Autoridad excluida:** Cesar (Capa 9) — `independent_author_required: true`, `excluded_authors: ["Capa 9 (Cesar)"]`.

> D5-D2 sustituye al held-out contaminado (HO-T-001…HO-T-N01, `CURRENT_HELD_OUT_REUSE_FOR_FINAL_GATE=PROHIBITED`).
> **Prohibido reutilizar o parafrasear trivialmente** los HO-T. Casos NUEVOS, dominio y redacción distintos.
> Se evalúa contra las reglas de completitud **v1.2** (tras `APPROVE_REMEDIATION_V1_2`).
> Match ESTRUCTURAL: `[finding_class, subtype, document, page_band]`, `page_band_tolerance: 3`.
> Thresholds CONGELADOS (idénticos a D5-D): `recall ≥ 0.90 · false_positive_rate ≤ 0.05 · fabricated_citations = 0`.

---

## 0. Corpus held-out D5-D2 (documentos NUEVOS — dominio: sistema de gestión de datos de cromatografía / LIMS)

Tres documentos sintéticos, materializados por un builder separado (`build_seed_corpus_d5d2`),
**sin** solapamiento léxico con los HO-T ni con RW. La redacción la fija el builder; el ground
truth (abajo) solo fija posición y tipo esperado. Documentos previstos:

| doc | tipo | rol |
|---|---|---|
| `HO2-URS` | URS | requisitos de usuario del CDS/LIMS |
| `HO2-FS` | FS | especificación funcional **con brechas deliberadas** |
| `HO2-FSOK` | FS | especificación funcional **conforme** (para el/los negativo(s)) |

`page_band` reales se resuelven **tras** materializar (D5-D2 punto 7C) y Maria los confirma en
`MATERIALIZATION_MATCHES_GROUND_TRUTH=YES` **antes** de ejecutar el analizador (sin backdating).

---

## 1. Casos candidatos — Maria decide cada campo (NO los infiere Capa 8)

Cobertura mínima exigida: **backup/recovery · authority-check · access-control · audit-trail integrity · ≥1 negativo conforme**.
Maria puede añadir casos si su revisión lo justifica.

### HO2-T-001 — backup / recovery

- **Texto del claim (builder, HO2-FS):** *"Chromatography result files are transferred each night to a separate archive volume in the data centre."*
- **Categoría objetivo:** backup/recovery completeness (Annex 11 §7.2 — realización regular **y** verificación de restauración).
- **Qué debe decidir Maria:**
  ```
  EXPECTED_FINDING     = true | false
  EXPECTED_CLASS       = ______            (p.ej. TechnicalFinding)
  EXPECTED_SUBTYPE     = ______            (p.ej. BACKUP_RECOVERY_GAP)
  PROVENANCE           = REG | DOM | ADV
  SOURCE_CLAUSE        = ______            (OBLIGATORIA si PROVENANCE=REG)
  RATIONALE_NOTE       = ______
  HUMAN_REVIEWED       = true
  HUMAN_APPROVED       = ______            (OBLIGATORIO si PROVENANCE=ADV)
  ```

### HO2-T-002 — authority check at operation

- **Texto del claim (builder, HO2-FS):** *"The application provides four user profiles: Analyst, Reviewer, Supervisor and Administrator."*
- **Categoría objetivo:** authority-check completeness (21 CFR 11.10(g) — verificación técnica de autoridad en el momento de cada operación).
- **Qué debe decidir Maria:** (mismos 8 campos)

### HO2-T-003 — access control model

- **Texto del claim (builder, HO2-FS):** *"Instrument methods may be edited by users with the appropriate profile."*
- **Categoría objetivo:** access-control completeness (21 CFR 11.10(g) — nivel de autorización por operación aplicable).
- **Qué debe decidir Maria:** (mismos 8 campos)

### HO2-T-004 — audit trail integrity

- **Texto del claim (builder, HO2-FS):** *"Every change to a result is written to the audit trail with the user name and a date-time stamp."*
- **Categoría objetivo:** audit-trail integrity completeness (21 CFR 11.10(e) — detección de manipulación / protección privilegiada).
- **Qué debe decidir Maria:** (mismos 8 campos)

### HO2-T-005 — access-control precision (posible candidato débil)

- **Texto del claim (builder, HO2-FS):** *"Only a member of the Supervisor or Administrator profile can approve a batch of results."*
- **Categoría objetivo:** ¿es esto un `ACCESS_CONTROL_GAP`, un candidato débil, o evidencia afirmativa (no-hallazgo)? — **decisión de Maria**.
- **Qué debe decidir Maria:** (mismos 8 campos, incluida la opción `EXPECTED_FINDING=false`)

### HO2-T-N01 — negativo conforme

- **Texto del claim (builder, HO2-FSOK):** *"The audit trail records the user, the timestamp, the previous value and the new value for every change; it is append-only and cannot be edited or switched off by any profile, and its integrity is verified during periodic review."*
- **Categoría objetivo:** control descrito por completo → el analizador **NO** debe emitir nada.
- **Qué debe decidir Maria:**
  ```
  EXPECTED_FINDING     = false
  EXPECTED_CLASS       = None
  EXPECTED_SUBTYPE     = None
  PROVENANCE           = REG | DOM | ADV
  RATIONALE_NOTE       = ______
  HUMAN_REVIEWED       = true
  ```

### HO2-T-N02 — negativo conforme (backup con verificación de restauración)

- **Texto del claim (builder, HO2-FSOK):** *"Result files are copied nightly to an offsite archive and the restore procedure is exercised during validation and re-tested every six months."*
- **Categoría objetivo:** backup **con** verificación de restauración → **NO** hallazgo.
- **Qué debe decidir Maria:** (`EXPECTED_FINDING=false` + los campos del negativo)

---

## 2. Entrega de Maria

Responder con los 7 bloques `HO2-T-00x` / `HO2-T-N0x` completos (más adicionales si los hay).
**Sin `page_band`** en esta fase (se resuelve tras materializar). Con eso, Capa 8 (sin decidir juicios):

```
1. transcribir LITERAL en factory/regulatory/requirement_catalog/held_out_technical_corpus_d5d2.yaml
2. PRE_RUN_GROUND_TRUTH_SHA256 = sha256(json canonical de {expected_finding, expected_class,
     expected_subtype, provenance, source_clause_or_rationale, human_reviewed, human_approved}
     por caso + thresholds + match_policy)  -- recomputar 2x desde disco -> HASH_MATCH=YES
3. GROUND_TRUTH_FROZEN = YES  (prohibido cambiar expected/class/subtype/provenance/thresholds)
4. materializar corpus canónico NUEVO (build_seed_corpus_d5d2) -- no RW, no HO-T, no corpus de tuning
5. registrar source_sha256 por doc, canonical IDs, paths, page_band reales, canonical fingerprint
6. presentar la tabla PRE-RUN a Maria -> detenerse para MATERIALIZATION_MATCHES_GROUND_TRUTH=YES
7. UNA corrida del analizador con reglas v1.2 aprobadas -> fingerprints + provenance + egress 0 + llm 0
8. presentar expected vs actual -> detenerse para la confirmación post-run de Maria (sin cambiar expected)
9. firma gobernada (status=SIGNED, author=rules_author=Maria, signed_at) -> assert_usable_as_gate()=PASS
10. scorer vs 0.90 / 0.05 / 0  ->  D5_D2=PASS => D5_D=SIGNED, D5_COMPLETE=YES  |  D5_D2=FAIL => STOP
```

**No tuning automático contra D5-D2.** Un `D5_D2=FAIL` se reporta con el threshold exacto y se detiene.
