# 06 — Git Status Final

Comando: `git status --porcelain=v1 -uall` (sin `-uall` completo del árbol,
excluyendo el flag `-uall` de directorios completos que pudiera agotar
memoria en árboles grandes — se usó la variante estándar de este repo).

**Rama:** `master`. **Rama principal para PRs:** `main`.

## Resumen

- **286 entradas**, todas con marca `??` (untracked). **0 modificadas, 0
  staged, 0 borradas** respecto al último commit (`e8e8b2c`).
- Ningún archivo de esta carpeta de cierre (`REPORTE_CIERRE_R4_T1_1v2_2026-08-13/`)
  fue commiteado durante esta auditoría — instrucción explícita.

## Distribución por directorio de primer nivel

| Directorio | Entradas untracked |
|---|---|
| `factory/` | 210 |
| `docs_plan/` | 59 |
| `docs_factory/` | 10 |
| `.claude/` | 5 |
| `scripts/` | 2 |

## Verificación de la regla `.gitignore` del commit `e8e8b2c`

```
grep -E "\.gnupg|private_reports" <lista completa de untracked>
→ sin coincidencias
```

Confirma que `.gnupg/` y `private_reports/` — el objeto del commit
`e8e8b2c` — no aparecen en el `git status`, es decir, la regla de
`.gitignore` está activa y funcionando.

## Archivos modificados

Ninguno. El working tree, respecto al último commit, solo tiene adiciones
no rastreadas.

## Archivos untracked relevantes (subconjunto, no exhaustivo)

- `factory/regulatory/pilot_run/checkpoints/*.checkpoint.json` (29
  archivos) — artefactos de ejecución del pipeline chunked, regenerables.
- `factory/regulatory/pilot_run/manifests/`, `status/`,
  `dry_run_validation_r4_t1_1v2/`, `tier1_dry_run_20260812/`,
  `tier1_rw0005/` — artefactos de corridas previas (R3-T1, dry runs),
  ninguno tocado en esta auditoría.
- `docs_plan/REPORTE_SESION_2026-08-12/` (26 archivos) — reporte de cierre
  de la sesión anterior (R3-T1), carpeta hermana de esta, no tocada.
- `docs_plan/REPORTE_CIERRE_R4_T1_1v2_2026-08-13/` — esta misma carpeta,
  generada durante esta auditoría.
- `.claude/settings.json`, `.claude/skills/gmp-implement/`,
  `.claude/skills/gmp-layer8-agent/`, `.claude/skills/gmp-read-evidence/`,
  `.claude/skills/gmp-status/` — configuración de Claude Code, no de
  código del producto.
- `scripts/11_ui_precheck.sh`, `scripts/22_ui_fix_frontend.sh` — scripts
  operativos no evaluados en esta auditoría.

## Qué se recomienda ignorar, limpiar o revisar después

- **Ignorar (candidatos a `.gitignore`):** `factory/regulatory/pilot_run/checkpoints/`
  y demás artefactos de ejecución regenerables bajo `pilot_run/` — evitar
  que un `git add -A` futuro los commitee accidentalmente, siguiendo el
  mismo criterio que ya se aplicó a `.gnupg/` y `private_reports/` en
  `e8e8b2c`.
- **Ya trazable:** `docs_plan/R4_T1_1v2_DESBLOQUEO_Y_VALIDACION_FRIA.md` (la
  fuente que este reporte audita) está commiteado en `d224b24`
  (`git ls-files` lo confirma tracked) — no requiere acción adicional.
- **Limpiar solo con aprobación de Cesar:** nada de lo untracked debe
  borrarse sin revisión — varias carpetas (`REPORTE_SESION_2026-08-12/`,
  `pilot_run/`) contienen evidencia de trabajo previo, no basura.
- **No se detectaron secretos, `.env`, claves ni tokens** en la lista de
  untracked — la exclusión de `.gnupg/` y `private_reports/` ya cubre las
  dos rutas sensibles conocidas de la raíz del home.
