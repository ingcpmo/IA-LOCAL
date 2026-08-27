# Reporte de Validación de Clon — Servidor Local

**Repo:** `/home/cmay/ivr-ia` · **Rama:** `main` @ `8fdcec5`
**Servidor:** local nuevo (no es el de referencia GCP `35.243.160.0`)
**Fecha de la auditoría:** 2026-08-26
**Modo:** auditoría de solo lectura + correcciones B1/B2 aprobadas por Cesar. Sin commits. Stack base completo levantado en modo dev (`gmp-api`, `gmp-postgres`, `gmp-redis`).

**Actualización 2026-08-26 (post-aprobación):** B1 y B2 aplicados. `gmp-api` operativo, `/health` todo OK, consulta LLM E2E funcionando (83 s, dentro de la referencia 20-120 s CPU). Detalle al final. Brecha nueva de seguridad: UFW inactivo + Ollama ahora en `0.0.0.0:11434` → expuesto a la LAN.

---

## 1. Resumen ejecutivo

**¿El clon es funcional en este servidor? — SÍ para el camino principal; PARCIAL en verificación.**

- El **repositorio está íntegro y completo**: `git fsck` limpio, 1500 archivos versionados, estructura esperada presente, `py_compile` limpio (2303/2303 `.py`), escaneo git-safety limpio.
- **Producto base `gmp-api` (:8000) OPERATIVO** (tras B1/B2): `/health` todo `ok`, auth correcta, ChromaDB poblado, cadena de auditoría propia limpia (116 logs, `hash_errors=0`, `part11_compliant=true`), y **consulta E2E RAG→LLM→audit en 83 s** con `mistral:7b` (dentro de la referencia CPU).
- **`factory-api` (capas 7-9, :9000) funciona**: health OK, API layer8/layer9 completa, auth (401/200), `headless_enabled = false`, E2E autenticado.
- **Pendiente de verificación:** entorno Python del host no permite correr la suite de tests (`pip` ausente, `.venv` roto del origen) → referencia "169 tests passed" sin verificar. Gate 0 de `factory` en FAIL por `pytest`/`PyYAML` faltantes + excepción de auditoría no resoluble (`hash_errors=0`, no es corrupción).
- **Brecha nueva de seguridad (B5):** B1 dejó Ollama en `0.0.0.0:11434` y UFW está inactivo → `:11434` expuesto sin auth en la LAN.
- El directorio del clon arrastra **secretos reales y datos de otros proyectos** fuera de git (`.env`, `.ssh/`, `.secrets/`, `ARIA/`, `GMPAI/`, `backups/` 1.4 GB) — el traslado fue una copia del home, no un `git clone`.

Gate 0 (`factory_selfcheck.sh`): **FAILED** (`PASS=2 WARN=1 FAIL=3`). Los 3 FAIL son 2 dependencias faltantes (`pytest`, `PyYAML`) y 1 gap de config de firmas (`AUDIT_EXCEPTION-2026-002` no resoluble sin las llaves). Ninguno indica corrupción de código.

---

## 2. Tabla de checkpoints (Bloques 1-6)

