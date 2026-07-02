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
import { refreshPipeline, loadClaudeStatus } from './pipeline.js';
import { renderExecStatus, renderExecMissions, renderExecReview, renderExecRisks } from './exec.js';
import { renderRisksView } from './risks_view.js';
import { renderAgentTasks, renderRegSources, renderCaseMemory } from './intel_views.js';

const TITLES={
  exec:["Executive Overview","mission-control / executive"],
  dash:["Panel operativo","mission-control / overview"],
  create:["Crear misión","mission-control / missions / new"],
  approve:["Aprobación de misión","mission-control / approvals"],
  pipeline:["Pipeline Capa 8","mission-control / layer8 / pipeline"],
  review:["Revisión humana","mission-control / review-queue"],
  audit:["Auditoría","mission-control / audit / chain"],
  risks:["Riesgos","mission-control / risks"],
  system:["Estado del sistema","mission-control / system"],
  tasks:["Tareas de agentes · MODO DISEÑO","mission-control / intel / agent-tasks"],
  sources:["Fuentes regulatorias · MODO DISEÑO","mission-control / intel / sources"],
  memory:["Memoria de casos · MODO DISEÑO","mission-control / intel / case-memory"]
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

/* ---- main refresh dispatcher ---- */
export async function refresh(v){
  try{
    if(v==='dash'||v==='system'){
      const r=await fetch(API_BASE+"/api/v1/status/full",{headers:headers()});
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
      if(r.ok){ const d=await r.json();
        document.getElementById('m-rc').innerHTML=(d.summary?.pending??0)+'<small> / revisar</small>';
        if(v==='review') renderReview(d.pending||[]);
      }
    }
    if(v==='pipeline'||v==='dash'){
      const r=await fetch(API_BASE+"/api/v1/layer8/status",{headers:headers()});
      if(r.ok){ const d=await r.json(); updateHeadless(d); }
    }
    if(v==='pipeline'){
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
  }catch(e){ /* mantiene datos de diseño */ }
}
