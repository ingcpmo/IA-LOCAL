/* W6.1 — Vista Validación GAMP 5: matriz de los 22 documentos del paquete
   CSV por misión. Estados solo desde disco; la brecha se muestra tal cual.
   W6.2 — generación asistida de borradores + aprobación humana por documento.
   Generar NUNCA aprueba; approved SOLO por acto humano con nombre real.
   W6.5 — propuestas de agente experto: el agente PROPONE con evidencia citada
   y verificada, el humano decide (accept ≠ approve — la aprobación formal
   sigue siendo el botón Aprobar de W6.2). */

import { API_BASE, headers } from './state.js';
import { toast, _gmpEscHtml } from './core.js';

const _RESERVED_RUN_BY=['human','agent','system','admin','user','factory'];

const ST = {
  approved: ['c-pass', 'aprobado'],
  draft: ['c-info', 'draft'],
  needs_human_review: ['c-warn', 'por revisar'],
  agent_proposed: ['c-accent', 'propuesta de agente'],
  missing_evidence: ['c-fail', 'sin evidencia'],
  not_started: ['c-mute', 'sin iniciar'],
};

// Estados del doc que admiten solicitar propuesta (espejo de ELIGIBLE_STATES
// del backend — la validación real la hace el POST, esto solo pinta el botón)
const _AGENT_ELIGIBLE = ['needs_human_review', 'agent_proposed'];

let _pid = null;   // misión del último render — la usan los handlers de acción

export function renderValidationPackage(d){
  const el = document.getElementById('validation-content'); if(!el) return;
  _pid = d.project_id || null;
  const c = d.counts || {};

  const rows = (d.documents || []).map(doc => {
    const [chip, label] = ST[doc.status] || ST.not_started;
    const canView = doc.status !== 'not_started';
    const canApprove = doc.status === 'draft' || doc.status === 'needs_human_review';
    const canAskAgent = !!doc.agent_routing && _AGENT_ELIGIBLE.includes(doc.status);
    const hasProposal = !!doc.agent_proposal;
    const missing = (doc.missing || []).length
      ? '<div class="meta" style="color:var(--fail);font-size:10px">falta: ' + _gmpEscHtml(doc.missing.join(', ')) + '</div>' : '';
    const propMeta = hasProposal
      ? '<div class="meta" style="color:var(--accent);font-size:10px">agente: '
        + _gmpEscHtml(doc.agent_proposal.agent || '') + ' · v' + _gmpEscHtml(String(doc.agent_proposal.version))
        + ' · ' + _gmpEscHtml(doc.agent_proposal.status || '')
        + ' · confianza ' + _gmpEscHtml(doc.agent_proposal.confidence || '—') + '</div>' : '';
    return `<div class="between" style="margin-bottom:7px">
      <div><b style="font-size:12.5px">${_gmpEscHtml(doc.title)}</b>
        ${doc.approved_by ? '<div class="meta" style="color:var(--human)">aprobado por ' + _gmpEscHtml(doc.approved_by) + '</div>' : ''}
        ${missing}${propMeta}</div>
      <div style="display:flex;gap:6px;align-items:center">
        ${canView ? `<button class="btn ghost" style="font-size:10px;padding:2px 8px" onclick="viewValidationDoc('${_gmpEscHtml(doc.doc_id)}')">Ver</button>` : ''}
        ${hasProposal ? `<button class="btn ghost" style="font-size:10px;padding:2px 8px;color:var(--accent)" onclick="viewAgentProposal('${_gmpEscHtml(doc.doc_id)}')">Propuesta</button>` : ''}
        ${canAskAgent ? `<button class="btn ghost" style="font-size:10px;padding:2px 8px" onclick="promptAgentProposal('${_gmpEscHtml(doc.doc_id)}')">Solicitar análisis de agente</button>` : ''}
        ${canApprove ? `<button class="btn human" style="font-size:10px;padding:2px 8px" onclick="promptApproveDoc('${_gmpEscHtml(doc.doc_id)}')">Aprobar</button>` : ''}
        <span class="chip ${chip}">${label}</span>
      </div>
    </div>`;
  }).join('');

  const inProgress = (c.draft ?? 0) + (c.needs_human_review ?? 0) + (c.missing_evidence ?? 0);
  el.innerHTML = `
    <div class="grid" style="grid-template-columns:repeat(6,1fr);margin-bottom:14px">
      <div class="card stat"><span class="k">Aprobados</span><span class="n" style="color:var(--pass)">${c.approved ?? 0}<small> / ${d.total}</small></span></div>
      <div class="card stat"><span class="k">Draft</span><span class="n" style="color:var(--primary)">${c.draft ?? 0}<small> / ${d.total}</small></span></div>
      <div class="card stat"><span class="k">Por revisar</span><span class="n" style="color:var(--warn)">${c.needs_human_review ?? 0}<small> / ${d.total}</small></span></div>
      <div class="card stat"><span class="k">Propuesta agente</span><span class="n" style="color:var(--accent)">${c.agent_proposed ?? 0}<small> / ${d.total}</small></span></div>
      <div class="card stat"><span class="k">Sin evidencia</span><span class="n" style="color:var(--fail)">${c.missing_evidence ?? 0}<small> / ${d.total}</small></span></div>
      <div class="card stat"><span class="k">Sin iniciar</span><span class="n" style="color:var(--muted)">${c.not_started ?? 0}<small> / ${d.total}</small></span></div>
    </div>
    <div class="between" style="margin-bottom:12px">
      <div class="meta" style="font-size:10.5px;color:var(--faint);max-width:640px">
        Generar produce BORRADORES desde evidencia real de la Factory (sin valor regulatorio).
        Nunca aprueba: <b>approved</b> requiere acto humano con nombre real y queda auditado.
        Si la evidencia de un doc aprobado cambia, su aprobación se invalida a "por revisar".
        El agente experto solo PROPONE análisis con evidencia citada y verificada — aceptar
        una propuesta NO aprueba el documento.</div>
      <button class="btn ghost" onclick="promptGenerateDossier()">${d.dossier_exists ? 'Regenerar borradores' : 'Generar dossier (asistido)'}</button>
    </div>
    ${d.dossier_exists ? '' : '<div class="banner warn"><span>⚠</span><div>' + _gmpEscHtml(d.note || 'sin dossier') + ' — el estado real del paquete es este, no se simula avance.</div></div>'}
    <div class="card">${rows || '<div class="meta" style="color:var(--faint)">sin documentos</div>'}</div>
    <div id="validation-proposal-viewer" style="margin-top:14px"></div>
    <div id="validation-doc-viewer" style="margin-top:14px"></div>`;
}

