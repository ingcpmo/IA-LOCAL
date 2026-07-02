/* W5 — renders del panel general y vistas de solo lectura (stacks, misiones,
   riesgos, auditoría, recursos, headless chip, flujo gobernado U3/W4). */

import { state, API_BASE, headers } from './state.js';
import { chipOk, chipTxt } from './core.js';

/* ---- render: stacks grid (dash + system) ---- */
export function renderStacks(d,gridId){
  const el=document.getElementById(gridId); if(!el) return;
  const b1=d.docker_1_base?.health, b2=d.docker_2_factory?.health;
  const customs=Array.isArray(d.custom_solutions)?d.custom_solutions:[];
  const rows=[
    {name:'Base · 8000', ok:b1?.reachable,
     detail:b1?.reachable?Object.entries(b1.body||{}).filter(([k])=>k!=='timestamp').map(([k,v])=>k+'·'+v).join(' '):(b1?.error||'error')},
    {name:'Factory · 9000', ok:b2?.reachable,
     detail:b2?.reachable?'factory-api → ok':(b2?.error||'error')},
    ...customs.map(c=>({
      name:c.project_id+' · '+c.api_port, ok:c.health?.reachable,
      detail:c.health?.reachable
        ?Object.entries(c.health.body||{}).filter(([k])=>k!=='timestamp').map(([k,v])=>k+'·'+v).join(' ')
        :(c.health?.error||'no reachable')
    }))
  ];
  el.className='grid g'+Math.min(rows.length,3);
  el.innerHTML=rows.map(s=>`
    <div class="card"><div class="between"><h3>${s.name}</h3><span class="chip ${chipOk(s.ok)}">${chipTxt(s.ok)}</span></div>
    <div class="hr"></div><div class="meta mono">${s.detail||'—'}</div></div>`).join('');
}

/* ---- render: missions list (dash) ---- */
export function missionChip(status){
  const m={approved:['c-pass','aprobada'],parcial_headless_interrupted:['c-warn','interrumpida'],
    pending_approval:['c-info','pend. aprobación'],in_progress:['c-info','en curso'],
    rejected:['c-fail','rechazada'],completed:['c-pass','completada']};
  const [cls,lbl]=m[status]||['c-mute',status||'—'];
  return `<span class="chip ${cls}">${lbl}</span>`;
}

export function renderMissions(ms){
  const el=document.getElementById('missions-list'); if(!el) return;
  el.innerHTML=ms.map(m=>`
    <div class="between mis-row" style="margin-bottom:6px;padding:5px 6px"
         onclick="openMissionDetail('${m.project_id.replace(/'/g,"\\'")}')" title="Ver detalle">
      <div><b class="mono">${m.project_id}</b>
      <div class="meta">${(m.objective||'').slice(0,55).replace(/</g,'&lt;')}…</div></div>
      ${missionChip(m.status)}
    </div>`).join('');
  const active=ms.find(m=>!['approved','rejected','completed'].includes(m.status));
  const amEl=document.getElementById('dash-active-mission');
  if(amEl&&active) amEl.textContent=active.project_id;
}

/* ---- render: audit seal + chain (view 06) ---- */
export function renderAuditSeal(d){
  const el=document.getElementById('audit-seal-text'); if(!el) return;
  const ok=d.verified&&d.part11_compliant;
  const isFork=!ok&&(d.hash_errors??0)===0&&(d.chain_errors??0)>0;
  const seal=el.parentElement?.querySelector('.seal');
  if(seal){
    seal.textContent=ok?'✓':'!';
    seal.style.borderColor=ok?'var(--accent)':isFork?'var(--warn)':'var(--fail)';
    seal.style.color=ok?'var(--accent)':isFork?'var(--warn)':'var(--fail)';
  }
  const estado=ok?'Cadena verificada':isFork?'Fork concurrente — contenido auténtico':'⚠ Hash corrupto — cadena inválida';
  el.innerHTML=`<b>${estado}</b> · ${d.log_count} entradas · ${d.hash_errors} errores de hash · ${d.chain_errors} errores de cadena · part11_compliant: ${d.part11_compliant}`;
  el.style.color=ok?'#d7c79a':isFork?'var(--warn)':'var(--fail)';
}

