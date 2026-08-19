/* W6 — Vistas de Inteligencia: Tareas operativas de agentes (diseño) ·
   Fuentes regulatorias · Memoria de casos.
   W6.3 — fase online controlada: la fuente `connected` (openFDA) expone un
   formulario de consulta limitada y cada caso permite selective fetch. Ambas
   acciones exigen nombre real, van rate-limited en el backend y se auditan.
   W7 Fase C — "Analizar con agente" es FLUJO REAL: form INLINE (sin
   window.prompt — hallazgo UX de Fase 0: los diálogos nativos son
   suprimibles y descartaban la solicitud en silencio), gobierno completo,
   claims coloreadas por el verificador y decisión humana con motivo. El
   análisis es informativo: jamás toca dossier ni cases.jsonl. */

import { state, API_BASE, headers } from './state.js';
import { toast, _gmpEscHtml } from './core.js';
import { _claimsBar, _renderResponse, _CONF_CHIP } from './validation_view.js';

const _RESERVED_RUN_BY=['human','agent','system','admin','user','factory'];

const AUTONOMY = {
  A: 'reactivo', B: 'programado read-only', C: 'programado + evidencia',
  D: 'programado + alerta QA/QC', E: 'requiere aprobación humana', F: 'prohibido automatizar',
};

/* ---- Tareas operativas ---- */
export function renderAgentTasks(d){
  const el = document.getElementById('tasks-list'); if(!el) return;
  const tasks = d.tasks || [];
  if(!tasks.length){
    el.innerHTML = '<div class="card"><div class="meta">Sin especificaciones de tarea. Se definen en <span class="mono">factory/agent_tasks/tasks.yaml</span>.</div></div>';
    return;
  }
  el.innerHTML = tasks.map(t => `
    <div class="card" style="margin-bottom:10px">
      <div class="between">
        <div><b class="mono">${_gmpEscHtml(t.task_id)}</b>
          <div class="meta">agente: <b class="mono">${_gmpEscHtml(t.agent_id)}</b> · tipo: ${_gmpEscHtml(t.task_type || '—')}</div></div>
        <span class="chip c-warn">${_gmpEscHtml(t.status || 'draft_design')}</span>
      </div>
      <div class="hr"></div>
      <div class="meta" style="line-height:1.8">${_gmpEscHtml(t.objective || '')}</div>
      <div class="meta mono" style="margin-top:8px;line-height:2;font-size:11px">
        autonomía &nbsp; ${_gmpEscHtml(t.autonomy_level || '—')} — ${_gmpEscHtml(AUTONOMY[t.autonomy_level] || '')}<br>
        fuente &nbsp;&nbsp;&nbsp;&nbsp; ${_gmpEscHtml(t.source || '—')} · acceso ${_gmpEscHtml(t.access_mode || '—')}<br>
        límites &nbsp;&nbsp;&nbsp; ${t.limits ? _gmpEscHtml(`${t.limits.max_runtime_s}s · ${t.limits.max_items} items · ${t.limits.max_external_requests} req ext`) : '—'}<br>
        ollama &nbsp;&nbsp;&nbsp;&nbsp; ${t.ollama?.allowed ? _gmpEscHtml('sí · ' + (t.ollama.purpose || '')) : 'no'}<br>
        responsable &nbsp;${_gmpEscHtml(t.human_owner || '—')} · auditada: ${t.audit ? 'sí' : 'no'}
      </div>
      <div class="actions" style="margin-top:10px">
        <button class="btn ghost" disabled title="Requiere ejecutor aprobado (fase futura)">Activar</button>
        <button class="btn ghost" disabled title="Requiere ejecutor aprobado (fase futura)">Pausar</button>
      </div>
    </div>`).join('');
}

