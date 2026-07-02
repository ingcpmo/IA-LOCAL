# Case Memory — memoria regulatoria de casos (W6: vacía por diseño)

Esta carpeta persiste los *case records* de la Regulatory Case Memory:
`cases.jsonl` (append-only, dedupe por content_hash). **En W6 no existe ningún
caso**: no hay conectores, no hay tráfico externo y no se poblará con datos
inventados — la memoria solo crecerá con casos reales consultados de fuentes
oficiales bajo aprobación (fase futura).

Cada línea de `cases.jsonl` será un case record:
`case_id · url · source_id · authority · consulted_at · last_checked ·
case_type · summary (≤1200 chars) · tags · keywords · content_hash ·
embedding_ref · retrieval_path · relevance`

Regla dura: aquí se guardan **solo pointers + metadata + resúmenes + hashes**
— nunca documentos completos, nunca PII, nunca casos sin URL oficial de origen.
Diseño completo: `factory/docs/W6_MISSION_CONTROL_ENTERPRISE.md` §6.
