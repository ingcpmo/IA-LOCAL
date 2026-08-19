/* R4-T1.1v2 §3.2 — panel mínimo de adjudicación humana para la cadena de
   remediación (directivas + paquetes BATCH_AND_EXCEPTION). Antes de esto no
   existía NINGÚN panel para esto en Mission Control: el endpoint de
   directivas (f6607e9) y los tres endpoints de decisión humana de
   remediation_packages.py estaban vivos pero sin superficie -- exactamente
   el mismo patrón de riesgo que causó el incidente "Hallazgo no encontrado"
   de R3-T1.7, un paso más adelante en la cadena.

   Alcance deliberadamente mínimo (sin backend nuevo, solo los endpoints ya
   reales): lista de directivas de solo lectura + adjudicación de UN paquete
   por vez, buscado a mano por (project_id, package_id, version) -- no existe
   endpoint de listado de paquetes todavía. */

import { API_BASE, headers } from './state.js';
import { toast } from './core.js';

const esc = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

let DIRECTIVES = [];
/* Último paquete leído -- cada acción reenvía sobre ESTO, no sobre un
   estado adivinado; tras cada POST se vuelve a pedir el GET real. */
let PKG = null;

/* ---- Directivas de remediación (solo lectura) ---- */

export function renderRemediationDirectives(data){
  const el = document.getElementById('remediation-directives-list');
  if(!el) return;
  DIRECTIVES = data.directives || [];
  if(!DIRECTIVES.length){
    el.innerHTML = '<div class="card"><div class="meta" style="color:var(--faint)">Sin directivas de remediación registradas.</div></div>';
    return;
  }
  el.innerHTML = DIRECTIVES.map(d => `
    <div class="card" style="margin-bottom:10px">
      <div class="between"><b class="mono">${esc(d.directive_id)}</b><span class="chip">${esc(d.status)}</span></div>
      <div class="meta mono" style="margin-top:4px">hallazgo: ${esc(d.finding_rc_id)} · tipo: ${esc(d.change_type)}</div>
      <div class="meta" style="margin-top:6px">${esc(d.rationale||'')}</div>
      <div class="meta mono" style="margin-top:6px;color:var(--faint)">ubicación: ${esc(JSON.stringify(d.target_location||{}))}</div>
      <div class="meta mono" style="margin-top:6px">cita: ${(d.regulatory_citation||[]).map(esc).join(', ')||'—'}</div>
      <details style="margin-top:6px"><summary class="meta">texto propuesto</summary>
        <div class="meta" style="margin-top:4px;white-space:pre-wrap">${esc(d.proposed_text||'')}</div>
      </details>
      <div class="meta" style="margin-top:6px;color:var(--faint)">
        autor: ${esc(d.authored_by_display_name||d.authored_by_id)} · ${esc((d.authored_at||'').slice(0,16).replace('T',' '))}Z</div>
    </div>`).join('');
}

/* ---- Paquete de remediación: adjudicación humana (BATCH_AND_EXCEPTION) ----
   Los tres actos que este panel expone son EXACTAMENTE los tres endpoints
   ya reales de remediation_packages.py -- ninguno nuevo:
     excepción HIGH_RISK individual / lote MEDIUM_RISK / decisión final. */

export async function loadRemediationPackage(){
  const project = (document.getElementById('rp-project')?.value||'').trim();
  const pkgId = (document.getElementById('rp-package')?.value||'').trim();
  const version = (document.getElementById('rp-version')?.value||'').trim();
  const box = document.getElementById('remediation-package-box');
  if(!box) return;
  if(!project || !pkgId || !version){ toast('Completa project_id, package_id y version.'); return; }
  box.innerHTML = '<div class="card"><div class="meta" style="color:var(--faint)">cargando…</div></div>';
  try{
    const r = await fetch(
      API_BASE+'/api/v1/remediation-packages/'+encodeURIComponent(project)+'/'
        +encodeURIComponent(pkgId)+'/'+encodeURIComponent(version),
      {headers: headers()});
    if(r.status===404){
      box.innerHTML = '<div class="card"><div class="meta" style="color:var(--fail)">Paquete no encontrado (404) — revisa project_id/package_id/version.</div></div>';
      PKG = null; return;
    }
    if(!r.ok){
      box.innerHTML = '<div class="card"><div class="meta" style="color:var(--fail)">Error HTTP '+r.status+' al leer el paquete.</div></div>';
      PKG = null; return;
    }
    const data = await r.json();
    PKG = {project_id: project, package_id: pkgId, version: Number(version), ...data};
    renderRemediationPackage();
  }catch(e){
    box.innerHTML = '<div class="card"><div class="meta" style="color:var(--fail)">Error de red: '+esc(e.message)+'</div></div>';
    PKG = null;
  }
}

