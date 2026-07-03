/* W6 — Vistas de Inteligencia: Tareas operativas de agentes (diseño) ·
   Fuentes regulatorias · Memoria de casos.
   W6.3 — fase online controlada: la fuente `connected` (openFDA) expone un
   formulario de consulta limitada y cada caso permite selective fetch. Ambas
   acciones exigen nombre real, van rate-limited en el backend y se auditan. */

import { state, API_BASE, headers } from './state.js';
import { toast, _gmpEscHtml } from './core.js';

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
  if(!by) return;
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

/* ---- Memoria de casos ---- */
export function renderCaseMemory(d){
  const cnt = document.getElementById('memory-count');
  if(cnt) cnt.textContent = (d.count ?? 0) + ' casos';
  renderCaseResults(d.cases || [], d.note);
}

export function renderCaseResults(cases, note){
  const el = document.getElementById('memory-results'); if(!el) return;
  if(!cases.length){
    el.innerHTML = '<div class="card"><div class="meta">' + _gmpEscHtml(note || 'Sin resultados para esta búsqueda.') + '</div></div>';
    return;
  }
  el.innerHTML = cases.map((c, i) => `
    <div class="card" style="margin-bottom:10px">
      <div class="between">
        <b class="mono">${_gmpEscHtml(c.case_id || '—')}</b>
        <div style="display:flex;gap:6px;align-items:center">
          ${(c.tags||[]).map(t=>'<span class="chip c-warn" style="font-size:9px">'+_gmpEscHtml(t)+'</span>').join('')}
          <span class="chip c-info">${_gmpEscHtml(c.case_type || '—')}</span>
        </div>
      </div>
      <div class="meta" style="margin-top:6px;line-height:1.8">${_gmpEscHtml(c.summary || '')}</div>
      <div class="meta mono" style="margin-top:6px;font-size:11px;color:var(--faint)">
        ${_gmpEscHtml(c.authority || '—')} · consultado: ${_gmpEscHtml(c.consulted_at || '—')}
        · hash: ${_gmpEscHtml((c.content_hash || '').slice(0, 19))}…
      </div>
      ${c.case_id ? `<div class="actions" style="margin-top:8px">
        <button class="btn ghost" style="font-size:10px;padding:2px 8px"
          onclick="promptCaseFetch('${_gmpEscHtml(c.case_id)}', ${i})">Detalle (fetch selectivo, auditado)</button>
      </div>
      <div id="case-detail-${i}"></div>` : ''}
    </div>`).join('');
}

export function promptCaseFetch(caseId, idx){
  const by=(window.prompt('Recuperar detalle de "'+caseId+'" desde la fuente (llamada ONLINE auditada). Nombre real:')||'').trim();
  if(!by) return;
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
        ${d.content_changed?'⚠ el contenido en la fuente CAMBIÓ desde la consulta original':'✓ contenido íntegro (hash coincide con la memoria)'}
        · recuperado: ${_gmpEscHtml(d.fetched_at||'')} · NO persistido</div>
      <pre style="background:var(--panel-2);border:1px solid var(--line);border-radius:6px;padding:10px;
        font-size:10.5px;max-height:320px;overflow:auto;white-space:pre-wrap;margin-top:4px">${_gmpEscHtml(JSON.stringify(d.detail,null,2))}</pre>`;
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
