/* W5 — W1/W3: Mission detail panel — grupos 01-04, visores de evidencia
   lazy y acciones (marcar canónico, F5). Los grupos 05/06 viven en
   tests_console.js y gmp_dashboard.js. */

import { state, API_BASE, headers } from './state.js';
import { toast, _esc, _filterFile } from './core.js';
import { missionChip, refreshFlowDiagram } from './dash.js';
import { _renderGrp5_tests } from './tests_console.js';
import { _renderGrp6_gmpDashboard } from './gmp_dashboard.js';

export function openMissionDetail(pid){
  state.selectedMissionId=pid;  // W4/TAREA3: el flujo gobernado del dashboard sigue a esta misión
  document.getElementById('dp-title').textContent=pid;
  document.getElementById('dp-status-chip').innerHTML='<span class="chip c-mute">cargando…</span>';
  document.getElementById('dp-body').innerHTML='<div class="meta" style="color:var(--faint)">Cargando detalle…</div>';
  document.getElementById('detail-overlay').classList.add('open');
  document.getElementById('detail-panel').classList.add('open');
  if(state.connected) _loadDetail(pid);
  else _renderDetailOffline(pid);
  if(state.connected) refreshFlowDiagram();
}

export function closeDetail(){
  document.getElementById('detail-overlay').classList.remove('open');
  document.getElementById('detail-panel').classList.remove('open');
  state.selectedMissionId=null;  // W4/TAREA3: sin misión abierta -> banner "Selecciona una misión"
  if(state.connected) refreshFlowDiagram();
}

export async function _loadDetail(pid){
  const enc=encodeURIComponent(pid);
  // W3: cargar /summary primero (rápido, cacheable) + preflight en paralelo
  const [sumR, pfR] = await Promise.allSettled([
    fetch(API_BASE+'/api/v1/layer9/missions/'+enc+'/summary',{headers:headers()}).then(r=>r.ok?r.json():null),
    fetch(API_BASE+'/api/v1/layer8/missions/'+enc+'/f5/preflight',{headers:headers()}).then(r=>r.ok?r.json():null),
  ]);
  const summary=sumR.value, preflight=pfR.value;

  if(summary?.mission?.status){
    document.getElementById('dp-status-chip').innerHTML=missionChip(summary.mission.status);
  }

  document.getElementById('dp-body').innerHTML=
    _grp('estado','01 Estado',true)+
    _grp('evidencia','02 Evidencia',false)+
    _grp('agentes','03 Agentes',false)+
    _grp('acciones','04 Acciones',false)+
    _grp('pruebas','05 Pruebas Funcionales',false)+
    _grp('gmp_dashboard','06 Dashboard GMP',false);

  _renderGrp1(pid, summary, preflight);
  _renderGrp2(pid, summary);  // lazy subpanels — carga en expandir
  _renderGrp3_agents(pid);    // agentes: carga inmediata
  _renderGrp4(pid, preflight, summary);
  _renderGrp5_tests(pid);     // W4: catálogo de pruebas — carga inmediata (reader, no audita)
  _renderGrp6_gmpDashboard(pid); // W4.1: dashboard GMP + PDF — carga inmediata (reader, no audita)
}

export function _grp(id, label, open){
  return `<div class="grp-block">
    <button class="grp-toggle${open?' open':''}" onclick="toggleGrp(this,'${id}','${label}')">
      ${label}<span class="arrow">▶</span></button>
    <div class="grp-content${open?' open':''}" id="grp-${id}">
      <div class="meta" style="color:var(--faint)">cargando…</div>
    </div></div>`;
}

export function toggleGrp(btn, id, label){
  btn.classList.toggle('open');
  const c=btn.nextElementSibling;
  c.classList.toggle('open');
}

