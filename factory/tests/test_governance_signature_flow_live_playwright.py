"""[N11] El ciclo de firma contra el SERVIDOR VIVO, con navegador real.

Este fichero existe por la tercera causa del bloqueo de la firma D1, que
ninguna prueba de Python podia ver: el worker de uvicorn corre SIN `--reload`,
asi que servia codigo viejo mientras el navegador ya tenia el JS nuevo. Se
"verifico" el fix con `docker exec factory-api python -c ...` y dio un falso
positivo, porque eso lanza un interprete NUEVO que lee la fuente nueva del
volumen montado y no dice nada de lo que el proceso tiene cargado.

Conclusion convertida en prueba: para saber que sirve un proceso vivo hay que
hablar con el ENDPOINT, y para saber que manda el navegador hay que usar un
navegador.

Se SALTA (skip) si no hay servidor o no hay clave: es una prueba de integracion
contra un despliegue, no una unitaria, y no debe volver rojo un entorno limpio.

NUNCA firma nada: el confirm va con identidad RESERVADA a proposito, asi que el
servidor lo rechaza con 422. Un 422 de identidad prueba justo lo que hace falta
-- que el token de estado PASO -- sin producir una firma en nombre de nadie.

OPT-IN OBLIGATORIO (post-incidente 2026-08-02): el propose SI llega al
servidor vivo a proposito (es lo que este fichero prueba) y deja una
propuesta real `agent_proposed` en `decisions_v2.jsonl` -- un almacen
git-trackeado, no un scratch. "propose nunca firma" es cierto para la
identidad, pero no es cierto que no deje huella: una corrida rutinaria de
la suite completa (Gate 0, CI) con factory-api vivo por casualidad
disparaba este fichero sin que nadie lo pidiera, y `decisions_v2.jsonl`
terminaba con una entrada de prueba real (D1-2026-055, encontrada por
`test_no_test_in_this_file_wrote_to_the_real_store` en
test_resignature_g2prime.py). Por eso ahora, ademas de servidor+clave,
hace falta que un humano ponga expresamente `FACTORY_LIVE_UI_TESTS=1` --
la prueba de integracion contra el despliegue vivo pasa a ser un acto
deliberado, no un efecto colateral de "el contenedor estaba arriba".
"""
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BASE = os.environ.get("FACTORY_UI_BASE", "http://localhost:9000")
IDENTIDAD_RESERVADA = "human"
_OPT_IN_VAR = "FACTORY_LIVE_UI_TESTS"


def _api_key() -> str | None:
    if os.environ.get("FACTORY_API_KEY"):
        return os.environ["FACTORY_API_KEY"]
    env = REPO / "factory" / ".env"
    if not env.is_file():
        return None
    for linea in env.read_text(encoding="utf-8").splitlines():
        if linea.startswith("FACTORY_API_KEY="):
            return linea.split("=", 1)[1].strip()
    return None


def _servidor_vivo() -> bool:
    try:
        import urllib.request
        with urllib.request.urlopen(f"{BASE}/health", timeout=3) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(
    os.environ.get(_OPT_IN_VAR) != "1" or not _servidor_vivo() or not _api_key(),
    reason=(
        f"prueba de integracion contra un despliegue vivo -- deja un propose "
        f"real en decisions_v2.jsonl. Requiere opt-in explicito ({_OPT_IN_VAR}=1) "
        "ademas de servidor+clave, para que un run rutinario de la suite nunca "
        "la dispare por accidente"))


@pytest.fixture()
def pagina():
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as pw:
        navegador = pw.chromium.launch()
        pg = navegador.new_page()
        errores: list[str] = []
        pg.on("pageerror", lambda e: errores.append(f"pageerror: {e}"))
        # El navegador registra en consola TODA respuesta no-2xx, y este test
        # provoca un 422 a proposito (identidad reservada). Ese ruido de red no
        # es un error de JS y contarlo como tal haria fallar justo el caso que se
        # quiere demostrar. Solo se recogen los fallos reales de codigo.
        pg.on("console",
              lambda m: errores.append(f"console.error: {m.text}")
              if m.type == "error" and "Failed to load resource" not in m.text
              else None)
        pg.goto(f"{BASE}/ui/mission_control.html", wait_until="networkidle")
        pg.fill("#apikey", _api_key())
        pg.click("text=Conectar")
        pg.wait_for_timeout(2500)
        pg.evaluate("window.refresh && window.refresh('gobierno')")
        pg.wait_for_timeout(2500)
        yield pg, errores
        navegador.close()


