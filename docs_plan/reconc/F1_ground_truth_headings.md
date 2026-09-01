# F1 — GROUND TRUTH de encabezados (congelado ANTES de medir)

**Plan de reconciliación v1.1 · FASE 1 · corrección 10.**
**Derivación:** MECÁNICA desde el DOCUMENTO REAL (cuerpo + TOC con líder de puntos), no sólo el TOC.
Reproducible por un tercero con `docs_plan/reconc/F1_measure.py` (`build_ground_truth`).
**Revisión humana:** pendiente en el gate F1 (Capa 9 confronta esta tabla con los PDF).

```
GROUND_TRUTH_SHA256 = 2f7a00dc9aad66bca7ee7195f9a19518fa0228bb0e5430a43fef772ab0b28f39
```
(sha256 del JSON canónico de `F1_ground_truth_headings.json`, claves ordenadas, ascii, sin espacios)

---

## RW-0011 — `MCCPDC EMS Control Block Narrative revB.pdf`  (sha256 `13bc6f50c4cee502`, 14 pág)

- Página "Contents": **2**
- Encabezados nivel-1 (forma literal en el documento: **`N. TÍTULO`**, con punto):

| # | título | visto en cuerpo (pág) | en TOC |
|---|---|---|---|
| 1 | OBJECTIVE | 3 | sí |
| 2 | TERMINOLOGY | 3 | sí |
| 3 | INPUT CONSIDERATIONS | 3 | sí |
| 4 | EMS CONTROL DESCRIPTION | 4 | sí |
| 5 | SOFTWARE PERMISSIVES | 14 | sí |
| 6 | INTER-NETWORK RELATIONSHIPS | 14 | sí |
| 7 | HARDWARE INTERLOCKS | 14 | sí |
| 8 | REFERENCES | 14 | sí |

## RW-0012 — `MCCPDC PCS Signal Interface Control Block Narrative.pdf`  (sha256 `de7b70c297f0fbf1`, 14 pág)

- Página "Contents": **2**

| # | título | visto en cuerpo (pág) | en TOC |
|---|---|---|---|
| 1 | OBJECTIVE | 4 | sí |
| 2 | TERMINOLOGY | 4 | sí |
| 3 | INPUT CONSIDERATIONS | 4 | sí |
| 4 | PCS SIGNAL INTERFACE CONTROL DESCRIPTION | 5 | sí |
| 5 | SOFTWARE PERMISSIVES | 14 | sí |
| 6 | INTER-NETWORK RELATIONSHIPS | 14 | sí |
| 7 | HARDWARE INTERLOCKS | 14 | sí |
| 8 | REFERENCES | 14 | sí |

## RW-0014 — `MCCPDC WFI Control Block Narrative revB.pdf`  (sha256 `8a67414d90ba28c8`, 18 pág)

- Página "Contents": **2**

| # | título | visto en cuerpo (pág) | en TOC |
|---|---|---|---|
| 1 | OBJECTIVE | 4 | sí |
| 2 | TERMINOLOGY | 4 | sí |
| 3 | INPUT CONSIDERATIONS | 4 | sí |
| 4 | WFI CONTROL DESCRIPTION | 5 | sí |
| 5 | SOFTWARE PERMISSIVES | 17 | sí |
| 6 | INTER-NETWORK RELATIONSHIPS | 18 | sí |
| 7 | HARDWARE INTERLOCKS | 18 | sí |
| 8 | REFERENCES | 18 | sí |

---

**Nota (corrección 10):** no se encontró NINGÚN encabezado de nivel 1 en el cuerpo que NO
estuviera también en el TOC. Los 3 documentos son plantillas MAVERICK "Control Block Narrative"
con TOC completo. La forma `N. TÍTULO` (con punto tras el número) es consistente en TOC y cuerpo
de los 3 — a diferencia de `N Título` (sin punto) del FS de Rockwell RW-0005.
