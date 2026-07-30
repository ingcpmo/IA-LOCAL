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

const PANELS = [
  { id:'d1-correccion',      gate:'G2', family:'D1', titulo:'Corrección D1 — Fuentes regulatorias',
    resumen:'Materializa el snapshot que "ALL" nunca materializó.' },
  { id:'d1a',                gate:'G2', family:'D1', titulo:'D1-A — Adendo de cobertura',
    resumen:'Extiende la cobertura a 21 CFR Part 211, sin tocar la Corrección.' },
  { id:'pack-211',           gate:'G4', family:'D2', titulo:'Revisión del pack 21 CFR 211.68(b)',
    resumen:'Regla predicado de los 5 requisitos de Part 11. 0 criterios hoy.' },
  { id:'d2a',                gate:'G5', family:'D2', titulo:'D2-A — Aprobación de Evidence Packs',
    resumen:'Criterios interpretativos, pack a pack. Sin "apruebo todos".' },
  { id:'excepcion-auditoria',gate:'G7', family:'AUDIT_EXCEPTION', titulo:'Excepción de auditoría histórica',
    resumen:'FORK-2026-06-15-001. Aceptar o rechazar, con causa raíz establecida.' },
  { id:'d4a',                gate:'G8', family:'D4', titulo:'D4-A — Presupuesto de corrida',
    resumen:'Límites duros derivados, no escritos a mano.' },
];

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

/* ── formulario de firma, común a los paneles que registran ────────────── */