// ── 01 Estado: summary + preflight ───────────────────────────────────────────
export function _renderGrp1(pid, summary, pf){
  const el=document.getElementById('grp-estado'); if(!el) return;
  let html='';

  // Bloque summary rápido
  if(summary){
    const m=summary.mission||{};
    const hl=summary.headless||{};
    const ts=summary.tests||{};
    const rcs=summary.rcs||{};
    const dep=summary.deployment||{};
    const badgeDep=dep.health_ok?'c-pass':dep.exists?'c-warn':'c-mute';
    const badgeTests=ts.failed===0&&ts.passed>0?'c-pass':ts.failed>0?'c-fail':'c-mute';
    const badgeRcs=rcs.canonical?'c-accent':'c-mute';
    html+=`<div class="grid g2" style="margin-bottom:10px">
      <div class="card" style="padding:10px 12px">
        <div class="k">Misión</div>
        <div class="meta mono" style="line-height:1.8;margin-top:4px;font-size:11px">
          estado &nbsp;&nbsp; ${m.status||'—'}<br>
          cliente &nbsp; ${m.client_type||'—'}<br>
          aprobada &nbsp; ${(m.approved_at||'—').toString().slice(0,10)||'—'}<br>
          aprobado por &nbsp; ${m.approved_by||'—'}
        </div>
      </div>
      <div class="card" style="padding:10px 12px">
        <div class="k">Resumen</div>
        <div style="margin-top:6px;display:flex;flex-direction:column;gap:5px">
          <div class="between"><span class="meta" style="font-size:11px">Tests</span>
            <span class="chip ${badgeTests}" style="font-size:9px">${ts.passed||0} pass · ${ts.failed||0} fail</span></div>
          <div class="between"><span class="meta" style="font-size:11px">RC canónico</span>
            <span class="chip ${badgeRcs}" style="font-size:9px">${rcs.canonical?(rcs.canonical.slice(-12)):'—'}</span></div>
          <div class="between"><span class="meta" style="font-size:11px">Deployment</span>
            <span class="chip ${badgeDep}" style="font-size:9px">${dep.health_ok?'health ok':dep.exists?'existe':'no existe'}</span></div>
          <div class="between"><span class="meta" style="font-size:11px">Headless</span>
            <span class="chip c-info" style="font-size:9px">${hl.num_turns||0} turns · $${(hl.total_cost_usd||0).toFixed(2)}</span></div>
        </div>
      </div>
    </div>`;
  }

  // Checklist preflight F5
  if(pf){
    const ready=pf.ready_for_f5;
    const blockers=pf.blockers||[];
    html+=`<div class="between" style="margin:10px 0 6px">
      <div class="dp-sub" style="margin:0">Preflight F5</div>
      <span class="chip ${ready?'c-pass':blockers.length===1&&blockers[0]==='rc_canonical_marked'?'c-warn':'c-fail'}">${ready?'LISTO':''+blockers.length+' bloqueo(s)'}</span>
    </div>`;
    if(pf.next_action) html+=`<div class="meta" style="margin-bottom:6px;color:var(--warn);font-size:11px">${pf.next_action}</div>`;
    html+=(pf.checks||[]).map(c=>{
      const dot=c.ok?'var(--pass)':blockers.includes(c.id)?'var(--fail)':'var(--warn)';
      return `<div class="pf-line"><span class="pf-dot" style="background:${dot}"></span>
        <span class="pf-id">${c.id}</span>
        <span class="pf-detail">${(c.detail||'').replace(/</g,'&lt;')}</span></div>`;
    }).join('');
  } else {
    html+='<div class="meta" style="color:var(--faint);margin-top:8px">Sin datos de preflight.</div>';
  }
  el.innerHTML=html;
}

