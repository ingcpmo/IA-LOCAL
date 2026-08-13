/* W5 — navegación entre vistas, conexión y dispatcher de refresco.
   Importa renderers de los módulos de vista; los módulos de vista que
   disparan refresh() lo importan de aquí (ciclo tolerado: solo function
   declarations, ninguna llamada en tiempo de evaluación de módulos). */

import { state, API_BASE, headers } from './state.js';
import {
  renderStacks, renderMissions, renderAuditSeal, renderAuditChain,
  updateHeadless, renderResources, renderRisks, renderSidebarDeploy,
  refreshFlowDiagram,
} from './dash.js';
import { renderApproveMissions } from './missions.js';
import { renderReview } from './review.js';
import { renderW5Decisions, renderW5Error } from './w5_decisions.js';
import { renderGovernance, renderGovernanceError } from './governance.js';
import { refreshPipeline, loadClaudeStatus } from './pipeline.js';
import { renderExecStatus, renderExecMissions, renderExecReview, renderExecRisks } from './exec.js';
import { renderRisksView, renderReadiness } from './risks_view.js';
import { renderAgentTasks, renderRegSources, renderCaseMemory } from './intel_views.js';
import { renderMissionDetail } from './mission_detail_view.js';
import { renderMissionAgents, renderAgentsCatalog } from './agents_view.js';
import { renderReports } from './reports_view.js';
import { renderValidationPackage } from './validation_view.js';
import { renderRemediationDirectives } from './remediation.js';
import { fillMissionSelect, toast } from './core.js';

const TITLES={
  exec:["Executive Overview","mission-control / executive"],
  dash:["Panel operativo","mission-control / overview"],
  detail:["Detalle de misión","mission-control / missions / detail"],
  agentsv:["Agentes","mission-control / agents"],
  reports:["Reportes","mission-control / reports"],
  validation:["Validación GAMP 5","mission-control / validation"],
  create:["Crear misión","mission-control / missions / new"],
  approve:["Aprobación de misión","mission-control / approvals"],
  pipeline:["Pipeline Capa 8","mission-control / layer8 / pipeline"],
  review:["Revisión humana","mission-control / review-queue"],
  w5:["Decisiones humanas W5","mission-control / governance / w5-decisions"],
  gobierno:["Gobernanza de decisiones","mission-control / governance / decisions"],
  audit:["Auditoría","mission-control / audit / chain"],
  risks:["Riesgos y Readiness","mission-control / risks"],
  system:["Estado del sistema","mission-control / system"],
  tasks:["Tareas de agentes · MODO DISEÑO","mission-control / intel / agent-tasks"],
  sources:["Fuentes regulatorias · MODO DISEÑO","mission-control / intel / sources"],
  memory:["Memoria de casos · memoria ligera gobernada","mission-control / intel / case-memory"],
  remediacion:["Remediación — directivas y adjudicación","mission-control / governance / remediation"],
};

export function show(v,btn){
  document.querySelectorAll('.view').forEach(s=>s.classList.remove('on'));
  document.getElementById('v-'+v).classList.add('on');
  document.querySelectorAll('#nav button').forEach(x=>x.classList.remove('on'));
  (btn||document.querySelector('#nav button[data-v="'+v+'"]')).classList.add('on');
  const t=TITLES[v];
  document.getElementById('vtitle').textContent=t[0];
  document.getElementById('vcrumb').textContent=t[1];
  document.getElementById('rail').classList.remove('open');
  if(state.connected) refresh(v);
}

export async function connect(){
  state.apiKey=document.getElementById('apikey').value.trim();
  const conn=document.getElementById('conn');
  if(!state.apiKey){ conn.innerHTML='modo <b>diseño</b>'; state.connected=false; return; }
  try{
    const r=await fetch(API_BASE+"/health");
    if(!r.ok) throw new Error();
    state.connected=true;
    conn.innerHTML='<span class="dotpass">●</span> conectado';
    refresh('dash');
  }catch(e){
    state.connected=false;
    conn.innerHTML='<span class="dotwarn">●</span> sin factory-api · <b>diseño</b>';
  }
}

/* W6.1 — llena un selector con las misiones actuales y devuelve el pid activo */
async function missionSelect(selectId){
  try{
    const r=await fetch(API_BASE+"/api/v1/layer9/missions",{headers:headers()});
    if(!r.ok) return null;
    return fillMissionSelect(selectId, await r.json());
  }catch(e){ return null; }
}

/* Corrección operativa (diagnóstico Mission Control 2026-07-14):
   #pipeline-project vivía como <option> estáticos en el HTML
   (r6_change_control/lab_qc_project/c8_alcoa_validator), nunca poblado por
   JS — misiones nuevas (p.ej. gmpai_document_validation) no aparecían nunca
   en el selector, y r6_change_control ya no tiene workspace real (misión
   rechazada y archivada) -> 404 permanente en tree/artifacts/file, dejando
   "conectar para ver" pese a estar conectado. Se puebla desde
   /api/v1/workspaces (solo proyectos con workspace real en disco). */