/* ---- Fuentes regulatorias ---- */
export function renderRegSources(d){
  const el = document.getElementById('sources-list'); if(!el) return;
  const sources = d.sources || [];
  if(!sources.length){
    el.innerHTML = '<div class="card"><div class="meta">Sin fuentes registradas.</div></div>';
    return;
  }
  el.innerHTML = sources.map(s => {
    const connected = s.status === 'connected';
    const quota = s.quota || {};
    return `
    <div class="card" style="margin-bottom:10px">
      <div class="between">
        <div><b>${_gmpEscHtml(s.name)}</b>
          <div class="meta mono">${_gmpEscHtml(s.source_id)} · autoridad: ${_gmpEscHtml(s.authority)}</div></div>
        <span class="chip ${connected ? 'c-pass' : 'c-mute'}">${_gmpEscHtml(s.status || 'not_connected')}</span>
      </div>
      <div class="meta" style="margin-top:8px;line-height:1.9">
        ${s.url ? '<span class="mono" style="font-size:11px">' + _gmpEscHtml(s.url) + '</span><br>' : ''}
        acceso: ${_gmpEscHtml(s.access_design || '—')}<br>
        rate limit: ${_gmpEscHtml(s.rate_limit_design || '—')} · última consulta: ${s.last_checked ? _gmpEscHtml(s.last_checked) : 'nunca'}
        ${connected ? '<br>cupo hoy: <b>' + (quota.calls_today ?? 0) + ' / ' + (quota.max_calls_per_day ?? '—') + '</b> llamadas online' : ''}
      </div>
      ${connected ? `
      <div class="hr"></div>
      <div class="meta" style="font-size:10.5px;color:var(--faint);margin-bottom:8px">
        Consulta ONLINE real (auditada, nombre real obligatorio). Guarda solo memoria
        ligera: pointer + metadata + resumen + hash — nunca el documento completo.</div>
      <div style="display:flex;gap:8px">
        <input id="regq-term" placeholder='término en reason_for_recall, p.ej. sterility' autocomplete="off"
          style="flex:1;background:var(--panel-2);border:1px solid var(--line);color:var(--text);border-radius:6px;padding:7px 10px;font-size:12.5px">
        <select id="regq-limit" class="mc-select" style="width:90px">
          <option value="3">3</option><option value="5" selected>5</option><option value="10">10</option>
        </select>
        <button class="btn ghost" onclick="submitRegQuery()">Consultar (auditado)</button>
      </div>
      <div id="regq-result" style="margin-top:8px"></div>` : `
      <div class="actions" style="margin-top:10px">
        <button class="btn ghost" disabled title="Conectar otra fuente requiere aprobación humana explícita">Conectar</button>
      </div>`}
    </div>`;
  }).join('');
}

export function submitRegQuery(){
  const term=document.getElementById('regq-term')?.value?.trim()||'';
  const limit=parseInt(document.getElementById('regq-limit')?.value||'5',10);
  if(!term){ toast('Escribe un término de búsqueda.'); return; }
  const by=(window.prompt('Nombre real de quien ejecuta esta consulta ONLINE (queda auditada):')||'').trim();
  if(!by){ toast('Consulta cancelada — no se envió nada (sin nombre).'); return; }
  if(_RESERVED_RUN_BY.includes(by.toLowerCase())){ toast('"'+by+'" es un nombre reservado — usa tu nombre real.'); return; }
  _regQuery(term,limit,by);
}

async function _regQuery(term,limit,by){
  const el=document.getElementById('regq-result');
  if(el) el.innerHTML='<div class="meta" style="color:var(--faint)">Consultando openFDA… (máx '+limit+' resultados, timeout 10s)</div>';
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/regulatory/query',{
      method:'POST', headers:headers(), body:JSON.stringify({search_term:term,limit:limit,run_by:by})
    });
    const d=await r.json().catch(()=>({}));
    if(!r.ok){
      if(el) el.innerHTML='<div class="meta" style="color:var(--fail)">Error '+r.status+': '+_gmpEscHtml(typeof d.detail==='object'?JSON.stringify(d.detail):(d.detail||'error'))+'</div>';
      return;
    }
    if(el) el.innerHTML='<div class="meta" style="color:var(--pass)">✓ '+d.results_returned+' resultados · '
      +d.saved+' casos nuevos en memoria · '+d.skipped_existing+' ya existían · cupo '
      +(d.quota?.calls_today??'?')+'/'+(d.quota?.max_calls_per_day??'?')+'</div>';
    toast('openFDA: '+d.saved+' casos nuevos guardados (memoria ligera)');
    window.refresh?.('memory');
  }catch(e){ if(el) el.innerHTML='<div class="meta" style="color:var(--fail)">Error de red: '+_gmpEscHtml(e.message)+'</div>'; }
}

/* ---- Memoria de casos (W6.4: interpretación primero, evidencia después) ----
   Cada tarjeta muestra 4 bloques: interpretación (resumen ejecutivo +
   relevancia + agente recomendado, todo determinista — NO juicio GMP),
   gobierno (estado del detalle), trazabilidad (fuente/query/hash/cita) y
   evidencia técnica colapsable. Los casos renderizados viven en _lastCases
   para que los handlers referencien por índice (case_id lleva ':' y comillas). */

let _lastCases = [];

const _REL_CHIP = { alta: 'c-fail', media: 'c-warn', baja: 'c-mute' };

export function renderCaseMemory(d){
  const cnt = document.getElementById('memory-count');
  if(cnt) cnt.textContent = (d.count ?? 0) + ' casos';
  renderCaseResults(d.cases || [], d.note);
}

function _detailStateHtml(p){
  const ds = p?.detail_status || {};
  if(ds.state === 'detail_fetched_not_persisted'){
    return '<span style="color:var(--warn)">●</span> detalle recuperado ' + (ds.fetch_count||0)
      + (ds.fetch_count===1?' vez':' veces') + ' — <b>no persistido</b> (último: '
      + _gmpEscHtml(ds.last_fetched_at||'—') + ')';
  }
  return '<span style="color:var(--pass)">●</span> memoria ligera solamente (pointer + metadata + resumen + hash)';
}