export function renderAuditChain(entries){
  const el=document.getElementById('audit-chain'); if(!el) return;
  if(!entries||!entries.length){
    el.innerHTML='<div style="padding:12px 16px;color:var(--faint);font-size:12px">Sin entradas disponibles.</div>';
    return;
  }
  el.innerHTML=[...entries].reverse().slice(0,20).map(e=>{
    const ts=(e.timestamp||'').slice(11,19)||'—';
    const ev=e.event_type||'?';
    const proj=e.project_id||'';
    const h=(e.entry_hash||'').replace('sha256:','');
    const hShort=h.length>8?h.slice(0,4)+'…'+h.slice(-4):'————';
    const isHuman=ev.includes('approval')&&ev.includes('granted');
    const evSpan=isHuman?`<span style="color:var(--human)">${ev}</span>`:ev;
    return `<div class="link"><span class="t">${ts}</span><span class="ev">${evSpan}</span><span class="meta mono">${proj}</span><span class="h">${hShort}</span></div>`;
  }).join('');
}

/* ---- render: headless state (pipeline chip + sidebar) ---- */
export function updateHeadless(d){
  const chip=document.getElementById('hl-state');
  if(chip){
    const on=d.headless_enabled;
    chip.className='chip '+(on?'c-warn':'c-pass');
    chip.textContent=on?'activo':'OFF';
  }
  const sb=document.getElementById('sidebar-hl');
  if(sb){
    const on=d.headless_enabled;
    const jobs=d.jobs||{};
    sb.innerHTML=`<span class="${on?'dotwarn':'dotpass'}">●</span> headless: ${on?'activo':'OFF'} · jobs: ${jobs.running||0} corriendo`;
  }
}

/* ---- render: system resources ---- */
export function renderResources(d){
  const ram=d.memory, disk=d.disk, cs=d.custom_solutions;
  const $=(id)=>document.getElementById(id);
  if(ram){
    const el=$('sys-ram'); if(el) el.innerHTML=(ram.used_pct||0).toFixed(1)+'%<small> usado</small>';
    const ch=$('sys-ram-chip'); if(ch){ ch.className='chip '+(ram.ok?'c-pass':'c-warn'); ch.textContent=ram.ok?'dentro de política':'revisar'; }
  }
  if(disk){
    const el=$('sys-disk'); if(el) el.innerHTML=(disk.used_pct||0).toFixed(1)+'%<small> usado</small>';
    const ch=$('sys-disk-chip'); if(ch){ ch.className='chip '+(disk.ok?'c-pass':'c-warn'); ch.textContent=disk.ok?'ok':'revisar'; }
  }
  if(cs){
    const el=$('sys-custom'); if(el) el.innerHTML=cs.active+'<small> / '+cs.max_allowed+' máx</small>';
    const ch=$('sys-custom-chip'); if(ch){ ch.className='chip '+(cs.ok?'c-pass':'c-warn'); ch.textContent=cs.ok?'ok':'revisar'; }
  }
}

/* ---- U4: risks card ---- */
export function renderRisks(data){
  const el=document.getElementById('risks-list'); if(!el) return;
  const cnt=document.getElementById('risks-count');
  const risks=data.risks||[];
  if(cnt){ cnt.textContent=risks.length; cnt.className='chip '+(risks.length?'c-warn':'c-pass'); }
  if(!risks.length){
    el.innerHTML='<div style="color:var(--pass)">Sin riesgos activos detectados.</div>'; return;
  }
  const sev={'alto':'c-fail','medio':'c-warn','info':'c-info'};
  el.innerHTML=risks.map(r=>'<div><span class="chip '+(sev[r.severity]||'c-mute')+'" style="margin-right:8px">'+r.severity+'</span>'+r.description.replace(/</g,'&lt;')+'</div>').join('');
}

/* ---- render: sidebar deployment info ---- */
export function renderSidebarDeploy(d){
  const el=document.getElementById('sidebar-deploy'); if(!el) return;
  const v=d.version||'—';
  const port=d.api_port||'';
  const ok=d.status==='approved';
  const proj=(d.project_id||'').replace('_project','');
  el.innerHTML='<span class="'+(ok?'dotpass':'dotwarn')+'">&#x25CF;</span> '+proj+' '+(port?port+' \xb7 ':'')+v;
}

