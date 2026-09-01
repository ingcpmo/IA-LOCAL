# F1 — GROUND TRUTH DE ENCABEZADOS · HOJA DE REVISIÓN HUMANA (Capa 9)

**Plan de reconciliación v1.1 · FASE 1 · corrección 10 · cierre procedimental.**

**Propósito:** el ground truth de F1 debe ser **declarado y aprobado por un humano ANTES de
cualquier re-medición**. La corrida anterior lo derivó mecánicamente; esta hoja lo presenta
para que Capa 9 lo verifique contra los PDF reales y lo apruebe (o corrija).

---

## ✅ APROBADO POR CAPA 9 — 2026-09-01T18:48:28Z

```
GROUND_TRUTH_F1_HUMAN_APPROVED   = SÍ
CORRECCIONES                     = ninguna
JERARQUÍA                        = F1 valida ÚNICAMENTE los 8 encabezados de NIVEL 1 por documento.
                                   Existen subencabezados N.M / N.M.N legítimos en los 3 PDF ->
                                   EXPLÍCITAMENTE FUERA DEL ALCANCE de F1 (por decisión de Capa 9).
APROBADO_POR                     = Capa 9 (Cesar)
FECHA_HORA                       = 2026-09-01T18:48:28Z
```

**PDF verificados en el momento de la aprobación (hashes sin cambio vs §1):**

| doc_id | SHA256 |
|---|---|
| RW-0011 | `13bc6f50c4cee50211d6877249cbacd19e797b0cb93e58e3579c037be68fbf53` |
| RW-0012 | `de7b70c297f0fbf1269d47e334a7575d4de3429bff6ed797fc663b85fea15c71` |
| RW-0014 | `8a67414d90ba28c8ee3cf9939d3be0d670ed7c8794a61f049b07ebe07ebf4ccb` |

**Efecto de esta aprobación:**
- El ground truth de §2 (8 encabezados de nivel 1 por documento) queda **CONGELADO y
  HUMANO-APROBADO**.
- El veredicto F1 (`CORRECCIÓN`) pasa de PROVISIONAL a **pendiente sólo de la re-medición
  reproducible** contra este ground truth ya humano-aprobado.
- Orden obligatorio de cierre (Capa 9): (1) registrar esta aprobación → (2) **commit** de la
  aprobación SIN medir → (3) recién entonces re-ejecutar `F1_measure.py` → (4) verificar
  PRE-fix 0/8 y POST-fix 8/8 exacto, sin sobre-segmentación de nivel 1 → (5) reporte
  correctivo + segundo commit → (6) tag nuevo `reconc-F1-r1` (NO se mueve `reconc-F1`) →
  (7) NO ejecutar F2.

*(Este bloque se commitea ANTES de correr ninguna medición — commit 1 del cierre corregido.)*

---

## 1. PDF verificados (filename + SHA256 + páginas)

| doc_id | filename | SHA256 | bytes | páginas | ¿== canonical_store meta? |
|---|---|---|---:|---:|---|
| **RW-0011** | `GMPAI/source/Rockwell/MCCPDC EMS Control Block Narrative revB.pdf` | `13bc6f50c4cee50211d6877249cbacd19e797b0cb93e58e3579c037be68fbf53` | 344 955 | 14 | **SÍ** (coincide) |
| **RW-0012** | `GMPAI/source/Rockwell/MCCPDC PCS Signal Interface Control Block Narrative.pdf` | `de7b70c297f0fbf1269d47e334a7575d4de3429bff6ed797fc663b85fea15c71` | 356 020 | 14 | **SÍ** (coincide) |
| **RW-0014** | `GMPAI/source/Rockwell/MCCPDC WFI Control Block Narrative revB.pdf` | `8a67414d90ba28c8ee3cf9939d3be0d670ed7c8794a61f049b07ebe07ebf4ccb` | 316 734 | 18 | **SÍ** (coincide) |

Los 3 SHA256 son idénticos a los registrados en `canonical_store/*.sqlite3` (`document.payload.sha256`)
para la extracción `canonical-v1-2026-08`. Son los mismos archivos.

---

## 2. GROUND TRUTH PROPUESTO — para verificación humana contra el PDF

Los 3 documentos son plantillas MAVERICK **"Control Block Narrative"**. Numeran los encabezados
de nivel 1 como **`N. TÍTULO`** (número, **punto**, espacio, título en MAYÚSCULAS), tanto en la
página "Contents" (pág. 2) como en el cuerpo. 8 encabezados de nivel 1 por documento.

> **Capa 9: verifique cada fila abriendo el PDF.** Marque cada `título` como `OK` o escriba la
> corrección. Confirme la columna `jerarquía`.

### 2.1 · RW-0011 — `MCCPDC EMS Control Block Narrative revB.pdf`  (14 pág, "Contents" en pág. 2)