export function renderCaseResults(cases, note){
  const el = document.getElementById('memory-results'); if(!el) return;
  _lastCases = cases || [];
  if(!cases.length){
    el.innerHTML = '<div class="card"><div class="meta">' + _gmpEscHtml(note || 'Sin resultados para esta búsqueda.') + '</div></div>';
    return;
  }
  el.innerHTML = cases.map((c, i) => {
    const p = c.presentation || {};
    const rel = p.gmp_relevance || {};
    const rec = p.recommended_agent || {};
    return `
    <div class="card" style="margin-bottom:12px">
      <!-- INTERPRETACIÓN -->
      <div style="font-size:13px;line-height:1.75;margin-bottom:8px">${_gmpEscHtml(p.executive_summary || c.summary || '')}</div>
      <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
        <span class="chip ${_REL_CHIP[rel.level] || 'c-mute'}">${_gmpEscHtml(c.classification || 'sin clasificación')}</span>
        <span class="chip ${_REL_CHIP[rel.level] || 'c-mute'}">relevancia GMP: ${_gmpEscHtml(rel.level || 'sin clasificar')}</span>
        <span class="chip c-info">${_gmpEscHtml(c.case_type || '—')}</span>
        ${(c.tags||[]).map(t=>'<span class="chip c-warn" style="font-size:9px">'+_gmpEscHtml(t)+'</span>').join('')}
      </div>
      <div class="meta" style="font-size:10px;color:var(--faint);margin-top:6px">
        ⚠ clasificación determinista de presentación — NO es juicio GMP · requiere revisión humana QA/QC</div>
      <div class="meta" style="margin-top:8px;line-height:1.7">
        Agente recomendado: <b class="mono">${_gmpEscHtml(rec.agent_id || '—')}</b><br>
        <span style="color:var(--faint);font-size:11px">${_gmpEscHtml(rec.reason || '')}</span></div>
      <div class="hr"></div>
      <!-- GOBIERNO -->
      <div class="meta" style="font-size:11px" id="case-state-${i}">${_detailStateHtml(p)}</div>
      <div class="meta" style="font-size:10px;color:var(--faint)">snapshot persistido: no disponible — requiere aprobación futura</div>
      <!-- TRAZABILIDAD -->
      <div class="meta mono" style="margin-top:8px;font-size:10.5px;line-height:2;color:var(--faint);overflow-wrap:anywhere">
        fuente &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ${_gmpEscHtml(c.authority||'—')} · ${_gmpEscHtml(c.source_id||'—')}<br>
        endpoint &nbsp;&nbsp;&nbsp; ${_gmpEscHtml(c.url||'—')}<br>
        query &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ${p.found_by_query ? '«'+_gmpEscHtml(p.found_by_query)+'»' : 'no registrada (caso pre-W6.4)'}<br>
        consultado &nbsp; ${_gmpEscHtml(c.consulted_at||'—')}<br>
        hash &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ${_gmpEscHtml(c.content_hash||'—')}</div>
      <div style="display:flex;gap:8px;align-items:flex-start;margin-top:6px">
        <div class="meta" style="flex:1;font-size:10px;color:var(--faint);font-style:italic;line-height:1.7">${_gmpEscHtml(p.citation||'')}</div>
        <button class="btn ghost" style="font-size:10px;padding:2px 8px;white-space:nowrap"
          onclick="copyCaseCitation(${i})">Copiar cita</button>
      </div>
      <!-- ACCIONES -->
      ${c.case_id ? `<div class="actions" style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn ghost" style="font-size:10px;padding:2px 8px"
          onclick="promptCaseFetch('${_gmpEscHtml(c.case_id)}', ${i})">Recuperar detalle (fetch selectivo, auditado)</button>
        <button class="btn ghost" style="font-size:10px;padding:2px 8px"
          onclick="toggleCaseAnalysis(${i})">Analizar con agente (real, auditado)</button>
        <button class="btn ghost" style="font-size:10px;padding:2px 8px"
          onclick="promptCaseCompare(${i})">Comparar con misión</button>
      </div>
      <div id="case-detail-${i}"></div>
      <div id="case-analyze-${i}"></div>
      <div id="case-compare-${i}"></div>` : ''}
      <!-- EVIDENCIA TÉCNICA -->
      <details style="margin-top:10px">
        <summary class="meta" style="cursor:pointer;font-size:11px">Evidencia técnica (JSON del case record)</summary>
        <pre style="background:var(--panel-2);border:1px solid var(--line);border-radius:6px;padding:10px;
          font-size:10.5px;max-height:280px;overflow:auto;white-space:pre-wrap;margin-top:6px">${_gmpEscHtml(JSON.stringify(c,null,2))}</pre>
      </details>
    </div>`;
  }).join('');
}