export function promptGenerateDossier(){
  if(!_pid){ toast('Selecciona una misión primero.'); return; }
  const by=(window.prompt('Nombre real de quien genera los borradores (queda auditado):')||'').trim();
  if(!by){ toast('Generación cancelada — no se envió nada (sin nombre).'); return; }
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
  if(!by){ toast('Aprobación cancelada — no se envió nada (sin nombre).'); return; }
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

/* ── W6.5 — propuestas de agente experto ─────────────────────────────────── */

const _PROPOSAL_URL=(pid,docId)=>API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(pid)
  +'/validation-package/documents/'+encodeURIComponent(docId)+'/agent-proposal';

// Espejo JS del CLAIM_RE del backend — solo para COLOREAR líneas; la
// clasificación real viene en claims.detail (verificador determinista Python)
const _CLAIM_LINE_RE=/^\s*[-*]\s*\[(E:\s*[^\]]+|SE|REF:\s*[^\]]*)\]\s*.+$/;
const _SUPPORT_COLOR={
  supported:'var(--pass)', partially_supported:'var(--warn)',
  unsupported:'var(--fail)', unverifiable:'var(--faint)',
};
export const _CONF_CHIP={alta:'c-pass', media:'c-warn', baja:'c-fail'};

export function promptAgentProposal(docId){
  if(!_pid){ toast('Selecciona una misión primero.'); return; }
  const by=(window.prompt('Solicitar análisis de agente para "'+docId+'".\n'
    +'Nombre real de quien solicita (queda auditado):')||'').trim();
  // Fase 0 W7 (hallazgo UX): jamás descartar en silencio — el diálogo nativo
  // puede volver vacío por cancelación O por supresión del navegador
  if(!by){ toast('Solicitud cancelada — no se envió nada (sin nombre).'); return; }
  if(_RESERVED_RUN_BY.includes(by.toLowerCase())){ toast('"'+by+'" es un nombre reservado — usa tu nombre real.'); return; }
  const guidance=(window.prompt('Instrucción opcional para el agente (vacío = ninguna):')||'').trim();
  _requestProposal(_pid, docId, by, guidance || null);
}

async function _requestProposal(pid, docId, by, guidance){
  toast('El agente está redactando la propuesta — puede tardar varios minutos (Ollama local)…');
  try{
    const r=await fetch(_PROPOSAL_URL(pid,docId),{
      method:'POST', headers:headers(),
      body:JSON.stringify({requested_by:by, guidance:guidance})
    });
    const d=await r.json().catch(()=>({}));
    if(!r.ok){ toast('Error '+r.status+': '+(typeof d.detail==='object'?JSON.stringify(d.detail):(d.detail||'error'))); return; }
    if(d.status==='format_invalid'){
      toast('⚠ La propuesta v'+d.version+' no cumplió el contrato de formato — archivada, el documento no cambió.');
    }else{
      toast('Propuesta v'+d.version+' generada · confianza '+(d.confidence||'—')
        +((d.flags||[]).length?' · ⚠ flags: '+d.flags.join(', '):''));
    }
    window.refresh?.('validation');
    viewAgentProposal(docId);
  }catch(e){ toast('Error de red: '+e.message); }
}

