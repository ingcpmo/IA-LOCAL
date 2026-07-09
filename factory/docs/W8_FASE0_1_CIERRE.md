# W8 Fase 0.1 — Cierre parcial: Fase 1 desplegada con certificado real, Fase 2 bloqueada

**Fecha:** 2026-07-09. Diseño aprobado conceptualmente por Cesar (opción C:
reverse proxy TLS + auth). Ejecución con autonomía técnica, deteniéndose
solo ante un bloqueo real de acceso (según instrucción explícita de Cesar
en dos rondas de esta misma sesión).

## 1. Historial de la topología (por qué se corrigió dos veces)

1. **v1 (descartada):** IP pública desnuda como nombre de sitio Caddy.
   Sin SNI (el cliente no manda SNI válida para IPs, RFC 6066), Caddy
   resuelve el certificado por la IP **local** del socket, que tras el
   NAT 1:1 de GCP nunca es la IP pública — el certificado nunca calzaría.
   Detectado y corregido en el primer despliegue.
2. **v2 (descartada, primer cierre de la sesión anterior):** nombres
   `*.gmp-factory.local` + `tls internal` (CA propia de Caddy). Funcionaba
   técnicamente (SNI real), pero Cesar señaló correctamente que un
   certificado autofirmado no es una solución final aceptable y que
   `.local` no debía asumirse válido para acceso externo sin verificar.
   Verificado: el certificado autofirmado exige un paso de confianza
   manual en cada navegador cliente — no es sostenible.
3. **v3 (ACTUAL):** nombres `*.35-243-160-0.sslip.io` (DNS público
   wildcard, gratuito, sin registro) + certificado real de **Let's
   Encrypt**, obtenido automáticamente por Caddy vía ACME HTTP-01. Sin
   avisos de navegador, sin pasos de confianza manual, renovación
   automática. Ver `factory/scripts/ops/reverse-proxy/README.md` §Topología
   para el detalle completo y la evidencia de por qué se descartaron v1/v2.

## 2. Qué está desplegado (v3, versión de repo v1.1.0)

| Sitio | Backend | Auth extra |
|---|---|---|
| `mission-control.35-243-160-0.sslip.io` | factory-api (9000) | Basic Auth |
| `gmp-api.35-243-160-0.sslip.io` | gmp-api (8000) | ninguna (x-api-key propia) |
| `lab-qc.35-243-160-0.sslip.io` | lab_qc_project (8101) | ninguna |
| `oos-hplc.35-243-160-0.sslip.io` | oos_hplc_investigator (8102) | ninguna |

Certificados **reales, emitidos y confirmados**: los 4 con
`issuer=Let's Encrypt`, validados con `openssl x509` y con `curl` **sin**
`-k`/`-insecure` (prueba de que la cadena de confianza es pública, no
autofirmada). Vigencia 90 días, renovación automática (requiere que el
puerto 80 siga abierto de forma permanente, no solo para la emisión
inicial).

## 3. Validado (Fase 1, con los puertos antiguos aún abiertos)

- `caddy validate` limpio; servicio `enabled` + `active`.
- Mission Control vía proxy: sin credenciales → 401; credenciales
  correctas → 200; credenciales incorrectas → 401.
- gmp-api, lab_qc, oos_hplc vía proxy: respuesta **idéntica** a la directa
  (`/health` byte a byte igual; 404 en raíz de oos_hplc confirmado igual
  en ambos caminos, no es regresión del proxy).
- `aria-*` (6 contenedores) y `hotelbot-*` (2) sin tocar, `Up`/`healthy`.
- Conectividad interna Docker (DNS de servicio, `gmp-api`→`gmp-postgres`/
  `gmp-redis`) intacta.
- `factory_selfcheck.sh`: **PASS=4, FAIL=0**, 441 tests, cadena de auditoría
  íntegra (mismo resultado que antes de esta fase, repetido dos veces en
  esta sesión tras cada cambio de topología).
- Repo como fuente de verdad: `factory/scripts/ops/reverse-proxy/`
  (Caddyfile v1.1.0, `SHA256SUMS`, `README.md`, `verify_installed.sh`).
  `verify_installed.sh` → **PASS 4/4**.

### Rollback — distinción exacta entre Fase 1 y Fase 2