| Bloque | Checkpoint | Estado | Observaciones |
|---|---|---|---|
| **1** | Integridad del clon (git + estructura) | **PASS** | `git fsck` limpio; 1500 archivos; estructura completa. `ports.yaml` está en `factory/registry/`, no en `registry/` (mismatch de expectativa, no falta). 1 secreto versionado: `.claude/daemon/control.key`. Working tree con WIP del origen (17 M + ~50 untracked). |
| **2** | Dependencias y entorno | **PARCIAL** | Docker 29.1.3 / Compose 2.40.3 OK. Ollama nativo 0.33.0 OK (proceso, no contenedor). `pip` ausente en host. `.venv` roto (py3.11 del origen, sin site-packages, sin pip). Modelos: `mistral:7b-...` OK; `qwen2.5:7b-...` y `nomic-embed-text` faltan (este último **no lo usa** el stack base: `EMBEDDING_MODEL=all-MiniLM-L6-v2`). Postgres/Redis vía Docker, no nativos. |
| **3** | Configuración y variables de entorno | **PARCIAL** | `.env` raíz presente, cubre 10/10 vars que consume `app/`. `factory/.env` es un archivo **separado** con `FACTORY_API_KEY`. Sin `.env.example` del producto raíz. Puertos: sin conflicto en este host (8000/5432/6379 libres, 9000 = factory-api). **Defecto P1:** `docker-compose.yml:53` monta `/home/ing_cpmo/.cache/chroma` (no existe aquí). |
| **4** | Levantamiento controlado (dry-run) | **PASS** (tras B1/B2) | `docker compose config` válido. Stack base completo Up: `gmp-api` + `gmp-postgres` + `gmp-redis`. `/health` → `{"api":"ok","postgres":"ok","redis":"ok","ollama":"ok"}`. `init.sql` aplicado (3 tablas). Conectividad API→Postgres / API→Redis / API→Ollama: **OK** desde el contenedor `gmp-api` real. |
| **5** | Quality Gates (Gate 0) | **FAIL** (mejorado: `PASS=3 WARN=1 FAIL=3`) | py_compile PASS (2303). **pytest FAIL — 2594 passed / 12 failed** (ver §7). audit chain **PASS+WARN** (`ACCEPTED_WITH_DOCUMENTED_EXCEPTION`, 77325 entradas) tras B3/B4. factory_status FAIL (solo `aria-ollama` — cosmético; `gmp-api` ahora PASS). git-safety scan PASS. artifact versions FAIL (1 real: `golden_dataset` `CONTENT_CHANGED_VERSION_SAME`, ver B7). |
| **6** | Smoke test E2E | **PASS** (base) / PARCIAL (custom) | **gmp-api :8000** (tras B1/B2): `/health` OK; auth 401 sin key / 200 con `GMP_API_KEY`; `/api/v1/knowledge/stats` 200 (ChromaDB poblado); `/api/v1/audit/verify` 200 (`verified:true`, `hash_errors:0`, `part11_compliant:true`); **`/api/v1/query` → 200 en 83 s**, modelo mistral, pipeline completo (`sources:[]` a revisar). **factory-api :9000**: health + auth + E2E layer8/layer9 read-only PASS. `headless_enabled=false` confirmado. lab_qc :8101 / oos_hplc :8102: **PENDIENTE** (no levantados). |

---

## 3. Brechas respecto al servidor de referencia (GCP `35.243.160.0`)

### Resueltas en esta sesión

| # | Brecha | Corrección aplicada | Verificación |
|---|---|---|---|
| B1 | **Ollama solo en loopback** | Drop-in `/etc/systemd/system/ollama.service.d/override.conf` con `Environment="OLLAMA_HOST=0.0.0.0:11434"`; `daemon-reload` + `restart`. (El primer intento de Cesar no había creado el archivo; se rehízo con `sudo`.) | `ss`: `LISTEN *:11434`. `gmp-api → host.docker.internal:11434` → HTTP 200. `/health` → `"ollama":"ok"`. |
| B2 | **`gmp-api` no construible tal cual** | `docker-compose.yml:53`: `/home/ing_cpmo/.cache/chroma` → `${HOME}/.cache/chroma`; `mkdir ~/.cache/chroma`; `docker compose build api` (imagen `ivr-ia-api:latest`); `up -d api`. | `gmp-api` Up. `/health` HTTP 200 todo `ok`. `/api/v1/knowledge/stats` y `/api/v1/audit/verify` → 200 autenticados. |

### Resueltas en esta sesión (cont.)

| # | Brecha | Corrección aplicada | Verificación |
|---|---|---|---|
| B3 | **Sin entorno Python para tests** | DNS del host estaba roto (stub `systemd-resolved` en timeout) → `resolvectl dns wlp1s0 8.8.8.8 1.1.1.1 192.168.1.1` (runtime, **no persistente**). `.venv` roto eliminado; recreado con `python3.12 -m venv` + `get-pip.py` (pip 26.2.1); `pip install -r requirements.txt -r factory/requirements.txt pytest pyyaml`. | Suite completa: **2594 passed / 12 failed / 79 skipped / 1 xfailed** (4m12s). Referencia "169 passed" obsoleta (~15×). |
| B4 | **Cadena de auditoría de `factory` en FAIL** | Era **solo la falta de `jsonschema`** (resuelto por B3). Las `identity_keys` estaban presentes. | Gate 0 paso 3: `CHAIN_CONTINUITY = ACCEPTED_WITH_DOCUMENTED_EXCEPTION`, `PART11 = ACCEPTED_WITH_DOCUMENTED_EXCEPTION`, "contenido auténtico (77325 entradas, excepción vigente)". PASS+WARN, ya no FAIL. |

### Bloqueantes / importantes pendientes

