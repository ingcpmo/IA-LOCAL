# Cierre — Investigación de la rotación de `identity_keys.yaml` (2026-08-26)

**Tipo de corrida:** documentación + diseño (read-only). No se modificó
código, no se rotaron keys, no se tocó `.secrets`, no se reinició ningún
contenedor, no hubo commit ni push como parte de esta investigación.

**Encargo:** Capa 9 (Cesar) pidió reconstruir la causa real de la rotación
de `factory/config/identity_keys.yaml` ocurrida el mismo día, distinguiendo
`EVIDENCIA_CONFIRMADA`, `INFERENCIA` y `NO_VERIFICADO`.

**Método:** lectura de los backups en
`factory/config/identity_keys.yaml.backup_*`, timestamps de archivo,
contenido de `.secrets/gmp_factory/` (solo verificación de hash, sin
imprimir texto plano), `~/.bash_history`, y `docker logs factory-api -t`
(marcas `Application startup complete`).

## Resultado

```
ROTATION_OCCURRED=YES

ROTATION_DATE=2026-08-26 (múltiples eventos: ~05:03, ~13:56, ~14:54, ~15:04 UTC)

ROTATED_IDENTITIES=Cesar, Andrea_Reviewer

INITIAL_TRIGGER=
  EVIDENCIA_CONFIRMADA: antes de la primera rotación del día se ejecutó un
  script que barre /home/ing_cpmo y /tmp buscando cualquier archivo ≤4KB
  cuyo sha256 coincida con el key_sha256 de Cesar registrado -- patrón de
  "no tengo la key en claro, ¿existe en algún lado?". Se repitieron varios
  ciclos de "PRE_E2E_IDENTITY_GATE" comparando /tmp/identity_cesar.key y
  /tmp/identity_b.key contra los hashes registrados.
  INFERENCIA: el resultado de esa búsqueda fue negativo (no se encontró la
  key original), lo cual explica por qué se procedió a generar keys nuevas
  en vez de recuperar la existente -- mismo patrón documentado para el
  09-19 (key solo existía en un scratchpad efímero ya borrado).

KEY_MISMATCH_CONFIRMED=
  EVIDENCIA_CONFIRMADA -- múltiples chequeos "{name}_KEY_MATCH" y
  "PRE_E2E_IDENTITY_GATE=FAIL/PASS" se ejecutaron repetidamente sobre
  ambas identidades antes de que las rotaciones definitivas ocurrieran.

KEY_LOSS_OR_UNAVAILABILITY_CONFIRMED=
  Cesar: EVIDENCIA_CONFIRMADA (búsqueda filesystem-wide de la key original,
  sin éxito verificable -- INFERENCIA sobre el resultado).
  Andrea_Reviewer: EVIDENCIA_CONFIRMADA -- el backup
  identity_keys.yaml.backup_20260826_135608 contiene un comentario propio
  del archivo explicando que el hash de Andrea se había calculado sobre el
  archivo CON salto de línea final, mientras resolve_identity() hace
  .strip() antes de hashear -- "el hash viejo nunca iba a coincidir con
  ninguna llamada real". Confirma que Andrea_Reviewer también requirió
  corrección/provisioning.

PLAINTEXT_EXPOSURE_TRIGGERED_ADDITIONAL_ROTATION=
  EVIDENCIA_CONFIRMADA (el evento de exposición) + INFERENCIA (que fue la
  causa de la rotación siguiente).
  Secuencia en bash_history:
    1. Backup identity_keys.yaml.backup_before_rotation_20260826_145429
       (14:54:29).
    2. Bloque "ROTACION DEFINITIVA X-IDENTITY-KEYS -- DECISION 2": genera
       Cesar/Andrea nuevas vía openssl rand -hex 32 en
       /tmp/identity_cesar.key y /tmp/identity_b.key, actualiza hashes,
       gate PASS, docker restart factory-api (confirmado por Application
       startup complete a las 14:54:32).
    3. Inmediatamente después: cat /tmp/identity_cesar.key y
       cat /tmp/identity_b.key -- ambas keys en texto plano impresas
       directamente a la terminal/sesión.
  Tras ese evento aparece un tercer set de hashes que NO tiene ningún
  comando correspondiente en bash_history (ni openssl, ni edición de
  yaml, ni docker restart inmediato), pero sí archivos nuevos con
  timestamp idéntico (15:04:16, ±56ms):
    - identity_keys.yaml.backup_20260826_150416_e2e (snapshot "antes")
    - identity_keys.yaml actual (snapshot "después")
    - .secrets/gmp_factory/cesar_identity.key y
      .secrets/gmp_factory/andrea_reviewer_identity.key (0600, verificados
      por hash: coinciden exactamente con el identity_keys.yaml VIVO
      actual, NO con el backup "_e2e").
  Application startup complete vuelve a aparecer a las 15:10:43 (~6 min
  después, no ~3s como el patrón automático de los scripts anteriores).
  INFERENCIA: esta tercera rotación (15:04) fue la remediación directa de
  la exposición en texto plano del paso DEFINITIVA -- se generaron keys
  nuevas otra vez y esta vez se guardaron en almacenamiento permanente
  fuera de /tmp (.secrets/gmp_factory/, 0600) en vez de mostrarse por cat.
  El mecanismo exacto que escribió esos 4 archivos NO_VERIFICADO (no hay
  comando de shell correspondiente en el historial -- pudo ejecutarse
  fuera de bash o con historial suprimido).
  Nota: se confirmó (EVIDENCIA_CONFIRMADA) que /tmp/identity_cesar.key y
  /tmp/identity_b.key ya NO existen en el servidor -- no hay exposición
  residual en /tmp a la fecha de este cierre.

HASHES_UPDATED=
  EVIDENCIA_CONFIRMADA -- 4 sets distintos de key_sha256 para Cesar y
  Andrea_Reviewer durante el día (05:03 solo-Cesar -> 13:56 corrección
  Andrea -> CONTROLADA -> DEFINITIVA -> rotación final ~15:04, que es la
  vigente).

FACTORY_API_RESTARTED_AFTER_ROTATION=
  EVIDENCIA_CONFIRMADA -- docker logs factory-api -t muestra "Application
  startup complete" en 05:06:04, 13:56:11, 14:54:32 y 15:10:43,
  correlacionando con cada backup/rotación del día. Restarts posteriores
  (16:00, 16:12, 16:26, 17:40, 17:52, 18:26, 18:36) NO coinciden con
  ningún cambio en identity_keys.yaml (mtime no cambia desde 15:04:16) --
  NO_VERIFICADO si están relacionados con la rotación; más probable que
  respondan a los cambios de código no commiteados en
  factory/api/routes/layer9.py / factory/core/audit_writer.py (fuera del
  alcance de esta investigación).

SECURE_STORAGE_PATH=/home/ing_cpmo/.secrets/gmp_factory/
  (cesar_identity.key, andrea_reviewer_identity.key -- 0600,
  EVIDENCIA_CONFIRMADA que coinciden con el yaml vivo actual)

DECISION_2_RELATION=
  EVIDENCIA_CONFIRMADA -- ambos scripts de rotación llevan explícitamente
  el encabezado "ROTACION [CONTROLADA|DEFINITIVA] X-IDENTITY-KEYS --
  DECISION 2", y el backup "_e2e" nombra literalmente el E2E de Decisión 2
  (liberación). La rotación fue condición previa para poder correr el E2E
  técnico de Decisión 2 con require_identity resolviendo Cesar/Andrea
  correctamente.

ROTATION_WAS_CODE_CHANGE=NO
ROTATION_WAS_PROVISIONING_CHANGE=YES

EVIDENCE=
  - factory/config/identity_keys.yaml.backup_20260826_050303 (05:03:03)
  - factory/config/identity_keys.yaml.backup_20260826_135608 (13:56:08,
    comentario interno de corrección de hash de Andrea)
  - factory/config/identity_keys.yaml.backup_before_rotation_20260826_145429
    (14:54:29)
  - factory/config/identity_keys.yaml.backup_20260826_150416_e2e (15:04:16)
  - factory/config/identity_keys.yaml (vigente, 15:04:16, hash verificado
    contra .secrets/gmp_factory/*)
  - .secrets/gmp_factory/cesar_identity.key,
    .secrets/gmp_factory/andrea_reviewer_identity.key (0600, mtime
    15:04:16)
  - ~/.bash_history líneas ~649 (búsqueda filesystem de key original),
    ~695-753 (RECREAR X-IDENTITY-KEYS PARA E2E, con set +o history antes
    de pegar keys por read -s), ~997-1190 (ROTACION CONTROLADA),
    ~1191-1409 (ROTACION DEFINITIVA + cat de las dos keys nuevas)
  - docker logs factory-api -t --since 2026-08-26: 12 "Application startup
    complete" en el día, 4 correlacionados 1:1 con backups/rotación

UNVERIFIED_POINTS=
  - Mecanismo exacto que produjo la rotación final (~15:04:16) y colocó
    las keys en .secrets/gmp_factory/: no hay comando en bash_history que
    lo explique; se infiere pero no se confirma el "cómo".
  - Resultado real (found/not found) de la búsqueda filesystem-wide de la
    key original de Cesar antes de la primera rotación (el output de ese
    script no quedó en bash_history).
  - Si los restarts de factory-api posteriores a 15:10:43 (16:00 en
    adelante) tienen alguna relación con identidad o son puramente por
    cambios de código sin commitear.
  - Contenido/resultado del chequeo FACTORY_API_KEY_MATCH (bloque previo a
    la primera rotación) -- el output no quedó registrado.
```

## Estado

Investigación cerrada. No se tomó ninguna acción correctiva como parte de
esta corrida (no se rotaron keys, no se tocó `.secrets`, no hubo restart,
no hubo commit). Queda pendiente de decisión de Cesar/Capa 9:

- Si se documenta formalmente el path `.secrets/gmp_factory/` como
  almacenamiento estándar de X-Identity-Key (hoy no aparece referenciado
  en ningún código ni doc del repo, solo existe como hecho en el
  filesystem).
- Si se requiere un procedimiento operativo escrito que impida el patrón
  de `cat` a terminal visto en el bloque "ROTACION DEFINITIVA" (usar
  siempre `read -s` + traslado directo a almacenamiento seguro, nunca
  imprimir la key para "confirmarla").
