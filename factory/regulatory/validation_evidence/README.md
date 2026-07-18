# Validation Evidence — gobernanza (W5.3 Fase 5.4.4)

## Finalidad

Este directorio persiste la evidencia cruda de corridas reales del pipeline
de validación regulatoria (`run_validation_evidence.py` / futuro
`evaluate_chunked(run_context="validation")`): cada llamada real a Ollama,
su respuesta cruda, el veredicto del verificador determinista y las
conclusiones por requisito. Es el sustento técnico de
`golden_dataset_eligible` y de cualquier reclamo de `OLLAMA_SCHEMA_
COMPATIBILITY`/`REGULATORY_EVALUATION_COMPLETE` en los cierres de fase.

## Clasificación de confidencialidad

`INTERNAL_VALIDATION_EVIDENCE` (mismo valor que el campo `classification`
dentro de cada archivo). Contiene:
- Citas literales del documento fuente (`evidence_quote`, dentro de
  `llm_output`).
- La respuesta cruda completa del modelo (`raw_response`), que puede
  incluir fragmentos extensos del texto del documento.
- Metadata de ejecución (hashes, digest del modelo, timestamps) —
  reproducibilidad GxP.

No es información pública ni de cliente externo, pero sí puede contener
contenido de documentos regulados (ej. Rockwell/FS_v1.2) que no fue
autorizado para publicación en un repositorio de código versionado.

## Contenido prohibido en Git

**Ningún archivo `*.json`/`*.tmp`/`*.partial` de este directorio (raíz)
entra a Git.** Ver `.gitignore` local. Específicamente nunca deben quedar
tracked:
- `raw_response` (texto crudo del modelo).
- `llm_output` completo / `evidence_quote` / `rationale` (texto del
  documento o derivado de él).
- `source_text` (texto de chunk previo a inferencia).
- `_by_req_candidates` (nombre heredado de Fase 5.2/5.3 para el contenido
  crudo por requisito).
- Cualquier credencial, API key o secreto (no debería aparecer aquí nunca,
  pero el escáner de pre-commit lo verifica igual, ver más abajo).

La única excepción versionable son los **manifiestos sanitizados** en
`manifests/*.manifest.json` (ver más abajo) — generados por construcción
sin ninguno de los campos anteriores (allowlist, no blocklist).

## Permisos requeridos

- Directorio: `0750`, propietario/grupo = el usuario autorizado del host
  (`ing_cpmo`), **nunca** dejado como `root:root` (el contenedor
  `factory-api` escribe como root; `validation_evidence_writer.py` y
  `validation_evidence_manifest.py` hacen `chown` al propietario/grupo del
  directorio en cada escritura — nunca a un UID/GID hardcodeado).
- Archivos: `0640`.
- Escritura: atómica (`write` a `.<pid>.tmp` en el mismo directorio +
  `os.replace()`), nunca un archivo parcial visible con el nombre final.

## Retención aprobada

Sin expiración automática. Ningún módulo de este árbol
(`validation_evidence_writer.py`, `validation_evidence_manifest.py`,
`factory/core/path_policy.py`) expone una función de borrado, purga o TTL
— verificado por test (`test_validation_evidence_persistence.py`). Un
archivo de evidencia cruda vive indefinidamente en el filesystem local
hasta una decisión humana explícita de eliminarlo.

## Legal hold

Si cualquier corrida de este directorio queda referenciada en una
investigación, auditoría externa, o disputa regulatoria en curso, esa
evidencia (el/los archivo(s) `.json` específicos, identificados por
`run_id`/`document_sha256`) queda bajo legal hold: **no se elimina bajo
ningún procedimiento de este documento hasta el cierre formal del hold**,
sin excepción, independientemente de cualquier política de retención local
que se defina en el futuro. Quien declare el hold debe registrarlo como
evento de auditoría (`factory/core/audit_writer.py`) citando el/los
`run_id` afectados.

## Procedimiento de eliminación auditada

No existe automatización de borrado por diseño (ver Retención). Si algún
día se necesita eliminar un archivo de evidencia cruda:
1. Confirmar que no está bajo legal hold (ver arriba).
2. Registrar el motivo, quién autoriza, y el `run_id`/`document_sha256`
   afectado como evento de auditoría explícito (no un `rm` silencioso).
3. Verificar que el manifiesto sanitizado correspondiente en `manifests/`
   permanece intacto (la trazabilidad agregada de que la corrida existió
   no desaparece aunque el crudo se elimine).
4. Ejecutar el borrado manualmente, fuera de cualquier script/cron.

## Estructura

```
validation_evidence/
├── .gitignore              (tracked -- ignora *.json/*.tmp/*.partial de esta raíz)
├── README.md                (tracked -- este archivo)
├── <run_id>.json             (NO tracked -- evidencia cruda real)
└── manifests/
    └── <run_id>.manifest.json  (tracked -- sanitizado, ver validation_evidence_manifest.py)
```
