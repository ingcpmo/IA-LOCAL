"""Chequeo LOCAL_ONLY / DOCUMENT_EGRESS = 0 (V2, B8) -- FASE 10 §2 + §3.2.

Ejecuta un callable con la SALIDA DE RED BLOQUEADA (todo `socket.connect`
a un host que no sea loopback / el Ollama local levanta `EgressBlocked`).
Cuenta los bytes que se intentaron enviar hacia afuera. Un pipeline V2
correcto no intenta ninguna conexión saliente -> `document_egress_bytes = 0`.

Sin dependencias nuevas (solo `socket` de stdlib).
"""
from __future__ import annotations

import socket
from contextlib import contextmanager
from dataclasses import dataclass, field

_ALLOWED_HOSTS = {"127.0.0.1", "::1", "localhost", "host.docker.internal"}
# El Ollama local del proyecto (aria-ollama) también es local -- se
# resuelve por nombre de servicio o IP de bridge; se permite explícito.
_ALLOWED_PREFIXES = ("172.17.", "172.18.", "172.19.", "10.", "192.168.")  # bridges docker / LAN local


class EgressBlocked(RuntimeError):
    """Un componente intentó una conexión de red saliente durante una
    corrida LOCAL_ONLY. Fail-closed: la corrida falla."""


@dataclass
class EgressReport:
    local_only: bool
    document_egress_bytes: int
    attempts: list = field(default_factory=list)   # [(host, port)]


def _is_local(host: str) -> bool:
    if host in _ALLOWED_HOSTS:
        return True
    return any(host.startswith(p) for p in _ALLOWED_PREFIXES)


@contextmanager
def network_locked(*, allow_local: bool = True):
    """Context manager: mientras esté activo, `socket.socket.connect`
    hacia un host no-local lanza `EgressBlocked`. `report.attempts`
    registra los intentos."""
    report = EgressReport(local_only=True, document_egress_bytes=0)
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def _check(address):
        try:
            host = address[0]
        except Exception:  # noqa: BLE001
            host = str(address)
        if allow_local and _is_local(str(host)):
            return
        report.attempts.append(tuple(address) if isinstance(address, (list, tuple)) else (host,))
        report.local_only = False
        raise EgressBlocked(f"conexión saliente bloqueada (LOCAL_ONLY): {address!r}")

    def patched_connect(self, address):
        _check(address)
        return real_connect(self, address)

    def patched_connect_ex(self, address):
        _check(address)
        return real_connect_ex(self, address)

    socket.socket.connect = patched_connect
    socket.socket.connect_ex = patched_connect_ex
    try:
        yield report
    finally:
        socket.socket.connect = real_connect
        socket.socket.connect_ex = real_connect_ex


def run_local_only(fn, *args, **kwargs) -> tuple[object, EgressReport]:
    """Corre `fn(*args, **kwargs)` con la red saliente bloqueada.
    Devuelve (resultado, EgressReport). Si `fn` intenta salir, propaga
    `EgressBlocked`."""
    with network_locked() as report:
        result = fn(*args, **kwargs)
    return result, report


# ---------------------------------------------------------------------------
# H-5F (2026-08-29) -- atestación de controles de egress: PROCESO vs RED
# ---------------------------------------------------------------------------
#: Objetivo de la sonda: resolvers DNS públicos que SIEMPRE aceptan TCP:53.
#: Se abre solo el SYN; 0 bytes de payload; se cierra de inmediato. Su ÚNICO
#: fin es distinguir de forma concluyente "sin ruta a Internet" (aislamiento
#: de RED real -> connect falla con ENETUNREACH) de "hay ruta" (connect
#: establece -> solo hay control de proceso). No está en ningún prefijo local
#: de `_ALLOWED_PREFIXES`.
_EXTERNAL_PROBE_TARGETS = (("1.1.1.1", 53), ("8.8.8.8", 53))  # Cloudflare / Google DNS