function changeCard(cid){
  const c = (PKG.changes||{})[cid] || {};
  return `<div class="card" style="margin-top:8px;padding:8px">
    <div class="mono" style="font-weight:600">${esc(cid)}</div>
    <div class="meta mono" style="margin-top:4px">${esc(c.change_type)} · riesgo: ${esc(c.change_risk)}
      · base: ${(c.change_risk_basis||[]).map(esc).join(', ')||'—'}</div>
    <div class="meta mono" style="margin-top:6px;color:var(--faint)">ubicación: ${esc(JSON.stringify(c.document_location||{}))}</div>
    <div class="meta" style="margin-top:6px">motivo: ${esc(c.change_reason||'')}</div>
    <details style="margin-top:6px"><summary class="meta">contenido propuesto</summary>
      <div class="meta" style="margin-top:4px;white-space:pre-wrap">${esc(c.proposed_content||'')}</div>
    </details>
    <div class="meta mono" style="margin-top:6px">citas: ${(c.citations||[]).map(x=>esc(typeof x==='string'?x:JSON.stringify(x))).join(', ')||'—'}</div>
  </div>`;
}

function exceptionBlock(cid){
  const existing = Object.values(PKG.exceptions||{}).find(e=>e.change_id===cid);
  if(existing){
    return `<div class="meta" style="margin-top:6px;color:var(--pass)">
      Ya revisado: <b>${esc(existing.human_review_decision)}</b> por ${esc(existing.responsible)}
      — "${esc(existing.justification)}" (${esc((existing.decided_at||'').slice(0,16).replace('T',' '))}Z)</div>`;
  }
  const safe = cid.replace(/[^a-zA-Z0-9_-]/g,'_');
  return `
    <div style="margin-top:8px">
      <div class="field"><label>Decisión</label>
        <select id="exc-decision-${safe}">
          <option value="accept_risk">accept_risk — aceptar el riesgo</option>
          <option value="reject_change">reject_change — rechazar el cambio</option>
        </select>
      </div>
      <div class="field"><label>Responsable (nombre real)</label>
        <input id="exc-responsible-${safe}" placeholder="p.ej. Cesar" autocomplete="off"></div>
      <div class="field"><label>Justificación (obligatoria)</label>
        <input id="exc-justification-${safe}" placeholder="motivo real de la decisión" autocomplete="off"></div>
      <button class="btn" onclick="submitExceptionReview('${esc(cid)}')">Registrar excepción — ${esc(cid)}</button>
    </div>`;
}

function mediumRiskBlock(mediumIds){
  const batches = Object.values(PKG.medium_risk_batch_decisions||{});
  const coveredAlready = new Set(batches.flatMap(b=>b.covered_change_ids||[]));
  const pending = mediumIds.filter(id=>!coveredAlready.has(id));
  const batchList = batches.map(b=>`<div class="meta" style="margin-top:4px;color:var(--pass)">
      lote ${esc(b.batch_decision_id)}: ${b.covered_change_ids.length} cambios — ${esc(b.responsible)}
      — "${esc(b.justification)}"</div>`).join('');
  if(!pending.length){
    return `<div class="meta" style="margin-top:6px;color:var(--pass)">Todos los MEDIUM_RISK ya tienen lote registrado.</div>${batchList}`;
  }
  const checks = pending.map(id=>`<label class="meta" style="display:block;margin-top:4px">
      <input type="checkbox" class="mrb-check" value="${esc(id)}" checked> ${esc(id)}</label>`).join('');
  return `${batchList}
    <div style="margin-top:8px">
      <div class="meta">Cambios pendientes de lote (${pending.length}):</div>
      ${checks}
      <div class="field" style="margin-top:6px"><label>Responsable (nombre real)</label>
        <input id="mrb-responsible" placeholder="p.ej. Cesar" autocomplete="off"></div>
      <div class="field"><label>Justificación (obligatoria)</label>
        <input id="mrb-justification" placeholder="motivo real del lote" autocomplete="off"></div>
      <button class="btn" onclick="submitMediumRiskBatch()">Registrar lote MEDIUM_RISK</button>
    </div>`;
}

