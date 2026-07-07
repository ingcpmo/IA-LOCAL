# Plan — Ingesta de Corpus Regulatorio Real

**Fecha:** 2026-06-25  
**Estado:** FASES 0–2 EJECUTADAS (2026-07-06) · Fases 3–4 pendientes  
**Bloqueador de go-live:** levantado — `go_live_blocked: false` en las 4 colecciones (corpus_manifest v2.0)  
**Siguiente paso:** Fase 3 (USP <621>/<1058>, ISPE — suscripción/licencia) · Fase 4 (SOPs del cliente)

## Ejecución 2026-07-06 (fases 0–2) — desviaciones del plan documentadas

- **Fase 0**: disclaimer implementado **default-deny** (más estricto que lo
  planeado): todo chunk sin fuente `OFFICIAL_*` recibe el prefijo
  `[RESUMEN INTERNO…]`; `sources[].official` expuesto; test G07-bis añadido.
- **Fase 1**: 9 documentos oficiales descargados y verificados (SHA-256 en
  `deployments/lab_qc_project/ingest_manifest.yaml` steps 5–8). eCFR vía API
  versioner oficial (vigencia 2026-07-01, XML fuente conservado).
- **Fase 2 — desviación**: `ingest_doc.sh` NO se usó (apunta al proyecto BASE
  prohibido y a una clase DocumentIngester inexistente). Vía real:
  `POST /api/v1/ingest` del deployment (la misma que creó el corpus original).
  12 ingestas → chunks oficiales: oos 172 · lims_di 318 · hplc 95 ·
  gmp_fda_regulations 296 (G05 ≥60 con solo oficiales en las 4). 12 eventos
  `knowledge_ingested` auditados (cadena verificada). Internal summaries
  reemplazados: chunks eliminados de ChromaDB y archivos movidos a
  `data/regulations/_archived_internal_summaries/` (Part 11: no borrar).
  USP <621>/<1058> e ISPE permanecen internos con disclaimer (Fase 3).

---

## Diagnóstico del estado actual

Todas las colecciones de `lab_qc_project` tienen `source_type: INTERNAL_SUMMARY`.
Los textos fueron redactados por GMP AI Factory como resúmenes de referencia.
Ningún archivo proviene de un PDF oficial. Esto bloquea el go-live comercial porque:

1. El agente cita "21 CFR 211.68" sin fuente verificable — riesgo regulatorio real.
2. Una inspección FDA/MHRA podría identificar el corpus como auto-generado.
3. El `corpus_manifest.yaml` lo documenta explícitamente y marca `go_live_blocked: true`.

**Infraestructura disponible (no re-implementar):**
- `ChromaDB` en `gmp-api` con 4 colecciones activas (585 chunks INTERNAL_SUMMARY)
- `factory/workspaces/lab_qc_project/knowledge/retriever.py` — ingest_directory() + retrieve()
- `factory/workspaces/lab_qc_project/scripts/ops/ingest_doc.sh` — script de ingesta auditado
- `factory/deployments/lab_qc_project/ingest_manifest.yaml` — registro SHA256 por step
- `gmp-api` EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2 ya instalado

---

## Fases del plan

### Fase 0 — Disclaimer en retriever (puente antes de corpus real)
**Esfuerzo:** 1 sesión · Sin adquisición documental · No bloquea Fase 1  
**Qué hace:** Mientras el corpus es INTERNAL_SUMMARY, el agente antepone:  
> `[RESUMEN INTERNO — No es cita del texto regulatorio oficial. Verificar contra el documento original.]`

**Dónde:** `knowledge/retriever.py` en `retrieve_context_with_sources()`:
```python
if "internal_summary_" in meta.get("source", ""):
    doc = "[RESUMEN INTERNO — NO ES TEXTO OFICIAL]\n\n" + doc
```

**Quality gate nuevo:** G07-bis — test que detecta disclaimer en respuestas cuando
la fuente es INTERNAL_SUMMARY; falla si el disclaimer está ausente.

**Valor:** Permite demos comerciales honestos durante el período de adquisición.
Documentado en `nota_disclaimer_r4.md` como Opción B.

---

### Fase 1 — Documentos de dominio público (gratis, sin gestión)

Todos los documentos de esta fase son descargables directamente.
No requieren suscripción ni acuerdo comercial.

#### Colección `lab_qc_oos` (OOS Investigation)

