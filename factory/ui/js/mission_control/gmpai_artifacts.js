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

// ── Cierre FS_v1.2 (Piloto B) — 6 bloques separados en Mission Control ─────
// Distinto del panel genérico de arriba (que lista TODOS los runs de
// artefactos): esto muestra el registro explícito de qué run es el vigente
// para FS_v1.2 (is_current) y cuál queda legado (supersedes_run_id), sin
// mezclar ambos estados visualmente. Nunca declara approved/compliant/
// effective/released — solo el estado real del borrador.

export async function gmpaiRenderFsV12ClosurePanel(){
  const el = document.getElementById('gmpai-fs-v1-2-closure-panel');
  if(!el) return;
  el.innerHTML = '<div class="meta" style="color:var(--faint)">Cargando cierre FS_v1.2…</div>';
  try{
    const r = await fetch(API_BASE + `/api/v1/layer9/missions/${PID}/gmpai-artifacts/fs-v1-2-closure`, { headers: headers() });
    if(r.status === 404){ el.innerHTML = '<div class="meta" style="color:var(--faint)">Cierre FS_v1.2 no registrado todavía.</div>'; return; }
    if(!r.ok){ el.innerHTML = '<div class="meta" style="color:var(--fail)">Error ' + r.status + '</div>'; return; }
    const d = await r.json();
    el.innerHTML = _renderFsV12Closure(d);
  }catch(e){ el.innerHTML = '<div class="meta" style="color:var(--fail)">Error de red: ' + e.message + '</div>'; }
}

function _statusBadge(text, kind){
  const colors = { warn: 'var(--warn, #b8860b)', fail: 'var(--fail)', neutral: 'var(--faint)' };
  return `<span class="mono" style="font-size:10px;padding:2px 7px;border-radius:3px;border:1px solid ${colors[kind] || colors.neutral};color:${colors[kind] || colors.neutral}">${_gmpEscHtml(text)}</span>`;
}

function _block(title, bodyHtml){
  return `<div class="card" style="padding:10px 12px;margin-bottom:8px">
    <div class="dp-sub" style="margin-bottom:6px">${_gmpEscHtml(title)}</div>
    ${bodyHtml}
  </div>`;
}

