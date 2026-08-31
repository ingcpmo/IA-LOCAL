"""UI de gobernanza — W5 V2 G1.16 (GOVERNANCE_UI_SPEC.md).

Los seis paneles se prueban EJECUTANDOLOS con un DOM minimo en node, no
mirando el fichero con `grep`. La diferencia importa: un `grep` pasa en verde
sobre una funcion que lanza al primer render, y una UI de gobernanza que
revienta al abrirse deja al humano sin la superficie para decidir -- que es
justo el estado que este trabajo entero existe para cerrar.

Si node no esta disponible, los tests de render se saltan (declarado, no
silenciado). Los estructurales corren siempre.
"""
import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

REPO = Path(__file__).resolve().parents[2]
UI = REPO / "factory" / "ui"
JS = UI / "js" / "mission_control"
GOVERNANCE_JS = JS / "governance.js"

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node no disponible en el entorno")


# ---------------------------------------------------------------------------
# DOM minimo + estado de fixture
# ---------------------------------------------------------------------------

_HARNESS = """
const nodes = {};
const mkEl = id => ({ id, innerHTML:'', textContent:'', style:{},
                      parentElement:null, querySelector:()=>null });
globalThis.document = {
  getElementById: id => (nodes[id] ??= mkEl(id)),
  querySelectorAll: () => [],
};
globalThis.location = { hash:'' };
globalThis.window = { crypto:{} };
globalThis.fetch = async () => ({ok:true, json:async()=>({})});
const gov = await import(%(mod)s);
const estado = %(estado)s;
const out = {};
gov.renderGovernance(estado);
out.index = nodes['gov-body'].innerHTML;
out.panels = {};
for (const p of ['d1-correccion','d1a','excepcion-auditoria','pack-211','d2a','d4a','catalog-version',
                 'gate-e1','gate-e2','gate-e3a']) {
  gov.govOpen(p);
  out.panels[p] = nodes['gov-body'].innerHTML;
}
gov.renderGovernanceError(500, 'boom');
out.error500 = nodes['gov-body'].innerHTML;
out.state_hash_shown = nodes['gov-state-hash'].textContent;
console.log(JSON.stringify(out));
"""

FIXTURE_STATE = {
    "state_hash": "a" * 64,
    "families": {"D1": {"label": "Fuentes regulatorias"}, "D2": {"label": "Packs"},
                 "D3": {}, "D4": {}, "D5": {},
                 "ARTIFACT_VERSION": {"label": "Aprobacion de una version de artefacto gobernado"}},
    "coverage": {
        "D1": {"registry_ids": ["ecfr_21cfr_part11", "ecfr_21cfr_part211",
                                "eu_gmp_annex11", "mhra_gxp_di_guidance_2018"],
               "covered_ids": [], "uncovered_ids": ["ecfr_21cfr_part211"],
               "reconstructed_only_ids": ["ecfr_21cfr_part11"], "revoked_ids": [],
               "active_instances": [], "registry_drift_since_decision": True,
               "drift_determinable": True},
        "D2": {"registry_ids": [], "covered_ids": [], "uncovered_ids": [],
               "reconstructed_only_ids": [], "revoked_ids": [], "active_instances": []},
        "D3": {"unavailable_reason": "almacen no encontrado"},
        "D4": {"registry_ids": [], "covered_ids": [], "uncovered_ids": [],
               "reconstructed_only_ids": [], "revoked_ids": [], "active_instances": []},
        "D5": {"registry_ids": [], "covered_ids": [], "uncovered_ids": [],
               "reconstructed_only_ids": [], "revoked_ids": [], "active_instances": []},
        "ARTIFACT_VERSION": {"registry_ids": [], "covered_ids": [], "uncovered_ids": [],
               "reconstructed_only_ids": [], "revoked_ids": [], "active_instances": []},
    },
    "artifacts": {"status": "FAIL", "fail_count": 1, "warn_count": 27,
                  "artifacts_seen": 30, "records_in_store": 30},
    "audit": {"content_hash_integrity": "VERIFIED",
              "chain_continuity": "BROKEN_HISTORICAL",
              "historical_fork_present": True, "new_forks_since_baseline": 0,
              "new_fork_entry_ids": [],
              "unbacked_known_fork_entry_ids": ["ab689c7c-3e0a-4c77-936b-152851f51a30"],
              "part11_compliant": "NOT_DETERMINED", "log_count": 21572,
              "hash_errors": 0, "chain_errors": 1},
    "critical_path": [
        {"gate": "G1", "status": "CERRADO", "blocked_by": []},
        {"gate": "G2", "status": "LISTO", "blocked_by": []},
        {"gate": "G7", "status": "BLOQUEADO",
         "blocked_by": ["fork sin excepcion firmada"]},
    ],
    # G7: el estado de las medidas lo DERIVA el backend y viaja en el estado.
    # Dos sin implementar a proposito: el fixture tiene que poder ejercitar el
    # candado del boton, no solo el caso feliz.
    "preventive_measures": [
        {"id": "flock_and_cache_invalidation", "measure": "flock + invalidacion",
         "implemented": True, "evidence_kind": "SOURCE_INSPECTION", "evidence": "8c033fa"},
        {"id": "writer_identity_guard", "measure": "identidad de escritor",
         "implemented": True, "evidence_kind": "DERIVED_FROM_CHAIN", "evidence": "0 sin identidad"},
        {"id": "baseline_validated", "measure": "baseline validado",
         "implemented": True, "evidence_kind": "DERIVED_FROM_CHAIN", "evidence": "resolver responde"},
        {"id": "new_forks_fail_gate0", "measure": "fork nuevo = FAIL",
         "implemented": False, "evidence_kind": "SOURCE_INSPECTION", "evidence": "pendiente"},
        {"id": "no_silent_write_failure", "measure": "sin fallo silencioso",
         "implemented": False, "evidence_kind": "SOURCE_INSPECTION", "evidence": "pendiente"},
    ],
    "preventive_measures_complete": False,
}


