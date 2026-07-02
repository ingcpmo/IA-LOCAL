"""
W5 — Capa de servicios de la fábrica.

Lógica de negocio extraída de los routers HTTP (backlog 75→85 ítem 1).
Los routers en factory/api/routes/ quedan como capa HTTP fina que delega
aquí. Ningún servicio escribe en la cadena de auditoría salvo donde el
comportamiento original ya lo hacía (executor W4, PDF con record_by).
"""
