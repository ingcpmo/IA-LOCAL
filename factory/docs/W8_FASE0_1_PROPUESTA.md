# W8 Fase 0.1 — Diseño: acceso remoto seguro a Mission Control y APIs

**Estado:** DISEÑO v2 (2026-07-09). No implementado. Requiere aprobación de
Cesar. Continúa `W8_FASE0_HARDENING.md` (cerrada, `e59a553` + `7b7d4eb`):
la superficie de **datos** está cerrada; esta fase cierra la superficie
**HTTP** (riesgo residual §4.2).

## 1. El problema

Cuatro APIs (8000 gmp-api · 9000 factory-api/Mission Control · 8101 lab_qc ·
8102 oos_hplc) publicadas a internet **sin TLS**: la `x-api-key` viaja en
claro en cada uso de la consola, con escaneo externo activo documentado y
sin límite de intentos. Cesar accede hoy **directo por IP pública**
(`http://35.243.160.0:9000/...`), posiblemente desde IP de cliente
**dinámica**.

## 2. Criterios de diseño (fijados por Cesar, 2026-07-09)

Sostenibilidad · TLS · autenticación · riesgo de lockout · acceso actual por
IP pública · IP de cliente posiblemente dinámica · rollback · impacto sobre
8000/9000/8101/8102.

## 3. Opciones evaluadas contra los criterios

| Criterio | A: túnel SSH | B: allowlist IP | C: proxy TLS |
|---|---|---|---|
| TLS / clave cifrada | ✅ (cifrado SSH) | ❌ sigue en claro | ✅ |
| Autenticación | clave SSH (fuerte) | ninguna nueva | TLS + basic auth + x-api-key |
| IP cliente dinámica | ✅ indiferente | ❌ **lockout de UI en cada cambio** | ✅ indiferente |
| Lockout | mínimo (SSH es la vía de rescate ya existente) | medio (UI cae al cambiar IP; SSH sobrevive) | bajo con despliegue por fases (§5) |
| Sostenible (uso diario navegador) | ⚠️ túnel manual cada vez | ✅ hasta que cambie la IP | ✅ URL https estable |
| Rollback | trivial | trivial (quitar reglas) | trivial (quitar 4 reglas DROP + parar proxy) |
| Mantenimiento | cero | cero | un servicio (Caddy renueva certificados solo) |

**B queda descartada como solución** por el criterio de IP dinámica: es la
única opción cuyo modo de fallo es exactamente el lockout que se quiere
evitar. A es máxima seguridad pero no cumple "sostenible" como vía diaria;
queda como **vía de rescate** (ya existe, no hay que construir nada).

## 4. Recomendación principal: C — reverse proxy Caddy con TLS + auth

### 4.1 Componentes
- **Nombre DNS** apuntando a `35.243.160.0` (requisito para Let's Encrypt).
  Opciones: subdominio propio de Cesar (mejor) o DuckDNS gratuito. La IP de
  la **VM** es estable (la dinámica es la del cliente, que a C no le afecta).
  Sin nombre DNS: fallback a certificado autofirmado de Caddy (cifra igual;
  el navegador avisa una vez).
- **Caddy en el host** (binario systemd, puerto 443; hoy libre). Un solo
  Caddyfile con 4 rutas → `127.0.0.1:9000/8000/8101/8102`. Caddy obtiene y
  **renueva solo** el certificado: mantenimiento ≈ cero, criterio de
  sostenibilidad.
- **Autenticación en capas**: TLS (cifra la `x-api-key` existente, que se
  conserva) + `basic_auth` de Caddy (bcrypt) delante de Mission Control como
  segunda barrera para la UI. Rate limiting básico opcional después (no es
  bloqueante).
- **Cierre de los puertos directos**: 4 reglas DROP para 8000/9000/8101/8102
  entrantes por `ens4`, **extendiendo el mecanismo ya validado y versionado**
  (`docker-user-hardening.sh` → v1.1.0 en `factory/scripts/ops/
  host-hardening/`, nuevo SHA-256, reinstalación documentada). Ventajas:
  no se toca ningún compose (el base está prohibido — 8000 no puede
  rebindearse de otra forma), un solo mecanismo para toda la política, y el
  proxy en el host sigue llegando por loopback.

### 4.2 Impacto sobre 8000/9000/8101/8102
- Desde internet: solo `https://<nombre>/...` (443, Caddy). Los 4 puertos
  directos dejan de responder desde fuera.
- Desde el host y entre contenedores: **sin cambio** (las reglas solo
  aplican a `ens4`, patrón ya probado en F0).
- Cero cambios en código de aplicación y cero cambios en composes.

### 4.3 Riesgo de lockout y mitigación (despliegue por fases)
1. **F1** — DNS + Caddy en 443 con las 4 rutas. Los puertos directos siguen
   abiertos: si el proxy fallara, nada se pierde. Verificar UI y APIs vía
   https (incluido flujo completo de Mission Control).
2. **F2** — Solo tras verificar F1: añadir las 4 reglas DROP (script
   v1.1.0). Ventana de comprobación inmediata.
3. **Vía de rescate permanente**: SSH (22) no depende de Docker ni de Caddy
   (UFW/VPC, intacto). Ante cualquier fallo:
   `ssh -L 9000:127.0.0.1:9000 ing_cpmo@35.243.160.0` y la consola vuelve
   por `http://localhost:9000`. Peor caso GCP: consola serie/IAP.
4. **Rollback total** (< 1 min): quitar las 4 reglas DROP (o reinstalar
   script v1.0.0) → estado actual exacto; `systemctl stop caddy` si hiciera
   falta. Nada del comportamiento validado en F0 se modifica.

### 4.4 Post-implementación obligatorio
**Rotar todas las API keys** (base, factory, 2 custom): viajaron en claro y
deben considerarse expuestas. Solo tiene sentido DESPUÉS de que el TLS esté
activo. Registrar la rotación en el informe de cierre.

## 5. Decisiones que necesita tomar Cesar antes de implementar
1. Aprobar el diseño C (o pedir A como alternativa).
2. **Nombre DNS**: ¿subdominio de dominio propio, DuckDNS, o autofirmado?
3. Credencial `basic_auth` para la UI (se genera en la implementación; no se
   commitea en claro).

## 6. Lo que esta fase NO hace
No toca `docker-compose.yml`/`.env` base (decisión vigente: "solo
firewall"); `gmp-redis` sigue sin `requirepass`, tapado por DOCKER-USER.
Revisitar cuando se autorice trabajo sobre el stack base.
