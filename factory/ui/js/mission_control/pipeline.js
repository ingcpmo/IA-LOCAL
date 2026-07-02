/* W5 — vista Pipeline Capa 8: workspace, jobs, gates, headless y
   configuración del modelo Claude (V2). */

import { state, API_BASE, headers } from './state.js';
import { toast } from './core.js';
import { refresh } from './refresh.js';

/* ---- U3: pipeline design artifacts ---- */
export function renderPipelineDesign(artifacts){
  const el=document.getElementById('pipeline-design-content'); if(!el) return;
  const cnt=document.getElementById('pipeline-design-count');
  if(cnt) cnt.textContent=(artifacts||[]).length+' artefactos';
  if(!artifacts||!artifacts.length){
    el.innerHTML='<div style="color:var(--faint)">Sin artefactos en workspace.</div>'; return;
  }
  el.innerHTML=artifacts.map(a=>{
    const kb=(a.size_bytes/1024).toFixed(1);
    return '<div class="gate-line"><span class="gid mono">'+a.file+'</span><span class="chip c-pass">'+kb+' k</span></div>';
  }).join('');
}

/* ---- U4: pipeline quality gates ---- */
export function renderPipelineGates(report){
  const el=document.getElementById('gates-list'); if(!el) return;
  const sum=document.getElementById('gates-summary');
  const s=report.summary||{};
  if(sum){
    const ok=s.FAIL===0&&s.PASS>0;
    sum.className='chip '+(ok?'c-pass':s.FAIL>0?'c-fail':'c-mute');
    sum.textContent='P:'+( s.PASS||0)+' F:'+(s.FAIL||0)+(s.SKIPPED?' S:'+(s.SKIPPED):'');
  }
  const gates=report.gates||[];
  if(!gates.length){
    el.innerHTML='<div class="meta" style="color:var(--faint)">Sin reporte en este workspace.</div>'; return;
  }
  const chip=st=>st==='PASS'?'c-pass':st==='FAIL'?'c-fail':'c-mute';
  el.innerHTML=gates.map(g=>'<div class="gate-line"><span class="gid">'+(g.gate||'—')+'</span><span class="chip '+chip(g.status)+'">'+g.status+'</span></div>').join('');
}

/* ---- render: workspace tree (pipeline) ---- */
export function renderWorkspaceTree(data){
  const el=document.getElementById('workspace-tree'); if(!el) return;
  const cnt=document.getElementById('ws-file-count');
  if(cnt) cnt.textContent=data.file_count+' archivos';
  if(!data.files||!data.files.length){ el.textContent='(workspace vacio)'; return; }
  const byDir={};
  data.files.forEach(function(f){
    const parts=f.path.split('/');
    const dir=parts.length>1?parts[0]:'(raiz)';
    if(!byDir[dir]) byDir[dir]=[];
    byDir[dir].push(f);
  });
  el.innerHTML=Object.entries(byDir).map(function(entry){
    const dir=entry[0], files=entry[1];
    return '<div style="color:var(--muted);margin-top:4px">'+dir+'/</div>'+
      files.map(function(f){
        const name=f.path.split('/').pop();
        const kb=(f.size/1024).toFixed(1);
        return '<div style="padding-left:12px;color:var(--text)">'+name+' <span style="color:var(--faint)">'+kb+'k</span></div>';
      }).join('');
  }).join('');
}

/* ---- render: pipeline jobs ---- */
export function renderPipelineJobs(jobs){
  const el=document.getElementById('pipeline-jobs'); if(!el) return;
  const cnt=document.getElementById('pipeline-jobs-count');
  if(cnt) cnt.textContent=jobs.length+' jobs';
  if(!jobs.length){
    el.innerHTML='<div class="meta" style="color:var(--faint)">Sin jobs para este proyecto.</div>'; return;
  }
  const sc=function(s){
    var m={completed:'c-pass',failed:'c-fail',running:'c-info',pending:'c-mute'};
    return '<span class="chip '+(m[s]||'c-mute')+'">'+s+'</span>';
  };
  el.innerHTML=[].concat(jobs).reverse().slice(0,8).map(function(j){
    var jt=j.job_type||j.job_id.slice(0,8);
    var ts=(j.created_at||'').slice(0,16).replace('T',' ')+'Z';
    var err=j.error?' \xb7 '+String(j.error).slice(0,40):'';
    return '<div class="gate-line"><span class="gid">'+jt+'</span>'+sc(j.status)+'</div>'+
      '<div class="meta mono" style="font-size:10.5px;padding-bottom:4px">'+ts+err+'</div>';
  }).join('');
}

/* ---- pipeline refresh: tree + jobs + artifacts for selected project ---- */
export async function refreshPipeline(){
  var proj=(document.getElementById('pipeline-project')||{}).value||'r6_change_control';
  try{
    var rt=await fetch(API_BASE+'/api/v1/layer8/workspaces/'+proj+'/tree',{headers:headers()});
    if(rt.ok) renderWorkspaceTree(await rt.json());
    var rj=await fetch(API_BASE+'/api/v1/layer8/jobs?project_id='+proj,{headers:headers()});
    if(rj.ok) renderPipelineJobs(await rj.json());
    var ra=await fetch(API_BASE+'/api/v1/layer8/missions/'+proj+'/artifacts',{headers:headers()});
    if(ra.ok){ var ad=await ra.json(); renderPipelineDesign(ad.artifacts||[]); }
    var rg=await fetch(API_BASE+'/api/v1/layer8/workspaces/'+proj+'/file?path=quality_gates_report.json',{headers:headers()});
    if(rg.ok){ try{ var gf=await rg.json(); renderPipelineGates(JSON.parse(gf.content)); }catch(e){} }
    else{ renderPipelineGates({}); }
  }catch(e){}
}