/* Cita trazable al portapapeles (con fallback para contexto no seguro) */
export function copyCaseCitation(i){
  const cit = _lastCases[i]?.presentation?.citation || '';
  if(!cit){ toast('Sin cita disponible para este caso.'); return; }
  const done = ()=>toast('Cita copiada al portapapeles.');
  if(navigator.clipboard?.writeText){ navigator.clipboard.writeText(cit).then(done).catch(()=>_copyFallback(cit,done)); }
  else _copyFallback(cit,done);
}
function _copyFallback(text,done){
  const ta=document.createElement('textarea'); ta.value=text; document.body.appendChild(ta);
  ta.select(); try{ document.execCommand('copy'); done(); }catch(e){ toast('No se pudo copiar.'); }
  ta.remove();
}

/* ---- W7 Fase C — "Analizar con agente": FLUJO REAL gobernado ----
   Form INLINE (nombre real + instrucción opcional): sin window.prompt, con
   feedback SIEMPRE — nada se descarta en silencio (hallazgo UX de Fase 0).
   El POST puede tardar ~7–9 min (qwen en CPU): spinner con cronómetro y
   botón de recarga por si la conexión se corta antes de la respuesta. */

const _ANALYSIS_URL=(caseId)=>API_BASE+'/api/v1/layer9/case-memory/'
  +encodeURIComponent(caseId)+'/analysis';

const _AN_ST={agent_analysis_proposed:['c-accent','propuesto — decisión pendiente'],
  accepted:['c-pass','aceptado'], rejected:['c-fail','rechazado'],
  changes_requested:['c-warn','ajuste pedido'], format_invalid:['c-fail','formato inválido']};

export async function toggleCaseAnalysis(i){
  const el=document.getElementById('case-analyze-'+i); if(!el) return;
  if(el.innerHTML){ el.innerHTML=''; return; }
  const c=_lastCases[i]||{}; const rec=c.presentation?.recommended_agent||{};
  el.innerHTML='<div class="meta" style="color:var(--faint);margin-top:8px">Cargando misiones…</div>';
  let missions=[];
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions',{headers:headers()});
    if(r.ok){ const d=await r.json(); missions=d.missions||d||[]; }
  }catch(e){ /* sin misiones: se informa abajo */ }
  const ids=(Array.isArray(missions)?missions:[]).map(m=>m.project_id).filter(Boolean);
  if(!ids.length){ el.innerHTML='<div class="meta" style="color:var(--fail);margin-top:8px">Sin misiones disponibles para analizar.</div>'; return; }
  const def=ids.includes(state.selectedMissionId)?state.selectedMissionId:(ids.includes('oos_hplc_investigator')?'oos_hplc_investigator':ids[0]);
  el.innerHTML=`
    <div style="border:1px solid var(--accent);border-radius:6px;padding:10px;margin-top:8px">
      <div class="meta" style="font-size:10.5px;color:var(--faint);margin-bottom:6px">
        Análisis REAL por agente (Ollama local, auditado). Agente por routing determinista:
        <b class="mono">${_gmpEscHtml(rec.agent_id||'—')}</b>. El resultado es INFORMATIVO:
        no es evaluación de impacto GMP ni toca el dossier — el humano decide.</div>
      <div style="display:flex;gap:8px;margin-bottom:8px">
        <select id="case-an-pid-${i}" class="mc-select" style="flex:1" onchange="loadCaseAnalysis(${i})">
          ${ids.map(id=>'<option value="'+_gmpEscHtml(id)+'"'+(id===def?' selected':'')+'>'+_gmpEscHtml(id)+'</option>').join('')}
        </select>
        <button class="btn ghost" style="font-size:10px" onclick="loadCaseAnalysis(${i})">Recargar análisis</button>
      </div>
      <div style="display:flex;gap:8px;margin-bottom:8px">
        <input id="case-an-by-${i}" placeholder="Nombre real (queda auditado)" autocomplete="off"
          style="width:220px;background:var(--panel-2);border:1px solid var(--line);color:var(--text);border-radius:6px;padding:7px 10px;font-size:12px">
        <input id="case-an-guidance-${i}" placeholder="Instrucción opcional al agente — 1 acción por instrucción (calibración 7B)" autocomplete="off"
          style="flex:1;background:var(--panel-2);border:1px solid var(--line);color:var(--text);border-radius:6px;padding:7px 10px;font-size:12px">
        <button class="btn ghost" id="case-an-run-${i}" style="font-size:10px;white-space:nowrap"
          onclick="runCaseAnalysis(${i})">Solicitar análisis (~7–9 min)</button>
      </div>
      <div id="case-an-out-${i}"></div>
    </div>`;
  loadCaseAnalysis(i);
}

export function runCaseAnalysis(i){
  const c=_lastCases[i]||{};
  const pid=document.getElementById('case-an-pid-'+i)?.value;
  const by=(document.getElementById('case-an-by-'+i)?.value||'').trim();
  const guidance=(document.getElementById('case-an-guidance-'+i)?.value||'').trim();
  if(!c.case_id||!pid){ toast('Selecciona una misión primero.'); return; }
  if(!by){ toast('Solicitud NO enviada: falta el nombre real (queda auditado).'); return; }
  if(_RESERVED_RUN_BY.includes(by.toLowerCase())){ toast('"'+by+'" es un nombre reservado — usa tu nombre real.'); return; }
  _runAnalysis(i, c.case_id, pid, by, guidance||null);
}

