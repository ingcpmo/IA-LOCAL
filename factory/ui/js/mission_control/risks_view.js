/* W6 — Vista Riesgos: lista completa de status/risks con franja de severidad.
   Read-only: aceptar riesgos sigue siendo una acción humana de otra vista. */

import { _gmpEscHtml } from './core.js';

const SEV = { alto: 'sev-high', medio: 'sev-med', info: 'sev-info' };
const SEV_CHIP = { alto: 'c-fail', medio: 'c-warn', info: 'c-info' };

export function renderRisksView(data){
  const el = document.getElementById('risks-view-list'); if(!el) return;
  const risks = data.risks || [];
  if(!risks.length){
    el.innerHTML = '<div class="card"><div class="meta" style="color:var(--pass)">Sin riesgos activos detectados por el sistema.</div></div>';
    return;
  }
  el.innerHTML = risks.map(r => `
    <div class="card ${SEV[r.severity] || ''}" style="margin-bottom:10px">
      <div class="between">
        <b class="mono">${_gmpEscHtml(r.id || '—')}</b>
        <span class="chip ${SEV_CHIP[r.severity] || 'c-mute'}">${_gmpEscHtml(r.severity || '—')}</span>
      </div>
      <div class="meta" style="margin-top:6px;line-height:1.7">${_gmpEscHtml(r.description || '')}</div>
      ${r.recommendation ? '<div class="meta" style="margin-top:4px;color:var(--faint)">Recomendación: ' + _gmpEscHtml(r.recommendation) + '</div>' : ''}
    </div>`).join('');
}
