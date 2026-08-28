"""Flag de routing del analizador (V2, B9) -- FASE 11.

Tres modos:
  current  (DEFAULT)  -- solo CURRENT corre. V2 no se ejecuta.
  shadow              -- V2 corre EN PARALELO sin efectos (validation_v2.shadow),
                         CURRENT sigue siendo el que decide.
  v2                  -- V2 es el que decide (cutover hecho). CURRENT queda como
                         fallback seleccionable volviendo a `current`.

Se lee de la variable de entorno `V2_ANALYZER_ROUTING` o del archivo
`factory/regulatory/validation_v2/routing.txt` (env gana). El DEFAULT es
`current` -- este módulo por sí solo NO cambia el comportamiento de
CURRENT; el cutover real es cablear `routing_mode()` en `corpus_runner`
(1 línea, reversible), que es una decisión de Capa 9 (B9b), no de este
paquete.
"""
from __future__ import annotations

import os
from pathlib import Path

_MODES = ("current", "shadow", "v2")
_ENV = "V2_ANALYZER_ROUTING"
_FILE = Path(__file__).resolve().parent / "routing.txt"
DEFAULT_MODE = "current"


class RoutingModeError(ValueError):
    pass


_HISTORY = Path(__file__).resolve().parent / "routing_history.jsonl"


def routing_mode() -> str:
    raw = os.environ.get(_ENV)
    if raw is None and _FILE.exists():
        raw = _FILE.read_text(encoding="utf-8").strip()
    mode = (raw or DEFAULT_MODE).strip().lower()
    if mode not in _MODES:
        raise RoutingModeError(f"V2_ANALYZER_ROUTING inválido: {mode!r} (permitidos: {_MODES})")
    return mode


def set_routing_mode(mode: str, *, actor: str, reason: str) -> dict:
    """Escribe el flag de routing (`routing.txt`) y registra el cambio en
    `routing_history.jsonl` (append-only). REVERSIBLE: volver a 'current'
    restaura CURRENT como motor activo. El env `V2_ANALYZER_ROUTING` sigue
    ganando si está definido."""
    import json as _json
    from datetime import datetime, timezone
    mode = mode.strip().lower()
    if mode not in _MODES:
        raise RoutingModeError(f"modo inválido: {mode!r} (permitidos: {_MODES})")
    prev = routing_mode()
    _FILE.write_text(mode + "\n", encoding="utf-8")
    entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "from": prev, "to": mode, "actor": actor, "reason": reason,
        "env_override_active": os.environ.get(_ENV) is not None,
        "current_retained_as_rollback": True,
    }
    with open(_HISTORY, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def routing_history() -> list[dict]:
    import json as _json
    if not _HISTORY.exists():
        return []
    return [_json.loads(l) for l in _HISTORY.read_text(encoding="utf-8").splitlines() if l.strip()]


def is_current_only() -> bool:
    return routing_mode() == "current"


def is_shadow_active() -> bool:
    return routing_mode() == "shadow"


def is_v2_active() -> bool:
    return routing_mode() == "v2"


def describe() -> dict:
    m = routing_mode()
    return {
        "mode": m,
        "current_decides": m in ("current", "shadow"),
        "v2_runs": m in ("shadow", "v2"),
        "v2_has_effects": m == "v2",
        "note": ("DEFAULT=current. El cutover a 'v2' es decisión de Capa 9; el dispatcher "
                 "`analyzer_router.analyze()` cablea routing_mode() al camino de análisis "
                 "(B9b hecho). CURRENT se conserva para rollback: volver a 'current'."),
    }