// ── 02 Evidencia: 7 subpaneles lazy ──────────────────────────────────────────
export function _renderGrp2(pid, summary){
  const el=document.getElementById('grp-evidencia'); if(!el) return;
  const ws=summary?.workspace||{};
  const rcs=summary?.rcs||{};
  const dep=summary?.deployment||{};
  const ts=summary?.tests||{};
  const hl=summary?.headless||{};
  const audit=summary?.audit||{};

  function sub(id, label, badge, badgeCls, lazyFn){
    return `<div class="ev-sub">
      <button class="ev-toggle" onclick="toggleEv(this,'ev-${id}-${_esc(pid)}',()=>${lazyFn})">
        <span class="ev-lbl">${label}</span>
        <span class="chip ${badgeCls||'c-mute'}" style="font-size:9px;padding:1px 7px">${badge}</span>
        <span class="arrow" style="font-size:9px;margin-left:auto">▶</span>
      </button>
      <div class="ev-body" id="ev-${id}-${_esc(pid)}" style="display:none"></div>
    </div>`;
  }

  const enc=_esc(pid);
  el.innerHTML=
    sub('design','Diseño',`${summary?.design?.files_count||0} archivos`,'c-info',`loadEv_design('${enc}')`) +
    sub('code','Código generado',`${ws.files_visible||0} arch · ${ws.py_files||0} .py`,'c-info',`loadEv_code('${enc}')`) +
    sub('tests','Tests',ts.failed===0&&ts.passed>0?`${ts.passed} pass`:'ver',(ts.failed===0&&ts.passed>0?'c-pass':ts.failed>0?'c-fail':'c-mute'),`loadEv_tests('${enc}')`) +
    sub('headless','Headless log',hl.num_turns?`${hl.num_turns} turns · $${(hl.total_cost_usd||0).toFixed(2)}`:'ver','c-info',`loadEv_headless('${enc}')`) +
    sub('rcs','Release Candidates',`${rcs.count||0} RCs`,rcs.canonical?'c-accent':'c-mute',`loadEv_rcs('${enc}')`) +
    sub('deploy','Deployment Docker',dep.health_ok?'health ok':dep.exists?'existe':'no existe',dep.health_ok?'c-pass':dep.exists?'c-warn':'c-mute',`loadEv_deploy('${enc}')`) +
    sub('audit','Auditoría',`${audit.event_count_filtered||0} eventos`,'c-accent',`loadEv_audit('${enc}')`);
}

export function toggleEv(btn, bodyId, lazyFn){
  const body=document.getElementById(bodyId); if(!body) return;
  const isOpen=body.style.display!=='none';
  body.style.display=isOpen?'none':'block';
  btn.classList.toggle('open', !isOpen);
  if(!isOpen && !body.dataset.loaded){
    body.dataset.loaded='1';
    body.innerHTML='<div class="meta" style="color:var(--faint);padding:6px 0">Cargando…</div>';
    try{ lazyFn(); }catch(e){ body.innerHTML='<div class="meta" style="color:var(--fail)">Error: '+e.message+'</div>'; }
  }
}

export async function loadEv_design(pid){
  const el=document.getElementById('ev-design-'+pid); if(!el) return;
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(pid)+'/design',{headers:headers()});
    if(!r.ok){ el.innerHTML='<div class="meta" style="color:var(--fail)">Error '+r.status+'</div>'; return; }
    const d=await r.json();
    el.innerHTML=(d.files||[]).map(f=>`<div class="gate-line">
      <span class="gid mono fname" onclick="loadDesignFile('${_esc(pid)}','${f.name.replace(/'/g,"\\'")}')">${f.name}</span>
      <span style="color:var(--faint);font-size:10.5px">${(f.size/1024).toFixed(1)}k</span>
    </div>`).join('')+
    `<div id="dfviewer-${pid}" class="fviewer" style="display:none;margin-top:8px"></div>`;
  }catch(e){ el.innerHTML='<div class="meta" style="color:var(--fail)">'+e.message+'</div>'; }
}

export async function loadDesignFile(pid, fname){
  const el=document.getElementById('dfviewer-'+pid); if(!el) return;
  el.style.display='block'; el.textContent='Cargando '+fname+'…';
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(pid)+'/design/file?path='+encodeURIComponent(fname),{headers:headers()});
    if(!r.ok){ el.textContent='Error '+r.status; return; }
    const d=await r.json();
    el.textContent=(d.content||'').slice(0,6000);
  }catch(e){ el.textContent='Error: '+e.message; }
}

export async function loadEv_code(pid){
  const el=document.getElementById('ev-code-'+pid); if(!el) return;
  try{
    const r=await fetch(API_BASE+'/api/v1/layer8/workspaces/'+encodeURIComponent(pid)+'/tree',{headers:headers()});
    if(!r.ok){ el.innerHTML='<div class="meta" style="color:var(--fail)">Error '+r.status+'</div>'; return; }
    const d=await r.json();
    const files=(d.files||[]).filter(f=>_filterFile(f.path));
    const byDir={};
    files.forEach(f=>{ const dir=f.path.includes('/')?f.path.split('/')[0]:'(raíz)'; (byDir[dir]=byDir[dir]||[]).push(f); });
    el.innerHTML=`<div class="ftree">` +
      Object.entries(byDir).map(([dir,fs])=>
        `<div style="color:var(--muted);font-size:11px">${dir}/</div>`+
        fs.map(f=>`<div style="padding-left:12px"><span class="fname"
          onclick="loadFileContent('${_esc(pid)}','${f.path.replace(/'/g,"\\'")}')"
          style="font-size:11px">${f.path.split('/').pop()}</span>
          <span style="color:var(--faint);font-size:10.5px">${(f.size/1024).toFixed(1)}k</span></div>`).join('')
      ).join('') + `</div><div id="fviewer-${pid}" class="fviewer" style="display:none;margin-top:6px"></div>`;
  }catch(e){ el.innerHTML='<div class="meta" style="color:var(--fail)">'+e.message+'</div>'; }
}