export function _claimsBar(c){
  return `<span style="color:var(--pass)">${c.supported ?? 0} supported</span> /
    <span style="color:var(--warn)">${c.partially_supported ?? 0} partially</span> /
    <span style="color:var(--fail)">${c.unsupported ?? 0} unsupported</span> /
    <span style="color:var(--faint)">${c.unverifiable ?? 0} unverifiable</span>`;
}

export function _renderResponse(response, detail){
  // Colorea cada viñeta-afirmación con el veredicto del verificador (en orden);
  // el texto del agente NUNCA se reescribe, solo se pinta.
  const claims=(detail||[]).slice();
  return (response||'').split('\n').map(line=>{
    const esc=_gmpEscHtml(line);
    if(_CLAIM_LINE_RE.test(line) && claims.length){
      const c=claims.shift();
      return '<span style="color:'+(_SUPPORT_COLOR[c.support]||'inherit')+'">'+esc+'</span>';
    }
    return esc;
  }).join('\n');
}

export async function viewAgentProposal(docId){
  if(!_pid) return;
  const el=document.getElementById('validation-proposal-viewer'); if(!el) return;
  el.innerHTML='<div class="meta" style="color:var(--faint)">Cargando propuesta de '+_gmpEscHtml(docId)+'…</div>';
  try{
    const r=await fetch(_PROPOSAL_URL(_pid,docId),{headers:headers()});
    const d=await r.json().catch(()=>({}));
    if(!r.ok){ el.innerHTML='<div class="meta" style="color:var(--fail)">Error '+r.status+': '+_gmpEscHtml(typeof d.detail==='object'?JSON.stringify(d.detail):(d.detail||'error'))+'</div>'; return; }

    const ag=d.agent||{}, mo=d.model||{}, pr=d.prompt||{}, co=d.corpus_sufficiency||{},
          cl=d.claims||{}, gov=d.governance||{}, dec=d.decision;
    const flags=(d.flags||[]);
    const decidable=d.status==='agent_proposed' && !dec;
    const docEsc=_gmpEscHtml(docId);

    el.innerHTML=`<div class="card" style="border-color:var(--accent)">
      <div class="between" style="margin-bottom:8px">
        <b style="font-size:13px">Propuesta de agente · <span class="mono">${docEsc}</span>
          <span class="chip c-accent" style="margin-left:6px">v${_gmpEscHtml(String(d.version))} · ${_gmpEscHtml(d.status||'')}</span>
          <span class="chip ${_CONF_CHIP[d.confidence]||'c-mute'}" style="margin-left:4px">confianza ${_gmpEscHtml(d.confidence||'—')} (computada)</span></b>
        <button class="btn ghost" style="font-size:10px;padding:2px 8px" onclick="document.getElementById('validation-proposal-viewer').innerHTML=''">Cerrar</button>
      </div>
      <div class="banner warn" style="margin-bottom:10px"><span>⚠</span><div>${_gmpEscHtml(d.regulatory_note||'PROPUESTA DE AGENTE — sin valor regulatorio hasta revisión y aprobación humana.')}</div></div>
      <div class="meta" style="font-size:10px;color:var(--faint);margin-bottom:4px">
        agente: <b>${_gmpEscHtml(ag.primary||'—')}</b>
        ${(ag.supporting||[]).length?' · revisión recomendada: '+_gmpEscHtml(ag.supporting.join(', ')):''}
        · modelo <span class="mono">${_gmpEscHtml(mo.name||'—')}</span>
        (temp ${_gmpEscHtml(String((mo.options||{}).temperature ?? '—'))}, num_predict ${_gmpEscHtml(String((mo.options||{}).num_predict ?? '—'))})</div>
      <div class="meta" style="font-size:10px;color:var(--faint);margin-bottom:4px">
        prompt set ${_gmpEscHtml(pr.set_version||'—')} · prompt agente v${_gmpEscHtml(pr.agent_prompt_version||'—')}
        · template <span class="mono">${_gmpEscHtml((pr.template_sha256||'').slice(0,12))}…</span>
        · rendered <span class="mono">${_gmpEscHtml((pr.rendered_sha256||'').slice(0,12))}…</span></div>
      <div class="meta" style="font-size:10px;color:var(--faint);margin-bottom:4px">
        corpus: <b>${_gmpEscHtml(co.level||'—')}</b> (${_gmpEscHtml(co.source||'—')})
        ${(co.pending||[]).length?' · pendiente: '+_gmpEscHtml(co.pending.join(', ')):''}
        · evidencia: ${_gmpEscHtml((d.evidence_sources||[]).map(s=>s.id).join(', '))}</div>
      <div class="meta" style="font-size:10px;margin-bottom:4px">afirmaciones: ${_claimsBar(cl)}</div>
      ${flags.length?'<div class="meta" style="font-size:10px;margin-bottom:4px">'+flags.map(f=>'<span class="chip c-fail" style="margin-right:4px">⚠ '+_gmpEscHtml(f)+'</span>').join('')+'</div>':''}
      <div class="meta" style="font-size:10px;color:var(--faint);margin-bottom:8px">
        solicitado por <span style="color:var(--human)">${_gmpEscHtml(gov.requested_by||'—')}</span>
        · ${_gmpEscHtml(gov.generated_at||'—')} · ${_gmpEscHtml(String(gov.latency_ms??'—'))} ms
        ${gov.format_retry?' · reintento de formato':''}
        ${gov.guidance?' · instrucción QA: “'+_gmpEscHtml(gov.guidance)+'”':''}</div>
      ${dec?'<div class="meta" style="font-size:10px;color:var(--human);margin-bottom:8px">decisión: <b>'+_gmpEscHtml(dec.decision||'')+'</b> por '+_gmpEscHtml(dec.decided_by||'')+' · '+_gmpEscHtml(dec.decided_at||'')+(dec.reason?' · motivo: “'+_gmpEscHtml(dec.reason)+'”':'')+'</div>':''}
      <pre style="background:var(--panel-2);border:1px solid var(--line);border-radius:8px;padding:12px;
        font-size:11px;max-height:480px;overflow:auto;white-space:pre-wrap">${_renderResponse(d.response, cl.detail)}</pre>
      ${decidable?`<div style="display:flex;gap:8px;margin-top:10px;align-items:center">
        <span class="meta" style="font-size:10px;color:var(--faint)">Decisión humana (queda auditada — NO es aprobación del documento):</span>
        <button class="btn human" style="font-size:10px;padding:3px 10px" onclick="decideAgentProposal('${docEsc}','accept')">Aceptar (incorpora al borrador)</button>
        <button class="btn ghost" style="font-size:10px;padding:3px 10px;color:var(--fail)" onclick="decideAgentProposal('${docEsc}','reject')">Rechazar</button>
        <button class="btn ghost" style="font-size:10px;padding:3px 10px" onclick="decideAgentProposal('${docEsc}','request_changes')">Pedir ajuste (regenera)</button>
      </div>`:''}
    </div>`;
    el.scrollIntoView({behavior:'smooth',block:'nearest'});
  }catch(e){ el.innerHTML='<div class="meta" style="color:var(--fail)">'+_gmpEscHtml(e.message)+'</div>'; }
}

