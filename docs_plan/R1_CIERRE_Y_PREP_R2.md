# CIERRE CONTROLADO R1.6/R1.7 + R1.8 (DESPACHO A REVISIÓN) + PREPARACIÓN R2
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/R1_CIERRE_Y_PREP_R2.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
# Corrida de CIERRE CONTROLADO + CORRECCIÓN DE GAP + DISEÑO (R2).
#
# Reglas duras: no R3/R4/R5; no corpus formal; no Piloto 2; no MarkItDown;
# no cambiar modelo; no borrar artefactos ni decisiones; no aflojar
# validadores; no commit sin diff + aprobación de Cesar.
#
# PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.

──────────────────────────────────────────────────────────────────────────────
1. CIERRE FORMAL DE R1.6/R1.7 (registrar, con verificación)
──────────────────────────────────────────────────────────────────────────────

Registrar en memoria + roadmap, cada punto verificado contra artefactos
reales (no de memoria):

1.1 P5 NO queda aprobado automáticamente. Resultado correcto y final:
    SUPPORTING_EVIDENCE_UNDER_REVIEW (con flag OBSERVED_ONLY_UNVERIFIED).
    Confirmar leyendo el checkpoint real del replay de R1.7.
1.2 ANNEX11_4 sigue RECHAZADO (chunks_observed=0), ahora por
    detect_reference_list_context() (mecanismo estructural), no por
    accidente de idioma. Confirmar con el test real
    test_r1_7_soft_relevance_verified_pipeline.py.
1.3 EL SEGUNDO NEGATIVO del fixture: el reporte confirma ANNEX11_4 pero NO
    menciona explícitamente el segundo negativo por el pipeline verificado.
    VERIFICAR que el segundo negativo del fixture 7P+2N sigue rechazado por
    el pipeline verificado; si no hay test que lo cubra, AGREGARLO (sin
    llamada nueva: replay/mock como en R1.7). Este es un hueco real de
    cobertura de la condición 3 de Cesar.
1.4 Estado real de la suite: focal + golden dataset (8/8) verdes; suite
    completa 2271 passed / 6 failed con los 6 caracterizados
    (3 Playwright ambientales + 1 cola no vacía + 2 runtime_identity por
    chunked_engine sin commit). VERIFICAR si tras el commit de R1.6/R1.7
    los 2 runtime_identity ya se cerraron (deberían) — reportar el conteo
    actualizado, no repetir el viejo.

──────────────────────────────────────────────────────────────────────────────
2. AUTORIZACIÓN DEL COMMIT (verificación de proceso — condición 5 de Cesar)
──────────────────────────────────────────────────────────────────────────────

2.1 Determinar si el commit de R1.6/R1.7 (y el 484d103 de R1.5) tuvieron
    aprobación EXPLÍCITA de Cesar sobre el diff ANTES de commitear.
    Evidencia: el plan .claude/plans/sharded-riding-turing.md fue "aprobado
    por Cesar antes de ejecutar" — aclarar si esa aprobación de PLAN
    incluye aprobación de COMMIT, o si el commit se hizo sin el paso
    diff→aprobación que exigen las reglas del proyecto.
2.2 Si hubo aprobación explícita de commit: registrarla y seguir.
2.3 Si NO la hubo (el diff no se mostró y aprobó antes del commit):
    documentarlo como DESVIACIÓN DE PROCESO (DEV-W5-xxx) — qué se
    commiteó sin aprobación previa, por qué el contenido es correcto de
    todos modos (tests verdes, no-regresión probada), y la acción
    correctiva: NO más commits sin el ciclo diff→aprobación. No revertir
    el commit (el contenido es válido y revertir historia Part 11 es peor);
    la desviación se cierra con el registro y la regla reafirmada, con
    aprobación retroactiva explícita de Cesar del contenido ya commiteado.
2.4 A partir de aquí, TODO commit de esta corrida y las siguientes:
    mostrar diff → esperar aprobación → commitear. Sin excepción.

──────────────────────────────────────────────────────────────────────────────
3. R1.8 — DESPACHO DE SUPPORTING_EVIDENCE_UNDER_REVIEW (el gap real de cierre)
──────────────────────────────────────────────────────────────────────────────

Hallazgo abierto de R1.7: SUPPORTING_EVIDENCE_UNDER_REVIEW llega a
result["verified_conclusions"] como campo CONSULTABLE, pero nada lo
despacha activamente a un humano. Para un sistema cuya regla es "QA humana
decide", una conclusión que pide revisión y no llega a ninguna cola es un
FALLO SILENCIOSO de nueva especie — la evidencia no se pierde, pero muere
en un campo que nadie mira. Cerrar esto es parte del cierre honesto de la
rama R1.

3.1 Diseño (mínimo, reutilizando lo existente):
    - toda conclusión SUPPORTING_EVIDENCE_UNDER_REVIEW (y EVALUATION_
      INCOMPLETE con flag, si aplica) se ENCOLA en la cola de revisión
      humana ya existente (factory/layer9/human_review_queue.py /
      review_queue.jsonl) con: run_id, requirement_id, documento+página,
      la cita anclada, el flag (OBSERVED_ONLY_UNVERIFIED), y el estado
      pendiente de decisión humana.
    - NUNCA auto-aprueba ni auto-promueve a DOCUMENTED_AND_SUPPORTED
      (CLAUDE.md prohíbe declaración de cumplimiento por el sistema).
    - La entrada en cola es la notificación; el despacho no cambia la
      conclusión, solo la hace visible y accionable para QA/Cesar.
