/* W5 V2 G1.16 — Gobernanza de decisiones: los seis paneles.

   Vista SEPARADA de "Decisiones W5" a propósito, y conviven durante la
   transición: aquella lee el almacén legacy (w5_human_decisions), esta lee el
   modelo nuevo (familias + resolver). Se retira la vieja en G8, no antes —
   apagarla ahora dejaría sin superficie a lo único que hoy tiene datos.

   Un panel es una VISTA SOBRE UNA FAMILIA, no un sistema aparte: los seis
   usan los mismos endpoints (/governance/state, /coverage/{f}, propose,
   confirm, return, reject). Es la traducción a UI de "un modelo, un almacén,
   una lectura".

   Reglas que este módulo implementa (GOVERNANCE_UI_SPEC §1):

     U-4  cada POST reenvía el `state_hash` del GET. Dos pestañas abiertas
          firmando sobre datos que ya no existen es el fork de la cadena de
          auditoría trasladado a la capa humana.
     U-5  registrar NO ejecuta. La leyenda es permanente, no un toast.
     U-7  lo bloqueado se muestra DESHABILITADO CON EL MOTIVO, jamás oculto.
          Un botón ausente es un bloqueo inexplicable.
     U-8  todo valor de gobernanza viaja con su procedencia.

   §10 sobre el 500: esta vista NUNCA muestra un estado de gobernanza que no
   pudo leer. Prefiere un error visible a un valor por defecto — un
   `uncovered` vacío porque el backend cayó es indistinguible de uno vacío de
   verdad, y esa ambigüedad es la que este trabajo entero existe para
   eliminar. */

import { API_BASE, headers } from './state.js';
import { toast } from './core.js';

const esc = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

/* Último estado leído. El `state_hash` que viaja en cada POST sale de aquí:
   si el usuario no ha recargado, firma sobre lo que vio. */
let GOV = null;

/* W5V2_FIX_FIRMA_SILENCIOSA (2026-07-31), H1: un toast se desvanece en 2.2s
   -- si nadie mira la esquina en ese instante exacto, un 409/422 real se lee
   como "no paso nada". `GOV_STALE` detecta la causa MAS PROBABLE del 409
   (sesion abierta desde antes de que otra firma o fix cambiara el estado)
   de forma PROACTIVA, antes de que el clic falle: al recuperar foco la
   pestaña, se relee el state_hash; si difiere, se bloquea la firma con un
   motivo explicito en vez de dejar que el POST reviente en silencio. */
let GOV_STALE = false;

const PANELS = [
  { id:'d1-correccion',      gate:'G2', family:'D1', titulo:'Corrección D1 — Fuentes regulatorias',
    resumen:'Materializa el snapshot que "ALL" nunca materializó.' },
  { id:'d1a',                gate:'G2', family:'D1', titulo:'D1-A — Adendo de cobertura',
    resumen:'Extiende la cobertura a 21 CFR Part 211, sin tocar la Corrección.' },
  { id:'pack-211',           gate:'G4', family:'D2', titulo:'Revisión del pack 21 CFR 211.68(b)',
    resumen:'Regla predicado cGMP: control de cambios, exactitud I/O y respaldo. Contenido redactado, pendiente de tu aprobación.' },
  { id:'d2a',                gate:'G5-D2A', family:'D2', titulo:'D2-A — Aprobación de Evidence Packs',
    /* NUNCA 'G5' a secas aqui, aunque sea el gate topicamente correcto
       ("D2-A: aprobacion de Evidence Packs"): su bloqueo real de HOY es
       "packs sin cobertura D2" -- literalmente lo que este panel existe
       para resolver. Con gate:'G5' el boton "Abrir panel" quedaria
       deshabilitado por el propio problema que el panel debe arreglar,
       encerrando a Cesar afuera. Mismo aprendizaje que golden-dataset
       (commit 3a486ca), version mas sutil: aqui el gate SI describe el
       panel correctamente y aun asi hay que evitarlo. */
    resumen:'Criterios interpretativos, pack a pack. Sin "apruebo todos".' },
  { id:'excepcion-auditoria',gate:'G7', family:'AUDIT_EXCEPTION', titulo:'Excepción de auditoría histórica',
    resumen:'FORK-2026-06-15-001. Aceptar o rechazar, con causa raíz establecida.' },
  { id:'d4a',                gate:'G8', family:'D4', titulo:'D4-A — Presupuesto de corrida',
    resumen:'Límites duros derivados, no escritos a mano.' },
  { id:'catalog-version',    gate:'G4', family:'ARTIFACT_VERSION', titulo:'Versionado del catálogo (G4c)',
    /* RC-3 (panel ARQ, 2026-08-04): este resumen tenia "1.0 -> 2.0" fijo --
       la transicion real cambia con el tiempo (hoy es 2.0->2.1) y vive en el
       endpoint, nunca en un literal del indice. */
    resumen:'Bump de versión del catálogo (transición vigente en el panel). Registrar NO lo aplica: ver factory/core/artifact_version_apply.py.' },
  /* RC-7 (panel ARQ, 2026-08-05): estos dos NO tenían panel -- caían a
     panelPendiente() (solo "Volver al índice", sin formulario) porque nadie
     les escribió el cuerpo. APPLICABILITY_MATRIX tampoco estaba en
     GOVERNED_FAMILIES del backend, así que ni siquiera había datos que un
     panel pudiera leer. Cesar firmó varias veces sin que nada llegara al
     servidor: no era un 409 silencioso, era un botón que nunca existió. */
  { id:'applicability-matrix', gate:'G6', family:'APPLICABILITY_MATRIX', titulo:'Matriz de aplicabilidad — versión vigente',
    resumen:'Confirma la versión vigente de la matriz. Precondición de G5 (D2-A) y de la recalificación del modelo.' },
  { id:'golden-dataset',     gate:'G6-GD', family:'ARTIFACT_VERSION', titulo:'Golden Dataset — primera aprobación (G6)',
    /* NUNCA 'G5' ni 'G6' a secas -- ya son gates REALES del camino critico
       interno (G5 = D2-A/Evidence Packs, G6 = Matriz de aplicabilidad) y
       significan algo distinto. Reusar 'G5' aqui (defecto real, 2026-08-05)
       le pego a este panel el bloqueo AJENO de "packs sin cobertura D2" y
       goveOpen() nunca dejaba ni abrirlo. Un id que no existe en
       GOV.critical_path resuelve a {status:'?'} via gateOf() -- nunca
       BLOQUEADO, nunca hereda un motivo que no es el suyo. */
    resumen:'Otorga la primera cobertura formal al dataset bootstrapeado, sin cambiar su contenido ni versión.' },
  { id:'source-currency',   gate:'G3', family:'SOURCE_CURRENCY', titulo:'Vigencia regulatoria de fuentes (G3)',
    /* Aqui SI es correcto reusar 'G3': su bloqueo real (G2 sin cerrar) es
       una precondicion legitima de este panel -- source_currency_checker.py
       ya lo exige antes de salir a la red (§ "COBERTURA DE DECISION ANTES
       DE LA RED"). No es el mismo error que 'G5'/'G6' en golden-dataset:
       ahi el bloqueo prestado no tenia relacion real con el panel. */
    resumen:'Un hash identico no prueba vigencia normativa -- el juicio de que la norma sigue vigente lo declara quien firma, fuente por fuente.' },
  { id:'matrix-version-regularizacion', gate:'G6-MVR', family:'ARTIFACT_VERSION',
    titulo:'Matriz de aplicabilidad — regularización de versión (G6)',
    /* Mismo motivo que golden-dataset para el gate ficticio: 'G6' a secas
       es el bloqueo REAL de "versión 2.1->2.2 sin decisión ACTIVE que la
       apruebe" -- justo lo que este panel existe para resolver. Con
       gate:'G6' el boton quedaria deshabilitado por el propio problema
       que hay que arreglar. Distinto del panel 'applicability-matrix'
       (familia APPLICABILITY_MATRIX, aprueba el CONTENIDO de una version):
       este es ARTIFACT_VERSION, la MISMA invariante hash<->version<->decision
       que ya protege al catalogo (G4c) -- aqui aplicada, por primera vez, a
       un cambio que ya esta en disco (commit 84a7a58, V6) sin decision
       previa. */
    resumen:'Regulariza 2.1→2.2 (V6, document_types) enlazando APPLICABILITY_MATRIX-2026-006 como fundamento humano. No reescribe el archivo: ya está correcto.' },
  { id:'source-origin-verification', gate:'G3', family:'SOURCE_ORIGIN_VERIFICATION',
    titulo:'Segunda observación de origen (G3, DEC-B)',
    /* Igual que source-currency, 'G3' es correcto reusar: el bloqueo real
       (G2 sin cerrar) es una precondicion legitima. Familia DISTINTA de
       SOURCE_CURRENCY -- esa declara vigencia normativa (un hash identico
       no prueba que la norma siga vigente); esta declara procedencia del
       archivo (que existe una segunda observacion real contra el mismo
       origen oficial, el dato que source_lifecycle.py exige para dejar de
       ser NOT_COMPARABLE_FIRST_INGESTION). No tiene campo de juicio humano
       libre como source-currency: un hash coincidente ya prueba el hecho
       por si mismo, no requiere interpretacion regulatoria. */
    resumen:'Promueve el ámbar FIRST_INGESTION a VERIFIED_AGAINST_PRIOR_KNOWN_HASH cuando una segunda reingesta real coincidió con el origen oficial ya gobernado.' },
  { id:'corpus-authorization', gate:'G8', family:'CORPUS_AUTHORIZATION',
    titulo:'Autorización de corpus — go/no-go (plan Bloque 6)',
    /* Distinta de D4-A: D4 dice CUANTO cuesta: esta dice SI se ejecuta,
       atada al run_fingerprint exacto (catalogo/prompts/modelo/golden
       dataset). NUNCA lanza ninguna corrida -- el runner real es una
       pieza de infraestructura aparte, todavia no construida a proposito
       (plan Bloque 6: "en ESTA corrida, llegar hasta dejar todo listo
       para la autorizacion"). */
    resumen:'Go/no-go atado al fingerprint exacto de configuración. Firmar esto NO lanza ninguna corrida — el runner es una pieza aparte, aún no construida.' },
  { id:'pilot-execution', gate:'PILOT', family:'PILOT_EXECUTION',
    titulo:'Piloto de diagnóstico — alcance acotado (pre-corpus)',
    /* gate:'PILOT' es deliberadamente un id que no existe en G1..G8: no hay
       precondicion real que este panel deba heredar (mismo patron que
       golden-dataset/G6-GD), asi que gateOf() resuelve a {status:'?'} y el
       boton nunca queda bloqueado por un gate ajeno. Encontrado 2026-08-08
       (mismo defecto de RC-7) ANTES de que Cesar terminara de intentar
       firmar PILOT_EXECUTION-2026-003 sin panel que lo mostrara. */
    resumen:'Alcance EXPLICITO (documento/agente/requisito) y tope duro de llamadas. NUNCA autoriza CORPUS_AUTHORIZATION ni D4 -- familia separada, ninguna otra la lee.' },
  { id:'embed-execution', gate:'EMBED', family:'EMBED_EXECUTION',
    titulo:'Capa semántica local — llamadas de embedding (R2.2 §4.2)',
    /* gate:'EMBED' es deliberadamente un id fuera de G1..G8 (mismo motivo
       que 'PILOT'): no hay precondicion real que heredar. Familia NUEVA
       (2026-08-10, docs_plan/R2_2_CIERRE_Y_CAPA_SEMANTICA.md sec.4.2):
       un embedding es un vector determinista, NO es juicio LLM -- separada
       de PILOT_EXECUTION a proposito, para que el presupuesto de recall de
       juicio nunca se mezcle con el de recuperacion semantica. */
    resumen:'Vectores deterministas (nomic-embed-text local) para medir recuperación semántica -- NUNCA juicio LLM, nunca autoriza PILOT_EXECUTION/CORPUS_AUTHORIZATION/D4.' },
  { id:'prompt-version-regularizacion', gate:'G-PV', family:'ARTIFACT_VERSION',
    titulo:'Prompts gobernados — regularización de versión (R2.1 Causa 2)',
    /* Mismo patron que matrix-version-regularizacion (RC-7/G6-MVR): un
       cambio que YA esta en disco (bump 1.1.0->1.1.1 de los 3 prompts,
       commit d42d919, contenido ya aprobado por Cesar en chat al aprobar
       ese commit) sin decision ARTIFACT_VERSION que cubra la invariante
       hash<->version<->decision -- encontrado por el guard (fail_count=3)
       durante el Gate 0 de R2.1 Opcion C, 2026-08-10. gate:'G-PV' es
       deliberadamente un id fuera de G1..G8 (mismo motivo que 'PILOT'):
       no hay precondicion real que heredar, el boton nunca queda
       bloqueado por un gate ajeno. */
    resumen:'3 prompts (part11/annex11/alcoa), cada uno 1.1.0→1.1.1 sin decisión ACTIVE que lo cubra. No reescribe ningún YAML: ya están en el estado que esta firma aprueba.' },
];

const GOLDEN_DATASET_ARTIFACT_ID = 'factory/regulatory/golden_dataset/semantic_verification_golden_dataset.py';

const CATALOG_ARTIFACT_ID = 'factory/regulatory/requirement_catalog/requirements.yaml';

const MATRIX_ARTIFACT_ID = 'factory/regulatory/applicability_matrix.yaml';

/* R2.1 Opción C (2026-08-10): lista explícita y acotada, igual que en
   governance_service.py -- agregar un 4º prompt gobernado a esta
   regularización es una decisión propia, no un efecto automático. */
const PROMPT_ARTIFACT_IDS = [
  'factory/engines/gmpai_integrity/prompts/part11_prompts.yaml',
  'factory/engines/gmpai_integrity/prompts/annex11_prompts.yaml',
  'factory/engines/gmpai_integrity/prompts/alcoa_prompts.yaml',
];
const PROMPT_STATUS_PREFIX = { // prefijo corto para cada form de firma (pp1/pp2/pp3)
  'factory/engines/gmpai_integrity/prompts/part11_prompts.yaml': 'pp1',
  'factory/engines/gmpai_integrity/prompts/annex11_prompts.yaml': 'pp2',
  'factory/engines/gmpai_integrity/prompts/alcoa_prompts.yaml': 'pp3',
};

/* ── error explícito, nunca un placeholder ─────────────────────────────── */

export function renderGovernanceError(status, detail){
  const el = document.getElementById('gov-body'); if(!el) return;
  const label = status===401||status===403 ? 'Sesión no autorizada'
              : status===404 ? 'Endpoint no encontrado'
              : status>=500 ? 'Error del backend'
              : 'Error';
  el.innerHTML = `<div class="card">
    <div class="meta" style="color:var(--fail);font-weight:600">
      ${esc(label)} — HTTP ${esc(status)}</div>
    <div class="meta" style="margin-top:6px">${esc(detail||'sin detalle')}</div>
    <div class="meta" style="margin-top:6px;color:var(--faint)">
      GET /api/v1/layer9/governance/state</div>
    <div class="meta" style="margin-top:10px;color:var(--warn)">
      No se muestra ningún estado de gobernanza parcial: un valor por defecto
      sería indistinguible de uno real.</div>
  </div>`;
}

/* ── dimensiones de la cadena (G1.14) ──────────────────────────────────── */

function dimClass(v){
  if(v==='VERIFIED'||v==='COMPLIANT') return 'var(--pass)';
  if(v==='ACCEPTED_WITH_DOCUMENTED_EXCEPTION') return 'var(--warn)';
  if(v==='NOT_DETERMINED'||v==='BROKEN_HISTORICAL') return 'var(--warn)';
  return 'var(--fail)';
}

function auditDimensions(a){
  const fila = (k,v,extra='') => `<tr>
    <td class="mono">${esc(k)}</td>
    <td class="mono" style="color:${dimClass(v)};font-weight:600">${esc(v)}</td>
    <td class="meta">${esc(extra)}</td></tr>`;
  return `<table class="tbl" style="width:100%;font-size:11px">
    <thead><tr><th>Dimensión</th><th>Valor</th><th></th></tr></thead><tbody>
    ${fila('CONTENT_HASH_INTEGRITY', a.content_hash_integrity,
           `${a.hash_errors} errores de hash / ${a.log_count} entradas`)}
    ${fila('CHAIN_CONTINUITY', a.chain_continuity,
           `${a.chain_errors} ruptura(s) de enlace`)}
    ${fila('HISTORICAL_FORK_PRESENT', String(a.historical_fork_present),
           (a.unbacked_known_fork_entry_ids||[]).join(', '))}
    ${fila('NEW_FORKS_SINCE_BASELINE', String(a.new_forks_since_baseline),
           (a.new_fork_entry_ids||[]).join(', '))}
    ${fila('PART11_COMPLIANCE', a.part11_compliant,
           a.part11_compliant==='NOT_DETERMINED'
             ? 'exige una excepción humana registrada' : '')}
    </tbody></table>
    <div class="meta" style="margin-top:6px;color:var(--faint)">
      Ninguna dimensión se deriva de otra. Que el contenido sea auténtico
      (hash_errors=0) es cierto y NO implica conformidad: la continuidad
      verificable de la secuencia es otra condición, y está rota.</div>`;
}

