# RE-AUDITORÍA PROGRAMADA — SAFE_TO_DECOMMISSION_HOTELBOT
Programada por instrucción explícita de Cesar (Capa 9), 2026-08-25.
**El desacople ARIA/hotelbot Fases 1-3 queda cerrado — no se reabre.**
Este documento programa únicamente la verificación sostenida en el
tiempo de que `/home/ing_cpmo/hotelbot` ya no participa en ningún
runtime activo, sin decidir su retiro.

**Fuera de alcance de esta tarea (explícitamente excluido):** reparación
de `aria-asterisk`, Decisión 2 de GMP AI Factory, `test_status_risks.py`,
"Graphify", y cualquier otro cambio de arquitectura.

──────────────────────────────────────────────────────────────────────────────
MECANISMO
──────────────────────────────────────────────────────────────────────────────

`docker compose ls`/agentes en la nube NO tienen acceso a este host — se
descartó la skill `/schedule` (lanza sesiones cloud sin Docker/filesystem
real). El mecanismo correcto es local: `crontab` (ya en uso por este
proyecto para `backup.sh`/`watch_source_origin_status.sh`), invocando un
script 100% determinístico y de solo lectura —
`scripts/ops/checkpoint_hotelbot_decommission.sh` — sin necesidad de
juicio de LLM en el momento de la ejecución (los 5 bloques de
verificación son comandos read-only fijos: `docker inspect`, `systemctl`,
`crontab -l`, `ps aux`, `git status`).

**Baseline capturado inmediatamente después del cutover** (2026-08-25T23:00:59Z,
~24 min después de `orchestrator StartedAt=2026-08-25T22:36:06Z`):
`docs_plan/DECOMMISSION_CHECKPOINT_baseline_20260825T230059Z.md`.
Resultado: `HOTELBOT_PATH_REFERENCES_FOUND = 0` — ninguna referencia
activa a `/home/ing_cpmo/hotelbot` en labels de Compose, bind mounts,
systemd, cron, procesos, o config activa. (El único "match" de la
palabra "hotelbot" en el propio reporte es el nombre del script de
checkpoint, que contiene "hotelbot" en su propio nombre de archivo — no
es una referencia funcional, es cosmético, documentado aquí para que no
se lea como hallazgo.)

**Checkpoints programados vía `crontab` (auto-limpieza: cada entrada se
borra a sí misma de la crontab al ejecutarse una vez):**
```
CHECKPOINT 1 = 2026-08-26T22:36:00Z (T+24h desde el cutover)
CHECKPOINT 2 = 2026-08-28T22:36:00Z (T+72h desde el cutover)
```
Cada corrida:
1. Toma un snapshot completo (Docker: contenedores/labels/mounts/redes/
   volúmenes; ARIA: origen del compose + health; Host: systemd/cron/
   procesos/scripts; Filesystem/Git: estado de `hotelbot/`).
2. Compara contra el baseline línea por línea (`diff`).
3. Calcula `HOTELBOT_PATH_REFERENCES_FOUND` (conteo determinístico, no
   interpretativo).
4. Escribe `docs_plan/DECOMMISSION_CHECKPOINT_<label>_<timestamp>.md`.
5. Se auto-remueve de la crontab (no queda una entrada recurrente
   colgada).

**Ningún checkpoint borra `hotelbot/` automáticamente, pase lo que
pase.** El script solo mide y reporta — la decisión de retiro sigue
siendo exclusivamente humana, de Cesar, leyendo los 2 reportes.

`aria-asterisk`: el checkpoint reporta su estado (`status`/`health`/
`exitcode`) en cada corrida, sin comparación automática de "regresión"
— eso requiere lectura humana del diff contra el baseline (que ya
registra su estado post-cutover: `Restarting`/`exitcode` por la falta de
`/etc/asterisk-templates`, conocido y aceptado).

──────────────────────────────────────────────────────────────────────────────
ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
DECOUPLING_PHASES_1_3 = CERRADO, NO REABIERTO
BASELINE_CAPTURED = SI, docs_plan/DECOMMISSION_CHECKPOINT_baseline_20260825T230059Z.md
BASELINE_HOTELBOT_REFERENCES = 0
CHECKPOINT_1_SCHEDULED = 2026-08-26T22:36:00Z (crontab, auto-limpieza)
CHECKPOINT_2_SCHEDULED = 2026-08-28T22:36:00Z (crontab, auto-limpieza)
SCRIPT = scripts/ops/checkpoint_hotelbot_decommission.sh (solo lectura,
    sin capacidad de borrar/mover/detener nada)
AUTO_DELETE_HOTELBOT = NO, NUNCA, bajo ninguna condición de este mecanismo
DECISION_FINAL = pendiente de lectura humana de Cesar tras el Checkpoint 2,
    no automatizada
```
