# R1.6 — DEFECTO DE VALIDADOR DE RELEVANCIA (MISMATCH DE IDIOMA)
# + verificación de integridad del commit R1.5 y cierre formal de R1.5
#
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/R1_6_VALIDADOR_RELEVANCIA_IDIOMA.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
# Corrida de VERIFICACIÓN + INVESTIGACIÓN + CORRECCIÓN GOBERNADA de un
# validador. Sensible: tocar un validador de la familia C exige el máximo
# rigor de no-regresión.
#
# Reglas duras: no R2; no Piloto 2; no corpus formal; no MarkItDown; no
# cambiar modelo; no borrar artefactos ni decisiones; no commit sin diff +
# aprobación de Cesar.
#
# PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.

──────────────────────────────────────────────────────────────────────────────
0. DECISIONES DE CAPA 9 YA TOMADAS (para esta corrida)
──────────────────────────────────────────────────────────────────────────────

Cesar resolvió las 4 decisiones pendientes del reporte R1.5:
1. R1.5 = CLOSED. La productización de H2+H4 funciona, está probada (10/10
   tests, plumbing correcto por flujo real, P5 ancló de verdad con cita
   verificada a score 1.0). Su objetivo se cumplió.
2. El hallazgo de _is_topically_relevant() se trata como R1.6, corrida
   propia y acotada (esta).
3. R2 permanece EN ESPERA hasta que R1.6 cierre. R1.6 es el camino crítico.
4. Autorizado investigar y, si es seguro, corregir _is_topically_relevant()
   — bajo el régimen de no-regresión de esta corrida (Bloque 3).

──────────────────────────────────────────────────────────────────────────────
1. VERIFICACIÓN DE INTEGRIDAD DEL COMMIT R1.5 (484d103)
──────────────────────────────────────────────────────────────────────────────

Antes de abrir R1.6, confirmar que R1.5 quedó íntegro en el árbol:

1.1 Verificar que el commit 484d103 contiene las versiones COMPLETAS de
    chunked_engine.py y corpus_runner.py con el modo evaluation_profile
    (no parciales). Diff del commit vs. el estado que el reporte describe
    (+89 chunked_engine, +149/-25 corpus_runner). Cualquier discrepancia
    ⇒ reportar; el código productizado no puede quedar a medias en HEAD.
1.2 Confirmar qué quedó FUERA a propósito (pilot_run/checkpoints/,
    manifests/, status/, r1_smoke de R1, árbol no relacionado) y que nada
    de eso era necesario para que R1.5 funcione. Listar lo que sigue
    untracked y clasificar: artefacto legítimo pendiente de su propio
    commit / ruido / estado runtime que no debe versionarse.
1.3 Suite + Gate 0: reconfirmar los 10 fallos ya caracterizados como no
    atribuibles al código nuevo (4 git-diff de decisions_v2, 3 Playwright
    ambientales, 2 runtime_identity por chunked_engine sin commit —
    verificar si estos 2 YA se resolvieron al commitear 484d103; si el
    commit los cerró, el conteo debe bajar).

>>> CHECKPOINT 1: estado de integridad de R1.5. Si íntegro, continuar.

──────────────────────────────────────────────────────────────────────────────
2. INVESTIGACIÓN DEL DEFECTO (solo lectura, con evidencia)
──────────────────────────────────────────────────────────────────────────────

2.1 Leer _is_topically_relevant() en chunked_engine.py: qué compara
    exactamente (palabras significativas del label del checkpoint vs. la
    cita/chunk), cómo, y por qué el label español no matchea un documento
    inglés. Archivo/línea.
2.2 ALCANCE DEL DEFECTO (clave — determina si es puntual o sistémico):
    - inventariar los labels de TODOS los prompts YAML por agente: ¿todos
      en español? ¿qué proporción de checkpoints quedaría afectada si el
      documento fuente está en inglés?
    - inventariar el idioma de los documentos de la allowlist analizables:
      ¿cuántos son inglés? (RW-0005 lo es). Si labels=español y
      docs=inglés es la norma, el gate rechaza sistemáticamente evidencia
      genuina en TODO documento inglés — no es un caso aislado de P5, es un
      bloqueo del analizador entero.
