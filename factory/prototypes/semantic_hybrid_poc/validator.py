"""Validador determinista FAIL-CLOSED (R4). Sin reparacion heuristica del JSON,
sin reintento silencioso. FASE 2, aislado."""
from __future__ import annotations

import json

import jsonschema

from factory.prototypes.semantic_hybrid_poc.schema import SCTA_V1


def validate(gen: dict) -> tuple[dict | None, str, list[str]]:
    """Devuelve (payload|None, status, errors).
    status in {OK, FAILED}. FAILED ante: transporte, done_reason=length (truncado),
    JSON invalido, o violacion de schema."""
    errs: list[str] = []
    if gen.get("transport_error"):
        return None, "FAILED", [f"transport: {gen['transport_error']}"]
    if gen.get("done_reason") == "length":
        return None, "FAILED", ["truncated: done_reason=length (generacion agoto num_predict)"]
    raw = gen.get("raw_response")
    if not raw:
        return None, "FAILED", ["respuesta vacia"]
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, "FAILED", [f"json_invalid: {e}"]
    v = jsonschema.Draft7Validator(SCTA_V1)
    for e in sorted(v.iter_errors(payload), key=lambda x: list(x.path)):
        errs.append(f"schema: {'/'.join(map(str, e.path)) or '<root>'}: {e.message}")
    if errs:
        return None, "FAILED", errs
    return payload, "OK", []
