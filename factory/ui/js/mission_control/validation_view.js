/* W6.1 — Vista Validación GAMP 5: matriz de los 22 documentos del paquete
   CSV por misión. Estados solo desde disco; la brecha se muestra tal cual. */

import { _gmpEscHtml } from './core.js';

const ST = {
  approved: ['c-pass', 'aprobado'],
  generated: ['c-info', 'generado'],
  not_started: ['c-mute', 'sin iniciar'],
};

export function renderValidationPackage(d){
  const el = document.getElementById('validation-content'); if(!el) return;
  const c = d.counts || {};

  const rows = (d.documents || []).map(doc => {
    const [chip, label] = ST[doc.status] || ST.not_started;
    return `<div class="between" style="margin-bottom:7px">
      <div><b style="font-size:12.5px">${_gmpEscHtml(doc.title)}</b>
        ${doc.approved_by ? '<div class="meta" style="color:var(--human)">aprobado por ' + _gmpEscHtml(doc.approved_by) + '</div>' : ''}</div>
      <span class="chip ${chip}">${label}</span>
    </div>`;
  }).join('');

  el.innerHTML = `
    <div class="grid g3" style="margin-bottom:14px">
      <div class="card stat"><span class="k">Aprobados</span><span class="n" style="color:var(--pass)">${c.approved ?? 0}<small> / ${d.total}</small></span></div>
      <div class="card stat"><span class="k">Generados</span><span class="n" style="color:var(--primary)">${c.generated ?? 0}<small> / ${d.total}</small></span></div>
      <div class="card stat"><span class="k">Sin iniciar</span><span class="n" style="color:var(--muted)">${c.not_started ?? 0}<small> / ${d.total}</small></span></div>
    </div>
    ${d.dossier_exists ? '' : '<div class="banner warn"><span>⚠</span><div>' + _gmpEscHtml(d.note || 'sin dossier') + ' — el estado real del paquete es este, no se simula avance.</div></div>'}
    <div class="card">${rows}</div>`;
}
