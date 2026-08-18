# M4.1 — SEGUNDA SEÑAL OBLIGATORIA ANTES DE DOCUMENTATION_GAP
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/M4_1_CORRECCION_SEGUNDA_SENAL.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
# Corrige un defecto de diseño en AD-3/M4 (mío, no de la implementación):
# el umbral de cobertura se calibró con un argumento de RECUPERACIÓN
# (recall@5=7/7) y se usó para autorizar una conclusión sobre confiabilidad
# de JUICIO — propiedad distinta y ya confirmada como no confiable para
# evidencia parafraseada (3 veces: H1-H4, Palanca A, V2). Consecuencia
# real observada: P2/P5 (sospecha alta de falso negativo, evidencia real
# ya identificada en su texto) pasaron de EVALUATION_INCOMPLETE a
# DOCUMENTATION_GAP — sobre-afirmación de certeza.
#
# Cero llamadas LLM. GAP ya routea a revisión humana (no hay riesgo de
# auto-aprobación) — esto es corrección de precisión de etiqueta, no
# emergencia de seguridad.

──────────────────────────────────────────────────────────────────────────────
QUÉ CORREGIR
──────────────────────────────────────────────────────────────────────────────

1. Añadir `_lexical_evidence_absent(candidate_metadata, evidence_pack)`:
   verifica, sobre el texto de LOS 3 candidatos evaluados, si existe
   CUALQUIER solapamiento léxico con `evidence_min_criteria`/términos
   clave del Evidence Pack del requisito (mismo tipo de comparación
   determinista ya usado en otras capas del pipeline — reutilizar
   utilidades existentes de tokenización/normalización si existen, no
   reimplementar).
2. `_top_k_fusion_coverage_complete()` (M4) pasa a exigir DOS condiciones
   con AND, no una: `len(candidate_metadata) >= threshold` **Y**
   `_lexical_evidence_absent(...) == True`. Si hay solapamiento léxico
   con el criterio en cualquiera de los 3 candidatos, M4 NO se activa —
   el resultado se queda en `EVALUATION_INCOMPLETE` (estado honesto:
   "se buscó, hay términos relacionados presentes, el juicio no pudo
   confirmar — requiere revisión humana con prioridad, no es ausencia
   declarada").
3. La entrada de cola ya enriquecida (umbral, ranking, extractos) se
   mantiene igual en AMBOS casos — el cambio es solo la etiqueta de
   conclusión, no el contenido que ve el revisor.
4. Actualizar el comentario de `M4_ABSENCE_RANK_THRESHOLD` para dejar
   explícita la distinción: el umbral k=3 garantiza que NINGÚN positivo
   conocido se pierde por RECUPERACIÓN; NO garantiza que el JUICIO sobre
   esos candidatos sea confiable — por eso la segunda señal es
   obligatoria, no opcional.

──────────────────────────────────────────────────────────────────────────────
TESTS (0 LLM)
──────────────────────────────────────────────────────────────────────────────

- Replay de P2 con la corrección: los candidatos contienen "21 CFR Part
  11", "access", tabla de niveles de seguridad → solapamiento léxico
  detectado → permanece `EVALUATION_INCOMPLETE`, NO `DOCUMENTATION_GAP`.
- Replay de P5: candidatos contienen "date and time stamps" (términos de
  contemporaneidad) → mismo resultado, permanece `EVALUATION_INCOMPLETE`.
- Caso sintético de ausencia genuina (cero términos relacionados en los 3
  candidatos): SÍ promueve a `DOCUMENTATION_GAP` — confirma que M4 sigue
  operando para el caso que de verdad puede automatizarse con confianza.
- Negativos N1/N2: siguen rechazados, sin cambio — bloqueante.
- Regresión: `test_m4_top_k_fusion_threshold_met_emits_gap_not_incomplete`
  (el test existente de M4) se actualiza para reflejar el nuevo
  comportamiento con AND — documentar el cambio de expectativa
  explícitamente en el mensaje de commit, no silenciarlo.

──────────────────────────────────────────────────────────────────────────────
RE-REPLAY DEL FIXTURE COMPLETO
──────────────────────────────────────────────────────────────────────────────

Tras el fix: correr el mismo replay de 8 checkpoints ya pagados y reportar
la tabla actualizada. Expectativa: P2/P5/P6/P7 vuelven a
`EVALUATION_INCOMPLETE` (a menos que el chequeo léxico de P6/P7 confirme
ausencia genuina de términos — reportar cada caso con su resultado real,
no asumir el mismo desenlace para los 4).

──────────────────────────────────────────────────────────────────────────────
ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
LEXICAL_CHECK_IMPLEMENTED =   (función pura, reutiliza tokenización existente)
M4_NOW_REQUIRES_AND =         confirmado (cobertura AND ausencia léxica)
P2_P5_RELABELED =             EVALUATION_INCOMPLETE (esperado)
P6_P7_RESULT =                (real, sin asumir)
SYNTHETIC_GAP_STILL_WORKS =   (confirma que M4 sigue teniendo alcance útil)
NEGATIVES_STILL_REJECTED =    bloqueante
CODE_CHANGED =                (diff mostrado, sin commit sin aprobación)
PRODUCTION_ENABLEMENT =       BLOCKED

```
generar una carpeta con el resultado de toda la ejecucion y mostrar la dirreccion
DETENERSE tras mostrar el diff. Commit solo con aprobación explícita de
Cesar, causa raíz separada del commit de M4 original (`9718fd7`).
