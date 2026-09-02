# DISEÑO E INSTRUCCIONES — CAPA LLM DE INTERPRETACIÓN SOBRE FINDINGS DETERMINISTAS · v1.1

> **Origen:** entregado por la mesa de diseño (Claude Web), pegado por Cesar en la sesión del
> 2026-09-02. Este fichero lo **congela verbatim** como fuente autoritativa del arco SHADOW
> (fases G0–G5). Cualquier revisión futura crea `v1.2`, no edita este fichero.
> Copia de trabajo bajo `docs_plan/shadow_llm/` en la rama `shadow/llm-interpretation-layer`.

---

**Fecha:** 2026-09-02 · **Autoridad:** Capa 9 = Cesar · **Rama:** `fix/clon-local-validacion`
**Baseline:** `reconc-acceptance-v1` → `0e1e88a` (código `reconc-arc-closure` → `56bd36a`).
**Cambios v1.0→v1.1:** incorpora las 6 correcciones del auditor externo (§CHANGELOG). **No cambia los
cuatro expertos, ni L0–L5, ni el orden G0–G5, ni pide rediseño.** Ajustes de consistencia.

---

## 0 · RESOLUCIÓN DE LAS 6 CORRECCIONES DEL AUDITOR

Las seis son válidas. Cinco se aceptan tal cual; la 6 se acepta en su principio con un matiz de
seguridad que se explica abajo.

| # | Corrección | Veredicto | Cómo se resuelve |
|---|---|---|---|
| 1 | Cross-domain no es un 5º bucket (285+98+17+15+57=472≠457) | **ACEPTADA** — error real | Routing primario exclusivo de 457; cross-domain = **flag secundario** sobre 15 relaciones |
| 2 | No escribir `related_finding_ids` dentro de L2 | **ACEPTADA** — contradecía mi propio principio | Las relaciones viven en `shadow/cross_domain_links.json`, nunca en el `Finding` |
| 3 | No atribuir 342 `INCONCLUSIVE` al 7B | **ACEPTADA** — precisión factual | Se separa el hecho (Tier-1 determinista) del riesgo (techo histórico del 7B) |
| 4 | No congelar el 7B como modelo arquitectónico | **ACEPTADA** | Se congela `ModelProvider` como abstracción; el modelo es configurable/versionado |
| 5 | `evaluate_bundle` solo si compatible con el contrato de interpretación | **ACEPTADA** | Reutilización **selectiva** de piezas, no imposición del pipeline de adjudicación |
| 6 | No bloquear Internet globalmente; separar egress de datos de cliente | **ACEPTADA con matiz** | Modelo de red de 3 canales; `CRIT-E` reformulado. **Pero en G0–G5 no se habilita retrieval externo: se diseña el mecanismo, no se abre la red** (ver §6) |

---

## 1 · ARQUITECTURA (L0–L5 sin cambios — el auditor la valida como "muy sólida")

```
L0  PDF ORIGINAL                     inmutable
L1  EVIDENCIA EXTRAÍDA (canonical)    inmutable · hash lógico gobernado
L2  FINDING DETERMINISTA              inmutable · class/subtype/risk/requirement_id/machine_state/
                                                  human_state/evidencia/related_finding_ids
─────────────────────────────────────────────────────────────────────────  ← FRONTERA DURA
L3  OPINIÓN DEL AGENTE EXPERTO (LLM)  aditiva · shadow/*, nunca toca L2
L4  REDACCIÓN DEL COMPOSER (LLM)      aditiva · narrativa marcada [SHADOW / NO GOBERNADO]
L5  DECISIÓN HUMANA                   única autoridad que cambia human_state
```

**Precisión de v1.1 (corrección 2):** `related_finding_ids` es un campo de L2, y aunque hoy está vacío,
**la capa LLM no lo escribe.** Cualquier relación que descubra o use la capa shadow (incluidos los
enlaces cross-domain) vive en `shadow/cross_domain_links.json`. L2 permanece intacto por construcción,
no por buena voluntad.

Además de la separación L0/L1/L2 vs L3/L4, la narrativa distingue **dos fuentes** (corrección 6):
```
CLIENT_EVIDENCE          RW-0006 pág.45 · hash=…            (del corpus, confidencial)
EXTERNAL_REG_REFERENCE   21 CFR §11.10(e) · fuente · hash · retrieved_at   (pública, contextual)
```
La referencia regulatoria externa **contextualiza**; nunca se convierte en evidencia de que el
documento del cliente cumple.

---

## 2 · AGENTES (sin cambios de roles — el auditor los valida)

Cuatro expertos + composer + dos verificadores deterministas. El routing primario y el volumen se
corrigen (corrección 1):

