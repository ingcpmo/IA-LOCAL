# CF-6 v2.0 · R3 — BLOQUEADO: canonical_store sin poblar en este entorno

**Fecha:** 2026-09-05 · Autorizado por Capa 9, verificado antes de ejecutar, **detenido por
decisión explícita de Capa 9** tras encontrar el bloqueo.

## Verificación previa (sin implementar nada)

1. **Gate de scope**: `PILOT_SCOPE_MATCH_CF6` da `PASS` mecánico, pero el scope firmado
   (`PILOT_EXECUTION-2026-041..044`) solo declara las fases `CF6-v2-R2`/`CF6-v2-R5` —
   no menciona R3 ni "fusion"/"benchmark". Los 4 chequeos automáticos son demasiado genéricos
   para distinguir este tipo de ejecución nuevo — **no se asumió cubierto**, se deja como
   hallazgo abierto (no bloqueante frente al bloqueo de datos, que es anterior).

2. **Datos** (bloqueante, confirmado):
   ```
   CanonicalStore (claims extraídos, B1):
     RW-0005: 0 claims, 0 tablas
     RW-0011: 0 claims, 0 tablas
     RW-0012: 0 claims, 0 tablas
   ```
   Los 3 `.sqlite3` de `factory/regulatory/canonical_store/` en este worktree están vacíos. No
   hay PDFs de los documentos del corpus (`RW-0005/0006/0009/0011/0012/0014`) en este entorno
   local — solo documentos no relacionados. `evidence_bundle.build_bundles_for_requirement()`
   (necesaria para comparar modo `bm25` vs `fusion`) devuelve candidatos vacíos siempre sin
   claims poblados -- una comparación sobre cero candidatos no mide nada real.

## Decisión

**Capa 9: "Detén R3 aquí hasta poblar el canonical_store en producción."**

No se implementó ningún código de R3 (ni benchmark, ni fixture, ni comparación). No se generó
ninguna medición simulada o sustituta. Cero llamadas LLM, cero cambios a
`relevance_model.py`/thresholds/Composer/`decomposition.yaml`.

## Condición de reactivación

R3 se retoma cuando el `canonical_store` (B1: extracción de claims desde los PDFs reales de
`RW-0005/0006/0009/0011/0012/0014`) esté poblado — probablemente solo posible en el servidor de
producción (`ing_cpmo@ivr-ia`), donde sí residen los documentos fuente. Antes de retomar,
verificar también explícitamente el gate de scope para el tipo de ejecución de R3 (no asumir
cubierto por el `PASS` mecánico ya observado).
