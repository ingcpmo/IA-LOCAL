# CHECKPOINT DE RETIRO — hotelbot/ (baseline)
Generado automáticamente (solo lectura) — 2026-08-25T23:01:04Z

```
=== SNAPSHOT baseline @ 2026-08-25T23:00:59Z ===

--- 1. DOCKER: contenedores completos ---
aria-orchestrator	fedea2eb7517	Up 24 minutes (healthy)
aria-celery-worker	2c3cd7b49b0a	Up 24 minutes (healthy)
aria-ai-engine	8b699158b3c2	Up 24 minutes (healthy)
aria-postgres-1	postgres:16-alpine	Up 24 minutes (healthy)
aria-redis-1	redis:7-alpine	Up 24 minutes (healthy)
aria-tts	0b2c70d67b71	Up 24 minutes (healthy)
aria-ollama	b166ed16ab6e	Up 24 minutes (healthy)
aria-asterisk	39a3b3be4f1a	Restarting (1) 38 seconds ago
gmp-api	ing_cpmo-api	Up 24 hours
gmp-postgres	postgres:16-alpine	Up 24 hours (healthy)
gmp-redis	redis:7-alpine	Up 24 hours (healthy)
factory-api	factory-factory-api	Up 24 hours
oos_hplc_investigator_api	oos_hplc_investigator-oos_hplc_investigator_api	Up 24 hours
lab_qc_project_api	lab_qc_project-lab_qc_project_api	Up 24 hours
lab_qc_project_postgres	57c72fd2a128	Up 24 hours (healthy)
lab_qc_project_redis	6ab0b6e73817	Up 24 hours (healthy)
oos_hplc_investigator_postgres	57c72fd2a128	Up 24 hours (healthy)
oos_hplc_investigator_redis	6ab0b6e73817	Up 24 hours (healthy)

--- 1b. DOCKER: labels compose de cada contenedor ---
/aria-orchestrator | project=aria | working_dir=/home/ing_cpmo/ARIA/deploy | config_files=/home/ing_cpmo/ARIA/deploy/docker-compose.yml
/aria-celery-worker | project=aria | working_dir=/home/ing_cpmo/ARIA/deploy | config_files=/home/ing_cpmo/ARIA/deploy/docker-compose.yml
/aria-ai-engine | project=aria | working_dir=/home/ing_cpmo/ARIA/deploy | config_files=/home/ing_cpmo/ARIA/deploy/docker-compose.yml
/aria-postgres-1 | project=aria | working_dir=/home/ing_cpmo/ARIA/deploy | config_files=/home/ing_cpmo/ARIA/deploy/docker-compose.yml
/aria-redis-1 | project=aria | working_dir=/home/ing_cpmo/ARIA/deploy | config_files=/home/ing_cpmo/ARIA/deploy/docker-compose.yml
/aria-tts | project=aria | working_dir=/home/ing_cpmo/ARIA/deploy | config_files=/home/ing_cpmo/ARIA/deploy/docker-compose.yml
/aria-ollama | project=aria | working_dir=/home/ing_cpmo/ARIA/deploy | config_files=/home/ing_cpmo/ARIA/deploy/docker-compose.yml
/aria-asterisk | project=aria | working_dir=/home/ing_cpmo/ARIA/deploy | config_files=/home/ing_cpmo/ARIA/deploy/docker-compose.yml
/gmp-api | project=ing_cpmo | working_dir=/home/ing_cpmo | config_files=/home/ing_cpmo/docker-compose.yml
/gmp-postgres | project=ing_cpmo | working_dir=/home/ing_cpmo | config_files=/home/ing_cpmo/docker-compose.yml
/gmp-redis | project=ing_cpmo | working_dir=/home/ing_cpmo | config_files=/home/ing_cpmo/docker-compose.yml
/factory-api | project=factory | working_dir=/home/ing_cpmo/factory | config_files=/home/ing_cpmo/factory/docker-compose.factory.yml
/oos_hplc_investigator_api | project=oos_hplc_investigator | working_dir=/home/ing_cpmo/factory/deployments/oos_hplc_investigator | config_files=/home/ing_cpmo/factory/deployments/oos_hplc_investigator/docker-compose.yml
/lab_qc_project_api | project=lab_qc_project | working_dir=/home/ing_cpmo/factory/deployments/lab_qc_project | config_files=/home/ing_cpmo/factory/deployments/lab_qc_project/docker-compose.yml
/lab_qc_project_postgres | project=lab_qc_project | working_dir=/home/ing_cpmo/factory/deployments/lab_qc_project | config_files=/home/ing_cpmo/factory/deployments/lab_qc_project/docker-compose.yml
/lab_qc_project_redis | project=lab_qc_project | working_dir=/home/ing_cpmo/factory/deployments/lab_qc_project | config_files=/home/ing_cpmo/factory/deployments/lab_qc_project/docker-compose.yml
/oos_hplc_investigator_postgres | project=oos_hplc_investigator | working_dir=/home/ing_cpmo/factory/deployments/oos_hplc_investigator | config_files=/home/ing_cpmo/factory/deployments/oos_hplc_investigator/docker-compose.yml
/oos_hplc_investigator_redis | project=oos_hplc_investigator | working_dir=/home/ing_cpmo/factory/deployments/oos_hplc_investigator | config_files=/home/ing_cpmo/factory/deployments/oos_hplc_investigator/docker-compose.yml

--- 1c. DOCKER: bind mounts de todos los contenedores ---








gmp-api: /home/ing_cpmo/data -> /app/data
gmp-api: /home/ing_cpmo/.cache/chroma -> /root/.cache/chroma
gmp-api: /home/ing_cpmo/app -> /app/app
gmp-api: /home/ing_cpmo/knowledge -> /app/knowledge

gmp-postgres: /home/ing_cpmo/scripts/sql/init.sql -> /docker-entrypoint-initdb.d/init.sql


factory-api: /home/ing_cpmo/backups/factory -> /app/backups_factory
factory-api: /home/ing_cpmo/factory -> /app/factory
factory-api: /home/ing_cpmo/GMPAI -> /home/ing_cpmo/GMPAI

oos_hplc_investigator_api: /home/ing_cpmo/factory/deployments/oos_hplc_investigator/knowledge -> /app/knowledge
oos_hplc_investigator_api: /home/ing_cpmo/factory/deployments/oos_hplc_investigator/app -> /app/app
oos_hplc_investigator_api: /home/ing_cpmo/factory/deployments/oos_hplc_investigator/data -> /app/data

lab_qc_project_api: /home/ing_cpmo/factory/deployments/lab_qc_project/data -> /app/data
lab_qc_project_api: /home/ing_cpmo/factory/deployments/lab_qc_project/knowledge -> /app/knowledge
lab_qc_project_api: /home/ing_cpmo/factory/deployments/lab_qc_project/app -> /app/app






--- 1d. DOCKER: networks ---
NETWORK ID     NAME                                 DRIVER    SCOPE
6066dad0eba6   bridge                               bridge    local
50c3397a391b   factory_default                      bridge    local
edffca0921d8   host                                 host      local
1c74992dcf55   hotelbot_aria_net                    bridge    local
8e9fdfee5915   ing_cpmo_default                     bridge    local
c6e7baa9186f   lab_qc_project_lab_qc_project_net    bridge    local
90c39b64c1d5   none                                 null      local
9dfd4e1980a3   oos_hplc_investigator_oos_hplc_net   bridge    local

--- 1e. DOCKER: volumes ---
DRIVER    VOLUME NAME
local     43ab5fc9d32f84c3bd7e9432d5d4aae4d3d192bd822ec7669e5bc60fed814b68
local     44c9d6f6004ffbb7c89dcbc1b4cd90f1801ff1b461d557c0a997c9b8ec4a382f
local     hotelbot_asterisk_logs
local     hotelbot_asterisk_sounds
local     hotelbot_asterisk_spool
local     hotelbot_ollama_models
local     hotelbot_postgres_data
local     hotelbot_redis_data
local     hotelbot_vosk_models
local     ing_cpmo_chroma_cache
local     ing_cpmo_gmp_postgres_data
local     ing_cpmo_gmp_redis_data
local     lab_qc_project_lab_qc_project_pgdata
local     oos_hplc_investigator_oos_hplc_pgdata
local     src_ollama_data
local     src_postgres_data
local     src_redis_data

--- 2. ARIA: origen del proyecto ---
NAME                    STATUS                      CONFIG FILES
aria                    restarting(1), running(7)   /home/ing_cpmo/ARIA/deploy/docker-compose.yml
factory                 running(1)                  /home/ing_cpmo/factory/docker-compose.factory.yml
ing_cpmo                running(3)                  /home/ing_cpmo/docker-compose.yml
lab_qc_project          running(3)                  /home/ing_cpmo/factory/deployments/lab_qc_project/docker-compose.yml
oos_hplc_investigator   running(3)                  /home/ing_cpmo/factory/deployments/oos_hplc_investigator/docker-compose.yml

--- 2b. ARIA: health de servicios reales ---
/aria-ai-engine: status=running health=healthy exitcode=0
/aria-tts: status=running health=healthy exitcode=0
/aria-orchestrator: status=running health=healthy exitcode=0
/aria-celery-worker: status=running health=healthy exitcode=0
/aria-ollama: status=running health=healthy exitcode=0
/aria-asterisk: status=restarting health=unhealthy exitcode=1
/aria-postgres-1: status=running health=healthy exitcode=0
/aria-redis-1: status=running health=healthy exitcode=0

--- 3. HOST: systemd, cron, procesos, scripts referenciando hotelbot ---
systemd:
crontab:
  sin coincidencias
procesos:
ing_cpmo 2558968  0.0  0.0   4484  3204 ?        Ss   23:00   0:00 /bin/bash -c source /home/ing_cpmo/.claude/shell-snapshots/snapshot-bash-1787675160835-nga4sw.sh 2>/dev/null || true && shopt -u extglob 2>/dev/null || true && { \builtin unalias -- 'unsetenv'; \builtin unset -f -- 'unsetenv'; } >/dev/null 2>&1 || true && eval 'bash /home/ing_cpmo/scripts/ops/checkpoint_hotelbot_decommission.sh baseline' < /dev/null && pwd -P >| /tmp/claude-a4b4-cwd
ing_cpmo 2558970  1.6  0.0   4484  3152 ?        S    23:00   0:00 bash /home/ing_cpmo/scripts/ops/checkpoint_hotelbot_decommission.sh baseline
scripts operativos:
/home/ing_cpmo/scripts/ops/checkpoint_hotelbot_decommission.sh
/home/ing_cpmo/scripts/11_ui_precheck.sh

--- 4. FILESYSTEM/GIT: estado de hotelbot/ ---
git status (dentro del propio checkout):
 M docker-compose.yml
?? README_ESTADO_REAL.md
HEAD:
6a5e741 fix(decision_migration): eliminar colision de decision_instance_id entre Sistema A/B

=== FIN SNAPSHOT ===
```

## Sin diferencia contra baseline (o es la propia captura de baseline).

## Veredicto determinístico
HOTELBOT_PATH_REFERENCES_FOUND = 0
(cuenta líneas del snapshot que mencionan /home/ing_cpmo/hotelbot -- 0 es lo esperado si ya no participa en runtime activo. Este script NO decide SAFE_TO_DECOMMISSION_HOTELBOT -- eso requiere revisión humana de este reporte por Cesar.)