export async function loadEv_tests(pid){
  const el=document.getElementById('ev-tests-'+pid); if(!el) return;
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(pid)+'/tests',{headers:headers()});
    if(!r.ok){ el.innerHTML='<div class="meta" style="color:var(--fail)">Error '+r.status+'</div>'; return; }
    const d=await r.json();
    if(!d.found){ el.innerHTML='<div class="meta" style="color:var(--faint)">Sin test_report.json</div>'; return; }
    const ok=d.failed===0&&d.passed>0;
    el.innerHTML=`<div class="between" style="margin-bottom:6px">
      <span class="meta mono" style="font-size:11px">${d.passed} pass · ${d.failed} fail · rc=${d.returncode}</span>
      <span class="chip ${ok?'c-pass':'c-fail'}">${ok?'OK':'FALLA'}</span>
    </div>`+
    (d.note?`<div class="meta" style="color:var(--faint);font-size:10.5px;margin-bottom:6px">${d.note}</div>`:'')  +
    `<pre style="background:var(--panel-2);border:1px solid var(--line);border-radius:6px;padding:10px;
      font-size:10.5px;max-height:200px;overflow:auto;white-space:pre-wrap;word-break:break-all;margin:0">${
      (d.output||'').slice(0,4000).replace(/</g,'&lt;')}</pre>`;
  }catch(e){ el.innerHTML='<div class="meta" style="color:var(--fail)">'+e.message+'</div>'; }
}

export async function loadEv_headless(pid){
  const el=document.getElementById('ev-headless-'+pid); if(!el) return;
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(pid)+'/headless',{headers:headers()});
    if(!r.ok){ el.innerHTML='<div class="meta" style="color:var(--fail)">Error '+r.status+'</div>'; return; }
    const d=await r.json();
    if(!d.found){ el.innerHTML='<div class="meta" style="color:var(--faint)">Sin headless log</div>'; return; }
    const res=d.result||{};
    const ok=res.returncode===0;
    const mb=res.model_breakdown||{};
    const breakdownHtml=Object.entries(mb).map(([m,s])=>
      `<div class="gate-line"><span class="gid mono" style="font-size:10px">${m}</span>
       <span style="color:var(--faint);font-size:10.5px">in=${s.inputTokens||0} out=${s.outputTokens||0} $${(s.costUSD||0).toFixed(4)}</span></div>`
    ).join('');
    el.innerHTML=`<div class="grid g2" style="margin-bottom:8px">
      <div class="meta mono" style="font-size:11px;line-height:1.9">
        returncode &nbsp; <span style="color:${ok?'var(--pass)':'var(--fail)'}">${res.returncode}</span><br>
        turns &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ${res.num_turns||0}<br>
        duración &nbsp;&nbsp; ${((res.duration_ms||0)/1000).toFixed(0)}s<br>
        costo total &nbsp; <b>$${(res.total_cost_usd||0).toFixed(4)}</b><br>
        terminal &nbsp;&nbsp; ${res.terminal_reason||'—'}
      </div>
      <div><div class="k" style="margin-bottom:4px">Modelos</div>${breakdownHtml}</div>
    </div>`+
    (res.result_text?`<pre style="background:var(--panel-2);border:1px solid var(--line);border-radius:6px;
      padding:10px;font-size:10.5px;max-height:200px;overflow:auto;white-space:pre-wrap;word-break:break-all;margin:0">${
      res.result_text.slice(0,2000).replace(/</g,'&lt;')}</pre>`:'');
  }catch(e){ el.innerHTML='<div class="meta" style="color:var(--fail)">'+e.message+'</div>'; }
}

