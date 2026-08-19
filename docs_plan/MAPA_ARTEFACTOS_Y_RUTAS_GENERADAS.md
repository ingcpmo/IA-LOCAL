# MAPA DE ARTEFACTOS Y RUTAS GENERADAS — Analizador Documental GMP

Todas las rutas verificadas por lectura directa de código y/o
`ls`/`find` real en el filesystem el 2026-08-19. Ninguna ruta se
documenta sin haberla comprobado.

| Artefacto | Ruta exacta (bajo `/home/ing_cpmo`) | Quién lo genera | Momento / origen | Temporal o persistente | Versionado en Git | Cómo lo localiza Cesar |
|---|---|---|---|---|---|---|
| RC canónico legacy v1.4 (`gmpai_document_validation`) | `factory/release_candidates/gmpai_document_validation/gmpai_document_validation-rc-v1.4-20260715T031540/` (incluye `rc_manifest.json`, `artifacts/pipeline_pilot_llm.json`, `artifacts/test_report.json`, `artifacts/quality_gates_report.json`, `artifacts/diff.txt`, `artifacts/headless_*.log`) | Motor LEGACY (`pipeline.py`) | Corrida única, 2026-07-15 | Persistente | Sí | Navegar directo a la carpeta; `rc_manifest.json` tiene el resumen |
| Motor legacy (código fuente) | `factory/workspaces/gmpai_document_validation/app/*.py` | — (código, no artefacto de corrida) | Última modificación 2026-07-25 | Persistente en disco, **NO versionado** (`factory/.gitignore` excluye `workspaces/*`) | No | `ls factory/workspaces/gmpai_document_validation/app/` |
| Corridas del motor actual (checkpoints) | `factory/regulatory/pilot_run/checkpoints/chunked-*.checkpoint.json` y subcarpetas fechadas (`palanca_a_14b_7p2n_20260815/checkpoints/`, `dry_run_validation_r4_t1_1v2/`, `n2_isolated_20260818/`) | Motor CURRENT (`chunked_engine.py`) | Una carpeta por corrida/experimento | Persistente | Sí (salvo binarios `.docx` que sí están trackeados como se ve en `git status`) | `find factory/regulatory/pilot_run -maxdepth 1 -type d` |
| Evidencia de validación por corrida | `factory/regulatory/validation_evidence/chunked-*.json` | Motor CURRENT | Una por `run_id` de `chunked_engine` | Persistente | Sí | Buscar por `run_id` (aparece también en `review_queue.jsonl`) |
| Cola de revisión humana (findings pendientes) | `factory/layer9/review_queue.jsonl` (+ `.lock`) | `factory/layer9/human_review_queue.py` | Se agrega una línea por finding que necesita revisión | Persistente, append-only | Sí | `tail factory/layer9/review_queue.jsonl`, o vía UI (pantalla Findings/Cola de revisión) |
| Tier-1 reports (informe unificado) | Servido vía API `/api/v1/layer9/tier1-reports`, `/api/v1/layer9/tier1-reports/{run_id}`, `/api/v1/layer9/tier1-reports/{run_id}/markdown`; generador en `factory/regulatory/tier1_report.py` / `tier1_report_writer.py` | Motor CURRENT | Al finalizar una corrida | Depende del backend de almacenamiento del servicio (no confirmado en esta auditoría dónde persiste en disco — **NOT_TESTED**, verificar con `grep output_dir factory/regulatory/tier1_report.py` en una próxima sesión) | — | Vía API o UI, panel de reportes |
| Paquetes de remediación reales (histórico) | `factory/remediation_packages/gmpai_document_validation/PKG-FS-V1-2-REAL-CONTROLLED/` y `.../PKG-FS-V1-2-MEDIUM-RISK-REAL/` (`.package.lock`, `v1/state.json`) | `factory/services/remediation_package_service.py` | 2026-07-21 (confirmado por `mtime`) | Persistente el `state.json`; **los artefactos de contenido que referencia (`candidate_document.md`, `remediation_report.md`, `redline_document.md`) ya NO existen** — apuntaban a una carpeta de scratchpad de sesión (`/tmp/claude-1001/.../scratchpad/...`) que fue limpiada | Depende — `factory/remediation_packages/` no está en el `git status` de la raíz, verificar `.gitignore` de `factory/` antes de asumir | `find factory/remediation_packages -name state.json` |
| Paquete/directiva del clic K3 (2026-08-19) | **No localizado.** Ver `AUDITORIA_FUNCIONAL_E2E_POST_CIERRE.md` §0.3 | — | — | — | — | No hay ruta que dar — es el hallazgo de la auditoría |
| Redline candidatos R4-T1 (dry run) | `factory/regulatory/pilot_run/dry_run_validation_r4_t1_1v2/{v1_candidate_EXCLUDED_pending_exception.docx, v1_redline_EXCLUDED_pending_exception.docx, v2_candidate_INCLUDED.docx, v2_redline_INCLUDED.docx}` | Motor CURRENT (candidate_validity.py + pipeline de dry-run) | Modificados 2026-08-19 03:10-03:11 UTC (mismo día que K3, pero no confirmado que sea el mismo evento — ver auditoría) | Persistente, trackeado en git (aparecen en `git status` como modificados) | Sí | `ls -la factory/regulatory/pilot_run/dry_run_validation_r4_t1_1v2/` |
| Manifest de evidencia de validación | Generado por `factory/regulatory/validation_evidence_manifest.py` / `validation_evidence_writer.py` — ruta de salida no confirmada en disco en esta corrida (**NOT_TESTED**, revisar `output_dir`/`storage_dir` del módulo) | Motor CURRENT | Por documento validado | Presumiblemente persistente | — | Pendiente de confirmar en próxima sesión |
| Audit trail / auditoría | Expuesto vía API: `/api/v1/audit/entries`, `/api/v1/audit/summary`, `/api/v1/audit/verify`; backend en `factory/audit/` | Sistema central de auditoría | Continuo, por cada acción con `require_identity` | Persistente | `factory/audit/` existe como carpeta — contenido no volcado en esta auditoría (**NOT_TESTED** el detalle interno) | Vía API `/api/v1/audit/entries` o panel Audit Trail de la UI |
| Deployments activos | `factory/deployments/lab_qc_project/` (manifest.yaml, approval.json, docker-compose.yml, quality_gates_report.json, app/, tests/) y `factory/deployments/oos_hplc_investigator/` (misma estructura) | Pipeline de deploy de Capa 8/9 | Al desplegar una misión | Persistente | No confirmado explícitamente (contiene `.env` — verificar antes de cualquier commit que lo toque) | `ls factory/deployments/` |
| Resultados de test por misión | `factory/test_results/oos_hplc_investigator.jsonl` (+ `.lock`) | Suite de test de la misión | Por corrida de test | Persistente | No confirmado | `cat factory/test_results/oos_hplc_investigator.jsonl` |
| **Ausencia confirmada:** resultados de test de `lab_qc_project` | No existe `factory/test_results/lab_qc_project.jsonl` ni equivalente | — | — | — | — | Hallazgo de auditoría — proyecto desplegado sin este artefacto |
| Release records (`create_release_record`) | Función existe en `factory/services/remediation_package_service.py:702` pero **sin endpoint ni artefacto de salida alcanzable desde la UI** | — | Nunca se ejecuta en producción (sin puerta de entrada) | N/A | N/A | No hay ruta — confirmado que no puede generarse hoy |
| RC históricos por misión (todas) | `factory/release_candidates/{gmpai_document_validation, oos_hplc_investigator, c8_alcoa_validator, lab_qc_project}/` | Pipeline de release candidate por misión | Por versión de RC | Persistente | Sí (verificar caso por caso, algunos `.docx`/binarios pueden estar excluidos) | `ls factory/release_candidates/<proyecto>/` |
| Workspace archivado (`r6_change_control`) | `factory/workspaces_archive/r6_change_control_20260625/` | — | Archivado 2026-06-25 | Persistente, fuera del flujo activo | No confirmado | `ls factory/workspaces_archive/` |
| Proyecto inexistente `oos_hplc_api_test` | **No localizado en ningún directorio** (`workspaces/`, `workspaces_archive/`, `deployments/`, `release_candidates/`) | — | — | — | — | No hay ruta — confirmar con Cesar si el nombre es correcto o si nunca se creó |

──────────────────────────────────────────────────────────────────────────
## Notas de verificación

- Todas las rutas marcadas "confirmado" se comprobaron con `ls`/`find`
  reales durante esta auditoría (2026-08-19), no se copiaron de memoria
  ni de documentación previa sin verificar.
- Las filas marcadas **NOT_TESTED** son puntos donde el código referencia
  un mecanismo de guardado pero esta auditoría de solo lectura no
  ejecutó una corrida nueva para observar la ruta de salida real —
  quedan como pendiente explícito, no como "verificado".
- Antes de tocar cualquier archivo `.env` bajo `factory/deployments/*/`,
  recordar la regla del proyecto: nunca mostrar contenido de `.env`.

Ver también:
`docs_plan/AUDITORIA_FUNCIONAL_E2E_POST_CIERRE.md`
`docs_plan/MANUAL_OPERATIVO_UI_MISSION_CONTROL.md`
