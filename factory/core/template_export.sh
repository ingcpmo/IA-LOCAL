#!/usr/bin/env bash
# Exporta el código base desde un git tag hacia un workspace destino.
#
# TODO F2:
# - Recibir <tag_base> y <workspace_dir> como argumentos
# - Validar que el tag existe (git tag -l | grep)
# - Ejecutar: git archive <tag> | tar -x -C <workspace_dir>
# - Registrar tag + commit hash en <workspace_dir>/.source_info
# - Salir con error si el tag no existe o si el directorio destino no está vacío