async function _runAnalysis(i, caseId, pid, by, guidance){
  const out=document.getElementById('case-an-out-'+i);
  const btn=document.getElementById('case-an-run-'+i);
  if(btn) btn.disabled=true;
  const t0=Date.now();
  const timer=setInterval(()=>{
    const s=Math.round((Date.now()-t0)/1000);
    const sp=document.getElementById('case-an-wait-'+i);
    if(sp) sp.textContent=Math.floor(s/60)+'m '+(s%60)+'s';
  },1000);
  if(out) out.innerHTML='<div class="meta" style="color:var(--warn);margin-top:6px">⏳ El agente está '
    +'redactando el análisis (Ollama en CPU, ~7–9 min)… <span id="case-an-wait-'+i+'" class="mono">0m 0s</span>'
    +' — si la conexión se corta, usa "Recargar análisis": la generación sigue en el servidor.</div>';
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/case-memory/'+encodeURIComponent(caseId)+'/analyze',{
      method:'POST', headers:headers(),
      body:JSON.stringify({project_id:pid, requested_by:by, guidance:guidance})
    });
    const d=await r.json().catch(()=>({}));
    if(!r.ok){
      if(out) out.innerHTML='<div class="meta" style="color:var(--fail);margin-top:6px">Error '+r.status+': '
        +_gmpEscHtml(typeof d.detail==='object'?JSON.stringify(d.detail):(d.detail||'error'))+'</div>';
      return;
    }
    if(d.status==='format_invalid'){
      toast('⚠ El análisis v'+d.version+' no cumplió el contrato de formato — archivado; nada cambió.');
    }else{
      toast('Análisis v'+d.version+' generado · confianza '+(d.confidence||'—')
        +((d.flags||[]).length?' · ⚠ flags: '+d.flags.join(', '):''));
    }
    loadCaseAnalysis(i);
  }catch(e){
    if(out) out.innerHTML='<div class="meta" style="color:var(--fail);margin-top:6px">Error de red: '
      +_gmpEscHtml(e.message)+' — la generación puede seguir en el servidor; usa "Recargar análisis" en unos minutos.</div>';
  }finally{ clearInterval(timer); if(btn) btn.disabled=false; }
}

export async function loadCaseAnalysis(i){
  const c=_lastCases[i]||{};
  const pid=document.getElementById('case-an-pid-'+i)?.value;
  const out=document.getElementById('case-an-out-'+i);
  if(!c.case_id||!pid||!out) return;
  out.innerHTML='<div class="meta" style="color:var(--faint);margin-top:6px">Buscando análisis existente…</div>';
  try{
    const r=await fetch(_ANALYSIS_URL(c.case_id)+'?project_id='+encodeURIComponent(pid),{headers:headers()});
    const d=await r.json().catch(()=>({}));
    if(r.status===404){
      out.innerHTML='<div class="meta" style="color:var(--faint);margin-top:6px">Sin análisis para esta misión todavía — solicita el primero.</div>';
      return;
    }
    if(!r.ok){
      out.innerHTML='<div class="meta" style="color:var(--fail);margin-top:6px">Error '+r.status+': '
        +_gmpEscHtml(typeof d.detail==='object'?JSON.stringify(d.detail):(d.detail||'error'))+'</div>';
      return;
    }
    _renderCaseAnalysis(i, d);
  }catch(e){ out.innerHTML='<div class="meta" style="color:var(--fail);margin-top:6px">Error de red: '+_gmpEscHtml(e.message)+'</div>'; }
}