/* ── cobertura de una familia ──────────────────────────────────────────── */

function coverageBlock(family, c){
  if(!c) return '<div class="meta">(sin datos)</div>';
  if(c.unavailable_reason){
    return `<div class="meta" style="color:var(--warn)">
      NO DETERMINADA — ${esc(c.unavailable_reason)}</div>`;
  }
  const chips = (ids,cls) => (ids||[]).map(i=>
    `<span class="chip ${cls}" style="margin:2px">${esc(i)}</span>`).join('') || '<span class="meta">—</span>';
  return `<div class="meta">cubiertas: <b>${(c.covered_ids||[]).length}</b>
      · sin cobertura: <b style="color:var(--fail)">${(c.uncovered_ids||[]).length}</b>
      · drift del registry: <b>${c.registry_drift_since_decision ? 'SÍ'
        : (c.drift_determinable ? 'no' : 'NO DETERMINABLE')}</b></div>
    <div style="margin-top:6px"><span class="meta">sin cobertura:</span> ${chips(c.uncovered_ids,'c-fail')}</div>
    ${(c.reconstructed_only_ids||[]).length ? `<div style="margin-top:4px">
      <span class="meta">solo reconstruidas (NO autorizan):</span> ${chips(c.reconstructed_only_ids,'c-warn')}</div>`:''}
    ${(c.revoked_ids||[]).length ? `<div style="margin-top:4px">
      <span class="meta">revocadas:</span> ${chips(c.revoked_ids,'c-fail')}</div>`:''}
    ${(c.confirmed_active_instances||[]).length ? `<div class="meta" style="margin-top:4px">
      decisiones FIRMADAS y vigentes: <span class="mono">${esc((c.confirmed_active_instances||[]).join(', '))}</span></div>`:`
      <div class="meta" style="margin-top:4px;color:var(--warn)">
        ninguna decisión firmada y vigente</div>`}
    ${(() => {
      /* Las PROPUESTAS se cuentan aparte y se dicen propuestas. Antes se
         mostraba `active_instances`, que incluye las no confirmadas porque
         `status: ACTIVE` en el esquema significa "no superseded" y no "vigente
         como decisión": 55 propuestas huérfanas de D1 se leían como decisiones
         ACTIVE. Presentar residuo como gobernanza es peor que no mostrar nada. */
      const props = (c.active_instances||[]).filter(
        i => !(c.confirmed_active_instances||[]).includes(i));
      return props.length ? `<div class="meta" style="margin-top:4px;color:var(--faint)">
        propuestas sin firmar (NO otorgan cobertura): <b>${props.length}</b>
        <span class="mono">${esc(props.slice(-3).join(', '))}${props.length>3?' …':''}</span></div>` : '';
    })()}`;
}

/* ── índice: seis tarjetas + camino crítico ────────────────────────────── */

function gateOf(gid){
  return (GOV?.critical_path||[]).find(g=>g.gate===gid) || {status:'?', blocked_by:[]};
}

function panelCard(p){
  const g = gateOf(p.gate);
  const bloqueado = g.status === 'BLOQUEADO';
  const cls = g.status==='CERRADO' ? 'c-pass' : bloqueado ? 'c-fail' : 'c-warn';
  return `<div class="card" style="margin-bottom:10px">
    <div style="display:flex;align-items:center;gap:8px">
      <span class="chip ${cls}">${esc(p.gate)} · ${esc(g.status)}</span>
      <b>${esc(p.titulo)}</b>
      <div class="spacer" style="flex:1"></div>
      <button ${bloqueado?'disabled':''} onclick="govOpen('${esc(p.id)}')">Abrir panel</button>
    </div>
    <div class="meta" style="margin-top:6px">${esc(p.resumen)}</div>
    ${bloqueado ? `<div class="meta" style="margin-top:6px;color:var(--warn)">
      BLOQUEADO — falta: ${esc((g.blocked_by||[]).join(' · '))}</div>` : ''}
  </div>`;
}

function indexView(){
  const a = GOV.audit;
  return `
  <div class="card" style="margin-bottom:14px">
    <b>Estado de la cadena de auditoría, por dimensión</b>
    ${auditDimensions(a)}
  </div>
  <div class="card" style="margin-bottom:14px">
    <b>Cobertura de decisión humana</b>
    ${['D1','D2','D3','D4','D5'].map(f=>`
      <div style="margin-top:8px">
        <div class="mono" style="font-weight:600">${esc(f)} — ${esc(GOV.families?.[f]?.label||'')}</div>
        ${coverageBlock(f, GOV.coverage?.[f])}
      </div>`).join('')}
  </div>
  ${PANELS.map(panelCard).join('')}
  <div class="card">
    <b>Camino crítico</b>
    <table class="tbl" style="width:100%;font-size:11px;margin-top:6px">
      <thead><tr><th>Gate</th><th>Estado</th><th>Qué falta</th></tr></thead><tbody>
      ${(GOV.critical_path||[]).map(g=>`<tr>
        <td class="mono">${esc(g.gate)}</td>
        <td><span class="chip ${g.status==='CERRADO'?'c-pass':g.status==='BLOQUEADO'?'c-fail':'c-warn'}">${esc(g.status)}</span></td>
        <td class="meta">${esc((g.blocked_by||[]).join(' · ')) || '—'}</td>
      </tr>`).join('')}
      </tbody></table>
  </div>`;
}

/* ── feedback visible y persistente por rama de respuesta ───────────────
   W5V2_FIX_FIRMA_SILENCIOSA §2. `toast()` sigue llamandose (redundancia
   deliberada), pero la fuente de verdad para depurar a distancia es esta
   linea: no se desvanece sola, lleva timestamp, y sobrevive a que Cesar
   mire la pantalla un segundo despues del clic en vez de en el instante
   exacto. */
function statusLine(prefix){
  return `<div id="${prefix}-status" class="meta" style="margin-top:8px;min-height:1.4em"></div>`;
}

function setStatus(prefix, kind, text){
  const el = document.getElementById(prefix+'-status');
  const color = kind==='ok' ? 'var(--pass)' : kind==='busy' ? 'var(--faint)'
              : kind==='warn' ? 'var(--warn)' : 'var(--fail)';
  const ts = new Date().toTimeString().slice(0,8);
  if(el) el.innerHTML = `<span style="color:${color}">[${esc(ts)}] ${esc(text)}</span>`;
  if(kind !== 'busy') toast(text);
}

/* Estados visibles del boton: habilitado / en vuelo (spinner+disabled) /
   restaurado. `dataset.origLabel` guarda el texto original UNA sola vez
   (llamadas repetidas de setBusy(true) no lo pisan con "Enviando…"). */
function setBusy(btnId, busy, busyLabel){
  const b = document.getElementById(btnId); if(!b) return;
  if(busy){
    if(b.dataset.origLabel === undefined) b.dataset.origLabel = b.textContent;
    b.disabled = true;
    b.textContent = busyLabel || 'Enviando…';
  } else {
    if(b.dataset.origLabel !== undefined) b.textContent = b.dataset.origLabel;
    b.disabled = false;
  }
}

/* ── formulario de firma, común a los paneles que registran ────────────── */

/* Paquete 2 (hallazgo M, 2026-08-19): la identidad que FIRMA ya no la
   declara este formulario -- se resuelve server-side desde tu
   IDENTITY KEY de sesión (state.js). El campo "nombre para mostrar" que
   queda aqui es puramente cosmetico (approved_by_display_name/
   rejected_by_display_name), nunca la identidad autorizante. */
function signatureForm(prefix, {motivoLabel='MOTIVO'}={}){
  return `
  <div style="margin-top:12px;display:grid;grid-template-columns:150px 1fr;gap:6px;align-items:center">
    <label class="meta">${esc(motivoLabel)} *</label>
    <input id="${prefix}-reason" placeholder="por qué se registra esta decisión">
    <label class="meta">FIRMA — nombre</label>
    <input id="${prefix}-id" placeholder="nombre para mostrar (cosmético)">
  </div>
  <div class="meta" style="margin-top:6px;color:var(--faint)">
    Quien firma se resuelve de tu IDENTITY KEY de sesión (arriba a la
    derecha) -- este campo es solo un nombre para mostrar en pantalla.
  </div>`;
}

function readSignature(prefix){
  return {
    reason: document.getElementById(prefix+'-reason')?.value.trim() || '',
    id: document.getElementById(prefix+'-id')?.value.trim() || '',
    name: document.getElementById(prefix+'-name')?.value.trim() || '',
  };
}

const NO_EJECUTA = `<div class="note" style="margin-top:12px">
  ⓘ Registrar esta decisión <b>NO ejecuta sus efectos</b>: no reverifica
  ninguna fuente, no promueve ningún Evidence Pack, no lanza corridas y no
  cambia ningún estado. Ejecutar es un paso posterior y separado.</div>`;

/* ── Panel A — Corrección D1 ───────────────────────────────────────────── */

const PART211 = 'ecfr_21cfr_part211';
const REQ_211_68B = '21_CFR_211.68(b)';

function panelD1Correccion(){
  const c = GOV.coverage?.D1 || {};
  const ids = c.registry_ids || [];
  const originales = ids.filter(i=>i!==PART211);

  return `
  <div class="card">
    <b>Corrección D1 — Fuentes regulatorias</b>
    <div class="meta" style="margin-top:6px">
      La D1 original se firmó con <span class="mono">approved_source_ids: "ALL"</span>,
      un comodín abierto que nunca se materializó. Esta corrección lo sustituye
      por el conjunto explícito que el registry tenía en el momento de aquella firma.
    </div>

    <div style="margin-top:12px"><b>SNAPSHOT EXPLÍCITO</b></div>
    ${originales.map(sid=>`
      <label style="display:block;margin-top:4px">
        <input type="checkbox" class="d1c-src" value="${esc(sid)}" checked
               onchange="govRecalcHash()"> <span class="mono">${esc(sid)}</span>
      </label>`).join('')}
    ${ids.includes(PART211) ? `
      <label style="display:block;margin-top:4px;opacity:.55" title="Se cubre en el panel D1-A">
        <input type="checkbox" disabled> <span class="mono">${esc(PART211)}</span>
      </label>
      <div class="meta" style="margin-left:20px;color:var(--warn)">
        POSTERIOR a la firma de D1: no pertenece a este snapshot. Se cubre en el
        panel D1-A como adendo separado. Mezclar la corrección con la ampliación
        produciría un solo registro que hace dos cosas distintas, y la
        trazabilidad de "qué se corrigió" se perdería.
      </div>` : ''}

    <div class="meta" style="margin-top:10px">
      supersede a: <span class="mono">${esc((c.confirmed_active_instances||[]).slice(-1)[0] || '(ninguna vigente)')}</span>
      <span style="color:var(--faint)"> — la correccion reemplaza a la D1 vigente;
      el original se conserva, el almacen es append-only.</span>
    </div>
    <div class="meta" style="margin-top:6px">
      target_set_hash: <span class="mono" id="d1c-hash">(calculando…)</span>
      <span style="color:var(--faint)"> — cambia al marcar o desmarcar: lo que
      se firma es un conjunto concreto, no una intención.</span>
    </div>

    ${signatureForm('d1c')}
    ${NO_EJECUTA}
    <div style="margin-top:12px">
      <button id="d1c-submit-btn" onclick="govSubmitD1Correccion()">Registrar corrección</button>
      <button onclick="govOpen('')" style="margin-left:6px">Volver al índice</button>
    </div>
    ${statusLine('d1c')}
  </div>`;
}

/* ── Panel B — D1-A ────────────────────────────────────────────────────── */

function panelD1A(){
  const c = GOV.coverage?.D1 || {};
  const cubierto = (c.covered_ids||[]).includes(PART211);
  const correccionHecha = !(c.reconstructed_only_ids||[]).length
                          && (c.covered_ids||[]).length > 0;
  return `
  <div class="card">
    <b>D1-A — Adendo de cobertura</b>
    ${coverageBlock('D1', c)}

    <div style="margin-top:12px"><b>FUENTE A CUBRIR</b></div>
    <div class="mono" style="margin-top:4px">${esc(PART211)}</div>
    <div class="meta">eCFR Title 21 Part 211 — Current Good Manufacturing Practice
      for Finished Pharmaceuticals</div>
    <div class="meta">desviación asociada: <span class="mono">DEV-W5-001</span></div>

    <div style="margin-top:12px"><b>ALCANCE</b> <span class="meta">(decisión previa, no editable)</span></div>
    <div class="meta">Parts en alcance: <b>211</b> · Excluida: <b>210</b> —
      "ámbito y definiciones; ningún requisito del catálogo se apoya en él".</div>
    <div class="meta" style="color:var(--faint)">Part 210 no aparece como opción marcable:
      reabrirlo invitaría a re-decidir lo ya decidido y firmado.</div>

    ${correccionHecha ? '' : `<div class="meta" style="margin-top:10px;color:var(--warn)">
      BLOQUEADO — la Corrección D1 no está registrada. Un adendo sobre un
      snapshot que no existe no tiene a qué añadirse.</div>`}

    ${signatureForm('d1a')}
    ${NO_EJECUTA}
    <div class="meta" style="margin-top:6px;color:var(--faint)">
      Registrar NO reverifica: la fuente pasará a
      <span class="mono">AUTHORIZED_PENDING_REVERIFICATION</span>, nunca a VERIFIED.</div>
    <div style="margin-top:12px">
      <button id="d1a-submit-btn" ${(correccionHecha && !cubierto)?'':'disabled'}
              onclick="govSubmitD1A()">Registrar D1-A</button>
      <button onclick="govOpen('')" style="margin-left:6px">Volver al índice</button>
    </div>
    ${statusLine('d1a')}
  </div>`;
}

/* ── Panel C — Revisión del pack 21 CFR 211.68(b) (D2) ─────────────────── */

/* D2 prohibe ALL_SNAPSHOT a proposito (decision_families.yaml): cada pack se
   aprueba por su contenido concreto, nunca "apruebo todos" -- ver G2' (el
   registro D2_evidence_packs sin ningun objetivo, huerfano de un "apruebo
   todo" anterior). Este panel firma UN solo requirement_id, no una lista
   editable: si mañana hace falta aprobar otro pack, es OTRO panel o una
   generalización deliberada, no un checkbox agregado aquí sin pensar. */
function panelPack211(){
  const c = GOV.coverage?.D2 || {};
  const cubierto = (c.covered_ids||[]).includes(REQ_211_68B);
  return `
  <div class="card">
    <b>Revisión del pack 21 CFR 211.68(b)</b>
    ${coverageBlock('D2', c)}

    <div style="margin-top:12px"><b>REQUISITO A APROBAR</b></div>
    <div class="mono" style="margin-top:4px">${esc(REQ_211_68B)}</div>
    <div class="meta">Controles sobre sistemas computarizados: cambios por personal
      autorizado, verificación de exactitud de entrada/salida y respaldo de datos
      (§ 211.68, paragraph (b)).</div>
    <div class="meta" style="margin-top:6px">Contenido interpretativo redactado por
      Claude Code (G4a, 2026-07-30): <span class="mono">governed_interpretation</span>,
      <span class="mono">evidence_min_criteria</span>,
      <span class="mono">exclusion_criteria</span>,
      <span class="mono">typical_insufficient_evidence</span>,
      <span class="mono">weak_keywords</span>,
      <span class="mono">expected_doc_types</span> — ver
      <span class="mono">factory/regulatory/requirement_catalog/requirements.yaml</span>.
      Firmar aquí es aprobar ESE contenido, no una promesa de que existe.</div>

    ${cubierto ? `<div class="meta" style="margin-top:10px;color:var(--pass)">
      Ya cubierto por una decisión D2 vigente — ver arriba.</div>` : ''}
    ${incidenteRevocable(c) ? panelIncidenteD2003() : `
    ${signatureForm('pk211')}
    ${NO_EJECUTA}
    <div class="meta" style="margin-top:6px;color:var(--faint)">
      Registrar NO versiona el catálogo (G4c, aparte) ni habilita liberación:
      la fuente ecfr_21cfr_part211 sigue PENDING_REVERIFICATION hasta que G3
      la reverifique de nuevo con este contenido.</div>
    <div style="margin-top:12px">
      <button id="pk211-submit-btn" ${cubierto?'disabled':''} onclick="govSubmitPack211()">Registrar aprobación</button>
      <button onclick="govOpen('')" style="margin-left:6px">Volver al índice</button>
    </div>
    ${statusLine('pk211')}`}
  </div>`;
}

