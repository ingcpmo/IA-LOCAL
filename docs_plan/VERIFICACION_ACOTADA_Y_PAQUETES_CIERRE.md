# VERIFICACIÓN ACOTADA + PAQUETES DE CIERRE DEFINITIVOS
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/VERIFICACION_ACOTADA_Y_PAQUETES_CIERRE.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# Rol: Arquitecto Principal. Autoridad: Capa 9 = Cesar.
# NO implementar código. NO commit. Cero llamadas LLM.
#
# Contexto: la evaluación final (EVALUACION_FINAL_ANALIZADOR_GMP_Y_PLAN_
# CIERRE.md) ya está hecha y es de buena calidad — no se repite. Un
# tercero propuso una segunda ronda completa de "mesa de diseño" sobre
# los NOT_VERIFIED; se acepta parcialmente: solo los 4 puntos que pueden
# CAMBIAR una clasificación de severidad se verifican ahora. El resto
# (A, K, M4.1) ya tiene evidencia suficiente o se resuelve dentro del
# propio paquete de implementación — abrirlos aparte sería otra ronda de
# auditoría sin necesidad.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 1 — VERIFICACIÓN ACOTADA (4 puntos, en orden de severidad potencial)
──────────────────────────────────────────────────────────────────────────────

## 1.1 I — ¿existe bypass de RemediationDirective? (verificar PRIMERO)

Si alguna ruta API/productiva puede generar un cambio de remediación sin
pasar por `remediation_directive.py`, esto deja de ser P1 y pasa a ser
**P0**: rompería la garantía central del proyecto de que la IA nunca
redacta autónomamente el texto regulatorio final.

Verificar: todos los endpoints/servicios que llaman a
`remediation_change_application_resolver.py` (o equivalente que aplique
cambios a un documento) — confirmar que TODOS exigen una
`RemediationDirective` con `status=SUBMITTED` y `proposed_text` de
autoría humana como precondición. Citar archivo:línea de cada llamador
encontrado. Si se encuentra un camino que no lo exige: reportarlo como
`I_BYPASS_FOUND = YES` con la ruta exacta — esto detiene todo lo demás
hasta que Cesar decida cómo tratarlo.

## 1.2 J — Trazabilidad end-to-end hasta la generación final

Verificar en `remediation_package_schemas.py` (o donde vivan
`RemediationChange`/`RegulatoryCitationReference`) si `finding_rc_id` y
`directive_id` viajan efectivamente hasta
`remediation_change_application_resolver.py` y aparecen en el manifest
final generado. Citar los campos exactos y su punto de origen/destino. Si
la cadena se rompe en algún punto, identificar dónde.

## 1.3 D — P4: ¿falta de dato o decisión regulatoria pendiente?

Localizar la fuente real de la matriz de aplicabilidad (dónde vive el
dato, no solo su consumidor ya identificado en
`absence_consolidator.py:90-233`). Determinar con evidencia: ¿el par
(ALCOA_ATTRIBUTABLE, tipo documental de RW-0011) simplemente no tiene
entrada en esa fuente (dato faltante, arreglo técnico), o la matriz sí
lo contempla pero de forma ambigua/contradictoria (requiere decisión
regulatoria de Cesar)? Esto determina si la acción de cierre es "llenar
un campo" o "presentarle una pregunta a Cesar".

## 1.4 H — Consumidores de decisions_v2.jsonl

Grep de todos los lectores de `decisions_v2.jsonl` con consecuencias
productivas (no solo el escritor ya verificado). Confirmar que ninguno
actúa sobre un registro `agent_proposed` sin su `human_confirmed`
correspondiente. Citar cada consumidor encontrado con su verificación.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 2 — RECLASIFICACIÓN (solo si el Bloque 1 cambia algo)
──────────────────────────────────────────────────────────────────────────────

Si 1.1 encuentra bypass real: `I` pasa a P0, se detiene todo lo demás,
se reporta a Cesar de inmediato sin esperar el resto del documento.

Si 1.2/1.3/1.4 no cambian la severidad de nada (resultado esperado más
probable, dado que el diseño de estos módulos ya está bien evidenciado):
confirmar los 4 P1 originales (F, G, D-dato-P4, M-firma-electrónica) tal
como quedaron en `EVALUACION_FINAL_ANALIZADOR_GMP_Y_PLAN_CIERRE.md`, con
una sola actualización: el ítem D ahora especifica si su cierre es
"completar dato" o "decisión de Cesar" según 1.3.

NO reabrir A, K ni M4.1 como verificación aparte — ya tienen evidencia
suficiente o se resuelven dentro de los paquetes del Bloque 3.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 3 — PAQUETES DE IMPLEMENTACIÓN (en la MISMA corrida, sin pausa)
──────────────────────────────────────────────────────────────────────────────

Agrupados por causa raíz, no por fase artificial. Para cada uno: objetivo,
causa raíz, archivos a tocar, archivos protegidos, comportamiento
esperado, tests, criterio PASS/FAIL, si requiere LLM (ninguno debería),
aprobación de Capa 9 requerida, commit independiente.

**PAQUETE 1 — Integración de hallazgos (causa raíz: F + G)**
Objetivo: (a) generar candidatos NCR/CAPA/change-control desde un
hallazgo real — SOLO detectar→sugerir clasificación→fundamento→cola
humana, NUNCA cerrar CAPA/NCR automáticamente (aclaración explícita del
tercero, correcta); (b) unificar `tier1_report.py` +
`gap_assessment_finding_mapper.py` en un único artefacto de informe por
hallazgo (evidencia+página+riesgo+recomendación+trazabilidad),
reutilizando ambos módulos, sin inventar campos cuando falte el dato.
Incluye la validación de A (page_numbers) como parte de la revisión de
este paquete, no aparte.

**PAQUETE 2 — Gobernanza de identidad (causa raíz: M, + I/H si 1.1/1.4
lo exigen)**
Atar `decided_by` a identidad autenticada real en vez de texto libre.
Si 1.1 encontró bypass: incluir su cierre aquí con prioridad P0.

**PAQUETE 3 — P4 (causa raíz: D, dato o decisión según 1.3)**
Si es dato faltante: completar la matriz. Si es decisión regulatoria:
presentar a Cesar la pregunta exacta, no automatizarla.

**PAQUETE 4 — UI y vocabulario (P2, no bloqueante)**
Completar superficie de UI de remediación a todos los paquetes;
unificar vocabulario de clasificación (conclusion/bucket/status) en
un glosario; obtener el clic real de validación de Cesar en producción.

──────────────────────────────────────────────────────────────────────────────
ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
genera un reporte de lo ejecutado en una carpeta solo para lo ejecutado
I_BYPASS_FOUND =              (YES/NO — si YES, se detiene todo)
J_TRACEABILITY_CONFIRMED =    (sí/no, con cita)
D_ROOT_CAUSE =                (dato faltante / decisión regulatoria pendiente)
H_CONSUMERS_VERIFIED =        (lista con cita)
P0_COUNT =                    (0 esperado, salvo hallazgo en 1.1)
P1_COUNT =                    (4, confirmado o ajustado)
PACKAGES_READY =              4 (listos para aprobación de Cesar)
CODE_CHANGED =                0
PRODUCTION_ENABLEMENT =       BLOCKED
```

DETENERSE tras el Bloque 3. Ningún paquete se implementa sin aprobación
explícita de Cesar, uno a la vez.