function _renderFsV12Closure(d){
  const c = d.current;
  const superseded = d.superseded_runs || [];
  const legacy = d.legacy_runs || [];
  const m = c.regulatory_metrics;
  const receipt = c.package_receipt;
  let html = '';

  // 1. Resumen ejecutivo
  html += _block('1. Resumen ejecutivo', `
    <div class="mono" style="font-size:10.5px;line-height:1.9">
      documento &nbsp; ${_gmpEscHtml(c.documento)}<br>
      SHA-256 original &nbsp; ${_gmpEscHtml(c.document_sha256)}<br>
      run vigente &nbsp; ${_gmpEscHtml(c.run_id)} (${_gmpEscHtml(c.version || '')}) ${_statusBadge('VIGENTE', 'neutral')}<br>
      commit de referencia &nbsp; ${_gmpEscHtml(c.commit)}<br>
      decisión Capa 9 &nbsp; ${_gmpEscHtml(c.capa9_decision_id)}<br>
      ${m ? `cobertura del análisis &nbsp; <b>${_gmpEscHtml(m.cobertura_tecnica_total_pct)}%</b><br>
      RRI (preparación documental) &nbsp; <b>${_gmpEscHtml(m.regulatory_readiness_index.rri_pct)}%</b><br>
      cumplimiento real (Part 11 / Annex 11 / ALCOA+) &nbsp; ${_statusBadge('NOT_DETERMINED', 'warn')}` : ''}
    </div>`);

  // 2. Ejecucion de los tres agentes (cobertura)
  const cobertura = Object.entries(c.cobertura_por_agente || {})
    .map(([agente, cov]) => `${_gmpEscHtml(agente)}: <b>${_gmpEscHtml(cov)}</b>`).join('<br>');
  html += _block('2. Ejecución de los tres agentes', `
    <div class="mono" style="font-size:10.5px;line-height:1.9">
      ${cobertura}<br>
      ${m ? `cobertura de páginas/chunks &nbsp; ${_gmpEscHtml(m.cobertura_paginas_y_chunks.cobertura_pct)}%` : ''}
    </div>`);

  // 3. Findings
  html += _block('3. Findings', `
    <div class="mono" style="font-size:10.5px;line-height:1.7">
      findings totales &nbsp; ${c.findings_totales} (19 consolidados)<br>
      ${m ? `% cumple &nbsp; ${m.pct_cumple}% &nbsp;|&nbsp; % cumple parcialmente &nbsp; ${m.pct_cumple_parcialmente}%
      &nbsp;|&nbsp; % no cumple documentalmente &nbsp; ${m.pct_no_cumple_documentalmente}%
      &nbsp;|&nbsp; % evidencia insuficiente &nbsp; ${m.pct_evidencia_insuficiente}%<br>
      % con cita literal validada &nbsp; ${m.pct_findings_con_cita_literal_validada}%` : ''}
    </div>`);

  // 4. Contradicciones y cambios
  const cor = (c.matriz_finding_correccion || []).map(mm =>
    `<div style="margin-bottom:4px"><b>${_gmpEscHtml(mm.correccion_id)}</b> — ${_gmpEscHtml(mm.tema)} (${mm.findings_sustento.length} finding(s) de sustento)</div>`
  ).join('');
  html += _block('4. Contradicciones y cambios', `
    <div class="mono" style="font-size:10.5px;line-height:1.7">
      contradicciones detectadas (C1-C4) &nbsp; ${c.contradicciones_totales}<br>
      resueltas técnicamente &nbsp; ${c.contradicciones_resueltas} ${_statusBadge('CONDITIONALLY_APPROVED', 'neutral')}
    </div>
    <div style="margin-top:6px">${cor}</div>
    <div class="meta" style="font-size:9px;color:var(--faint);margin-top:4px">Detalle completo por campo: changelog_FS_v1_2_v3.json</div>`);

  // 5. Recomendaciones y remediaciones abiertas
  const openBadges = (c.open_items || []).map(i => _statusBadge(i + ' — ABIERTO', 'warn')).join(' ');
  html += _block('5. Recomendaciones y remediaciones abiertas', `
    <div style="margin-bottom:6px">${openBadges}</div>
    <div class="meta" style="font-size:9.5px;color:var(--faint)">
      Ver informe_profesional_FS_v1_2_v3 seccion F para recomendaciones documentales, tecnicas,
      de procedimiento, QA, Ingenieria y seguimiento.
    </div>`);

  // 6. Metricas, gobernanza y artefactos
  const dec = c.capa9_decision || {};
  const metricsRows = m ? `
      TECHNICAL_CONTRADICTION_RESOLUTION &nbsp; ${_statusBadge('CONDITIONALLY_APPROVED', 'neutral')}<br>
      DRAFT_DOCUMENT_STATUS &nbsp; ${_statusBadge('AWAITING_HUMAN_REVIEW_AND_APPROVAL', 'warn')}<br>
      REGULATORY_COMPLIANCE_STATUS &nbsp; ${_statusBadge('NOT_DETERMINED', 'warn')}<br>
      decidido por &nbsp; ${_gmpEscHtml(dec.decided_by || 'no disponible')} (${_gmpEscHtml(dec.decision_origin || '')})<br>
      <br>
      RRI = [(cumple x 1.0)+(cumple_parcial x 0.5)] / total_aplicable x 100 =
      [(${m.regulatory_readiness_index.cumple} x 1.0)+(${m.regulatory_readiness_index.cumple_parcialmente} x 0.5)] /
      ${m.regulatory_readiness_index.denominador_total_aplicable} x 100 =
      <b>${m.regulatory_readiness_index.rri_pct}%</b><br>
      <span style="font-size:9px">${_gmpEscHtml(m.regulatory_readiness_index.etiqueta_obligatoria)}</span>
    ` : '';
  html += _block('6. Métricas, gobernanza y artefactos (run vigente ' + c.run_id + ')', `
    <div class="mono" style="font-size:10.5px;line-height:1.9">${metricsRows}</div>
    <div class="meta" style="font-size:9.5px;color:var(--faint);margin:6px 0">
      El borrador v3 NUNCA se muestra como approved, compliant, effective ni released.
    </div>
    <div>${_artifactButtons(c.run_id)}</div>
    <div class="meta" style="font-size:9px;color:var(--faint);margin-top:6px">
      zip (${_gmpEscHtml(c.zip_filename)}) SHA-256: <span class="mono">${_gmpEscHtml(c.zip_sha256)}</span><br>
      ${receipt ? `package_receipt: artifact_count=${receipt.artifact_count_real}, manifest_hash=${_gmpEscHtml((receipt.manifest_hash||'').slice(0,16))}…` : ''}
    </div>`);

  // Bloque de version chain -- superseded (intermedio) vs legacy (historico RC v1.4)
  if(superseded.length){
    const rows = superseded.map(sr => `
      <div style="margin-bottom:8px">
        run_id <b>${_gmpEscHtml(sr.run_id)}</b> (${_gmpEscHtml(sr.version || 'v?')}) ${_statusBadge('SUPERSEDED_FOR_OPERATIONAL_USE', 'fail')}<br>
        <span class="meta" style="font-size:9.5px;color:var(--faint)">superseded_by ${_gmpEscHtml(sr.superseded_by_run_id)} — conservado integro para auditoria, no operativo.</span><br>
        ${_btn(sr.zip_filename + ' (superseded)', sr.run_id, sr.zip_filename)}
      </div>`).join('');
    html += _block('Versión intermedia superada (NO vigente)', rows);
  }
  if(legacy.length){
    const legacyRows = legacy.map(lr => `
      <div style="margin-bottom:8px">
        run_id <b>${_gmpEscHtml(lr.run_id)}</b> ${_statusBadge('LEGACY_RC_V1.4_PRE_FS_REANALYSIS', 'fail')} ${_statusBadge('SUPERSEDED_FOR_OPERATIONAL_USE', 'fail')}<br>
        <span class="meta" style="font-size:9.5px;color:var(--faint)">superseded_by ${_gmpEscHtml(lr.superseded_by_run_id)} — conservado íntegro solo para auditoría histórica, no operativo.</span><br>
        ${_btn('paquete_final.zip (legado)', lr.run_id, 'paquete_final.zip')}
      </div>`).join('');
    html += _block('Histórico — RC v1.4 (NO vigente)', legacyRows);
  }

  return html;
}