/* ── Incidente D2-2026-003 (2026-07-30) ─────────────────────────────────
   Una sonda de diagnostico uso 'claude_probe' como approved_by_id; el match
   EXACTO de RESERVED_IDENTITIES no lo rechazo ('claude_probe' != 'claude') y
   el /confirm quedo human_confirmed/ACTIVE de verdad -- ver
   RECORD_ANNOTATION-2026-005. El hueco de identidad ya esta cerrado
   (identity_policy.RESERVED_PREFIXES), pero la cobertura que otorgo sigue
   activa: el almacen es append-only y una anotacion no revoca nada. Solo una
   REVOCATION firmada por un humano real la retira -- este bloque es ESA
   superficie, acotada a esta unica instancia, no un mecanismo general de
   revocacion (eso, si hace falta de nuevo, es una generalizacion aparte). */
const INCIDENTE_D2_003 = 'D2-2026-003';
// La REVOCATION real que Cesar firmo sobre D2-2026-003 (ver govSubmitPack211:
// la via gobernada para re-aprobar despues de una revocacion es supersederla).
const INCIDENTE_D2_003_REVOCATION = 'D2-2026-005';

function incidenteRevocable(coverage){
  /* DEFECTO REAL (2026-07-30): comprobaba solo que D2-2026-003 estuviera
     confirmada, sin mirar si YA fue revocada -- una vez que Cesar firmo la
     REVOCATION (D2-2026-005), el requisito paso a `revoked_ids` y salio de
     `covered_ids`, pero este panel seguia mostrando el bloque de incidente e
     invitando a revocar otra vez. `confirm` es idempotente y respondio "ya
     estaba firmada", que es correcto -- el bug era que el panel ofrecia la
     accion de nuevo cuando ya no hacia falta. La condicion real es la
     cobertura VIGENTE, no la mera existencia del registro erroneo. */
  return (coverage.covered_ids||[]).includes(REQ_211_68B)
      && (coverage.confirmed_active_instances||[]).includes(INCIDENTE_D2_003);
}

function panelIncidenteD2003(){
  return `
  <div class="meta" style="margin-top:12px;padding:8px;border:1px solid var(--warn);border-radius:4px">
    <b style="color:var(--warn)">INCIDENTE — firma fabricada por el agente (2026-07-30)</b>
    <div class="meta" style="margin-top:6px">
      <span class="mono">${esc(INCIDENTE_D2_003)}</span> quedó
      <span class="mono">human_confirmed</span>/<span class="mono">ACTIVE</span> con
      <span class="mono">approved_by_id: "claude_probe"</span> — una sonda de
      diagnóstico que debía ser rechazada y no lo fue (ver
      <span class="mono">RECORD_ANNOTATION-2026-005</span>). Esta cobertura de
      <span class="mono">${esc(REQ_211_68B)}</span> NO tiene respaldo de una firma
      humana real.</div>
    ${signatureForm('pk211rev', {motivoLabel:'MOTIVO DE LA REVOCACIÓN'})}
    ${NO_EJECUTA}
    <div style="margin-top:12px">
      <button id="pk211rev-submit-btn" onclick="govSubmitRevokeD2003()">Revocar ${esc(INCIDENTE_D2_003)}</button>
      <button onclick="govOpen('')" style="margin-left:6px">Volver al índice</button>
    </div>
    ${statusLine('pk211rev')}
  </div>`;
}

/* ── Panel C-2 — D2-A: aprobación de Evidence Packs (D2, G5) ──────────── */

/* D2A_READY (spec §5.3) se calcula por requisito -- fuente verificada +
   cobertura D1 + pack completo (V1-V10, incluido V5 ya redefinido a
   citation.citation_text) + matriz aprobada + catálogo versionado, las
   cinco a la vez. `GOV.d2a_readiness` ya trae el veredicto Y el contenido
   del pack (evidence_pack_governance.d2a_ready() vía governance_service),
   este panel solo lo pinta -- nunca reimplementa ninguna de las cinco
   reglas.

   Solo "Aprobar" está implementado (decision_type=ADDENDUM sobre D2, mismo
   mecanismo que ya usa el panel del pack 211) -- "devolver con comentario"
   y "rechazar" (spec §5.1) exigirían un registro de PROPUESTA por pack que
   hoy no existe (el contenido vive directo en requirements.yaml, redactado
   en G4a), declarado NOT_IMPLEMENTED_YET explícito, mismo criterio que
   otras piezas fuera de alcance de este spec (ver docstring del módulo
   Python). */

function panelD2A(){
  const c = GOV.coverage?.D2 || {};
  const items = GOV?.d2a_readiness || [];
  const listos = items.filter(i => i.ready);

  const filaChecklist = (i) => `<tr>
    <td class="mono">${esc(i.requirement_id)}</td>
    <td>${i.ready ? '<span style="color:var(--pass)">READY</span>' : '<span class="meta">—</span>'}</td>
    <td class="meta">${esc((i.reasons||[]).join(' · ') || '—')}</td>
  </tr>`;

  const bloqueListo = (i) => {
    const prefix = 'd2a_' + i.requirement_id.replace(/[^a-zA-Z0-9]/g, '_');
    const cubierto = (c.covered_ids||[]).includes(i.requirement_id);
    return `<div class="card" style="margin-top:10px;padding:8px;border:1px solid var(--pass)">
      <b>${esc(i.requirement_id)}</b> — ${esc(i.label||'')}
      <div class="meta" style="margin-top:6px">Fuente: <span class="mono">${esc(i.source_id||'?')}</span></div>
      <div class="meta" style="margin-top:4px">Cita literal (V5, ya anclada): <span class="mono">${esc(i.citation_text||'?')}</span></div>
      <div class="meta" style="margin-top:6px"><b>Interpretación gobernada</b></div>
      <div class="meta">${esc(i.governed_interpretation||'')}</div>
      <div class="meta" style="margin-top:6px"><b>Criterios mínimos</b></div>
      <ul class="meta" style="margin:2px 0 0 18px">${(i.evidence_min_criteria||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>
      <div class="meta" style="margin-top:6px"><b>Criterios de exclusión</b></div>
      <ul class="meta" style="margin:2px 0 0 18px">${(i.exclusion_criteria||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>
      ${cubierto ? `<div class="meta" style="margin-top:8px;color:var(--pass)">
        Ya cubierto por una decisión D2 vigente.</div>` : `
      ${signatureForm('d2a_'+i.requirement_id.replace(/[^a-zA-Z0-9]/g, '_'))}
      ${NO_EJECUTA}
      <div style="margin-top:8px">
        <button id="${prefix}-submit-btn" onclick="govSubmitD2A('${esc(i.requirement_id)}','${esc(prefix)}')">
          Aprobar ${esc(i.requirement_id)}</button>
      </div>
      ${statusLine(prefix)}`}
    </div>`;
  };

  return `
  <div class="card">
    <b>D2-A — Aprobación de Evidence Packs</b>
    ${coverageBlock('D2', c)}
    <div class="meta" style="margin-top:6px;color:var(--faint)">
      D2_A_READY calculado, nunca declarado a mano (spec §5.3): fuente
      verificada + cobertura D1 + pack completo (V1-V10) + matriz aprobada +
      catálogo versionado, las cinco a la vez. Sin "apruebo todos": cada
      pack se firma por su propio contenido.</div>

    <div style="margin-top:12px"><b>CHECKLIST — LOS ${items.length} REQUISITOS DEL CATÁLOGO</b></div>
    <table class="tbl" style="width:100%;font-size:11px;margin-top:6px">
      <thead><tr><th>Requisito</th><th>Estado</th><th>Qué falta</th></tr></thead>
      <tbody>${items.map(filaChecklist).join('')}</tbody>
    </table>

    <div style="margin-top:12px"><b>LISTOS PARA APROBAR (${listos.length})</b></div>
    ${listos.map(bloqueListo).join('') || '<div class="meta" style="margin-top:8px">Ningún requisito D2A_READY hoy.</div>'}

    <div style="margin-top:12px"><button onclick="govOpen('')">Volver al índice</button></div>
  </div>`;
}

/* ── Panel D — Versionado del catálogo (ARTIFACT_VERSION, G4c) ─────────── */

/* Este panel REGISTRA la decisión (propose+confirm), igual que todos los
   demás -- NUNCA bumpea el archivo. El bump real es un paso posterior y
   separado (`factory/core/artifact_version_apply.apply_catalog_version_bump`,
   invocado por un humano/agente bajo su direccion tras esta firma), mismo
   patrón U-5 que el resto de la vista: registrar no ejecuta.

   HALLAZGO REAL (panel ARQ, 2026-08-04): este panel describía el estado con
   texto FIJO en el HTML ("1.0 → 2.0"), congelado desde antes de que ese bump
   se aplicara de verdad (2026-08-01) -- para cuando el catálogo volvió a
   cambiar de hash (2026-08-03, regeneración de Part 11), el texto ya mentía.
   Además, "Registrar autorización" SIEMPRE creaba una propuesta NUEVA con
   payload vacío (`{}`) -- así se produjeron ARTIFACT_VERSION-2026-001/002/003,
   ninguna con la transición declarada. Y el panel no filtraba por artefacto:
   una propuesta de `golden_dataset` (ARTIFACT_VERSION-2026-004) aparecía
   mezclada bajo "Versionado del catálogo".

   Fix: todo se deriva de `GOV.artifacts.catalog_state` (versión/hash VIVOS,
   calculados ahora, nunca texto fijo) y `GOV.proposals.ARTIFACT_VERSION`
   (payload real de cada propuesta). El botón ya NO propone -- CONFIRMA la
   propuesta válida existente (generada por
   `artifact_version_apply.propose_artifact_version_change()`, que calcula
   el payload del estado vivo, nunca lo acepta como parámetro humano). */

function catalogVersionProposals(){
  const props = GOV?.proposals?.ARTIFACT_VERSION || [];
  return props.filter(p => (p.resolved_target_ids||[]).includes(CATALOG_ARTIFACT_ID));
}

function validCatalogVersionProposal(cs){
  if(!cs || !cs.found) return null;
  return catalogVersionProposals().find(p =>
    p.proposal_state === 'PROPOSED' &&
    p.payload && p.payload.artifact_path === CATALOG_ARTIFACT_ID &&
    p.payload.from_version === cs.live_version &&
    p.payload.artifact_hash_before === cs.live_sha256 &&
    p.payload.to_version && p.payload.expected_hash_after
  ) || null;
}

function panelCatalogVersion(){
  const c = GOV.coverage?.ARTIFACT_VERSION || {};
  const art = GOV.artifacts || {};
  const cs = art.catalog_state || {found:false};
  const propuestas = catalogVersionProposals();  // SOLO las de este artefacto -- nunca golden_dataset
  const valida = validCatalogVersionProposal(cs);
  const hashCoincide = cs.found && cs.live_sha256 === cs.last_approved_sha256;

  const filasPropuestas = propuestas.map(p => {
    const t = p.payload && p.payload.to_version
      ? `${esc(p.payload.from_version||'?')} → ${esc(p.payload.to_version)}`
      : '(sin transición declarada -- no aplicable)';
    const esValida = valida && p.decision_instance_id === valida.decision_instance_id;
    return `<div class="meta" style="margin-top:4px">
      <span class="mono">${esc(p.decision_instance_id)}</span>
      [${esc(p.proposal_state)}] ${t}
      ${esValida ? ' <b style="color:var(--pass)">← vigente, firmable</b>' : ''}
    </div>`;
  }).join('') || '<div class="meta" style="margin-top:4px">Ninguna propuesta para este artefacto.</div>';

  return `
  <div class="card">
    <b>Versionado del catálogo — G4c</b>
    ${coverageBlock('ARTIFACT_VERSION', c)}

    <div style="margin-top:12px"><b>ARTEFACTO</b></div>
    <div class="mono" style="margin-top:4px">${esc(CATALOG_ARTIFACT_ID)}</div>

    ${cs.found ? `
    <div class="meta" style="margin-top:6px">Estado VIVO (calculado ahora, no texto fijo):
      versión <span class="mono">${esc(cs.live_version)}</span>,
      hash <span class="mono">${esc((cs.live_sha256||'').slice(0,16))}…</span>.</div>
    <div class="meta" style="margin-top:4px">Última aprobación real:
      <span class="mono">${esc(cs.approved_by_decision||'ninguna')}</span> →
      versión <span class="mono">${esc(cs.last_approved_version||'?')}</span>,
      hash <span class="mono">${esc((cs.last_approved_sha256||'').slice(0,16))}…</span>.
      ${hashCoincide
        ? '<span style="color:var(--pass)">El hash vivo coincide con lo último aprobado.</span>'
        : '<span style="color:var(--warn)">El hash vivo NO coincide con lo último aprobado -- el contenido cambió desde entonces (CONTENT_CHANGED_VERSION_SAME).</span>'}
    </div>` : `<div class="meta" style="margin-top:6px;color:var(--warn)">No se pudo leer el estado vivo de este artefacto.</div>`}

    ${valida ? `
    <div style="margin-top:12px;padding:8px;border:1px solid var(--pass)">
      <b style="color:var(--pass)">PROPUESTA SELECCIONADA PARA FIRMAR</b>
      <div class="meta" style="margin-top:6px">PROPOSAL_ID = <span class="mono">${esc(valida.decision_instance_id)}</span></div>
      <div class="meta">FROM_VERSION = <span class="mono">${esc(valida.payload.from_version)}</span></div>
      <div class="meta">TO_VERSION = <span class="mono">${esc(valida.payload.to_version)}</span></div>
      <div class="meta">ARTIFACT_PATH = <span class="mono">${esc(valida.payload.artifact_path)}</span></div>
      <div class="meta">ARTIFACT_HASH_BEFORE = <span class="mono">${esc(valida.payload.artifact_hash_before)}</span></div>
      <div class="meta">EXPECTED_HASH_AFTER = <span class="mono">${esc(valida.payload.expected_hash_after)}</span></div>
      <div class="meta" style="margin-top:6px">STATE_HASH = <span class="mono">${esc((GOV?.family_state_hashes?.ARTIFACT_VERSION||'').slice(0,16))}…</span></div>
      ${valida.payload.artifact_hash_before === valida.payload.expected_hash_after ? `
      <div class="meta" style="margin-top:6px;color:var(--faint)">
        CASO A (§2 del panel ARQ): <span class="mono">catalog_version</span> está
        excluido del hash canónico del catálogo (<span class="mono">artifact_version_guard.py:83</span>) --
        bumpear SOLO la etiqueta de versión, sin cambio de contenido, produce
        legítimamente <span class="mono">ARTIFACT_HASH_BEFORE == EXPECTED_HASH_AFTER</span>.
        No es un error: es el comportamiento esperado de este tipo de bump.</div>` : ''}
    </div>` : ''}

    <div style="margin-top:12px"><b>PROPUESTAS ARTIFACT_VERSION PARA ESTE ARTEFACTO</b>
      <span class="meta">(filtradas por <span class="mono">artifact_path</span> --
      una propuesta de otro artefacto, p.ej. <span class="mono">golden_dataset</span>,
      nunca aparece aquí)</span></div>
    ${filasPropuestas}

    ${signatureForm('catv')}
    ${NO_EJECUTA}
    <div class="meta" style="margin-top:6px;color:var(--faint)">
      Registrar NO bumpea <span class="mono">catalog_version</span> ni escribe el
      <span class="mono">version_record</span>: eso lo hace
      <span class="mono">artifact_version_apply.apply_catalog_version_bump()</span>,
      un paso separado que exige esta decisión ya confirmada Y que la transición
      declarada coincida exactamente con el estado vivo en el momento de aplicar.</div>
    ${!valida ? `<div class="meta" style="margin-top:6px;color:var(--warn)">
      No hay ninguna propuesta con la transición vigente (atada al hash/versión
      VIVOS de hoy) -- el botón queda deshabilitado. Generar una nueva con
      <span class="mono">artifact_version_apply.propose_artifact_version_change()</span>.</div>` : ''}
    <div style="margin-top:12px">
      <button id="catv-submit-btn" ${valida?'':'disabled'} onclick="govSubmitCatalogVersion()">
        ${valida ? `Confirmar ${esc(valida.decision_instance_id)}` : 'Registrar autorización'}</button>
      <button onclick="govOpen('')" style="margin-left:6px">Volver al índice</button>
    </div>
    ${statusLine('catv')}
  </div>`;
}

