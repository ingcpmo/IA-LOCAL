/* W6.1 — Vista Agentes: catálogo de Capa 6 (base/custom/perfiles) y agentes
   asignados a la misión seleccionada. Read-only; muestra alcance, no prompts. */

import { _gmpEscHtml } from './core.js';

export function renderMissionAgents(d){
  const el = document.getElementById('agentsv-mission'); if(!el) return;
  const agents = d.agents || [];
  if(!agents.length){
    el.innerHTML = '<div class="card"><div class="meta">Sin agentes en el diseño de esta misión.</div></div>';
    return;
  }
  el.innerHTML = agents.map(a => `
    <div class="card" style="margin-bottom:10px">
      <div class="between">
        <div><b class="mono">${_gmpEscHtml(a.agent_id || '—')}</b>
          <div class="meta">${a.is_inherited ? 'perfil derivado de <b class="mono">' + _gmpEscHtml(a.base_agent || '—') + '</b>' : 'agente nuevo'}${a.profile_name ? ' · ' + _gmpEscHtml(a.profile_name) : ''}</div></div>
        <span class="chip ${a.is_inherited ? 'c-info' : 'c-pass'}">${a.is_inherited ? 'perfil' : 'nuevo'}</span>
      </div>
      ${a.rationale ? '<div class="meta" style="margin-top:6px;line-height:1.7">' + _gmpEscHtml(a.rationale) + '</div>' : ''}
      ${a.routing_key ? '<div class="meta mono" style="margin-top:4px;color:var(--faint)">routing: ' + _gmpEscHtml(a.routing_key) + '</div>' : ''}
    </div>`).join('');
}

export function renderAgentsCatalog(d){
  const el = document.getElementById('agentsv-catalog'); if(!el) return;
  const groups = [
    ['Agentes base', d.base_agents || {}, 'c-pass'],
    ['Agentes custom', d.custom_agents || {}, 'c-info'],
    ['Perfiles derivados', d.derived_profiles || {}, 'c-warn'],
  ];
  const cards = groups.map(([title, obj, chip]) => {
    const entries = Object.entries(obj);
    const body = entries.length
      ? entries.map(([id, a]) => `
          <div class="between" style="margin-bottom:8px">
            <div><b class="mono">${_gmpEscHtml(id)}</b>
              <div class="meta">${_gmpEscHtml((a && (a.name || a.description) || '').slice(0, 90))}</div></div>
            ${a && a.collection ? '<span class="chip c-mute">' + _gmpEscHtml(a.collection) + '</span>' : ''}
          </div>`).join('')
      : '<div class="meta" style="color:var(--faint)">ninguno</div>';
    return `<div class="card"><div class="between"><h3>${title}</h3><span class="chip ${chip}">${entries.length}</span></div><div class="hr"></div>${body}</div>`;
  }).join('');
  el.innerHTML = '<div class="grid g3">' + cards + '</div>';
}
