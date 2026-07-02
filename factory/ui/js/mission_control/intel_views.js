/* W6 — Vistas de Inteligencia en MODO DISEÑO (read-only):
   Tareas operativas de agentes · Fuentes regulatorias · Memoria de casos.
   Consumen los endpoints de diseño /layer9/{agent-tasks,regulatory-sources,
   case-memory}; nada aquí ejecuta tareas ni sale a internet. */

import { state, API_BASE, headers } from './state.js';
import { _gmpEscHtml } from './core.js';

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
  el.innerHTML = sources.map(s => `
    <div class="card" style="margin-bottom:10px">
      <div class="between">
        <div><b>${_gmpEscHtml(s.name)}</b>
          <div class="meta mono">${_gmpEscHtml(s.source_id)} · autoridad: ${_gmpEscHtml(s.authority)}</div></div>
        <span class="chip c-mute">${_gmpEscHtml(s.status || 'not_connected')}</span>
      </div>
      <div class="meta" style="margin-top:8px;line-height:1.9">
        ${s.url ? '<span class="mono" style="font-size:11px">' + _gmpEscHtml(s.url) + '</span><br>' : ''}
        acceso: ${_gmpEscHtml(s.access_design || '—')}<br>
        rate limit: ${_gmpEscHtml(s.rate_limit_design || '—')} · última consulta: ${s.last_checked ? _gmpEscHtml(s.last_checked) : 'nunca'}
      </div>
      <div class="actions" style="margin-top:10px">
        <button class="btn ghost" disabled title="Los conectores requieren aprobación (fase futura)">Conectar</button>
      </div>
    </div>`).join('');
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
  el.innerHTML = cases.map(c => `
    <div class="card" style="margin-bottom:10px">
      <div class="between">
        <b class="mono">${_gmpEscHtml(c.case_id || '—')}</b>
        <span class="chip c-info">${_gmpEscHtml(c.case_type || '—')}</span>
      </div>
      <div class="meta" style="margin-top:6px;line-height:1.8">${_gmpEscHtml(c.summary || '')}</div>
      <div class="meta mono" style="margin-top:6px;font-size:11px;color:var(--faint)">
        ${_gmpEscHtml(c.authority || '—')} · ${_gmpEscHtml(c.url || '')} · consultado: ${_gmpEscHtml(c.consulted_at || '—')}
      </div>
    </div>`).join('');
}

export async function doCaseSearch(){
  const q = document.getElementById('memory-q')?.value?.trim() || '';
  if(!state.connected || !q) return;
  try{
    const r = await fetch(API_BASE + '/api/v1/layer9/case-memory/search?q=' + encodeURIComponent(q), {headers: headers()});
    if(r.ok){ const d = await r.json(); renderCaseResults(d.results || [], 'Sin resultados para "' + q + '" (la memoria está vacía en W6).'); }
  }catch(e){ /* mantiene estado actual */ }
}