```
ROUTING PRIMARIO (exclusivo, suma exacta 457):
  REGULATORY        285   (REGULATORY_INCONCLUSIVE → triage de ≤5 candidatos, NO juicio)
  FUNCTIONAL/TRACE   98   (70 NOT_TESTED + 20 IMPL_WITHOUT_REQ + 8 ORPHAN_DESIGN)
  TECHNICAL          17   (reglas de completitud gobernadas)
  HUMAN_ONLY         57   (RW-0009 NOT_ANALYZABLE → NUNCA al LLM)
  ─────────────────────
  TOTAL             457

ATRIBUTO SECUNDARIO (no es un bucket, es un flag sobre findings ya ruteados):
  CROSS_DOMAIN_REQUIRED = YES  para 15 relaciones (gap técnico + INCONCLUSIVE regulatorio
                               sobre la misma regla y el mismo documento)
```

Cada finding tiene **un** experto primario y, opcionalmente, `cross_domain_flag=YES`. El Cross-domain
Reviewer no "posee" 15 findings: procesa las 15 **relaciones** después de que sus findings pasaron por
su experto primario.

El modelo que ejecuta los agentes es intercambiable (corrección 4):
```
Expert role (contrato + prompt + contexto + verificador)
      ↓
ModelProvider  ← ABSTRACCIÓN CONGELADA
      ↓
modelo configurable/versionado   (el 7B actual = primer candidato de piloto, NO el modelo definitivo)
```
La capacidad del agente la define su contrato, prompt, contexto y verificador — **no** un modelo
específico. Esto mantiene el sistema sostenible y no cierra la puerta a un modelo mayor si un futuro
`MODEL_QUALIFICATION` lo aprueba.

Contratos de entrada/salida: sin cambios respecto de v1.0 (paquete acotado y trazable; salida con
`assessment` ∈ enum y bloque `MUST_NOT_CHANGE`).

---

## 3 · FLUJO (v1.1)

```
1. run_v2_pipeline → 457 findings L2 + report_v2 factual                          [SIN CAMBIOS]
2. ROUTER determinista: routing primario exclusivo (457) + marca cross_domain_flag en 15
   - HUMAN_ONLY (57) excluido del LLM, va al reporte como "requiere humano"
3. paquete de entrada por finding, desde artefactos existentes
4. Expert LLM (primario) → shadow/expert_<agent>.json
5. VERIFICADOR DETERMINISTA fail-closed: cita anclada existe en L1/L2, MUST_NOT_CHANGE intacto,
   assessment ∈ enum → lo que no verifica = SHADOW_REJECTED, no entra al reporte
6. Cross-domain Reviewer procesa las 15 relaciones + DISAGREEMENT → shadow/cross_domain_links.json
   (conserva ambas opiniones; persistente → HUMAN_REVIEW_REQUIRED)   [NUNCA escribe en L2]
7. REPORT COMPOSER (LLM): narrativa por documento × regulación, cada afirmación anclada a
   finding_record_id, narrativa LLM marcada [SHADOW], CLIENT_EVIDENCE vs EXTERNAL_REG_REFERENCE separadas
8. VERIFICADOR DETERMINISTA del reporte: cobertura 457/457, 0 afirmaciones sin finding, cabecera GxP
9. borrador → REVISOR HUMANO (L5). 0 cambios de human_state en todo el flujo.
```

Artefactos nuevos bajo `<run_dir>/shadow/`: `expert_{regulatory,functional,technical}.json`,
`cross_domain_links.json`, `shadow_audit.json`, `informe_narrativo_v2.md`. **Ninguno toca
`*_findings.json`, `final_report_v2.json` ni el `FINDINGS_FINGERPRINT`.**

---

## 4 · PLAN POR FASES (orden sin cambios; el auditor lo valida)

`G0 → G1 → G2 → G3 → (gate + PILOT firmada) → G4a Technical → G4b Cross-domain → G4c Functional →
G4d Regulatory-triage → G4e Composer → G5`. G0–G3 sin LLM.

Cambios v1.1 por fase:

- **G0** — se etiqueta explícitamente **CONSOLIDACIÓN/FORMALIZACIÓN** de la baseline, **no** un
  re-análisis del corpus (corrección del auditor: "G0 es formalización, no nueva caracterización"). La
  caracterización ya existe en el diagnóstico; G0 la consolida.
- **G1** — el router produce **routing primario exclusivo (457)** + `cross_domain_flag` sobre 15. El
  test de aceptación cambia: `285+98+17+57=457` y **15 flags secundarios**, no un reparto de 472.
- **G3** — el enlace cross-domain se materializa en `shadow/cross_domain_links.json`, **no** en
  `related_finding_ids` del `Finding` (corrección 2). El post-pass que los detecta es determinista y
  escribe solo en shadow.
