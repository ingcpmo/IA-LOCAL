# GMP AI Factory — Cierre Operativo Serie U

**Fecha de cierre:** 2026-06-25  
**Commit HEAD:** `994a708`  
**Autor:** Cesar / Capa 8 (Claude Sonnet 4.6)  
**Ciclo:** U5 → U12 (7 commits serie U + cierre operativo U12)

---

## Resumen ejecutivo

La serie U resolvió la deuda técnica y los riesgos de observabilidad identificados
tras la entrega de las Capas 7-9. Siete commits consolidaron la seguridad de paths,
la semántica Part-11, el contrato de tests y la interfaz Mission Control. U12 cerró
los 2 ciclos operativos que la serie habilitó pero no ejecutó (RC pending, zombie r6).

**Resultado:** 151 tests verdes, Gate 0 PASS, part11_compliant=true, 0 riesgos activos.

---

## Tabla de objetivos cumplidos

| ID | Objetivo | Estado |
|----|----------|--------|
| O1 | Invariante read-only: refresh no escribe en cadena Part-11 | CUMPLIDO — U5 |
| O2 | Semántica WARN vs FAIL en verify_chain (fork ≠ corrupción) | CUMPLIDO — U6 |
| O3 | Política de paths única; prevenir path traversal | CUMPLIDO — U7 |
| O4 | Observabilidad: exponer zombie r6+puerto en /status/risks | CUMPLIDO — U8 |
| O5 | UI Mission Control: visor read-only, headless/logs, rechazo de misión | CUMPLIDO — U9-U11 |
| O6 | Cierre operativo: RC c8_alcoa_validator, r6_change_control | CUMPLIDO — U12 |

---

## Commits de la serie

| Commit | Descripción |
|--------|-------------|
| `c213dc2` | U5 — confirma invariante read-only; guard regresión verde; remediación documentada |
| `f92d68d` | U6 — semántica Part-11 WARN(fork) vs FAIL(corrupción) en verify_chain y /audit/summary |
| `a7880be` | U7 — política de rutas compartida; resolve_workspace previene path traversal en diff/tree/file |
| `5b33ad0` | U8 — expone zombie 8102 y remediación r6 en /status/risks (R6+R7) |
| `8321d34` | U9 — visor read-only endurecido; headless/logs y artifacts usan _safe_workspace; jobs valida UUID |
| `a83274a` | U10 — afina form Crear misión: parseo legible de 422 y protección doble submit |
| `994a708` | U11 — cierre: rechazar misión (endpoint+UI), Ver log headless, limpia MOCKUP y tarjeta RC estática |

---

## Remediaciones aplicadas

| Documento | Riesgo remediado |
|-----------|-----------------|
| `factory/docs/REMEDIATION_U5.md` | Write-on-read: refresh no debe ejecutar quality gates |
| U6 — semántica WARN/FAIL | Fork concurrente en cadena ≠ error de hash: distinguir `is_fork` de `hash_errors` |
| U7 — `path_policy.py` | Path traversal via project_id con `../`, `\`, segmentos dobles |
| U8 — `/status/risks` | Misiones devueltas y puertos zombie sin deployment activo |
| U12 — cierre r6 | Cancelación formal, liberación de slot 8102, archivo de workspace |

---

## Archivos modificados (serie U)

| Archivo | Responsabilidad |
|---------|----------------|
| `factory/api/main.py` | Registro de routes; wire-up de middleware |
| `factory/api/routes/layer8.py` | Endpoints headless/logs, artifacts, jobs UUID; `_safe_workspace` |
| `factory/api/routes/layer9.py` | Endpoint rechazar misión; reject endpoint |
| `factory/api/routes/status.py` | `/status/risks` R6+R7; expose returned missions y zombies |
| `factory/core/audit_writer.py` | `verify_chain`: semántica is_fork, hash_errors, part11_compliant |
| `factory/core/path_policy.py` | `resolve_workspace()`: política única de validación de paths |
| `factory/docs/REMEDIATION_U5.md` | Documentación del riesgo write-on-read |
| `factory/tests/test_audit_chain.py` | Guards semántica WARN/FAIL cadena Part-11 |
| `factory/tests/test_layer9_mission_control.py` | Guards endpoints Capa 9 (reject, logs, RC) |
| `factory/tests/test_path_policy.py` | Guards path traversal (31 casos paramétricos) |
| `factory/tests/test_status_risks.py` | Guards R6/R7 presencia y estado post-U12 |
| `factory/ui/mission_control.html` | UI Mission Control: visor, headless, rechazo, tarjeta RC |
| `factory/registry/ports.yaml` | Liberación slot 8102 (r6_change_control) |
| `factory/workspaces_archive/` | Archivo de r6_change_control (Part-11: no borrar) |

---

## Métricas finales

| Métrica | Valor |
|---------|-------|
| Tests totales | 151 passed |
| Tests añadidos (serie U) | ~51 (100 → 151) |
| Endpoints en OpenAPI | 58 paths |
| Gate 0 (factory_selfcheck) | PASS — FAIL=0 |
| part11_compliant | true |
| hash_errors cadena | 0 |
| chain_errors (forks) | 1 (aceptable, contenido auténtico) |
| headless_enabled | false |
| Riesgos activos post-U12 | 0 |
| RC pending post-U12 | 0 |
| fakeSubmit en UI | 0 (eliminados en U10) |

---

## Lecciones aprendidas

### 1. Patrón Ejecutor / Lectura
El endpoint `refresh()` del frontend debe ser estrictamente de lectura. Cualquier
acción que escriba en la cadena Part-11 debe ser disparada por el operador de forma
deliberada. Separar "observar estado" de "ejecutar acción" previene escrituras
accidentales que contaminan la evidencia.

### 2. Política de rutas única vs filtrado disperso
Antes de U7, cada endpoint filtraba `project_id` con su propia lógica. Un solo
módulo `path_policy.py` con `resolve_workspace()` elimina el riesgo de que un
endpoint nuevo olvide el filtro. El test paramétrico con 4+ vectores de traversal
actúa como contrato: cualquier endpoint futuro debe pasar por la política o el
test lo detecta.

### 3. Tests como contrato arquitectónico
`test_refresh_readonly` no testa un endpoint: testa una propiedad del sistema.
Si alguien añade una llamada a `run_quality_gates()` dentro de `/status`, el test
falla antes de que llegue a producción. Este patrón — tests que verifican
invariantes arquitectónicas, no solo respuestas HTTP — es más duradero que una
revisión de código puntual.

### 4. Semántica de cadena Part-11: fork ≠ corrupción
Un restart del proceso escribe 2 entradas encadenadas desde el mismo punto, creando
un fork legítimo. Reportar esto como FAIL cuando los hashes son correctos oculta
errores reales y genera falsos positivos. La distinción `is_fork + assessment=WARN`
vs `hash_errors > 0 + assessment=FAIL` permite auditoría de la evidencia sin alarmas
innecesarias en entornos de desarrollo.

### 5. Atribución real vs actores genéricos
Los eventos en la cadena Part-11 requieren `approved_by` o `rejected_by` con nombre
real (Cesar). Actores genéricos como "system" o "auto" son aceptables para eventos
de plataforma, pero las decisiones humanas (aprobar/rechazar RC, cancelar misiones)
deben tener atribución nominal para cumplir Part 11.

---

*Generado en cierre U12 — commit `994a708` — 2026-06-25*
