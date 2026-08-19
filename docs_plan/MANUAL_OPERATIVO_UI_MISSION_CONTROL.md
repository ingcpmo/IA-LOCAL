# MANUAL OPERATIVO — MISSION CONTROL (GMP AI Factory)

Para: Cesar (Capa 9). Escrito en lenguaje directo, paso a paso. Este
manual describe qué ves, qué debes revisar tú y qué botón hace qué —
nada aquí se aprueba solo. Basado en auditoría real del código y de la
API en vivo (2026-08-19), no en supuestos.

──────────────────────────────────────────────────────────────────────────
## LOS CUATRO AVISOS MÁS IMPORTANTES — LEE ESTO PRIMERO
──────────────────────────────────────────────────────────────────────────

### AVISO 1 — Hay dos motores, no uno

Cuando veas resultados de `gmpai_document_validation` (el proyecto
Rockwell), pueden venir de dos sitios distintos y NO debes tratarlos
igual:

- **Motor histórico (LEGACY):** generó el primer informe grande, el RC
  v1.4 de julio. Vive en una carpeta que ni siquiera está guardada en
  Git (`factory/workspaces/gmpai_document_validation/app/`). Está
  **apagado** — no hay ningún cron, ni botón, ni proceso que lo vuelva a
  ejecutar hoy. Es historia, no algo que sigue corriendo en segundo plano.
- **Motor actual:** todo lo que ves después de agosto — las corridas
  Tier-1, la cola de revisión (`review-queue`), los hallazgos con página
  y cita ancladas. Este es el que sigue vivo y el que debes confiar para
  trabajo nuevo.

Si algún día ves un resultado de `gmpai_document_validation` que "no
cuadra" con lo que esperas del sistema actual, pregunta primero de qué
motor viene antes de asumir que es un bug.

### AVISO 2 — Nadie puede "liberar" un documento, ni por accidente

Existe una función en el código (`create_release_record`) que en teoría
marcaría un documento como oficialmente liberado. **No tiene ningún botón
ni ruta de API conectada.** Es decir: aunque alguien —tú, yo, o cualquier
usuario de la UI— quisiera forzar una liberación, no hay forma de
hacerlo desde el sistema tal como está hoy. `DOCUMENT_RELEASED` siempre
va a decir `false`. Esto es intencional, no un error pendiente de arreglar.

### AVISO 3 — Tu clic real del 19 de agosto (K3): qué se pudo confirmar y qué no

Ese día confirmaste dos cosas en el chat: que recibiste la clave nueva
(`X-Identity-Key`) y que el clic en Mission Control funcionó sin error
401, viendo el flujo de remediación de principio a fin. Eso quedó
registrado en `docs_plan/CIERRE_FORMAL_E2E.md` y es válido — tu palabra
como Capa 9 es la autoridad aquí.

Lo que la auditoría **no pudo encontrar** es un archivo en el servidor
que reconstruya exactamente esa corrida (qué documento, qué directiva,
qué paquete). Los paquetes de remediación que sí existen en disco son de
un mes antes (21 de julio), y algunos de los archivos que referencian ya
se borraron (eran de una carpeta temporal). No significa que tu clic no
haya funcionado — significa que si alguien pidiera "muéstrame el archivo
exacto que generó ese clic" dentro de un año, hoy no se podría producir.
Es una brecha de trazabilidad para el archivo regulatorio formal, no una
duda sobre si funcionó.

### AVISO 4 — "Modelo" significa dos cosas distintas según el panel

- Panel **Pipeline Capa 8**: el modelo ahí es `claude-haiku-4-5-20251001`
  — es el que **construye misiones nuevas** (el que arma código y
  proyectos cuando le pides una solución custom).
- El analizador de documentos GMP (el que lee tus PDFs y encuentra
  hallazgos) usa **Ollama con un modelo qwen**, corriendo local en el
  servidor — es el que **juzga documentos**.

Son dos sistemas separados. Si un panel dice "modelo X" y el otro dice
"modelo Y", no es una inconsistencia — son dos trabajos distintos.

──────────────────────────────────────────────────────────────────────────
## RECORRIDO DE PANTALLAS
──────────────────────────────────────────────────────────────────────────

Mission Control se sirve desde `factory/ui/mission_control.html`, servido
por `factory-api` en el puerto 9000. La navegación (`<nav id="nav">`) arma
las secciones dinámicamente desde JavaScript — no son páginas separadas,
son vistas dentro de una sola pantalla.

### 1. Panel general (`vtitle` = "Panel general")
- **Para qué sirve:** vista de resumen de todo el sistema.
- **Qué muestra:** estado de proyectos, recursos, riesgos —viene de
  `/api/v1/status/full`, `/api/v1/status/resources`,
  `/api/v1/status/risks`.
- **Qué debes revisar:** que no haya riesgos abiertos sin explicación.
- **Solo lectura.** Ningún botón de este panel cambia estado.

### 2. Misiones (Layer 8/9)
- **Para qué sirve:** ver las 6 misiones/proyectos de la fábrica
  (`gmpai_document_validation`, `oos_hplc_investigator`,
  `oos_hplc_api_test`, `c8_alcoa_validator`, `lab_qc_project`,
  `r6_change_control`).