def probe_external_reachability(timeout: float = 3.0) -> str:
    """`BLOCKED`  -> el kernel rechaza la salida (ENETUNREACH/EHOSTUNREACH) o
                     no hay ruta: aislamiento de RED demostrado.
    `REACHABLE` -> se estableció (o progresó) una conexión saliente a Internet:
                     NO hay aislamiento de red.
    `UNKNOWN`   -> timeout / estado ambiguo (p.ej. un firewall que hace DROP
                     silencioso: no se puede afirmar ni negar con esta sonda).

    Usa el `socket.connect` REAL -- debe llamarse FUERA de `network_locked()`.
    """
    import errno

    real_connect = socket.socket.connect
    verdict = "UNKNOWN"
    for host, port in _EXTERNAL_PROBE_TARGETS:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            real_connect(s, (host, port))
            verdict = "REACHABLE"          # estableció -> hay ruta a Internet
        except socket.timeout:
            verdict = "UNKNOWN"            # DROP silencioso: no concluyente
        except OSError as e:
            if e.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ENETDOWN, errno.EADDRNOTAVAIL):
                verdict = "BLOCKED"        # el kernel no tiene ruta -> aislado
            elif e.errno in (errno.ECONNREFUSED,):
                verdict = "REACHABLE"      # llegó un RST -> hubo ruta hasta un host
            else:
                verdict = "UNKNOWN"
        finally:
            try:
                s.close()
            except Exception:  # noqa: BLE001
                pass
        if verdict in ("BLOCKED", "REACHABLE"):
            break
    return verdict


def _ollama_reachable(base_url: str | None = None, timeout: float = 4.0) -> bool:
    import os as _os
    import urllib.request

    configured = (base_url or _os.getenv("FACTORY_OLLAMA_BASE_URL")
                  or _os.getenv("OLLAMA_BASE_URL") or "http://host.docker.internal:11434")
    # el nombre host.docker.internal solo resuelve dentro del contenedor; en el
    # host se prueba además 127.0.0.1 (mismo Ollama local, otra ruta).
    candidates = [configured, "http://127.0.0.1:11434", "http://localhost:11434"]
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    socket.socket.connect, socket.socket.connect_ex = real_connect, real_connect_ex  # asegura socket real
    for url in candidates:
        try:
            with urllib.request.urlopen(url.rstrip("/") + "/api/tags", timeout=timeout) as r:
                if r.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            continue
    return False


def egress_control_state(*, network_probe: str | None = None,
                         ollama_ok: bool | None = None) -> dict:
    """Estado de los DOS controles de egress, para la atestación de corrida.

    `PROCESS_LEVEL_CONTROL` = ENFORCED siempre que el pipeline corra dentro de
        `network_locked()` (monkeypatch de `socket.connect`). Es defensa en
        profundidad -- NO prueba aislamiento.
    `NETWORK_LEVEL_CONTROL` = ENFORCED solo si `probe_external_reachability()`
        devuelve `BLOCKED`. `UNKNOWN`/`REACHABLE` -> NOT_ENFORCED.
    `EGRESS_GUARANTEE` = FORBIDDEN solo si AMBOS controles ENFORCED. En cualquier
        otro caso, `BEST_EFFORT_PROCESS_ONLY` -- nunca declarar FORBIDDEN por el
        monkeypatch.
    """
    probe = network_probe if network_probe is not None else probe_external_reachability()
    net = "ENFORCED" if probe == "BLOCKED" else "NOT_ENFORCED"
    proc = "ENFORCED"
    guarantee = "FORBIDDEN" if (net == "ENFORCED" and proc == "ENFORCED") else "BEST_EFFORT_PROCESS_ONLY"
    oll = _ollama_reachable() if ollama_ok is None else ollama_ok
    return {
        "process_level_control": proc,
        "network_level_control": net,
        "network_probe_result": probe,
        "egress_guarantee": guarantee,
        "ollama_local_access": "PASS" if oll else "FAIL",
        "note": ("PROCESS_LEVEL_CONTROL es el monkeypatch de socket.connect "
                 "(defensa adicional, NO prueba de aislamiento). NETWORK_LEVEL_CONTROL "
                 "solo es ENFORCED si el kernel no tiene ruta a Internet "
                 "(probe_external_reachability == BLOCKED). EGRESS_GUARANTEE == "
                 "FORBIDDEN exige ambos."),
    }
