# QA40 — ALINEACIÓN DETERMINISTA POST E3-A (sin re-muestreo, sin tocar ground truth)

**Fecha:** 2026-08-31 · **Disparador:** E3-A = APPROVE (`ARTIFACT_VERSION-2026-027`, Cesar,
2026-08-31T16:36 · base canónica CLEAN aceptada: RW-0012 = 258 claims). · **Autoridad:** Capa 9 = Cesar.

```
NO re-muestreo · NO modificación de qa40_adjudication_sheet.yaml · NO adjudicación (label sigue PENDING)
qa40_finding_ids_sha256 = 02b6d3d0b6fadb1f882c4e63b7f7421dd387268ddabe5b5f16abfa5d9d360d32   (INMUTABLE, sin cambio)
```

## Resultado

**40/40 casos QA40 son direccionables en el escenario D (candidato H-10 `+tests-v1`).**

39/40 resuelven directo (mismo `finding_record_id`). El 1/40 que no resolvía por `finding_record_id`:

| | QA40 sheet | Escenario D |
|---|---|---|
| `finding_record_id` | `rec-8c79d376a707b7f3` | **`rec-a3965dbc0f624005`** |
| `finding_id` | `fnd-dda4452c2717e340` | `fnd-3416d726b78c9075` |
| `subtype` | `ALCOA_ATTRIBUTABLE_GAP` | `ALCOA_ATTRIBUTABLE_GAP` |
| `document` / `page` | RW-0012 / 5 | RW-0012 / 5 |
| `source_hash` | `721d38e3a1967615bb9b9a8f7ae08c92b604d9a5cba6e709d64ec6e92fa68698` | **`721d38e3a1967615bb9b9a8f7ae08c92b604d9a5cba6e709d64ec6e92fa68698`** (idéntico) |
| `anchored_quote` | "with the proper credentials, the input points can be simulated for troubleshooting or other" | (mismo ancla) |

**Regla de re-resolución determinista:** clave = `(document, subtype, page, source_hash)`.
El `finding_record_id` difiere porque se deriva por corrida (incluye contexto de grafo); el **ancla
es estable** (`source_hash` byte-idéntico). No es un finding nuevo ni un re-anclaje por clone-drift
(esos tienen `source_hash` distinto) — es el MISMO hallazgo analítico con id de registro por-corrida.

```
QA40_CASES_ADDRESSABLE_IN_D          = 40 / 40
QA40_REMAP (1 caso)                  = rec-8c79d376a707b7f3  ->  rec-a3965dbc0f624005   (por source_hash 721d38e3…)
QA40_SET_CHANGED                     = NO   (los 40 finding_id siguen siendo los mismos)
QA40_RESAMPLED                       = NO
qa40_adjudication_sheet.yaml status  = DRAFT_UNSIGNED   (sin cambio ; la adjudicación es D-5, humana)
GROUND_TRUTH_TOUCHED                 = NO
```

Insumo para D-5. **No adjudica precisión/recall/especificidad** — eso exige ground truth humano (D-5).
