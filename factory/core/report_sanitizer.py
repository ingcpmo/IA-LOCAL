"""
Sanitización de secretos para reportes expuestos fuera de la cadena de auditoría
(Dashboard GMP W4.1 y su PDF). Función pura, sin dependencias de FastAPI ni de
layer9 — reutilizable por cualquier vista que consolide evidencia real.
"""

import re
from typing import Any

_REDACTED = "***REDACTED***"

_SENSITIVE_KEY_RE = re.compile(
    r"(api[_-]?key|password|secret|token|credential)", re.IGNORECASE
)

# Patrones de valores que delatan un secreto aunque no se pase su valor exacto.
_VALUE_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_-]+"),
    # Credenciales embebidas en connection strings / URLs:
    #   postgresql://user:password@host  →  postgresql://***REDACTED***@host
    #   redis://:password@host           →  redis://***REDACTED***@host
    # El usuario puede ser vacío (redis); el password nunca. No matchea URLs
    # sin '@' (http://host:8000/path queda intacta).
    re.compile(r"(?<=://)[^/\s:@]*:[^/\s@]+(?=@)"),
]


def sanitize_for_report(data: Any, secret_values: list[str] | None = None) -> Any:
    """
    Retorna una copia sanitizada de `data` (dict/list/str/escalar):
      - cualquier clave cuyo nombre matchee api_key/password/secret/token/credential
        se enmascara sin importar el valor.
      - cualquier substring igual a uno de `secret_values` (valores reales conocidos,
        ej. FACTORY_API_KEY o GMP_API_KEY del deployment) se reemplaza.
      - patrones conocidos de credenciales embebidas (ej. sk-ant-...) se reemplazan.
    No muta `data`.
    """
    values = [v for v in (secret_values or []) if v]

    def _scrub_string(s: str) -> str:
        for v in values:
            if v in s:
                s = s.replace(v, _REDACTED)
        for pat in _VALUE_PATTERNS:
            s = pat.sub(_REDACTED, s)
        return s

    def _walk(node: Any) -> Any:
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                if isinstance(k, str) and _SENSITIVE_KEY_RE.search(k):
                    out[k] = _REDACTED
                else:
                    out[k] = _walk(v)
            return out
        if isinstance(node, list):
            return [_walk(v) for v in node]
        if isinstance(node, tuple):
            return tuple(_walk(v) for v in node)
        if isinstance(node, str):
            return _scrub_string(node)
        return node

    return _walk(data)