- **Rollback de Fase 1 (Caddy): PROBADO EN VIVO dos veces** (una con la
  topología `.local`, repetido con la topología final de Let's Encrypt).
  `systemctl disable --now caddy` libera 443 al instante; verificado en
  ambas pruebas que el acceso directo antiguo (8000/9000/8101/8102) no se
  ve afectado en ningún momento. `systemctl enable --now caddy` restaura
  el proxy con Mission Control respondiendo 200 de nuevo.
- **Rollback de Fase 2 (DROP de 8000/9000/8101/8102): PENDIENTE.** Fase 2
  no se ha ejecutado todavía (ver §4), por lo tanto su rollback tampoco se
  ha podido probar. Se probará en la misma sesión en que se aplique Fase 2,
  siguiendo el mismo patrón usado en W8 Fase 0 (quitar reglas → confirmar
  restauración → reponer → confirmar bloqueo).

## 4. BLOQUEO real — Fase 2 (cierre de puertos directos) NO EJECUTADA

Evidencia exacta, verificada con un vantage point externo real (fuera de
la VM), reconfirmada tras el cambio a Let's Encrypt:

- **Puerto 80: alcanzable desde internet.** Prueba objetiva: los 4
  certificados fueron emitidos por Let's Encrypt vía reto ACME HTTP-01,
  que solo se completa si los servidores de validación de Let's Encrypt
  (en internet) pudieron conectar al puerto 80 de esta VM.
- **Puerto 443: NO alcanzable desde internet.** `ECONNREFUSED` en una
  prueba directa repetida después de la emisión de certificados.

UFW e `iptables` locales permiten ambos puertos (verificado). El
`gcloud` de esta VM está autenticado (cuenta de servicio de la instancia)
pero sin scopes para leer ni modificar reglas de firewall — confirmado de
nuevo en esta sesión. El bloqueo es exclusivamente el **firewall de VPC de
GCP**.

**Aplicar ahora las reglas DROP de Fase 2 dejaría a Cesar sin acceso a
Mission Control** hasta abrir 443 — es exactamente el escenario de lockout
que se pidió evitar. Se detiene aquí por instrucción explícita, por
segunda vez en esta sesión.

**Único comando pendiente de Cesar** (instancia `ivr-ia`, zona
`us-east1-b`, red `default`, sin network tags):

```bash
gcloud compute firewall-rules create allow-caddy-https \
  --network=default --direction=INGRESS --action=ALLOW \
  --rules=tcp:443 --source-ranges=0.0.0.0/0
```

Detalle completo, incluida la sugerencia de revisar si ya existe una regla
editable en vez de crear una nueva, en
`factory/scripts/ops/reverse-proxy/README.md` §"Bloqueo activo".

## 5. Evidencia exacta sobre las API keys expuestas (corrección)

Afirmación anterior ("4 API keys viajaron en claro") verificada con
evidencia, no asumida. Se compararon los valores por **hash SHA-256** (sin
exponer texto plano en ningún momento) para confirmar que son 4 secretos
realmente distintos y no el mismo valor repetido:

| Servicio | Variable | Hash SHA-256 (primeros 16 car.) | ¿Exigido por el servicio? |
|---|---|---|---|
| gmp-api | `GMP_API_KEY` | `6f3a78248400cd8e…` | Sí — `401` sin cabecera |
| lab_qc_project_api | `GMP_API_KEY` | `f0c07670badbd888…` | Sí — `401` sin cabecera |
| oos_hplc_investigator_api | `GMP_API_KEY` | `dce535417be9c18c…` | Sí — `401` sin cabecera |
| factory-api | `FACTORY_API_KEY` | `3727e8137d54b4c6…` | Sí (validación por header `x-api-key` en `factory/api/main.py`) |

Confirmado: **4 valores distintos** (no el mismo secreto reutilizado bajo
el mismo nombre de variable), los 4 exigidos activamente por su servicio,
los 4 servidos hasta ahora solo por HTTP plano en 8000/9000/8101/8102.
`APP_SECRET_KEY` (presente en `gmp-api`) se investigó aparte: no se
encontró ninguna referencia a esa variable en el código de la aplicación
(`/home/ing_cpmo/app/`), por lo que **no se incluye** en la afirmación de
"viajó por HTTP" — no hay evidencia de que se use en tráfico de red.

**Rotación: sigue pendiente**, condicionada a que Fase 2 esté cerrada (no
tiene sentido rotar mientras el tráfico plano sigue siendo posible).

## 6. Qué falta para el cierre total de F0.1 (siguiente sesión)

1. Cesar ejecuta el comando de §4 (abrir 443 en la VPC).
2. Confirmar alcanzabilidad externa real de 443 (repetir la prueba que hoy
   dio `ECONNREFUSED`) y probar desde un navegador real: Mission Control,
   autenticación, las 4 rutas.
3. Extender `docker-user-hardening.sh` a v1.1.0 (DROP de
   8000/9000/8101/8102 por `ens4`), probar ese rollback específico
   (pendiente, ver §3), y repetir selfcheck + verificación de contenedores.
4. Rotar las 4 API keys de §5 y confirmar que las nuevas funcionan
   únicamente por el flujo HTTPS.

## 7. Estado

Fase 0.1 **parcialmente cerrada, en mejor punto que el cierre anterior**:
certificado real de confianza pública desplegado y verificado (no
autofirmado), topología corregida dos veces con evidencia en cada paso,
rollback de Fase 1 probado dos veces, evidencia exacta de las API keys
documentada por hash. El único punto pendiente es una acción de Cesar
fuera del alcance de esta VM (abrir 443 en la VPC). Ningún comportamiento
previamente validado (W8 Fase 0, selfcheck, `aria-*`, `hotelbot-*`, acceso
directo actual de Cesar) se vio afectado en ningún momento de esta sesión.