async function workspaceSelect(selectId){
  try{
    const r=await fetch(API_BASE+"/api/v1/workspaces",{headers:headers()});
    if(!r.ok) return null;
    const ws=await r.json();
    return fillMissionSelect(selectId, (ws||[]).map(w=>({project_id:w.project_id})));
  }catch(e){ return null; }
}

/* Corrección operativa: antes, cualquier 401/403 (p.ej. api key vencida o
   rotada) dejaba el header "conectado" intacto mientras cada panel fallaba
   en silencio (if(r.ok) sin rama else) -> "conectado" arriba, módulos
   internos vacíos/"conectar para ver" abajo, sin explicación. Ahora se
   detecta en los dos fetches de mayor tráfico (status/full y missions,
   presentes en casi toda navegación) y se refleja honestamente. */
function _checkAuthFailure(r){
  if(r.status===401||r.status===403){
    state.connected=false;
    const conn=document.getElementById('conn');
    if(conn) conn.innerHTML='<span class="dotwarn">●</span> sesión expirada · reconectar';
    toast('Sesión expirada (HTTP '+r.status+') — ingresa la API key de nuevo.');
    return true;
  }
  return false;
}

/* ---- main refresh dispatcher ---- */
export async function refresh(v){
  try{
    if(v==='dash'||v==='system'){
      const r=await fetch(API_BASE+"/api/v1/status/full",{headers:headers()});
      if(_checkAuthFailure(r)) return;
      if(r.ok){ const d=await r.json();
        const av=d.summary?.audit_verified, ae=d.summary?.audit_entries;
        const ahash=d.summary?.audit_hash_errors??0, achain=d.summary?.audit_chain_errors??0;
        if(av!=null){
          const el=document.getElementById('m-audit');
          const isFork=!av&&ahash===0&&achain>0;
          el.style.color=av?'var(--pass)':isFork?'var(--warn)':'var(--fail)';
          el.innerHTML=(av?'OK':isFork?'WARN':'FALLA')+'<small> · '+(ae||0)+'</small>';
        }
        renderStacks(d, v==='dash'?'dash-stacks':'sys-stacks');
        const note=document.getElementById('dash-note');
        if(note) note.style.display='none';
      }
    }
    if(v==='dash'||v==='approve'){
      const r=await fetch(API_BASE+"/api/v1/layer9/missions",{headers:headers()});
      if(_checkAuthFailure(r)) return;
      if(r.ok){ const ms=await r.json();
        document.getElementById('m-active').textContent=Array.isArray(ms)?ms.length:'—';
        const pend=ms.filter(m=>!['approved'].includes(m.status));
        document.getElementById('m-pending').textContent=pend.length;
        if(v==='dash') renderMissions(ms);
        if(v==='approve') renderApproveMissions(ms);
        if(v==='dash'){
          await refreshFlowDiagram();
        }
      }
    }
    if(v==='dash'||v==='review'){
      const r=await fetch(API_BASE+"/api/v1/layer9/review-queue",{headers:headers()});
      if(_checkAuthFailure(r)) return;
      if(r.ok){ const d=await r.json();
        document.getElementById('m-rc').innerHTML=(d.summary?.pending??0)+'<small> / revisar</small>';
        if(v==='review') renderReview(d.pending||[]);
      } else if(v==='review'){
        /* Antes: sin rama else, un 404/500 dejaba el placeholder
           "(conectar para ver cola de revisión…)" mientras el header seguía
           en "conectado" -- indistinguible de no estar conectado. */
        const el=document.getElementById('review-list');
        if(el) el.innerHTML='<div class="card"><div class="meta" style="color:var(--fail)">'
          +'Error HTTP '+r.status+' al leer la cola de revisión (no es un problema de conexión).</div></div>';
      }
    }
    if(v==='w5'){
      const r=await fetch(API_BASE+"/api/v1/layer9/w5-decisions",{headers:headers()});
      if(_checkAuthFailure(r)) return;
      if(r.ok){ renderW5Decisions(await r.json()); }
      else {
        const err=await r.json().catch(()=>({}));
        renderW5Error(r.status, typeof err.detail==='string'?err.detail:'');
      }
    }
    if(v==='gobierno'){
      const r=await fetch(API_BASE+"/api/v1/layer9/governance/state",{headers:headers()});
      if(_checkAuthFailure(r)) return;
      if(r.ok){ renderGovernance(await r.json()); }
      else {
        /* §10: ningun estado de gobernanza parcial. Un valor por defecto seria
           indistinguible de uno real, que es la ambiguedad que este trabajo
           existe para eliminar. */
        const err=await r.json().catch(()=>({}));
        renderGovernanceError(r.status, typeof err.detail==='string'?err.detail:'');
      }
    }
    if(v==='pipeline'||v==='dash'){
      const r=await fetch(API_BASE+"/api/v1/layer8/status",{headers:headers()});
      if(r.ok){ const d=await r.json(); updateHeadless(d); }
    }
    if(v==='pipeline'){
      await workspaceSelect('pipeline-project');
      await refreshPipeline();
      await loadClaudeStatus();
    }
    if(v==='dash'){
      const rd=await fetch(API_BASE+"/api/v1/deployments/lab_qc_project",{headers:headers()});
      if(rd.ok){ renderSidebarDeploy(await rd.json()); }
      const rr=await fetch(API_BASE+"/api/v1/status/risks",{headers:headers()});
      if(rr.ok){ renderRisks(await rr.json()); }
    }
    if(v==='audit'){
      const rv=await fetch(API_BASE+"/api/v1/audit/verify",{headers:headers()});
      if(rv.ok){ const d=await rv.json(); renderAuditSeal(d); }
      const re=await fetch(API_BASE+"/api/v1/audit/entries?limit=20",{headers:headers()});
      if(re.ok){ const entries=await re.json(); renderAuditChain(entries); }
    }
    if(v==='system'){
      const r=await fetch(API_BASE+"/api/v1/status/resources",{headers:headers()});
      if(r.ok){ const d=await r.json(); renderResources(d); }
    }
    if(v==='exec'){
      const rf=await fetch(API_BASE+"/api/v1/status/full",{headers:headers()});
      if(rf.ok){ const d=await rf.json(); renderExecStatus(d); renderStacks(d,'ex-stacks'); }
      const rm=await fetch(API_BASE+"/api/v1/layer9/missions",{headers:headers()});
      if(rm.ok){ renderExecMissions(await rm.json()); }
      const rq=await fetch(API_BASE+"/api/v1/layer9/review-queue",{headers:headers()});
      if(rq.ok){ renderExecReview(await rq.json()); }
      const rr=await fetch(API_BASE+"/api/v1/status/risks",{headers:headers()});
      if(rr.ok){ renderExecRisks(await rr.json()); }
    }
    if(v==='risks'){
      const r=await fetch(API_BASE+"/api/v1/status/risks",{headers:headers()});
      if(r.ok){ renderRisksView(await r.json()); }
      const pid=await missionSelect('readiness-project');
      if(pid){
        const rr=await fetch(API_BASE+"/api/v1/layer9/missions/"+pid+"/readiness",{headers:headers()});
        if(rr.ok){ renderReadiness(await rr.json()); }
      }
    }
    if(v==='detail'){
      const pid=await missionSelect('detail-project');
      if(pid){
        const r=await fetch(API_BASE+"/api/v1/layer9/missions/"+pid+"/summary",{headers:headers()});
        if(r.ok){ renderMissionDetail(await r.json()); }
      }
    }
    if(v==='agentsv'){
      const pid=await missionSelect('agentsv-project');
      if(pid){
        const rm=await fetch(API_BASE+"/api/v1/layer9/missions/"+pid+"/agents",{headers:headers()});
        if(rm.ok){ renderMissionAgents(await rm.json()); }
      }
      const rc=await fetch(API_BASE+"/api/v1/agents",{headers:headers()});
      if(rc.ok){ renderAgentsCatalog(await rc.json()); }
    }
    if(v==='reports'){
      const pid=await missionSelect('reports-project');
      if(pid){
        const r=await fetch(API_BASE+"/api/v1/layer9/missions/"+pid+"/reports",{headers:headers()});
        if(r.ok){ renderReports(await r.json(), pid); }
      }
    }
    if(v==='validation'){
      const pid=await missionSelect('validation-project');
      if(pid){
        const r=await fetch(API_BASE+"/api/v1/layer9/missions/"+pid+"/validation-package",{headers:headers()});
        if(r.ok){ renderValidationPackage(await r.json()); }
      }
    }
    if(v==='tasks'){
      const r=await fetch(API_BASE+"/api/v1/layer9/agent-tasks",{headers:headers()});
      if(r.ok){ renderAgentTasks(await r.json()); }
    }
    if(v==='sources'){
      const r=await fetch(API_BASE+"/api/v1/layer9/regulatory-sources",{headers:headers()});
      if(r.ok){ renderRegSources(await r.json()); }
    }
    if(v==='memory'){
      const r=await fetch(API_BASE+"/api/v1/layer9/case-memory",{headers:headers()});
      if(r.ok){ renderCaseMemory(await r.json()); }
    }
    if(v==='remediacion'){
      const r=await fetch(API_BASE+"/api/v1/layer9/remediation/directives",{headers:headers()});
      if(r.ok){ renderRemediationDirectives(await r.json()); }
      else {
        const el=document.getElementById('remediation-directives-list');
        if(el) el.innerHTML='<div class="card"><div class="meta" style="color:var(--fail)">Error HTTP '+r.status+' al leer las directivas.</div></div>';
      }
    }
  }catch(e){
    /* Corrección operativa: antes se tragaba en silencio cualquier error
       (red, CORS, JSON inválido) dejando el panel con contenido estático
       obsoleto sin ninguna señal al usuario. Ahora se reporta. */
    console.error('[mission-control] refresh("'+v+'") falló:', e);
    toast('Error actualizando "'+v+'": '+(e?.message||e));
  }
}