| # | título propuesto (nivel 1) | 1ª aparición en cuerpo (pág) | en TOC | jerarquía | ¿OK? (Capa 9) |
|---|---|---:|---|---|---|
| 1 | OBJECTIVE | 3 | sí | nivel 1 | ______ |
| 2 | TERMINOLOGY | 3 | sí | nivel 1 | ______ |
| 3 | INPUT CONSIDERATIONS | 3 | sí | nivel 1 | ______ |
| 4 | EMS CONTROL DESCRIPTION | 4 | sí | nivel 1 | ______ |
| 5 | SOFTWARE PERMISSIVES | 14 | sí | nivel 1 | ______ |
| 6 | INTER-NETWORK RELATIONSHIPS | 14 | sí | nivel 1 | ______ |
| 7 | HARDWARE INTERLOCKS | 14 | sí | nivel 1 | ______ |
| 8 | REFERENCES | 14 | sí | nivel 1 | ______ |

### 2.2 · RW-0012 — `MCCPDC PCS Signal Interface Control Block Narrative.pdf`  (14 pág, "Contents" en pág. 2)

| # | título propuesto (nivel 1) | 1ª aparición en cuerpo (pág) | en TOC | jerarquía | ¿OK? (Capa 9) |
|---|---|---:|---|---|---|
| 1 | OBJECTIVE | 4 | sí | nivel 1 | ______ |
| 2 | TERMINOLOGY | 4 | sí | nivel 1 | ______ |
| 3 | INPUT CONSIDERATIONS | 4 | sí | nivel 1 | ______ |
| 4 | PCS SIGNAL INTERFACE CONTROL DESCRIPTION | 5 | sí | nivel 1 | ______ |
| 5 | SOFTWARE PERMISSIVES | 14 | sí | nivel 1 | ______ |
| 6 | INTER-NETWORK RELATIONSHIPS | 14 | sí | nivel 1 | ______ |
| 7 | HARDWARE INTERLOCKS | 14 | sí | nivel 1 | ______ |
| 8 | REFERENCES | 14 | sí | nivel 1 | ______ |

### 2.3 · RW-0014 — `MCCPDC WFI Control Block Narrative revB.pdf`  (18 pág, "Contents" en pág. 2)

| # | título propuesto (nivel 1) | 1ª aparición en cuerpo (pág) | en TOC | jerarquía | ¿OK? (Capa 9) |
|---|---|---:|---|---|---|
| 1 | OBJECTIVE | 4 | sí | nivel 1 | ______ |
| 2 | TERMINOLOGY | 4 | sí | nivel 1 | ______ |
| 3 | INPUT CONSIDERATIONS | 4 | sí | nivel 1 | ______ |
| 4 | WFI CONTROL DESCRIPTION | 5 | sí | nivel 1 | ______ |
| 5 | SOFTWARE PERMISSIVES | 17 | sí | nivel 1 | ______ |
| 6 | INTER-NETWORK RELATIONSHIPS | 18 | sí | nivel 1 | ______ |
| 7 | HARDWARE INTERLOCKS | 18 | sí | nivel 1 | ______ |
| 8 | REFERENCES | 18 | sí | nivel 1 | ______ |

---

## 3. Preguntas explícitas para Capa 9 (corrección 10)

1. **¿Los 8 títulos de cada documento son EXACTOS** (mayúsculas, guiones, "INTER-NETWORK" con
   guion, etc.) tal como aparecen en el PDF?
2. **¿Hay algún encabezado de nivel 1 adicional** en el cuerpo que NO esté en esta lista ni en el
   TOC? (El extractor sólo modela nivel 1; si existiera uno fuera del TOC, hay que declararlo).
3. **¿Existen sub-encabezados de nivel 2** legítimos (p.ej. `4.1 …`, `4.2 …`) que deban formar
   parte del ground truth de jerarquía? *(Límite conocido del extractor: sólo nivel 1; el fix
   `\.?` NO amplía el match a `N.M` — "4.1 Título" queda como párrafo).*
4. **¿La forma `N. TÍTULO` (con punto)** es la correcta para los 3, o algún documento usa
   `N TÍTULO` (sin punto)?

---

## 4. Bloque de aprobación (Capa 9) — RESUELTO

Ver bloque **"✅ APROBADO POR CAPA 9 — 2026-09-01T18:48:28Z"** arriba.

- `GROUND_TRUTH_F1_HUMAN_APPROVED = SÍ` · `CORRECCIONES = ninguna`.
- Respuestas a las 4 preguntas de §3: (1) títulos exactos = confirmados; (2) sin nivel-1
  adicional fuera del listado; (3) **sí hay** sub-encabezados N.M / N.M.N legítimos →
  **fuera del alcance de F1** por decisión de Capa 9; (4) forma `N. TÍTULO` (con punto) =
  correcta en los 3.

**Al aprobar:** se congela el ground truth humano, se marca el veredicto F1 (`CORRECCIÓN`)
como **CONFIRMADO por evidencia humana** tras la re-medición reproducible → gate F1 → F2.
