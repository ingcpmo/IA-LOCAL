/* W6 — Executive Overview: estado del sistema en un vistazo.
   Solo consume endpoints existentes; cada KPI proviene de evidencia real. */

import { _gmpEscHtml } from './core.js';

const CHIP = {
  approved: 'c-pass', deployed: 'c-pass', pending_approval: 'c-info',
  draft: 'c-mute', rejected: 'c-fail', returned: 'c-warn',
};

export function renderExecStatus(d){
  const el = document.getElementById('ex-audit'); if(!el) return;
  const av = d.summary?.audit_verified, ae = d.summary?.audit_entries;
  const hashErr = d.summary?.audit_hash_errors ?? 0, chainErr = d.summary?.audit_chain_errors ?? 0;
  const isFork = !av && hashErr === 0 && chainErr > 0;
  el.style.color = av ? 'var(--pass)' : isFork ? 'var(--warn)' : 'var(--fail)';
  el.innerHTML = (av ? 'OK' : isFork ? 'WARN' : 'FALLA') + '<small> · ' + (ae || 0) + '</small>';
}

export function renderExecMissions(ms){
  const n = document.getElementById('ex-missions');
  if(n) n.textContent = Array.isArray(ms) ? ms.length : '—';
  const pend = ms.filter(m => m.status !== 'approved');
  const p = document.getElementById('ex-pending');
  if(p) p.textContent = pend.length;
  const el = document.getElementById('ex-mission-list'); if(!el) return;
  if(!ms.length){ el.innerHTML = '<div style="color:var(--faint)">Sin misiones registradas.</div>'; return; }
  el.innerHTML = ms.map(m => `
    <div class="between" style="margin-bottom:8px">
      <div><b class="mono">${_gmpEscHtml(m.project_id)}</b>
      <div class="meta">${_gmpEscHtml((m.objective || '').slice(0, 60))}…</div></div>
      <span class="chip ${CHIP[m.status] || 'c-mute'}">${_gmpEscHtml(m.status || '—')}</span>
    </div>`).join('');
}

export function renderExecReview(d){
  const el = document.getElementById('ex-rc'); if(!el) return;
  el.innerHTML = (d.summary?.pending ?? 0) + '<small> / revisar</small>';
}

export function renderExecRisks(d){
  const risks = d.risks || [];
  const cnt = document.getElementById('ex-risk-count');
  if(cnt){ cnt.textContent = risks.length; cnt.className = 'chip ' + (risks.length ? 'c-warn' : 'c-pass'); }
  const el = document.getElementById('ex-risk-list'); if(!el) return;
  if(!risks.length){ el.innerHTML = '<div style="color:var(--pass)">Sin riesgos activos detectados.</div>'; return; }
  const sev = { alto: 'c-fail', medio: 'c-warn', info: 'c-info' };
  el.innerHTML = risks.slice(0, 3).map(r => `
    <div style="margin-bottom:8px"><span class="chip ${sev[r.severity] || 'c-mute'}" style="margin-right:8px">${_gmpEscHtml(r.severity)}</span>${_gmpEscHtml(r.description)}</div>`).join('')
    + (risks.length > 3 ? '<div class="meta" style="color:var(--faint)">+ ' + (risks.length - 3) + ' más en la vista Riesgos</div>' : '');
}
