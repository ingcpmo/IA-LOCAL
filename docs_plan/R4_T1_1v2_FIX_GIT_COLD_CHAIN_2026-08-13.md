# R4-T1.1v2 — Fix mínimo: dependencia de `git` en test de cadena en frío

**Fecha:** 2026-08-13
**Autoridad de la corrida:** ARQ (Capa 8 / Claude Code) — instrucción explícita: fix mínimo, sin rediseño, sin LLM, sin Tier-1, sin generación documental real.
**Commit:** `6b2d69e`

## Alcance de la corrida

Prohibido explícitamente y respetado:
- No se rediseñó R4-T1.1v2.
- No se abrió R4_GENERATION_GATE.
- 0 llamadas LLM.
- 0 ejecuciones Tier-1.
- 0 generación documental real (los artefactos DRY_RUN los genera el propio test, en `tmp_path`/`dry_run_validation_r4_t1_1v2/`, ya contemplado en su diseño original).
- No se tocó `factory/layer9/review_queue.jsonl`.
- No se tocó `factory/layer9/decisions_v2.jsonl`.
- No se tocaron archivos untracked preexistentes.
- Commit realizado solo tras mostrar diff y resultado de tests, con aprobación explícita.

## ROOT_CAUSE

`test_full_cold_chain_rw0005_directive_to_traceable_candidate` ejecutaba:

```python
subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2], ...)
```

`cwd` resuelve a `/app` dentro del contenedor `factory-api`. Dos problemas, no uno:

1. El contenedor no tiene el binario `git` instalado (`python:3.11-slim`).
2. **Aunque se instalara `git`, el fix no funcionaría igual**: el `docker-compose` de `factory-api` solo monta `/home/ing_cpmo/factory` → `/app/factory` (y `backups_factory`, `GMPAI`). El directorio `.git` del repo **no está montado** en el contenedor, así que no hay repositorio que inspeccionar en `/app`.

## CHOSEN_FIX

Opción B: fallback en el propio test.

```python
try:
    commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
except (FileNotFoundError, subprocess.CalledProcessError):
    commit_sha = "UNKNOWN_NO_GIT_IN_CONTAINER"
```

`generation_commit_sha` es metadata de trazabilidad que el test pasa a `create_package()`; ningún criterio de aceptación (a-h) valida su contenido.

## WHY_MINIMAL

Opción A (agregar `git` al Dockerfile de `factory-api`) fue descartada porque:
- Exige rebuild de la imagen productiva por una dependencia que solo usa un test.
- **No resolvería el problema real**: sin `.git` montado, `git rev-parse HEAD` seguiría fallando (esta vez con "not a git repository" en vez de "binario no encontrado").
- Iría contra la restricción dura del proyecto de no ampliar infraestructura sin necesidad.

La opción B es un cambio de 7 líneas en un solo archivo de test, sin tocar Docker, endpoints, ni infraestructura.

## FILES_CHANGED

- `factory/tests/test_r4_t1_1v2_cold_chain_validation.py` (único archivo)

## TEST_RESULT_BEFORE

6/7 passing. Fallo:
```
FileNotFoundError: [Errno 2] No such file or directory: 'git'
```
en `test_full_cold_chain_rw0005_directive_to_traceable_candidate`.

## TEST_RESULT_AFTER

7/7 passing (23-26s, 0 errores), confirmado dos veces (antes y después del commit):

```
factory/tests/test_r4_t1_1v2_cold_chain_validation.py::test_synthetic_finding_isolated_never_touches_real_queue PASSED
factory/tests/test_r4_t1_1v2_cold_chain_validation.py::test_directive_authored_by_cesar_is_accepted_and_dispatches_to_high_risk_change PASSED
factory/tests/test_r4_t1_1v2_cold_chain_validation.py::test_full_cold_chain_rw0005_directive_to_traceable_candidate PASSED
factory/tests/test_r4_t1_1v2_cold_chain_validation.py::test_delete_change_type_still_rejected PASSED
factory/tests/test_r4_t1_1v2_cold_chain_validation.py::test_directive_without_citation_still_rejected PASSED
factory/tests/test_r4_t1_1v2_cold_chain_validation.py::test_directive_with_non_anchoring_original_text_still_rejected PASSED
factory/tests/test_r4_t1_1v2_cold_chain_validation.py::test_directive_with_stale_document_sha_still_rejected PASSED
======================= 7 passed, 24 warnings in 23-26s ========================
```

Comando: `docker exec factory-api python -m pytest factory/tests/test_r4_t1_1v2_cold_chain_validation.py -v`

## LLM_CALLS_EXECUTED
0

## TIER1_STATUS
NOT_EXECUTED

## DOCUMENT_GENERATION_STATUS
NOT_EXECUTED (fuera del comportamiento propio del test DRY_RUN, ya existente antes de este fix)

## UI_PANEL_CHECK

Verificado por inspección de rutas (sin clic real, sin invocar endpoints):
- `factory-api` responde `200` en `/health`.
- Router `remediation-packages` (`prefix=/api/v1/remediation-packages`) registrado en `factory/api/main.py`, con `dependencies=[Depends(verify_api_key)]`.
- Endpoints presentes: crear paquete, obtener paquete, `POST .../exceptions/{change_id}`, `POST .../medium-risk-batch`, `POST .../decision`.
- No se creó ni mutó estado real; no hubo decisión humana ejecutada.

## GIT_STATUS

- Único archivo modificado y commiteado: `factory/tests/test_r4_t1_1v2_cold_chain_validation.py`.
- `review_queue.jsonl` y `decisions_v2.jsonl`: sin cambios (verificado, diff vacío antes y después).
- Untracked bajo `factory/regulatory/pilot_run/`: preexistentes al inicio de la sesión, no tocados por esta corrida (el test escribe en `tmp_path` de pytest).

## Commit

```
6b2d69e fix(r4-t1.1v2): test cold-chain no depende de binario git en factory-api
1 file changed, 11 insertions(+), 4 deletions(-)
```

Aprobado explícitamente por Cesar tras revisar diff y resultado de tests.
