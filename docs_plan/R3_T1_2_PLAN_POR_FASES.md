# R3-T1.2 — PLAN POR FASES: VALIDAR BARATO, CORRER COMPLETO SOLO SI PASA
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/R3_T1_2_PLAN_POR_FASES.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
# Reemplaza el §1.3 de R3_T1_1 (re-corrida directa de 145 llamadas) por un
# plan de 4 fases con gates. Todo lo demás de R3_T1_1 se conserva.
#
# Reglas duras: no corpus multi-documento; no MarkItDown; no cambiar modelo
# de juicio; no aflojar validadores; CERO llamadas LLM sin la autorización
# firmada de la fase correspondiente; no commit sin diff + aprobación.
# Cada fase se ejecuta en background (systemd-run/tmux, verificación de
# supervivencia a SSH) y DETIENE al final para el gate humano.
#
# PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.

──────────────────────────────────────────────────────────────────────────────
PRINCIPIO DEL PLAN
──────────────────────────────────────────────────────────────────────────────

Probar primero que el sistema funciona (F0-F1), validar el flujo completo
con la unidad mínima real (F2), y solo entonces la corrida completa (F3).
Cada fase tiene: criterio de éxito PRE-FIJADO antes de ejecutar, tope de
llamadas propio firmado por Cesar, y gate de salida — si una fase falla su
criterio, se corrige y se repite ESA fase; nunca se avanza "porque ya casi".

REGLA DE CONGELAMIENTO (clave para la economía): tras F1, la configuración
completa (prompt_version, schema, modelo+digest, catálogo, perfil H2H4,
chunking) queda CONGELADA. F2 y F3 corren con fingerprint idéntico ⇒ los
resultados de F2 son reutilizables por cache en F3 por diseño (la
invalidación de cache existe exactamente para lo contrario). Si algo debe
cambiar tras F1, se declara, se re-congela y F2 se repite — nunca se
mezclan resultados de fingerprints distintos.

──────────────────────────────────────────────────────────────────────────────
F0 — CIERRE SIN COSTO (cero llamadas LLM; ejecutar ya)
──────────────────────────────────────────────────────────────────────────────

Todo lo de R3_T1_1 que no requiere inferencia:

F0.1 Verificación del hallazgo (§0 de R3_T1_1): evaluation_profile real
     del run 943a, su autorización de presupuesto, archivo:línea del
     default equivocado.
F0.2 ENFORCEMENT del perfil de producto (§1.1): runs de producto = H2H4
     obligatorio, fail-closed si se pide producto con perfil no
     calificado, con test bloqueante.
F0.3 Informe 943a + sus 3 entradas de cola ⇒ SUPERSEDED_BY_PROFILE_
     CORRECTION (trazable, sin borrar).
F0.4 UI de revisión (§2 completo): render por tipo (findings sin diff),
     cero cargas mudas con timeout+error visible, vista de evidencia con
     candidatos de fusión (página+extracto+rank), identidad del revisor
     validada (422/409, un evento por decisión). Playwright.
F0.5 Consistencia del informe (§3): bucket de NOT_OBSERVED_OPTIONAL
     resuelto, page_or_section unificado, CROSS_REFERENCE con documento
     destino registrado.
F0.6 REVERIFICACIÓN DE FUENTES G3 (Part 11/211, segunda reingesta):
     preparar el paquete para la firma de Cesar y, tras firmarse,
     ejecutarla — es descarga gobernada + hash, no LLM. Sin esto, TODA
     conclusión de F2/F3 cargará SOURCE_PENDING_REVERIFICATION y no
     consolidará formal. Es prerequisito de F2, no un pendiente paralelo.
F0.7 Suite + Gate 0 verdes; commits por causa raíz (diff→aprobación).

GATE F0: reporte de cierre + firma de Cesar de la reverificación G3.
Criterio: todo lo anterior verde y fuentes Part 11/211 en estado
verificado.

──────────────────────────────────────────────────────────────────────────────
F1 — MICRO-VALIDACIÓN: EL CASO CONOCIDO (≈5-8 llamadas)
──────────────────────────────────────────────────────────────────────────────

Objetivo: demostrar que el runner de PRODUCTO con H2H4 ancla lo que
sabemos que existe, antes de gastar nada más.

F1.1 Proponer autorización (tope 8 llamadas; familia que corresponda) y
     DETENERSE para firma.
F1.2 Ejecutar por el flujo real de producto (no script ad hoc):
     21_CFR_11.10(e) × sus top-5 candidatos de fusión (el caso P1 —
     evidencia conocida p.45-46). Perfil H2H4, background, checkpoints.
F1.3 CRITERIO PRE-FIJADO: 11.10(e) ancla (observed con cita verificada,
     score de anclaje) en al menos uno de los candidatos ∧ el registro
     por llamada completo (fingerprint, perfil, validación A/B/C/D) ∧
     latencia p50/p95 medida (insumo D4-A).
F1.4 Si FALLA: investigar (con los raw persistidos), corregir, repetir F1
     con presupuesto nuevo firmado. NO avanzar a F2. Si PASA: CONGELAR la
     configuración (regla de congelamiento) y registrar el fingerprint
     que regirá F2/F3.

GATE F1: reporte con el anclaje demostrado + fingerprint congelado.

──────────────────────────────────────────────────────────────────────────────
F2 — UN REQUISITO, COBERTURA COMPLETA, FLUJO COMPLETO (≈29 llamadas)
──────────────────────────────────────────────────────────────────────────────

Objetivo: validar TODO el producto de punta a punta con la unidad mínima
que puede producir un informe legítimo: un requisito sobre el documento
completo.

F2.1 Proponer autorización (tope 35 = 29 + margen) y DETENERSE para firma.
F2.2 Ejecutar 21_CFR_11.10(e) × los 29 chunks de RW-0005 por el flujo
     Tier-1 real (baseline de cobertura completa, perfil H2H4, fingerprint
     congelado de F1).
F2.3 CRITERIO PRE-FIJADO (todo debe cumplirse):
     a) 11.10(e) = CONFIRMED en el informe (anclado; ya sin flag de
        fuente gracias a F0.6);
     b) la consolidación de ausencia y la agregación D operan con
        cobertura completa sin emitir nada inconsistente;
     c) el informe se genera con manifest, sanitizado, formato consistente;
     d) el ciclo de revisión humana opera EN VIVO: Cesar abre la UI
        corregida, ve la evidencia con candidatos, y registra una decisión
        real (aunque sea sobre un hallazgo de prueba) con identidad
        validada — el gate incluye tu clic, no solo tests;
     e) economía medida: llamadas, latencias, tiempo de pared ⇒ costo
        proyectado de F3 CALCULADO con datos, no estimado.
F2.4 Si FALLA cualquier literal: corregir y repetir F2 (el cache del
     fingerprint congelado hace que la repetición solo pague los chunks
     afectados). Si PASA: preparar la propuesta de F3 con el costo real.

GATE F2: informe de un requisito legítimo + tu decisión de revisión
registrada + costo de F3 en números reales.