export function decideAgentProposal(docId, decision){
  if(!_pid) return;
  const labels={accept:'ACEPTAR e incorporar al borrador (el doc vuelve a "por revisar")',
    reject:'RECHAZAR (la propuesta queda archivada)',
    request_changes:'PEDIR AJUSTE (regenera una nueva versión con tu instrucción — puede tardar varios minutos)'};
  const by=(window.prompt(labels[decision]+'\n\nNombre real de quien decide (queda auditado — NO es firma electrónica):')||'').trim();
  if(!by){ toast('Decisión cancelada — no se envió nada (sin nombre).'); return; }
  if(_RESERVED_RUN_BY.includes(by.toLowerCase())){ toast('"'+by+'" es un nombre reservado — usa tu nombre real.'); return; }
  let reason=null;
  if(decision!=='accept'){
    reason=(window.prompt(decision==='reject'?'Motivo del rechazo (obligatorio):'
      :'Instrucción de ajuste para el agente (obligatoria):')||'').trim();
    if(!reason){ toast('El motivo es obligatorio para '+decision+'.'); return; }
  }
  _decideProposal(_pid, docId, decision, by, reason);
}

async function _decideProposal(pid, docId, decision, by, reason){
  if(decision==='request_changes') toast('Regenerando propuesta con tu instrucción — puede tardar varios minutos…');
  try{
    const r=await fetch(_PROPOSAL_URL(pid,docId)+'/decision',{
      method:'POST', headers:headers(),
      body:JSON.stringify({decision:decision, decided_by:by, reason:reason})
    });
    const d=await r.json().catch(()=>({}));
    if(!r.ok){ toast('Error '+r.status+': '+(typeof d.detail==='object'?JSON.stringify(d.detail):(d.detail||'error'))); return; }
    toast('✓ '+decision+' registrado por '+by+' · doc → '+(d.doc_status||'—')
      +(d.new_proposal?' · nueva propuesta v'+d.new_proposal.version:''));
    window.refresh?.('validation');
    viewAgentProposal(docId);
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
