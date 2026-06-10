"""
Asignación y validación de puertos desde factory/registry/ports.yaml.

TODO F2:
- load_registry() → dict desde ports.yaml
- assign_port(project_id, port_type) → int
  Lee el rango correspondiente, valida con ss -tlnp que esté libre,
  escribe la asignación en allocations con project_id y fecha
- release_port(project_id) → libera puertos del proyecto en allocations
- validate_port_free(port) → bool (ss -tlnp)
"""