/* ── Panel — Matriz de aplicabilidad, regularización ARTIFACT_VERSION ────
   Plan W5V2_ARQ_RETOMAR_Y_FINALIZAR.md Bloque 2: applicability_matrix.yaml
   pasó de 2.1 a 2.2 (commit 84a7a58, V6) sin decisión ARTIFACT_VERSION que
   lo cubra -- FAIL real de artifact_version_guard.check_artifact(), no
   simulado. Mismo mecanismo de echo-back que catalog-version (endpoint
   genérico /governance/artifact-version/{proposals,sign}, ya parametrizado
   por artifact_path -- no hubo que tocar el backend de firma), pero
   PROPUESTO con artifact_version_apply.propose_regularization_for_applied_change()
   en vez de propose_artifact_version_change(): el cambio YA está en disco,
   el 'antes' viene del bootstrap ya registrado (versions.jsonl), no de una
   simulación de un cambio futuro. Aplicar (escribir el version_record) es
   artifact_version_apply.apply_regularization_for_applied_change() -- un
   paso separado y posterior, igual que el catálogo, y NUNCA reescribe el
   YAML (ya está correcto). */

function matrixVersionProposals(){
  const props = GOV?.proposals?.ARTIFACT_VERSION || [];
  return props.filter(p => (p.resolved_target_ids||[]).includes(MATRIX_ARTIFACT_ID));
}

function validMatrixVersionProposal(ms){
  if(!ms || !ms.found) return null;
  return matrixVersionProposals().find(p =>
    p.proposal_state === 'PROPOSED' &&
    p.payload && p.payload.artifact_path === MATRIX_ARTIFACT_ID &&
    p.payload.from_version && p.payload.artifact_hash_before &&
    p.payload.to_version === ms.live_version &&
    p.payload.expected_hash_after === ms.live_sha256
  ) || null;
}

function panelMatrixVersionRegularizacion(){
  const c = GOV.coverage?.ARTIFACT_VERSION || {};
  const art = GOV.artifacts || {};
  const ms = art.matrix_state || {found:false};
  const propuestas = matrixVersionProposals();
  const valida = validMatrixVersionProposal(ms);

  const filasPropuestas = propuestas.map(p => {
    const t = p.payload && p.payload.to_version
      ? `${esc(p.payload.from_version||'?')} → ${esc(p.payload.to_version)}`
      : '(sin transición declarada -- no aplicable)';
    const esValida = valida && p.decision_instance_id === valida.decision_instance_id;
    return `<div class="meta" style="margin-top:4px">
      <span class="mono">${esc(p.decision_instance_id)}</span>
      [${esc(p.proposal_state)}] ${t}
      ${esValida ? ' <b style="color:var(--pass)">← vigente, firmable</b>' : ''}
    </div>`;
  }).join('') || '<div class="meta" style="margin-top:4px">Ninguna propuesta para este artefacto.</div>';

  return `
  <div class="card">
    <b>Matriz de aplicabilidad — regularización de versión (G6)</b>
    ${coverageBlock('ARTIFACT_VERSION', c)}

    <div style="margin-top:12px"><b>ARTEFACTO</b></div>
    <div class="mono" style="margin-top:4px">${esc(MATRIX_ARTIFACT_ID)}</div>

    ${ms.found ? `
    <div class="meta" style="margin-top:6px">Estado VIVO (calculado ahora, no texto fijo):
      versión <span class="mono">${esc(ms.live_version)}</span>,
      hash <span class="mono">${esc((ms.live_sha256||'').slice(0,16))}…</span>.</div>
    <div class="meta" style="margin-top:4px;color:var(--faint)">
      El contenido de 2.2 ya está en disco (V6, expected_doc_types) y ya fue
      revisado por vos bajo la familia <span class="mono">APPLICABILITY_MATRIX</span>
      (<span class="mono">APPLICABILITY_MATRIX-2026-006</span>). Esta firma es
      DISTINTA: cubre la invariante hash⟺versión⟺decisión de
      <span class="mono">ARTIFACT_VERSION</span> (la misma que ya protege al
      catálogo), no vuelve a aprobar el contenido.</div>` : `<div class="meta" style="margin-top:6px;color:var(--warn)">No se pudo leer el estado vivo de este artefacto.</div>`}

    ${valida ? `
    <div style="margin-top:12px;padding:8px;border:1px solid var(--pass)">
      <b style="color:var(--pass)">PROPUESTA SELECCIONADA PARA FIRMAR</b>
      <div class="meta" style="margin-top:6px">PROPOSAL_ID = <span class="mono">${esc(valida.decision_instance_id)}</span></div>
      <div class="meta">FROM_VERSION = <span class="mono">${esc(valida.payload.from_version)}</span></div>
      <div class="meta">TO_VERSION = <span class="mono">${esc(valida.payload.to_version)}</span></div>
      <div class="meta">ARTIFACT_PATH = <span class="mono">${esc(valida.payload.artifact_path)}</span></div>
      <div class="meta">ARTIFACT_HASH_BEFORE = <span class="mono">${esc(valida.payload.artifact_hash_before)}</span></div>
      <div class="meta">EXPECTED_HASH_AFTER = <span class="mono">${esc(valida.payload.expected_hash_after)}</span></div>
      <div class="meta">CHANGE_REASON = <span class="mono">${esc(valida.payload.change_reason)}</span></div>
      <div class="meta" style="margin-top:6px">STATE_HASH = <span class="mono">${esc((GOV?.family_state_hashes?.ARTIFACT_VERSION||'').slice(0,16))}…</span></div>
    </div>` : ''}

    <div style="margin-top:12px"><b>PROPUESTAS ARTIFACT_VERSION PARA ESTE ARTEFACTO</b>
      <span class="meta">(filtradas por <span class="mono">artifact_path</span> --
      una propuesta del catálogo o del golden dataset nunca aparece aquí)</span></div>
    ${filasPropuestas}

    ${signatureForm('mxv')}
    ${NO_EJECUTA}
    <div class="meta" style="margin-top:6px;color:var(--faint)">
      Registrar NO escribe el <span class="mono">version_record</span>: eso lo hace
      <span class="mono">artifact_version_apply.apply_regularization_for_applied_change()</span>,
      un paso separado que exige esta decisión ya confirmada. El archivo
      <span class="mono">applicability_matrix.yaml</span> nunca se reescribe --
      ya está en el estado que esta decisión aprueba.</div>
    ${!valida ? `<div class="meta" style="margin-top:6px;color:var(--warn)">
      No hay ninguna propuesta con la transición vigente (atada al hash/versión
      VIVOS de hoy) -- el botón queda deshabilitado.</div>` : ''}
    <div style="margin-top:12px">
      <button id="mxv-submit-btn" ${valida?'':'disabled'} onclick="govSubmitMatrixVersionRegularizacion()">
        ${valida ? `Confirmar ${esc(valida.decision_instance_id)}` : 'Registrar autorización'}</button>
      <button onclick="govOpen('')" style="margin-left:6px">Volver al índice</button>
    </div>
    ${statusLine('mxv')}
  </div>`;
}

/* ── Panel — Prompts gobernados, regularización de versión (R2.1 Causa 2) ── */

function promptVersionProposals(artifactId){
  const props = GOV?.proposals?.ARTIFACT_VERSION || [];
  return props.filter(p => (p.resolved_target_ids||[]).includes(artifactId));
}

function validPromptVersionProposal(artifactId, ps){
  if(!ps || !ps.found) return null;
  return promptVersionProposals(artifactId).find(p =>
    p.proposal_state === 'PROPOSED' &&
    p.payload && p.payload.artifact_path === artifactId &&
    p.payload.from_version && p.payload.artifact_hash_before &&
    p.payload.to_version === ps.live_version &&
    p.payload.expected_hash_after === ps.live_sha256
  ) || null;
}

function panelPromptVersionRegularizacion(){
  const c = GOV.coverage?.ARTIFACT_VERSION || {};
  const promptStates = GOV.artifacts?.prompt_states || {};

  const secciones = PROMPT_ARTIFACT_IDS.map(artifactId => {
    const prefix = PROMPT_STATUS_PREFIX[artifactId];
    const ps = promptStates[artifactId] || {found:false};
    const propuestas = promptVersionProposals(artifactId);
    const valida = validPromptVersionProposal(artifactId, ps);

    const filasPropuestas = propuestas.map(p => {
      const t = p.payload && p.payload.to_version
        ? `${esc(p.payload.from_version||'?')} → ${esc(p.payload.to_version)}`
        : '(sin transición declarada -- no aplicable)';
      const esValida = valida && p.decision_instance_id === valida.decision_instance_id;
      return `<div class="meta" style="margin-top:4px">
        <span class="mono">${esc(p.decision_instance_id)}</span>
        [${esc(p.proposal_state)}] ${t}
        ${esValida ? ' <b style="color:var(--pass)">← vigente, firmable</b>' : ''}
      </div>`;
    }).join('') || '<div class="meta" style="margin-top:4px">Ninguna propuesta para este artefacto.</div>';

    return `
    <div class="card" style="margin-top:10px">
      <b class="mono">${esc(artifactId)}</b>
      ${ps.found ? `
      <div class="meta" style="margin-top:6px">Estado VIVO: versión
        <span class="mono">${esc(ps.live_version)}</span>, hash
        <span class="mono">${esc((ps.live_sha256||'').slice(0,16))}…</span>.</div>` : `
      <div class="meta" style="margin-top:6px;color:var(--warn)">No se pudo leer el estado vivo de este artefacto.</div>`}

      ${valida ? `
      <div style="margin-top:10px;padding:8px;border:1px solid var(--pass)">
        <b style="color:var(--pass)">PROPUESTA SELECCIONADA PARA FIRMAR</b>
        <div class="meta" style="margin-top:6px">PROPOSAL_ID = <span class="mono">${esc(valida.decision_instance_id)}</span></div>
        <div class="meta">FROM_VERSION = <span class="mono">${esc(valida.payload.from_version)}</span></div>
        <div class="meta">TO_VERSION = <span class="mono">${esc(valida.payload.to_version)}</span></div>
        <div class="meta">ARTIFACT_HASH_BEFORE = <span class="mono">${esc(valida.payload.artifact_hash_before)}</span></div>
        <div class="meta">EXPECTED_HASH_AFTER = <span class="mono">${esc(valida.payload.expected_hash_after)}</span></div>
        <div class="meta">CHANGE_REASON = <span class="mono">${esc(valida.payload.change_reason)}</span></div>
      </div>` : ''}

      <div style="margin-top:10px"><b>PROPUESTAS PARA ESTE ARTEFACTO</b></div>
      ${filasPropuestas}

      ${signatureForm(prefix)}
      ${!valida ? `<div class="meta" style="margin-top:6px;color:var(--warn)">
        No hay ninguna propuesta con la transición vigente (atada al hash/versión
        VIVOS de hoy) -- el botón queda deshabilitado.</div>` : ''}
      <div style="margin-top:10px">
        <button id="${prefix}-submit-btn" ${valida?'':'disabled'}
          onclick="govSubmitPromptVersionRegularizacion('${esc(artifactId)}')">
          ${valida ? `Confirmar ${esc(valida.decision_instance_id)}` : 'Registrar autorización'}</button>
      </div>
      ${statusLine(prefix)}
    </div>`;
  }).join('');

  return `
  <div class="card">
    <b>Prompts gobernados — regularización de versión (R2.1 Causa 2)</b>
    ${coverageBlock('ARTIFACT_VERSION', c)}
    <div class="meta" style="margin-top:6px">
      El bump 1.1.0→1.1.1 de los 3 prompts ya está en disco (commit
      <span class="mono">d42d919</span>, contenido ya aprobado por Cesar al
      aprobar ese commit) -- esta firma cubre la invariante
      hash⟺versión⟺decisión de <span class="mono">ARTIFACT_VERSION</span>
      (la misma que ya protege al catálogo y a la matriz), no vuelve a
      aprobar el contenido del prompt. Registrar NO reescribe ningún YAML:
      eso lo hace <span class="mono">artifact_version_apply.apply_regularization_for_applied_change()</span>,
      un paso separado que exige esta decisión ya confirmada.</div>
    ${NO_EJECUTA}
    ${secciones}
    <div style="margin-top:12px"><button onclick="govOpen('')">Volver al índice</button></div>
  </div>`;
}

export async function govSubmitPromptVersionRegularizacion(artifactId){
  const ps = GOV?.artifacts?.prompt_states?.[artifactId];
  const valida = validPromptVersionProposal(artifactId, ps);
  const prefix = PROMPT_STATUS_PREFIX[artifactId];
  if(!valida){
    setStatus(prefix, 'warn', 'No hay ninguna propuesta ARTIFACT_VERSION con la '
      + 'transición vigente (atada al hash/versión vivos) para este artefacto.');
    return;
  }
  const sig = readSignature(prefix);
  if(!sig.reason){ setStatus(prefix,'warn','El motivo es obligatorio.'); return; }
  if(GOV_STALE){
    setStatus(prefix,'warn','El estado cambió desde que cargaste esta página. '
      + 'Pulsa "Recargar estado" arriba antes de firmar.');
    return;
  }
  setBusy(prefix+'-submit-btn', true);
  setStatus(prefix,'busy','Firmando (echo-back)…');
  try {
    const r = await postJSON('/api/v1/layer9/governance/artifact-version/sign', {
      proposal_id: valida.decision_instance_id,
      artifact_path: valida.payload.artifact_path,
      from_version: valida.payload.from_version,
      to_version: valida.payload.to_version,
      artifact_hash_before: valida.payload.artifact_hash_before,
      expected_hash_after: valida.payload.expected_hash_after,
      state_hash: GOV?.family_state_hashes?.ARTIFACT_VERSION,
      reason: sig.reason,
      approved_by_display_name: sig.name || sig.id,
    });
    if(!r.ok){ setStatus(prefix,'fail', explicaError(r.status, r.data)); return; }
    setStatus(prefix,'ok', explicaFirma(r.data));
    govRefresh();
  } catch(e) {
    setStatus(prefix,'fail', 'Error de red/JS al firmar: ' + (e && e.message || e));
  } finally {
    setBusy(prefix+'-submit-btn', false);
  }
}

/* ── Panel D-2 — Matriz de aplicabilidad (APPLICABILITY_MATRIX, G6) ────── */

/* RC-7 (panel ARQ, 2026-08-05): esta familia nunca tuvo panel -- ni siquiera
   estaba en GOVERNED_FAMILIES del backend, así que GOV.proposals/coverage/
   family_state_hashes de APPLICABILITY_MATRIX no existían para ningún
   cliente. A diferencia de catalog-version, el payload de estas propuestas es
   SIEMPRE `{}` (no declaran una transición estructurada de 6 campos, son una
   aprobación de primer grado sobre un `target_id` fijo, la versión de la
   matriz) -- por eso el botón CONFIRMA directamente el `decision_instance_id`
   mostrado, sin echo-back, con el endpoint genérico de confirmación (el mismo
   que ya usan D1/D1-A/excepción). */

function applicabilityMatrixProposals(){
  return GOV?.proposals?.APPLICABILITY_MATRIX || [];
}

function validApplicabilityMatrixProposal(ms){
  if(!ms || !ms.found) return null;
  return applicabilityMatrixProposals().find(p =>
    p.proposal_state === 'PROPOSED' &&
    (p.resolved_target_ids||[]).includes(ms.live_version)
  ) || null;
}

