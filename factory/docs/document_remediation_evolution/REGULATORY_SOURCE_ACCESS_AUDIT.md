# REGULATORY_SOURCE_ACCESS_AUDIT — Acceso y control de fuentes regulatorias

Verificación real ejecutada en esta auditoría (2026-07-21): `curl` en vivo
(GET, sin caché, `--max-time 15`) contra las 3 URLs oficiales declaradas en
`factory/regulatory/sources/registry.json`. No se inventó ningún enlace,
cita, numeral ni versión — donde la verificación no fue posible o falló, se
aplica el estado correspondiente sin conclusión de cumplimiento.

## Fuente 1 — 21 CFR Part 11 (US, FDA/eCFR)

| Campo | Valor |
|---|---|
| Organismo emisor | eCFR (Office of the Federal Register), bajo autoridad FDA |
| Nombre | Title 21 Part 11 — Electronic Records; Electronic Signatures |
| Versión / fecha | `current` (eCFR es un texto vivo, sin número de versión fijo — la copia gobernada quedó fijada por hash en la ingesta) |
| Vigencia | **NO reverificada desde la ingesta** — `regulatory_currency_status: pending_reverification` (campo real de `sources/registry.json`) |
| URL oficial | `https://www.ecfr.gov/current/title-21/chapter-I/subchapter-A/part-11` |
| Acceso real verificado ahora | **200 OK** (verificado en esta auditoría, GET real) |
| Numerales cubiertos por el catálogo | § 11.10(a), (d), (e), (g); § 11.50(a)(1) — 5 entradas |
| Hash y ubicación de la copia gobernada | sha256 `e41aa1b33dd09397352820b6568b0619d8b61a7f340f550a09553e6fdd82c21e`, `factory/regulatory/sources/sha256/e41aa1b3.../OFFICIAL_ECFR_21CFR_part11.txt`, `hashes_match: true`, `local_integrity_status: PASS` |
| `binding_status` | `binding_regulation` (regulación vinculante) |
| Estado | **REGULATORY_SOURCE_UNVERIFIED (vigencia)** — el acceso y el hash local son verificables ahora mismo, pero la vigencia (¿el texto sigue siendo el actual, no ha habido enmienda desde la ingesta?) no tiene un mecanismo de reverificación activo. |

## Fuente 2 — EU GMP Annex 11 (Comisión Europea / EudraLex Volumen 4)

| Campo | Valor |
|---|---|
| Organismo emisor | Comisión Europea (EudraLex Volume 4) |
| Nombre | Annex 11 — Computerised Systems |
| Versión / fecha | No declarada en `registry.json` (sin campo de versión/fecha de publicación) |
| Vigencia | `pending_reverification` |
| URL oficial declarada | `https://health.ec.europa.eu/document/download/annex-11-computerised-systems` |
| **Acceso real verificado ahora** | **404 Not Found** (verificado en esta auditoría, GET real, dos veces, sin caché) — **la URL declarada como oficial ya no resuelve** |
| Numerales cubiertos por el catálogo | Sección 4.1 (Validation), 7.1 (Data Storage), 9 (Audit Trails), 12.1 (Security), 17 (Archiving) — 5 entradas |
| Hash y ubicación de la copia gobernada | sha256 `8ec11211ba33bf88ad4e71acc6bf60fd0e7823cfa495b116872e2c287e4aebbb`, `factory/regulatory/sources/sha256/8ec11211.../OFFICIAL_EU_GMP_ANNEX11.pdf`, `hashes_match: true`, `local_integrity_status: PASS`, con extracción derivada trazada (`pdfplumber` v0.11.10, hash del artefacto derivado registrado) |
| `binding_status` | `binding_requirement` |
| Estado | **REGULATORY_SOURCE_UNVERIFIED** — la copia local tiene hash íntegro y trazable, pero **la URL oficial declarada no es accesible ahora mismo**. No se puede confirmar que la copia gobernada siga correspondiendo a la publicación vigente en el sitio del organismo emisor. `EVALUATION_INCOMPLETE` para cualquier análisis que dependa de reverificar esta fuente contra su origen. **No se inventó una URL alternativa** — corresponde a decisión humana/QA localizar la URL vigente correcta si se requiere reverificación. |

## Fuente 3 — MHRA GxP Data Integrity Guidance (Reino Unido)

