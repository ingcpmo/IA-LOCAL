# GMP AI Factory — Capas 7-9

Fábrica de soluciones GMP sobre el producto base GMP AI Copilot (tag `base-v1.0.0`).

## Arquitectura

- **Docker 1** — GMP AI Copilot base, puerto 8000, capas 1-6. NO TOCAR.
- **Docker 2** — GMP AI Factory (este repo), puerto 9000, capas 7-9.
- **Docker 3..N** — Soluciones custom generadas, puertos 8101+.

## Flujo

requerimiento → registro → análisis (Capa 8) → propuesta → workspace → generación → quality gates → diff → aprobación humana (Capa 9) → release inmutable → deployment.

## Regla principal

Una fase por sesión de Claude Code. Ningún commit, release ni deploy sin aprobación explícita del usuario.

## Documentación del plan

Ver `/home/ing_cpmo/docs_factory/` — documentos 00 a 05.