function panelApplicabilityMatrix(){
  const ms = GOV.artifacts?.matrix_state || {found:false};
  const propuestas = applicabilityMatrixProposals();
  const valida = validApplicabilityMatrixProposal(ms);

  return `
  <div class="card">
    <b>Matriz de aplicabilidad — versión vigente (G6)</b>

    ${ms.found ? `
    <div class="meta" style="margin-top:6px">Estado VIVO (calculado ahora, no texto fijo):
      versión <span class="mono">${esc(ms.live_version)}</span>,
      hash <span class="mono">${esc((ms.live_sha256||'').slice(0,16))}…</span>.</div>
    <div class="meta" style="margin-top:4px">Última aprobación real:
      <span class="mono">${esc(ms.approved_by_decision||'ninguna')}</span> →
      versión <span class="mono">${esc(ms.last_approved_version||'?')}</span>.</div>
    ` : `<div class="meta" style="margin-top:6px;color:var(--warn)">No se pudo leer el estado vivo de este artefacto.</div>`}

    <div style="margin-top:12px"><b>PROPUESTAS APPLICABILITY_MATRIX</b>
      <span class="meta">(target = versión de la matriz, no un artifact_path)</span></div>
    ${propuestas.map(p => `<div class="meta" style="margin-top:4px">
      <span class="mono">${esc(p.decision_instance_id)}</span>
      [${esc(p.proposal_state)}] target: <span class="mono">${esc((p.resolved_target_ids||[]).join(', '))}</span>
      ${valida && p.decision_instance_id===valida.decision_instance_id ? ' <b style="color:var(--pass)">← vigente, firmable</b>' : ''}
    </div>`).join('') || '<div class="meta" style="margin-top:4px">Ninguna propuesta registrada.</div>'}

    ${signatureForm('matx')}
    ${NO_EJECUTA}
    <div style="margin-top:12px">
      <button id="matx-submit-btn" ${valida?'':'disabled'} onclick="govSubmitApplicabilityMatrix()">
        ${valida ? `Confirmar ${esc(valida.decision_instance_id)}` : 'Confirmar'}</button>
      <button onclick="govOpen('')" style="margin-left:6px">Volver al índice</button>
    </div>
    ${!valida ? `<div class="meta" style="margin-top:6px;color:var(--warn)">
      No hay ninguna propuesta PROPOSED atada a la versión vigente
      (<span class="mono">${esc(ms.live_version||'?')}</span>) -- el botón queda deshabilitado.</div>` : ''}
    ${statusLine('matx')}
  </div>`;
}

/* ── Panel D-3 — Golden Dataset, primera aprobación (ARTIFACT_VERSION, G6) ── */

/* Misma familia que catalog-version pero OTRO artefacto -- filtrado por
   artifact_path, igual disciplina que evitó mezclar golden_dataset bajo
   "Versionado del catálogo" el 2026-08-04. Payload también `{}`: es una
   aprobación de primer grado, no una transición declarada, así que tampoco
   hace falta echo-back. */

function goldenDatasetProposals(){
  const props = GOV?.proposals?.ARTIFACT_VERSION || [];
  return props.filter(p => (p.resolved_target_ids||[]).includes(GOLDEN_DATASET_ARTIFACT_ID));
}

function validGoldenDatasetProposal(){
  return goldenDatasetProposals().find(p => p.proposal_state === 'PROPOSED') || null;
}

function panelGoldenDataset(){
  const propuestas = goldenDatasetProposals();
  const valida = validGoldenDatasetProposal();

  return `
  <div class="card">
    <b>Golden Dataset — primera aprobación (G6)</b>
    <div class="meta" style="margin-top:6px">
      Artefacto <span class="mono">${esc(GOLDEN_DATASET_ARTIFACT_ID)}</span> está
      bootstrapeado (foto del estado observado, <span class="mono">approved_by_decision: null</span>)
      -- ninguna decisión humana lo respalda todavía. Confirmar esta propuesta NO
      cambia el contenido ni la versión del dataset: solo otorga la primera
      cobertura formal, una de las 5 precondiciones antes de que la
      recalificación del modelo sea ejecutable.</div>

    <div style="margin-top:12px"><b>PROPUESTAS ARTIFACT_VERSION PARA ESTE ARTEFACTO</b>
      <span class="meta">(filtradas por artifact_path -- una propuesta del catálogo
      nunca aparece aquí)</span></div>
    ${propuestas.map(p => `<div class="meta" style="margin-top:4px">
      <span class="mono">${esc(p.decision_instance_id)}</span> [${esc(p.proposal_state)}]
      ${valida && p.decision_instance_id===valida.decision_instance_id ? ' <b style="color:var(--pass)">← vigente, firmable</b>' : ''}
    </div>`).join('') || '<div class="meta" style="margin-top:4px">Ninguna propuesta registrada.</div>'}

    ${signatureForm('gdset')}
    ${NO_EJECUTA}
    <div style="margin-top:12px">
      <button id="gdset-submit-btn" ${valida?'':'disabled'} onclick="govSubmitGoldenDataset()">
        ${valida ? `Confirmar ${esc(valida.decision_instance_id)}` : 'Confirmar'}</button>
      <button onclick="govOpen('')" style="margin-left:6px">Volver al índice</button>
    </div>
    ${!valida ? `<div class="meta" style="margin-top:6px;color:var(--warn)">
      No hay ninguna propuesta PROPOSED para este artefacto -- el botón queda deshabilitado.</div>` : ''}
    ${statusLine('gdset')}
  </div>`;
}

/* ── Panel E — Excepción de auditoría ──────────────────────────────────── */

/* Las cinco medidas preventivas de AUDIT_FORK_REMEDIATION_SPEC §7. `Aceptar`
   permanece deshabilitado hasta que las cinco estén: aceptar una excepción cuya
   prevención no está implementada es aceptar que vuelva a pasar.

   El estado lo DERIVA el backend (`audit_writer.preventive_measures()`). Antes
   vivía aquí como cinco literales `ok:false` para ir flipándolos a mano, y eso
   convertía el candado del botón en una declaración de intenciones: un `true`
   escrito a mano habilita una firma regulatoria sobre una prevención que puede
   no existir. Si el backend no manda la lista, se asume que NO están: degradar
   hacia "faltan todas" mantiene el botón cerrado. */
function medidas(){
  const ms = GOV?.preventive_measures;
  if(!Array.isArray(ms) || !ms.length){
    return [{ ok:false, txt:'estado de las medidas preventivas no disponible',
              ev:'el backend no lo reportó — se asume que faltan' }];
  }
  return ms.map(m=>({ ok:!!m.implemented, txt:m.measure||m.id||'',
                      ev:`${m.evidence_kind||''}: ${m.evidence||''}` }));
}

/* ── Panel D-4 — Vigencia regulatoria de fuentes (SOURCE_CURRENCY, G3) ─── */

/* A diferencia de matriz/golden-dataset (un solo target), aqui hay hasta 4
   fuentes independientes con su propia evidencia y su propia decision --
   cada bloque es un mini-formulario con su propio prefijo de ids, firmable
   por separado. `regulatory_judgment_note` del payload es la nota TECNICA
   que quien propuso (agente) escribio -- describe lo que el checker
   verifico, nunca afirma vigencia. El MOTIVO que se pide aqui en la firma
   es el juicio humano real: "reviso esto y sigo considerando que la norma
   esta vigente", o lo que corresponda. */

function sourceCurrencyProposals(){
  return (GOV?.proposals?.SOURCE_CURRENCY || [])
    .filter(p => p.proposal_state === 'PROPOSED');
}

/* Hallazgo real (2026-08-05): con las 4 fuentes ya firmadas, el panel
   solo mostraba "Ninguna propuesta pendiente de firma" -- verdad, pero
   indistinguible de un panel roto o desactualizado para quien llega
   despues de firmar todo. `firmadas()` recupera el historial (mismo
   GOV.proposals.SOURCE_CURRENCY, filtrado por CONFIRMED) para que
   "ya se hizo, aqui esta la prueba" sea tan visible como "falta firmar". */
function sourceCurrencyFirmadas(){
  return (GOV?.proposals?.SOURCE_CURRENCY || [])
    .filter(p => p.proposal_state === 'CONFIRMED')
    .sort((a, b) => (a.signed_at||'').localeCompare(b.signed_at||''));
}

function panelSourceCurrency(){
  const propuestas = sourceCurrencyProposals();
  const firmadas = sourceCurrencyFirmadas();

  const bloques = propuestas.map(p => {
    const sid = (p.resolved_target_ids || [])[0] || '?';
    const prefix = 'sc_' + sid.replace(/[^a-zA-Z0-9]/g, '_');
    const pl = p.payload || {};
    return `<div class="card" style="margin-top:10px;padding:8px;border:1px solid var(--warn)">
      <b>${esc(sid)}</b>
      <div class="meta" style="margin-top:6px">PROPOSAL_ID = <span class="mono">${esc(p.decision_instance_id)}</span></div>
      <div class="meta">Verificación revisada: <span class="mono">${esc(pl.reviewed_log_checked_at||'?')}</span></div>
      <div class="meta">SHA256 observado: <span class="mono">${esc((pl.reviewed_downloaded_sha256||'').slice(0,16))}…</span></div>
      <div class="meta" style="margin-top:6px;color:var(--faint)">${esc(pl.regulatory_judgment_note||'')}</div>
      ${signatureForm(prefix, {motivoLabel:'JUICIO DE VIGENCIA (tuyo, no del checker)'})}
      <div style="margin-top:8px">
        <button id="${prefix}-submit-btn"
          onclick="govSubmitSourceCurrency('${esc(p.decision_instance_id)}','${esc(prefix)}')">
          Confirmar vigencia de ${esc(sid)}</button>
      </div>
      ${statusLine(prefix)}
    </div>`;
  }).join('') || `<div class="meta" style="margin-top:8px;color:var(--pass)">
    Ninguna propuesta pendiente de firma -- las fuentes de abajo ya están confirmadas.</div>`;

  const historial = firmadas.length ? `
    <div style="margin-top:16px"><b>YA FIRMADAS (${firmadas.length})</b></div>
    <table class="tbl" style="width:100%;font-size:11px;margin-top:6px">
      <thead><tr><th>Fuente</th><th>Propuesta</th><th>Firmado por</th><th>Cuándo</th></tr></thead>
      <tbody>${firmadas.map(p => `<tr>
        <td class="mono">${esc((p.resolved_target_ids||[])[0] || '?')}</td>
        <td class="mono">${esc(p.decision_instance_id)}</td>
        <td>${esc(p.signed_by_display_name || p.signed_by_id || '?')}</td>
        <td class="mono">${esc((p.signed_at||'').slice(0,16).replace('T',' '))}</td>
      </tr>`).join('')}</tbody>
    </table>` : '';

  return `
  <div class="card">
    <b>Vigencia regulatoria de fuentes — G3</b>
    <div class="meta" style="margin-top:6px">
      Cada bloque es una fuente distinta con su propia evidencia real
      (<span class="mono">source_currency_log.jsonl</span>). Que el hash
      coincida solo prueba que la URL sigue sirviendo lo mismo que se
      archivó -- <b>no</b> prueba que la norma siga vigente hoy. Ese juicio
      es tuyo, y se declara en el motivo de cada firma, no en la nota
      técnica que ya trae la propuesta.</div>
    ${NO_EJECUTA}
    ${bloques}
    ${historial}
  </div>`;
}

/* ── Panel — Segunda observación de origen (SOURCE_ORIGIN_VERIFICATION, G3,
   DEC-B) ── plan W5V2_ARQ_RETOMAR_Y_FINALIZAR.md Bloque 1. Mismo par de
   helpers (proposals/firmadas) y misma estructura de panel que
   source-currency -- diferencia real: sin campo de juicio humano libre
   (el hash coincidente ya prueba procedencia por si mismo), y el resumen
   deja explícito el ANTES/DESPUÉS del official_origin_status. */

function sourceOriginVerificationProposals(){
  return (GOV?.proposals?.SOURCE_ORIGIN_VERIFICATION || [])
    .filter(p => p.proposal_state === 'PROPOSED');
}

function sourceOriginVerificationFirmadas(){
  return (GOV?.proposals?.SOURCE_ORIGIN_VERIFICATION || [])
    .filter(p => p.proposal_state === 'CONFIRMED')
    .sort((a, b) => (a.signed_at||'').localeCompare(b.signed_at||''));
}

function panelSourceOriginVerification(){
  const propuestas = sourceOriginVerificationProposals();
  const firmadas = sourceOriginVerificationFirmadas();

  const bloques = propuestas.map(p => {
    const sid = (p.resolved_target_ids || [])[0] || '?';
    const prefix = 'sov_' + sid.replace(/[^a-zA-Z0-9]/g, '_');
    const pl = p.payload || {};
    return `<div class="card" style="margin-top:10px;padding:8px;border:1px solid var(--warn)">
      <b>${esc(sid)}</b>
      <div class="meta" style="margin-top:6px">PROPOSAL_ID = <span class="mono">${esc(p.decision_instance_id)}</span></div>
      <div class="meta">Verificación revisada: <span class="mono">${esc(pl.reviewed_log_checked_at||'?')}</span></div>
      <div class="meta">SHA256 observado: <span class="mono">${esc((pl.reviewed_downloaded_sha256||'').slice(0,16))}…</span></div>
      <div class="meta" style="margin-top:6px">ANTES: <span class="mono">${esc(pl.prior_official_origin_status||'?')}</span></div>
      <div class="meta">DESPUÉS: <span class="mono">VERIFIED_AGAINST_PRIOR_KNOWN_HASH_&lt;fecha&gt;_REVERIFICATION</span>
        <span class="meta" style="color:var(--faint)"> (fecha real del día en que se aplique)</span></div>
      ${signatureForm(prefix, {motivoLabel:'MOTIVO DE LA FIRMA'})}
      <div style="margin-top:8px">
        <button id="${prefix}-submit-btn"
          onclick="govSubmitSourceOriginVerification('${esc(p.decision_instance_id)}','${esc(prefix)}')">
          Confirmar segunda observación de ${esc(sid)}</button>
      </div>
      ${statusLine(prefix)}
    </div>`;
  }).join('') || `<div class="meta" style="margin-top:8px;color:var(--pass)">
    Ninguna propuesta pendiente de firma -- las fuentes de abajo ya están confirmadas,
    o todavía no hay una segunda observación real que proponer.</div>`;

  const historial = firmadas.length ? `
    <div style="margin-top:16px"><b>YA FIRMADAS (${firmadas.length})</b></div>
    <table class="tbl" style="width:100%;font-size:11px;margin-top:6px">
      <thead><tr><th>Fuente</th><th>Propuesta</th><th>Firmado por</th><th>Cuándo</th></tr></thead>
      <tbody>${firmadas.map(p => `<tr>
        <td class="mono">${esc((p.resolved_target_ids||[])[0] || '?')}</td>
        <td class="mono">${esc(p.decision_instance_id)}</td>
        <td>${esc(p.signed_by_display_name || p.signed_by_id || '?')}</td>
        <td class="mono">${esc((p.signed_at||'').slice(0,16).replace('T',' '))}</td>
      </tr>`).join('')}</tbody>
    </table>` : '';

  return `
  <div class="card">
    <b>Segunda observación de origen — G3, DEC-B</b>
    <div class="meta" style="margin-top:6px">
      <span class="mono">source_lifecycle.py</span> deja una fuente en ámbar
      (<span class="mono">FIRST_INGESTION_NO_PRIOR_KNOWN_HASH</span>) hasta que
      exista una segunda comparación real en el tiempo contra el mismo origen
      oficial. Cada bloque es una fuente con evidencia real ya recolectada
      (<span class="mono">source_currency_log.jsonl</span>, generada por
      <span class="mono">reverify_governed_sources.py</span>) esperando que
      confirmes que esa segunda observación es la que autoriza promover el
      estado -- distinto de "vigencia regulatoria" (panel de arriba): aquí
      no se declara si la norma sigue aplicando, solo que el archivo
      gobernado coincide con una segunda descarga real del mismo origen.</div>
    ${NO_EJECUTA}
    ${bloques}
    ${historial}
  </div>`;
}

/* ── Panel — D4-A, presupuesto de corrida (G8) ──────────────────────────
   Plan W5V2_ARQ_RETOMAR_Y_FINALIZAR.md Bloque 3.3. Defecto historico que
   este panel cierra: D4_corpus_execution (2026-07-29) se firmo APPROVE
   SIN resolved_target_ids -- "un si sin objeto" (spec
   MODEL_REQUALIFICATION_AND_D4A_SPEC.md §5.1). La propuesta real
   (D4-2026-002) SI declara document_ids explicitos -- el panel los
   muestra para que quede claro que corridas autoriza esta firma. */

function d4aProposals(){
  return (GOV?.proposals?.D4 || []).filter(p => p.proposal_state === 'PROPOSED');
}