| Documento | Fuente | Formato | Estado |
|-----------|--------|---------|--------|
| 21 CFR Part 211 Subpart I (§211.160–§211.198) | ecfr.gov/current/title-21/chapter-I/subchapter-C/part-211/subpart-I | HTML→TXT | Pendiente |
| FDA Guidance — Investigating OOS Test Results (Oct 2006) | fda.gov/media/71001/download | PDF | Pendiente |

**Acción:** Descargar PDFs → colocar en `data/regulations/qa_oos/` → ejecutar:
```bash
bash factory/workspaces/lab_qc_project/scripts/ops/ingest_doc.sh \
  data/regulations/qa_oos/21_cfr_211_subpart_i.pdf fda
```

#### Colección `lab_qc_lims_di` (LIMS / Data Integrity)

| Documento | Fuente | Formato | Estado |
|-----------|--------|---------|--------|
| 21 CFR Part 11 (completo) | ecfr.gov/current/title-21/chapter-I/subchapter-A/part-11 | HTML→TXT | Pendiente |
| FDA Data Integrity Guidance 2018 | fda.gov/media/119267/download | PDF | Pendiente |
| EU GMP Annex 11 (Computerised Systems) | health.ec.europa.eu/system/files/2016-11/annex11_01-2011_en_0.pdf | PDF | Pendiente |
| MHRA Data Integrity Guidance 2018 | gov.uk/government/publications/data-integrity-definitions-and-guidance-for-industry | PDF | Pendiente |

#### Colección `lab_qc_hplc` (HPLC / Analytical)

| Documento | Fuente | Formato | Estado |
|-----------|--------|---------|--------|
| ICH Q2(R1) Validation of Analytical Procedures | ich.org/fileadmin/Public_Web_Site/ICH_Products/Guidelines/Quality/Q2_R1/Step4/Q2_R1__Guideline.pdf | PDF | Pendiente |
| 21 CFR 211.194 (Laboratory Records) | ecfr.gov/current/title-21/chapter-I/subchapter-C/part-211/subpart-J/section-211.194 | HTML→TXT | Pendiente |

#### Colección `gmp_fda_regulations` (GMP base)

| Documento | Fuente | Formato | Estado |
|-----------|--------|---------|--------|
| ICH Q9 Quality Risk Management | ich.org/fileadmin/.../Q9_Guideline.pdf | PDF | Pendiente |
| ICH Q10 Pharmaceutical Quality System | ich.org/fileadmin/.../Q10_Guideline.pdf | PDF | Pendiente |
| EU GMP Annex 11 | (mismo que lims_di) | PDF | Pendiente |
| 21 CFR Part 11 | (mismo que lims_di) | PDF | Pendiente |

**Total Fase 1:** ~8 documentos · 0 € · descargables hoy

---

### Fase 2 — Validación e ingesta auditada

Para cada documento de Fase 1:

1. **Calcular SHA256** y registrar en `ingest_manifest.yaml`:
   ```bash
   sha256sum <documento>.pdf
   ```

2. **Ingestar** via script auditado:
   ```bash
   bash factory/workspaces/lab_qc_project/scripts/ops/ingest_doc.sh \
     <documento>.pdf <colección>
   ```
   El script genera evento `knowledge_ingested` en la cadena Part-11.

3. **Quality gate G05** — verificar ≥ 60 chunks por colección:
   ```bash
   curl -s -H "X-API-Key: $FK" http://localhost:9000/api/v1/layer8/workspaces/lab_qc_project/knowledge/stats
   ```

4. **Actualizar `corpus_manifest.yaml`** — cambiar `source_type` de INTERNAL_SUMMARY a OFFICIAL_PDF; actualizar SHA256 y `go_live_blocked`.

5. **Test de regresión RAG** — preguntas representativas por colección:
   - OOS: "¿Qué dice 21 CFR 211.192 sobre la revisión de OOS?"
   - DI: "¿Qué es ALCOA+ según la FDA?"
   - HPLC: "¿Cuáles son los criterios de SST según ICH Q2?"

6. **Eliminar INTERNAL_SUMMARY** del directorio de cada colección tras verificar que los chunks oficiales superan el mínimo.

**Esfuerzo estimado:** 1–2 días (descarga + ingesta + validación)

---

### Fase 3 — Documentos de suscripción (gestión necesaria)

| Documento | Proveedor | Costo aproximado | Necesario para |
|-----------|-----------|-----------------|----------------|
| USP <621> Chromatography | USP — subscription | ~$1,200 USD/año (USP Digital) | lab_qc_hplc HPLC SST |
| USP <1058> AIQ | USP | incluido en suscripción | lab_qc_lims_di |
| ISPE GAMP 5 | ISPE — member | ~$400 USD no-miembro | gmp_fda_regulations |

