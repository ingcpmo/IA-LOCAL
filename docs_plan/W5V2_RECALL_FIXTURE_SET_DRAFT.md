# W5 V2 — Fixture Set de Recall (borrador, Bloque 2 del plan de remediación)

Estado: **BORRADOR, sin aprobar.** Propuesta de versión nueva del Golden
Dataset, pendiente de aprobación de Cesar como cualquier artefacto —
`W5V2_REMEDIACION_RECALL_MODELO.md` §2. Ningún experimento (H1-H6) corre
hasta que este set esté aprobado y `PILOT_EXECUTION-2026-002` esté firmada.

Actualización 2026-08-08: N2 (segundo negativo) ya seleccionado y
documentado por lectura directa del PDF — ver abajo. Los 9 fixtures (7
positivos + 2 negativos) están completos; el fixture set queda listo para
tu revisión/aprobación.

## Positivos (7) — de las llamadas reales del Piloto 1

Todos verificados a mano por lectura directa del PDF (ver
`W5V2_PILOTO1_REPORTE.md` §1). Cada uno con documento, página real
(0-based), requirement_id y el pasaje exacto que un evaluador competente
debe anclar.

| # | documento | agente | requirement_id | página | pasaje a anclar (resumen) |
|---|---|---|---|---|---|
| P1 | RW-0005 | fda_part11_agent | 21_CFR_11.10(e) | 45 | "Audit trail records shall be archived... Logins, logouts, and login attempts must be recorded" |
| P2 | RW-0005 | fda_part11_agent | 21_CFR_11.10(g) | 39 | Sección 4 Security / F09.00 Physical Security, control de acceso al operador |
| P3 | RW-0005 | eu_annex11_agent | ANNEX11_12 | 44 | UR3.3.6 Data retention — 1 año, archivado en ubicación alterna |
| P4 | RW-0011 | alcoa_plus_agent | ALCOA_ATTRIBUTABLE | 12 | Acción de calibración atada a credenciales del operador |
| P5 | RW-0005 | alcoa_plus_agent | ALCOA_CONTEMPORANEOUS | 45 | Mismo pasaje de audit trail (P1), envío a base de datos con timestamp |
| P6 | RW-0011 | fda_cgmp_211_agent | 21_CFR_211.68(b) | 12 | Mismo pasaje de credenciales/calibración (P4) |
| P7 | RW-0012 | fda_cgmp_211_agent | 21_CFR_211.68(b) | 13 | Pasaje casi idéntico a P6, documento REAL DISTINTO (SHA-256 distinto) |

## Negativos (2)

| # | documento | agente | requirement_id | página | tipo |
|---|---|---|---|---|---|
| N1 | RW-0005 | eu_annex11_agent | ANNEX11_4 | 1 | Caso CONOCIDO: "GAMP5" en lista de referencias numeradas — verificado en el Piloto 1, el control determinista lo rechazó correctamente en ambas corridas |
| N2 | RW-0005 | fda_part11_agent | 21_CFR_11.10(e) | 3 | Tabla de contenidos del documento: `"F12.00: Audit Trail .............................................. 45"` — mención superficial de la palabra clave exacta del requisito (audit trail), en un contexto (índice) que no aporta evidencia sustantiva ninguna. El contenido REAL de esa sección vive en la página 45 (= P1/P5 de este mismo fixture set), así que N2 y P1 comparten requirement_id y agente sobre el mismo documento — el par ideal para medir si el modelo distingue "la palabra está mencionada" de "el requisito está evidenciado" |

### N2 — verificación directa (lectura del PDF, 2026-08-08)

Página 3 (0-based) de RW-0005 es la sección "Contents" completa del
documento. Extracto relevante (texto real extraído del PDF, sin
modificar):

```
5 Data .......................................................................... 45
F11.00: Databases and Historical Logging ........................ 45
F12.00: Audit Trail .............................................................. 45
F13.00: Long-Term Archiving and Data Retrieval .............. 47
F14.00: Backup and recovery ............................................ 47
```

Ningún criterio de `21_CFR_11.10(e)` (generación automática, timestamp,
registro de acciones, preservación de valor previo, controles de acceso
privilegiado, trazabilidad, retención, exportación) puede evaluarse como
`MET` a partir de esta página — es una entrada de índice con un número de
página, nada más. Un evaluador competente debe marcar los 9 criterios como
`NOT_ASSESSABLE`/`NOT_MET` con evidencia vacía, igual que el rechazo
correcto de ANNEX11_4.

## Criterio de éxito (recordatorio, igual que §2 del plan)

```
recall >= 6/7 positivos con cita anclada válida (A en verde)
AND 2/2 negativos rechazados
AND schema_valid_rate = 100%
AND latencia por llamada registrada
```

## Pendiente antes de aprobar este fixture set

1. ~~Seleccionar y documentar N2~~ — cerrado 2026-08-08 (ver arriba).
2. Presentar a Cesar como versión nueva del Golden Dataset para aprobación
   — mismo circuito que cualquier artefacto gobernado.
3. Firma de Cesar sobre `PILOT_EXECUTION-2026-002` (tope de llamadas para
   H1-H6) antes de la primera llamada de diagnóstico — `W5V2_REMEDIACION_
   RECALL_MODELO.md` §3. Ningún experimento corre hasta entonces.
