# G. Lista dura de intocables

Ninguna implementación futura derivada de esta auditoría puede modificar
lo siguiente sin control de cambios explícito y aprobación separada de
Cesar (más allá de la aprobación general de la iniciativa).

## Producto base (Docker 1, puerto 8000) — completo

`gmp-api` completo. Producto estable en modo real. NO MODIFICAR bajo
ninguna circunstancia derivada de esta auditoría (que es 100% sobre
`factory`, capas 7-9).

## Módulos de gobernanza y validación (capa 7, `factory/regulatory/`)

- `path_policy.py`
- `decision_scope_resolver.py` (si existe bajo ese nombre exacto —
  verificar ruta real antes de cualquier cambio; no confirmado en esta
  auditoría)
- `candidate_validity.py`
- `evidence_verifier.py` — **validación A**. El objeto de verdad para el
  anclaje literal. Cualquier capa DOM propuesta en `EVIDENCE_ARCHITECTURE.md`
  es aditiva, nunca reemplaza este módulo como fuente de verificación.
- `semantic_evidence_verification.py` — **validaciones B/C/D**,
  incluido `detect_reference_list_context` (la regla que rechaza
  ANNEX11_4).
- `absence_consolidator.py` — implementa `DOCUMENTATION_GAP` (el
  equivalente real de NO_SIGNAL). No se modifica su lógica de bloqueo
  fail-closed (`ABSENCE_BLOCKED_BY_*`, `APPLICABILITY_UNRESOLVED`).

## Contenido gobernado (Part 11)

- Los prompts YAML gobernados (`factory/engines/gmpai_integrity/prompts/
  part11_prompts.yaml`, `annex11_prompts.yaml`, `alcoa_prompts.yaml`) —
  cambiar su texto/versión requiere `prompt_version` nuevo y aprobación
  explícita de Cesar, nunca un commit silencioso de Capa 8.
- `factory/regulatory/requirement_catalog/requirements.yaml`.
- El corpus regulatorio completo (Annex 11, MHRA, eCFR ya gobernados en
  `factory/regulatory/sources/`).
- `decisions_v2.jsonl` (o el archivo de decisiones append-only
  equivalente — verificar nombre exacto vigente antes de tocar cualquier
  cosa cerca de él).
- La cadena de auditoría completa (`factory/audit/factory_audit.jsonl`,
  hash chain SHA-256, y cualquier `write_event`/`VALID_EVENTS` cerrado en
  `factory/core/audit_writer.py`).

## Originales fuente

- `GMPAI/source/Rockwell/` completo — el documento original es la fuente
  maestra, nunca se sobrescribe (regla permanente de `CLAUDE.md`).
- `factory/regulatory/scope/source_baseline_allowlist.yaml` — cualquier
  cambio de clasificación de un archivo fuente requiere el mismo proceso
  humano ya usado en Fase A de W5 V2, no un ajuste silencioso.

## Infraestructura (fuera del alcance de esta auditoría, recordatorio)

Docker, PostgreSQL, Redis, UFW, systemd, backups, contenedores `aria-*` y
`hotelbot-*` — ya prohibidos por `CLAUDE.md`, no relacionados con esta
auditoría pero reafirmados aquí por completitud.

## Regla de verificación antes de tocar cualquier archivo cercano a esta lista

Antes de modificar cualquier archivo en `factory/regulatory/` que no esté
explícitamente en esta lista pero importe o sea importado por alguno de
estos módulos, correr el test de contrato propuesto en
`CONTEXT_ENGINEERING_ARCHITECTURE.md` (Componente 1) si ya existe, o al
mínimo el Gate 0 completo antes y después del cambio.