**Opciones:**
- A) El cliente aporta sus propias copias licenciadas (lo más habitual en pharma).
- B) GMP AI Factory adquiere una suscripción USP (amortizable en múltiples clientes).
- C) Sustituir USP <621> por la descripción ICH Q2(R1) equivalente (sin gap funcional significativo para demos).

**Recomendación:** Opción A para go-live con primer cliente; Opción B si se confirman ≥ 3 clientes pharma.

---

### Fase 4 — Corpus específico del cliente

Cada cliente en pharma tiene SOPs propios que el agente debe conocer:
- SOP de OOS del cliente (WORD/PDF)
- SOP de Data Integrity del cliente
- Manual de uso del LIMS del cliente
- Especificaciones de producto relevantes

**Proceso:** El cliente entrega los archivos → GMP AI Factory los ingesta en una colección `<project_id>_sops` → Quality gate G05 → aprobación humana.

**Infraestructura ya lista:** `ingest_doc.sh` acepta cualquier PDF/TXT/MD.

---

## Orden de ejecución recomendado

```
Hoy mismo (sin bloqueadores):
  1. Fase 0 — disclaimer en retriever (1 sesión de código)

Esta semana:
  2. Descargar documentos Fase 1 (FDA, ECF, ICH, EMA, MHRA)
  3. Fase 2 — validar e ingestar los documentos descargados
  4. Actualizar corpus_manifest.yaml → go_live_blocked: false por colección

Antes de go-live comercial:
  5. Fase 3 — resolver documentos USP (con/sin cliente)
  6. Fase 4 — incorporar SOPs del cliente tras firma de acuerdo

Fecha objetivo go-live: cuando Fases 0–2 completadas + al menos 1 cliente confirma SOPs.
```

---

## Criterios de "corpus listo para go-live" por colección

| Colección | Chunks mínimos (G05) | source_type requerido | go_live_blocked |
|-----------|---------------------|----------------------|-----------------|
| lab_qc_oos | 60 | OFFICIAL_PDF | false |
| lab_qc_hplc | 60 | OFFICIAL_PDF | false |
| lab_qc_lims_di | 60 | OFFICIAL_PDF | false |
| gmp_fda_regulations | 60 | OFFICIAL_PDF | false |

Condición suficiente para unlock de go-live:  
**Todas las colecciones con source_type=OFFICIAL_PDF + chunks ≥ 60 + disclaimer eliminado.**

---

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|-----------|
| PDF con layout complejo (tablas, headers) → chunks pobres | Media | Medio | Preprocesar con `pdfplumber` si `pypdf` da texto sucio; revisar manualmente muestra de 5 chunks |
| USP requiere suscripción que cliente no tiene | Alta | Bajo | Opción C: ICH Q2(R1) cubre funcionalidad equivalente para demos |
| Cliente entrega SOPs en WORD con imágenes | Media | Medio | Convertir a PDF+OCR antes de ingestar; documentar en `ingest_manifest.yaml` |
| Agente cita erróneamente un chunk roto | Baja | Alto | Test de regresión RAG obligatorio antes de cada release (G05 + pregunta de control) |
| Disclaimer Fase 0 no se muestra en todas las respuestas | Baja | Alto | Guard test G07-bis — falla si INTERNAL_SUMMARY sin disclaimer |

---

## Archivos a modificar en cada fase

| Fase | Archivo | Cambio |
|------|---------|--------|
| 0 | `knowledge/retriever.py` | Añadir bloque disclaimer en `retrieve_context_with_sources` |
| 0 | `tests/test_agents.py` | Añadir test G07-bis: disclaimer presente cuando fuente es INTERNAL_SUMMARY |
| 1-2 | `data/regulations/<colección>/` | Añadir PDFs oficiales; eliminar INTERNAL_SUMMARY |
| 1-2 | `ingest_manifest.yaml` | Actualizar SHA256 y `actual_chunks` |
| 1-2 | `data/corpus_manifest.yaml` | Cambiar source_type y go_live_blocked por colección |
| 3-4 | `ingest_manifest.yaml` | Añadir steps 5–N con documentos USP y SOPs del cliente |

---

*Documento de planificación — no es código. Actualizar conforme avancen las fases.*  
*Generado: 2026-06-25 · Contexto: cierre U12 · Próxima acción: Fase 0 (código) → Fase 1 (adquisición)*
