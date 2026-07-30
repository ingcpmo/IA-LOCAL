# Resumen de sesión — 2026-07-29

**Destinatario:** Cesar (Capa 9)
**Alcance:** agente de la regla predicado 21 CFR Part 211 + pasada de tests que
congelaban conteos del corpus.

---

## Qué se cerró

Dos commits, ambos verificados antes de versionar.

| Commit | Contenido |
|---|---|
| `53f77d1` | Agente `fda_cgmp_211_agent` para la regla predicado 21 CFR Part 211 |
| `26b4319` | Pasada de tests que afirmaban conteos del mundo en vez de invariantes |

Suite **1527 passed / 1 skipped**. Gate 0 **PASS=5 FAIL=0**.

---

## 1. El agente de la regla predicado (`53f77d1`)

`21_CFR_211.68(b)` estaba declarado en el catálogo y en la matriz, pero sin
prompt ni agente — la excepción explícita que quedó escrita en la cabecera de
la matriz v2.1. Ya tiene:

- Prompt gobernado `factory/engines/gmpai_integrity/prompts/cgmp211_prompts.yaml`:
  un checkpoint, mismo contrato de salida (`checkpoint_llm_response_v1`) y mismo
  motor compartido que los otros tres. **Cero lógica de motor nueva.**
- Perfil `integrity_cgmp211_ot_profile` en `factory/profiles/integrity_profiles.yaml`,
  términos de dominio en `requirement_terms.yaml`, y la rama de Capa 8 que lo
  propone.

La única regla del `common_contract` que no se copió de los otros tres es la que
justifica que sea un agente aparte: prohíbe resolver un requisito **predicado**
citando controles de Part 11, Annex 11 o ALCOA+ que no estén en el texto
canónico inyectado. Sin ella, el modelo encuentra "audit trail conforme" y lo da
por evidencia de un requisito de respaldo que no cumple.

### Hallazgo

`21_CFR_PART_211` ya se detectaba en `REGULATORY_KEYWORDS` desde siempre,
entraba en `detected_flags`… y moría ahí. Nunca llegaba a la spec ni generaba
decisión de agente. La regla predicado se reconocía y se descartaba en silencio.
Se añadió `cgmp211_required` con default `False`: ninguna construcción previa de
`RequirementSpec` cambia.

### Declarado ≠ operativo, y ahora está probado

El Evidence Pack sigue en `PENDING_HUMAN_INTERPRETATION`, así que el gate 4
bloquea la llamada. `factory/tests/test_cgmp211_agent.py` cubre las dos mitades:

- **Hoy:** cero inferencias, el requisito sale *no evaluado* — **nunca
  `no_cumple`**. Afirmar incumplimiento de algo que jamás se le mostró al modelo
  sería peor que no evaluarlo.
- **Con criterios inyectados** (mutación controlada, sin tocar el catálogo
  real): admite el checkpoint, construye el prompt con texto canónico y
  criterios numerados, y ejecuta. Es decir: **falta la redacción humana, no
  código.**

Se actualizó la cabecera de la matriz, que afirmaba que no había agente.

---

## 2. La pasada de tests (`26b4319`)

Barrido de los 103 archivos de la suite. De 390 aserciones numéricas, **15
archivos** tenían el patrón real.

**Criterio de triage:** un conteo sobre datos que el propio test construye es
correcto. El defecto es congelar un hecho del corpus real, que evoluciona.

El caso de referencia ya estaba documentado en el repo (`test_status_risks.py`):
cuando `r6_change_control` se devolvió a ajustes —transición gobernada,
legítima y auditada— dos tests cayeron y tumbaron Gate 0. Eso crea presión para
no cerrar misiones reales.

Lo mismo estaba latente en varios sitios más:

- **El más serio:** un test congelaba que las fases cerradas son `{0, 2, 4}`, así
  que **cerrar la Fase 3 —objetivo declarado del roadmap— habría roto la suite.**
- `test_golden_regression` exigía igualdad exacta con `{C1..C4}`: *ampliar* el
  dataset lo rompía.
- Conteos del corpus: 13 documentos y 247 findings (readiness), 267/83/184
  (resumen de correcciones), 32/14/18 (alcance declarado), el 14 de Rockwell en
  dos sitios.

### Varios quedaron más fuertes que el conteo que reemplazan

- El resumen de correcciones debe **particionar** la matriz: ningún finding
  perdido ni contado dos veces. El conteo no lo detectaba.
- Ningún documento del RC con findings puede quedarse sin fila de readiness.
- El presupuesto de tokens se contrasta contra lo que el motor **realmente
  envía** — el defecto de `NUM_PREDICT` del 28-jul.

Dos casos cambiaron conteo por **nombres** (los 6 documentos no listos para
generación, los 4 controles `NOT_EVALUATED`): mismo tripwire, pero al fallar
dicen *qué* cambió.

### Intactos a propósito

Los tripwires deliberados: los 4 `source_id` del registry real y las versiones
regulatorias (`"revision 1"`, `2011-06-30`). Ahí el valor congelado **es** el
control, y que cambie debe doler.

### Verificación por mutación

Suite verde no basta: un test relajado también pasa. Cinco mutaciones del código
real, revertidas después:

| Mutación | Resultado |
|---|---|
| La matriz de readiness pierde un documento en silencio | detectada |
| Off-by-one en una categoría no vacía del resumen | detectada |
| El motor vuelve a `num_predict = 1024` fijo | detectada |
| Una fase se declara `CERRADA` con pendientes abiertos | detectada |
| Un documento OCR deja de bloquearse | detectada |

---

## Lo que requiere decisión de Capa 9

1. **Camino crítico:** redactar `evidence_min_criteria`, `governed_interpretation`
   y `exclusion_criteria` de `21_CFR_211.68(b)`. Es juicio regulatorio, fuera del
   alcance de Capa 8. Al escribirlos hay que sacar el req_id de
   `PENDING_HUMAN_INTERPRETATION_REQ_IDS` (`factory/tests/conftest.py`) — los
   tests ya exigen que esa lista y lo que el gate bloquea digan lo mismo.
2. **Matriz v2.1:** las filas añadidas tras MC-0001 siguen `# PROPUESTO`. Sus
   propias reglas exigen re-confirmación humana (tipo `MC-0002`).
3. **`ecfr_21cfr_part211` sin cobertura de D1:** sigue sin cadencia de
   reverificación ni autoridad declarante.

---

## Dos apuntes

**La calificación del modelo está invalidada por dos causas, no una.** Ya lo
estaba por el cambio de catálogo (`6486405a` → `a83c8168`) antes de tocar nada;
el prompt nuevo añade `prompt_versions` como segunda clave cambiada, porque el
fingerprint deriva del glob del directorio. Al recalificar aparecerán ambas.

**Salvedad honesta sobre un test:** en `test_gmpai_document_readiness.py` la
expectativa se deriva de los mismos `records` que recorre el servicio, así que
está cerca de reformular la implementación. Es al menos tan fuerte como el
`== 13` que había —que también lo era, y además se rompía al crecer el corpus—
pero no es un invariante independiente. Para eso haría falta una fuente distinta
contra la que contrastar, y hoy no la hay.

---

`REGULATORY_COMPLIANCE = NOT_DETERMINED` · `PRODUCTION_ENABLEMENT = BLOCKED`
