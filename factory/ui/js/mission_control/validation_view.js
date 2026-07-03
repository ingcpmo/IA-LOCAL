/* W6.1 — Vista Validación GAMP 5: matriz de los 22 documentos del paquete
   CSV por misión. Estados solo desde disco; la brecha se muestra tal cual.
   W6.2 — generación asistida de borradores + aprobación humana por documento.
   Generar NUNCA aprueba; approved SOLO por acto humano con nombre real. */

import { API_BASE, headers } from './state.js';
import { toast, _gmpEscHtml } from './core.js';

const _RESERVED_RUN_BY=['human','agent','system','admin','user','factory'];

const ST = {
  approved: ['c-pass', 'aprobado'],
  draft: ['c-info', 'draft'],
  needs_human_review: ['c-warn', 'por revisar'],
  missing_evidence: ['c-fail', 'sin evidencia'],
  not_started: ['c-mute', 'sin iniciar'],
};

let _pid = null;   // misión del último render — la usan los handlers de acción

export function renderValidationPackage(d){
  const el = document.getElementById('validation-content'); if(!el) return;
  _pid = d.project_id || null;
  const c = d.counts || {};

  const rows = (d.documents || []).map(doc => {
    const [chip, label] = ST[doc.status] || ST.not_started;
    const canView = doc.status !== 'not_started';
    const canApprove = doc.status === 'draft' || doc.status === 'needs_human_review';
    const missing = (doc.missing || []).length
      ? '<div class="meta" style="color:var(--fail);font-size:10px">falta: ' + _gmpEscHtml(doc.missing.join(', ')) + '</div>' : '';
    return `<div class="between" style="margin-bottom:7px">
      <div><b style="font-size:12.5px">${_gmpEscHtml(doc.title)}</b>
        ${doc.approved_by ? '<div class="meta" style="color:var(--human)">aprobado por ' + _gmpEscHtml(doc.approved_by) + '</div>' : ''}
        ${missing}</div>
      <div style="display:flex;gap:6px;align-items:center">
        ${canView ? `<button class="btn ghost" style="font-size:10px;padding:2px 8px" onclick="viewValidationDoc('${_gmpEscHtml(doc.doc_id)}')">Ver</button>` : ''}
        ${canApprove ? `<button class="btn human" style="font-size:10px;padding:2px 8px" onclick="promptApproveDoc('${_gmpEscHtml(doc.doc_id)}')">Aprobar</button>` : ''}
        <span class="chip ${chip}">${label}</span>
      </div>
    </div>`;
  }).join('');

  const inProgress = (c.draft ?? 0) + (c.needs_human_review ?? 0) + (c.missing_evidence ?? 0);
  el.innerHTML = `
    <div class="grid" style="grid-template-columns:repeat(5,1fr);margin-bottom:14px">
      <div class="card stat"><span class="k">Aprobados</span><span class="n" style="color:var(--pass)">${c.approved ?? 0}<small> / ${d.total}</small></span></div>
      <div class="card stat"><span class="k">Draft</span><span class="n" style="color:var(--primary)">${c.draft ?? 0}<small> / ${d.total}</small></span></div>
      <div class="card stat"><span class="k">Por revisar</span><span class="n" style="color:var(--warn)">${c.needs_human_review ?? 0}<small> / ${d.total}</small></span></div>
      <div class="card stat"><span class="k">Sin evidencia</span><span class="n" style="color:var(--fail)">${c.missing_evidence ?? 0}<small> / ${d.total}</small></span></div>
      <div class="card stat"><span class="k">Sin iniciar</span><span class="n" style="color:var(--muted)">${c.not_started ?? 0}<small> / ${d.total}</small></span></div>
    </div>
    <div class="between" style="margin-bottom:12px">
      <div class="meta" style="font-size:10.5px;color:var(--faint);max-width:640px">
        Generar produce BORRADORES desde evidencia real de la Factory (sin valor regulatorio).
        Nunca aprueba: <b>approved</b> requiere acto humano con nombre real y queda auditado.
        Si la evidencia de un doc aprobado cambia, su aprobación se invalida a "por revisar".</div>
      <button class="btn ghost" onclick="promptGenerateDossier()">${d.dossier_exists ? 'Regenerar borradores' : 'Generar dossier (asistido)'}</button>
    </div>
    ${d.dossier_exists ? '' : '<div class="banner warn"><span>⚠</span><div>' + _gmpEscHtml(d.note || 'sin dossier') + ' — el estado real del paquete es este, no se simula avance.</div></div>'}
    <div class="card">${rows || '<div class="meta" style="color:var(--faint)">sin documentos</div>'}</div>
    <div id="validation-doc-viewer" style="margin-top:14px"></div>`;
}

