# W7 Fase 0 — Preflight: primera corrida real del modo revisión (W6.5.1)

Estado: **EJECUTADO 2026-07-07** · Actor: Cesar (trigger manual y decisión;
POSTs lanzados desde servidor bajo su autorización explícita en sesión — su
UI no emitía las peticiones, ver Hallazgo UX) · Modelo: qwen2.5:7b-instruct
· Doc: `data_integrity_assessment` de `oos_hplc_investigator`.

## Corridas

| | v07 (draft) | v08 (revision) |
|---|---|---|
| Modo / temp | draft / 0.2 | **revision / 0.0** · based_on: 7 · ledger: 1 |
| Latencia | 522 s, sin retry | 562 s, sin retry |
| Formato | válido, 1 claim/viñeta | válido |
| Claims (S/P/U/Uv) | 2/3/**1**/7 | 2/4/**0**/7 |
| Confianza | baja (unsupported_claims) | media |
| Verificador v2 | 0 findings (correctos: única cita 11.10(e) dentro del alcance; negaciones no contradichas por registros) | 0 findings |
| Auditoría | generated v7 mode=draft | decision v7 + generated v8 mode=revision ledger_sha=1 |

Guidance única del ledger (aprobada por Cesar): 3 correcciones concretas
(overclaim ALCOA+ en [E: runs] + separar negación; "Relevo candidato"→RC y
reconocer deployment; eliminar "falta perfil OOS" — qa_oos_profile lo es).

## Resultado central: el whack-a-mole desapareció

**11 de 14 viñetas (78%) conservadas VERBATIM; las 3 modificadas son
exactamente las 3 apuntadas por la guidance; cero regresiones introducidas.**
Contraste directo con Fase D sin modo revisión (v4→v5→v6): cada revisión
corregía lo pedido y rompía algo previamente correcto. La causa
arquitectónica (regenerar desde cero sin el texto anterior) está corregida.
Cambio no pedido único: `### Limitaciones` → `## Limitaciones` (conformidad
con el contrato de formato — aceptable).

## Cumplimiento de las instrucciones (capa modelo, no arquitectura)

1. Overclaim [E: runs]: **corregido** ("resultado PASS con operador
   identificado y timestamp" — pasó de unsupported a anclado); la separación
   de la negación en viñeta [SE] propia **no se aplicó**.
2. RC: reconoció el deployment ("aprobado y desplegado") pero **mantuvo** el
   término inventado "Relevo candidato" y una negación residual "en el flujo
   OOS".
3. Perfil OOS: corrigió la claim [E: agents] ("qa_oos_profile es el perfil
   específico") pero **dejó intacta** la viñeta [SE] compañera que afirma lo
   contrario — contradicción interna en v08.

Cumplimiento ≈ parcial (cada punto a medias), pero **sin daño colateral**:
las fallas restantes son de capacidad del 7B (limitación declarada en el
cierre de Fase D y en el gate), no del mecanismo. Con GPU/modelo mayor se
reevalúa (disparador escrito en el gate).

## Hallazgo UX (no bloqueante, candidato a W7 Fase C)

`promptAgentProposal` descarta la solicitud EN SILENCIO si el diálogo de
nombre vuelve vacío (window.prompt cancelado o suprimido por el navegador).
Dos intentos reales de Cesar se perdieron sin feedback ni log. Mejora
candidata: toast "solicitud cancelada" + considerar reemplazar window.prompt
por un form inline (los prompts nativos son suprimibles por el navegador).

## Veredicto de Fase 0

- **Pieza A (modo revisión) VALIDADA EN VIVO**: edición localizada,
  determinista (temp 0.0), ledger y modo auditados, sin regresiones.
- **Verificador v2 en vivo**: precisión correcta (0 falsos positivos en 2
  corridas con negaciones legítimas presentes).
- Latencia revisión ≈ latencia draft (~9 min): sin costo extra apreciable.
- **GO para Fase A de W7** (diseño del análisis de casos) con una
  calibración: las guidances a 7B deben ser 1 acción por instrucción y pedir
  eliminación explícita de viñetas compañeras ([E:] y [SE] van en pares).

## Decisión humana y cierre

v08 **rechazada por Cesar** (2026-07-07T19:50:14Z, evento auditado
`dossier_agent_proposal_decision` entry_id
`ff0a40da-631a-42a0-ba63-aa70ed3675bc`). Motivo: calidad residual del 7B —
contradicción interna (viñeta [SE] afirma que falta perfil OOS tras corregir
la [E: agents]), término inventado "Relevo candidato" y negación residual
sobre el RC. El doc vuelve a `needs_human_review` y sigue sin aprobar (flujo
W6.2 intacto). Fase 0 queda **CERRADA**.

## Limitaciones abiertas de Fase 0

1. **Verificador v2 — falso negativo**: no detectó la contradicción residual
   entre la viñeta [SE] ("falta perfil OOS") y la [E: agents] corregida
   ("qa_oos_profile es el perfil específico") en v08; la identificó Cesar
   manualmente. El verificador contrasta negaciones contra evidencia
   operacional, no detecta contradicciones internas entre viñetas de la
   misma propuesta. Candidato a regla nueva (intra-proposal contradiction).
2. **Flujo UI — solicitud descartada sin feedback ni POST**:
   `promptAgentProposal` descarta la solicitud en silencio cuando el diálogo
   de nombre vuelve vacío; no emite el POST ni deja rastro (detalle en
   Hallazgo UX). Los POSTs de esta corrida se lanzaron desde servidor bajo
   autorización explícita de Cesar. Candidato a W7 Fase C.
