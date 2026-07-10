# W8 — Grounding regulatorio (propuesta de diseño, sin implementar)

Estado: **PROPUESTA, pendiente de aprobación de Cesar.** No hay código
escrito para este bloque. Este documento reconstruye el alcance desde el
trabajo ya cerrado (Corpus Regulatorio, W6.3/W6.4, W6.5/W7) porque no
existía un plan formal con este nombre — es la base a aprobar antes de
tocar código, igual que se hizo con `W7_PLAN.md` y el gate
`W6_5_1_GATE_REVISION_DIRIGIDA.md`.

## Diagnóstico: qué existe ya

- **Corpus regulatorio** (`a213740`): 4 colecciones ChromaDB (oos, lims_di,
  hplc, gmp_fda), 9 docs oficiales, disclaimer default-deny. Fase 3
  (USP/ISPE) quedó pendiente de licencias.
- **Memoria de casos** (W6.3/W6.4): 1 conector online (openFDA Drug
  Enforcement), cita trazable, routing a agente por señales, confianza y
  gobierno por caso.
- **Análisis de casos por agente** (W6.5→W7.1): pipeline demostrado
  end-to-end en **1 caso × 1 misión** (openfda_enforcement:D-0554-2026 ×
  oos_hplc_investigator), verificador v2.2 (`unverified_reference`,
  `negation_contradicted`, `multi_claim_line`, `guidance_unapplied`), modo
  revisión con ledger acumulado.
- **Dossier de validación** (W6.2): generación asistida + aprobación
  humana, **flujo separado** del análisis de casos — no se citan entre sí.

## Objetivo

Que el grounding regulatorio deje de ser una demostración puntual (1 caso)
y un flujo aislado (dossier vs. análisis de casos), y pase a ser
**evidencia reutilizable y citable desde el dossier real**, con el mismo
nivel de gobierno (verificador, ledger, auditoría) ya validado en W6.5/W7.

## Alcance de esta propuesta (3 bloques, cada uno gated por separado)

### Bloque 1 (candidato W8) — Escalar el análisis de casos más allá de 1
Correr el pipeline ya existente (sin cambios de código, o mínimos) sobre
más casos de la memoria regulatoria actual y, si aplica, otra misión
(`lab_qc_project`), para confirmar que el comportamiento de W7 Fase D no
fue un artefacto de un único caso. Sin esto, "grounding" descansa en n=1.

### Bloque 2 (candidato W9) — Conectar análisis de casos → dossier
Diseñar cómo una propuesta de análisis de caso **aceptada** (`accept`, no
solo `draft`) puede citarse desde una sección del dossier (p. ej.
`data_integrity_assessment`, `capa`) sin fusionar los dos modelos de
aprobación (dossier: `approve` formal; caso: `accept`/`reject` ya
existente) ni las auditorías. Requiere decisión de diseño explícita: ¿el
dossier referencia el caso por ID, o el generador incorpora texto?

### Bloque 3 (candidato W10) — Segunda fuente regulatoria
Segundo conector online, mismo patrón que W6.3 (`regulatory_connector_service.py`):
openFDA Device/Food Enforcement (recomendado en el cierre de W6.3;
Warning Letters desaconsejado por ser scraping/HTML, fase propia).

## Fuera de alcance de esta propuesta

Ejecutor/scheduler de tareas, conectores no-openFDA (EudraGMDP, Warning
Letters), embeddings, perfiles de agente derivados, contribución humana de
juicio QA en el dossier (backlog ya conocido, sin relación directa con
grounding).

## Criterio de cierre de W8 (Bloque 1)

- Al menos 2 casos adicionales analizados end-to-end (draft → decisión
  humana), con al menos 1 en una misión distinta de `oos_hplc_investigator`.
- Verificador v2.2 ejercitado en los casos nuevos sin falsos positivos
  nuevos no explicados.
- Ningún cambio a los flujos de dossier (W6.2) ni a la memoria de casos
  (W6.3/W6.4) — solo ejecución/observación del pipeline existente.
- `factory_selfcheck.sh` PASS=4 FAIL=0 y cadena de auditoría íntegra tras
  cada ejecución.
- Informe de cierre (`W8_GROUNDING_CIERRE.md`) con los hallazgos, igual
  formato que `W7_FASED_CIERRE.md`.

## Primer paso concreto recomendado

**Arrancar por el Bloque 1**, no por el 2 ni el 3: es el que menos riesgo
de diseño tiene (reusa código ya cerrado, sin nuevos endpoints), y su
resultado (¿escala el pipeline a más de 1 caso sin regresiones?) es la
precondición real para que el Bloque 2 (conectar con el dossier) tenga
sentido — conectar el dossier a una capacidad demostrada en n=1 sería
prematuro. El Bloque 3 (segunda fuente) es independiente y puede
posponerse sin bloquear a los otros dos.
