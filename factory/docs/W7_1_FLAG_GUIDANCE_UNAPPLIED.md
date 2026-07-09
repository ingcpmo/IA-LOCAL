# W7.1 — Flag determinista `guidance_unapplied` (Fase A: diseño y contrato)

**Origen:** limitación §7.1 del cierre de W7 Fase D (`W7_FASED_CIERRE.md`):
en la ejecución real, la revisión v2 reprodujo v1 byte a byte sin aplicar la
guidance y pasó el verificador v2.1 sin ninguna señal — el incumplimiento se
detectó solo por diff externo. **Arranque de Fase A autorizado por Cesar
(2026-07-09).** Este documento es el contrato; la implementación (Fase B)
requiere aprobación separada.

## 1. Objetivo

Señal determinista, sin LLM y sin juicio, de que una **revisión** produjo
una respuesta idéntica a la versión que debía corregir — es decir, que la
instrucción del revisor humano no tuvo efecto observable alguno. El flag es
**advisory** (filosofía W6.5.1): se registra y penaliza confianza; jamás
bloquea, jamás reintenta, jamás decide. La decisión sigue siendo humana.

## 2. Qué detecta y qué NO detecta (alcance declarado)

**Detecta:** respuesta de revisión idéntica a la respuesta de su
`based_on_version`, con normalización mínima (comparación de la secuencia de
líneas no vacías con espacios laterales recortados — inmune a diferencias de
solo whitespace, determinista, cero heurística).

**NO detecta (fuera de alcance, declarado):**
- Incumplimiento parcial: el modelo cambia algo irrelevante e ignora la
  guidance (requeriría juicio semántico — no determinista).
- Regresión a una versión anterior distinta de `based_on_version`
  (p. ej. v3 idéntica a v1): se compara SOLO contra la versión revisada.
- Cumplimiento incorrecto (cambió lo pedido pero mal): dominio del humano.

## 3. Diseño técnico

### 3.1 Función pura nueva en `claim_verifier.py` (reutilizable, sin IO)

```python
def check_guidance_unapplied(response: str, prev_response: str | None) -> list:
    """prev_response None (modo draft) → []. Normaliza ambas respuestas a
    secuencia de líneas no vacías .strip() y compara igualdad. Idénticas →
    [{"type": "guidance_unapplied", "detail": "la revisión es idéntica a la
    versión revisada — la instrucción QA no tuvo efecto observable"}]."""
```

### 3.2 Integración en `verify_v2` (firma retrocompatible)

`verify_v2(response, claims, items, grants, prev_response=None)` — parámetro
opcional con default `None`: los llamadores existentes no cambian de
comportamiento. `findings += check_guidance_unapplied(response,
prev_response)`; el flag entra a `flags` por el mecanismo existente.
`VERIFIER_VERSION` 2.1 → **2.2** (el pin de tests usa el símbolo, no la
cadena).

### 3.3 Llamadores (los 2 pipelines de revisión, cambio de 1 línea c/u)

- `dossier_agent_review_service.py`: `prev_response` ya existe en el scope
  (línea ~530) — se pasa a `verify_v2` (None en draft).
- `case_analysis_service.py`: `prev` ya se carga en modo revisión (línea
  ~323) — se pasa `prev["response"]` (None en draft).

Sin cambios en prompts YAML (el flag es post-generación), sin cambios de
esquema (flags/findings son listas existentes), sin cambios de UI (ambas
vistas renderizan `flags[]` genéricamente como chips), sin eventos nuevos
(`flags` ya viaja en `*_generated`). Read path: registros previos sin el
flag se sirven igual (aditivo).

### 3.4 Confianza (anti-optimismo)

`guidance_unapplied` se suma a la lista severa de `_confidence` ⇒
**confianza baja**. Racional: la salida desobedece una instrucción QA
explícita y trazada en el ledger — mismo rango que texto potencialmente
falso. (En el caso real, v2 habría quedado baja en vez de media.)

### 3.5 Re-verificación de archivados (`items_from_prompt`)

La re-verificación de propuestas archivadas no dispone de `prev_response`
(default None) → nunca produce este flag retroactivamente. Los registros
históricos conservan sus flags tal cual. Declarado, no es brecha: v2 del
caso real entra como fixture (§4).

## 4. Fixtures y criterios de aceptación (testables, Fase B)

Fixtures: copiar `v01/v02/v03.json` del caso real
`openfda_enforcement__D-0554-2026` a `tests/fixtures/case_analyses/`
(mismo patrón que los v01–v06 del dossier en W6.5.1; validation/ y
case_analyses/ no están en git).

- [ ] **A1** v2 real vs v1 real (idénticas) ⇒ flag `guidance_unapplied` +
      confianza `baja` (regresión del caso vivo de Fase D).
- [ ] **A2** v3 real vs v2 real (1 viñeta eliminada) ⇒ SIN flag.
- [ ] **A3** Modo draft (`prev_response=None`) ⇒ SIN flag, jamás.
- [ ] **A4** Diferencia de solo whitespace/líneas vacías ⇒ flag (la
      normalización la absorbe).
- [ ] **A5** Cualquier cambio real de contenido, aun de 1 carácter ⇒ SIN
      flag (conservador: cero heurística de casi-igualdad).
- [ ] **A6** Pipeline de dossier con LLM mockeado devolviendo la respuesta
      previa ⇒ mismo flag + confianza baja (paridad entre pipelines).
- [ ] **A7** `verify_v2` sin el parámetro nuevo (llamada legada) ⇒
      comportamiento idéntico al actual (retrocompatibilidad).
- [ ] **A8** `claim_verifier.py` sigue puro: test estructural anti-httpx/
      audit/IO existente cubre el código nuevo.
- [ ] **A9** Registro generado en revisión idéntica lleva el flag en
      `record.flags`, en el evento `*_generated` y se renderiza en UI sin
      cambios de JS (verificación en vivo post-restart).
- [ ] **A10** Suite completa verde + selfcheck PASS=4 FAIL=0.

## 5. Plan de Fase B (para aprobación separada)

1 función nueva + 1 firma extendida en `claim_verifier.py` · 1 línea por
pipeline · `guidance_unapplied` en `_confidence` · docstring de
`_confidence` actualizado · fixtures + ~8 tests nuevos · bump VERIFIER_VERSION
2.2 · restart gated de factory-api (cambia .py) · verificación en vivo
read-only. Ningún archivo prohibido; ningún contacto con dossier approval,
cases.jsonl ni contenedores ajenos.

## 6. Criterio de cierre de W7.1

Fase B implementada con A1–A10 en verde, verificación en vivo, aprobación
de Cesar y commit único "factory: W7.1 …".