export async function loadEv_rcs(pid){
  const el=document.getElementById('ev-rcs-'+pid); if(!el) return;
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(pid)+'/rcs',{headers:headers()});
    if(!r.ok){ el.innerHTML='<div class="meta" style="color:var(--fail)">Error '+r.status+'</div>'; return; }
    const d=await r.json();
    if(!d.count){ el.innerHTML='<div class="meta" style="color:var(--faint)">Sin RCs</div>'; return; }
    el.innerHTML=(d.rcs||[]).map(rc=>{
      const isCanon=rc.is_canonical===true;
      const cls=rc.status==='approved'?(isCanon?'c-accent':'c-pass'):rc.status==='rejected'?'c-fail':'c-mute';
      const arts=(rc.artifacts||[]).map(a=>`<span class="fname" style="font-size:10px;margin-left:12px"
        onclick="loadRcFile('${_esc(pid)}','${rc.rc_id.replace(/'/g,"\\'")}','artifacts/${a.name.replace(/'/g,"\\'")}')"
        >${a.name}</span>`).join('');
      return `<div style="border-bottom:1px solid var(--line-soft);padding:6px 0">
        <div class="gate-line" style="border:0;padding:0">
          <span class="gid mono">${rc.version||'?'} ${isCanon?'★':''}</span>
          <span class="chip ${cls}" style="font-size:9px">${rc.status||'?'}</span>
        </div>
        <div class="meta mono" style="font-size:10px;color:var(--faint);margin-top:2px">
          ${isCanon?'<b style="color:var(--accent)">CANÓNICO</b> · ':''
          }aprobado por: ${rc.approved_by||'—'} · ${(rc.decided_at||'').slice(0,10)||'pendiente'}
        </div>
        ${arts?`<div style="margin-top:4px">${arts}</div>`:''}
      </div>`;
    }).join('') + `<div id="rcfviewer-${pid}" class="fviewer" style="display:none;margin-top:6px"></div>`;
  }catch(e){ el.innerHTML='<div class="meta" style="color:var(--fail)">'+e.message+'</div>'; }
}

export async function loadRcFile(pid, rcId, path){
  const el=document.getElementById('rcfviewer-'+pid); if(!el) return;
  el.style.display='block'; el.textContent='Cargando…';
  try{
    const url=`${API_BASE}/api/v1/layer9/missions/${encodeURIComponent(pid)}/rc/${encodeURIComponent(rcId)}/file?path=${encodeURIComponent(path)}`;
    const r=await fetch(url,{headers:headers()});
    if(!r.ok){ el.textContent='Error '+r.status; return; }
    const d=await r.json();
    el.textContent=(d.content||'').slice(0,6000);
  }catch(e){ el.textContent='Error: '+e.message; }
}

export async function loadEv_deploy(pid){
  const el=document.getElementById('ev-deploy-'+pid); if(!el) return;
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(pid)+'/deployment',{headers:headers()});
    if(!r.ok){ el.innerHTML='<div class="meta" style="color:var(--fail)">Error '+r.status+'</div>'; return; }
    const d=await r.json();
    if(!d.exists){ el.innerHTML='<div class="meta" style="color:var(--faint)">Deployment no existe</div>'; return; }
    const ok=d.health_ok;
    el.innerHTML=`<div class="between" style="margin-bottom:8px">
      <span class="meta mono" style="font-size:11px">puerto: ${d.api_port||'?'}</span>
      <span class="chip ${ok?'c-pass':'c-warn'}">${ok?'health ok':'no responde'}</span>
    </div>`+
    (d.docs_url?`<div class="meta" style="margin-bottom:6px;font-size:11px">docs: <a href="${d.docs_url}" target="_blank" style="color:var(--primary-h)">${d.docs_url}</a></div>`:'') +
    `<div class="k" style="margin:6px 0 3px">Archivos (${d.files_visible||0})</div>`+
    (d.files||[]).slice(0,30).map(f=>`<div class="gate-line"><span class="gid mono fname" style="font-size:10.5px"
      onclick="loadDepFile('${_esc(pid)}','${f.path.replace(/'/g,"\\'")}')">${f.path}</span>
      <span style="color:var(--faint);font-size:10px">${(f.size/1024).toFixed(1)}k</span></div>`).join('') +
    `<div id="depfviewer-${pid}" class="fviewer" style="display:none;margin-top:6px"></div>`;
  }catch(e){ el.innerHTML='<div class="meta" style="color:var(--fail)">'+e.message+'</div>'; }
}