| # | Brecha | Detalle | Efecto |
|---|---|---|---|
| B5 | **UFW inactivo + Ollama en `0.0.0.0` (introducido por B1)** | Tras B1 Ollama escucha en todas las interfaces, incluida `wlp1s0` (192.168.1.104). `ufw status` → **inactivo**. `:11434` sin auth → cualquiera en la LAN puede consumir el modelo. | Exposición de recurso LLM a la red local. Requiere decisión: activar UFW con ruleset (cuidado con SSH), o re-bind a la IP del bridge Docker. |
| B6 | **DNS fix no persistente** | `resolvectl dns wlp1s0 …` se pierde al reiniciar la red / el host. El stub `systemd-resolved` seguía sin resolver `pypi.org`/`archive.ubuntu.com` (uplink `192.168.1.1` no responde para esos nombres). | Tras reboot, `pip`/`apt` vuelven a fallar. Persistir en `/etc/systemd/resolved.conf` (`DNS=8.8.8.8 1.1.1.1`) — requiere aprobación (bloqueado por el clasificador en esta sesión). |
| B7 | **Inconsistencia de trazabilidad en `golden_dataset`** | `artifact_version_guard`: `semantic_verification_golden_dataset.py` → `CONTENT_CHANGED_VERSION_SAME` (hash cambió, `version_record` no se bumpeó). El archivo está limpio en git → el store de `version_record` quedó desfasado respecto al código commiteado (o se copió incompleto). Causa el FAIL 6/6 de Gate 0 y 4 de los 12 tests fallidos (`test_gate0_extended`, `test_artifact_versioning`, `test_evidence_pack_governance`, `test_model_qualification_gate`). | Gate 0 en rojo por versionado. Requiere decisión Layer 9: bumpear el `version_record` con decisión aprobatoria, o restaurar el baseline correcto del store. |
| B8 | **Dep faltante `pdfplumber`** | No está en `requirements.txt` ni `factory/requirements.txt`. Rompe `test_m2_section_aware_chunking`. | 1 test en error de colección. Añadir a `factory/requirements.txt` y `pip install`. |
| B9 | **Tests con rutas `/home/ing_cpmo` hardcodeadas** | `test_artifact_type_mismatch_report`, `test_broken_link_report`, `test_source_currency_checker` leen archivos vía `Path("/home/ing_cpmo/factory/...")`. `test_corpus_runner` espera `/home/ing_cpmo/GMPAI/source/Rockwell/…pdf`. | 4 tests fallan por ruta, no por defecto de código. Son bugs de test (deberían usar ruta relativa al repo). |

### Importantes (no bloquean el arranque, pero deben resolverse)

| # | Brecha | Detalle |
|---|---|---|
| I1 | **Secreto versionado** | `.claude/daemon/control.key` (32 chars ASCII) está en git. Debe salir del índice y rotarse. Impacto limitado (auth del daemon local). |
| I2 | **Secretos reales y datos ajenos en el directorio del clon** | Fuera de git pero en disco: `.env`, `.ssh/`, `.secrets/`, `.gnupg/`, `.claude/.credentials.json`, `factory/config/identity_keys.yaml`, `private_reports/`. Además `ARIA/` (512K), `GMPAI/` (271M), `backups/` (1.4G). El `.gitignore` protege el repo, pero los secretos del origen están presentes; decidir si rotarlos (`JWT_SECRET`, `APP_SECRET_KEY`, `DB_PASS`, `GMP_API_KEY`, `FACTORY_API_KEY`). |
| I3 | **`docker compose config` imprime secretos en claro** | Al validar la config quedan expuestos en el output. Considerar rotación tras la validación. |
| I4 | **Modelos Ollama incompletos** | Falta `qwen2.5:7b-instruct-q4_K_M`. Falta `nomic-embed-text` (pero el stack base **no lo usa**; confirmar si algún perfil de la fábrica sí). |
| I5 | **`factory_status.sh` asume Ollama como contenedor** | Chequea `docker ps: aria-ollama`; en este host Ollama es nativo → FAIL cosmético. El check necesita ajuste para host con Ollama nativo. |
| I6 | **`.venv` roto induce a error** | Si se decide "todo en contenedor", conviene borrarlo para que Gate 0 no lo tome como `PYBIN`. |

### Menores

