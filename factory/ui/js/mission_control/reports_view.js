/* W6.1 — Vista Reportes: artefactos ya en disco (hash + fecha) y reportes
   generables bajo demanda. No genera nada; el PDF reutiliza el flujo W4.1.1. */

import { _esc, _gmpEscHtml } from './core.js';

const KIND_LABEL = {
  release_candidate: 'Release candidate',
  functional_test_results: 'Pruebas funcionales W4',
};

function fmtBytes(n){
  if(n == null) return '—';
  return n > 1048576 ? (n / 1048576).toFixed(1) + ' MB'
       : n > 1024 ? (n / 1024).toFixed(1) + ' KB' : n + ' b';
}

export function renderReports(d, pid){
  const el = document.getElementById('reports-content'); if(!el) return;
  const stored = d.stored_reports || [];

  const rows = stored.length ? stored.map(r => `
    <div class="between" style="margin-bottom:8px;gap:10px">
      <div style="min-width:0"><b class="mono" style="font-size:11.5px;word-break:break-all">${_gmpEscHtml(r.path)}</b>
        <div class="meta">${_gmpEscHtml(KIND_LABEL[r.kind] || r.kind)} · ${fmtBytes(r.size_bytes)} · ${_gmpEscHtml(r.modified_at)}</div></div>
      <span class="chip c-mute mono" title="SHA-256 (12)">${_gmpEscHtml(r.sha256_12)}</span>
    </div>`).join('')
    : '<div class="meta">' + _gmpEscHtml(d.note || 'sin reportes almacenados') + '</div>';

  const onDemand = (d.on_demand || []).map(o => `
    <div class="between" style="margin-bottom:8px">
      <div><b>${_gmpEscHtml(o.name)}</b><div class="meta mono" style="font-size:10.5px">${_gmpEscHtml(o.endpoint)}</div></div>
      ${o.endpoint.endsWith('.pdf')
        ? `<button class="btn ghost" id="gmp-pdf-btn-${_esc(pid)}" onclick="downloadGmpReportPdf('${_esc(pid)}')">⬇ PDF</button>`
        : ''}
    </div>`).join('');

  el.innerHTML = `
    <div class="card" style="margin-bottom:14px">
      <div class="between"><h3>Almacenados en disco</h3><span class="chip c-mute">${stored.length}</span></div>
      <div class="hr"></div>${rows}
    </div>
    <div class="card">
      <div class="between"><h3>Generables bajo demanda</h3><span class="chip c-info">W4.1</span></div>
      <div class="hr"></div>${onDemand}
    </div>`;
}
