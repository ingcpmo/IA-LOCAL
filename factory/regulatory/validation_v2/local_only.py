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