def _abrir_panel_d1(pg):
    pg.evaluate("window.govOpen && window.govOpen('d1-correccion')")
    pg.wait_for_timeout(1500)
    marcadas = pg.evaluate("""() => {
        const cs=[...document.querySelectorAll('.d1c-src')];
        cs.forEach(c=>{ c.checked = c.value!=='ecfr_21cfr_part211'; });
        return cs.filter(c=>c.checked).length;
    }""")
    assert marcadas >= 1, "el panel de la Correccion D1 no expuso las fuentes"
    pg.evaluate(f"""() => {{
        const set=(s,v)=>{{const e=document.querySelector(s); if(e) e.value=v;}};
        set('#d1c-id','{IDENTIDAD_RESERVADA}');
        set('#d1c-name','PRUEBA AUTOMATICA — NO ES UNA FIRMA');
        set('#d1c-reason','prueba de integracion G2.1 — no es una firma');
    }}""")


def test_n11_the_live_flow_sends_the_token_propose_returned(pagina):
    """El navegador real reenvia el token del propose, no el del GET.

    Este es el test que habria cazado las tres causas de un tiro: si /propose no
    devuelve el token (causa 3), si el cliente manda el del GET (causa 1) o si el
    hash es global y ya cambio (causa 2), la asercion falla.
    """
    pg, errores = pagina
    capturado = {}

    def espia(route):
        req = route.request
        cuerpo = json.loads(req.post_data or "{}")
        clave = "propose" if req.url.endswith("/propose") else "confirm"
        capturado[clave] = cuerpo
        if clave == "propose":
            route.continue_()          # el propose SI va al servidor vivo
        else:
            # El confirm se deja pasar tambien: con identidad reservada el
            # servidor responde 422 y no se firma nada.
            route.continue_()

    pg.route("**/governance/decisions/*/propose", espia)
    pg.route("**/governance/decisions/*/confirm", espia)

    respuestas = []
    pg.on("response", lambda r: respuestas.append((r.url, r.status))
          if "/governance/decisions/" in r.url else None)

    _abrir_panel_d1(pg)
    pg.evaluate("window.govSubmitD1Correccion()")
    pg.wait_for_timeout(4000)

    assert "propose" in capturado, "el navegador no llego a proponer"
    assert "confirm" in capturado, (
        "el navegador no llego a confirmar: si el propose no devolvio los "
        "tokens, la UI aborta a proposito en vez de mandar undefined")

    conf = capturado["confirm"]
    # El campo VIAJA y no es undefined. Esto es literalmente lo que fallaba.
    assert "family_state_hash" in conf, "el confirm no lleva family_state_hash"
    assert conf["family_state_hash"], "family_state_hash viajo vacio/undefined"
    assert re.fullmatch(r"[0-9a-f]{64}", conf["family_state_hash"]), (
        f"family_state_hash no es un sha256: {conf['family_state_hash']!r}")

    # Y el propose del servidor VIVO tiene que haber devuelto ese mismo token.
    #
    # 201 si creo la propuesta, 200 si el dedupe reutilizo una viva y equivalente:
    # las dos son respuestas correctas y en las dos viaja el token, que es lo que
    # este test mide. Exigia 201 a secas, y eso empezo a fallar en cuanto el
    # codigo dejo de anunciar "Created" sobre escrituras que no ocurrian —
    # confundia "el propose funciono" con "el propose escribio".
    propose_resp = [s for u, s in respuestas if u.endswith("/propose")]
    assert propose_resp and propose_resp[0] in (200, 201), propose_resp

    confirm_status = [s for u, s in respuestas if u.endswith("/confirm")]
    assert confirm_status, "no hubo respuesta al confirm"
    # 422 = el token de estado PASO y solo cayo la identidad reservada.
    # 409 significaria que el control de estado sigue roto.
    assert confirm_status[0] == 422, (
        f"se esperaba 422 por identidad reservada; llego {confirm_status[0]}. "
        "Un 409 aqui significa que el token de estado sigue fallando.")

    assert not errores, f"la pagina lanzo errores JS: {errores[:5]}"


