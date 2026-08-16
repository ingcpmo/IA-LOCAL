# README — Reporte de Cierre R4-T1.1v2 (2026-08-13)

**Ruta absoluta de esta carpeta:**
`/home/ing_cpmo/docs_plan/REPORTE_CIERRE_R4_T1_1v2_2026-08-13/`

**Alcance:** documentación y auditoría del cierre de R4-T1.1v2 (desbloqueo
de formato y validación en frío). No se ejecutó LLM, no se corrió Tier-1, no
se generaron documentos reales, no se modificó código de producto durante la
elaboración de este reporte. No se hizo commit de esta carpeta.

## Índice de archivos

| Archivo | Contenido |
|---|---|
| `00_REPORTE_EJECUTIVO.md` | Resumen ejecutivo, veredicto de cierre (PARCIAL, condicionado), qué se cerró, qué sigue bloqueado, recomendación final. |
| `01_ESTADO_PLAN_SECCIONES.md` | Veredicto PASA/FALLA por sección del plan (§0 frescura de despliegue, §1 desbloqueo de formato, §2 validación en frío 8 criterios, §3 pre-vuelo 3.1–3.8, §4 gobernanza), con evidencia citada. |
| `02_COMMITS_Y_ARCHIVOS.md` | Detalle de los 5 commits auditados (`d224b24`, `0796bb9`, `c2c06bb`, `99f36c3`, `e8e8b2c`): propósito, archivos incluidos/excluidos, tests asociados. |
| `03_VALIDACION_EN_VIVO.md` | Verificaciones en vivo: endpoints de directivas en `/openapi.json`, health de `factory-api`, panel UI, decisiones RECORDED, confirmación de que `create_release_record()` no está conectado. |
| `04_GOBERNANZA_DATOS.md` | Análisis de `decisions_v2.jsonl`, `review_queue.jsonl` y `w5_human_decisions.jsonl`: qué fue append puro, qué fue mutación controlada, y justificación de cada una. |
| `05_PENDIENTES_Y_SIGUIENTE_FASE.md` | Pendientes clasificados en A (bloqueantes de R4-T1.1v2), B (bloqueantes de `R4_GENERATION_GATE`), C (limpieza de repositorio), D (deuda de diseño), más propuesta de siguiente plan mínimo. |
| `06_GIT_STATUS_FINAL.md` | Git status final: 286 archivos untracked (0 modificados/staged), distribución por directorio, confirmación de que `.gnupg/` y `private_reports/` quedan excluidos, recomendaciones de limpieza. |
| `CHECKSUMS.sha256` | Hash SHA-256 de todos los archivos `.md` de esta carpeta, para verificar integridad tras la descarga. |

## Instrucciones para descargar esta carpeta desde el servidor

Ver `DOWNLOAD_INSTRUCTIONS` al final de la respuesta que generó este
reporte, o ejecutar desde una máquina con acceso SSH al servidor
`ing_cpmo@ivr-ia`:

```bash
# Listar el contenido de la carpeta en el servidor
ssh ing_cpmo@ivr-ia "ls -la /home/ing_cpmo/docs_plan/REPORTE_CIERRE_R4_T1_1v2_2026-08-13/"

# Copiar la carpeta completa al equipo local
scp -r ing_cpmo@ivr-ia:/home/ing_cpmo/docs_plan/REPORTE_CIERRE_R4_T1_1v2_2026-08-13 .
```

## Verificación de integridad tras la descarga

```bash
cd REPORTE_CIERRE_R4_T1_1v2_2026-08-13
sha256sum -c CHECKSUMS.sha256
```