/* W5: wrapper para el onchange del selector de proyecto (antes inline
   `if(CONNECTED)refreshPipeline()` — CONNECTED ya no es global). */
export function refreshPipelineIfConnected(){ if(state.connected) refreshPipeline(); }

/* ---- U11: Ver logs headless ---- */
export async function viewHeadlessLogs(){
  if(!state.connected){ toast('Sin conexión — no se pueden cargar logs.'); return; }
  const proj=(document.getElementById('pipeline-project')||{}).value||'r6_change_control';
  try{
    const r=await fetch(API_BASE+'/api/v1/layer8/missions/'+encodeURIComponent(proj)+'/headless/logs',{headers:headers()});
    if(!r.ok){ toast('Error '+r.status+' al cargar logs de '+proj); return; }
    const d=await r.json();
    const lines=Array.isArray(d.lines)?d.lines:(d.content||'').split('\n');
    const txt=lines.length?lines.slice(-40).join('\n'):'(sin entradas de log)';
    const box=document.getElementById('headless-log-box');
    if(box){ box.textContent=txt; box.style.display='block'; }
    else { toast('Logs (últimas 40 líneas):\n'+txt.slice(0,400)); }
  }catch(e){ toast('Error de red: '+e.message); }
}

/* ---- U10: Devolver headless a OFF ---- */
export async function submitHeadlessOff(){
  const actor=(document.getElementById('headless-operator')?.value||'').trim();
  if(!actor){ toast('Ingresa el nombre real del operador.'); return; }
  if(actor.toLowerCase()==='human'){ toast('"human" no es válido — usa un nombre real.'); return; }
  try{
    const r=await fetch(API_BASE+'/api/v1/layer8/headless/config',{
      method:'POST', headers:headers(),
      body:JSON.stringify({enabled:false, approved_by:actor, timeout_seconds:600})
    });
    if(r.ok){ toast('Headless → OFF · operador: '+actor); refresh('pipeline'); }
    else { const e=await r.json().catch(()=>({})); toast('Error '+r.status+': '+(e.detail||'ver consola')); }
  }catch(e){ toast('Error de red: '+e.message); }
}

// === V2: Claude model config ===
export async function loadClaudeStatus(){
  if(!state.connected) return;
  try{
    const r=await fetch(API_BASE+'/api/v1/layer8/claude/status',{headers:headers()});
    if(!r.ok) return;
    const d=await r.json();

    const badge=document.getElementById('active-model-badge');
    if(badge) badge.textContent=d.active_model||'—';

    const sel=document.getElementById('claude-model-select');
    if(sel && d.available_models){
      sel.innerHTML=d.available_models.map(m=>
        `<option value="${m.id}"${m.id===d.active_model?' selected':''}>${m.label}</option>`
      ).join('');
    }

    const installed=d.cli_installed;
    const authBadge=document.getElementById('cli-auth-badge');
    if(authBadge){ authBadge.textContent=installed?'instalado':'no encontrado'; authBadge.className='chip '+(installed?'c-pass':'c-warn'); }
    const instEl=document.getElementById('cli-installed-val');
    if(instEl) instEl.textContent=installed?'sí':'no';
    const verEl=document.getElementById('cli-version-val');
    if(verEl) verEl.textContent=d.cli_version||'—';
    const modEl=document.getElementById('cli-model-val');
    if(modEl) modEl.textContent=d.active_model||'—';

  }catch(e){ console.warn('claude/status no disponible:',e); }
}

let _modelChanging=false;
export async function submitModelChange(){
  if(_modelChanging) return;
  const model=document.getElementById('claude-model-select')?.value;
  const changedBy=(document.getElementById('claude-model-changed-by')?.value||'').trim();
  const statusEl=document.getElementById('model-change-status');

  if(!model){ if(statusEl) statusEl.textContent='Selecciona un modelo'; return; }
  if(!changedBy){ if(statusEl) statusEl.textContent='Escribe tu nombre real'; return; }
  const reserved=['human','agent','system','admin','user','factory'];
  if(reserved.includes(changedBy.toLowerCase())){
    if(statusEl) statusEl.textContent='Nombre genérico rechazado — usa nombre real';
    return;
  }

  _modelChanging=true;
  if(statusEl) statusEl.textContent='Actualizando…';
  try{
    const r=await fetch(API_BASE+'/api/v1/layer8/claude/config',{
      method:'POST', headers:headers(),
      body:JSON.stringify({model, changed_by:changedBy})
    });
    const data=await r.json().catch(()=>({}));
    if(r.ok && data.active_model){
      const badge=document.getElementById('active-model-badge');
      if(badge) badge.textContent=data.active_model;
      const modEl=document.getElementById('cli-model-val');
      if(modEl) modEl.textContent=data.active_model;
      if(statusEl) statusEl.textContent='✓ Actualizado · auditado';
      toast('Modelo: '+data.active_model+' · '+data.changed_by);
    } else {
      if(statusEl) statusEl.textContent=data.detail||'Error al actualizar';
    }
  }catch(e){ if(statusEl) statusEl.textContent='Error de red: '+e.message; }
  _modelChanging=false;
}
// === fin V2 ===