3.2 Reader/Executor: el encolado ocurre en el camino de escritura del
    run (Executor), no en un GET. Un evento de auditoría por encolado.
3.3 Tests: una conclusión SUPPORTING_EVIDENCE_UNDER_REVIEW genera
    exactamente una entrada en cola con los campos completos; una
    conclusión negativa (ANNEX11_4) NO genera entrada de "revisar
    evidencia" (no hay evidencia que revisar); P5 real (replay) produce su
    entrada en cola. Sin llamadas nuevas.
3.4 Si el diseño resulta más grande de lo mínimo (p. ej. requiere un panel
    de UI nuevo), DETENERSE tras el diseño y presentarlo a Cesar como
    corrida separada — no expandir alcance sin aprobación. El encolado en
    review_queue.jsonl (sin UI nueva) es el mínimo viable y probablemente
    suficiente para cerrar el gap.

──────────────────────────────────────────────────────────────────────────────
4. PREPARACIÓN DE R2 — SOLO DISEÑO Y MEDICIÓN DE RECUPERACIÓN
──────────────────────────────────────────────────────────────────────────────

Alcance PERMITIDO de R2 en su preparación (esta y las próximas corridas
hasta que Cesar habilite ejecución):

R2_SCOPE_ALLOWED:
- Diseño detallado del módulo de recuperación determinista por
  requirement_id (ubicación en factory/regulatory/, separación 8000/9000).
- Construcción de la query desde el Evidence Pack (canonical_text +
  evidence_min_criteria + sinónimos gobernados de requirement_terms.yaml;
  NUNCA weak_keywords solas).
- Indexación del documento objetivo en colección ChromaDB propia (patrón
  knowledge/retriever.py) con mapeo chunk→página.
- MÉTRICA DE RECUPERACIÓN pura (determinista, CERO llamadas LLM): para
  cada positivo del fixture, ¿el pasaje verificado a mano está entre los
  top-k candidatos recuperados? Esta medición NO consume presupuesto
  PILOT_EXECUTION porque no invoca el modelo — es recuperación pura.
- Tests de recuperación contra el fixture 7P+2N (el negativo no debe
  arrastrar candidatos que luego disparen un falso positivo).

R2_NOT_ALLOWED (sin firma explícita de Cesar):
- Ejecutar la fase de JUICIO (llamadas LLM sobre los top-k) — eso es la
  medición de recall de R2, requiere PILOT_EXECUTION nueva firmada.
- Corpus formal, Piloto 2, R3/R4/R5.
- Cambiar el modelo, los umbrales o cualquier validador.
- Tocar el pipeline verificado de juicio (ya productizado en R1.5-R1.7);
  R2 le antecede (le entrega mejores pasajes), no lo modifica.

Entregable de esta corrida para R2: solo el DISEÑO detallado
(R2_DESIGN_DETALLADO.md) + la medición de recuperación pura si el diseño
queda listo y el tiempo alcanza. La medición de recall (con LLM) queda
para una corrida futura con su PILOT_EXECUTION firmada.

──────────────────────────────────────────────────────────────────────────────
5. ENTREGA
──────────────────────────────────────────────────────────────────────────────

Mostrar diffs (R1.8 código+tests + memoria/roadmap/skill + diseño R2),
sin commit. Reportar SOLO:

```
R1_6_STATUS:                 CLOSED (defecto de idioma corregido)
R1_7_STATUS:                 CLOSED (pre-filtro rediseñado, maquinaria C real)
P5_FINAL_STATE:              SUPPORTING_EVIDENCE_UNDER_REVIEW (no auto-aprobado)
NEGATIVES_CONFIRMED:         ANNEX11_4 rechazado + segundo negativo
                             (verificado / test agregado)
GATE0_REAL_STATUS:           (conteo actualizado tras commit; focal+golden verde)
COMMIT_AUTHORIZATION_STATUS: (aprobado / desviación DEV-W5-xxx registrada)
R1_8_STATUS:                 (SUPPORTING_EVIDENCE_UNDER_REVIEW ahora encolado
                             a revisión humana / diseñado y pendiente)
OPEN_GAPS:                   (lo que quede, con dueño)
R2_SCOPE_ALLOWED:            (diseño + recuperación pura determinista)
R2_NOT_ALLOWED:              (juicio LLM sin firma, corpus, Piloto 2, R3-R5)
D4_2026_004_STATUS:          PROPOSED (sin cambios; recálculo H2H4 pendiente)
NEXT_DIFF_OR_PLAN:           (qué espera aprobación de Cesar y en qué orden)
```

DETENERSE. No commit hasta aprobación de Cesar. R2 no ejecuta juicio LLM
hasta que Cesar firme una PILOT_EXECUTION nueva; hasta entonces, solo
diseño y recuperación determinista pura.