export async function loadDepFile(pid, path){
  const el=document.getElementById('depfviewer-'+pid); if(!el) return;
  el.style.display='block'; el.textContent='Cargando '+path+'…';
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(pid)+'/deployment/file?path='+encodeURIComponent(path),{headers:headers()});
    if(!r.ok){ el.textContent='Error '+r.status; return; }
    const d=await r.json();
    el.textContent=(d.content||'').slice(0,6000);
  }catch(e){ el.textContent='Error: '+e.message; }
}

export async function loadEv_audit(pid){
  const el=document.getElementById('ev-audit-'+pid); if(!el) return;
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(pid)+'/audit?limit=50',{headers:headers()});
    if(!r.ok){ el.innerHTML='<div class="meta" style="color:var(--fail)">Error '+r.status+'</div>'; return; }
    const d=await r.json();
    if(!d.count){ el.innerHTML='<div class="meta" style="color:var(--faint)">Sin eventos de auditoría</div>'; return; }
    el.innerHTML='<div class="chain" style="border-radius:6px">' +
      (d.events||[]).slice(0,20).map(e=>{
        const ts=(e.timestamp||'').slice(11,19)||'—';
        const ev=e.event_type||'?';
        const h=(e.entry_hash||'').replace('sha256:','');
        const hS=h.length>8?h.slice(0,4)+'…'+h.slice(-4):'————';
        return `<div class="link" style="grid-template-columns:80px 1fr auto">
          <span class="t">${ts}</span><span class="ev" style="font-size:11px">${ev}</span>
          <span class="h">${hS}</span></div>`;
      }).join('') + '</div>'+
      `<div class="meta" style="font-size:10.5px;color:var(--faint);margin-top:4px">Mostrando ${Math.min(d.count,20)} de ${d.total} eventos</div>`;
  }catch(e){ el.innerHTML='<div class="meta" style="color:var(--fail)">'+e.message+'</div>'; }
}

// ── 03 Agentes ────────────────────────────────────────────────────────────────
export async function _renderGrp3_agents(pid){
  const el=document.getElementById('grp-agentes'); if(!el) return;
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(pid)+'/agents',{headers:headers()});
    if(!r.ok){ el.innerHTML='<div class="meta" style="color:var(--faint)">Sin datos de agentes</div>'; return; }
    const d=await r.json();
    const s=d.summary||{};
    let html=`<div class="between" style="margin-bottom:8px">
      <span class="meta">${s.profiles_inherited||0} profiles heredados + ${s.new_agents||0} agent(s) nuevo(s)</span>
      <span class="chip c-info">${(d.agents||[]).length} total</span>
    </div>
    <div class="tbl-wrap"><table>
      <tr><th>Agent ID</th><th>Decisión</th><th>Routing key</th></tr>
      ${(d.agents||[]).map(a=>`<tr>
        <td class="mono">${a.agent_id||'?'}</td>
        <td><span class="chip ${a.is_inherited?'c-pass':'c-human'}" style="font-size:9px">${
          a.is_inherited?'PROFILE HEREDADO':'AGENT NUEVO'}</span></td>
        <td class="mono" style="color:var(--faint);font-size:11px">${a.routing_key||'—'}</td>
      </tr>`).join('')}
    </table></div>`;
    if(d.routing_notes){
      html+=`<div class="meta" style="font-size:10.5px;color:var(--faint);margin-top:8px">${d.routing_notes}</div>`;
    }
    el.innerHTML=html;
  }catch(e){ el.innerHTML='<div class="meta" style="color:var(--fail)">'+e.message+'</div>'; }
}