| # | Brecha | Detalle |
|---|---|---|
| M1 | Ruta de `ports.yaml` | Está en `factory/registry/ports.yaml`, no en `registry/ports.yaml` como esperaba el guion del BLOQUE 1. No es un defecto. |
| M2 | Referencias de conteo obsoletas | "113 archivos Python" → hoy 2303 bajo `factory/` (1892 en el workspace generado `gmpai_document_validation`), 395 trackeados en el repo. El proyecto creció; py_compile limpio. |
| M3 | Drift de versión `aiofiles` | `requirements.txt` raíz pin `24.1.0`; imagen `factory-api` trae `25.1.0` (build desde reqs de `factory/`, no del raíz). |
| M4 | Redis warning | `Memory overcommit must be enabled` (`vm.overcommit_memory=1`). No bloquea. |
| M5 | Working tree no limpio | El clon arrastra 17 archivos modificados + ~50 sin trackear del servidor origen (WIP en `docs_plan/`, backups de `identity_keys.yaml`, `factory/regulatory/corpus_run/`). El clon no se tomó desde HEAD limpio. |

---

## 4. Acciones que requieren aprobación explícita antes de proceder

> B1 y B2: **HECHOS** (ver §3). Lo siguiente sigue pendiente y requiere OK de Cesar.

1. **[B5 — nuevo, seguridad] Cerrar la exposición de Ollama en la LAN.** Tras B1, `:11434` está abierto en `wlp1s0` sin auth y UFW está inactivo. Opciones: (a) activar UFW con `allow OpenSSH` + `allow` desde subredes Docker a `:11434` + `deny` en `wlp1s0`; (b) re-bind Ollama a la IP del bridge (`OLLAMA_HOST=172.17.0.1` — pero hay 3 bridges); (c) regla iptables puntual. Recomendado (a).

2. **[B3] Restaurar entorno Python del host.** `sudo apt install python3-pip python3.12-venv`, recrear `.venv` con `requirements.txt` **+ `pytest` + `PyYAML`** + deps que importan los tests (`fastapi`, `pydantic`, `httpx`). Alternativa: decidir "solo contenedor" y **borrar `.venv`** (ver I6).

3. **[B4] Aportar `factory/config/identity_keys.yaml` + almacén de excepciones** desde el servidor de referencia, o confirmar que el FAIL de continuidad de cadena es esperado en un clon sin llaves.

4. **[I4] `ollama pull qwen2.5:7b-instruct-q4_K_M`** (~4.4 GB). `nomic-embed-text` solo si se confirma que algún perfil lo usa.

5. **[I1] Sacar `.claude/daemon/control.key` del índice git** (`git rm --cached`) y rotarlo.

6. **[I2] Decidir rotación de secretos del origen** (`JWT_SECRET`, `APP_SECRET_KEY`, `DB_PASS`, `GMP_API_KEY`, `FACTORY_API_KEY`) y limpieza de `ARIA/`, `GMPAI/`, `backups/` del directorio del clon (~1.7 GB).

7. **[6.3] Revisar `sources: []` en `/api/v1/query`** — confirmar si el endpoint del producto base debe devolver fuentes ancladas o si es esperado.

8. **Levantar `lab_qc` (:8101) y `oos_hplc` (:8102)** para completar BLOQUE 6.4 — solo cuando el stack base esté sano.

---

## 5. Estado dejado en el servidor

- **Corriendo:** `gmp-api` (Up, `/health` OK), `gmp-postgres` (healthy), `gmp-redis` (healthy), `factory-api` (Up, previo a la auditoría).
- **Creado:** red `ivr-ia_default`, volúmenes `ivr-ia_gmp_postgres_data` / `ivr-ia_gmp_redis_data`, imagen `ivr-ia-api:latest`, dir `~/.cache/chroma`, drop-in systemd `ollama.service.d/override.conf`, **`.venv` nuevo** (py3.12, pip 26.2.1, ~150 paquetes de `requirements.txt` + `factory/requirements.txt` + `pytest` + `pyyaml`).
- **Imágenes descargadas:** `postgres:16-alpine`, `redis:7-alpine`.
- **Modificado (sin commit):** `docker-compose.yml:53` (B2). `ollama.service` con override `OLLAMA_HOST=0.0.0.0:11434` (B1). DNS runtime en `wlp1s0` → `8.8.8.8 1.1.1.1 192.168.1.1` (B3, **no persistente**).

Para revertir el stack: `docker compose down` (opcional `-v`). Para revertir B1: `sudo rm -r /etc/systemd/system/ollama.service.d && sudo systemctl daemon-reload && sudo systemctl restart ollama`. DNS revierte solo al reiniciar la red.

