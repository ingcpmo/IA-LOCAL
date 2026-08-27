"""Modelo canónico documental (V2, B1) —
docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md FASE 2.

Representación intermedia con ESTRUCTURA preservada (a diferencia de
`chunked_engine.build_page_chunks`, que aplana todo a texto plano por
chunk). El objetivo es que el LLM de juicio deje de leer páginas enteras
y trabaje sobre `Claim`/`Control` ya estructurados y normalizados.

B1 es 100% determinista: sin llamadas LLM, sin gobernanza nueva, sin
descargas. `normalize_claims` usa heurística léxica en esta versión; la
variante opcional con 1 llamada LLM local corta por sección se documenta
pero NO se implementa aquí.
"""