function signatureForm(prefix, {motivoLabel='MOTIVO'}={}){
  return `
  <div style="margin-top:12px;display:grid;grid-template-columns:150px 1fr;gap:6px;align-items:center">
    <label class="meta">${esc(motivoLabel)} *</label>
    <input id="${prefix}-reason" placeholder="por qué se registra esta decisión">
    <label class="meta">FIRMA — id *</label>
    <input id="${prefix}-id" placeholder="identificador real (no 'human', no 'admin')">
    <label class="meta">FIRMA — nombre</label>
    <input id="${prefix}-name" placeholder="nombre para mostrar">
  </div>
  <div class="meta" style="margin-top:6px;color:var(--faint)">
    La identidad se valida contra una lista ÚNICA compartida por toda la
    fábrica. Un nombre genérico no identifica a nadie y se rechaza con 422.
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
      <button onclick="govSubmitD1Correccion()">Registrar corrección</button>
      <button onclick="govOpen('')" style="margin-left:6px">Volver al índice</button>
    </div>
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
      <button ${(correccionHecha && !cubierto)?'':'disabled'}
              onclick="govSubmitD1A()">Registrar D1-A</button>
      <button onclick="govOpen('')" style="margin-left:6px">Volver al índice</button>
    </div>
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
      <button ${pendientes?'disabled':''} onclick="govSubmitExcepcion('APPROVE')">Aceptar</button>
      <button onclick="govSubmitExcepcion('REJECT')" style="margin-left:6px">Rechazar</button>
      <button onclick="govOpen('')" style="margin-left:6px">Volver al índice</button>
    </div>
    ${pendientes ? `<div class="meta" style="margin-top:8px;color:var(--warn)">
      "Aceptar" deshabilitado: faltan ${pendientes} de las 5 medidas preventivas.
      Aceptar una excepción cuya prevención no está implementada es aceptar que
      vuelva a pasar. Rechazar sí está disponible: es un final legítimo.</div>`:''}
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

function paint(){
  const el = document.getElementById('gov-body'); if(!el || !GOV) return;
  const p = PANELS.find(x=>x.id===PANEL_ABIERTO);
  if(!p){ el.innerHTML = indexView(); return; }
  if(p.id==='d1-correccion')       el.innerHTML = panelD1Correccion();
  else if(p.id==='d1a')            el.innerHTML = panelD1A();
  else if(p.id==='excepcion-auditoria') el.innerHTML = panelExcepcion();
  else                             el.innerHTML = panelPendiente(p);
  if(p.id==='d1-correccion') govRecalcHash();
}

export function renderGovernance(data){
  GOV = data;
  const h = document.getElementById('gov-state-hash');
  if(h) h.textContent = (data.state_hash||'').slice(0,16) + '…';
  const m = location.hash.match(/^#gobierno\/(.+)$/);
  PANEL_ABIERTO = m ? m[1] : PANEL_ABIERTO;
  paint();
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
  const detalle = typeof data?.detail === 'string' ? data.detail : JSON.stringify(data?.detail ?? '');
  /* 422 y 409 dicen cosas distintas y la guía tiene que diferenciarlas: un
     campo ausente NO se arregla recargando, y decir "recarga y revisa" ante un
     422 manda al humano a perseguir un fantasma. */
  if(status===422) return 'Rechazado (422): ' + detalle
       + ' — es un problema de la petición o de la identidad, no del estado: recargar no lo arregla.';
  if(status===409) return 'Conflicto (409): ' + detalle + ' — recarga y revisa antes de firmar.';
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
async function proponerYConfirmar(family, targetIds, sig, extra={}){
  if(!sig.reason){ toast('El motivo es obligatorio.'); return; }
  if(!sig.id){ toast('La firma exige un identificador real.'); return; }
  if(!targetIds.length){ toast('No hay ninguna fuente seleccionada.'); return; }

  const prop = await postJSON(`/api/v1/layer9/governance/decisions/${family}/propose`, {
    target_ids: targetIds, proposed_by_id: 'mission_control_ui',
    reason: sig.reason,
    /* El hash de LA FAMILIA, no el global: el servidor compara por familia y
       mandarle el global es comparar dos ámbitos distintos -> 409 inmediato. */
    family_state_hash: GOV?.family_state_hashes?.[family],
    ...extra,
  });
  if(!prop.ok){ toast(explicaError(prop.status, prop.data)); return; }

  /* Los tokens SALEN de la respuesta del propose, que es la autoridad: es el
     acto que cambió el estado, así que es el único que puede describir el
     estado posterior. Si alguno falta, se aborta ANTES de firmar en vez de
     mandar `undefined` -- ese envío silencioso produjo un 409 "falta
     state_hash" que mandó a recargar durante una sesión entera. */
  const iid = prop.data.proposal_id || prop.data.decision_instance_id;
  const fh  = prop.data.family_state_hash ?? prop.data.state_hash;
  if(!iid || !fh){
    toast('El servidor no devolvió los tokens de firma (proposal_id/'
        + 'family_state_hash). No se firma a ciegas. Propuesta: ' + (iid||'?'));
    return;
  }
  if(prop.data.reused_existing_proposal){
    toast(`Se reutiliza la propuesta ${iid} en vez de crear otra.`);
  }
  const conf = await postJSON(`/api/v1/layer9/governance/decisions/${iid}/confirm`, {
    approved_by_id: sig.id, approved_by_display_name: sig.name || sig.id,
    reason: sig.reason,
    family_state_hash: fh,
    expected_active_instance_id: prop.data.expected_active_instance_id ?? null,
  });
  if(!conf.ok){
    toast(explicaError(conf.status, conf.data) +
          ` La propuesta ${iid} queda registrada y sin confirmar.`);
    return;
  }
  toast(`Registrada ${conf.data.decision_instance_id}. No se ejecutó ningún efecto.`);
  govRefresh();
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
    toast('No hay ninguna D1 vigente que corregir. Recarga el estado.');
    return;
  }
  await proponerYConfirmar('D1', ids, readSignature('d1c'),
                           {decision_type:'CORRECTION',
                            supersedes_instance_id: supersede});
}

export async function govSubmitD1A(){
  await proponerYConfirmar('D1', [PART211], readSignature('d1a'),
                           {decision_type:'ADDENDUM', amendment_sequence:1});
}

export async function govSubmitExcepcion(verdict){
  const sig = readSignature('gexc');
  if(!sig.reason){ toast('El motivo es obligatorio.'); return; }
  if(!sig.id){ toast('La firma exige un identificador real.'); return; }
  const forks = GOV?.audit?.unbacked_known_fork_entry_ids || [];
  if(!forks.length){ toast('No hay ningún fork pendiente de excepción.'); return; }

  const prop = await postJSON('/api/v1/layer9/governance/decisions/AUDIT_EXCEPTION/propose', {
    target_ids: forks, proposed_by_id:'mission_control_ui', reason: sig.reason,
    state_hash: GOV?.state_hash,
  });
  if(!prop.ok){ toast(explicaError(prop.status, prop.data)); return; }

  /* Mismos tokens autoritativos que en `proponerYConfirmar`: los del propose,
     nunca los del GET, y se aborta si no llegan. Este panel arrastraba el
     defecto idéntico. */
  const iid = prop.data.proposal_id || prop.data.decision_instance_id;
  const fh  = prop.data.family_state_hash ?? prop.data.state_hash;
  if(!iid || !fh){
    toast('El servidor no devolvió los tokens de firma. No se firma a ciegas.');
    return;
  }
  const url = verdict==='APPROVE'
    ? `/api/v1/layer9/governance/decisions/${iid}/confirm`
    : `/api/v1/layer9/governance/decisions/${iid}/reject`;
  const body = verdict==='APPROVE'
    ? {approved_by_id:sig.id, approved_by_display_name:sig.name||sig.id,
       reason:sig.reason, family_state_hash:fh,
       expected_active_instance_id: prop.data.expected_active_instance_id ?? null}
    : {rejected_by_id:sig.id, rejected_by_display_name:sig.name||sig.id,
       reason:sig.reason, state_hash:fh};

  const res = await postJSON(url, body);
  if(!res.ok){ toast(explicaError(res.status, res.data)); return; }
  toast(verdict==='APPROVE'
    ? 'Excepción aceptada. CHAIN_CONTINUITY pasa a ACCEPTED_WITH_DOCUMENTED_EXCEPTION — nunca a VERIFIED.'
    : 'Excepción rechazada. PART11_COMPLIANCE permanece NOT_DETERMINED: es un final legítimo.');
  govRefresh();
}

export async function govRefresh(){
  const { refresh } = await import('./refresh.js');
  refresh('gobierno');
}
