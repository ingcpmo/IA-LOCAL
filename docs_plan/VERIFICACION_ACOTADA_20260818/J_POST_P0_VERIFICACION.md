# J — verificación post-cierre de P0 (solo lectura, sin código)

Fecha: 2026-08-18 (continuación de la sesión, tras commit `77a9b66`)
Rol: Arquitecto Principal, solo lectura, cero LLM, cero commits.

## Pregunta

`VERIFICACION_ACOTADA_Y_PAQUETES_CIERRE.md` (1.2) preveía: "Si el bypass
de 1.1 se cierra exigiendo `directive_id`, este mismo hallazgo (J) exige
agregar el campo explícitamente al schema y al manifest — no basta con
'ya viaja disfrazado de `change_id`'." El bypass ya se cerró exigiendo
`directive_id` (commit `77a9b66`). ¿Quedó J resuelto como efecto
colateral, o sigue pendiente?

## Resultado: J_TRACEABILITY_CONFIRMED = NO (parcialmente, actualizado)

**Lo que el fix de P0 sí logró:** `directive_id` ahora es obligatorio en
tiempo de creación del paquete (`remediation_package_service.py:377-392`,
`create_package()`) y se persiste tal cual en `package_state["changes"]`
porque `changes_by_id = {c["change_id"]: c for c in changes}`
(línea 409) guarda el dict completo del change, `directive_id` incluido.
O sea: **el dato ya vive en disco**, a diferencia de antes de `77a9b66`.

**Lo que sigue faltando:** `factory/services/remediation_traceability_and_manifest.py`
— `TraceabilityRow` (líneas 91-100) y `build_traceability_matrix()`
(líneas 103-131) leen `change["requirement_id"]` y
`[c["citation_id"] for c in change["citations"]]` del mismo dict que ya
tiene `directive_id` disponible, pero **no lo copian al `TraceabilityRow`
ni a ningún campo de salida**. Grep confirmado sobre el archivo completo:
cero apariciones de `directive_id` o `finding_id`. El manifest final que
ve un humano (o una API) sigue sin mostrar de qué directiva vino cada
cambio — el dato existe en el JSON crudo del paquete, no en la matriz de
trazabilidad que es el artefacto pensado para revisión humana.

## Conclusión

J no se cerró como efecto colateral de P0. Es un cambio real pendiente,
acotado y de bajo riesgo:
- Agregar `directive_id: str` a `TraceabilityRow`.
- Poblarlo en `build_traceability_matrix()` con `change.get("directive_id")`.
- Decidir si además se expone en el manifest JSON serializado (fuera de
  este archivo, en el punto donde `TraceabilityRow` se convierte a dict
  para el paquete final — no verificado en esta pasada, fuera de alcance
  de "solo J").

```
J_TRACEABILITY_CONFIRMED =    NO (dato persiste en disco desde 77a9b66,
                               pero no se expone en TraceabilityRow/manifest)
CODE_CHANGED =                0 (esta verificación es solo lectura)
```

Pendiente: decisión de Cesar sobre si autoriza este fix acotado (2 líneas
en `remediation_traceability_and_manifest.py`, + tests) antes de seguir
con D (pregunta regulatoria ALCOA_ATTRIBUTABLE/DS) o el Bloque 3.
