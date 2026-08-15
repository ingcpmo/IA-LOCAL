# D. Arquitectura de disciplina de Capa 8 (Context Engineering)

**Estado**: propuesta de diseño derivada de `ECC_ADOPTION_MATRIX.md`. No
implementa nada. Alcance honesto: esto es tooling de desarrollo para
Capa 8, no una mejora del producto GMP — salvo donde se indica lo
contrario.

## Qué es este documento y qué no es

Los patrones ECC ADOPTAR/ADAPTAR/INSPIRAR de la matriz, ensamblados como
una arquitectura coherente de disciplina de sesión para Claude Code
operando como Capa 8 dentro de GMP AI Factory. No es una recomendación de
instalar ECC — es un plan de reescritura selectiva, propia, con origen
citado.

## Componente 1 (P1, único que toca producto): contrato formal prompt↔verificador

**Problema real que resuelve**: la clase de defecto documentada como
Causa 2 en R3-T1 — un cambio de contrato en un lado (prompt YAML o
`evidence_verifier.py` o `chunked_engine.py`) que no se propaga al otro,
detectado tarde, ya materializado 3 veces en la cadena B3→B4→B5.

**Diseño**: formalizar el `common_contract_sha256` que ya existe en los 3
YAML gobernados (`part11_prompts.yaml`, `annex11_prompts.yaml`,
`alcoa_prompts.yaml`) como un JSON Schema explícito y versionado, en vez
de solo un hash de contenido opaco. El schema declara: campos que
`chunked_engine.build_prompt()` puede inyectar, forma esperada de
`evidencia_exacta`, checkpoints válidos por prompt. Un test de contrato
(no implementado aquí, solo diseñado) valida en Gate 0 que
`evidence_verifier.py` y `chunked_engine.py` coinciden con el mismo
schema — cualquier drift falla el gate ANTES de llegar a producción, no
después de un fallo silencioso.

**Gobernanza**: cambiar el schema es contenido gobernado (prompt_version
nuevo, aprobación de Cesar), igual que cambiar el texto de los YAML — no
se relaja ese control, se le agrega verificación mecánica.

## ACTUALIZACIÓN 2026-08-15 — Bloque 3 ejecutado, corrección al diagnóstico original

El diagnóstico de arriba subestimó lo que ya existía — mismo patrón
repetido en el proyecto ("diagnosticar antes de construir" encuentra
infraestructura ya construida). Al implementar este Componente
(`docs_plan/CONTINUACION_FASE0_P4_FASE1.md` Bloque 3), se confirmó que
**el contrato formal YA EXISTÍA**: `factory/regulatory/schemas/
checkpoint_llm_response_v1.json` (forma de checkpoint que produce
`chunked_engine.evaluate_chunked()`) y `finding_llm_v1.json` (forma que
consume `evidence_verifier.verify_llm_output()`) son JSON Schemas
Draft-07 reales, versionados por nombre de archivo (convención `_v1`/
`_v2` ya usada en el resto de `schemas/`), validados vía
`schema_loader.validate_against()` — no había que construir nada desde
cero.

**El gap real, más preciso que el diagnóstico original**:
`verified_pipeline_adapter.candidate_to_llm_output()` — el único
traductor checkpoint→finding activo en producción real ("Ruta B
verificada", invocado desde `chunked_engine.evaluate_chunked(
use_verified_pipeline=True)`) — construye el dict `llm_output` a mano en
Python (no vía generación forzada de Ollama) y su salida nunca se
validaba contra `finding_llm_v1` antes de pasarla a `verify_llm_output()`.
Exactamente la clase de defecto "no parchear el segundo sitio" (Causa 2,
B3→B4→B5), pero localizada en el sitio real, no uno hipotético. Tampoco
existía ningún test que fijara (`schema_sha256`) el contenido de los 2
schemas — un edit silencioso a cualquiera no rompía nada.

**Cerrado con `factory/tests/test_checkpoint_finding_contract.py`** (11
tests, cero cambio a `evidence_verifier.py`/`chunked_engine.py`/los
schemas mismos): pin de hash de ambos schemas (fuerza crear un `_v2.json`
nuevo ante cualquier cambio real, nunca editar el `_v1` en su sitio);
round-trip real de `candidate_to_llm_output()` contra `finding_llm_v1`
para los 5 `estado` reales que el motor puede emitir hoy, incluida la
forma literal exacta que `chunked_engine.py` construye en producción
(`v_candidate`); dos tests de control que confirman que el schema
realmente detecta un drift sintético (campo faltante, campo espurio) —
no solo que el test pasa por casualidad.

## Componente 2 (P2, entorno): secuencia obligatoria test→build→revisión

Adaptado de `ai-regression-testing`, reescrito para el stack real del
proyecto (Python/pytest, no Node/TS). Formalizar un comando propio
(ej. `/gmp-verify`, fuera de alcance implementar aquí) que fuerce, en
orden: `pytest` completo → Gate 0 (`factory_selfcheck.sh`) → recién
entonces admitir que Capa 8 pida revisión o declare una fase cerrada.
Esto mecaniza una disciplina que hoy es manual (y ha fallado
manualmente: R3-T1 documentó "los 3 falsos cierres" que este componente
ataca directamente).

## Componente 3 (P2, entorno, con control): autoevaluación de Capa 8

Adaptado de `agent-self-evaluation`, con el control de gobernanza como
parte del diseño, no como nota aparte:

- **Permitido**: Capa 8 se autoevalúa en ejes de proceso (completitud de
  la tarea, claridad del reporte, si siguió el flujo leer→deducir→
  implementar) al cerrar una fase.
- **Prohibido, sin excepción**: usar este mecanismo para autoevaluar la
  CORRECCIÓN de un hallazgo GMP, una conclusión de cumplimiento, o
  cualquier cosa que se acerque a que la IA certifique su propio juicio
  regulatorio. Esa evaluación es siempre humana (QA/Cesar/Capa 9),
  consistente con `CLAUDE.md`.

## Componente 4 (P3, inspiración, no construcción): hook de cierre de sesión

Inspirado en `delivery-gate`. En vez de copiar el check de disco/
"rationalization" del original, la versión propia verificaría
mecánicamente que Gate 0 corrió y dio PASS antes de que una sesión de
Capa 8 se declare "terminada" en cualquier reporte a Cesar. No bloquea
la sesión (Claude Code no tiene ese hook nativo garantizado en todos los
modos) — funciona como recordatorio/verificación, no como enforcement
duro, hasta que se evalúe si el hook `Stop` real está disponible y es
seguro en este entorno.

## Componentes explícitamente descartados (no construir)

- **eval-harness**: el fixture set 7P+2N + golden dataset ya son una
  versión superior y gobernada de este concepto. No se toca.
- **hooks/memory-persistence**: el sistema de memoria propio del
  proyecto ya es equivalente y ya tiene la regla dura correcta
  incorporada. Adoptar el mecanismo de ECC agregaría una segunda fuente
  de persistencia no auditada.
- **iterative-retrieval** para el pipeline de evidencia: el retrieval de
  evidencia GMP ya está resuelto (7/7 at_5). No hay problema que
  resolver ahí.

## Relación con la gobernanza IA (§19, ya aplicada por diseño, no repetida)

Ningún componente de este documento puede: aprobar cumplimiento, aprobar
un hallazgo, modificar el corpus, modificar una decisión humana, firmar,
impersonar un aprobador, generar una `RemediationDirective`, ni modificar
el original. El Componente 3 es el único con riesgo real de acercarse a
esa línea, y por eso lleva el control explícito descrito arriba.
