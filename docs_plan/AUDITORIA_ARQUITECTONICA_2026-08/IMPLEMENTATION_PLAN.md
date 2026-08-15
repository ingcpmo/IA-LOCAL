# F. Plan de implementación

**Estado**: propuesta, condicionada en su totalidad a aprobación
explícita de Cesar. `CODE_CHANGED = 0` en esta auditoría.
`PRODUCTION_ENABLEMENT` sigue `BLOCKED`. Ninguna fase empieza sin
confirmación separada, punto por punto, siguiendo el mismo protocolo ya
usado en todo el roadmap W5 V2.

## Orden propuesto (secuencia de menor a mayor riesgo/costo)

### Fase 0 — Correcciones baratas, sin LLM (Pista A)

1. Corregir la asimetría furniture LLM/verificador
   (`INFORMATION_LOSS_ANALYSIS.md`): aplicar `_PAGE_FURNITURE_RE` también
   al texto que ve el LLM, no solo en verificación. Cero llamadas LLM
   para implementar; requiere re-run de juicio solo para medir impacto
   (brazo B del `EXPERIMENT_PLAN.md`).
2. Aclarar la nomenclatura NO_SIGNAL/`DOCUMENTATION_GAP` en
   documentación viva del proyecto (no en código — el código ya está
   bien, es la documentación la que usa el nombre del brief).

### Fase 1 — Experimento C, condicionado (Pista A)

Ejecutar `EXPERIMENT_PLAN.md` en el orden de fases descrito ahí (0→1→2→3,
detenerse en cualquier punto si la evidencia ya responde la pregunta).
Requiere: `PILOT_EXECUTION` vigente seleccionada por el resolver (nunca
proponer una nueva sin verificar primero), aprobación de Cesar para
gastar hasta 2 llamadas LLM nuevas.

### Fase 2 — Table/EvidenceUnit: NO JUSTIFICADA (cerrado 2026-08-15)

**Estado anterior**: "condicionada al resultado del experimento C".
**Estado real, cerrado formalmente** (`docs_plan/
CONTINUACION_CIERRE_ESTRATEGICO.md` Bloque 1): el experimento C se
ejecutó de verdad el 2026-08-14/15 — tabla de señales I/O y cabecera de
plantilla removidas por completo, prosa relevante en contexto narrativo
limpio (1670 caracteres, ratio de señal 6.6% vs. 4.5% original),
verificado mecánicamente antes de gastar la llamada. **Resultado:
idéntico al de la corrida sin aislar** — ambos `evidencia_insuficiente`,
sin cita, mismos criterios `NOT_MET`/`NOT_ASSESSABLE`. Checkpoints
reales preservados: `chunked-8e2b20bfa511` (P4 aislado),
`chunked-510444cedc9b` (P6 aislado) — comparar contra
`chunked-5a439f3fde11`/`chunked-554544f4090f` (misma corrida sin aislar).

**Esta fase queda CANCELADA, no pausada**: la evidencia del propio
experimento la refuta. No se construye `Table`/`EvidenceUnit` — sería
invertir esfuerzo real contra el resultado ya medido. Reabrir solo si
aparece un caso futuro con una causa distinta a las ya evaluadas
(paráfrasis, confirmada refutada para representación; dilución tabular,
confirmada refutada), con su propio experimento previo.

### Fase 3 — Contrato formal prompt↔verificador (Pista B, P1)

Independiente de las fases de Pista A — puede correr en paralelo.
Formalizar `common_contract_sha256` como JSON Schema versionado + test de
contrato en Gate 0 (`CONTEXT_ENGINEERING_ARCHITECTURE.md` Componente 1).
Sin llamadas LLM. Riesgo bajo, beneficio directo sobre la clase de
defecto B3→B4→B5 ya materializada 3 veces.

### Fase 4 — Disciplina de Capa 8 (Pista B, P2-P3)

Componentes 2-4 de `CONTEXT_ENGINEERING_ARCHITECTURE.md` (secuencia
test→build→revisión, autoevaluación con control, hook de cierre de
sesión inspirado en delivery-gate). Sin relación con el producto GMP en
sí — mejora de proceso de Capa 8, puede posponerse sin bloquear nada del
analizador documental.

## Explícitamente NO planificado (fuera de alcance, o rechazado)

- Quinta validación E (A.7) — rechazada, sin caso real.
- Reemplazo de NO_SIGNAL/`DOCUMENTATION_GAP` — permanece.
- Adopción de `eval-harness`, `hooks/memory-persistence`,
  `iterative-retrieval` de ECC — rechazados, ver `ECC_ADOPTION_MATRIX.md`.
- Cualquier cambio a evidence_verifier.py como objeto de verificación —
  el DOM es siempre aditivo, nunca reemplaza el anclaje contra el texto
  plano original.
- Instalación de ECC como plugin — prohibido sin excepción (§B.3).

## Punto de decisión para Cesar

Este documento no autoriza ninguna fase. Antes de iniciar Fase 0 (la más
barata), Capa 8 debe presentar el diff propuesto y esperar aprobación
explícita — mismo protocolo que el resto del proyecto.