- **G4** — la reutilización de `v2_judgment` es **selectiva** (corrección 5): se evalúa qué piezas
  cumplen el contrato de *interpretación* (probablemente `ModelProvider`, generación controlada,
  infraestructura de prompts, verificación de evidencia, parseo de respuesta) y se descarta lo que
  imponga semántica de *adjudicación* incompatible. El diseño gobierna el código, no al revés.

---

## 5 · CORRECCIÓN 3 — REDACCIÓN PRECISA SOBRE EL RECALL

Documentalmente, en todo el diseño y en G0, se usa esta formulación exacta y se prohíbe la anterior:

```
HECHO (de la corrida diag-corpus-20260902):
  Los 342 REGULATORY_INCONCLUSIVE los produjo el MOTOR DETERMINISTA Tier-1 (Palanca C).
  En esa corrida: LLM_CALLS = 0, MODEL = null, PROVIDER = null.
  Tier-1 no encontró eco léxico anclado en 6 docs × 12 requisitos → todos INCONCLUSIVE.

RIESGO (de experimentos previos, NO de esta corrida):
  El juicio semántico del 7B sobre paráfrasis tiene techo medido (1–2/7; 4/7 confirmado por
  experimento directo; R2 CERRADO sin alcanzar el gate ≥6/7).

Ambos respaldan precaución. NO se afirma que "el 7B produjo recall 0 en esta corrida": el 7B no se
ejecutó. La precaución sobre el bloque regulatorio (triage, no juicio) se sostiene en el RIESGO
histórico, no en atribuir al 7B un resultado de una corrida determinista.
```

---

## 6 · CORRECCIÓN 6 — MODELO DE RED (con el matiz de seguridad)

El auditor tiene razón en el principio: **el objetivo no es "0 conexiones externas" sino "0 egress no
autorizado de datos del cliente".** Un sistema GMP puede legítimamente necesitar consultar fuentes
regulatorias públicas (eCFR, FDA, EMA…). Acepto la distinción y el modelo de tres canales:

```
1. LOCAL MODEL ACCESS            127.0.0.1 / Ollama            PERMITIDO
2. PUBLIC REGULATORY WEB ACCESS  eCFR/FDA/EMA/PIC-S/ICH/WHO    PERMITIDO Y GOBERNADO (a diseñar)
3. CLIENT DATA EGRESS            PDF/claims/evidencia/finding  PROHIBIDO salvo autorización específica
```

**El matiz de seguridad que añado (y que el auditor subestima):** *permitir en la arquitectura* ≠
*abrir la red ahora*. Para la capa shadow G0–G5 **no se necesita** retrieval regulatorio externo — los
expertos interpretan findings sobre evidencia ya extraída. Por tanto:

```
EN G0–G5:
  - NO se habilita el canal 2 (retrieval regulatorio externo). Se DISEÑA el mecanismo gobernado
    (Regulatory Retrieval Gateway) como especificación, no se implementa ni se activa.
  - El canal 1 (Ollama local) es el único tráfico saliente real, y solo en G4+.
  - Abrir el canal 2 en la primera versión shadow amplía la superficie de ataque sin beneficio
    para el objetivo de estas fases. Se difiere a una mesa de diseño propia (post-G5).

Especificación del Regulatory Retrieval Gateway (diseño, no implementación en estas fases):
  Expert → ¿necesita referencia externa? → SÍ → Gateway → fuente pública autorizada →
  documento público cacheado + hash + URL + timestamp → Expert
  El Gateway envía SOLO términos ("21 CFR 11.10(e)", "FDA audit trail guidance"), NUNCA contenido
  del cliente. Toda consulta auditada: destino, timestamp, propósito, clasificación, hash de respuesta.
  Sin allowlist rígida congelada aún; governance decide las fuentes permitidas más adelante.
```

Reformulación de `CRIT-E` (antes `document_egress_bytes == 0`, demasiado amplio):

```
CRIT-E1  UNAUTHORIZED_CLIENT_DATA_EGRESS = 0
         (0 bytes de PDF/canonical/evidencia/finding/graph/identificadores de cliente salen del host
          sin autorización específica — esto es innegociable en TODAS las fases)
CRIT-E2  Toda consulta externa auditada: destino · timestamp · propósito · clasificación · response_hash
CRIT-E3  Ningún contenido documental del cliente sale a Internet sin autorización explícita
CRIT-E4  (G0–G5) LLM_PROVIDER = LOCAL ; el canal regulatorio externo NO está habilitado en estas fases
```

En G0–G3, además, `LLM_CALLS = 0` y no hay razón para tráfico externo — pero **no se exige bloquear la
red del servidor**, solo que estas fases no la usen. La diferencia con v1.0 es real: v1.0 hacía de
`egress_bytes==0` una condición de PASS que habría impedido cualquier acceso regulatorio futuro; v1.1
protege lo que importa (datos del cliente) sin cerrar la arquitectura.

