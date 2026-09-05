"""SHADOW · CF-6 v2.0 · R4/E1 — tabla de equivalencia de fases (vocabulario).

Decisión de Capa 9 (2026-09-04, instrucción "RECONCILIACIÓN POST-R2 + EJECUCIÓN
R4" §2): **se reconcilia el VOCABULARIO, no se debilita el chequeo**
`c_cf6_3` de `cf6_pilot_scope.py`.

## Por qué existe

`cf6_pilot_scope.py::c_cf6_3` (heredado de v1.2/v1.3, SIN modificar aquí en
su semántica) exige que el scope firmado de la PILOT cubra explícitamente
la CORRIDA COMPLETA sobre el corpus (no solo un piloto de muestra). La
nomenclatura de fases del diseño v2.0 (`R1..R6`) no existía cuando ese
chequeo se escribió, así que el ADDENDUM `PILOT_EXECUTION-2026-041/-042`
(que usó `"CF6-v2-R5"`) falló el chequeo por vocabulario, no por alcance
insuficiente -- costó una segunda ronda de propose→confirm
(`-043/-044`) para añadir el token literal `"CF6-3"`.

## Qué declara esta tabla, y qué NO hace

- Declara, de forma explícita y versionada, qué cadenas de scope son
  EQUIVALENTES en significado ("corrida completa sobre el corpus,
  post-gate") bajo generaciones de nomenclatura distintas.
- El gate `cf6_pilot_scope.py` puede consultar esta tabla para aceptar
  CUALQUIERA de las formas ya declaradas aquí -- nunca un token nuevo no
  listado, y nunca elimina la exigencia de que el scope cubra
  explícitamente la corrida completa.
- **No retira ni relaja** el requisito semántico del chequeo `c_cf6_3`
  (sigue exigiendo cobertura explícita de la corrida completa post-gate).
  Solo amplía qué TEXTOS cuentan como esa declaración.
- Prohibido: aceptar un token no enumerado aquí, o interpretar "corrida
  completa" de forma implícita/heurística fuera de esta lista cerrada.

## Versionado

Cambiar esta tabla (añadir una generación nueva de nomenclatura) es una
decisión de Capa 9, igual que cualquier cambio de gobernanza -- se
versiona (`TABLE_VERSION`) y se commitea ANTES de redactar cualquier
ADDENDUM que dependa de la nomenclatura nueva.
"""
from __future__ import annotations

TABLE_VERSION = "1"
TABLE_SIGNED_BY = "Capa 9 (Cesar)"
TABLE_SIGNED_AT = "2026-09-04"
TABLE_SIGNED_ON = (
    "instrucción de sesión 2026-09-04, 'RECONCILIACIÓN POST-R2 + EJECUCIÓN R4' §2: "
    "'se reconcilia el VOCABULARIO, no se debilita el chequeo'"
)

# Cada clase de equivalencia representa UN significado semántico. El gate
# acepta cualquier token de la clase que corresponda al chequeo que esté
# evaluando -- nunca mezcla clases.
EQUIVALENCE_CLASSES = {
    "FULL_CORPUS_RUN_POST_GATE": {
        "meaning": "corrida completa sobre el corpus, posterior al gate de calidad "
                   "(NO un piloto de muestra)",
        "tokens": {
            # nomenclatura v1.2/v1.3 (heredada, la que el chequeo original codificaba)
            "CF6-3", "cf6_3", "corrida completa cf6", "full cf6",
            # nomenclatura v2.0 (diseño CF6_v2_REDISENO_AUDITORIA_PROFESIONAL.md §13)
            "CF6-v2-R5", "cf6-v2-r5", "corrida completa bajo la arquitectura r1-r3",
        },
    },
    "QUALITY_PILOT_SAMPLE": {
        "meaning": "piloto de calidad sobre la muestra congelada (SAMPLE_MANIFEST), "
                   "NO la corrida completa",
        "tokens": {
            "CF6-2.5", "cf6_2_5", "quality pilot", "human_quality_gate",
            "CF6-v2-R2", "cf6-v2-r2",
        },
    },
}


def tokens_for(equivalence_class: str) -> set:
    """Tokens declarados (en minúscula) para una clase de equivalencia. Lanza
    si la clase no existe -- fail-closed, nunca devuelve un conjunto vacío
    por una clave mal escrita."""
    if equivalence_class not in EQUIVALENCE_CLASSES:
        raise KeyError(f"clase de equivalencia desconocida: {equivalence_class!r} "
                       f"(declaradas: {sorted(EQUIVALENCE_CLASSES)})")
    return {t.lower() for t in EQUIVALENCE_CLASSES[equivalence_class]["tokens"]}


def spec() -> dict:
    return {
        "schema": "SHADOW_CF6_V2_PHASE_EQUIVALENCE_TABLE/v1",
        "table_version": TABLE_VERSION,
        "signed_by": TABLE_SIGNED_BY,
        "signed_at": TABLE_SIGNED_AT,
        "signed_on": TABLE_SIGNED_ON,
        "classes": {k: {"meaning": v["meaning"], "tokens": sorted(v["tokens"])}
                   for k, v in EQUIVALENCE_CLASSES.items()},
        "does_not_relax": "el chequeo sigue exigiendo cobertura EXPLÍCITA de la corrida "
                          "completa post-gate; solo se amplía qué texto cuenta como esa "
                          "declaración",
    }