| Campo | Valor |
|---|---|
| Organismo emisor | MHRA (Medicines and Healthcare products Regulatory Agency, UK) |
| Nombre / versión | GXP Data Integrity Guidance and Definitions, **Revision 1, March 2018** (versión y fecha sí declaradas explícitamente en `registry.json`) |
| Vigencia | `pending_reverification` |
| URL oficial declarada | `https://assets.publishing.service.gov.uk/media/5c3b3c37e5274a15b9788e88/MHRA_GxP_data_integrity_guide_March_edited_Final.pdf` |
| **Acceso real verificado ahora** | **404 Not Found** (verificado en esta auditoría, GET real, dos veces) — **la URL declarada como oficial ya no resuelve** (patrón típico de `assets.publishing.service.gov.uk`: rutas por hash de archivo que rotan cuando el documento se re-publica) |
| Numerales cubiertos por el catálogo | p.4, p.5, p.8 — definiciones ALCOA/ALCOA+ (Attributable, Legible, Contemporaneous, Original, Accurate, Complete, Consistent, Enduring, Available) — **9 entradas del catálogo**, no 8: hay 9 checkpoints ALCOA+ reales bajo este `source_id` (el docstring de `regulatory_catalog.py` dice "8 ALCOA+" — es una imprecisión menor del propio comentario del código frente al conteo real de `requirements.yaml`, verificado aquí campo por campo) |
| Hash y ubicación de la copia gobernada | sha256 `e05dda11a93324c47f3f96aa106933d0073d8eb450f09d736ea53b19cf7ebd0d`, `factory/regulatory/sources/sha256/e05dda11.../OFFICIAL_MHRA_GXP_DI_GUIDANCE_2018.pdf`, `hashes_match: true`, `local_integrity_status: PASS`, extracción derivada trazada |
| `binding_status` | `non_binding_guidance` (es guía oficial, no norma vinculante — usada por el sistema para derivar `gxp_impact=INDIRECT`, ver `gap_assessment_finding_mapper.py`) |
| Estado | **REGULATORY_SOURCE_UNVERIFIED** — mismo patrón que Fuente 2: copia local íntegra, URL oficial declarada actualmente inaccesible. `EVALUATION_INCOMPLETE`. |

## Discrepancia real encontrada en esta auditoría: conteo de entradas ALCOA+

`regulatory_catalog.py` (docstring) declara *"8 ALCOA+"*; `requirements.yaml`
contiene **9** entradas con `source_id=mhra_gxp_di_guidance_2018`
(`ALCOA_ATTRIBUTABLE`, `ALCOA_LEGIBLE`, `ALCOA_CONTEMPORANEOUS`,
`ALCOA_ORIGINAL`, `ALCOA_ACCURATE`, `ALCOA_COMPLETE`, `ALCOA_CONSISTENT`,
`ALCOA_ENDURING`, `ALCOA_AVAILABLE`). El total de 19 entradas del catálogo
(5+5+9=19) es correcto; el desglose "8" del comentario es inexacto. No afecta
la validación fail-closed del catálogo (que no depende de ese comentario),
pero se registra como hallazgo de higiene documental.

## Resumen ejecutivo de esta sección

| Fuente | Acceso URL ahora | Vigencia reverificada | Hash local | Estado |
|---|---|---|---|---|
| eCFR 21 CFR Part 11 | 200 OK | No | PASS | REGULATORY_SOURCE_UNVERIFIED (solo vigencia) |
| EU Annex 11 | **404** | No | PASS | REGULATORY_SOURCE_UNVERIFIED (acceso + vigencia) |
| MHRA GxP DI 2018 | **404** | No | PASS | REGULATORY_SOURCE_UNVERIFIED (acceso + vigencia) |

**Ninguna de las 3 fuentes tiene hoy un mecanismo de reverificación
periódica de vigencia ni de detección de rotura de enlace.** Las 3 copias
locales tienen integridad de hash confirmada — el riesgo no es "el catálogo
contiene texto alterado", es "no hay forma automática de saber si el texto
gobernado quedó desactualizado o si la URL de origen murió, hasta que
alguien lo verifica manualmente (como en esta auditoría)".

## Aplicación de los estados exigidos

Para cualquier análisis de documento que dependa de estas 3 fuentes
(ANNEX11_*, ALCOA_*, 21_CFR_11.*): mientras la vigencia no se reverifique
activamente y, en 2 de 3 casos, mientras la URL oficial declarada no vuelva
a resolver o se reemplace por una URL verificada (nunca inventada), cualquier
hallazgo que dependa de esas 14 entradas del catálogo (9 ALCOA+ + 5 Annex 11)
debe acompañarse de:

```
REGULATORY_SOURCE_UNVERIFIED = true
EVALUATION_INCOMPLETE = true (para conclusiones que dependan de vigencia confirmada)
COMPLIANCE_NOT_DETERMINED = true
```

La entrada eCFR (5 entradas 21 CFR Part 11) tiene acceso URL confirmado
ahora, pero **igual** hereda `REGULATORY_SOURCE_UNVERIFIED` porque la
vigencia no está activamente reverificada — el estado de "vigencia
verificada" no puede degradarse a "verificado" solo porque el enlace
responda; ambas condiciones (acceso + vigencia) deben cumplirse.

## Qué falta para pasar a VALIDATED (no implementado en esta auditoría)

1. Job/proceso de reverificación periódica de acceso HTTP a las 3 URLs
   (ligero: HEAD/GET + comparación de hash del contenido descargado contra
   `sha256_original`).
2. Proceso para localizar y proponer (nunca auto-aplicar) una URL de
   reemplazo cuando una fuente declarada rompe — con aprobación humana
   explícita antes de escribirla en `registry.json` (ver
   `TARGET_REGULATORY_ARCHITECTURE.md`).
3. Campo de vigencia con fecha de última reverificación real (hoy
   `regulatory_currency_status` es un enum estático sin timestamp de
   reverificación).
