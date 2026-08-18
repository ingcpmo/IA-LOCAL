# CIERRE P0 — Opción 1: exigir directive_id real en el endpoint

Fecha: 2026-08-18
Rol: Arquitecto Principal (Capa 8)
Autoridad: Cesar (Capa 9) aprobó explícitamente "Opción 1: exigir
directive_id real en el endpoint" — una de las 3 opciones enumeradas en
`docs_plan/VERIFICACION_ACOTADA_20260818/REPORTE.md` para cerrar el
hallazgo P0 (I_BYPASS_FOUND).

## Qué se implementó

`POST /api/v1/remediation-packages/{project_id}/{package_id}/{version}`
ya no acepta `changes` sin respaldo. Cada `RemediationChange` debe traer
un `directive_id` que resuelva a una `RemediationDirective` real con
`status="SUBMITTED"` (autoría humana ya confirmada, Acto 2).

1. **`factory/services/remediation_directive.py`** — nueva función
   `get_directive(directive_id)`: única resolución real por id.

2. **`factory/services/remediation_package_schemas.py`** — `directive_id`
   agregado como campo OPCIONAL a nivel de forma (`_CHANGE_OPTIONAL_FIELDS`).
   Deliberadamente opcional aquí: `validate_remediation_change()` la usan
   también `document_quality_gates.py`/`golden_dataset_criteria.py` para
   validar forma sin estar atados al flujo de paquetes — forzarlo como
   requerido ahí habría sido alcance no pedido.

3. **`factory/services/remediation_package_service.py`** — `create_package()`
   ahora exige, para cada `change`: (a) `directive_id` presente; (b) que
   resuelva a una directiva real (`DirectiveNotFoundError` si no); (c) que
   `status == "SUBMITTED"` (`DirectiveNotSubmittedError` si no).
   Nuevo símbolo rebindable a nivel de módulo, `svc._resolve_directive`
   (default `remediation_directive.get_directive`), para que los tests de
   invariantes no relacionadas puedan inyectar un resolutor sintético sin
   depender de un PDF real + `human_review_queue` — mismo patrón que el
   resto del archivo ya usa para `paths.REMEDIATION_PACKAGES_BASE`.

4. **`factory/api/routes/remediation_packages.py`** — las 3 excepciones
   nuevas se mapean a HTTP 400 (error de cliente), igual que el resto de
   invariantes de forma.

5. **`factory/services/remediation_directive_dispatch.py`** — hallazgo
   colateral real (ver "Efecto de segundo orden" abajo): el único
   adaptador de producción que traduce una `RemediationDirective` a un
   `RemediationChange` no llevaba el campo `directive_id` consigo (aunque
   `change_id` ya coincidía con él por construcción). Se agregó
   explícitamente `mapped.change["directive_id"] = directive["directive_id"]`
   antes de devolver el `MappedChange`.

## Efecto de segundo orden descubierto al validar (no solo el bypass)

Al correr la suite completa tras el cambio, dos tests fallaron por una
razón real y relevante, no un artefacto de test:
`test_r4_t1_1v2_cold_chain_validation.py` (el flujo E2E real
directiva→candidato) y una prueba de integración de
`test_remediation_change_application_resolver.py`. El primero probó que
**incluso el camino "correcto" y ya gobernado** (`remediation_directive.py`
→ `remediation_directive_dispatch.py` → Ruta D) no adjuntaba
`directive_id` al `RemediationChange` resultante — exactamente el
hallazgo J (trazabilidad) ya reportado en
`VERIFICACION_ACOTADA_20260818/REPORTE.md`. Cerrar I sin tocar
`remediation_directive_dispatch.py` habría dejado el propio camino
gobernado incapaz de crear paquetes. Se corrigió ahí mismo (punto 5
arriba) — mismo alcance que "exigir directive_id en el endpoint": sin
esto, el endpoint no podría aceptar NINGÚN change, ni siquiera los
legítimos.

## Validación

- Tests nuevos: 2 en `test_remediation_directive.py` (`get_directive`),
  4 end-to-end en `test_remediation_packages_router.py` (sin el resolutor
  sintético del fixture — ejercitan la ruta HTTP real completa: falta
  `directive_id` → 400; `directive_id` desconocido → 400; directiva no
  `SUBMITTED` → 400; directiva real `SUBMITTED` → 201).
- Tests existentes ajustados (campo `directive_id` agregado a fixtures +
  `svc._resolve_directive` sintético inyectado vía monkeypatch en cada
  autouse fixture, para pruebas de invariantes no relacionadas a
  directivas): `test_remediation_package_service.py`,
  `test_remediation_package_concurrency.py`,
  `test_remediation_package_audit_isolation.py`,
  `test_remediation_packages_router.py`,
  `test_remediation_change_application_resolver.py`.
- Suite completa (`factory/tests/`, 2611 tests): **153/153 tests
  relacionados pasan**; de los 2529 pasan / 14 fallan / 5 skip / 1 xfail
  reportados por la corrida completa, los 14 fallos se verificaron
  preexistentes en el baseline (antes de este cambio, vía `git stash`) —
  dependen de estado en vivo del servidor (uso de disco, endpoints reales
  de gobernanza) o de otros hallazgos ya conocidos, ninguno relacionado
  con `remediation_package`/`remediation_directive`.

## Estado

```
CODE_CHANGED =            SI (5 archivos de servicio/API, 6 archivos de test)
COMMIT =                  NO (pendiente de tu revisión del diff)
PRODUCTION_ENABLEMENT =   BLOCKED (sin cambios -- sigue sin endpoint de
                           ReleaseRecord conectado, ver
                           remediation_packages.py:4-8)
```

Pendiente: tu aprobación explícita para hacer commit. `git status
--short` y `git diff --stat` se muestran en el mensaje de cierre de esta
tarea.