/* ---- U3: flow diagram ---- */
const FLOW_NODES=[
  {ix:'01',lab:'Misi\xf3n',dn:'aprobada',ac:'revisando',td:'pendiente'},
  {ix:'02',lab:'Dise\xf1o',dn:'generado',ac:'generando',td:'pendiente'},
  {ix:'03',lab:'Headless',dn:'completado',ac:'en curso',td:'pendiente'},
  {ix:'04',lab:'C\xf3digo',dn:'generado',ac:'generando',td:'pendiente'},
  {ix:'05',lab:'Tests',dn:'pass',ac:'corriendo',td:'pendiente'},
  {ix:'06',lab:'Quality gates',dn:'pass',ac:'corriendo',td:'pendiente'},
  {ix:'07',lab:'Release cand.',dn:'emitido',ac:'generando',td:'pendiente'},
  {ix:'08',lab:'Aprobaci\xf3n',dn:'aprobado',ac:'humano',td:'humano',gate:true},
];

// W4/TAREA3: cada nodo se evalúa de forma INDEPENDIENTE contra datos reales
// de /summary (+ gates report) — no una escalera secuencial. Un artefacto
// tardío (p.ej. gates-report ausente) no debe "tapar" evidencia real de
// pasos posteriores (p.ej. un RC ya canónico y aprobado). Esto evita tanto
// falsos "GENERANDO" (job ya terminado o nunca disparado) como falsos
// "pendiente" (paso intermedio sin evidencia pero posterior ya cumplido).
export function computeNodeDone(summary,gatesSummary){
  if(!summary) return null;
  const m=summary.mission||{}, design=summary.design||{}, ws=summary.workspace||{},
        hl=summary.headless, ts=summary.tests, rcs=summary.rcs||{};
  return [
    ['approved','completed'].includes(m.status||'') || !!m.approved_at,          // 01 Misión
    (design.files_count||0) > 0,                                                 // 02 Diseño
    !!(hl && hl.returncode===0),                                                 // 03 Headless
    (ws.py_files||0) > 0,                                                        // 04 Código
    !!(ts && ts.passed>0 && ts.failed===0),                                      // 05 Tests
    !!(gatesSummary && (gatesSummary.FAIL||0)===0 && (gatesSummary.PASS||0)>0),  // 06 Quality gates
    !!rcs.canonical || (rcs.count||0)>0,                                         // 07 Release cand.
    !!rcs.canonical,                                                             // 08 Aprobación humana
  ];
}

export async function refreshFlowDiagram(){
  const el=document.getElementById('flow-diagram'); if(!el) return;
  const amEl=document.getElementById('dash-active-mission');
  const pid=state.selectedMissionId;

  if(!pid){
    if(amEl) amEl.textContent='Selecciona una misión';
    renderFlowDiagram(null,null,null,null);
    return;
  }
  if(amEl) amEl.textContent=pid;

  const enc=encodeURIComponent(pid);
  const [sumR,gatesR,statusR]=await Promise.allSettled([
    fetch(API_BASE+'/api/v1/layer9/missions/'+enc+'/summary',{headers:headers()}).then(r=>r.ok?r.json():null),
    fetch(API_BASE+'/api/v1/deployments/'+enc+'/gates-report',{headers:headers()}).then(r=>r.ok?r.json():null),
    fetch(API_BASE+'/api/v1/layer8/status',{headers:headers()}).then(r=>r.ok?r.json():null),
  ]);
  const summary=sumR.value, gatesReport=gatesR.value, status=statusR.value;
  renderFlowDiagram(pid, summary, status?.jobs, gatesReport?.summary);
}

export function renderFlowDiagram(pid,summary,jobsSummary,gatesSummary){
  const el=document.getElementById('flow-diagram'); if(!el) return;
  const done=computeNodeDone(summary,gatesSummary);
  const firstPending=done?done.findIndex(x=>!x):-1;
  // Regla dura: si no hay jobs running/pending, ningún nodo puede quedar "en curso".
  const noActive=(jobsSummary?.running??0)===0&&(jobsSummary?.pending??0)===0;
  const interrupted=(summary?.mission?.status||'').includes('interrupted');
  el.innerHTML=FLOW_NODES.map((n,i)=>{
    const isDone=done?done[i]:false;
    let cls;
    if(isDone) cls='done';
    else if(n.gate) cls='gate';
    else if(i===firstPending&&!noActive) cls='active';
    else cls='todo';
    const st=cls==='done'?n.dn
      :cls==='active'?(interrupted&&i===firstPending?'interrumpido':n.ac)
      :n.td;
    return '<div class="node '+cls+'"><div><div class="ix">'+n.ix+'</div><div class="lab">'+n.lab+'</div></div><div class="st">'+st+'</div><span class="led"></span></div>';
  }).join('');
}
