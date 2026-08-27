"""Validación integral V2 (B8) --
docs_plan/PLAN_VALIDACION_ANALIZADOR_GMP_LOCAL_V2.md FASE 10.

Tres suites INDEPENDIENTES:
  A. Regulatory  -- fixture 7P+2N existente (W5V2_RECALL_FIXTURE_SET_DRAFT.md), NO se cambia.
  B. Functional  -- fixture NUEVO (20 casos URS<->FS, FS<->SAT), Golden Dataset, firma de Capa 9.
  C. Technical   -- fixture NUEVO (20 casos), Golden Dataset, firma de Capa 9.

B8a (este código): harness + evaluadores de gate deterministas + chequeo
LOCAL_ONLY, con provider MOCKEADO en los tests. CERO llamadas reales,
cero gobernanza consumida.
B8b (corrida real de medición) NO arranca sin:
  - firma de Capa 9 sobre los prompts de juicio V2 (B4),
  - firma de las suites B y C como Golden Dataset,
  - una PILOT_EXECUTION firmada.

Regla dura heredada (skill gmp-recall-pipeline): el fixture es el ÚNICO
instrumento de medición; PROHIBIDO aflojar validadores para inflar gates.
"""
