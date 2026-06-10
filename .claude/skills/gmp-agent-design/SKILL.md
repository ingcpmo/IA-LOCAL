---
name: gmp-agent-design
description: Criterios y requisitos para decidir entre usar un agente GMP existente, crear un perfil derivado o crear un agente nuevo, y checklist completo de creacion. USAR SIEMPRE que la tarea implique agentes, perfiles, system prompts de agentes, corpus RAG nuevo, colecciones ChromaDB nuevas, routing de agentes, o disenar la parte de agentes de una solucion custom de la fabrica.
---

# Diseño de agentes y perfiles GMP

## Agentes base disponibles (DOCKER 1, heredables)
csv (CSV/CSA Validation), qa (Quality Assurance), audit (FDA 483 Inspector),
automation (PLC/SCADA ISA-88/95), integrity (ALCOA+ Part 11),
capa (Root Cause/Closure). Colecciones: gmp_fda_regulations, gmp_iq_oq_pq,
gmp_qa_system, gmp_data_integrity, gmp_automation, gmp_capa.

## Arbol de decision (aplicar en este orden)
1. USAR AGENTE EXISTENTE si el requerimiento cabe 100% en un agente actual,
   sin corpus nuevo, sin reglas nuevas, sin salida diferente.
2. CREAR PERFIL DERIVADO si el agente base cubre 70-80% del alcance y solo
   se necesita prompt especializado y/o corpus especializado, sin logica
   backend nueva. El perfil hereda agent_id base + sufijo
   (ej. qa_oos_profile) y se define en factory/profiles/<base>_profiles.yaml.
3. CREAR AGENTE NUEVO si el dominio es nuevo, requiere corpus propio,
   reglas propias, pruebas propias o salida distinta, o si mezclarlo con
   agentes actuales reduce precision.

## Ejemplos calibrados
OOS laboratorio → perfil de qa. Excel sin control → perfil de integrity.
SCADA firmware → perfil de automation (o automation+csv).
Validacion de limpieza → agente nuevo. Farmacovigilancia → agente nuevo.
Produccion esteril → agente nuevo o paquete de agentes.

## Checklist obligatorio de agente nuevo (todo o nada)
[ ] agent_id (snake_case) y nombre visible
[ ] descripcion de alcance y limites
[ ] system_prompt (idioma dinamico, formato de salida definido)
[ ] coleccion RAG propia con >= 60 chunks de fuentes regulatorias citables
[ ] reglas asociadas (extension del Rule Engine si aplica)
[ ] >= 5 preguntas de prueba con criterios de aceptacion verificables
[ ] entrada en manifest.yaml (agents.custom) y en
    factory/registry/agents_catalog.yaml
[ ] evidencia de validacion (respuestas reales archivadas en el release)
[ ] aprobacion humana registrada (approval_policy)

## Checklist de perfil derivado
[ ] perfil_id, agente base, % de cobertura estimado y justificacion
[ ] system_prompt especializado (delta sobre el base)
[ ] coleccion RAG propia o compartida (declararlo en manifest)
[ ] >= 3 preguntas de prueba con criterios de aceptacion
[ ] entrada en profiles/<base>_profiles.yaml y en manifest (agents.profiles)

## Leccion aprendida del base
La calidad depende del corpus: el refuerzo dirigido de corpus es la
palanca principal (caso ALCOA+ / FDA 483). Todo corpus nuevo debe citar
fuente y fecha del documento regulatorio de origen.
