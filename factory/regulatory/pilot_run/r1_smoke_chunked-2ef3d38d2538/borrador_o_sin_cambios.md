# Borrador corregido controlado — SMOKE / DEMO

**NO APROBADO. NO ES UN BORRADOR OFICIAL. Documento original intacto.**

## Resultado: SIN CAMBIOS PROPUESTOS

A diferencia del caso contemplado en `docs_plan/ARQ_RESOLVER_BLOQUEO_R1.md`
§4.2 ("si el caso P5 resulta 'cumple' (sin gap), el borrador correcto es
'sin cambios propuestos'"), aquí el motivo es distinto y hay que
declararlo explícito para no confundir uno con otro:

- **No es "sin cambios porque el requisito está satisfecho".**
- **Es "sin cambios porque no hay hallazgo anclado que los justifique."**

La regla permanente del proyecto (`CLAUDE.md`, "Reglas GMP permanentes")
es: **todo hallazgo requiere evidencia anclada; sin evidencia vacía ni
citas no ancladas**. El resultado de este smoke para `ALCOA_CONTEMPORANEOUS`
es `sin_evidencia_localizada` (ver `informe_hallazgos.md`) — no hay cita
verificada de la que derivar una corrección específica. Generar un
borrador de todos modos sería exactamente el tipo de fabricación que el
diseño de este sistema existe para impedir.

## Verificación de integridad del original

```
document_id: RW-0005
archivo: /home/ing_cpmo/GMPAI/source/Rockwell/215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf
sha256 (antes de esta corrida, del checkpoint): 56095a7541fbb62e30d00e77308fde4c2ac0f4ec945adbf19a968b79debc82eb
sha256 (verificado ahora, post-corrida): ver comando de verificación abajo
```

Verificación ejecutada como parte de este entregable — ver
`trazabilidad.json`, campo `original_sha256_post_smoke`. El original
**no fue tocado**: este smoke solo leyó el PDF (`_extract_pilot_excerpt`,
extracción de solo lectura vía `pypdf`), nunca lo escribió.

## Qué haría falta para un borrador real sobre este requisito

Solo si una corrida futura (idealmente ya con R2, recuperación
determinista) produce un `hallazgo_con_evidencia` para
`ALCOA_CONTEMPORANEOUS` sobre `RW-0005` — con cita anclada verificada por
`evidence_verifier` — correspondería generar un borrador acotado a ESE
hallazgo específico, siguiendo el diseño AGT-REM→AGT-QLT→AGT-DOC→AGT-RVL
ya especificado (`factory/docs/design/regulatory_redesign_v2/
AGENT_RESPONSIBILITY_ARCHITECTURE.md`), marcado como borrador controlado,
nunca aprobado automáticamente. Eso es alcance de R4, no de este smoke.