---

## 7 · INSTRUCCIONES PARA CLAUDE CODE (v1.1)

```
RÉGIMEN — igual que v1.0: una fase G, estado congelado (tag shadow-G<n>), gate humano, reporte por fase.
  G0..G3 SIN LLM. G4 requiere PILOT_EXECUTION vigente firmada; no proponer nueva si hay vigente.

INVARIANTES (toda fase)
- No mutar class/subtype/severity/risk/requirement_id/machine_state/human_state ni related_finding_ids
  de ningún Finding. human_state solo por set_human_state(reviewer=<humano real>).
- No mover INPUT_CONFIG / GRAPH_SNAPSHOT / FINDINGS fingerprint. findings == 235f724a… al cerrar.
- Relaciones cross-domain SOLO en shadow/cross_domain_links.json. NUNCA en el objeto Finding. (corr. 2)
- Toda salida LLM en <run_dir>/shadow/. Verificador determinista fail-closed antes del reporte.
- UNAUTHORIZED_CLIENT_DATA_EGRESS = 0 en TODAS las fases. En G0–G5, LLM_PROVIDER=LOCAL y canal
  regulatorio externo NO habilitado (solo se diseña el Gateway). (corr. 6)
- No declarar cumplimiento, no aprobar, no cerrar CAPA, no liberar lote, no convertir INCONCLUSIVE/
  NOT_ANALYZABLE en observed. Los 57 HUMAN_ONLY nunca al LLM.

ROUTING (corr. 1)
- Primario exclusivo: REGULATORY 285 · FUNCTIONAL 98 · TECHNICAL 17 · HUMAN_ONLY 57 = 457.
- cross_domain_flag = YES sobre 15 relaciones. NO es un quinto bucket. NO sumar 472.

MODELO (corr. 4)
- Congelar ModelProvider como abstracción. El 7B es el primer candidato de piloto, configurable/
  versionado. La capacidad del agente = contrato+prompt+contexto+verificador, no el modelo.

REUTILIZACIÓN (corr. 5)
- Evaluar qué piezas de v2_judgment cumplen el contrato de INTERPRETACIÓN (probables: ModelProvider,
  generación controlada, infra de prompts, evidence_verifier, parseo). NO imponer el pipeline
  hunter/critic/adjudicator si aporta semántica de adjudicación incompatible. El diseño gobierna.

REDACCIÓN (corr. 3)
- En G0 y en todo doc: los 342 INCONCLUSIVE son de Tier-1 DETERMINISTA (LLM_CALLS=0 en esa corrida).
  La precaución regulatoria se apoya en el techo HISTÓRICO del 7B, no en atribuirle esa corrida.

NO HACER
- No 2º motor. No re-extraer. No re-juzgar en el composer. No abrir el canal regulatorio externo en G0–G5.
- No arreglar bug de IDs, tests stale ni RW-0009. No R2, no PILOT-035, no producción.
```

Formato de reporte por fase (v1.1):
```
FASE · PRE/POST_COMMIT · WORKTREE · DIFF (prohibidos=VACÍO) · COMMANDS · TEST_RESULTS (real) ·
INPUT/OUTPUT_HASHES · FINGERPRINTS (findings==235f724a…) · LLM_CALLS (0 en G0..G3) ·
CLIENT_DATA_EGRESS (0) · LLM_PROVIDER (LOCAL) · ARTIFACTS · GOVERNANCE_EVENTS (solo servicio) ·
HUMAN_STATE_CHANGES (0) · L2_MUTATIONS (0) · DEVIATIONS · EXPECTED_VS_ACTUAL · PROPOSED_VERDICT
```

---

## CHANGELOG v1.0 → v1.1

```
1  Cross-domain = flag secundario sobre 15 relaciones; routing primario exclusivo suma 457 (no 472).
2  related_finding_ids NO se escribe en L2; enlaces cross-domain en shadow/cross_domain_links.json.
3  342 INCONCLUSIVE atribuidos a Tier-1 determinista (LLM_CALLS=0); techo del 7B = riesgo histórico aparte.
4  ModelProvider congelado como abstracción; el 7B es candidato de piloto, no modelo arquitectónico.
5  Reutilización selectiva de v2_judgment por compatibilidad con el contrato de interpretación.
6  Modelo de red de 3 canales; CRIT-E → CRIT-E1..E4 (client-data egress 0, no "0 conexiones"); el canal
   regulatorio externo se DISEÑA (Gateway) pero NO se habilita en G0–G5.
```

*Diseño v1.1 para ejecución fase a fase con auditoría independiente. Sin implementación, sin LLM, sin
PILOT nuevo, sin mover el fingerprint, sin tocar L0/L1/L2, sin abrir el canal regulatorio externo. La
decisión final es humana.*