function _renderCaseAnalysis(i, d){
  const out=document.getElementById('case-an-out-'+i); if(!out) return;
  const ag=d.agent||{}, mo=d.model||{}, pr=d.prompt||{}, co=d.corpus_sufficiency||{},
        cl=d.claims||{}, gov=d.governance||{}, dec=d.decision, rev=d.revision||{},
        ref=d.case_ref||{};
  const flags=(d.flags||[]);
  const [stChip,stLabel]=_AN_ST[d.status]||['c-mute',d.status||'—'];
  const decidable=d.status==='agent_analysis_proposed' && !dec;
  out.innerHTML=`<div class="card" style="border-color:var(--accent);margin-top:8px">
    <div class="between" style="margin-bottom:8px">
      <b style="font-size:12.5px">Análisis de caso · <span class="mono">${_gmpEscHtml(d.case_id||'')}</span>
        <span class="chip ${stChip}" style="margin-left:6px">v${_gmpEscHtml(String(d.version))} · ${_gmpEscHtml(stLabel)}</span>
        <span class="chip ${_CONF_CHIP[d.confidence]||'c-mute'}" style="margin-left:4px">confianza ${_gmpEscHtml(d.confidence||'—')} (computada)</span></b>
    </div>
    <div class="banner warn" style="margin-bottom:10px"><span>⚠</span><div>${_gmpEscHtml(d.regulatory_note||'ANÁLISIS PROPUESTO POR AGENTE — informativo, sin valor regulatorio.')}</div></div>
    <div class="meta" style="font-size:10px;color:var(--faint);margin-bottom:4px">
      agente: <b>${_gmpEscHtml(ag.primary||'—')}</b> (routing determinista W6.4)
      ${(ag.supporting||[]).length?' · revisión recomendada: '+_gmpEscHtml(ag.supporting.join(', ')):''}
      · modelo <span class="mono">${_gmpEscHtml(mo.name||'—')}</span>
      (temp ${_gmpEscHtml(String((mo.options||{}).temperature ?? '—'))}, modo ${_gmpEscHtml(rev.mode||'draft')})</div>
    <div class="meta" style="font-size:10px;color:var(--faint);margin-bottom:4px">
      prompt set ${_gmpEscHtml(pr.set_version||'—')} · prompt agente v${_gmpEscHtml(pr.agent_prompt_version||'—')}
      · template <span class="mono">${_gmpEscHtml((pr.template_sha256||'').slice(0,12))}…</span>
      · rendered <span class="mono">${_gmpEscHtml((pr.rendered_sha256||'').slice(0,12))}…</span></div>
    <div class="meta" style="font-size:10px;color:var(--faint);margin-bottom:4px">
      corpus: <b>${_gmpEscHtml(co.level||'—')}</b> · evidencia: ${_gmpEscHtml((d.evidence_sources||[]).map(s=>s.id).join(', '))}
      · caso: hash <span class="mono">${_gmpEscHtml((ref.content_hash||'').slice(0,19))}…</span>${ref.stale?' · <span style="color:var(--warn)">⚠ caso stale (>30 días)</span>':''}</div>
    <div class="meta" style="font-size:10px;margin-bottom:4px">afirmaciones: ${_claimsBar(cl)}</div>
    ${flags.length?'<div class="meta" style="font-size:10px;margin-bottom:4px">'+flags.map(f=>'<span class="chip c-fail" style="margin-right:4px">⚠ '+_gmpEscHtml(f)+'</span>').join('')+'</div>':''}
    <div class="meta" style="font-size:10px;color:var(--faint);margin-bottom:8px">
      solicitado por <span style="color:var(--human)">${_gmpEscHtml(gov.requested_by||'—')}</span>
      · ${_gmpEscHtml(gov.generated_at||'—')} · ${_gmpEscHtml(String(gov.latency_ms??'—'))} ms
      ${gov.format_retry?' · reintento de formato':''}
      ${(rev.guidance_ledger||[]).length?' · instrucciones QA acumuladas: '+rev.guidance_ledger.length:''}</div>
    ${dec?'<div class="meta" style="font-size:10px;color:var(--human);margin-bottom:8px">decisión: <b>'+_gmpEscHtml(dec.decision||'')+'</b> por '+_gmpEscHtml(dec.decided_by||'')+' · '+_gmpEscHtml(dec.decided_at||'')+(dec.reason?' · motivo: “'+_gmpEscHtml(dec.reason)+'”':'')+'</div>':''}
    <pre style="background:var(--panel-2);border:1px solid var(--line);border-radius:8px;padding:12px;
      font-size:11px;max-height:420px;overflow:auto;white-space:pre-wrap">${_renderResponse(d.response, cl.detail)}</pre>
    ${decidable?`
    <div class="meta" style="font-size:10px;color:var(--faint);margin-top:10px">
      Decisión humana (auditada — NO es aprobación de dossier ni firma electrónica). Usa el
      nombre real del formulario superior; reject/ajuste exigen motivo. Calibración 7B:
      1 acción por instrucción y pide eliminar viñetas compañeras contradictorias.</div>
    <div style="display:flex;gap:8px;margin-top:6px;align-items:center">
      <input id="case-an-reason-${i}" placeholder="Motivo (obligatorio para rechazar / pedir ajuste)" autocomplete="off"
        style="flex:1;background:var(--panel-2);border:1px solid var(--line);color:var(--text);border-radius:6px;padding:7px 10px;font-size:12px">
      <button class="btn human" style="font-size:10px;padding:3px 10px" onclick="decideCaseAnalysis(${i},'accept')">Aceptar (solo registro)</button>
      <button class="btn ghost" style="font-size:10px;padding:3px 10px;color:var(--fail)" onclick="decideCaseAnalysis(${i},'reject')">Rechazar</button>
      <button class="btn ghost" style="font-size:10px;padding:3px 10px" onclick="decideCaseAnalysis(${i},'request_changes')">Pedir ajuste (regenera, ~7–9 min)</button>
    </div>`:''}
  </div>`;
}

/* decided_by ya NO viaja en el body de /decision (Paquete 2, hallazgo M)
   -- el backend lo resuelve desde X-Identity-Key. El input "case-an-by"
   sigue existiendo para requested_by (runCaseAnalysis, no migrado). */
