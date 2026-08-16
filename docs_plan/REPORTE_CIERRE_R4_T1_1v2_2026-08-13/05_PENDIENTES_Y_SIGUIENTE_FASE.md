# 05 — Pendientes y Siguiente Fase

## A. Bloqueantes para cerrar R4-T1.1v2

1. **`git` ausente dentro del contenedor `factory-api`.** Detectado durante
   esta auditoría, no durante el desarrollo original.
   `test_full_cold_chain_rw0005_directive_to_traceable_candidate`
   (`factory/tests/test_r4_t1_1v2_cold_chain_validation.py`) falla con
   `FileNotFoundError: git` porque el propio código del test invoca
   `subprocess.run(["git", "rev-parse", "HEAD"], ...)` como parte de su
   fixture de datos, y el binario no existe en la imagen. No es un defecto
   de lógica de negocio — es una brecha de tooling del contenedor. Cierre
   trivial: agregar `git` al Dockerfile de `factory-api`, o sustituir la
   llamada a `subprocess` por un valor mockeado dentro del test.
2. **Clic real de Cesar en el panel de adjudicación nuevo.** El panel está
   construido y verificado por código y por los endpoints que consume
   (`03_VALIDACION_EN_VIVO.md`), pero no se ha ejercitado visualmente en
   navegador — esta corrida fue documentación, no ejecución de UI.

## B. Bloqueantes para `R4_GENERATION_GATE`

1. **Adjudicación humana pendiente en `review_queue.jsonl` para RW-0005.**
   12 entradas en `pending`, de las cuales 5 corresponden a los runs nuevos
   persistidos en el commit `99f36c3` (todas `21_CFR_11.10(e)`). Ninguna fue
   promovida a decisión de remediación real todavía.
2. **`R4_GENERATION_GATE` no evaluado en esta corrida** — fuera del alcance
   explícito de esta auditoría (instrucción: no ejecutar LLM, no correr
   Tier-1, no generar documentos reales).
3. La única entrada `confirmed` de esta tanda
   (`finding-chunked-50534e75927c-21_CFR_11.10(e)`) tiene una limitación
   documentada por escrito (`RECORD_ANNOTATION-2026-007`): su
   `human_confirmed_evidence.quote="mejora"` no es una cita real y la
   entrada está explícitamente excluida del Golden Dataset. Cualquier
   avance hacia `R4_GENERATION_GATE` que dependa de esta entrada debe
   respetar esa exclusión.

## C. Limpieza / repositorio

1. **286 archivos untracked en el working tree**, ninguno modificado ni
   staged (ver `06_GIT_STATUS_FINAL.md`). Concentrados en `factory/`
   (210 — en su mayoría checkpoints de `pilot_run/`), `docs_plan/` (59),
   `docs_factory/` (10), `.claude/` (5) y `scripts/` (2). Ninguno de estos
   se tocó ni se commiteó durante esta auditoría.
2. Los checkpoints de `factory/regulatory/pilot_run/checkpoints/` (29
   archivos) y los manifests/status asociados no tienen regla de
   `.gitignore` explícita — evaluar si deben ignorarse (son artefactos de
   ejecución regenerables) o versionarse deliberadamente.

## D. Deuda de diseño

1. **`review_queue.jsonl` no es estrictamente append-only a nivel de
   línea** — una transición de estado reescribe la línea completa del
   `rc_id` (ver `04_GOBERNANZA_DATOS.md`). El sistema compensa esto con
   anotaciones `RECORD_ANNOTATION` separadas y append-only, pero el patrón
   en sí (mutación + anotación correctiva paralela) es más frágil que un
   log append-only puro y depende de que cada mutación recuerde escribir su
   anotación.
2. La familia `PILOT_EXECUTION-2026-017`/`-018` documenta explícitamente que
   no autoriza corpus ni baseline — el patrón de "autorización ligera
   separada de la autorización formal" (repetido también en
   `EMBED_EXECUTION` vs. `PILOT_EXECUTION`) funciona, pero no hay todavía un
   mecanismo automático que impida usar una decisión ligera para justificar
   una acción que requeriría la autorización formal — depende de disciplina
   de quien lee el registro.

## Propuesta de siguiente plan mínimo

1. Cerrar el Bloqueante A (agregar `git` al Dockerfile de `factory-api` o
   mockear el `subprocess` del test) y re-ejecutar
   `test_r4_t1_1v2_cold_chain_validation.py` completo dentro del contenedor
   para confirmar 7/7.
2. Presentar a Cesar el panel de adjudicación en navegador para el clic real
   (Bloqueante A.2) — sesión corta, sin cambios de código si el panel
   funciona como está.
3. Antes de tocar `R4_GENERATION_GATE`: sesión de adjudicación humana
   dedicada sobre las 12 entradas `pending` de `review_queue.jsonl`
   (5 nuevas de RW-0005 más 7 previas), con la exclusión de Golden Dataset
   de `RECORD_ANNOTATION-2026-007` respetada explícitamente.
4. Solo después de 1–3: evaluar si `R4_GENERATION_GATE` puede abrirse, y
   bajo qué alcance mínimo (no implícito en esta auditoría).
