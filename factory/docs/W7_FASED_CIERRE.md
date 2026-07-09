# W7 Fase D — Cierre: ejecución real gated del análisis de casos regulatorios

**Fecha de cierre:** 2026-07-09 · **Decisión final:** v3 ACEPTADO por Cesar
(solo registro — el análisis aceptado NO entra a ningún documento GMP).
**Compromiso de Fase D (W7_PLAN.md):** análisis de 1 caso real con Cesar,
ciclo de decisión completo, cierre con informe. **CUMPLIDO.**

## 1. Objetivo y alcance ejecutado

Primera ejecución real end-to-end del análisis de casos regulatorios
(Fases A/B/C de W7) sobre 1 caso real de memoria regulatoria:
`openfda_enforcement:D-0554-2026` (recall Class II, Lack of Assurance of
Sterility) contra la misión `oos_hplc_investigator`. Modelo:
`qwen2.5:7b-instruct-q4_K_M` (Ollama host, CPU). Ciclo completo:
draft → request_changes → revisión → request_changes → revisión → accept.
Las tres decisiones humanas y las dos regeneraciones se ejecutaron **desde
la UI de Fase C** (Mission Control → Inteligencia → Memoria de casos),
validando además el flujo UI end-to-end con navegador real (Chromium
headless dirigido por Playwright; evidencia de red, consola y screenshots
archivada en el scratchpad de la sesión 2026-07-09).

## 2. Cronología auditada (cadena hash, 6 eventos)

| UTC | Evento | Detalle | entry_hash |
|---|---|---|---|
| 07-08 22:07:22 | case_analysis_generated | v1 draft, temp 0.2, 595 s | c22c883dc43c… |
| 07-09 03:26:39 | case_analysis_decision | request_changes v1, Cesar | c7e9833f7534… |
| 07-09 03:36:42 | case_analysis_generated | v2 revision de v1, temp 0.0, 603 s | bcf5d0904ca0… |
| 07-09 03:51:47 | case_analysis_decision | request_changes v2, Cesar | bd2b3b75b890… |
| 07-09 04:01:50 | case_analysis_generated | v3 revision de v2, temp 0.0, 603 s | 808982bf6588… |
| 07-09 04:10:46 | case_analysis_decision | accept v3, Cesar | d1bcea185314… |

Ledger de guidances verificado por SHA-256 contra los textos originales:
`4d2e1d5e…` (guidance 1) y `067061d0…` (guidance 2); v3 lleva ambas
acumuladas en `revision.guidance_ledger` y en el evento.

## 3. Resultados por versión

- **v1 (draft):** análisis válido a la primera pasada. 6 claims
  (1 supported / 2 partially / 0 unsupported / 3 unverifiable), verificador
  v2.1 sin findings, confianza media, sin flags. Defecto de calidad
  detectado por el revisor humano: viñeta [SE] en Acciones redundante con
  el [SE] de Impacto (falta de confirmación de alcance).
- **v1→v2 (guidance de BORRADO: "Elimina la viñeta [SE] de Acciones…"):**
  **guidance NO aplicada.** v2 = v1 byte a byte (100% verbatim, diff vacío).
  El prompt contenía el bloque de revisión y la instrucción íntegra
  (verificado en `prompt_full`): el fallo es del modelo, no del pipeline.
  0 regresiones (trivialmente), 0% cumplimiento.