export function decideCaseAnalysis(i, decision){
  const c=_lastCases[i]||{};
  const pid=document.getElementById('case-an-pid-'+i)?.value;
  const reason=(document.getElementById('case-an-reason-'+i)?.value||'').trim();
  if(!c.case_id||!pid) return;
  if(decision!=='accept' && !reason){ toast('Decisión NO enviada: el motivo es obligatorio para '+decision+'.'); return; }
  _decideAnalysis(i, c.case_id, pid, decision, decision==='accept'?(reason||null):reason);
}

async function _decideAnalysis(i, caseId, pid, decision, reason){
  const out=document.getElementById('case-an-out-'+i);
  if(decision==='request_changes' && out){
    out.insertAdjacentHTML('afterbegin','<div class="meta" style="color:var(--warn)">⏳ Registrando decisión y regenerando en modo revisión (~7–9 min)…</div>');
  }
  try{
    const r=await fetch(_ANALYSIS_URL(caseId)+'/decision',{
      method:'POST', headers:headers(),
      body:JSON.stringify({project_id:pid, decision:decision, reason:reason})
    });
    const d=await r.json().catch(()=>({}));
    if(!r.ok){ toast('Error '+r.status+': '+(typeof d.detail==='object'?JSON.stringify(d.detail):(d.detail||'error'))); loadCaseAnalysis(i); return; }
    toast('✓ '+decision+' registrado · análisis → '+(d.analysis_status||'—')
      +(d.new_analysis?' · nueva versión v'+d.new_analysis.version:''));
    loadCaseAnalysis(i);
  }catch(e){
    toast('Error de red: '+e.message+' — usa "Recargar análisis": la decisión/regeneración puede haber quedado registrada.');
    loadCaseAnalysis(i);
  }
}

/* "Comparar con misión" — READ-ONLY real: cruce informativo de datos locales
   (tags vs alcance, agente recomendado vs agentes diseñados, pruebas, dossier).
   Jamás decide ni escribe — el veredicto es de QA/QC humano. */
export async function promptCaseCompare(i){
  const el=document.getElementById('case-compare-'+i); if(!el) return;
  if(el.innerHTML){ el.innerHTML=''; return; }
  el.innerHTML='<div class="meta" style="color:var(--faint);margin-top:8px">Cargando misiones…</div>';
  let missions=[];
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions',{headers:headers()});
    if(r.ok){ const d=await r.json(); missions=d.missions||d||[]; }
  }catch(e){ /* sin misiones: se informa abajo */ }
  const ids=(Array.isArray(missions)?missions:[]).map(m=>m.project_id).filter(Boolean);
  if(!ids.length){ el.innerHTML='<div class="meta" style="color:var(--fail);margin-top:8px">Sin misiones disponibles para comparar.</div>'; return; }
  const def=ids.includes(state.selectedMissionId)?state.selectedMissionId:(ids.includes('oos_hplc_investigator')?'oos_hplc_investigator':ids[0]);
  el.innerHTML=`
    <div style="border:1px solid var(--line);border-radius:6px;padding:10px;margin-top:8px">
      <div class="meta" style="font-size:10.5px;color:var(--faint);margin-bottom:6px">
        Comparación INFORMATIVA (read-only, sin auditar): cruza tags GMP, agentes, pruebas y dossier locales. No es decisión GMP.</div>
      <div style="display:flex;gap:8px">
        <select id="case-compare-sel-${i}" class="mc-select" style="flex:1">
          ${ids.map(id=>'<option value="'+_gmpEscHtml(id)+'"'+(id===def?' selected':'')+'>'+_gmpEscHtml(id)+'</option>').join('')}
        </select>
        <button class="btn ghost" style="font-size:10px" onclick="runCaseCompare(${i})">Comparar</button>
      </div>
      <div id="case-compare-out-${i}"></div>
    </div>`;
}