function panelD4A(){
  const propuestas = d4aProposals();

  const bloque = (p) => {
    const pl = p.payload || {};
    const prefix = 'd4a_' + p.decision_instance_id.replace(/[^a-zA-Z0-9]/g, '_');
    const desglose = (pl.breakdown_summary || []).map(b => `<tr>
      <td class="mono">${esc(b.document_id)}</td>
      <td class="mono">${esc(b.document_type)}</td>
      <td class="mono">${esc(b.agent_id)}</td>
      <td class="mono">${esc(b.calls)}</td>
      <td class="mono">${esc(b.estimated_minutes)}</td>
    </tr>`).join('');
    return `<div class="card" style="margin-top:10px;padding:8px;border:1px solid var(--warn)">
      <b>${esc(p.decision_instance_id)}</b>
      <div class="meta" style="margin-top:6px">DOCUMENTOS QUE AUTORIZA (${(pl.document_ids||[]).length}):
        <span class="mono">${esc((pl.document_ids||[]).join(', '))}</span></div>

      <div style="margin-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:6px 16px">
        <div class="meta">MAX_CALLS: <span class="mono">${esc(pl.max_calls)}</span></div>
        <div class="meta">HARD_STOP_CALLS: <span class="mono">${esc(pl.hard_stop_calls)}</span></div>
        <div class="meta">RUNTIME (min/likely/max, h): <span class="mono">${esc(pl.estimated_runtime_min_hours)} / ${esc(pl.estimated_runtime_likely_hours)} / ${esc(pl.estimated_runtime_max_hours)}</span></div>
        <div class="meta">HARD_STOP_WALL_TIME (h): <span class="mono">${esc(pl.hard_stop_wall_time_hours)}</span></div>
        <div class="meta">CHECKPOINT_MODE: <span class="mono">${esc(pl.checkpoint_mode)}</span></div>
        <div class="meta">RESUME_FINGERPRINT_REQUIRED: <span class="mono">${esc(pl.resume_fingerprint_required)}</span></div>
      </div>

      ${pl.runtime_dispersion_measured === false ? `<div class="meta" style="margin-top:8px;color:var(--warn)">
        Min/likely/max quedan iguales a propósito: <span class="mono">min_per_1k_tokens=${esc(pl.min_per_1k_tokens_used)}</span>
        viene de UNA sola corrida real (eu_annex11 sobre RW-0005) -- no hay p50/p95
        medidos todavía para simular una dispersión real. Sustituir cuando la
        recalificación (G6 §4) mida latencias reales.</div>` : ''}

      <div class="meta" style="margin-top:10px">${esc(p.reason||'')}</div>

      <div style="margin-top:10px"><b>DESGLOSE POR DOCUMENTO/AGENTE (${(pl.breakdown_summary||[]).length})</b></div>
      <table class="tbl" style="width:100%;font-size:11px;margin-top:6px">
        <thead><tr><th>Documento</th><th>Tipo</th><th>Agente</th><th>Llamadas</th><th>Minutos est.</th></tr></thead>
        <tbody>${desglose}</tbody>
      </table>

      ${signatureForm(prefix)}
      ${NO_EJECUTA}
      <div class="meta" style="margin-top:6px;color:var(--faint)">
        Firmar D4-A autoriza el PRESUPUESTO, no lanza ninguna corrida --
        la autorización de corpus (decisión separada, con fingerprint) es
        un paso posterior distinto, ver plan Bloque 6.</div>
      <div style="margin-top:8px">
        <button id="${prefix}-submit-btn" onclick="govSubmitD4A('${esc(p.decision_instance_id)}','${esc(prefix)}')">
          Confirmar ${esc(p.decision_instance_id)}</button>
      </div>
      ${statusLine(prefix)}
    </div>`;
  };

  return `
  <div class="card">
    <b>D4-A — Presupuesto de corrida (G8)</b>
    <div class="meta" style="margin-top:6px">
      Límites duros derivados de R(d,a) real (cobertura D2 + fuentes VERIFIED
      de hoy), nunca escritos a mano. Calculado sobre el catálogo de HOY --
      distinto de la tabla calibratoria histórica del spec (esa describe un
      catálogo con Part 11 en 4 checkpoints y <span class="mono">21_CFR_211.68(b)</span>
      en 0 criterios).</div>
    ${propuestas.map(bloque).join('') || '<div class="meta" style="margin-top:8px;color:var(--pass)">Ninguna propuesta D4 pendiente de firma.</div>'}
    <div style="margin-top:12px"><button onclick="govOpen('')">Volver al índice</button></div>
  </div>`;
}

/* ── Panel — Autorización de corpus (CORPUS_AUTHORIZATION, G8, plan
   Bloque 6) ── go/no-go atado al run_fingerprint exacto. Mismo patrón que
   d4a: propuesta real ya creada por Capa 8, este panel solo confirma. */

function corpusAuthorizationProposals(){
  return (GOV?.proposals?.CORPUS_AUTHORIZATION || []).filter(p => p.proposal_state === 'PROPOSED');
}

function panelCorpusAuthorization(){
  const propuestas = corpusAuthorizationProposals();

  const bloque = (p) => {
    const pl = p.payload || {};
    const fp = pl.run_fingerprint || {};
    const prefix = 'cauth_' + p.decision_instance_id.replace(/[^a-zA-Z0-9]/g, '_');
    return `<div class="card" style="margin-top:10px;padding:8px;border:1px solid var(--warn)">
      <b>${esc(p.decision_instance_id)}</b>
      <div class="meta" style="margin-top:6px">DOCUMENTOS: <span class="mono">${esc((pl.document_ids||[]).join(', '))}</span></div>
      <div class="meta">PRESUPUESTO (D4): <span class="mono">${esc(pl.d4_decision_instance_id)}</span></div>

      <div class="meta" style="margin-top:8px;${pl.qualification_status_at_proposal==='QUALIFIED'?'color:var(--pass)':'color:var(--warn)'}">
        ESTADO DE CALIFICACIÓN DEL MODELO al proponer:
        <span class="mono">${esc(pl.qualification_status_at_proposal)}</span>
        ${pl.qualification_status_at_proposal!=='QUALIFIED' ? `
        <div style="margin-top:4px">Esta firma NO afirma que el modelo esté calificado --
        solo autoriza presupuesto/alcance. La inferencia real seguirá bloqueada
        (salvo recalificación) hasta que el modelo pase a QUALIFIED por separado.</div>` : ''}
      </div>

      <div style="margin-top:10px"><b>RUN_FINGERPRINT</b> <span class="meta">(cualquier cambio desde aquí invalida esta autorización)</span></div>
      <div class="meta" style="margin-top:4px">catalog_sha256: <span class="mono">${esc((fp.catalog_sha256||'').slice(0,16))}…</span></div>
      <div class="meta">catalog_version: <span class="mono">${esc(fp.catalog_version)}</span></div>
      <div class="meta">golden_dataset_sha256: <span class="mono">${esc((fp.golden_dataset_sha256||'').slice(0,16))}…</span></div>
      <div class="meta">model_name / model_digest: <span class="mono">${esc(fp.model_name)} / ${esc((fp.model_digest||'').slice(0,16))}…</span></div>
      <div class="meta">num_ctx / temperature: <span class="mono">${esc(fp.num_ctx)} / ${esc(fp.temperature)}</span></div>

      <div class="meta" style="margin-top:10px">${esc(p.reason||'')}</div>

      ${signatureForm(prefix)}
      ${NO_EJECUTA}
      <div class="meta" style="margin-top:6px;color:var(--faint)">
        Confirmar esto NO lanza ninguna corrida real -- el runner gobernado
        (batches, checkpoints per_document, resume por fingerprint, topes
        duros de D4-A) es una pieza de infraestructura aparte, todavía no
        construida a propósito.</div>
      <div style="margin-top:8px">
        <button id="${prefix}-submit-btn" onclick="govSubmitCorpusAuthorization('${esc(p.decision_instance_id)}','${esc(prefix)}')">
          Confirmar ${esc(p.decision_instance_id)}</button>
      </div>
      ${statusLine(prefix)}
    </div>`;
  };

  return `
  <div class="card">
    <b>Autorización de corpus — go/no-go (G8)</b>
    <div class="meta" style="margin-top:6px">
      Distinta de D4-A (presupuesto): esta decisión ata la autorización al
      <span class="mono">run_fingerprint</span> EXACTO de configuración
      (catálogo, prompts, modelo, golden dataset) -- un cambio de
      cualquiera de esos campos desde la firma invalida la autorización,
      no se hereda.</div>
    ${propuestas.map(bloque).join('') || '<div class="meta" style="margin-top:8px;color:var(--pass)">Ninguna propuesta pendiente de firma.</div>'}
    <div style="margin-top:12px"><button onclick="govOpen('')">Volver al índice</button></div>
  </div>`;
}

/* ── Panel — Piloto de diagnóstico (PILOT_EXECUTION, plan
   W5V2_PILOTO_DIAGNOSTICO_PRECORPUS.md / W5V2_REMEDIACION_RECALL_MODELO.md)
   ── autoriza SOLO un alcance acotado y explícito, con tope duro de
   llamadas, para diagnosticar el pipeline antes de comprometer el corpus
   formal. Mismo patrón que d4a/corpus-authorization: propuesta real ya
   creada por Capa 8 (agent_proposed), este panel solo confirma. */

function pilotExecutionProposals(){
  return (GOV?.proposals?.PILOT_EXECUTION || []).filter(p => p.proposal_state === 'PROPOSED');
}

function panelPilotExecution(){
  const propuestas = pilotExecutionProposals();

  const bloque = (p) => {
    const pl = p.payload || {};
    const scope = pl.scope || [];
    const prefix = 'pilexec_' + p.decision_instance_id.replace(/[^a-zA-Z0-9]/g, '_');
    const filas = scope.map(u => `<tr>
      <td class="mono">${esc(u.document_id)}</td>
      <td class="mono">${esc(u.agent_id)}</td>
      <td class="mono">${esc(u.requirement_id)}</td>
      <td class="mono">${esc((u.page_indices||[]).join(', '))}</td>
      <td class="mono">${esc(u.purpose)}</td>
      <td class="meta">${esc(u.selection_reason)}</td>
    </tr>`).join('');
    return `<div class="card" style="margin-top:10px;padding:8px;border:1px solid var(--warn)">
      <b>${esc(p.decision_instance_id)}</b>

      <div style="margin-top:8px;display:grid;grid-template-columns:1fr 1fr;gap:6px 16px">
        <div class="meta">TOPE DURO DE LLAMADAS: <span class="mono">${esc(pl.max_calls)}</span></div>
        <div class="meta">UNIDADES EN EL ALCANCE: <span class="mono">${scope.length}</span></div>
        <div class="meta">AUTORIZA CORPUS_AUTHORIZATION: <span class="mono" style="color:var(--fail)">${esc(String(pl.authorizes_corpus))}</span></div>
        <div class="meta">AUTORIZA BASELINE FORMAL: <span class="mono" style="color:var(--fail)">${esc(String(pl.authorizes_baseline))}</span></div>
      </div>

      <div class="meta" style="margin-top:8px;color:var(--warn)">
        Familia SEPARADA de CORPUS_AUTHORIZATION/D4 -- ninguna otra familia
        consulta PILOT_EXECUTION, así que firmar esto no puede, ni por
        accidente, satisfacer la cobertura que el corpus formal exige.</div>

      <div class="meta" style="margin-top:10px">${esc(p.reason||'')}</div>

      <div style="margin-top:10px"><b>ALCANCE EXPLÍCITO (${scope.length})</b></div>
      <table class="tbl" style="width:100%;font-size:11px;margin-top:6px">
        <thead><tr><th>Documento</th><th>Agente</th><th>Requisito</th><th>Página(s)</th><th>Propósito</th><th>Motivo de selección</th></tr></thead>
        <tbody>${filas}</tbody>
      </table>

      ${signatureForm(prefix)}
      ${NO_EJECUTA}
      <div class="meta" style="margin-top:6px;color:var(--faint)">
        Confirmar esto NO lanza ninguna llamada real a Ollama -- el runner
        del piloto es una pieza aparte que se invoca por separado, siempre
        con este tope duro de llamadas como techo.</div>
      <div style="margin-top:8px">
        <button id="${prefix}-submit-btn" onclick="govSubmitPilotExecution('${esc(p.decision_instance_id)}','${esc(prefix)}')">
          Confirmar ${esc(p.decision_instance_id)}</button>
      </div>
      ${statusLine(prefix)}
    </div>`;
  };

  return `
  <div class="card">
    <b>Piloto de diagnóstico — alcance acotado (pre-corpus)</b>
    <div class="meta" style="margin-top:6px">
      Ligera y separada de D4/CORPUS_AUTHORIZATION a propósito: existe para
      diagnosticar el pipeline (representatividad, recall) ANTES de
      comprometer una corrida formal de 80-94h. Nunca promueve
      FORMAL_BASELINE_READY.</div>
    ${propuestas.map(bloque).join('') || '<div class="meta" style="margin-top:8px;color:var(--pass)">Ninguna propuesta de piloto pendiente de firma.</div>'}
    <div style="margin-top:12px"><button onclick="govOpen('')">Volver al índice</button></div>
  </div>`;
}

/* ── Panel — Capa semántica local, llamadas de embedding (R2.2 §4.2) ──── */

function embedExecutionProposals(){
  return (GOV?.proposals?.EMBED_EXECUTION || []).filter(p => p.proposal_state === 'PROPOSED');
}

function panelEmbedExecution(){
  const propuestas = embedExecutionProposals();

  const bloque = (p) => {
    const pl = p.payload || {};
    const scope = pl.scope || [];
    const prefix = 'embexec_' + p.decision_instance_id.replace(/[^a-zA-Z0-9]/g, '_');
    const filas = scope.map(u => `<tr>
      <td class="mono">${esc(u.document_id)}</td>
      <td class="mono">${esc(u.purpose)}</td>
      <td class="meta">${esc(u.selection_reason)}</td>
    </tr>`).join('');
    return `<div class="card" style="margin-top:10px;padding:8px;border:1px solid var(--warn)">
      <b>${esc(p.decision_instance_id)}</b>

      <div style="margin-top:8px;display:grid;grid-template-columns:1fr 1fr;gap:6px 16px">
        <div class="meta">TOPE DURO DE LLAMADAS: <span class="mono">${esc(pl.max_calls)}</span></div>
        <div class="meta">MODELO DE EMBEDDING: <span class="mono">${esc(pl.embedding_model)}</span></div>
        <div class="meta">AUTORIZA PILOT_EXECUTION: <span class="mono" style="color:var(--fail)">${esc(String(pl.authorizes_pilot_execution))}</span></div>
        <div class="meta">AUTORIZA CORPUS_AUTHORIZATION: <span class="mono" style="color:var(--fail)">${esc(String(pl.authorizes_corpus))}</span></div>
      </div>

      <div class="meta" style="margin-top:8px;color:var(--warn)">
        Un embedding es un vector determinista de un input -- no genera
        texto ni conclusiones, no es juicio LLM. Familia SEPARADA de
        PILOT_EXECUTION: firmar esto no puede, ni por accidente, gastar
        presupuesto de juicio ni autorizar una corrida de juicio.</div>

      <div class="meta" style="margin-top:10px">${esc(p.reason||'')}</div>

      <div style="margin-top:10px"><b>ALCANCE EXPLÍCITO (${scope.length})</b></div>
      <table class="tbl" style="width:100%;font-size:11px;margin-top:6px">
        <thead><tr><th>Documento</th><th>Propósito</th><th>Motivo de selección</th></tr></thead>
        <tbody>${filas}</tbody>
      </table>

      ${signatureForm(prefix)}
      ${NO_EJECUTA}
      <div class="meta" style="margin-top:6px;color:var(--faint)">
        Confirmar esto NO calcula ningún embedding real -- el runner de
        recuperación semántica es una pieza aparte que se invoca por
        separado, siempre con este tope duro de llamadas como techo.</div>
      <div style="margin-top:8px">
        <button id="${prefix}-submit-btn" onclick="govSubmitEmbedExecution('${esc(p.decision_instance_id)}','${esc(prefix)}')">
          Confirmar ${esc(p.decision_instance_id)}</button>
      </div>
      ${statusLine(prefix)}
    </div>`;
  };

  return `
  <div class="card">
    <b>Capa semántica local — llamadas de embedding (R2.2 §4.2)</b>
    <div class="meta" style="margin-top:6px">
      Ligera y separada de PILOT_EXECUTION a propósito: mide recuperación
      semántica pura (BM25 + embeddings + fusión) para el caso de
      paráfrasis (P2/P4/P5/P6/P7, R2.2 §3) ANTES de comprometer
      presupuesto de juicio nuevo. Nunca promueve CORPUS_READY ni
      PRODUCTION_ENABLEMENT.</div>
    ${propuestas.map(bloque).join('') || '<div class="meta" style="margin-top:8px;color:var(--pass)">Ninguna propuesta de embedding pendiente de firma.</div>'}
    <div style="margin-top:12px"><button onclick="govOpen('')">Volver al índice</button></div>
  </div>`;
}