function packageDecisionBlock(){
  const pd = PKG.package_decision;
  if(pd){
    return `<div class="card" style="margin-top:10px;border:1px solid var(--pass)">
      <b>Decisión final registrada</b>
      <div class="meta mono" style="margin-top:4px">${esc(pd.decision_id)}</div>
      <div class="meta" style="margin-top:4px">${esc(pd.decision)} — ${esc(pd.decided_by)} — "${esc(pd.justification)}"</div>
      <div class="meta" style="margin-top:4px;color:var(--faint)">${esc((pd.decided_at||'').slice(0,16).replace('T',' '))}Z — inmutable, no admite segunda decisión.</div>
    </div>`;
  }
  if(PKG.package.status !== 'AWAITING_PACKAGE_DECISION'){
    return `<div class="meta" style="margin-top:10px;color:var(--faint)">
      Decisión final disponible cuando el estado sea AWAITING_PACKAGE_DECISION
      (estado actual: ${esc(PKG.package.status)}).</div>`;
  }
  const batches = Object.values(PKG.medium_risk_batch_decisions||{});
  const batchOptions = batches.map(b=>`<option value="${esc(b.batch_decision_id)}">${esc(b.batch_decision_id)}</option>`).join('');
  return `<div class="card" style="margin-top:10px">
    <b>Decisión final del paquete</b>
    <div class="meta" style="margin-top:6px;color:var(--warn)">
      Nunca ejecuta ni libera nada -- create_release_record() no está conectado
      a ningún endpoint. Registrar esta decisión NO libera el documento.</div>
    <div class="field" style="margin-top:8px"><label>Decisión</label>
      <select id="pd-decision">
        <option value="APPROVE_CLEAN">APPROVE_CLEAN</option>
        <option value="APPROVE_WITH_EXCEPTIONS">APPROVE_WITH_EXCEPTIONS</option>
        <option value="RETURN_TO_ADJUSTMENTS">RETURN_TO_ADJUSTMENTS</option>
        <option value="REJECT">REJECT</option>
      </select></div>
    <div class="field"><label>Lote MEDIUM_RISK a citar (opcional)</label>
      <select id="pd-batch"><option value="">(ninguno)</option>${batchOptions}</select></div>
    <div class="meta" style="margin-top:6px;color:var(--faint)">
      Quien decide se resuelve de tu IDENTITY KEY de sesión (Paquete 2) --
      ya no es un campo de texto libre.</div>
    <div class="field"><label>Justificación (obligatoria)</label>
      <input id="pd-justification" placeholder="motivo real de la decisión final" autocomplete="off"></div>
    <button class="btn pass" onclick="submitPackageDecision()">Registrar decisión final</button>
  </div>`;
}

function renderRemediationPackage(){
  const box = document.getElementById('remediation-package-box');
  if(!box || !PKG) return;
  const p = PKG.package;
  const groups = p.changes || {low_risk:[], medium_risk:[], high_risk:[]};

  const artifacts = Object.entries(p.artifacts||{}).map(([k,a])=>`
    <div class="meta mono" style="margin-top:4px">${esc(k)}: ${esc(a.sha256||'').slice(0,16)}… (${esc(a.size_bytes ?? a.size ?? '?')} bytes)</div>
  `).join('') || '<div class="meta" style="color:var(--faint)">(sin artefactos)</div>';

  box.innerHTML = `
  <div class="card">
    <div class="between"><b class="mono">${esc(PKG.package_id)} v${esc(PKG.version)}</b><span class="chip">${esc(p.status)}</span></div>
    <div class="meta mono" style="margin-top:4px">proyecto: ${esc(PKG.project_id)}</div>
    <div class="meta" style="margin-top:6px">
      evaluación automática completa: ${esc(String(p.automatic_evaluation_complete))} ·
      revisión de excepciones completa: ${esc(String(p.human_exception_review_complete))}</div>
    <div style="margin-top:6px">${artifacts}</div>
  </div>

  <div class="card" style="margin-top:10px">
    <b>HIGH_RISK (${groups.high_risk.length}) — requiere excepción individual antes de la decisión final</b>
    ${groups.high_risk.map(cid=>changeCard(cid)+exceptionBlock(cid)).join('') || '<div class="meta" style="color:var(--faint);margin-top:8px">Ninguno.</div>'}
  </div>

  <div class="card" style="margin-top:10px">
    <b>MEDIUM_RISK (${groups.medium_risk.length}) — un solo lote cubre todo</b>
    ${groups.medium_risk.length ? mediumRiskBlock(groups.medium_risk) : '<div class="meta" style="color:var(--faint);margin-top:8px">Ninguno.</div>'}
  </div>

  <div class="card" style="margin-top:10px">
    <b>LOW_RISK (${groups.low_risk.length}) — sin revisión individual</b>
    ${groups.low_risk.map(changeCard).join('') || '<div class="meta" style="color:var(--faint);margin-top:8px">Ninguno.</div>'}
  </div>

  ${packageDecisionBlock()}`;
}