export async function runCaseCompare(i){
  const c=_lastCases[i]||{}; const pid=document.getElementById('case-compare-sel-'+i)?.value;
  const out=document.getElementById('case-compare-out-'+i);
  if(!c.case_id||!pid||!out) return;
  out.innerHTML='<div class="meta" style="color:var(--faint);margin-top:6px">Comparando…</div>';
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/case-memory/'+encodeURIComponent(c.case_id)
      +'/compare/'+encodeURIComponent(pid),{headers:headers()});
    const d=await r.json().catch(()=>({}));
    if(!r.ok){ out.innerHTML='<div class="meta" style="color:var(--fail);margin-top:6px">Error '+r.status+': '+_gmpEscHtml(d.detail||'error')+'</div>'; return; }
    const ov=d.overlap||{}, m=d.mission||{};
    out.innerHTML=`
      <div class="meta" style="font-size:11px;line-height:2;margin-top:8px">
        <b>Misión:</b> <span class="mono">${_gmpEscHtml(d.project_id)}</span> · ${_gmpEscHtml((m.objective||'').slice(0,140))}…<br>
        <b>Tags del caso presentes en la misión:</b> ${(ov.matched_tags||[]).length
          ? ov.matched_tags.map(t=>'<span class="chip c-pass" style="font-size:9px">'+_gmpEscHtml(t)+'</span>').join(' ')
          : '<span style="color:var(--faint)">ninguno</span>'}<br>
        <b>Tags sin coincidencia:</b> ${(ov.unmatched_tags||[]).map(t=>'<span class="chip c-mute" style="font-size:9px">'+_gmpEscHtml(t)+'</span>').join(' ')||'—'}<br>
        <b>Agente recomendado del caso</b> (<span class="mono">${_gmpEscHtml(d.case?.recommended_agent||'—')}</span>):
          ${ov.recommended_agent_in_mission
            ? '<span style="color:var(--pass)">✓ está diseñado en la misión</span> · '+(ov.recommended_agent_tests||0)+' pruebas en catálogo'
            : '<span style="color:var(--warn)">no está entre los agentes de la misión</span>'}<br>
        <b>Agentes de la misión:</b> ${(m.agents||[]).map(a=>'<span class="mono">'+_gmpEscHtml(a)+'</span>').join(', ')||'—'}<br>
        <b>Dossier CSV:</b> ${m.dossier?.exists ? (m.dossier.approved+'/'+m.dossier.total_docs+' documentos aprobados') : 'sin dossier generado'}
      </div>
      <div class="meta" style="font-size:10px;color:var(--faint);margin-top:4px">
        ⚠ informativo — no es análisis GMP ni recomendación de disposición; la evaluación es de QA/QC.</div>`;
  }catch(e){ out.innerHTML='<div class="meta" style="color:var(--fail);margin-top:6px">Error de red: '+_gmpEscHtml(e.message)+'</div>'; }
}

export function promptCaseFetch(caseId, idx){
  const by=(window.prompt('Recuperar detalle de "'+caseId+'" desde la fuente (llamada ONLINE auditada). Nombre real:')||'').trim();
  if(!by){ toast('Recuperación cancelada — no se envió nada (sin nombre).'); return; }
  if(_RESERVED_RUN_BY.includes(by.toLowerCase())){ toast('"'+by+'" es un nombre reservado — usa tu nombre real.'); return; }
  _caseFetch(caseId, idx, by);
}

async function _caseFetch(caseId, idx, by){
  const el=document.getElementById('case-detail-'+idx);
  if(el) el.innerHTML='<div class="meta" style="color:var(--faint)">Recuperando de la fuente…</div>';
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/case-memory/'+encodeURIComponent(caseId)+'/fetch',{
      method:'POST', headers:headers(), body:JSON.stringify({run_by:by})
    });
    const d=await r.json().catch(()=>({}));
    if(!r.ok){
      if(el) el.innerHTML='<div class="meta" style="color:var(--fail)">Error '+r.status+': '+_gmpEscHtml(typeof d.detail==='object'?JSON.stringify(d.detail):(d.detail||'error'))+'</div>';
      return;
    }
    if(el) el.innerHTML=`
      <div class="meta" style="font-size:10px;color:${d.content_changed?'var(--warn)':'var(--pass)'};margin-top:6px">
        ${d.content_changed?'⚠ el contenido en la fuente CAMBIÓ desde la consulta original (hash distinto)':'✓ contenido íntegro (hash coincide con la memoria)'}
        · recuperado: ${_gmpEscHtml(d.fetched_at||'')} · NO persistido</div>
      <details open style="margin-top:4px">
        <summary class="meta" style="cursor:pointer;font-size:11px">Detalle recuperado de la fuente (JSON, no persistido)</summary>
        <pre style="background:var(--panel-2);border:1px solid var(--line);border-radius:6px;padding:10px;
          font-size:10.5px;max-height:320px;overflow:auto;white-space:pre-wrap;margin-top:4px">${_gmpEscHtml(JSON.stringify(d.detail,null,2))}</pre>
      </details>`;
    const st=document.getElementById('case-state-'+idx);
    if(st) st.innerHTML='<span style="color:var(--warn)">●</span> detalle recuperado en esta sesión — <b>no persistido</b> ('+_gmpEscHtml(d.fetched_at||'')+')';
  }catch(e){ if(el) el.innerHTML='<div class="meta" style="color:var(--fail)">Error de red: '+_gmpEscHtml(e.message)+'</div>'; }
}

export async function doCaseSearch(){
  const q = document.getElementById('memory-q')?.value?.trim() || '';
  if(!state.connected || !q) return;
  try{
    const r = await fetch(API_BASE + '/api/v1/layer9/case-memory/search?q=' + encodeURIComponent(q), {headers: headers()});
    if(r.ok){ const d = await r.json(); renderCaseResults(d.results || [], 'Sin resultados para "' + q + '" (la memoria está vacía en W6).'); }
  }catch(e){ /* mantiene estado actual */ }
}