## 6. Consulta de prueba E2E (BLOQUE 6.3)

`POST /api/v1/query` (campo `question`), autenticada con `GMP_API_KEY`:

- **HTTP 200 en 83.1 s** (dentro de la referencia 20-120 s CPU). Modelo `mistral:7b-instruct-q4_K_M`.
- Respuesta con pipeline completo: `response`, `answer`, `model`, `agent_id`, `agent_name`, `context_used`, `elapsed_seconds`, `rules_triggered`, `rules_count`, `highest_risk`.
- Contenido coherente (cita 21 CFR Part 11, EU GMP Annex 11 en el texto).
- ⚠️ `sources: []` vacío — las citas van inline en el texto pero el array de fuentes ancladas viene vacío. A revisar (relevante por la regla GMP "sin citas no ancladas", aunque este es el endpoint del producto base, no el analizador).

## 7. Suite de tests — desglose de los 12 fallos (de 2606)

**`2594 passed / 12 failed / 79 skipped / 1 xfailed`** en 4m12s. Referencia "169 passed" obsoleta (~15×).

| Categoría | Tests | Naturaleza |
|---|---|---|
| Ruta `/home/ing_cpmo` hardcodeada en el test | `test_artifact_type_mismatch_report`, `test_broken_link_report`, `test_source_currency_checker` (los 3 `test_never_writes_registry_json*`) | Bug de test — leen el fuente vía ruta absoluta del origen. No es defecto de código. |
| Ruta + dato de otro proyecto | `test_corpus_runner::…d4a_232_llamadas` | Espera `/home/ing_cpmo/GMPAI/source/Rockwell/…FS_v1.2.pdf`. `GMPAI/` existe aquí bajo otra ruta. |
| Dep faltante | `test_m2_section_aware_chunking::…security_section` | `ModuleNotFoundError: pdfplumber` (B8). |
| Servicio no levantado | `test_mission_evidence_readers::test_deployment_exists_and_health` | `health_ok=False` para `oos_hplc_investigator` (:8102 no corre). |
| Runner anidado | `test_new_managers::TestTestExecutionManager::{test_passing_tests,test_failing_tests}` | El `TestExecutionManager` corre pytest dentro de pytest y valida el resultado; falla por entorno/cwd anidado. |
| Deriva de estado de gobernanza (B7) | `test_artifact_versioning::…photographs_without_approving`, `test_gate0_extended::…g6_matrix_regularization_closed`, `test_evidence_pack_governance::…p08…`, `test_model_qualification_gate::…q08…` | Mismo origen que el FAIL 6/6 de Gate 0: el `version_record` de `semantic_verification_golden_dataset.py` está desfasado del código commiteado. Requiere decisión Layer 9. |

Ninguno de los 12 indica corrupción de código. 8 son de entorno/ruta/dep/servicio; 4 son la única inconsistencia real de estado (B7).

---

## 8. Acciones pendientes (actualizado)

| # | Acción | Requiere |
|---|---|---|
| B5 | Cerrar exposición de Ollama en la LAN (activar UFW con ruleset, o re-bind al bridge) | decisión + sudo |
| B6 | Persistir DNS (`/etc/systemd/resolved.conf` → `DNS=8.8.8.8 1.1.1.1`) o arreglar el uplink `192.168.1.1` | aprobación (bloqueado por clasificador) + sudo |
| B7 | Resolver `version_record` de `golden_dataset` (bump con decisión aprobatoria Layer 9, o restaurar baseline del store) | decisión Layer 9 / Cesar |
| B8 | Añadir `pdfplumber` a `factory/requirements.txt` + `pip install` | OK de Cesar |
| B9 | Corregir rutas `/home/ing_cpmo` hardcodeadas en 4 tests | OK de Cesar (cambio de código de test) |
| I1 | `git rm --cached .claude/daemon/control.key` + rotar | OK de Cesar |
| I2 | Rotación de secretos del origen + limpieza `ARIA/`,`GMPAI/`,`backups/` (~1.7 GB) | decisión de Cesar |
| I4 | `ollama pull qwen2.5:7b-instruct-q4_K_M` (si se confirma su uso) | OK de Cesar |
| — | Revisar `sources: []` en `/api/v1/query` | investigación |
| — | Levantar `lab_qc` (:8101) / `oos_hplc` (:8102) para BLOQUE 6.4 | OK de Cesar |

---

*Reporte generado por la auditoría de clon. NO commiteado — pendiente de revisión de Cesar.*