export function promptGenerateDossier(){
  if(!_pid){ toast('Selecciona una misión primero.'); return; }
  const by=(window.prompt('Nombre real de quien genera los borradores (queda auditado):')||'').trim();
  if(!by) return;
  if(_RESERVED_RUN_BY.includes(by.toLowerCase())){ toast('"'+by+'" es un nombre reservado — usa tu nombre real.'); return; }
  _generateDossier(_pid, by);
}

async function _generateDossier(pid, by){
  toast('Generando borradores desde evidencia…');
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(pid)+'/validation-package/generate',{
      method:'POST', headers:headers(), body:JSON.stringify({generated_by:by})
    });
    const d=await r.json().catch(()=>({}));
    if(!r.ok){ toast('Error '+r.status+': '+(typeof d.detail==='object'?JSON.stringify(d.detail):(d.detail||'error'))); return; }
    let msg='Generados '+(d.generated||[]).length+' borradores';
    if((d.skipped_approved||[]).length) msg+=' · '+d.skipped_approved.length+' aprobados intactos';
    if((d.invalidated||[]).length) msg+=' · ⚠ '+d.invalidated.length+' aprobaciones invalidadas';
    toast(msg);
    window.refresh?.('validation');
  }catch(e){ toast('Error de red: '+e.message); }
}

export function promptApproveDoc(docId){
  if(!_pid) return;
  const by=(window.prompt('Aprobar "'+docId+'": nombre real del aprobador (queda auditado — NO es firma electrónica):')||'').trim();
  if(!by) return;
  if(_RESERVED_RUN_BY.includes(by.toLowerCase())){ toast('"'+by+'" es un nombre reservado — usa tu nombre real.'); return; }
  _approveDoc(_pid, docId, by);
}

async function _approveDoc(pid, docId, by){
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(pid)
      +'/validation-package/documents/'+encodeURIComponent(docId)+'/approve',{
      method:'POST', headers:headers(), body:JSON.stringify({approved_by:by})
    });
    const d=await r.json().catch(()=>({}));
    if(!r.ok){ toast('Error '+r.status+': '+(typeof d.detail==='object'?JSON.stringify(d.detail):(d.detail||'error'))); return; }
    toast('✓ '+docId+' aprobado por '+by);
    window.refresh?.('validation');
  }catch(e){ toast('Error de red: '+e.message); }
}

export async function viewValidationDoc(docId){
  if(!_pid) return;
  const el=document.getElementById('validation-doc-viewer'); if(!el) return;
  el.innerHTML='<div class="meta" style="color:var(--faint)">Cargando '+_gmpEscHtml(docId)+'…</div>';
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(_pid)
      +'/validation-package/documents/'+encodeURIComponent(docId),{headers:headers()});
    const d=await r.json().catch(()=>({}));
    if(!r.ok){ el.innerHTML='<div class="meta" style="color:var(--fail)">Error '+r.status+': '+_gmpEscHtml(d.detail||'error')+'</div>'; return; }
    const m=d.meta||{};
    el.innerHTML=`<div class="card">
      <div class="between" style="margin-bottom:8px">
        <b style="font-size:13px">${_gmpEscHtml(d.title)} <span class="meta mono" style="font-size:10px">(${_gmpEscHtml(d.doc_id)})</span></b>
        <button class="btn ghost" style="font-size:10px;padding:2px 8px" onclick="document.getElementById('validation-doc-viewer').innerHTML=''">Cerrar</button>
      </div>
      <div class="meta" style="font-size:10px;color:var(--faint);margin-bottom:8px">
        generado: ${_gmpEscHtml((m.generated_at||'—'))} por ${_gmpEscHtml(m.generated_by||'—')}
        · sha256: <span class="mono">${_gmpEscHtml((m.content_sha256||'').slice(0,12))}…</span>
        ${(m.evidence_sources||[]).length ? '· fuentes: '+_gmpEscHtml(m.evidence_sources.join(' · ')) : ''}</div>
      <pre style="background:var(--panel-2);border:1px solid var(--line);border-radius:8px;padding:12px;
        font-size:11px;max-height:480px;overflow:auto;white-space:pre-wrap">${_gmpEscHtml(d.content||'')}</pre>
    </div>`;
    el.scrollIntoView({behavior:'smooth',block:'nearest'});
  }catch(e){ el.innerHTML='<div class="meta" style="color:var(--fail)">'+e.message+'</div>'; }
}
