# W8 Fase 0.1 — Cierre parcial: Fase 1 desplegada, Fase 2 bloqueada

**Fecha:** 2026-07-09. Diseño aprobado conceptualmente por Cesar (opción C:
reverse proxy TLS + auth). Ejecución con autonomía técnica, deteniéndose
solo ante un bloqueo real de acceso (según instrucción explícita).

## 1. Qué se implementó

Reverse proxy **Caddy 2.6.2** en el host (paquete Debian, no contenedor),
terminando TLS en el puerto **443** con 4 sitios distinguidos por nombre
(SNI/Host) — ver `factory/scripts/ops/reverse-proxy/README.md` para la
topología completa y por qué se descartó usar la IP pública como nombre de
sitio (NAT 1:1 de GCP invalida ese enfoque; documentado con la prueba que
lo demostró).

| Sitio | Backend | Auth extra |
|---|---|---|
| `mission-control.gmp-factory.local` | factory-api (9000) | Basic Auth |
| `gmp-api.gmp-factory.local` | gmp-api (8000) | ninguna (x-api-key propia) |
| `lab-qc.gmp-factory.local` | lab_qc_project (8101) | ninguna |
| `oos-hplc.gmp-factory.local` | oos_hplc_investigator (8102) | ninguna |

TLS vía CA local de Caddy (`tls internal`, `skip_install_trust`); sin
dominio público disponible, este es el fallback ya documentado en el
diseño v2. Certificado autofirmado: el navegador de Cesar mostrará un
aviso la primera vez (o puede importar la CA — instrucciones en el README).

## 2. Validado (Fase 1, con los puertos antiguos aún abiertos)

- `caddy validate` limpio; servicio `enabled` + `active`.
- Mission Control vía proxy: sin credenciales → 401; credenciales correctas
  → 200; credenciales incorrectas → 401.
- gmp-api, lab_qc, oos_hplc vía proxy: respuesta **idéntica** a la directa
  (`/health` byte a byte igual; 404 en raíz de oos_hplc confirmado igual
  en ambos caminos, no es regresión del proxy).
- `aria-*` (6 contenedores) y `hotelbot-*` (2) sin tocar, `Up`/`healthy`.
- Conectividad interna Docker (DNS de servicio, `gmp-api`→`gmp-postgres`/
  `gmp-redis`) intacta.
- `factory_selfcheck.sh`: **PASS=4, FAIL=0**, 441 tests, cadena de auditoría
  315 entradas íntegra (mismo resultado que antes de esta fase).
- **Rollback de Caddy probado en vivo**: `systemctl disable --now caddy`
  libera 443 al instante; acceso directo antiguo (8000/9000/8101/8102)
  verificado sin ningún efecto durante la prueba; `systemctl enable --now
  caddy` restaura el proxy con Mission Control respondiendo 200 de nuevo.
- Repo como fuente de verdad: `factory/scripts/ops/reverse-proxy/`
  (Caddyfile, `SHA256SUMS`, `README.md`, `verify_installed.sh`).
  `verify_installed.sh` → **PASS 4/4** (hash, enabled, active, puerto
  escuchando).

## 3. BLOQUEO real — Fase 2 (cierre de puertos directos) NO EJECUTADA

Prueba de alcanzabilidad desde un punto de vista externo real (fuera de la
VM): **443 responde `ECONNREFUSED`**; 8000/9000/8101/8102 sí responden.
UFW e `iptables` locales permiten 443 (verificado); el bloqueo está en el
**firewall de VPC de GCP**, que hoy solo permite los 4 puertos antiguos.
El `gcloud` de esta VM no tiene scopes para leer ni modificar reglas de
firewall (limitación ya conocida desde Fase 0).

**Aplicar ahora las reglas DROP de Fase 2 dejaría a Cesar sin acceso a
Mission Control** hasta abrir 443 — es exactamente el escenario de lockout
que se pidió evitar. Se detiene aquí por instrucción explícita.

**Acción pendiente de Cesar** (única cosa que falta para cerrar del todo):
abrir `tcp:443` entrante en el firewall de VPC. Comando e instrucciones
exactas en `factory/scripts/ops/reverse-proxy/README.md` §"Bloqueo activo"
(instancia `ivr-ia`, zona `us-east1-b`, red `default`, sin network tags —
confirmado vía metadata de la instancia sin necesitar scopes de `gcloud`).

## 4. Qué falta para el cierre total de F0.1 (siguiente sesión)

1. Cesar abre 443 en la VPC.
2. Confirmar alcanzabilidad externa real (repetir la prueba que hoy dio
   `ECONNREFUSED`).
3. Cesar configura las 4 líneas de `/etc/hosts` en su máquina (README) y
   confirma acceso a Mission Control por HTTPS con su usuario/clave.
4. Solo entonces: extender `docker-user-hardening.sh` a v1.1.0 (DROP de
   8000/9000/8101/8102 por `ens4`), probar el rollback de esas reglas
   específicas (quitar/reponer, como se hizo en Fase 0), y verificar de
   nuevo selfcheck + los 7 puntos de este informe.
5. Rotar las 4 API keys (viajaron en claro hasta ahora) — tiene sentido
   solo después de que el TLS sea el único camino externo.

## 5. Estado

Fase 0.1 **parcialmente cerrada**: infraestructura de proxy TLS + auth
desplegada, probada y versionada (repo = fuente de verdad, hashes
verificados). El objetivo final — eliminar el acceso HTTP plano — **no**
se ha completado porque cortar los puertos antiguos ahora causaría
lockout real. Ningún comportamiento previamente validado (W8 Fase 0,
selfcheck, `aria-*`, `hotelbot-*`, acceso directo actual de Cesar) se vio
afectado en ningún momento de esta sesión.
