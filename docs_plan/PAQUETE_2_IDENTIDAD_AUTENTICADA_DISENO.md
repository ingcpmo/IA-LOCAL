# PAQUETE 2 — Identidad autenticada real (hallazgo M) — DISEÑO, sin implementar

Fecha: 2026-08-18. Solicitado por Cesar: "empieza con el paquete 2 —
identidad autenticada". Cesar pidió explícitamente **solo diseño, no
implementación** hasta su aprobación.

## Problema exacto (confirmado en código, no supuesto)

`factory-api` tiene **una sola** credencial: `FACTORY_API_KEY`
(`factory/api/main.py:28-38`, `verify_api_key` línea 138-140), comparada
por igualdad de string contra el header `X-API-Key`. No distingue quién,
entre todos los que conocen esa key, hace una llamada — solo si la conoce.

Sobre esa base, **15+ endpoints** (`factory/api/routes/layer9.py`,
`factory/api/routes/remediation_packages.py`) aceptan la identidad de
quien decide como **campo de texto libre en el body**, puesto por el
propio cliente:

| Endpoint | Campo | Línea |
|---|---|---|
| `POST /missions/{id}/approve` | `approved_by` | layer9.py:81 |
| `POST .../decisions` (DecisionCreate) | `decided_by` | layer9.py:98 |
| `POST .../risks/accept` | `accepted_by` (default `"human"`) | layer9.py:108 |
| `ReviewDecision` (aprobación RC) | `approved_by` | layer9.py:113 |
| `ReviewReturn` | `approved_by` | layer9.py:118 |
| `FindingReviewDecision` | `reviewer` | layer9.py:129 |
| `MissionReturn` | `returned_by` | layer9.py:136 |
| `MissionReject` | `rejected_by` | layer9.py:141 |
| dossier approve | `approved_by` | layer9.py:1125 |
| decisión sobre finding/case | `decided_by` (x2) | layer9.py:1174, 1212 |
| `W5DecisionBody` | `approved_by` | layer9.py:1370 |
| `GovernanceConfirmBody` | `approved_by_id`/`approved_by_display_name` | layer9.py:1484-1485 |
| `GovernanceRejectBody` | `rejected_by_id`/`...display_name` | layer9.py:1502-1503 |
| `GovernanceReturnBody` | `returned_by_id`/`...display_name` | layer9.py:1509-1510 |
| `ArtifactVersionSignBody` | `approved_by_id`/`...display_name` | layer9.py:1695-1696 |
| remediation package decision | `decided_by` | remediation_packages.py:75 |

`identity_policy.validate_identity()` (`core/identity_policy.py`) ya
rechaza nombres genéricos/reservados/vacíos (`"human"`, `"admin"`, etc.)
en el camino de gobernanza V2 (`governance_service.py:784,988`), pero eso
**no es autenticación** — solo filtra la forma del string. Cualquiera con
la única key compartida puede escribir `"Cesar"` en `approved_by_id` y el
sistema lo acepta como si Cesar realmente hubiera firmado.

Esto es exactamente el hallazgo M de
`EVALUACION_FINAL_ANALIZADOR_GMP_Y_PLAN_CIERRE.md` (línea 290): *"Atar
`decided_by` a una identidad autenticada real (login/token) en vez de
string libre, antes de cualquier uso en producción real con consecuencias
regulatorias."*

## Qué NO es este paquete

- No es login con usuario/password + sesión (Cesar descartó esa opción
  para este paquete — mucho mayor alcance, proyecto aparte).
- No reemplaza `FACTORY_API_KEY` como puerta de entrada general a la API
  — esa key sigue protegiendo lectura/operación normal.
- No implica IA firmando nada — la IA sigue sin poder ser
  `decision_origin=human_confirmed` en ningún camino (ya garantizado por
  `identity_policy` + `governance_service._closing_record`).

## Arquitectura propuesta

### 1. Registro de identidades por persona (`factory/core/identity_registry.py`)

Un archivo de config **fuera de git** (mismo patrón que `.env` /
`FACTORY_API_KEY`), p.ej. `factory/config/identity_keys.yaml`
(gitignored), con una entrada por persona autorizada a firmar decisiones:

```yaml
# NO versionar. Cada key es un secreto individual, generado una vez con
# `openssl rand -hex 32` y entregado fuera de banda a esa persona.
identities:
  - name: "Cesar"
    key_sha256: "<hash de la key real, nunca la key en claro>"
  - name: "QA_Reviewer_1"
    key_sha256: "..."
```

