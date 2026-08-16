# Skill: gmp-read-evidence

Lee toda la evidencia del proyecto GMP AI Copilot y presenta un resumen estructurado del estado actual antes de implementar nada.

## Instrucciones

1. Leer `/home/ing_cpmo/CONTEXT_FOR_CLAUDE.md` completo
2. Leer el directorio de evidencia más reciente en `/home/ing_cpmo/logs/evidence/` (el de fecha más reciente)
3. De ese directorio leer en orden:
   - `app_main.py` — código actual del contenedor
   - `endpoints_check.log` — detalle de los 404
   - `python_packages_key.log` — packages instalados
   - `ollama_connectivity.log` — modelos disponibles
   - `status_output.log` — estado general del sistema
   - `project_files.txt` — archivos Python existentes
4. Leer `/home/ing_cpmo/app/main.py` — código fuente actual en el host
5. Ejecutar: `docker exec gmp-api pip list 2>/dev/null | grep -iE "langchain|chroma|sentence|torch|fastapi|httpx|pydantic"`
6. Ejecutar: `docker exec gmp-api env 2>/dev/null | grep -E "OLLAMA|CHROMA|AUDIT|DATABASE|REDIS"`

## Output esperado

Presentar un resumen con:
- Estado de cada endpoint (OK/WARN/FAIL)
- Packages disponibles en el contenedor
- Variables de entorno clave
- Lista exacta de qué falta implementar
- Diagnóstico de si el contenedor necesita rebuild