- **Qué debes revisar:** estado real de cada una — desplegada vs. no,
  con pruebas vs. sin pruebas. Ver el mapa de artefactos para el detalle
  actual de cada una; a la fecha de esta auditoría solo
  `oos_hplc_investigator` y `lab_qc_project` tienen contenedor
  corriendo de verdad.
- **Botones típicos:** `build`, `run`, `deploy-if-authorized`,
  `release-candidate` — cada uno cambia estado del proyecto. No pulses
  `deploy-if-authorized` sin haber revisado los quality gates primero.
- **X-Identity-Key interviene:** en las acciones de aprobación/decisión,
  no en la sola visualización.

### 3. Pipeline Capa 8 (`claude-model-panel`)
- **Para qué sirve:** monitorear el modelo que construye misiones nuevas
  (`claude-haiku-4-5-20251001`, ver Aviso 4).
- **Solo lectura** en su mayor parte (`/api/v1/layer8/claude/status`);
  las acciones de construcción viven en el panel de Misiones.

### 4. Findings / Cola de revisión (`review-queue`)
- **Para qué sirve:** esta es la pantalla más importante del sistema —
  aquí aparece cada hallazgo que el motor actual generó sobre un
  documento real, con página y cita ancladas.
- **Qué debes revisar:** cada entrada `pending` — el sistema **nunca**
  la aprueba solo. Verificado en código: cada ruta de decisión
  (`/review/findings/{rc_id}/decide`, `/review/candidates/{rc_id}/decide`)
  exige tu identidad.
- **Qué significa "candidatos" en cada finding:** son fragmentos que el
  buscador recuperó como posiblemente relevantes — NO son evidencia
  confirmada. El propio sistema lo marca así en cada entrada
  ("candidates_honesty_note"): tienes que leer el pasaje, no asumir que
  el candidato con mejor ranking es la respuesta correcta.
- **Botones:** decidir (confirmar hallazgo / descartar). Cambia estado
  de `pending` a una decisión tuya, queda en el audit trail.

### 5. NCR/CAPA candidatos
- **Para qué sirve:** cuando un hallazgo confirmado se repite (misma
  causa raíz vista más de una vez en la cola de revisión), el sistema
  sugiere que podría ameritar un NCR o CAPA formal.
- **Qué debes revisar:** la sugerencia es solo eso — una sugerencia. Tú
  decides si abrir el NCR/CAPA real en tu sistema de calidad.
- **Nunca se cierra un CAPA automáticamente** — regla dura del proyecto,
  no negociable.

### 6. Remediation Directives y Remediation Packages
- **Para qué sirve:** aquí es donde tú (o alguien con tu identidad)
  escribe el texto de corrección propuesto para un hallazgo confirmado
  (`RemediationDirective`), y el sistema arma un paquete controlado
  (documento borrador + redline + manifest).
- **Qué debes revisar:** que el borrador diga claramente "NO APROBADO"
  — así debe aparecer siempre, porque no existe forma de marcarlo como
  liberado (Aviso 2).
- **Botones:** `decision` (aprobar/rechazar el paquete a nivel interno de
  workflow — esto NO es lo mismo que "liberar el documento"),
  `medium-risk-batch`, `exceptions`.
- **X-Identity-Key interviene aquí directamente** — sin ella, 401.

### 7. Validación / Revisión de documentos (validation-package)
- **Para qué sirve:** ver el paquete completo de validación de un
  documento — propuestas de agentes, decisiones, referencias de casos.
- **Qué debes introducir:** tu decisión sobre cada `agent-proposal`
  (`/validation-package/documents/{doc_id}/agent-proposal/decision`).

### 8. Audit Trail
- **Para qué sirve:** consulta de todo lo que pasó — entradas de
  auditoría, resumen, verificación de integridad
  (`/api/v1/audit/entries`, `/audit/summary`, `/audit/verify`).
- **Solo lectura.** Es tu forma de confirmar que nada se movió sin
  quedar registrado — con la salvedad del Aviso 3 (K3 no dejó archivo
  propio, solo tu palabra en chat).

### 9. Agentes
- **Para qué sirve:** ver qué agentes especializados existen
  (`alcoa_plus_agent`, `fda_cgmp_211_agent`, `fda_part11_agent`, etc.) y
  sus perfiles (`/api/v1/agents`, `/api/v1/agents/profiles`).
- **Solo lectura.**

──────────────────────────────────────────────────────────────────────────
## QUÉ NO DEBE APROBARSE AUTOMÁTICAMENTE (verificado, no supuesto)
──────────────────────────────────────────────────────────────────────────

- Ningún hallazgo pasa de `pending` a confirmado sin tu decisión —
  confirmado por código real (`require_identity` en cada ruta de
  decisión).
- Ningún documento se marca `DOCUMENT_RELEASED = true` — no existe ruta
  de API para hacerlo (Aviso 2).
- Ningún NCR/CAPA se cierra automáticamente.
- Ningún lote se libera — el sistema no tiene ninguna noción de "lote"
  en su modelo de datos actual.
- La IA no redacta la decisión regulatoria final — solo propone
  (`agent-proposal`), tú decides.

──────────────────────────────────────────────────────────────────────────
Ver también:
`docs_plan/AUDITORIA_FUNCIONAL_E2E_POST_CIERRE.md` — el detalle técnico
completo detrás de estos cuatro avisos.
`docs_plan/MAPA_ARTEFACTOS_Y_RUTAS_GENERADAS.md` — dónde buscar cada
archivo que el sistema genera.
