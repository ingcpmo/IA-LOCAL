# F2 — DEFINICIÓN DE DOBLE HASH (congelada ANTES de medir)

**Plan de reconciliación v1.1 · FASE 2 · corrección 7 · resuelve D-F0-05 ("logical hash subespecificado").**

Esta definición se fija **antes** de ver ningún resultado de materialización. No se ajusta
después.

---

## 1. `BYTE_HASH`

```
BYTE_HASH(archivo) = sha256( bytes del archivo tal cual )
```

- Para un **directorio** (store multi-archivo):
  ```
  TREE_BYTE_HASH(dir) = sha256(  concat, en orden lexicográfico de ruta relativa,
                                 de  sha256(cada archivo regular)  )
  ```

El `BYTE_HASH` **puede diferir legítimamente** entre entornos por: orden de páginas de
`pdfplumber`, versión de librería, VACUUM/rowid de SQLite, orden de inserción, `PRAGMA`,
timestamps embebidos (p.ej. `.docx` = zip con mtimes). **Un `BYTE_HASH` distinto NO es FAIL.**

## 2. `LOGICAL_CONTENT_HASH`

Hash del **contenido semántico canónico normalizado**, excluyendo metadatos volátiles.

### 2.1 SQLite (`canonical_store/*.sqlite3`, `graph_store/*.sqlite3`)

```
LOGICAL_CONTENT_HASH(db) = sha256(
    for tabla in sorted(nombres de tabla de sqlite_master WHERE type='table'):
        emit( tabla )
        for fila in  SELECT * FROM {tabla}  ORDER BY (todas las columnas, en orden de declaración):
            emit( json_canónico(fila) )
)
```

- `json_canónico(fila)`: cada valor serializado de forma determinista; si una columna contiene
  un JSON (p.ej. `payload`), se **re-serializa con claves ordenadas** (`json.dumps(obj,
  sort_keys=True, separators=(",",":"))`) para que el orden de claves no afecte el hash.
- **Campos volátiles EXCLUIDOS del hash** (se sustituyen por un placeholder fijo antes de
  serializar):
  - `provenance.run_id`, `provenance.run_context`, `provenance.agent_id`
  - cualquier `*_at` / `*_timestamp` / `generated_at` / `recorded_at`
  - `meta.extraction_version` **NO** se excluye (es contenido gobernado; un cambio ahí SÍ debe
    mover el hash).
- **Campos de identidad derivados** (`section_id`, `claim_id`, `finding_id`, `source_hash`,
  `entry_hash`): se **conservan** en el hash. Son deterministas por diseño (`build_section` /
  `_det_id`); si cambian, el contenido cambió.
- El **orden de filas** se impone por `ORDER BY` explícito sobre todas las columnas → inmune al
  orden físico / rowid / VACUUM.

### 2.2 JSON generado (`*_findings.json`, `report_v2`, `audit_metadata.json`, manifests)

```
LOGICAL_CONTENT_HASH(json) = sha256( json.dumps( obj_sin_campos_volátiles, sort_keys=True, separators=(",",":") ) )
```

Campos volátiles excluidos: `generated_at`, `run_id`, `run_context`, `timestamp`,
`*_at`, rutas absolutas del entorno (`/tmp/...`, `/home/...`) → normalizadas a `<ENV>`.

### 2.3 `.docx` (candidate / redline)

`.docx` = zip con mtimes internos → `BYTE_HASH` nunca estable. `LOGICAL_CONTENT_HASH(.docx)` =
`sha256` del **texto extraído en orden de lectura** (párrafos + celdas de tabla concatenados,
sin estilos). Si el texto extraído coincide, el documento es lógicamente idéntico aunque el
zip difiera.

---

## 3. Regla de veredicto (corrección 7)

| BYTE_HASH | LOGICAL_CONTENT_HASH | veredicto |
|---|---|---|
| igual | igual | reproducible total |
| **distinto** | **igual** | **reproducible lógico — NO es FAIL** |
| — | **distinto** | **FAIL** (el contenido cambió) |
| n/a (no regenerable) | manifestado con hash + ubicación | **PARTIAL** (EVIDENCIA_CONGELADA) |

`FAIL` de F2 = (a) el nº targeted sólo se reproduce **copiando stores a mano**, o
(b) el `LOGICAL_CONTENT_HASH` de un store regenerable **difiere** entre materialización limpia
y disco.

---

## 4. Clasificación de artefactos (fijada aquí)

| artefacto | clase | hash que decide |
|---|---|---|
| `canonical_store/*.sqlite3` (6 docs) | **REGENERABLE** (procedimiento: `materialize_stores.py` → `extract_document`) | `LOGICAL_CONTENT_HASH` §2.1 |
| `graph_store/*.sqlite3` | **REGENERABLE** (procedimiento: `build_project_graph` sobre los canonical regenerados) | `LOGICAL_CONTENT_HASH` §2.1 |
| `canonical_store_v2/`, `graph_store_v2/` | REGENERABLE (H-9/H-10, gitignored) — **fuera del alcance del nº targeted v1.2**; se manifiestan con ambos hashes | `LOGICAL_CONTENT_HASH` |
| `corpus_run/` (983 archivos, mtime 2026-08-20) | **EVIDENCIA_CONGELADA** — salida de corridas históricas, no regenerable sin re-correr | `BYTE_HASH` + ubicación |
| `pilot_run/` (780 archivos) | **EVIDENCIA_CONGELADA** — salidas de corridas (D-F0-02) | `BYTE_HASH` + ubicación |
| `pilot_run/dry_run_validation_r4_t1_1v2/*.docx` (4) | **EVIDENCIA_CONGELADA** — `.docx` no byte-reproducible (D-F0-03) | `LOGICAL_CONTENT_HASH` §2.3 (texto) |

`corpus_run/` y `pilot_run/` **NO** son insumo del nº targeted v1.2 — el targeted lee
`canonical_store` + `graph_store` + los YAML gobernados. Su reproducibilidad lógica no
condiciona el PASS de F2; se manifiestan para trazabilidad (D-F0-01/02/03).