2.3 CLASIFICACIÓN DEL GATE: confirmar a qué validación pertenece
    _is_topically_relevant (¿es parte de C — relevancia semántica — o un
    pre-filtro anterior?). Esto define el régimen de prueba: si es C,
    tocarlo roza la prohibición central y exige el fixture completo como
    guardia (Bloque 3). Documentar la clasificación con evidencia.
2.4 Reproducir el rechazo en P5 con datos reales (sin gastar llamada
    nueva: usar el raw_response y checkpoint ya persistidos en
    r1_5_h2h4_chunked-596f70cc4520/) — mostrar el paso exacto donde la
    cita anclada (score 1.0) es rechazada por el mismatch de label.

──────────────────────────────────────────────────────────────────────────────
3. DISEÑO DE LA CORRECCIÓN — DISTINGUIR "ARREGLAR BUG" DE "AFLOJAR CONTROL"
──────────────────────────────────────────────────────────────────────────────

PRINCIPIO RECTOR (leer con cuidado): la prohibición central dice que un
validador NO se afloja para subir recall. Corregir _is_topically_relevant
para que acepte más citas es, en la forma, exactamente eso. La diferencia
legítima entre "arreglar un bug" y "relajar un control" debe DEMOSTRARSE,
no asumirse:
- un bug se arregla haciendo que el gate mida lo que DEBÍA medir
  (relevancia real entre requisito y evidencia), independientemente del
  idioma del label;
- una relajación es bajar el listón para que pase más de todo, incluidos
  los falsos positivos.
La prueba de que es lo primero y no lo segundo: ANNEX11_4 (y todos los
negativos) DEBEN seguir rechazados después del cambio, y los positivos
genuinos deben pasar. Si el cambio hace pasar también a ANNEX11_4, es una
relajación disfrazada y se descarta.

Opciones de diseño a evaluar (elegir la más segura, justificar):
(a) el gate compara relevancia contra el TEXTO NORMATIVO CANÓNICO /
    evidence_min_criteria del Evidence Pack (contenido gobernado,
    disponible en el idioma de la norma) en vez de contra el label
    traducido — ataca la causa (el label es una etiqueta de UI, no el
    criterio de relevancia) sin bajar ningún umbral;
(b) neutralizar el idioma del label (normalización/traducción del label a
    un espacio común) — más frágil, evaluar;
(c) que la relevancia se derive de la propia cadena de recuperación
    (anticipo de R2) — probablemente fuera de alcance de R1.6, anotar.
Recomendación esperable: (a) — mueve el criterio de relevancia del label
cosmético al contenido gobernado real, que es donde debió estar. Pero la
decide el análisis, no esta nota.

NO tocar: validación A (anclaje literal), umbral fuzzy, el fix de viñetas,
el schema, ni el contrato baseline. El cambio se acota a _is_topically_
relevant y su fuente de comparación.

──────────────────────────────────────────────────────────────────────────────
4. RÉGIMEN DE NO-REGRESIÓN (obligatorio antes de cualquier cambio real)
──────────────────────────────────────────────────────────────────────────────

4.1 Tests deterministas (almacén temporal, sin llamadas LLM) que fijen,
    ANTES y DESPUÉS del cambio:
    - ANNEX11_4 (GAMP5 en lista de referencias) sigue RECHAZADO por el
      gate — test bloqueante;
    - el segundo negativo del fixture sigue rechazado;
    - la cita real de P5 (ya persistida, score 1.0) pasa el gate tras el
      fix (deja de ser rechazada por idioma);
    - casos construidos: label-inglés/doc-inglés (no debe romperse),
      label-español/doc-español (no debe romperse), label-español/
      doc-inglés (el caso roto, debe arreglarse).
4.2 Regresión completa: la suite entera + Gate 0 verdes; ningún llamador
    existente cambia de comportamiento salvo el efecto deseado del gate.