def _render(tmp_path_factory, estado: dict, nombre: str) -> dict:
    if NODE is None:
        pytest.skip("node no disponible")
    script = tmp_path_factory.mktemp(nombre) / "harness.mjs"
    script.write_text(_HARNESS % {
        "mod": json.dumps(str(GOVERNANCE_JS)),
        "estado": json.dumps(estado, ensure_ascii=False),
    }, encoding="utf-8")

    proc = subprocess.run([NODE, str(script)], capture_output=True, text=True,
                          timeout=60)
    assert proc.returncode == 0, (
        f"la UI de gobernanza no renderiza:\nstdout:{proc.stdout}\nstderr:{proc.stderr}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    return _render(tmp_path_factory, FIXTURE_STATE, "gov_ui")


# Marcado inyectado en TODOS los campos de texto que el backend controla y que
# la vista muestra: ids de fuentes, etiquetas de familia, motivos de bloqueo,
# entry_ids de forks y valores de dimension.
_XSS = '<script>alert(1)</script>PAYLOAD"><img src=x onerror=alert(2)>'


@pytest.fixture(scope="module")
def hostile_render(tmp_path_factory):
    import copy
    estado = copy.deepcopy(FIXTURE_STATE)
    estado["families"]["D1"]["label"] = _XSS
    estado["coverage"]["D1"]["registry_ids"] = [_XSS, "ecfr_21cfr_part211"]
    estado["coverage"]["D1"]["uncovered_ids"] = [_XSS]
    estado["coverage"]["D1"]["reconstructed_only_ids"] = [_XSS]
    estado["coverage"]["D1"]["revoked_ids"] = [_XSS]
    estado["coverage"]["D1"]["active_instances"] = [_XSS]
    estado["coverage"]["D3"]["unavailable_reason"] = _XSS
    estado["audit"]["chain_continuity"] = _XSS
    estado["audit"]["part11_compliant"] = _XSS
    estado["audit"]["unbacked_known_fork_entry_ids"] = [_XSS]
    estado["critical_path"][2]["blocked_by"] = [_XSS]
    estado["critical_path"][2]["status"] = _XSS
    return _render(tmp_path_factory, estado, "gov_ui_xss")


# ===========================================================================
# Render real
# ===========================================================================

@needs_node
def test_the_six_panels_all_render(rendered):
    """Ninguno vacio y ninguno lanza. Un panel que revienta al abrirse deja al
    humano sin superficie para decidir.

    7, no 6: G4c (2026-07-31) agrego el panel 'catalog-version' sobre la
    familia ARTIFACT_VERSION -- el nombre del test se conserva (GOVERNANCE_UI_SPEC
    los llama "los seis paneles" como concepto original) en vez de renumerar
    todo el vocabulario del spec por un panel mas.

    10, no 7: el cierre H-1..H-10 (2026-08-31) agrego los paneles de firma
    'gate-e1'/'gate-e2'/'gate-e3a', tambien sobre ARTIFACT_VERSION."""
    assert len(rendered["panels"]) == 10
    for pid, html in rendered["panels"].items():
        assert len(html) > 400, f"panel {pid} practicamente vacio ({len(html)} bytes)"


@needs_node
def test_the_e1_e2_e3a_gate_panels_have_a_signature_surface(rendered):
    """Los tres paneles de firma del cierre H-1..H-10 tienen que traer el
    formulario de firma y un boton cableado a su govSubmitGate*. Un panel de
    firma sin superficie de firma es un panel muerto."""
    for pid, submit in [("gate-e1", "govSubmitGateE1("),
                        ("gate-e2", "govSubmitGateE2("),
                        ("gate-e3a", "govSubmitGateE3A(")]:
        html = rendered["panels"][pid]
        assert "-reason" in html, f"{pid}: falta el campo MOTIVO del signatureForm"
        assert submit in html, f"{pid}: el boton no llama a {submit}"
        assert "NO ejecuta sus efectos" in html, f"{pid}: falta el aviso NO_EJECUTA"
    # E1 pide el array de veredictos y calcula el hash en el cliente
    assert "e1-verdicts" in rendered["panels"]["gate-e1"]
    assert "govGateE1Calc(" in rendered["panels"]["gate-e1"]
    # E2/E3-A ofrecen APPROVE y REJECT
    for pid in ("gate-e2", "gate-e3a"):
        assert 'value="APPROVE"' in rendered["panels"][pid]
        assert 'value="REJECT"' in rendered["panels"][pid]


@needs_node
def test_u7_a_blocked_gate_says_why_in_the_card(rendered):
    """Lo bloqueado se muestra deshabilitado CON EL MOTIVO, jamas oculto.

    Un boton ausente es un bloqueo inexplicable.
    """
    assert "fork sin excepcion firmada" in rendered["index"]
    assert "BLOQUEADO" in rendered["index"]


@needs_node
def test_part211_checkbox_is_disabled_with_its_reason(rendered):
    """El punto pedagogico del panel A.

    El usuario tiene que VER por que Part 211 no esta en el snapshot, en vez
    de deducirlo. Mezclar la correccion con la ampliacion produciria un solo
    registro que hace dos cosas distintas.
    """
    html = rendered["panels"]["d1-correccion"]
    assert "ecfr_21cfr_part211" in html
    assert "disabled" in html
    assert "POSTERIOR a la firma" in html
    assert "D1-A" in html


@needs_node
def test_accepting_the_audit_exception_is_disabled_until_prevention_is_done(rendered):
    """Aceptar una excepcion cuya prevencion no esta implementada es aceptar
    que vuelva a pasar. Rechazar SI esta disponible: es un final legitimo.

    El conteo se DERIVA del fixture. Estaba escrito a mano ("faltan 4 de las
    5"), o sea afirmaba el mundo de aquel dia en vez de la regla, y se puso rojo
    en cuanto las medidas se implementaron de verdad -- exactamente el defecto
    que `ecc7fa6` corrigio en el guard de riesgos.
    """
    html = rendered["panels"]["excepcion-auditoria"]
    faltan = sum(1 for m in FIXTURE_STATE["preventive_measures"]
                 if not m["implemented"])
    assert "disabled" in html
    assert f"faltan {faltan} de las 5" in html
    assert "Rechazar" in html


def test_a_repeated_click_is_not_announced_as_a_new_signature():
    """Si el servidor no escribio nada, la UI no puede decir "Registrada".

    El servidor es idempotente desde el agujero de `/confirm` (tres firmas del
    mismo acto, las tres ACTIVE). Un toast de "Registrada X" sobre una escritura
    que no ocurrio es peor que no avisar: confirma al humano una accion que no
    paso, y es lo que invita al tercer clic.
    """
    js = GOVERNANCE_JS.read_text(encoding="utf-8")
    fn = js.split("function explicaFirma(", 1)[1].split("\n}", 1)[0]
    assert "already_signed" in fn
    assert "Ya estaba firmada" in fn
    assert "No se registró nada nuevo" in fn

    # Y los dos caminos de firma lo usan: el de las correcciones y el de la
    # excepcion de auditoria. El segundo arrastraba ya un defecto identico.
    assert js.count("explicaFirma(") >= 3
    assert "already_signed" in js.split("govSubmitExcepcion", 1)[1]


def test_e1_3_panel_prep_is_correct():
    """Preparación de la 3ª revisión E1 (post FIX-A + FIX-B RC-3 + FIX-C RC-2),
    verificada por inspección de fuente:

      - `E1_SAMPLE_SHA` declarado UNA sola vez y = 77e8324f… (muestra E1-3).
      - Los sha de E1-1 (f56d4bab) y E1-2 (c2ca5aaa) SÓLO dentro de
        `E1_PRIOR_REVIEWS` (append-only: las firmas previas se conservan).
      - `govGateE1Calc` exige exactamente `E1_SAMPLE_SIZE` (67) veredictos,
        vocabulario válido y sin index repetidos/faltantes.
      - Registrar E1-3 (`decision:'APPROVE'`) NO declara E1_ACCEPTANCE=PASS.
      - La evidencia activa es el paquete E1-3.
    """
    js = GOVERNANCE_JS.read_text(encoding="utf-8")
    e13 = "77e8324f333f08edb4115a1dcb65962c9daf61bc4c6b0c584af8668b783dd0a4"
    f1 = "f56d4babe7e8466368c9a6dbefe26e3716186f96e2658c68cf2f0469f5244f20"  # E1-1
    c2 = "c2ca5aaa36e9904b77cecf266cfa6645ab76949828074c857a360a5bf75ad3fd"  # E1-2

    assert js.count("const E1_SAMPLE_SHA") == 1, "E1_SAMPLE_SHA declarado más de una vez"
    assert f"const E1_SAMPLE_SHA   = '{e13}'" in js
    assert "const E1_SAMPLE_SIZE  = 67;" in js
    # los sha de revisiones previas sólo dentro de E1_PRIOR_REVIEWS
    prior_block = js.split("const E1_PRIOR_REVIEWS", 1)[1].split("\n];", 1)[0]
    assert f1 in prior_block and c2 in prior_block
    assert js.count(f1) == 1 and js.count(c2) == 1  # cada uno una sola vez, y ahí

    calc = js.split("export function govGateE1Calc(", 1)[1].split("\n}\n", 1)[0]
    assert "arr.length !== E1_SAMPLE_SIZE" in calc
    assert "E1_VOCAB.includes(v.verdict)" in calc
    assert "idx.size !== E1_SAMPLE_SIZE" in calc
    assert "v.index < 1 || v.index > E1_SAMPLE_SIZE" in calc

    submit = js.split("export async function govSubmitGateE1(", 1)[1].split("\n}\n", 1)[0]
    assert "E1_ACCEPTANCE=PASS" in submit and "does_not_imply" in submit
    assert "authenticated_confirmation_of_this_human_verdict_set" in submit
    assert "docs_plan/E1_REVIEW_PACKET_E1_3_20260831.md" in submit
    assert "sample_sha256: E1_SAMPLE_SHA" in submit
    assert "prior_reviews: E1_PRIOR_REVIEWS" in submit

    panel = js.split("function panelGateE1(", 1)[1].split("\nfunction ", 1)[0]
    assert "E1_REVIEW_PACKET_E1_3_20260831.md" in panel
    assert "E1_REVIEW_PACKET_POST_FIXA_20260831.md" not in panel  # E1-2 ya no es evidencia activa
    assert "NO declara" in panel and "E1_ACCEPTANCE=PASS" in panel


@needs_node
def test_the_index_can_actually_open_the_exception_panel(tmp_path_factory):
    """El indice tiene que poder ABRIR el panel, no solo mostrar su tarjeta.

    Con G7 en LISTO —prevencion completa, falta solo la decision— el boton "Abrir
    panel" debe estar habilitado. La tarjeta se veia y el boton estaba apagado,
    asi que la unica superficie para firmar la excepcion era inalcanzable desde
    la UI. Un panel al que no se llega es lo mismo que un panel que no existe.

    Verificar el panel llamando a `govOpen` directamente NO cubre esto: se salta
    exactamente el enlace que estaba roto.
    """
    import copy
    estado = copy.deepcopy(FIXTURE_STATE)
    for g in estado["critical_path"]:
        if g["gate"] == "G7":
            g["status"], g["blocked_by"] = "LISTO", []

    index = _render(tmp_path_factory, estado, "gov_ui_indice")["index"]
    i = index.index("govOpen('excepcion-auditoria')")
    tag = index[index.rindex("<button", 0, i):index.index(">", i)]
    assert "disabled" not in tag, tag


@needs_node
def test_the_index_still_disables_panels_blocked_by_a_real_precondition(
        tmp_path_factory):
    """La otra mitad: un gate con precondicion real SI queda cerrado.

    Ya no se usa el panel 'd2a' para este caso: commit 3a486ca/RC (2026-08-05)
    lo desacoplo a proposito de G5 (`gate:'G5-D2A'`, un id que nunca aparece
    en critical_path) precisamente porque el bloqueo real de G5
    ("packs sin cobertura D2") es lo que ESE panel existe para resolver --
    atarlo a G5 encerraria a Cesar fuera del panel que arregla G5 (ver
    comentario en PANELS, governance.js). Se usa 'd4a' (gate real 'G8') en su
    lugar, que si sigue el patron normal panel<->gate.

    El estado se construye aqui: el fixture no declara G8 en su camino critico, y
    un gate ausente no es un gate bloqueado.
    """
    import copy
    estado = copy.deepcopy(FIXTURE_STATE)
    estado["critical_path"].append(
        {"gate": "G8", "status": "BLOQUEADO",
         "blocked_by": ["G5, G6 bloqueado(s)"]})

    index = _render(tmp_path_factory, estado, "gov_ui_g8_bloqueado")["index"]
    i = index.index("govOpen('d4a')")
    tag = index[index.rindex("<button", 0, i):index.index(">", i)]
    assert "disabled" in tag, tag


@needs_node
def test_the_accept_button_opens_when_the_backend_says_prevention_is_done(
        tmp_path_factory):
    """La otra mitad del invariante: con las cinco medidas, el boton abre.

    Sin esta direccion, el test anterior lo aprobaria una UI que dejara el boton
    cerrado para siempre -- y un candado que nunca se abre no es un control, es
    un bloqueo, y ademas dejaria a Cesar sin superficie para decidir.
    """
    import copy
    estado = copy.deepcopy(FIXTURE_STATE)
    for m in estado["preventive_measures"]:
        m["implemented"] = True
    estado["preventive_measures_complete"] = True

    html = _render(tmp_path_factory, estado, "gov_ui_completas")["panels"]["excepcion-auditoria"]
    assert "de las 5 medidas" not in html

    # El tag del boton "Aceptar", no la pagina entera: buscar `disabled` en todo
    # el HTML lo encontraria en cualquier otro control y pasaria por accidente.
    i = html.index("govSubmitExcepcion('APPROVE')")
    tag = html[html.rindex("<button", 0, i):html.index(">", i)]
    assert "disabled" not in tag, tag


@needs_node
def test_a_backend_that_reports_no_measures_keeps_the_button_shut(tmp_path_factory):
    """Fail-closed: sin datos, faltan todas.

    Degradar hacia "estan todas" abriria la firma justo cuando no se sabe nada
    de la prevencion.
    """
    import copy
    estado = copy.deepcopy(FIXTURE_STATE)
    estado.pop("preventive_measures")
    estado.pop("preventive_measures_complete")

    html = _render(tmp_path_factory, estado, "gov_ui_sin_medidas")["panels"]["excepcion-auditoria"]
    assert "disabled" in html
    assert "no disponible" in html


@needs_node
def test_the_exception_panel_states_what_is_not_being_asked(rendered):
    """§7.2: la excepcion cubre UN entry_id. Decir que NO se pide es tan
    importante como decir que se pide."""
    html = rendered["panels"]["excepcion-auditoria"]
    assert "NO SE PIDE" in html
    assert "Declarar la cadena íntegra" in html
    assert "ab689c7c-3e0a-4c77-936b-152851f51a30" in html


@needs_node
def test_reconstructed_coverage_is_shown_as_not_authorizing(rendered):
    """Una D1 reconstruida se distingue Y se declara que no autoriza."""
    assert "NO autorizan" in rendered["index"]
    assert "ecfr_21cfr_part11" in rendered["index"]


@needs_node
def test_an_undeterminable_family_is_declared_not_shown_as_covered(rendered):
    """D3 con `unavailable_reason`: NO DETERMINADA, nunca "0 sin cobertura"."""
    assert "NO DETERMINADA" in rendered["index"]
    assert "almacen no encontrado" in rendered["index"]


@needs_node
def test_the_five_audit_dimensions_are_shown_separately(rendered):
    """G1.14 llega hasta la pantalla: nunca un booleano de conformidad."""
    for dim in ("CONTENT_HASH_INTEGRITY", "CHAIN_CONTINUITY",
                "HISTORICAL_FORK_PRESENT", "NEW_FORKS_SINCE_BASELINE",
                "PART11_COMPLIANCE"):
        assert dim in rendered["index"], dim
    assert "NOT_DETERMINED" in rendered["index"]
    # La buena noticia real se dice, sin arrastrar conformidad.
    assert "VERIFIED" in rendered["index"]


@needs_node
def test_a_500_shows_the_error_and_no_partial_governance_state(rendered):
    """§10: preferir un error visible a un valor por defecto."""
    html = rendered["error500"]
    assert "Error del backend" in html
    assert "NOT_DETERMINED" not in html
    assert "ecfr_21cfr_part211" not in html


@needs_node
def test_the_state_hash_is_shown_to_the_user(rendered):
    """U-4: el usuario ve sobre que estado esta a punto de firmar."""
    assert rendered["state_hash_shown"].startswith("aaaa")


# ===========================================================================
# Estructural (sin node)
# ===========================================================================

def test_u6_the_frontend_backup_is_a_real_pre_change_copy():
    """U-6 exige backup de index.html y mission_control.html antes de tocar.

    `backups/` esta en .gitignore -- correctamente: son datos de operacion, no
    codigo. Asi que este test SE SALTA si el directorio no esta, igual que el
    gate real contra GMPAI/source/Rockwell en test_source_baseline_allowlist:
    afirmar la presencia de un artefacto no versionado pasaria en esta maquina
    y fallaria en un clon limpio, que es un test que miente segun donde corra.

    Lo que si comprueba cuando el backup existe es que sea de ANTES: un backup
    tomado despues del cambio no es un backup, es una copia del cambio.
    """
    directorio = REPO / "backups" / "frontend"
    if not directorio.is_dir():
        pytest.skip("backups/frontend/ no existe en este entorno (dir gitignorado)")
    backups = sorted(directorio.glob("pre_g116_*"))
    if not backups:
        pytest.skip("sin backup pre-G1.16 en este entorno")

    previo = backups[-1] / "mission_control.html"
    assert previo.is_file(), "el backup no incluye mission_control.html"
    assert (backups[-1] / "index.html").is_file(), "U-6 exige tambien index.html"
    assert 'id="v-gobierno"' not in previo.read_text(encoding="utf-8"), (
        "el backup ya incluye la vista nueva: es una copia del cambio, no un backup")


def test_the_view_is_wired_in_html_nav_and_dispatcher():
    html = (UI / "mission_control.html").read_text(encoding="utf-8")
    assert 'data-v="gobierno"' in html
    assert 'id="v-gobierno"' in html
    assert 'id="gov-body"' in html

    refresh = (JS / "refresh.js").read_text(encoding="utf-8")
    assert "renderGovernance" in refresh
    assert "/api/v1/layer9/governance/state" in refresh
    assert "gobierno:[" in refresh

    main = (JS / "main.js").read_text(encoding="utf-8")
    for fn in ("govOpen", "govSubmitD1Correccion", "govSubmitD1A",
               "govSubmitExcepcion", "govRecalcHash"):
        assert fn in main, f"{fn} no expuesto como global: los onclick del HTML fallarian"


def test_every_exported_handler_used_in_html_is_exported_by_the_module():
    """Los `onclick` generados llaman por nombre global. Un nombre que el
    modulo no exporte es un boton que no hace nada y no avisa."""
    import re
    js = GOVERNANCE_JS.read_text(encoding="utf-8")
    usados = set(re.findall(r'onclick="(gov[A-Za-z]+)\(', js))
    exportados = set(re.findall(r"export (?:async )?function (gov[A-Za-z]+)", js))
    assert usados <= exportados, f"handlers sin exportar: {usados - exportados}"


def test_the_legacy_w5_view_is_not_removed():
    """Conviven durante la transicion y la vieja se retira en G8.

    Apagarla ahora dejaria sin superficie a lo unico que hoy tiene datos.
    """
    html = (UI / "mission_control.html").read_text(encoding="utf-8")
    assert 'data-v="w5"' in html
    assert (JS / "w5_decisions.js").is_file()


@needs_node
def test_api_data_is_escaped_before_reaching_innerhtml(hostile_render):
    """Se RENDERIZA con una respuesta hostil y se comprueba la salida.

    La primera version de este test buscaba interpolaciones sin `esc()` con una
    regex sobre el fichero, y era un mal test: no sabe parsear plantillas
    anidadas, asi que marcaba `dimClass(v)` (devuelve una constante CSS), `cls`
    (nombre de clase literal), `prefix` (constante interna) y `a.log_count` (un
    numero) -- 21 hallazgos y ninguno real, porque el escapado ocurre una capa
    mas adentro (`fila()` hace `esc(extra)`, `chips()` escapa cada id).

    Una guardia con falsos positivos estructurales se acaba borrando entera, y
    con ella la proteccion real. Esta version prueba la PROPIEDAD -- ningun
    marcado del backend llega vivo a la pantalla -- en vez de inspeccionar la
    forma del codigo, y por eso no se puede esquivar reordenando plantillas.
    """
    superficies = {"index": hostile_render["index"],
                   "error500": hostile_render["error500"],
                   **{f"panel:{k}": v for k, v in hostile_render["panels"].items()}}
    for nombre, html in superficies.items():
        # La propiedad exacta: el payload NO aparece literal en ningun sitio.
        # Basta con eso -- sin `<` sin escapar no se puede formar una etiqueta,
        # y por tanto ningun atributo ni handler.
        assert _XSS not in html, f"{nombre}: el payload del backend llego literal"
        assert "<script" not in html.lower(), f"{nombre}: <script> del backend sin escapar"
        assert "<img" not in html.lower(), f"{nombre}: <img> del backend sin escapar"

    # `onerror=` SI sobrevive como texto escapado dentro de un <td>, y debe:
    # es parte del dato. Lo que no puede es venir precedido de un `<` vivo.
    idx = hostile_render["index"]
    assert "onerror=" in idx, "el dato desaparecio en vez de escaparse"
    assert "&lt;img" in idx, "el `<` del payload no quedo escapado"


@needs_node
def test_the_hostile_payload_is_actually_visible_as_text(hostile_render):
    """El escapado no puede ser "borrar el dato".

    Si un `source_id` llega con marcado, hay que MOSTRARLO tal cual escapado:
    un id que desaparece de la pantalla es peor que uno feo -- el humano firma
    creyendo que ese id no esta en el conjunto.
    """
    assert "&lt;script&gt;" in hostile_render["index"] or "&lt;" in hostile_render["index"]
    assert "PAYLOAD" in hostile_render["index"]


@needs_node
def test_pack211_panel_only_offers_revoke_while_the_fabricated_coverage_is_live(
        tmp_path_factory):
    """W5V2_FIX_FIRMA_SILENCIOSA §3.3 -- defecto real cerrado el 2026-07-30:
    el panel seguia ofreciendo "Revocar D2-2026-003" despues de que Cesar YA
    la habia revocado (D2-2026-005), porque `incidenteRevocable()` solo
    miraba si D2-2026-003 estaba confirmada, sin mirar si la cobertura
    seguia vigente. Las dos mitades del invariante, en el mismo estado base
    que produjo el incidente real."""
    import copy

    estado_incidente_activo = copy.deepcopy(FIXTURE_STATE)
    estado_incidente_activo["coverage"]["D2"]["covered_ids"] = ["21_CFR_211.68(b)"]
    estado_incidente_activo["coverage"]["D2"]["confirmed_active_instances"] = ["D2-2026-003"]

    panel_activo = _render(tmp_path_factory, estado_incidente_activo,
                           "gov_ui_d2_incidente_activo")["panels"]["pack-211"]
    assert "INCIDENTE" in panel_activo
    assert "govSubmitRevokeD2003" in panel_activo
    assert "govSubmitPack211()\">Registrar aprobación" not in panel_activo

    estado_ya_revocado = copy.deepcopy(FIXTURE_STATE)
    estado_ya_revocado["coverage"]["D2"]["covered_ids"] = []
    estado_ya_revocado["coverage"]["D2"]["revoked_ids"] = ["21_CFR_211.68(b)"]
    estado_ya_revocado["coverage"]["D2"]["confirmed_active_instances"] = [
        "D2-2026-003", "D2-2026-005"]

    panel_revocado = _render(tmp_path_factory, estado_ya_revocado,
                             "gov_ui_d2_ya_revocado")["panels"]["pack-211"]
    assert "INCIDENTE" not in panel_revocado
    assert "govSubmitRevokeD2003" not in panel_revocado
    assert "govSubmitPack211()\">Registrar aprobación" in panel_revocado


# ===========================================================================
# G4c -- panel del catálogo, hallazgo real del panel ARQ (2026-08-04):
# texto fijo desactualizado + propuestas de OTRO artefacto mezcladas.
# ===========================================================================

CATALOG_ARTIFACT_ID = "factory/regulatory/requirement_catalog/requirements.yaml"
GOLDEN_ARTIFACT_ID = "factory/regulatory/golden_dataset/semantic_verification_golden_dataset.py"


def _catalog_version_estado(tmp_path_factory=None, **overrides):
    import copy
    estado = copy.deepcopy(FIXTURE_STATE)
    estado["artifacts"]["catalog_state"] = {
        "artifact_id": CATALOG_ARTIFACT_ID, "found": True,
        "live_version": "2.0", "live_sha256": "7ae4aaf2" + "0" * 56,
        "last_approved_version": "2.0", "last_approved_sha256": "dc017efb" + "0" * 56,
        "approved_by_decision": "ARTIFACT_VERSION-2026-002",
    }
    estado["proposals"] = {"ARTIFACT_VERSION": [
        {  # -001: la propuesta original, ya resuelta -- confirmada por -002
            "decision_instance_id": "ARTIFACT_VERSION-2026-001",
            "resolved_target_ids": [CATALOG_ARTIFACT_ID],
            "payload": {}, "proposal_state": "CONFIRMED"},
        {  # -003: historica, payload vacio -- ya no aplicable tras el fix
            "decision_instance_id": "ARTIFACT_VERSION-2026-003",
            "resolved_target_ids": [CATALOG_ARTIFACT_ID],
            "payload": {}, "proposal_state": "PROPOSED"},
        {  # -004: OTRO artefacto -- nunca debe aparecer en este panel
            "decision_instance_id": "ARTIFACT_VERSION-2026-004",
            "resolved_target_ids": [GOLDEN_ARTIFACT_ID],
            "payload": {"artifact_path": GOLDEN_ARTIFACT_ID}, "proposal_state": "PROPOSED"},
        {  # -005: la transicion EXACTA sobre el estado vivo -- la unica firmable
            "decision_instance_id": "ARTIFACT_VERSION-2026-005",
            "resolved_target_ids": [CATALOG_ARTIFACT_ID],
            "payload": {"artifact_path": CATALOG_ARTIFACT_ID,
                       "artifact_hash_before": "7ae4aaf2" + "0" * 56,
                       "from_version": "2.0", "to_version": "2.1",
                       "expected_hash_after": "7ae4aaf2" + "0" * 56},
            "proposal_state": "PROPOSED"},
    ]}
    for k, v in overrides.items():
        estado[k] = v
    return estado


def test_catalog_panel_shows_the_live_transition_not_frozen_text(tmp_path_factory):
    """El estado se lee de `GOV.artifacts.catalog_state` (vivo, calculado),
    nunca de un texto fijo -- "1.0 → 2.0" no debe aparecer cuando el estado
    vivo real es 2.0 con hash cambiado."""
    estado = _catalog_version_estado()
    panel = _render(tmp_path_factory, estado, "gov_ui_catv_vivo")["panels"]["catalog-version"]
    assert "1.0 → 2.0" not in panel
    assert "2.0" in panel
    assert "7ae4aaf2" in panel


def test_catalog_panel_filters_proposals_by_artifact_and_excludes_golden_dataset(tmp_path_factory):
    """-004 (golden_dataset) NUNCA aparece en el panel del catálogo -- el
    filtro es por `resolved_target_ids`/`payload.artifact_path`, no "todas
    las propuestas ARTIFACT_VERSION"."""
    estado = _catalog_version_estado()
    panel = _render(tmp_path_factory, estado, "gov_ui_catv_filtrado")["panels"]["catalog-version"]
    assert "ARTIFACT_VERSION-2026-004" not in panel
    assert "ARTIFACT_VERSION-2026-001" in panel
    assert "ARTIFACT_VERSION-2026-003" in panel
    assert "ARTIFACT_VERSION-2026-005" in panel


def test_catalog_panel_enables_signature_only_for_the_valid_proposal(tmp_path_factory):
    """El boton queda habilitado y atado a -005 (la unica con from_version/
    hash coincidiendo con el estado vivo) -- nunca a -001/-003 (payload
    vacio) ni a -004 (otro artefacto)."""
    estado = _catalog_version_estado()
    panel = _render(tmp_path_factory, estado, "gov_ui_catv_valida")["panels"]["catalog-version"]
    assert "Confirmar ARTIFACT_VERSION-2026-005" in panel
    assert 'id="catv-submit-btn" ' in panel and 'disabled' not in panel.split(
        'id="catv-submit-btn"')[1].split('>')[0]


def test_catalog_panel_disables_signature_when_no_proposal_matches_live_state(tmp_path_factory):
    """Si NINGUNA propuesta declara la transicion exacta sobre el estado
    vivo (p.ej. solo quedan -001/-003/-004), el boton se deshabilita -- nunca
    se ofrece firmar sobre una propuesta que no aplica."""
    estado = _catalog_version_estado()
    estado["proposals"]["ARTIFACT_VERSION"] = [
        p for p in estado["proposals"]["ARTIFACT_VERSION"]
        if p["decision_instance_id"] != "ARTIFACT_VERSION-2026-005"]
    panel = _render(tmp_path_factory, estado, "gov_ui_catv_sin_valida")["panels"]["catalog-version"]
    assert 'id="catv-submit-btn" disabled' in panel
    assert "No hay ninguna propuesta con la transición vigente" in panel
