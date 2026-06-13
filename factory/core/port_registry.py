"""
Asignación y validación de puertos desde factory/registry/ports.yaml.
Fuente única de verdad. Valida disponibilidad real con ss -tlnp.
"""

import subprocess
import yaml
from datetime import datetime, timezone
from pathlib import Path

REGISTRY_PATH = Path(__file__).parent.parent / "registry" / "ports.yaml"

PORT_TYPES = ("custom_api", "custom_postgres", "custom_redis")


def _load() -> dict:
    with open(REGISTRY_PATH) as f:
        return yaml.safe_load(f)


def _save(data: dict) -> None:
    with open(REGISTRY_PATH, "w") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)


def validate_port_free(port: int) -> bool:
    """True si el puerto NO está en uso. Usa ss -tlnp si disponible, socket Python si no."""
    # Intentar con ss (disponible en host, no en contenedor slim)
    try:
        result = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return f":{port} " not in result.stdout and f":{port}\n" not in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    # Fallback: intentar bind en el puerto (si falla, está ocupado)
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def assign_ports(project_id: str) -> dict[str, int]:
    """
    Asigna api, postgres y redis ports para project_id.
    Valida que cada puerto esté libre (ss -tlnp) y no esté ya en allocations.
    Escribe la asignación en registry/ports.yaml.
    Retorna: {"api": int, "postgres": int, "redis": int}
    """
    data = _load()
    allocs = data.get("allocations") or {}

    if project_id in allocs:
        # Ya asignados — retornar los existentes
        return allocs[project_id]["ports"]

    ranges = data["ranges"]
    reserved_ports = set(data.get("reserved", {}).keys())
    used_ports: set[int] = set()
    for v in allocs.values():
        used_ports.update(v["ports"].values())

    assigned: dict[str, int] = {}
    type_map = {
        "custom_api":      "api",
        "custom_postgres": "postgres",
        "custom_redis":    "redis",
    }

    for range_key, out_key in type_map.items():
        r = ranges[range_key]
        start, end = int(r["start"]), int(r["end"])
        found = None
        for port in range(start, end + 1):
            if port in reserved_ports or port in used_ports:
                continue
            if validate_port_free(port):
                found = port
                used_ports.add(port)
                break
        if found is None:
            raise RuntimeError(f"No hay puertos libres en el rango {range_key} ({start}-{end})")
        assigned[out_key] = found

    # Escribir en registry
    if allocs is None:
        data["allocations"] = {}
    data["allocations"][project_id] = {
        "ports": assigned,
        "allocated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save(data)
    return assigned


def release_ports(project_id: str) -> None:
    """Libera los puertos de project_id en allocations."""
    data = _load()
    allocs = data.get("allocations") or {}
    if project_id in allocs:
        del allocs[project_id]
        data["allocations"] = allocs
        _save(data)


def get_allocated_ports(project_id: str) -> dict[str, int] | None:
    """Retorna los puertos asignados a project_id, o None si no existe."""
    data = _load()
    alloc = (data.get("allocations") or {}).get(project_id)
    return alloc["ports"] if alloc else None


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python3 port_registry.py <assign|release|show> <project_id>")
        sys.exit(1)
    cmd, pid = sys.argv[1], sys.argv[2]
    if cmd == "assign":
        ports = assign_ports(pid)
        print(f"Puertos asignados para '{pid}': {ports}")
    elif cmd == "release":
        release_ports(pid)
        print(f"Puertos liberados para '{pid}'")
    elif cmd == "show":
        p = get_allocated_ports(pid)
        print(f"Puertos de '{pid}': {p}")
