/* W5 — creación y decisiones de misión (U10/U11). */

import { API_BASE, headers } from './state.js';
import { toast } from './core.js';
import { missionChip } from './dash.js';
import { refresh } from './refresh.js';

/* ---- U10: Mission approve/return reales ----
   approved_by/rejected_by/returned_by ya NO viajan en el body (Paquete 2,
   hallazgo M) -- el backend resuelve quien decide desde X-Identity-Key
   (headers(), state.js). Sin identity key valida, el POST falla 401. */
export async function submitMissionDecision(projectId, action){
  try{
    let url, body, msg;
    if(action==='approve'){
      url='/api/v1/layer9/missions/'+encodeURIComponent(projectId)+'/approve';
      body={decision_origin:'human_confirmed'};
      msg='Misión aprobada ✓';
    } else if(action==='reject'){
      url='/api/v1/layer9/missions/'+encodeURIComponent(projectId)+'/reject';
      body={reason:'rechazo de misión · vía Mission Control'};
      msg='Misión rechazada';
    } else {
      url='/api/v1/layer9/missions/'+encodeURIComponent(projectId)+'/return';
      body={reason:'devolución a ajustes · vía Mission Control'};
      msg='Misión devuelta a ajustes';
    }
    const r=await fetch(API_BASE+url,{
      method:'POST', headers:headers(), body:JSON.stringify(body)
    });
    if(r.ok){
      toast(msg);
      setTimeout(()=>refresh('approve'),600);
    } else {
      const err=await r.json().catch(()=>({}));
      toast('Error '+r.status+': '+(err.detail||'ver consola'));
    }
  }catch(e){ toast('Error de red: '+e.message); }
}

/* ---- render: approve list (view 03) ---- */
export function renderApproveMissions(ms){
  const el=document.getElementById('approve-list'); if(!el) return;
  const pending=ms.filter(m=>!['approved','completed','rejected'].includes(m.status));
  if(!pending.length){
    el.innerHTML='<div class="card"><div class="meta" style="color:var(--pass)">✓ Sin misiones pendientes de decisión.</div></div>';
    return;
  }
  el.innerHTML=pending.map(m=>{
    return `
    <div class="card" style="margin-bottom:14px">
      <div class="between"><h3 class="mono">${m.project_id}</h3>${missionChip(m.status)}</div>
      <div class="hr"></div>
      <div class="meta">${(m.objective||'').slice(0,120).replace(/</g,'&lt;')}…</div>
      <div class="meta mono" style="margin-top:8px">created_at · ${(m.created_at||'').slice(0,16).replace('T',' ')}Z</div>
      <div class="hr"></div>
      <div class="meta" style="color:var(--faint)">Quien decide se resuelve de tu IDENTITY KEY de sesión (Paquete 2).</div>
      <div class="actions" style="margin-top:12px">
        <button class="btn human" onclick="submitMissionDecision('${m.project_id}','approve')">Aprobar misión</button>
        <button class="btn warn" onclick="submitMissionDecision('${m.project_id}','return')">Devolver</button>
        <button class="btn fail" onclick="submitMissionDecision('${m.project_id}','reject')">Rechazar</button>
      </div>
    </div>`;
  }).join('');
}

/* ---- U11: Crear misión — form real ---- */
export async function submitCreateMission(e){
  e.preventDefault();
  const pid=(document.getElementById('create-pid')?.value||'').trim().toLowerCase().replace(/\s+/g,'_');
  const objective=(document.getElementById('create-objective')?.value||'').trim();
  const clientType=(document.getElementById('create-client-type')?.value||'').trim()||'pharma_mfg_site';
  const regRaw=(document.getElementById('create-regulatory')?.value||'').split(',').map(s=>s.trim()).filter(Boolean);
  const docsRaw=(document.getElementById('create-docs')?.value||'').split(',').map(s=>s.trim()).filter(Boolean);
  const autonomy=document.getElementById('create-autonomy')?.value||'controlled_full';
  const actionsRaw=(document.getElementById('create-actions')?.value||'').split(',').map(s=>s.trim()).filter(Boolean);
  const exitRaw=(document.getElementById('create-exit')?.value||'');
  const constraints=exitRaw.split(/[\n,]/).map(s=>s.trim()).filter(Boolean);

  if(!pid){ toast('project_id es obligatorio.'); return false; }
  if(!/^[a-z0-9_]+$/.test(pid)){ toast('project_id: solo minúsculas, números y guiones bajos.'); return false; }
  if(!objective){ toast('El objetivo es obligatorio.'); return false; }
  if(!regRaw.length){ toast('Alcance regulatorio: ingresa al menos un valor (p.ej. 21_CFR_PART_11).'); return false; }
  if(!docsRaw.length){ toast('Documentos requeridos: ingresa al menos uno (p.ej. ICH Q10).'); return false; }
  if(!constraints.length){ toast('Criterios de salida: ingresa al menos uno.'); return false; }

  const docs={};
  docsRaw.forEach(d=>{ docs[d]='pending'; });

  const DEFAULT_ACTIONS=['analyze_requirement','design_agents','create_workspace','run_claude_code',
    'generate_code','generate_tests','run_quality_gates','create_release'];
  const allowed=actionsRaw.length?actionsRaw:DEFAULT_ACTIONS;

  const payload={
    project_id: pid, client_type: clientType, objective: objective,
    regulatory_scope: regRaw, documents: docs, constraints: constraints,
    mission_approval:{
      autonomy_level: autonomy, allowed_actions: allowed,
      stop_conditions:['quality_gate_fail','resource_limit_exceeded','claude_execution_failed'],
      final_human_decision_required:['deploy_docker'],
      deploy_docker_if_gates_pass: false
    }
  };

  const btn=document.querySelector('#create-mission-form button[type="submit"]');
  if(btn){ btn.disabled=true; btn.textContent='Creando…'; }
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions',{
      method:'POST', headers:headers(), body:JSON.stringify(payload)
    });
    if(r.status===201){
      const d=await r.json();
      toast('Misión creada: '+d.project_id+' · status='+d.status);
      document.getElementById('create-mission-form')?.reset();
      setTimeout(()=>refresh('approve'),800);
    } else {
      const err=await r.json().catch(()=>({}));
      if(r.status===409){
        toast('Ya existe una misión con project_id "'+pid+'".');
      } else {
        let msg;
        if(Array.isArray(err.detail)){
          msg=err.detail.map(function(e){ return e.msg||JSON.stringify(e); }).join(' · ');
        } else {
          msg=err.detail||JSON.stringify(err);
        }
        toast('Error '+r.status+': '+String(msg).slice(0,200));
      }
    }
  }catch(ex){ toast('Error de red: '+ex.message); }
  finally{ if(btn){ btn.disabled=false; btn.textContent='Crear misión (borrador)'; } }
  return false;
}