// ── 04 Acciones ───────────────────────────────────────────────────────────────
export async function _renderGrp4(pid, pf, summary){
  const el=document.getElementById('grp-acciones'); if(!el) return;
  const rcs=(summary?.rcs)||{};
  // Cargar lista de RCs para el selector de canónico
  let rcList=[];
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/projects/'+encodeURIComponent(pid)+'/rcs',{headers:headers()});
    if(r.ok){ const d=await r.json(); rcList=d.rcs||[]; }
  }catch(e){}
  const hasApprovedRCs=rcList.filter(r=>r.status==='approved');
  const canonical=rcList.find(r=>r.is_canonical===true);
  const ready=pf?.ready_for_f5;
  let html='';

  if(hasApprovedRCs.length){
    html+=`<div class="dp-sub">Marcar RC canónico</div>
    <div style="margin-bottom:10px">
      <select id="canonical-sel-${pid}" style="background:var(--panel-2);border:1px solid var(--line);
        color:var(--text);border-radius:6px;padding:5px 8px;font-family:var(--mono);font-size:11px;width:100%">
        ${hasApprovedRCs.map(r=>`<option value="${r.rc_id}"${r.is_canonical?' selected':''}>
          ${r.version} — ${r.rc_id.slice(-16)}${r.is_canonical?' ★':''}</option>`).join('')}
      </select>
      <div class="field" style="margin-top:8px">
        <label>Confirmado por (nombre real)</label>
        <input id="canonical-by-${pid}" placeholder="p.ej. Cesar" autocomplete="off">
      </div>
      <div class="actions" style="margin-top:8px">
        <button class="btn pass" onclick="submitMarkCanonical('${pid}')">Marcar como canónico</button>
        ${canonical?`<span class="chip c-accent" style="margin-left:4px">Actual: ${canonical.version}</span>`:''}
      </div>
    </div>`;
  }

  html+=`<div class="dp-sub" style="margin-top:10px">Docker F5</div>
  <button class="btn${ready?' pass':' ghost'}" style="${ready?'':'opacity:.5;cursor:not-allowed'}"
    ${ready?`onclick="confirmF5('${pid}')"`:'disabled title="Resolver blockers antes de F5"'}>
    Preparar Docker F5
  </button>`;
  if(!ready&&pf?.blockers?.length){
    html+=`<div class="meta" style="margin-top:6px;color:var(--warn);font-size:11px">
      Blockers: ${pf.blockers.join(', ')}</div>`;
  }

  html+=`<div class="dp-sub" style="margin-top:12px">Modificar misión</div>
  <button class="btn ghost" onclick="toast('Modificar misión: usar POST /api/v1/layer9/missions/${pid}/revise')">
    Ver endpoint de revisión</button>`;

  el.innerHTML=html;
}

export async function loadFileContent(pid, path){
  const vid=`fviewer-${pid}`;
  const el=document.getElementById(vid); if(!el) return;
  el.style.display='block';
  el.textContent='Cargando…';
  try{
    const r=await fetch(API_BASE+'/api/v1/layer8/workspaces/'+encodeURIComponent(pid)+'/file?path='+encodeURIComponent(path),{headers:headers()});
    if(!r.ok){ el.textContent='Error '+r.status+' al cargar '+path; return; }
    const d=await r.json();
    el.textContent=(d.content||'').slice(0,4000);
  }catch(e){ el.textContent='Error: '+e.message; }
}

export async function submitMarkCanonical(pid){
  const rcId=(document.getElementById('canonical-sel-'+pid)?.value||'').trim();
  const by=(document.getElementById('canonical-by-'+pid)?.value||'').trim();
  if(!rcId){ toast('Selecciona un RC.'); return; }
  if(!by){ toast('Ingresa el nombre real del responsable.'); return; }
  const reserved=['human','agent','system','admin','capa8','capa9','layer8'];
  if(reserved.includes(by.toLowerCase())){ toast('"'+by+'" es un nombre reservado — usa tu nombre real.'); return; }
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/review/'+encodeURIComponent(rcId)+'/mark-canonical',{
      method:'POST', headers:headers(), body:JSON.stringify({marked_by:by})
    });
    if(r.ok){
      toast('RC marcado como canónico ✓ · '+by);
      setTimeout(()=>_loadDetail(pid),500);
    } else {
      const e=await r.json().catch(()=>({}));
      toast('Error '+r.status+': '+(typeof e.detail==='object'?JSON.stringify(e.detail):e.detail||'error'));
    }
  }catch(e){ toast('Error de red: '+e.message); }
}

export function confirmF5(pid){
  toast('F5 aún no disponible — pendiente autorización explícita de Cesar. (W2)');
}

export function _renderDetailOffline(pid){
  document.getElementById('dp-body').innerHTML=
    '<div class="meta" style="color:var(--warn)">Sin conexión. Conecta el factory-api para ver detalle en vivo.</div>';
}
