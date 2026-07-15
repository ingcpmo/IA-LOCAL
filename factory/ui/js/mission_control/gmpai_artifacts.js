/* GMPAI — artefactos de cierre de gmpai_document_validation (REM-GMPAI-001,
   informe final, tracker, documentos corregidos, paquete ZIP). Solo aplica
   a esa misión — no reprocesa documentos, solo lista/genera/descarga lo que
   ya está aprobado (RC canónico). Mismo patrón de auth que
   downloadGmpReportPdf en gmp_dashboard.js (fetch con headers() + blob,
   nunca <a href> directo porque el navegador no mandaría x-api-key). */

import { API_BASE, headers } from './state.js';
import { toast, _gmpEscHtml } from './core.js';

const PID = 'gmpai_document_validation';

async function _fetchBlob(url, filenameFallback){
  const r = await fetch(API_BASE + url, { headers: headers() });
  if(!r.ok){
    const t = await r.text().catch(() => '');
    throw new Error('HTTP ' + r.status + (t ? ': ' + t.slice(0, 160) : ''));
  }
  const cd = r.headers.get('content-disposition') || '';
  const m = /filename="([^"]+)"/.exec(cd);
  const filename = m ? m[1] : filenameFallback;
  const blob = await r.blob();
  return { blob, filename };
}

export async function gmpaiViewArtifact(runId, artifactPath){
  try{
    const { blob } = await _fetchBlob(
      `/api/v1/layer9/missions/${PID}/gmpai-artifacts/${encodeURIComponent(runId)}/${artifactPath}/view`,
      artifactPath.split('/').pop());
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }catch(e){ toast('Error abriendo artefacto: ' + e.message); }
}

export async function gmpaiDownloadArtifact(runId, artifactPath){
  try{
    const { blob, filename } = await _fetchBlob(
      `/api/v1/layer9/missions/${PID}/gmpai-artifacts/${encodeURIComponent(runId)}/${artifactPath}/download`,
      artifactPath.split('/').pop());
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename; document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast('Descargado: ' + filename);
  }catch(e){ toast('Error descargando artefacto: ' + e.message); }
}

export async function gmpaiGeneratePackage(){
  const btn = document.getElementById('gmpai-generate-btn');
  if(btn){ btn.disabled = true; btn.textContent = 'Generando…'; }
  try{
    const r = await fetch(API_BASE + `/api/v1/layer9/missions/${PID}/gmpai-artifacts/generate`, {
      method: 'POST', headers: { ...headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ recorded_by: 'Cesar' }),
    });
    if(!r.ok){
      const t = await r.text().catch(() => '');
      toast('Error ' + r.status + ' generando paquete' + (t ? ': ' + t.slice(0, 160) : ''));
      return;
    }
    toast('Paquete generado — recargando artefactos…');
    await gmpaiRenderArtifactsPanel();
  }catch(e){ toast('Error de red generando paquete: ' + e.message); }
  finally{ if(btn){ btn.disabled = false; btn.textContent = '⚙ Generar paquete de artefactos'; } }
}

export async function gmpaiRenderArtifactsPanel(){
  const el = document.getElementById('gmpai-artifacts-panel');
  if(!el) return;
  el.innerHTML = '<div class="meta" style="color:var(--faint)">Cargando artefactos…</div>';
  try{
    const r = await fetch(API_BASE + `/api/v1/layer9/missions/${PID}/gmpai-artifacts`, { headers: headers() });
    if(!r.ok){ el.innerHTML = '<div class="meta" style="color:var(--fail)">Error ' + r.status + '</div>'; return; }
    const d = await r.json();
    el.innerHTML = _renderPanel(d);
  }catch(e){ el.innerHTML = '<div class="meta" style="color:var(--fail)">Error de red: ' + e.message + '</div>'; }
}

// _esc() de core.js sanea IDs de misión (reemplaza todo lo que no sea
// [a-zA-Z0-9_-] por "_") — NO sirve aquí: run_id y filename traen puntos y
// slashes reales (final_report.pdf, compliance_matrices/x.json) que _esc
// destruiría. Este escape solo neutraliza comilla simple y backslash para
// poder embeber el valor dentro de onclick="...('valor')" sin romper el JS.
function _jsAttr(s){ return String(s).replace(/\\/g,'\\\\').replace(/'/g,"\\'"); }

function _btn(label, runId, path){
  return `<button class="btn ghost" style="font-size:10px;padding:4px 9px;margin:2px"
    onclick="gmpaiViewArtifact('${_jsAttr(runId)}','${_jsAttr(path)}')">👁 ${_gmpEscHtml(label)}</button>
  <button class="btn ghost" style="font-size:10px;padding:4px 9px;margin:2px"
    onclick="gmpaiDownloadArtifact('${_jsAttr(runId)}','${_jsAttr(path)}')">⬇ ${_gmpEscHtml(label)}</button>`;
}

function _renderPanel(d){
  const runs = d.runs || [];
  let html = `<div class="between" style="margin-bottom:8px">
    <div class="meta" style="font-size:11px">${runs.length} paquete(s) generado(s)</div>
    <button class="btn ghost" id="gmpai-generate-btn" style="font-size:11px;padding:6px 14px"
      onclick="gmpaiGeneratePackage()">⚙ Generar paquete de artefactos</button>
  </div>`;

  if(!d.latest){
    html += '<div class="meta" style="color:var(--faint)">Sin paquete generado todavía.</div>';
    return html;
  }

  const m = d.latest;
  html += `<div class="card" style="padding:10px 12px;margin-bottom:8px">
    <div class="meta mono" style="font-size:10.5px;line-height:1.8">
      run_id &nbsp; ${_gmpEscHtml(m.run_id)}<br>
      generado &nbsp; ${_gmpEscHtml((m.generated_at || '').slice(0, 19).replace('T', ' '))}<br>
      RC canónico &nbsp; ${_gmpEscHtml(m.rc_canonical)}<br>
      artefactos &nbsp; ${m.artifacts.length}
    </div>
  </div>`;

  html += `<div class="dp-sub">Informe final y tracker</div>
    <div style="margin-bottom:8px">
      ${_btn('Informe final PDF', m.run_id, 'final_report.pdf')}
      ${_btn('Tracker remediaciones PDF', m.run_id, 'remediation_tracker.pdf')}
    </div>`;

  const corrected = m.artifacts.filter(a => a.filename.startsWith('corrected_documents/'));
  if(corrected.length){
    html += `<div class="dp-sub">Documentos corregidos (draft)</div><div style="margin-bottom:8px">`;
    for(const a of corrected){
      html += _btn(a.filename.split('/').pop(), m.run_id, a.filename);
    }
    html += `</div>`;
  }

  const matrices = m.artifacts.filter(a => a.filename.startsWith('compliance_matrices/'));
  if(matrices.length){
    html += `<div class="dp-sub">Matrices de cumplimiento</div><div style="margin-bottom:8px">`;
    for(const a of matrices){
      html += _btn(a.filename.split('/').pop(), m.run_id, a.filename);
    }
    html += `</div>`;
  }

  html += `<div class="dp-sub">Paquete completo</div>
    <div style="margin-bottom:4px">${_btn('paquete_final.zip', m.run_id, 'paquete_final.zip')}</div>
    <div class="meta" style="font-size:9px;color:var(--faint)">
      SHA-256 en manifest.json y SHA256SUMS.txt dentro del paquete.
    </div>`;

  return html;
}
