/* W5 — cola de revisión de release candidates (U9). */

import { API_BASE, headers } from './state.js';
import { toast } from './core.js';
import { refresh } from './refresh.js';

/* ---- U9: RC review — aprobar/rechazar reales ---- */
export async function submitRCDecision(rcId, action){
  const safeName=rcId.replace(/[^a-zA-Z0-9_-]/g,'_');
  const inp=document.getElementById('rc-reviewer-'+safeName);
  const reviewer=(inp?.value||'').trim();
  if(!reviewer){ toast('Ingresa el nombre real del revisor.'); return; }
  if(reviewer.toLowerCase()==='human'){ toast('"human" no es válido — usa un nombre real.'); return; }
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/review/'+encodeURIComponent(rcId)+'/'+action,{
      method:'POST', headers:headers(),
      body:JSON.stringify({approved_by:reviewer, notes:'decision_origin: human_confirmed · via Mission Control'})
    });
    if(r.ok){
      toast((action==='approve'?'RC aprobado ✓':'RC rechazado')+'  · revisor: '+reviewer);
      setTimeout(()=>refresh('review'),600);
    } else {
      const err=await r.json().catch(()=>({}));
      toast('Error '+r.status+': '+(err.detail||'ver consola'));
    }
  }catch(e){ toast('Error de red: '+e.message); }
}

export function renderReview(pending){
  const el=document.getElementById('review-list'); if(!el) return;
  if(!pending.length){
    el.innerHTML='<div class="card"><div class="meta" style="color:var(--pass)">✓ Cola vac\xeda — no hay release candidates pendientes.</div></div>';
    return;
  }
  el.innerHTML=pending.map(rc=>{
    const safeName=rc.rc_id.replace(/[^a-zA-Z0-9_-]/g,'_');
    return `
    <div class="rc" style="margin-bottom:14px">
      <div class="rc-head">
        <span class="seal" style="width:30px;height:30px;font-size:10px">RC</span>
        <div>
          <div class="mono" style="font-weight:600">${rc.project_id} \xb7 ${rc.summary?.version||rc.rc_id}</div>
          <div class="meta mono">enqueued ${(rc.enqueued_at||'').slice(0,16).replace('T',' ')}Z \xb7 ${rc.status}</div>
        </div>
        <div class="spacer"></div>
        <span class="chip c-human">espera humano</span>
      </div>
      <div class="rc-body">
        <div class="rc-col">
          <div class="k" style="margin-bottom:8px">Diff / archivos</div>
          <div class="diffbox" id="rc-diff-${rc.project_id}">(cargando…)</div>
        </div>
        <div class="rc-col">
          <div class="k" style="margin-bottom:8px">RC ID</div>
          <div class="meta mono" style="font-size:10.5px;word-break:break-all">${rc.rc_id}</div>
          <div class="hr"></div>
          <div class="field"><label>Revisor (nombre real)</label>
            <input id="rc-reviewer-${safeName}" placeholder="p.ej. Cesar" autocomplete="off">
          </div>
          <div class="actions">
            <button class="btn pass" onclick="submitRCDecision('${rc.rc_id}','approve')">Aprobar RC</button>
            <button class="btn fail" onclick="submitRCDecision('${rc.rc_id}','reject')">Rechazar</button>
          </div>
        </div>
      </div>
    </div>`;
  }).join('');
  pending.forEach(async rc=>{
    try{
      const r=await fetch(API_BASE+'/api/v1/layer8/missions/'+rc.project_id+'/diff',{headers:headers()});
      if(!r.ok) return;
      const txt=await r.json();
      const box=document.getElementById('rc-diff-'+rc.project_id);
      if(!box) return;
      const lines=(typeof txt==='string'?txt:'').slice(0,1000).split('\n');
      box.innerHTML=lines.map(l=>{
        const s=l.replace(/</g,'&lt;').replace(/>/g,'&gt;');
        if(l.startsWith('+')) return '<span class="add">'+s+'</span>';
        if(l.startsWith('-')) return '<span class="del">'+s+'</span>';
        return '<span class="ctx">'+s+'</span>';
      }).join('\n');
    }catch(e){}
  });
}
