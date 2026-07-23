# REQUIREMENT_EVIDENCE_PACK_SPEC

## 1. Regla dura que este spec corrige

Baseline confirmado (sección 3.1.5-6 del plan, y evidencia real en
`compliance_agents.py:57-96` — checkpoints con descripción breve): una LLM
**NUNCA** debe recibir únicamente `requirement_id` + descripción breve. El
baseline actual (121 llamadas = 11 requirement_id × 11 chunks) recibió
exactamente eso — es la causa raíz del falso positivo semántico ANNEX11_4.
Este Evidence Pack es la corrección estructural de esa causa raíz.

## 2. Schema

```yaml
evidence_pack:
  pack_version: <semver>
  requirement_id: <id>
  body: <organismo emisor>
  regulation: <nombre>
  regulation_version: <versión>
  clause: <numeral>
  canonical_text: <texto normativo canónico literal>
  context_before: <texto>
  context_after: <texto>
  governed_interpretation: <interpretación aprobada por humano>
  evidence_min_criteria: [<criterios de evidencia válida>]
  exclusion_criteria: [<qué NO cuenta como evidencia>]
  typical_insufficient_evidence: [<patrones típicos insuficientes>]
  weak_keywords: [<palabras que solas NO demuestran el requisito>]
  expected_doc_types: [URS|FS|SOP|...]
  applicability: <regla desde matriz de aplicabilidad>
  official_url: <URL>
  source_sha256: <hash de la copia canónica>
  source_status: <estado de REGULATORY_SOURCE_GOVERNANCE_SPEC.md>
```

## 3. Contenido obligatorio del prompt regulatorio

El prompt que recibe la LLM (vía AGT-EVD/AGT-VER) incluye obligatoriamente:
texto normativo canónico; contexto regulatorio suficiente
(`context_before`/`context_after`); criterios mínimos
(`evidence_min_criteria`); criterios de exclusión (`exclusion_criteria`);
fragmento documental; ubicación exacta; SHA-256 del documento; schema de
salida; prohibición explícita de inventar implementación; prohibición
explícita de declarar cumplimiento; instrucción de responder
`INSUFFICIENT_CONTEXT` cuando el fragmento no alcance.

## 4. Ejemplo aplicado al caso ANNEX11_4 (retrospectivo, solo como diseño — no re-ejecutado)

Con este pack, `weak_keywords` habría incluido términos como "Risk-Based
Approach" cuando aparecen dentro de un título de referencia bibliográfica
(`GAMP5 A Risk-Based Approach to Compliant GXP Computerized Systems`), y
`exclusion_criteria` habría marcado explícitamente "mención en lista de
referencias/estándares" como no-evidencia. La regla determinista de
validación C (sección 12.1 del plan) habría rechazado automáticamente esta
evidencia sin depender del juicio de la LLM.

## 5. Versionado y cache

`pack_version` (semver) es parte del fingerprint de la corrida
(`PERFORMANCE_AND_INFERENCE_ORCHESTRATION_SPEC.md`). Cambiar el pack
invalida cualquier cache de resultados asociada al `requirement_id`
correspondiente.

## 6. Dependencias y responsable

Construido por AGT-REP a partir del catálogo regulatorio gobernado
(AGT-RSG) y la matriz de aplicabilidad (AGT-APP). Ningún campo de este
schema se genera por LLM — es 100% ensamblado determinista desde fuentes ya
verificadas; la LLM consume el pack, nunca lo produce.

## 7. Estado actual (brecha)

No existe hoy código que produzca este objeto. `compliance_agents.py`
(`PART11_CHECKPOINTS`, `ANNEX11_CHECKPOINTS`, líneas 57-96) es el precedente
más cercano, pero contiene solo descripciones cortas — exactamente el
antipatrón que este spec reemplaza. Brecha completa, gated a Fase C del
roadmap.