function panelExcepcion(){
  const a = GOV.audit;
  const MEDIDAS = medidas();
  const pendientes = MEDIDAS.filter(m=>!m.ok).length;
  const forks = a.unbacked_known_fork_entry_ids || [];
  return `
  <div class="card">
    <b>Excepción de auditoría — FORK-2026-06-15-001</b>
    ${auditDimensions(a)}

    <div style="margin-top:12px"><b>CAUSA RAÍZ</b> <span class="meta">— establecida, no conjeturada</span></div>
    <div class="meta"><span class="mono">stale_in_process_head_cache</span>.
      Dos procesos cachearon la cabeza de la cadena y ninguno la releyó; el
      segundo escribió 3 min 10 s después con su valor obsoleto. Con ese margen,
      un lock por sí solo no lo habría evitado: el problema era la caché, no la
      simultaneidad. Corregido por <span class="mono">8c033fa</span>, 27 minutos
      después del fork.</div>

    <div style="margin-top:12px"><b>RIESGO</b></div>
    <div class="meta">autenticidad del contenido: <b>NO AFECTADA</b> (hash_errors = 0)</div>
    <div class="meta">verificabilidad de secuencia: <b>AFECTADA localmente</b> (2 entradas)</div>
    <div class="meta">conclusiones regulatorias: <b>ninguna</b> se apoya en ese tramo</div>

    <div style="margin-top:12px"><b>MEDIDAS PREVENTIVAS</b></div>
    ${MEDIDAS.map(m=>`<div class="meta">
      <span style="color:${m.ok?'var(--pass)':'var(--warn)'}">${m.ok?'✓':'☐'}</span>
      ${esc(m.txt)} <span style="color:var(--faint)">— ${esc(m.ev)}</span></div>`).join('')}

    <div style="margin-top:12px"><b>SE PIDE</b></div>
    <div class="meta">Reportar CHAIN_CONTINUITY como
      <span class="mono">ACCEPTED_WITH_DOCUMENTED_EXCEPTION</span> para
      ${esc(forks.join(', ') || 'ese entry_id')} y solo para ese.</div>
    <div style="margin-top:8px"><b>NO SE PIDE</b></div>
    <div class="meta">Declarar la cadena íntegra · declarar conformidad global ·
      aceptar forks futuros · reescribir, borrar o reordenar nada.</div>

    ${signatureForm('gexc')}
    <div style="margin-top:12px">
      <button id="gexc-approve-btn" ${pendientes?'disabled':''} onclick="govSubmitExcepcion('APPROVE')">Aceptar</button>
      <button id="gexc-reject-btn" onclick="govSubmitExcepcion('REJECT')" style="margin-left:6px">Rechazar</button>
      <button onclick="govOpen('')" style="margin-left:6px">Volver al índice</button>
    </div>
    ${pendientes ? `<div class="meta" style="margin-top:8px;color:var(--warn)">
      "Aceptar" deshabilitado: faltan ${pendientes} de las 5 medidas preventivas.
      Aceptar una excepción cuya prevención no está implementada es aceptar que
      vuelva a pasar. Rechazar sí está disponible: es un final legítimo.</div>`:''}
    ${statusLine('gexc')}
  </div>`;
}

/* ── Paneles cuyo gate aún no está abierto ─────────────────────────────── */

function panelPendiente(p){
  const g = gateOf(p.gate);
  return `<div class="card">
    <b>${esc(p.titulo)}</b>
    <div class="meta" style="margin-top:6px">${esc(p.resumen)}</div>
    <div class="meta" style="margin-top:10px;color:var(--warn)">
      Gate ${esc(p.gate)} — ${esc(g.status)}.
      ${esc((g.blocked_by||[]).join(' · ') || 'sin precondiciones pendientes; el panel de edición llega con su gate.')}
    </div>
    <div class="meta" style="margin-top:6px;color:var(--faint)">
      Se muestra deshabilitado y explicado, no oculto: un panel ausente es un
      bloqueo inexplicable.</div>
    <div style="margin-top:12px"><button onclick="govOpen('')">Volver al índice</button></div>
  </div>`;
}

/* ── router de la vista ────────────────────────────────────────────────── */

let PANEL_ABIERTO = '';

export function govOpen(panelId){
  PANEL_ABIERTO = panelId || '';
  location.hash = PANEL_ABIERTO ? `gobierno/${PANEL_ABIERTO}` : 'gobierno';
  paint();
}

/* W5V2_FIX_FIRMA_SILENCIOSA §2.5 -- banner PROACTIVO de estado obsoleto,
   no oculto, con un boton que recarga SIN recargar toda la pagina.
   Deliberado: nunca se re-firma sola con el hash nuevo (la re-firma tras un
   409 es siempre un acto humano explicito sobre el estado ya revisado). */
function staleBanner(){
  return `<div class="card" style="border:1px solid var(--warn);margin-bottom:10px">
    <b style="color:var(--warn)">El estado cambió desde que cargaste esta página</b>
    <div class="meta" style="margin-top:6px">Otra sesión, otra pestaña o una acción
      reciente escribió en el almacén de decisiones. Firmar sobre un estado viejo
      produce un 409 (o, si la lectura no coincide con el hash, un conflicto que
      el servidor rechaza igual). Recarga el estado antes de continuar.</div>
    <div style="margin-top:10px"><button onclick="govRefresh()">Recargar estado</button></div>
  </div>`;
}

function paint(){
  const el = document.getElementById('gov-body'); if(!el || !GOV) return;
  const p = PANELS.find(x=>x.id===PANEL_ABIERTO);
  const banner = GOV_STALE ? staleBanner() : '';
  if(!p){ el.innerHTML = banner + indexView(); return; }
  let body;
  if(p.id==='d1-correccion')       body = panelD1Correccion();
  else if(p.id==='d1a')            body = panelD1A();
  else if(p.id==='pack-211')       body = panelPack211();
  else if(p.id==='d2a')            body = panelD2A();
  else if(p.id==='catalog-version') body = panelCatalogVersion();
  else if(p.id==='matrix-version-regularizacion') body = panelMatrixVersionRegularizacion();
  else if(p.id==='applicability-matrix') body = panelApplicabilityMatrix();
  else if(p.id==='golden-dataset') body = panelGoldenDataset();
  else if(p.id==='source-currency') body = panelSourceCurrency();
  else if(p.id==='source-origin-verification') body = panelSourceOriginVerification();
  else if(p.id==='excepcion-auditoria') body = panelExcepcion();
  else if(p.id==='d4a')            body = panelD4A();
  else if(p.id==='corpus-authorization') body = panelCorpusAuthorization();
  else if(p.id==='pilot-execution')      body = panelPilotExecution();
  else if(p.id==='prompt-version-regularizacion') body = panelPromptVersionRegularizacion();
  else if(p.id==='embed-execution')       body = panelEmbedExecution();
  else                             body = panelPendiente(p);
  el.innerHTML = banner + body;
  if(p.id==='d1-correccion') govRecalcHash();
}