4.3 Solo DESPUÉS de que 4.1/4.2 estén verdes con datos ya persistidos
    (cero llamadas), evaluar si hace falta UNA validación con llamada real
    sobre P5 por el flujo real (perfil H2H4) para confirmar que ahora
    llega a "observed" de punta a punta. Si se necesita: usar la
    PILOT_EXECUTION seleccionada determinísticamente (‑004/‑006, con
    presupuesto), NO proponer nueva; confirmar en el reporte cuál y cuánto.

>>> CHECKPOINT 4: mostrar diff del validador + tests de no-regresión, con
>>> la tabla ANTES/DESPUÉS del fixture. Sin commit.

──────────────────────────────────────────────────────────────────────────────
5. RE-MEDICIÓN DE RECALL (contexto, no gate de esta corrida)
──────────────────────────────────────────────────────────────────────────────

El defecto pudo haber deprimido el recall medido (2/7): citas genuinas
rechazadas por idioma antes de contar como observed. Anotar como hipótesis:
tras el fix, el recall REAL del fixture podría ser mayor que 2/7. NO
re-medir el fixture completo en esta corrida (consumiría presupuesto y es
alcance de R2/recalificación). Solo dejar registrado que la medición 2/7
quedó potencialmente sesgada a la baja por este gate, y que la re-medición
formal ocurre cuando R2 arranque con el pipeline ya corregido.

──────────────────────────────────────────────────────────────────────────────
6. ACTUALIZACIÓN DE MEMORIA, SKILL Y ROADMAP
──────────────────────────────────────────────────────────────────────────────

6.1 Memoria: registrar R1.5 CLOSED, R1.6 (este hallazgo, estado y
    resultado), y la corrección de la narrativa de recall — el 2/7 no era
    puramente límite del modelo; un gate de relevancia con mismatch de
    idioma estaba descartando anclajes genuinos. Esto es importante para
    la decisión futura GPU/externo: el techo del modelo puede ser más alto
    de lo que se creía.
6.2 Skill gmp-recall-pipeline: agregar _is_topically_relevant y el patrón
    label-vs-contenido-gobernado a la sección de validadores, con la
    advertencia de idioma, para que ninguna sesión futura vuelva a
    confundir un rechazo por idioma con un fallo de recall del modelo.
6.3 Roadmap: R1.5 CLOSED; R1.6 con su estado; R2 desbloqueado SOLO cuando
    R1.6 cierre (P5 llega a observed de punta a punta, negativos intactos).

──────────────────────────────────────────────────────────────────────────────
7. ENTREGA
──────────────────────────────────────────────────────────────────────────────

Mostrar diffs (validador + tests + memoria + skill + roadmap), sin commit.
Reportar SOLO:

```
R1_5_COMMIT_INTEGRITY =        (484d103 íntegro / discrepancia)
R1_5_STATUS = CLOSED
DEFECT_CONFIRMED =             (_is_topically_relevant, mismatch idioma)
DEFECT_SCOPE =                 (puntual P5 | sistémico: labels-es/docs-en)
GATE_CLASSIFICATION =          (familia C / pre-filtro — con evidencia)
DOCS_IN_ENGLISH_IN_ALLOWLIST = (cuántos, riesgo sistémico)
CORRECTION_DESIGN =            (opción elegida + por qué no afloja)
ANNEX11_4_STILL_REJECTED =     true (test bloqueante; si false ⇒ descartar)
NEGATIVES_STILL_REJECTED =     2/2
P5_PASSES_GATE_AFTER_FIX =     (con datos persistidos)
P5_OBSERVED_END_TO_END =       (si se hizo la validación con llamada real)
RECALL_2_7_POTENTIALLY_BIASED_LOW = true (nota, no re-medido)
SUITE / GATE_0 =
R2_ENABLED =                   false hasta cierre de R1.6
MEMORY_UPDATED / SKILL_UPDATED / ROADMAP_UPDATED =
PENDIENTE_DE_APROBACIÓN =      (diff para commit; cierre de R1.6;
                               habilitación de R2)
```

DETENERSE. No commit hasta aprobación de Cesar. R2 arranca solo cuando
R1.6 cierre: P5 observado de punta a punta por el flujo real Y los dos
negativos intactos. Si la corrección del validador hiciera pasar algún
negativo, se descarta y se rediseña — la integridad del control pesa más
que cerrar R1.6 rápido.
