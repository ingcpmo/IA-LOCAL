# REGULATORY_SOURCE_GOVERNANCE_SPEC

## 1. Registro regulatorio (schema)

```yaml
- source_id: FDA-OOS-2022
  body: FDA
  regulation: "Investigating Out-of-Specification (OOS) Test Results"
  version: "2022"
  effective_date: <fecha>
  official_url: <URL oficial primaria>
  local_copy: factory/regulatory/sources/canonical/<source_id>/<archivo>
  sha256: <hash de la copia local>
  retrieved_at: <timestamp>
  retrieved_by: <identidad real>
  status: <enum>
  supersedes: <source_id | null>
  reverification_due: <fecha>
  history: [<entradas inmutables de cambios aprobados>]
```

Solo fuentes oficiales primarias (FDA.gov, USP, ICH.org, ISPE/GAMP según
licencia). El corpus **JAMÁS** se fabrica: si el PDF no está disponible, el
estado es `SOURCE_UNAVAILABLE` con estructura de ingesta en
`PENDING_DOCUMENT`.

## 2. Estados (enum cerrado)

`OFFICIAL_SOURCE_VERIFIED` | `LOCAL_CANONICAL_COPY_VERIFIED` |
`PENDING_REVERIFICATION` | `SUPERSEDED` | `REGULATORY_SOURCE_UNVERIFIED` |
`SOURCE_UNAVAILABLE`

## 3. Reglas deterministas

- La inferencia trabaja exclusivamente con copias locales gobernadas;
  Ollama sin acceso a internet (confirmado en la auditoría: único cliente
  es `httpx` local, sin `requests`/`urllib` salientes).
- Conclusión positiva SOLO permitida cuando la fuente está en
  `LOCAL_CANONICAL_COPY_VERIFIED`.
- Fuente no verificada ⇒ `EVALUATION_INCOMPLETE` + `COMPLIANCE_NOT_DETERMINED`
  para **todos** los requisitos dependientes; análisis bloqueado, no
  degradado.
- Nueva versión detectada ⇒ `PENDING_REVERIFICATION`; **nunca** sustitución
  automática. Cambio de URL/versión/hash requiere aprobación humana
  (`approved_by` real) + entrada en `history` + evento de auditoría.
- Copias canónicas inmutables, con la misma disciplina de verificación de
  hash que se exige para los originales de Rockwell
  (`ORIGINAL_DOCUMENTS_IMMUTABLE`).
- Descargas ocurren fuera del proceso de inferencia — AGT-RSG opera en
  batch asíncrono aprobado por humano, nunca dentro de una llamada LLM
  síncrona.

## 4. Estado actual reutilizable

`factory/regulatory/sources/sha256/...` ya contiene PDFs oficiales con
hash (confirmado en la sanitización del reporte URS v2.1: "PDFs oficiales
con hash"). Este es el punto de partida para el catálogo formal, pero hoy
no tiene el schema completo de esta sección (falta `retrieved_by`,
`history`, `reverification_due` como campos versionados explícitos) —
brecha a cerrar en Fase B del roadmap.

## 5. Componente de código

No existe hoy un agente ejecutable `AGT-RSG`. El nombre `risk_agent.py`
en el código actual corresponde a un concepto distinto (AGT-GAP, riesgo de
hallazgos) — ver nota de desambiguación en `CURRENT_AGENT_RUNTIME_AUDIT.md`.
AGT-RSG se construye desde cero sobre los activos estáticos existentes en
`factory/regulatory/sources/`.

## 6. Auditoría y trazabilidad

Todo cambio de estado de una fuente (nueva versión, reverificación,
supersesión) genera un evento de auditoría con identidad real del
aprobador. El historial (`history`) es append-only — nunca se reescribe una
entrada pasada, siguiendo el mismo principio de inmutabilidad que gobierna
los documentos originales de Rockwell.
