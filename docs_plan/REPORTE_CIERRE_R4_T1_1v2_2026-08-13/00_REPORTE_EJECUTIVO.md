# 00 — Reporte Ejecutivo: Cierre R4-T1.1v2

**Fecha:** 2026-08-13
**Alcance:** Documentación y auditoría del cierre de R4-T1.1v2 (desbloqueo de
formato y validación en frío). No se ejecutó LLM, no se corrió Tier-1, no se
generaron documentos reales, no se modificó código durante la elaboración de
este reporte.

## Resumen ejecutivo

R4-T1.1v2 cierra dos bloqueantes declarados en
`docs_plan/R4_T1_1v2_DESBLOQUEO_Y_VALIDACION_FRIA.md`:

1. **§4 — Gobernanza de la autoría de directivas de remediación:** familia
   nueva `REMEDIATION_DIRECTIVE_AUTHORSHIP` (registrada en
   `factory/registry/decision_families.yaml`), separada deliberadamente de
   `REMEDIATION_PACKAGE_GENERATION` porque una directiva no tiene
   `package_id` (existe antes del paquete). D6 (`D6_pdf_generation_policy`)
   queda firmada por Cesar en `factory/services/w5_human_decisions.py` /
   `factory/layer9/decisions/w5_human_decisions.jsonl`, confirmando como
   decisión humana la política de generación PDF sin fuente editable ya
   implementada.
2. **§3.2 / §2.3.b — Panel mínimo de adjudicación y marca NO_APROBADO:**
   UI de Mission Control (`factory/ui/mission_control.html` +
   `factory/ui/js/mission_control/remediation.js`) sobre endpoints ya vivos
   de directivas/paquetes de remediación, sin backend nuevo. Constante
   `NO_APROBADO_MARK = "BORRADOR — NO APROBADO — pendiente de revisión QA"`
   centralizada en `factory/services/candidate_document_generator.py` y
   aplicada a candidato y redline.

Adicionalmente se cerró R2.2 (familia `EMBED_EXECUTION`, capa semántica
local de embeddings) y R3-T1.8 (persistencia de ejecución piloto auditada y
registros de cola de revisión).

## Veredicto de cierre

**PARCIAL — con un bloqueante técnico menor identificado durante esta
auditoría, no durante el desarrollo original.**

- Las 5 secciones evaluadas (§0 a §4, ver `01_ESTADO_PLAN_SECCIONES.md`)
  **PASAN** en cuanto a diseño, gobernanza y código presente en el
  repositorio.
- La suite de validación en frío (`test_r4_t1_1v2_cold_chain_validation.py`,
  8 criterios de aceptación declarados en el commit `0796bb9`) se ejecutó
  dentro del contenedor `factory-api` durante esta auditoría:
  **6 de 7 tests pasan**. El test
  `test_full_cold_chain_rw0005_directive_to_traceable_candidate` **falla**
  por `FileNotFoundError: git` — el binario `git` no está instalado dentro
  del contenedor `factory-api`, y ese test específico invoca
  `subprocess.run(["git", "rev-parse", "HEAD"], ...)` como parte de su
  propio código de prueba (no es un llamado de producción). Es una brecha
  de tooling del contenedor, no un defecto de lógica de negocio.
- No se ejecutó ningún LLM ni Tier-1 durante esta auditoría, conforme a
  instrucción explícita.

## Qué se cerró

- Familia de gobernanza `REMEDIATION_DIRECTIVE_AUTHORSHIP` + D6 firmado.
- Panel de adjudicación de remediación en Mission Control + marca
  NO_APROBADO centralizada.
- Familia `EMBED_EXECUTION` (R2.2) separada de `PILOT_EXECUTION`.
- Persistencia auditada de ejecución piloto y cola de revisión (R3-T1.8).
- `.gitignore` corregido para excluir `.gnupg/` y `private_reports/` de la
  raíz del home (que también es el repo).

## Qué sigue bloqueado

- **Bloqueante A (nuevo, detectado en esta auditoría):** instalar `git`
  dentro de la imagen del contenedor `factory-api` (o ajustar el test para
  no depender de un binario ausente en el runtime productivo) antes de
  poder afirmar que la suite de validación en frío pasa al 100%.
- **Bloqueante B (ya conocido, no tocado por R4-T1.1v2):** juicio QA humano
  sobre los 4 `pending` y 1 `superseded`/`confirmed` en
  `review_queue.jsonl` para RW-0005 — ninguno fue promovido a decisión de
  remediación real todavía.
- Clic real de Cesar en el panel de adjudicación nuevo (UI construida y
  verificada por código; no verificada visualmente en navegador durante
  esta auditoría — tarea es documentación, no ejecución de UI).
- `R4_GENERATION_GATE` no evaluado en esta corrida (ver
  `05_PENDIENTES_Y_SIGUIENTE_FASE.md`, bloque B).

## Recomendación final

Cerrar R4-T1.1v2 en el registro de fases **condicionado** a resolver el
Bloqueante A (trivial: agregar `git` al Dockerfile de `factory-api` o
mockear `subprocess` en el test) antes de declarar la suite en verde al
100%. El resto del alcance de R4-T1.1v2 (gobernanza, UI, marca NO_APROBADO)
está verificado por código y por ejecución parcial de tests, sin hallazgos
de diseño. No se recomienda avanzar a `R4_GENERATION_GATE` hasta la
adjudicación humana de los pendientes de `review_queue.jsonl`.
