# PAQUETE 4 — UI y vocabulario (hallazgos E + K) — DISEÑO, sin implementar

Fecha: 2026-08-19. Investigación de código previa (solo lectura).
`CODE_CHANGED = 0` en este documento.

## Alcance exacto (`VERIFICACION_ACOTADA_Y_PAQUETES_CIERRE.md`, PAQUETE 4)

1. Completar la superficie de UI de remediación a todos los paquetes.
2. Unificar vocabulario de clasificación (`conclusion`/`bucket`/`status`)
   en un glosario.
3. Obtener el clic real de validación de Cesar en producción.

## Hallazgo E — vocabulario: 3-4 taxonomías sin Enum formal

Confirmado en código, sin glosario previo (no existe ningún artefacto
canónico hoy — se parte de cero):

| Taxonomía | Dueño canónico | Valores |
|---|---|---|
| `conclusion` | `chunked_engine.py` (verificador ABCD) | `DOCUMENTATION_GAP`, `PROVISIONAL_GAP`, `EVALUATION_INCOMPLETE`, `SUPPORTING_EVIDENCE_UNDER_REVIEW`, `EVIDENCE_NOT_LOCATED_IN_CANDIDATES`, `DOCUMENTED_AND_SUPPORTED`, `PARTIALLY_DOCUMENTED`, `PROVISIONALLY_DOCUMENTED`, `PROVISIONALLY_PARTIALLY_DOCUMENTED`, `NOT_APPLICABLE`, `CROSS_REFERENCE_MISSING`, `NOT_OBSERVED_OPTIONAL` |
| `bucket` | `tier1_report.py` — renombra `conclusion` a una taxonomía más gruesa vía `_bucket_for_conclusion()` | `CONFIRMED`, `NEEDS_HUMAN_REVIEW`, `NOT_APPLICABLE`, `CROSS_REFERENCE`, `OPTIONAL_NOT_OBSERVED` |
| `status` (RC / review queue) | `human_review_queue.py` | `pending`, `approved`, `rejected`, `returned`, `superseded` |
| `status` (decisión v2) | `decision_store_v2.py` | valor libre del caller; `decision_origin` (`human_confirmed`/`agent_proposed`) es un campo aparte |
| `status` (paquete de remediación) | `remediation_package_service.py`, consumido en `remediation.js` | p.ej. `AWAITING_PACKAGE_DECISION` |

**El defecto real**: el mismo campo `status` nombra 3 conceptos distintos
sin prefijo que los distinga, y `conclusion`→`bucket` es el mismo
concepto de clasificación bajo dos nombres en dos módulos, con un mapeo
muchos-a-uno explícito.

**Ejecutable directo, sin más decisiones de Cesar**: escribir el glosario
canónico (`docs_plan/GLOSARIO_VOCABULARIO_CLASIFICACION.md` o similar),
documentando cada taxonomía, su dueño, sus valores, y la relación
`conclusion`→`bucket`. **Sin tocar código** — el propio hallazgo E lo
pide así ("no cambiar comportamiento, solo consolidar nombres").
Formalizar `conclusion` como Enum es explícitamente OPCIONAL en el
hallazgo original — lo dejo fuera salvo que Cesar lo pida, porque tocar
tipos reales en `chunked_engine.py` es right cambio de comportamiento
potencial, no solo documentación.

## Hallazgo K — superficie de UI + clic real: 3 partes con riesgo y alcance muy distintos

### K1 — REGRESIÓN REAL introducida por Paquete 2: la UI viva ya no puede completar el flujo de decisión

`factory/ui/mission_control.html` (con `factory/ui/js/mission_control/`)
es la UI real y desplegada — servida en `/` y `/mission-control` por
`factory/api/main.py:166-219`. `factory/ui/index.html` es un prototipo
más viejo, NO wireado a ninguna ruta de `main.py` (solo alcanzable por
accidente vía el montaje estático `/ui`) — no es el punto de entrada real.

El Paquete 2 (`9f07d95`) migró 18 endpoints, incluido
`POST .../remediation-packages/.../decision`, a exigir
`X-Identity-Key` resuelta server-side, quitando `decided_by` del body.
**Nadie actualizó la UI viva**: `factory/ui/js/mission_control/state.js:14`
(`headers()`) solo manda `x-api-key`, nunca `X-Identity-Key`;
`remediation.js:262-277` (`submitPackageDecision()`) sigue juntando
`decided_by` de un `<input>` y mandándolo en el body (que el backend
ahora ignora en silencio). **Resultado real: si Cesar hoy clickea
"Registrar decisión final" en producción, la petición falla con 401**
antes de que el campo `decided_by` del body llegue a importar.

Esto bloquea directamente la parte 3 del paquete ("obtener el clic real
de Cesar") — no puede haber clic real exitoso mientras esto no se
arregle. **Prioridad alta, causada por mi propio cambio anterior.**

Fix acotado y de bajo riesgo (mismo patrón que la API key ya usa en
`mission_control.html`, sesión en memoria, sin `localStorage`):
- `state.js`: agregar un segundo campo de sesión para la identity key,
  mandar `X-Identity-Key` en `headers()`.
- `remediation.js::submitPackageDecision()`: quitar `decided_by` del
  body (ya no lo acepta el backend) — el nombre de quien decide ya no lo
  escribe el humano en un `<input>`, lo resuelve el servidor desde la
  key.
- Mismo chequeo para cualquier otro flujo de `mission_control.html` que
  llame a un endpoint migrado en Paquete 2 (aprobación de misión,
  gobernanza D1-D5, etc. — auditar `remediation.js`/`main.js`/otros
  módulos de `js/mission_control/` completos, no solo el panel de
  remediación).

### K2 — "cubre solo un paquete": falta un endpoint de listado

El propio código lo declara (`remediation.js:1-12`): "adjudicación de UN
paquete por vez, buscado a mano por (project_id, package_id, version) --
no existe endpoint de listado de paquetes todavía." Completar esto
requiere: (a) un endpoint nuevo `GET /api/v1/remediation-packages/{project_id}`
o similar que liste paquetes reales (backend nuevo, no solo UI), y (b) un
panel de UI que use ese listado en vez de la búsqueda manual. Alcance
backend + UI real, no un simple parche.

### K3 — el clic real de Cesar en producción

No es código — es una acción humana pendiente desde R3-T1
(`docs_plan/R3_T1_6_FIX_B4_Y_CIERRE.md:130`,
`docs_plan/R3_T1_7_SUPERFICIE_UNICA_CANDIDATO.md:836,859`). Yo no puedo
ejecutarlo. Lo único que puedo hacer es asegurar que, cuando Cesar lo
intente, funcione (K1) — y ampliar qué puede validar (K2).

## Preguntas para Cesar

1. **¿Autorizás K1 ahora?** Es un fix acotado, causado por mi propio
   cambio de Paquete 2, necesario para que cualquier clic real en
   producción no falle con 401. Recomiendo ejecutarlo ya, con la misma
   urgencia que J tuvo en su momento.
2. **¿K2 (endpoint de listado + panel) en esta iteración, o se difiere?**
   Es backend + UI real, más grande que K1.
3. **E (glosario)**: ¿lo ejecuto ya (solo documentación, sin riesgo), o
   preferís esperar a que K2 defina si vale la pena formalizar `conclusion`
   como Enum al mismo tiempo?

## Lo que SÍ puedo ejecutar sin más decisiones

- **E** (glosario): sin ambigüedad, cero riesgo, solo documentación.
- **K1** (fix de la regresión de identidad en la UI viva): acotado, sin
  ambigüedad de diseño — mismo patrón que la API key ya usa.
