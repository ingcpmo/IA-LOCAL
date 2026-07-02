/* W6.1 — Vista Detalle de misión: cadena de trazabilidad
   objetivo → agentes → pruebas → evidencia → release → deployment,
   construida desde /missions/{id}/summary (evidencia real, read-only).
   El detail panel lateral (detail_panel.js) sigue existiendo; esta vista
   es la versión de página completa con la cadena dibujada. */

import { _gmpEscHtml } from './core.js';

function node(label, status, detail){
  // status: done | active | todo — reutiliza las clases .flow/.node existentes
  return `<div class="node ${status}"><div><div class="lab">${label}</div></div>
    <div class="st">${_gmpEscHtml(detail)}</div><span class="led"></span></div>`;
}

export function renderMissionDetail(s){
  const el = document.getElementById('detail-content'); if(!el) return;
  const m = s.mission || {}, d = s.design || {}, rcs = s.rcs || {},
        dep = s.deployment || {}, audit = s.audit || {}, ws = s.workspace || {};
  const agents = (d.agents_summary || {}).agent_ids || [];
  const t = s.tests;

  const chain = [
    node('Objetivo', m.status === 'approved' ? 'done' : 'active', m.status || '—'),
    node('Agentes', agents.length ? 'done' : 'todo', agents.length + ' definidos'),
    node('Pruebas', t && (t.passed + t.failed) > 0 ? (t.failed === 0 ? 'done' : 'active') : 'todo',
         t ? `${t.passed} pass / ${t.failed} fail` : 'sin evidencia'),
    node('Evidencia', ws.files_visible ? 'done' : 'todo', (ws.files_visible || 0) + ' archivos'),
    node('Release', rcs.canonical ? 'done' : 'todo', rcs.canonical ? 'canónico' : (rcs.count || 0) + ' RCs'),
    node('Deploy', dep.health_ok ? 'done' : (dep.exists ? 'active' : 'todo'),
         dep.health_ok ? 'salud OK · :' + dep.api_port : dep.exists ? 'sin salud' : 'no existe'),
  ].join('');

  el.innerHTML = `
    <div class="card" style="margin-bottom:14px">
      <div class="between">
        <div><b class="mono">${_gmpEscHtml(s.project_id)}</b>
          <div class="meta">cliente: ${_gmpEscHtml(m.client_type || '—')} · creada: ${_gmpEscHtml(m.created_at || '—')}</div></div>
        <span class="chip ${m.status === 'approved' ? 'c-pass' : 'c-info'}">${_gmpEscHtml(m.status || '—')}</span>
      </div>
      <div class="meta mono" style="margin-top:6px">aprobada por <span style="color:var(--human)">${_gmpEscHtml(m.approved_by || '—')}</span> · ${_gmpEscHtml(m.approved_at || '—')}</div>
    </div>

    <div class="sec-h"><h3>Cadena de trazabilidad</h3><span class="bar"></span><span class="chip c-mute">evidencia real</span></div>
    <div class="card" style="padding:14px;margin-bottom:14px">
      <div class="flow" style="grid-template-columns:repeat(6,1fr)">${chain}</div>
    </div>

    <div class="grid g2">
      <div class="card">
        <div class="between"><h3>Agentes</h3><span class="chip c-mute">${agents.length}</span></div>
        <div class="hr"></div>
        <div class="meta" style="line-height:2">${agents.length ? agents.map(a => '<b class="mono">' + _gmpEscHtml(a) + '</b>').join(' · ') : 'sin agentes en el diseño'}</div>
        <div class="meta" style="color:var(--faint);margin-top:6px">perfiles heredados: ${(d.agents_summary || {}).profiles_inherited ?? 0} · nuevos: ${(d.agents_summary || {}).new_agents ?? 0}</div>
      </div>
      <div class="card">
        <div class="between"><h3>Releases y deployment</h3><span class="chip ${rcs.canonical ? 'c-pass' : 'c-mute'}">${rcs.count || 0} RCs</span></div>
        <div class="hr"></div>
        <div class="meta mono" style="line-height:2">
          canónico &nbsp; ${_gmpEscHtml(rcs.canonical || '—')}<br>
          deployment ${dep.exists ? 'puerto ' + _gmpEscHtml(String(dep.api_port || '—')) + ' · salud ' + (dep.health_ok ? 'OK' : 'sin respuesta') : 'no existe'}
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:14px">
      <div class="between"><h3>Auditoría de la misión</h3><span class="chip c-mute">${audit.event_count_filtered || 0} eventos</span></div>
      <div class="hr"></div>
      <div class="meta mono">último evento: ${_gmpEscHtml(audit.last_event_type || '—')} · ${_gmpEscHtml(audit.last_event_at || '—')}</div>
      <div class="meta" style="color:var(--faint);margin-top:6px">El detalle completo por grupo de evidencia sigue disponible en el panel lateral del Panel operativo.</div>
    </div>`;
}