- **v2→v3 (guidance de REEMPLAZO POSITIVO: "Reescribe únicamente la sección
  Acciones. Debe conservar solo la viñeta normativa [REF: 21 CFR 211.192] y
  eliminar cualquier viñeta [SE] redundante…"):** **cumplimiento exacto.**
  Diff = exactamente 1 línea eliminada (la viñeta [SE] redundante); Acciones
  quedó con solo la viñeta [REF]; las demás secciones byte-idénticas
  (10/11 líneas, 90.9% conservado). 0 regresiones. Claims 1/2/0/2
  (unverifiable 3→2 = la viñeta eliminada), verificador v2.1 sin findings,
  confianza media, sin format_retry.

## 4. HALLAZGO OPERATIVO — calibración provisional para qwen 7B

En esta prueba, con temp 0.0 y la respuesta anterior en contexto:

1. La **guidance negativa de borrado** ("elimina X") **no fue aplicada**:
   el modelo reprodujo su salida anterior íntegra, sin cumplimiento y sin
   señal alguna de fallo (formato válido, verificador limpio).
2. La **reformulación positiva como reemplazo** ("reescribe la sección
   dejando solo Y") **logró cumplimiento exacto sin regresiones**.
3. Esta regla queda como **calibración provisional para qwen 7B — NO como
   garantía universal**: n=1 por tipo de instrucción, un solo caso, un solo
   modelo. Complementa la calibración de Fase 0 (1 acción por instrucción).

Implicación de gobierno: el modo revisión (W6.5.1) garantiza no-regresión y
trazabilidad, pero **no garantiza cumplimiento de la guidance** — el
cumplimiento sigue siendo verificación humana (o determinista futura, §6).

## 5. Validación del flujo UI end-to-end (objetivo añadido por Cesar)

Las 3 decisiones se emitieron desde la página real
`http://localhost:9000/mission-control` (conectar con API key → Memoria de
casos → buscar → "Analizar con agente" → nombre real + motivo → botón de
decisión). Evidencia: POST del navegador capturado con headers
(`referer: /mission-control`, user-agent HeadlessChrome, x-api-key
presente), access log de factory-api con la secuencia GET/POST/GET 200 por
ciclo, body de respuesta recibido por la página, screenshots del recorrido,
consola JS sin errores. Hallazgo cosmético (no bug): el chip de versión se
renderiza en mayúsculas por CSS (`text-transform: uppercase`), a considerar
por quien automatice contra `innerText`.

## 6. Integridad post-cierre

- Suite: **430 passed** · Selfcheck: **PASS=4 FAIL=0** (Gate 0 OK).
- Cadena de auditoría: **315 entradas, 0 hash_errors** (solo el fork
  histórico aceptado; part11 true).
- `cases.jsonl`: **intacto** (mtime 2026-07-03 16:02:54, sin escritura
  durante toda la fase; sha256 ec95766a…).
- Dossier de validación: **intacto** (ningún YAML de factory/validation/
  modificado desde antes de v1; el análisis aceptado no toca aprobaciones).
- Persistencia inmutable: v01/v02/v03.json en
  `regulatory/case_analyses/oos_hplc_investigator/openfda_enforcement__D-0554-2026/`
  (data runtime escrita por el contenedor, fuera de git — mismo patrón que
  factory/validation/).

## 7. Limitaciones abiertas

1. **Cumplimiento de guidance no verificado por máquina**: el verificador
   v2.1 no flaggea "guidance no aplicada" (v2 pasó limpio siendo copia
   total; se detectó por diff externo). Candidato de bajo costo y
   determinista: flag `guidance_unapplied` cuando una revisión produce
   respuesta idéntica a su `based_on_version` (aplica también al pipeline
   de dossier). Requiere aprobación como mejora.
2. **Calibración 7B provisional** (§4): reemplazo positivo sí, borrado no —
   sin garantía universal; reevaluar ante cambio de modelo o GPU (disparador
   ya previsto en el gate W6.5.1).
3. **Latencia**: ~10 min por corrida en CPU (595–603 s); el flujo UI lo
   soporta (cronómetro + recuperación), pero limita la iteración.
4. **Muestra n=1**: un caso, una misión, un agente (qa_oos_profile);
   escalar a más casos/fuentes sigue gated.

## 8. Estado por componente al cierre

Pipeline de análisis de casos (Fase B): FUNCIONAL en real · Modo revisión +
ledger + temp 0.0 (W6.5.1): FUNCIONAL (con la limitación §4) · Verificador
v2.1: FUNCIONAL (con la limitación §7.1) · UI Fase C: FUNCIONAL end-to-end ·
Auditoría/gobierno/persistencia inmutable: FUNCIONALES · Decisión humana con
nombre real: FUNCIONAL en las 3 decisiones.

## 9. Siguiente paso recomendado

Commit de cierre de Fase D (este informe + 1 línea de texto en
mission_control.html actualizada en la fase). Después, en orden de valor:
(a) flag determinista `guidance_unapplied` en el modo revisión (§7.1,
pequeño y testeable); (b) retomar la contribución humana de juicio QA en el
dossier (pausada desde W6.2.1, mueve readiness); (c) escalar el análisis a
un segundo caso/fuente cuando Cesar lo autorice. Todo gated por aprobación.
