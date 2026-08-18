# J — cierre implementado (trazabilidad directive_id hasta manifest)

Fecha: 2026-08-18. Autorizado explícitamente por Cesar: "implementar
únicamente el cierre de J — trazabilidad directive_id hasta TraceabilityRow
y manifest final". Sin implementar ningún otro paquete del Bloque 3.

## Cambio

`factory/services/remediation_traceability_and_manifest.py`:
- `TraceabilityRow` gana el campo `directive_id: str`.
- `build_traceability_matrix()` lo puebla con
  `change.get("directive_id") or DIRECTIVE_ID_MISSING` — mismo patrón
  fail-explicit ya usado en el módulo para `revalidation_status`
  (`REVALIDATION_NOT_EXECUTED`): si el dato no está, se declara, nunca se
  omite en silencio ni se inventa.
- `DIRECTIVE_ID_MISSING` nueva constante exportada, para `package_state`
  de origen anterior a `77a9b66` (previo a que `directive_id` fuera
  obligatorio en `create_package()`).

No se tocó `build_package_manifest()` ni `regulatory_document_package_pipeline.py`:
`_as_dict()` en el pipeline usa `dataclasses.asdict()` sobre cada
`TraceabilityRow`, así que el nuevo campo llega automáticamente al artefacto
`ARTIFACT_MATRIX` del manifest final sin ningún cambio adicional — confirma
lo que decía la verificación previa (`J_POST_P0_VERIFICACION.md`): el fix
real era acotado a este archivo.

## Tests

`factory/tests/test_remediation_traceability_and_manifest.py`:
- Fixture `_change()` ahora incluye `directive_id="DIR-1"` por defecto.
- `test_directive_id_travels_from_change_to_row` — el valor real viaja sin
  re-derivarse.
- `test_missing_directive_id_declares_explicitamente_never_silently` —
  ausencia del campo se declara con `DIRECTIVE_ID_MISSING`, nunca se omite.

Resultado: 23/23 en el archivo del módulo. Suites relacionadas
(`test_corrected_document_generation_gate.py`,
`test_regulatory_document_package_pipeline.py`, y todo lo que matchea
`remediation|traceability|manifest` en `factory/tests/`): **172/172
pasan**, sin regresiones.

## Resultado

```
J_TRACEABILITY_CONFIRMED =    SI (directive_id ahora expuesto en
                               TraceabilityRow y propagado al manifest
                               final vía asdict())
CODE_CHANGED =                2 archivos (remediation_traceability_and_manifest.py,
                               test_remediation_traceability_and_manifest.py)
TESTS =                       172/172 pasan
COMMIT =                      pendiente (ver siguiente paso)
```

## Siguiente paso

Mostrar diff a Cesar y commitear con su aprobación explícita, según regla
permanente del proyecto para corridas de documentación+diseño/verificación
acotada.