export function renderGovernance(data){
  GOV = data;
  GOV_STALE = false;  // toda carga fresca (incluida govRefresh) limpia el aviso
  const h = document.getElementById('gov-state-hash');
  if(h) h.textContent = (data.state_hash||'').slice(0,16) + '…';
  const m = location.hash.match(/^#gobierno\/(.+)$/);
  PANEL_ABIERTO = m ? m[1] : PANEL_ABIERTO;
  paint();
}

/* Deteccion PROACTIVA de obsolescencia (H1): al recuperar foco o visibilidad
   la pestaña, releer solo el state_hash (GET, sin escribir nada) y comparar
   contra el cargado. Nunca declara "obsoleto" por una excepcion de red o un
   GET fallido -- sin evidencia, no se bloquea la firma. */
async function checkStaleness(){
  if(!GOV || !PANEL_ABIERTO || GOV_STALE) return;
  try {
    const r = await fetch(API_BASE + '/api/v1/layer9/governance/state', {headers: headers()});
    if(!r.ok) return;
    const data = await r.json();
    if(data.state_hash && GOV.state_hash && data.state_hash !== GOV.state_hash){
      GOV_STALE = true;
      paint();
    }
  } catch(e) { /* sin conectividad -- no se declara obsoleto sin poder comprobarlo */ }
}

/* Guardas de entorno: el harness de tests (test_governance_ui.py) monta un
   DOM minimo sin addEventListener -- no es un navegador real y no debe
   fallar por eso. */
if(typeof document !== 'undefined' && typeof document.addEventListener === 'function'){
  document.addEventListener('visibilitychange',
    () => { if(document.visibilityState === 'visible') checkStaleness(); });
}
if(typeof window !== 'undefined' && typeof window.addEventListener === 'function'){
  window.addEventListener('focus', checkStaleness);
}

/* ── target_set_hash en vivo ───────────────────────────────────────────── */

/* sha256 de los ids ordenados unidos por \n — la MISMA regla que
   `compute_target_set_hash` del backend, deliberadamente reproducible a mano
   con `printf '%s\n' ... | sha256sum`. Si el navegador no expone WebCrypto
   (contexto no seguro), se dice que no se pudo calcular en vez de mostrar un
   valor inventado. */
export async function govRecalcHash(){
  const out = document.getElementById('d1c-hash'); if(!out) return;
  const ids = [...document.querySelectorAll('.d1c-src:checked')].map(i=>i.value).sort();
  if(!ids.length){ out.textContent = '(ninguna fuente marcada)'; return; }
  if(!window.crypto?.subtle){ out.textContent = '(no calculable en este contexto)'; return; }
  const buf = new TextEncoder().encode(ids.join('\n'));
  const dig = await crypto.subtle.digest('SHA-256', buf);
  out.textContent = [...new Uint8Array(dig)].map(b=>b.toString(16).padStart(2,'0')).join('');
}

/* ── POSTs ─────────────────────────────────────────────────────────────── */

async function postJSON(url, body){
  const r = await fetch(API_BASE+url, {method:'POST', headers:headers(),
                                       body:JSON.stringify(body)});
  let data = null;
  try { data = await r.json(); } catch(e){ /* cuerpo no-JSON */ }
  return { ok:r.ok, status:r.status, data };
}

function explicaError(status, data){
  /* Panel ARQ 2026-08-04: /governance/artifact-version/sign devuelve
     detail={detail, reason} (reason en {proposal_mismatch, duplicate,
     stale_state}) -- se desempaqueta antes de mostrarlo, nunca JSON crudo. */
  const inner = data?.detail;
  const reason = (inner && typeof inner === 'object') ? inner.reason : null;
  const detalle = (inner && typeof inner === 'object') ? (inner.detail ?? '')
                 : (typeof inner === 'string' ? inner : JSON.stringify(inner ?? ''));
  const porReason = {
    proposal_mismatch: ' — el panel mostraba una propuesta distinta a la almacenada: recarga antes de firmar.',
    duplicate: ' — esta propuesta ya fue resuelta (firmada, aplicada o retirada).',
    stale_state: ' — recarga y revisa antes de firmar.',
  };
  /* 422 y 409 dicen cosas distintas y la guía tiene que diferenciarlas: un
     campo ausente NO se arregla recargando, y decir "recarga y revisa" ante un
     422 manda al humano a perseguir un fantasma. */
  if(status===422) return 'Rechazado (422): ' + detalle
       + ' — es un problema de la petición o de la identidad, no del estado: recargar no lo arregla.';
  if(status===409) return 'Conflicto (409): ' + detalle + (porReason[reason] || ' — recarga y revisa antes de firmar.');
  if(status===404) return 'No encontrado (404): ' + detalle;
  return 'Error ' + status + ': ' + detalle;
}

/* Ciclo completo: proponer y confirmar. Se hace en dos POST y no en uno
   porque son dos actos distintos y el almacén los distingue -- la propuesta
   queda registrada aunque la firma se rechace después.

   El `state_hash` se ENCADENA: el del GET va al propose (que valida lo que el
   humano leyó), y el que devuelve el propose va al confirm. Mandar el del GET
   a las DOS llamadas era el defecto: el propose escribe, así que para cuando
   llegaba el confirm ese hash ya estaba obsoleto por la propia acción del
   usuario, y el 409 era inevitable en todos los casos. Ver G2.1. */
async function proponerYConfirmar(family, targetIds, sig, extra={}, ui={}){
  const { statusPrefix, btnId } = ui;
  const status = (kind, text) => {
    if(statusPrefix) setStatus(statusPrefix, kind, text);
    else if(kind !== 'busy') toast(text);
  };

  if(!sig.reason){ status('warn', 'El motivo es obligatorio.'); return; }
  if(!targetIds.length){ status('warn', 'No hay ninguna fuente seleccionada.'); return; }
  if(GOV_STALE){
    status('warn', 'El estado cambió desde que cargaste esta página. '
      + 'Pulsa "Recargar estado" arriba antes de firmar.');
    return;
  }

  if(btnId) setBusy(btnId, true);
  status('busy', 'Enviando propuesta…');
  try {
    const prop = await postJSON(`/api/v1/layer9/governance/decisions/${family}/propose`, {
      target_ids: targetIds, proposed_by_id: 'mission_control_ui',
      reason: sig.reason,
      /* El hash de LA FAMILIA, no el global: el servidor compara por familia y
         mandarle el global es comparar dos ámbitos distintos -> 409 inmediato. */
      family_state_hash: GOV?.family_state_hashes?.[family],
      ...extra,
    });
    if(!prop.ok){ status('fail', explicaError(prop.status, prop.data)); return; }

    /* Los tokens SALEN de la respuesta del propose, que es la autoridad: es el
       acto que cambió el estado, así que es el único que puede describir el
       estado posterior. Si alguno falta, se aborta ANTES de firmar en vez de
       mandar `undefined` -- ese envío silencioso produjo un 409 "falta
       state_hash" que mandó a recargar durante una sesión entera. */
    const iid = prop.data.proposal_id || prop.data.decision_instance_id;
    const fh  = prop.data.family_state_hash ?? prop.data.state_hash;
    if(!iid || !fh){
      status('fail', 'El servidor no devolvió los tokens de firma (proposal_id/'
          + 'family_state_hash). No se firma a ciegas. Propuesta: ' + (iid||'?'));
      return;
    }
    if(prop.data.reused_existing_proposal){
      status('warn', `Se reutiliza la propuesta ${iid} en vez de crear otra.`);
    }
    status('busy', 'Confirmando firma…');
    const conf = await postJSON(`/api/v1/layer9/governance/decisions/${iid}/confirm`, {
      approved_by_display_name: sig.name || sig.id,
      reason: sig.reason,
      family_state_hash: fh,
      expected_active_instance_id: prop.data.expected_active_instance_id ?? null,
    });
    if(!conf.ok){
      status('fail', explicaError(conf.status, conf.data) +
            ` La propuesta ${iid} queda registrada y sin confirmar.`);
      return;
    }
    status('ok', explicaFirma(conf.data));
    govRefresh();
  } catch(e) {
    /* Excepcion JS (red caida, timeout, bug) -- nunca solo console.error:
       sin esto, cualquier fallo entre el mousedown y el primer postJSON es
       indistinguible de "el clic no hizo nada". */
    status('fail', 'Error inesperado: ' + (e && e.message ? e.message : String(e)));
  } finally {
    if(btnId) setBusy(btnId, false);
  }
}

/* Un clic repetido NO debe parecer una firma nueva. El servidor es idempotente
   desde el agujero de /confirm —tres firmas del mismo acto, las tres ACTIVE— y
   aquí se dice en voz alta: si no se escribió nada, se dice que no se escribió
   nada y quién lo había firmado ya. Un toast de "Registrada X" sobre una
   escritura que no ocurrió es peor que no avisar. */
function explicaFirma(data){
  if(data?.already_signed){
    return `Ya estaba firmada: ${data.decision_instance_id}`
         + (data.signed_by_id ? ` por ${data.signed_by_id}` : '')
         + (data.signed_at ? ` el ${String(data.signed_at).slice(0,16).replace('T',' ')}` : '')
         + '. No se registró nada nuevo.';
  }
  return `Registrada ${data.decision_instance_id}. No se ejecutó ningún efecto.`;
}

export async function govSubmitD1Correccion(){
  const ids = [...document.querySelectorAll('.d1c-src:checked')].map(i=>i.value);
  /* Una CORRECTION tiene que decir A QUE supersede (I-6), y se deriva del
     estado en vez de fijarse a mano: la D1 vigente puede haber cambiado -- de
     hecho cambio, cuando Cesar corrigio la cadencia por la UI legacy. Sin
     esto el panel devolvia 422 en el primer clic. */
  const activas = GOV?.coverage?.D1?.confirmed_active_instances || [];
  const supersede = activas[activas.length - 1];
  if(!supersede){
    setStatus('d1c','warn','No hay ninguna D1 vigente que corregir. Recarga el estado.');
    return;
  }
  await proponerYConfirmar('D1', ids, readSignature('d1c'),
                           {decision_type:'CORRECTION',
                            supersedes_instance_id: supersede},
                           {statusPrefix:'d1c', btnId:'d1c-submit-btn'});
}

export async function govSubmitD1A(){
  await proponerYConfirmar('D1', [PART211], readSignature('d1a'),
                           {decision_type:'ADDENDUM', amendment_sequence:1},
                           {statusPrefix:'d1a', btnId:'d1a-submit-btn'});
}

export async function govSubmitPack211(){
  /* DEFECTO REAL cerrado (W5V2_FIX_FIRMA_SILENCIOSA, 2026-07-31): tras
     revocar D2-2026-003 (la firma fabricada), Cesar intento la aprobacion
     real y el servidor la trato como "Ya estaba firmada... por
     claude_probe" -- corregido en governance_service.equivalent_signed_decision
     (ya no cuenta un candidato cuyo target fue revocado). Pero ADEMAS,
     `decision_scope_resolver._effective_coverage` tiene su propia regla
     dura y DELIBERADA (test_t07_revocation_wins_over_a_later_addendum): una
     vez que un target fue revocado, ORIGINAL/ADDENDUM nunca lo vuelve a
     cubrir -- "retirar autorizacion es la operacion segura y domina", a
     proposito, para que una firma valida no pueda desactivarse por
     accidente con un simple addendum posterior. Esa regla es correcta y no
     se toca: la via gobernada para reactivar un target revocado es que la
     aprobacion nueva SUPERSEDA la REVOCATION misma (CORRECTION), afirmando
     explicitamente "esa revocacion ya cumplio su proposito, esto la
     reemplaza" -- nunca ignorarla en silencio.
     ORIGINAL + EXPLICIT_LIST son los defaults de GovernanceProposeBody: se
     usan tal cual mientras el target NO este revocado (el primer D2 real
     que cubre este id; el unico D2 previo, D2_evidence_packs, quedo
     huerfano sin objetivo -- G2'). */
  const yaRevocado = (GOV?.coverage?.D2?.revoked_ids || []).includes(REQ_211_68B);
  const extra = yaRevocado
    ? {decision_type:'CORRECTION', supersedes_instance_id: INCIDENTE_D2_003_REVOCATION}
    : {};
  await proponerYConfirmar('D2', [REQ_211_68B], readSignature('pk211'), extra,
                           {statusPrefix:'pk211', btnId:'pk211-submit-btn'});
}

export async function govSubmitD2A(requirementId, prefix){
  /* Mismo criterio que govSubmitPack211(): si este requisito ya fue
     revocado alguna vez, la via gobernada es CORRECTION superseding la
     revocacion, nunca un ORIGINAL que la ignore (decision_scope_resolver
     hace que la revocacion domine a proposito). Generico -- no asume que
     el unico target revocable sea REQ_211_68B. */
  const revocados = GOV?.coverage?.D2?.revoked_ids || [];
  let extra = {};
  if(revocados.includes(requirementId)){
    const activas = GOV?.coverage?.D2?.confirmed_active_instances || [];
    setStatus(prefix, 'warn', `${requirementId} fue revocado antes -- necesita una CORRECTION `
      + `explicita sobre la revocacion, no soportado desde este panel todavia. `
      + `Instancias activas de D2: ${activas.join(', ') || '(ninguna)'}.`);
    return;
  }
  await proponerYConfirmar('D2', [requirementId], readSignature(prefix), extra,
                           {statusPrefix: prefix, btnId: prefix+'-submit-btn'});
}


/* Panel ARQ 2026-08-04 (§3.3): firma con ECHO-BACK -- el POST reenvía los
   6 campos que el humano VIO en pantalla (proposal_id/artifact_path/
   from_version/to_version/ambos hashes) más el state_hash vigente. El
   backend (/governance/artifact-version/sign) los compara byte a byte
   contra lo almacenado ANTES de confirmar nada -- nunca "lo mas parecido".
   Reemplaza a confirmarPropuestaExistente() para este panel: aquella
   confía en que el cliente mandó el id correcto; esta prueba que el
   cliente vio EXACTAMENTE lo que existe. */
export async function govSubmitCatalogVersion(){
  const cs = GOV?.artifacts?.catalog_state;
  const valida = validCatalogVersionProposal(cs);
  if(!valida){
    setStatus('catv', 'warn', 'No hay ninguna propuesta ARTIFACT_VERSION con la '
      + 'transición vigente (atada al hash/versión vivos) para este artefacto.');
    return;
  }
  const sig = readSignature('catv');
  if(!sig.reason){ setStatus('catv','warn','El motivo es obligatorio.'); return; }
  if(GOV_STALE){
    setStatus('catv','warn','El estado cambió desde que cargaste esta página. '
      + 'Pulsa "Recargar estado" arriba antes de firmar.');
    return;
  }
  setBusy('catv-submit-btn', true);
  setStatus('catv','busy','Firmando (echo-back)…');
  try {
    const r = await postJSON('/api/v1/layer9/governance/artifact-version/sign', {
      proposal_id: valida.decision_instance_id,
      artifact_path: valida.payload.artifact_path,
      from_version: valida.payload.from_version,
      to_version: valida.payload.to_version,
      artifact_hash_before: valida.payload.artifact_hash_before,
      expected_hash_after: valida.payload.expected_hash_after,
      state_hash: GOV?.family_state_hashes?.ARTIFACT_VERSION,
      reason: sig.reason,
      approved_by_display_name: sig.name || sig.id,
    });
    if(!r.ok){ setStatus('catv','fail', explicaError(r.status, r.data)); return; }
    setStatus('catv','ok', explicaFirma(r.data));
    govRefresh();
  } catch(e) {
    setStatus('catv','fail', 'Error de red/JS al firmar: ' + (e && e.message || e));
  } finally {
    setBusy('catv-submit-btn', false);
  }
}

/* Misma firma con echo-back que govSubmitCatalogVersion(), mismo endpoint
   generico (parametrizado por artifact_path, no hubo que tocarlo) --
   MATRIX_ARTIFACT_ID en vez de CATALOG_ARTIFACT_ID. */
export async function govSubmitMatrixVersionRegularizacion(){
  const ms = GOV?.artifacts?.matrix_state;
  const valida = validMatrixVersionProposal(ms);
  if(!valida){
    setStatus('mxv', 'warn', 'No hay ninguna propuesta ARTIFACT_VERSION con la '
      + 'transición vigente (atada al hash/versión vivos) para este artefacto.');
    return;
  }
  const sig = readSignature('mxv');
  if(!sig.reason){ setStatus('mxv','warn','El motivo es obligatorio.'); return; }
  if(GOV_STALE){
    setStatus('mxv','warn','El estado cambió desde que cargaste esta página. '
      + 'Pulsa "Recargar estado" arriba antes de firmar.');
    return;
  }
  setBusy('mxv-submit-btn', true);
  setStatus('mxv','busy','Firmando (echo-back)…');
  try {
    const r = await postJSON('/api/v1/layer9/governance/artifact-version/sign', {
      proposal_id: valida.decision_instance_id,
      artifact_path: valida.payload.artifact_path,
      from_version: valida.payload.from_version,
      to_version: valida.payload.to_version,
      artifact_hash_before: valida.payload.artifact_hash_before,
      expected_hash_after: valida.payload.expected_hash_after,
      state_hash: GOV?.family_state_hashes?.ARTIFACT_VERSION,
      reason: sig.reason,
      approved_by_display_name: sig.name || sig.id,
    });
    if(!r.ok){ setStatus('mxv','fail', explicaError(r.status, r.data)); return; }
    setStatus('mxv','ok', explicaFirma(r.data));
    govRefresh();
  } catch(e) {
    setStatus('mxv','fail', 'Error de red/JS al firmar: ' + (e && e.message || e));
  } finally {
    setBusy('mxv-submit-btn', false);
  }
}

/* Confirma DIRECTAMENTE una propuesta ya existente y visible en pantalla --
   sin propose() previo (a diferencia de `proponerYConfirmar`) y sin
   echo-back (a diferencia de catalog-version): el payload de estas dos
   familias es siempre `{}`, así que no hay campos que el humano deba ver
   coincidir byte a byte antes de firmar. Reutilizado por los paneles de
   matriz de aplicabilidad y golden dataset (RC-7, 2026-08-05). */
async function confirmarPropuestaExistente(instanceId, family, sig, {statusPrefix, btnId}){
  if(!sig.reason){ setStatus(statusPrefix,'warn','El motivo es obligatorio.'); return; }
  if(GOV_STALE){
    setStatus(statusPrefix,'warn','El estado cambió desde que cargaste esta página. '
      + 'Pulsa "Recargar estado" arriba antes de firmar.');
    return;
  }
  setBusy(btnId, true);
  setStatus(statusPrefix,'busy','Confirmando…');
  try {
    const r = await postJSON(`/api/v1/layer9/governance/decisions/${instanceId}/confirm`, {
      approved_by_display_name: sig.name || sig.id,
      reason: sig.reason,
      family_state_hash: GOV?.family_state_hashes?.[family],
    });
    if(!r.ok){ setStatus(statusPrefix,'fail', explicaError(r.status, r.data)); return; }
    setStatus(statusPrefix,'ok', explicaFirma(r.data));
    govRefresh();
  } catch(e) {
    setStatus(statusPrefix,'fail', 'Error de red/JS al firmar: ' + (e && e.message || e));
  } finally {
    setBusy(btnId, false);
  }
}

export async function govSubmitApplicabilityMatrix(){
  const ms = GOV?.artifacts?.matrix_state;
  const valida = validApplicabilityMatrixProposal(ms);
  if(!valida){
    setStatus('matx','warn','No hay ninguna propuesta PROPOSED atada a la versión vigente.');
    return;
  }
  await confirmarPropuestaExistente(valida.decision_instance_id, 'APPLICABILITY_MATRIX',
                                    readSignature('matx'),
                                    {statusPrefix:'matx', btnId:'matx-submit-btn'});
}

export async function govSubmitGoldenDataset(){
  const valida = validGoldenDatasetProposal();
  if(!valida){
    setStatus('gdset','warn','No hay ninguna propuesta PROPOSED para este artefacto.');
    return;
  }
  await confirmarPropuestaExistente(valida.decision_instance_id, 'ARTIFACT_VERSION',
                                    readSignature('gdset'),
                                    {statusPrefix:'gdset', btnId:'gdset-submit-btn'});
}

export async function govSubmitSourceCurrency(decisionInstanceId, prefix){
  const sig = readSignature(prefix);
  if(!sig.reason){
    setStatus(prefix,'warn','El motivo es obligatorio -- aquí es donde declaras tu propio '
      + 'juicio de vigencia, no una formalidad.');
    return;
  }
  await confirmarPropuestaExistente(decisionInstanceId, 'SOURCE_CURRENCY', sig,
                                    {statusPrefix:prefix, btnId:prefix+'-submit-btn'});
}

export async function govSubmitSourceOriginVerification(decisionInstanceId, prefix){
  const sig = readSignature(prefix);
  if(!sig.reason){ setStatus(prefix,'warn','El motivo es obligatorio.'); return; }
  await confirmarPropuestaExistente(decisionInstanceId, 'SOURCE_ORIGIN_VERIFICATION', sig,
                                    {statusPrefix:prefix, btnId:prefix+'-submit-btn'});
}

export async function govSubmitD4A(decisionInstanceId, prefix){
  const sig = readSignature(prefix);
  if(!sig.reason){ setStatus(prefix,'warn','El motivo es obligatorio.'); return; }
  await confirmarPropuestaExistente(decisionInstanceId, 'D4', sig,
                                    {statusPrefix:prefix, btnId:prefix+'-submit-btn'});
}

export async function govSubmitCorpusAuthorization(decisionInstanceId, prefix){
  const sig = readSignature(prefix);
  if(!sig.reason){ setStatus(prefix,'warn','El motivo es obligatorio.'); return; }
  await confirmarPropuestaExistente(decisionInstanceId, 'CORPUS_AUTHORIZATION', sig,
                                    {statusPrefix:prefix, btnId:prefix+'-submit-btn'});
}

export async function govSubmitPilotExecution(decisionInstanceId, prefix){
  const sig = readSignature(prefix);
  if(!sig.reason){ setStatus(prefix,'warn','El motivo es obligatorio.'); return; }
  await confirmarPropuestaExistente(decisionInstanceId, 'PILOT_EXECUTION', sig,
                                    {statusPrefix:prefix, btnId:prefix+'-submit-btn'});
}

export async function govSubmitEmbedExecution(decisionInstanceId, prefix){
  const sig = readSignature(prefix);
  if(!sig.reason){ setStatus(prefix,'warn','El motivo es obligatorio.'); return; }
  await confirmarPropuestaExistente(decisionInstanceId, 'EMBED_EXECUTION', sig,
                                    {statusPrefix:prefix, btnId:prefix+'-submit-btn'});
}

export async function govSubmitRevokeD2003(){
  /* REVOCATION retira `resolved_target_ids` (el requirement_id, no el
     decision_instance_id) SIN filtrar por `decision` -- revocar es la
     operacion segura (decision_scope_resolver._effective_coverage). I-6
     exige supersedes_instance_id apuntando a lo que se revoca. */
  await proponerYConfirmar('D2', [REQ_211_68B], readSignature('pk211rev'),
                           {decision_type:'REVOCATION',
                            supersedes_instance_id: INCIDENTE_D2_003},
                           {statusPrefix:'pk211rev', btnId:'pk211rev-submit-btn'});
}

export async function govSubmitExcepcion(verdict){
  const sig = readSignature('gexc');
  const btnId = verdict==='APPROVE' ? 'gexc-approve-btn' : 'gexc-reject-btn';
  if(!sig.reason){ setStatus('gexc','warn','El motivo es obligatorio.'); return; }
  const forks = GOV?.audit?.unbacked_known_fork_entry_ids || [];
  if(!forks.length){ setStatus('gexc','warn','No hay ningún fork pendiente de excepción.'); return; }
  if(GOV_STALE){
    setStatus('gexc','warn','El estado cambió desde que cargaste esta página. '
      + 'Pulsa "Recargar estado" arriba antes de firmar.');
    return;
  }

  setBusy(btnId, true);
  setStatus('gexc','busy','Enviando propuesta…');
  try {
    const prop = await postJSON('/api/v1/layer9/governance/decisions/AUDIT_EXCEPTION/propose', {
      target_ids: forks, proposed_by_id:'mission_control_ui', reason: sig.reason,
      state_hash: GOV?.state_hash,
    });
    if(!prop.ok){ setStatus('gexc','fail', explicaError(prop.status, prop.data)); return; }

    /* Mismos tokens autoritativos que en `proponerYConfirmar`: los del propose,
       nunca los del GET, y se aborta si no llegan. Este panel arrastraba el
       defecto idéntico. */
    const iid = prop.data.proposal_id || prop.data.decision_instance_id;
    const fh  = prop.data.family_state_hash ?? prop.data.state_hash;
    if(!iid || !fh){
      setStatus('gexc','fail','El servidor no devolvió los tokens de firma. No se firma a ciegas.');
      return;
    }
    const url = verdict==='APPROVE'
      ? `/api/v1/layer9/governance/decisions/${iid}/confirm`
      : `/api/v1/layer9/governance/decisions/${iid}/reject`;
    const body = verdict==='APPROVE'
      ? {approved_by_display_name:sig.name||sig.id,
         reason:sig.reason, family_state_hash:fh,
         expected_active_instance_id: prop.data.expected_active_instance_id ?? null}
      : {rejected_by_display_name:sig.name||sig.id,
         reason:sig.reason, state_hash:fh};

    setStatus('gexc','busy', verdict==='APPROVE' ? 'Confirmando aceptación…' : 'Confirmando rechazo…');
    const res = await postJSON(url, body);
    if(!res.ok){ setStatus('gexc','fail', explicaError(res.status, res.data)); return; }
    setStatus('gexc','ok', res.data?.already_signed ? explicaFirma(res.data)
      : verdict==='APPROVE'
      ? 'Excepción aceptada. CHAIN_CONTINUITY pasa a ACCEPTED_WITH_DOCUMENTED_EXCEPTION — nunca a VERIFIED.'
      : 'Excepción rechazada. PART11_COMPLIANCE permanece NOT_DETERMINED: es un final legítimo.');
    govRefresh();
  } catch(e) {
    setStatus('gexc','fail','Error inesperado: ' + (e && e.message ? e.message : String(e)));
  } finally {
    setBusy(btnId, false);
  }
}

export async function govRefresh(){
  const { refresh } = await import('./refresh.js');
  refresh('gobierno');
}
