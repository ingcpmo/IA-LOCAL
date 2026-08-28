"""Evidence / Knowledge Graph local (V2, B2) —
docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md FASE 3.

Representa relaciones entre los objetos del modelo canónico (B1) y los
requisitos regulatorios:

    URS.Requirement  --implemented_by-->  FS.Claim/Section
    FS.Claim         --designed_by-->     DS.Claim/Section
    DS.Claim         --tested_by-->       SAT.Test / OQ.Test
    Requirement      --regulated_by-->    Regulation
    Test             --verifies-->        Requirement
    Evidence         --supports-->        Control
    Evidence         --contradicts-->     Claim
    Claim            --refers_to-->       SystemComponent / Actor
    Document         --supersedes-->      Document

Habilita las clases FUNCTIONAL/TECHNICAL de findings (FASE 5/7) y la
detección de desviaciones e inconsistencias cross-documento.

B2 es 100% DETERMINISTA: sin llamadas LLM, sin red, sin gobernanza nueva.
El poblado por similitud semántica de embeddings (aristas difusas) es una
etapa POSTERIOR (B3+, gobernada por EMBED_EXECUTION) y NO está aquí — B2
solo puebla aristas por coincidencia de identificadores/referencias
literales y por el catálogo de requisitos.

Persistencia: SQLite local en `factory/regulatory/graph_store/` (gitignored,
regenerable desde el canonical_store + el catálogo — mismo criterio que
retrieval_index/). No Neo4j (OPTIONAL_INFRASTRUCTURE, rechazado en el ADR).
"""