function _artifactButtons(runId){
  const artifactList = [
    ['Borrador correcciones v3 (DOCX)', 'FS_v1.2_borrador_correcciones_draft_v3.docx'],
    ['Borrador correcciones v3 (PDF)', 'FS_v1.2_borrador_correcciones_draft_v3.pdf'],
    ['Informe profesional v3 (DOCX)', 'informe_profesional_FS_v1_2_v3.docx'],
    ['Informe profesional v3 (PDF)', 'informe_profesional_FS_v1_2_v3.pdf'],
    ['regulatory_metrics_FS_v1_2.json', 'regulatory_metrics_FS_v1_2.json'],
    ['matriz_findings_recomendaciones_FS_v1_2.json', 'matriz_findings_recomendaciones_FS_v1_2.json'],
    ['technical_error_log_FS_v1_2.json', 'technical_error_log_FS_v1_2.json'],
    ['changelog_FS_v1_2_v3.json', 'changelog_FS_v1_2_v3.json'],
    ['fs_v1_2_status.json', 'fs_v1_2_status.json'],
    ['REGULATORY_SOURCE_CHECK.json', 'REGULATORY_SOURCE_CHECK.json'],
    ['fda_part11_agent.json', 'agent_reports/fda_part11_agent.json'],
    ['eu_annex11_agent.json', 'agent_reports/eu_annex11_agent.json'],
    ['alcoa_plus_agent.json', 'agent_reports/alcoa_plus_agent.json'],
    ['alcoa_plus_agent.pre_retry.json', 'agent_reports/alcoa_plus_agent.pre_retry.json'],
    ['manifest.json', 'manifest.json'],
    ['SHA256SUMS.txt', 'SHA256SUMS.txt'],
    ['package_receipt.json', 'package_receipt.json'],
    ['paquete_final_FS_v1_2_v3.zip', 'paquete_final_FS_v1_2_v3.zip'],
  ];
  return artifactList.map(([label, path]) => _btn(label, runId, path)).join('');
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