def test_n11_the_live_propose_endpoint_returns_every_token(pagina):
    """Lo mismo desde el contrato: el proceso VIVO devuelve los tokens.

    Se comprueba llamando al endpoint desde el propio navegador, no importando
    el modulo: importar la fuente fue el falso positivo que dejo correr el fallo.
    """
    pg, _ = pagina
    cuerpo = pg.evaluate("""async () => {
        const r = await fetch('/api/v1/layer9/governance/proposals',
                              {headers:{'x-api-key': document.getElementById('apikey').value}});
        return {status: r.status, data: await r.json()};
    }""")
    assert cuerpo["status"] == 200, cuerpo
    props = cuerpo["data"]["proposals"]
    assert props, "no hay propuestas que inspeccionar"
    # Una propuesta huerfana se ve como huerfana y declara que no otorga nada.
    assert all(p["grants_coverage"] is False for p in props)
    assert all(p["proposal_state"] in
               ("PROPOSED", "CONFIRMED", "ABANDONED", "EXPIRED") for p in props)


def test_n11_reads_do_not_write_to_the_real_store(pagina):
    """[N12] en vivo: abrir la UI y leer no ensucia el almacen real."""
    pg, _ = pagina
    rel = "factory/layer9/decisions/decisions_v2.jsonl"
    antes = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", rel])
    if antes.returncode != 0:
        pytest.skip("el almacen real ya difiere de HEAD antes de la prueba")

    pg.evaluate("window.refresh && window.refresh('gobierno')")
    pg.wait_for_timeout(2000)
    pg.evaluate("window.govOpen && window.govOpen('d1-correccion')")
    pg.wait_for_timeout(1500)

    despues = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", rel])
    assert despues.returncode == 0, "leer la UI escribio en el almacen real"


def test_pilot_execution_panel_exists_and_wires_to_the_live_server(pagina):
    """RC-7 otra vez (2026-08-08): antes de esto, PILOT_EXECUTION no tenia
    panel Y no estaba en GOVERNED_FAMILIES -- un boton que no podia existir
    ni con datos. Este test prueba las dos capas contra el servidor vivo:
    el panel RENDERIZA la propuesta real PILOT_EXECUTION-2026-003 (prueba
    que get_state() ya expone la familia) y el click en el boton de
    confirmar SALE por la red y llega al backend (prueba que el panel esta
    cableado). Identidad reservada -> 422, nunca una firma real."""
    pg, errores = pagina

    # `refresh(v)` (llamado por el fixture) solo repinta datos -- NO agrega
    # la clase `.view.on` que hace visible la seccion (eso es trabajo de
    # `show(v)`, disparado normalmente por el click de navegacion). Sin esto
    # el boton real existe en el DOM pero con bounding box 0x0, y un
    # pg.click() real (a diferencia de invocar la funcion JS directo) falla
    # por "elemento no visible" -- no es un fallo de la firma, es que la
    # pestana de Gobernanza nunca se abrio.
    pg.evaluate("window.show && window.show('gobierno')")
    pg.evaluate("window.govOpen && window.govOpen('pilot-execution')")
    pg.wait_for_timeout(1500)

    texto = pg.inner_text("#gov-body")
    if "PILOT_EXECUTION-2026-003" not in texto:
        pytest.skip("PILOT_EXECUTION-2026-003 ya no esta PROPOSED en este entorno "
                     "(fue confirmada o abandonada) -- este test solo cubre el "
                     "caso con una propuesta viva pendiente")

    respuestas = []
    pg.on("response", lambda r: respuestas.append((r.url, r.status))
          if "/governance/decisions/" in r.url else None)

    pg.evaluate("""() => {
        const set=(s,v)=>{const e=document.querySelector(s); if(e) e.value=v;};
        const idField = document.querySelector('[id^="pilexec_"][id$="-id"]');
        const prefix = idField ? idField.id.replace('-id','') : null;
        if(prefix){
          set('#'+prefix+'-id', 'human');
          set('#'+prefix+'-name', 'PRUEBA AUTOMATICA -- NO ES UNA FIRMA');
          set('#'+prefix+'-reason', 'prueba de integracion -- no es una firma');
        }
    }""")
    # Click real sobre el boton, que ya trae el decision_instance_id/prefix
    # cableados en su propio onclick -- no una llamada sintetica con
    # argumentos adivinados.
    pg.click('[id^="pilexec_"][id$="-submit-btn"]')
    pg.wait_for_timeout(3000)

    confirm_status = [s for u, s in respuestas if u.endswith("/confirm")]
    assert confirm_status, ("el click no genero ningun POST de confirm -- "
                             "el boton existe pero no esta cableado a la red")
    assert confirm_status[0] == 422, (
        f"se esperaba 422 por identidad reservada; llego {confirm_status[0]}.")
    assert not errores, f"la pagina lanzo errores JS: {errores[:5]}"