async function _postJSON(path, body){
  const r = await fetch(API_BASE+path, {method:'POST', headers:headers(), body: JSON.stringify(body)});
  const data = await r.json().catch(()=>({}));
  return {ok:r.ok, status:r.status, data};
}

export async function submitExceptionReview(changeId){
  if(!PKG) return;
  const safe = changeId.replace(/[^a-zA-Z0-9_-]/g,'_');
  const human_review_decision = document.getElementById('exc-decision-'+safe)?.value;
  const responsible = (document.getElementById('exc-responsible-'+safe)?.value||'').trim();
  const justification = (document.getElementById('exc-justification-'+safe)?.value||'').trim();
  if(!responsible){ toast('Ingresa el nombre real del responsable.'); return; }
  if(!justification){ toast('La justificación es obligatoria.'); return; }
  const {ok, status, data} = await _postJSON(
    '/api/v1/remediation-packages/'+encodeURIComponent(PKG.project_id)+'/'
      +encodeURIComponent(PKG.package_id)+'/'+PKG.version+'/exceptions/'+encodeURIComponent(changeId),
    {human_review_decision, responsible, justification});
  if(ok){ toast('Excepción registrada — '+changeId); await loadRemediationPackage(); }
  else { toast('Error '+status+': '+(data.detail||JSON.stringify(data))); }
}

export async function submitMediumRiskBatch(){
  if(!PKG) return;
  const covered_change_ids = Array.from(document.querySelectorAll('.mrb-check:checked')).map(el=>el.value);
  const responsible = (document.getElementById('mrb-responsible')?.value||'').trim();
  const justification = (document.getElementById('mrb-justification')?.value||'').trim();
  if(!covered_change_ids.length){ toast('Selecciona al menos un cambio MEDIUM_RISK.'); return; }
  if(!responsible){ toast('Ingresa el nombre real del responsable.'); return; }
  if(!justification){ toast('La justificación es obligatoria.'); return; }
  const {ok, status, data} = await _postJSON(
    '/api/v1/remediation-packages/'+encodeURIComponent(PKG.project_id)+'/'
      +encodeURIComponent(PKG.package_id)+'/'+PKG.version+'/medium-risk-batch',
    {covered_change_ids, responsible, justification});
  if(ok){ toast('Lote MEDIUM_RISK registrado ('+covered_change_ids.length+' cambios)'); await loadRemediationPackage(); }
  else { toast('Error '+status+': '+(data.detail||JSON.stringify(data))); }
}

export async function submitPackageDecision(){
  if(!PKG) return;
  const decision = document.getElementById('pd-decision')?.value;
  const justification = (document.getElementById('pd-justification')?.value||'').trim();
  const medium_risk_batch_decision_id = document.getElementById('pd-batch')?.value || null;
  if(!justification){ toast('La justificación es obligatoria.'); return; }
  let high_risk_exception_ids = null;
  if(decision === 'APPROVE_WITH_EXCEPTIONS'){
    high_risk_exception_ids = Object.values(PKG.exceptions||{}).map(e=>e.exception_id);
  }
  // decided_by ya NO viaja en el body (Paquete 2, hallazgo M) -- lo
  // resuelve el backend desde X-Identity-Key (headers(), state.js).
  const {ok, status, data} = await _postJSON(
    '/api/v1/remediation-packages/'+encodeURIComponent(PKG.project_id)+'/'
      +encodeURIComponent(PKG.package_id)+'/'+PKG.version+'/decision',
    {decision, justification, medium_risk_batch_decision_id, high_risk_exception_ids});
  if(ok){ toast('Decisión final registrada: '+decision); await loadRemediationPackage(); }
  else if(status===409){ toast('Ya existe una decisión para este paquete (409) — no se puede re-decidir.'); await loadRemediationPackage(); }
  else { toast('Error '+status+': '+(data.detail||JSON.stringify(data))); }
}