- Se carga una sola vez al arrancar, igual que `FACTORY_API_KEY` (fail-closed:
  si el archivo no existe o está vacío, el servicio arranca igual pero
  **ningún endpoint de gobernanza queda disponible** hasta que se
  provisione al menos una identidad — no se relaja el M0 existente sobre
  `FACTORY_API_KEY`).
- Comparación por hash (`sha256(key) in {registradas}`), nunca por string
  en claro guardado en memoria más tiempo del necesario.
- Nueva dependencia FastAPI `resolve_identity(x_identity_key: str =
  Header(default=""))` — devuelve el `name` real o lanza `401`. Vive junto
  a `verify_api_key` en `main.py`, pero es una segunda cabecera
  (`X-Identity-Key`), **no reemplaza** `X-API-Key`: las dos se exigen para
  un endpoint de gobernanza (acceso a la API + identidad de quien firma).

### 2. Migración de los endpoints de la tabla de arriba

Patrón único para los 15 puntos: el campo de identidad (`approved_by`,
`decided_by`, `reviewer`, `*_by_id`, etc.) **deja de venir del body** —
se inyecta vía `Depends(resolve_identity)` y el handler lo pasa al
servicio en vez del campo del `BaseModel`. Los campos `*_display_name`
(donde existen, p.ej. `GovernanceConfirmBody`) se mantienen como
cosmético opcional, no como identidad.

Esto es un **cambio de contrato de API que rompe a los llamadores
actuales** de esos 15 endpoints (dejan de poder mandar `approved_by` en
el body; deben mandar `X-Identity-Key`). Aceptable solo si Cesar lo
autoriza explícitamente, y solo tiene sentido si primero existen personas
reales provisionadas en el registro (paso 1).

### 3. UI (`factory/ui/mission_control.html`)

Ya pide la API key en sesión y la guarda solo en memoria (nunca
`localStorage`, confirmado en el comentario de cabecera del archivo). El
mismo patrón se extiende: un segundo campo de sesión para "tu identity
key personal", enviado como `X-Identity-Key` en las llamadas de
gobernanza. Cambio de UI, no de arquitectura — el archivo ya está
preparado para este patrón.

### 4. Alcance de esta primera iteración: solo el registro de decisiones

Se propone limitar el Paquete 2 al camino de **decisiones de gobernanza**
(los 15 endpoints listados) y dejar fuera explícitamente:
- `runtime_identity.py` (identidad del *código*, no de personas — no
  relacionado).
- Autenticación general de lectura de la API (sigue siendo
  `FACTORY_API_KEY`).

## Archivos a tocar (si Cesar aprueba implementar)

```
NUEVO   factory/core/identity_registry.py         (+ tests)
NUEVO   factory/config/identity_keys.yaml.example  (plantilla, sin secretos reales)
        .gitignore                                 (+ factory/config/identity_keys.yaml)
MOD     factory/api/main.py                         (dependencia resolve_identity)
MOD     factory/api/routes/layer9.py                (10 endpoints, quitar campo de identidad del body)
MOD     factory/api/routes/remediation_packages.py  (1 endpoint)
MOD     factory/services/governance_service.py      (propose/confirm/reject/return ya
                                                       separan by_id/by_name -- by_id pasa
                                                       a venir del caller inyectado, no del
                                                       body -- sin cambio de firma interna)
MOD     factory/ui/mission_control.html             (campo de sesión para identity key)
MOD     tests correspondientes a cada endpoint tocado
```

## Preguntas abiertas para Cesar antes de implementar

1. **¿Provisionar quién primero?** Se necesita al menos una identidad real
   en el registro antes de que cualquier endpoint de gobernanza funcione
   — ¿Cesar es la única persona por ahora, o hay más (QA)?
2. **¿Ruptura de contrato aceptable ya?** Los 15 endpoints dejan de
   aceptar el campo de identidad en el body. ¿Se acepta romper eso ahora,
   o se prefiere una fase de transición donde el campo del body deba
   *coincidir* con la identidad resuelta de la key (sin romper, solo
   verificar) antes de eliminarlo del todo?
3. **¿Fuera de alcance confirmado?** ¿Login/password queda descartado
   también a futuro, o es un paquete aparte pendiente para más adelante?

## Siguiente paso

Este documento es solo diseño — `CODE_CHANGED = 0`. Pendiente de
aprobación explícita de Cesar sobre las 3 preguntas antes de escribir una
sola línea de implementación.
