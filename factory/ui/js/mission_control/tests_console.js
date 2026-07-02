/* W5 — grupo 05 del detail panel: consola de pruebas funcionales (W4).
   Reader (GET test-catalog/test-results) vs Executor (POST test/run[-suite]):
   el executor SIEMPRE pide nombre real del operador y deja evidencia auditada. */

import { API_BASE, headers } from './state.js';
import { toast, _esc } from './core.js';

const _RESERVED_RUN_BY=['human','agent','system','admin','user','factory'];

export async function _renderGrp5_tests(pid){
  const el=document.getElementById('grp-pruebas'); if(!el) return;
  el.innerHTML='<div class="meta" style="color:var(--faint)">Cargando catálogo…</div>';
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(pid)+'/test-catalog',{headers:headers()});
    if(r.status===404){ el.innerHTML='<div class="meta" style="color:var(--faint)">Sin catálogo de pruebas para esta misión.</div>'; return; }
    if(!r.ok){ el.innerHTML='<div class="meta" style="color:var(--fail)">Error '+r.status+'</div>'; return; }
    const d=await r.json();
    const ready=!!d.deployment_ready;
    let html=`<div class="between" style="margin-bottom:8px">
      <span class="meta">Deployment: puerto ${d.deployment?.api_port??'?'}</span>
      <span class="chip ${ready?'c-pass':'c-fail'}">${ready?'VIVO':'NO VIVO'}</span>
    </div>
    <div class="meta" style="font-size:10.5px;color:var(--faint);margin-bottom:10px">
      Ejecutar una prueba llama al endpoint real del deployment y DEJA EVIDENCIA AUDITADA (Part-11).
      El payload SIEMPRE viene del catálogo — no es editable.</div>`;
    if(!ready){
      html+=`<div class="meta" style="color:var(--warn);margin-bottom:10px;font-size:11px">
        El deployment no responde — los botones "Probar" están deshabilitados.</div>`;
    }
    html+=(d.agents||[]).map(a=>_agentTestCard(pid,a,ready)).join('');
    html+=`<div class="dp-sub" style="margin-top:14px">Historial de pruebas</div>
      <div id="test-history-${_esc(pid)}"><div class="meta" style="color:var(--faint)">cargando…</div></div>`;
    el.innerHTML=html;
    _loadTestHistory(pid);
  }catch(e){ el.innerHTML='<div class="meta" style="color:var(--fail)">'+e.message+'</div>'; }
}

export function _agentTestCard(pid,agent,ready){
  const tests=agent.tests||[];
  let html=`<div class="card" style="padding:10px 12px;margin-bottom:10px">
    <div class="between" style="margin-bottom:4px">
      <span class="k mono">${agent.agent_id}</span>
      <button class="btn ghost" style="font-size:10px;padding:3px 9px" ${ready?'':'disabled title="Deployment no vivo"'}
        onclick="runSuite('${_esc(pid)}','${agent.agent_id}')">Probar suite (${tests.length})</button>
    </div>
    ${agent.description?`<div class="meta" style="font-size:10.5px;color:var(--faint);margin-bottom:6px">${agent.description}</div>`:''}`;
  html+=tests.map(t=>_testCaseRow(pid,t,ready)).join('');
  html+='</div>';
  return html;
}

export function _testCaseRow(pid,t,ready){
  const rid=_esc(pid)+'-'+t.test_id;
  const payloadStr=JSON.stringify(t.payload,null,2).replace(/</g,'&lt;');
  const expectStr=JSON.stringify(t.expect,null,2).replace(/</g,'&lt;');
  return `<div class="gate-line" style="flex-direction:column;align-items:stretch;gap:4px">
    <div class="between">
      <span class="mono" style="font-size:11px">${t.title||t.test_id}</span>
      <button class="btn ghost" style="font-size:10px;padding:2px 8px" ${ready?'':'disabled'}
        onclick="promptRunTest('${_esc(pid)}','${t.test_id}')">Probar</button>
    </div>
    <div class="meta mono" style="font-size:10px;color:var(--faint)">${t.endpoint}</div>
    <details><summary style="cursor:pointer;font-size:10px;color:var(--faint)">payload / expect (solo lectura)</summary>
      <pre style="background:var(--panel-2);border:1px solid var(--line);border-radius:6px;padding:8px;
        font-size:10px;max-height:160px;overflow:auto;margin:4px 0 0">payload: ${payloadStr}

expect: ${expectStr}</pre>
    </details>
    <div id="result-${rid}"></div>
  </div>`;
}

export function promptRunTest(pid,testId){
  const by=(window.prompt('Nombre real del operador que ejecuta esta prueba (queda auditado):')||'').trim();
  if(!by) return;
  if(_RESERVED_RUN_BY.includes(by.toLowerCase())){ toast('"'+by+'" es un nombre reservado — usa tu nombre real.'); return; }
  _runTest(pid,testId,by);
}

export async function _runTest(pid,testId,by){
  const rid=pid+'-'+testId;
  const resEl=document.getElementById('result-'+rid);
  if(resEl) resEl.innerHTML='<div class="meta" style="color:var(--faint)">Ejecutando… (timeout 15s)</div>';
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(pid)+'/test/run',{
      method:'POST', headers:headers(), body:JSON.stringify({test_id:testId,run_by:by})
    });
    const d=await r.json().catch(()=>({}));
    if(!r.ok){
      if(resEl) resEl.innerHTML='<div class="meta" style="color:var(--fail)">Error '+r.status+': '+
        (typeof d.detail==='object'?JSON.stringify(d.detail):(d.detail||'error'))+'</div>';
      return;
    }
    if(resEl) resEl.innerHTML=_renderTestResult(d);
    toast((d.result==='PASS'?'✓ PASS':d.result==='FAIL'?'✗ FAIL':'⚠ ERROR')+' · '+testId+' · '+by);
    _loadTestHistory(pid);
  }catch(e){ if(resEl) resEl.innerHTML='<div class="meta" style="color:var(--fail)">Error de red: '+e.message+'</div>'; }
}

export function runSuite(pid,agentId){
  const by=(window.prompt('Nombre real del operador que ejecuta la suite de "'+agentId+'" (queda auditado):')||'').trim();
  if(!by) return;
  if(_RESERVED_RUN_BY.includes(by.toLowerCase())){ toast('"'+by+'" es un nombre reservado — usa tu nombre real.'); return; }
  _runSuite(pid,agentId,by);
}

export async function _runSuite(pid,agentId,by){
  toast('Ejecutando suite de '+agentId+'…');
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(pid)+'/test/run-suite',{
      method:'POST', headers:headers(), body:JSON.stringify({agent_id:agentId,run_by:by})
    });
    const d=await r.json().catch(()=>({}));
    if(!r.ok){
      toast('Error '+r.status+': '+(typeof d.detail==='object'?JSON.stringify(d.detail):(d.detail||'error')));
      return;
    }
    (d.results||[]).forEach(res=>{
      const resEl=document.getElementById('result-'+pid+'-'+res.test_id);
      if(resEl) resEl.innerHTML=_renderTestResult(res);
    });
    toast('Suite '+agentId+': '+d.passed+'/'+d.total+' PASS · '+by);
    _loadTestHistory(pid);
  }catch(e){ toast('Error de red: '+e.message); }
}

export function _renderTestResult(d){
  const cls=d.result==='PASS'?'c-pass':d.result==='FAIL'?'c-fail':'c-warn';
  const a=d.assertion||{};
  return `<div style="border:1px solid var(--line);border-radius:6px;padding:8px;margin-top:2px;background:var(--panel-2)">
    <div class="between">
      <span class="chip ${cls}" style="font-size:9px">${d.result}</span>
      <span class="meta mono" style="font-size:10px;color:var(--faint)">${d.latency_ms??'—'}ms · status ${d.response_status??'—'}</span>
    </div>
    ${d.detail?`<div class="meta" style="color:var(--warn);font-size:10.5px;margin-top:4px">${d.detail}</div>`:''}
    <div class="meta mono" style="font-size:10px;margin-top:6px">
      aserción ${a.json_path||'—'}: esperado=<b>${JSON.stringify(a.expected_value)}</b> · recibido=<b>${JSON.stringify(a.received_value)}</b>
    </div>
    <pre style="background:var(--panel);border:1px solid var(--line-soft);border-radius:6px;padding:6px;
      font-size:10px;max-height:140px;overflow:auto;white-space:pre-wrap;word-break:break-all;margin:6px 0 0">${
      (d.response_excerpt||'').replace(/</g,'&lt;')}</pre>
    <div class="meta" style="font-size:9.5px;color:var(--faint);margin-top:4px">run_by: ${d.run_by||'—'} · ${(d.run_at||'').slice(0,19).replace('T',' ')}</div>
  </div>`;
}

export async function _loadTestHistory(pid){
  const el=document.getElementById('test-history-'+_esc(pid)); if(!el) return;
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(pid)+'/test-results?limit=20',{headers:headers()});
    if(!r.ok){ el.innerHTML='<div class="meta" style="color:var(--fail)">Error '+r.status+'</div>'; return; }
    const d=await r.json();
    if(!d.total){ el.innerHTML='<div class="meta" style="color:var(--faint)">Sin pruebas ejecutadas todavía.</div>'; return; }
    el.innerHTML=(d.results||[]).map(res=>{
      const cls=res.result==='PASS'?'c-pass':res.result==='FAIL'?'c-fail':'c-warn';
      return `<div class="gate-line">
        <span class="gid mono" style="font-size:10.5px">${res.test_id}</span>
        <span class="chip ${cls}" style="font-size:9px">${res.result}</span>
        <span class="meta mono" style="font-size:10px;color:var(--faint)">${res.run_by||'—'} · ${(res.run_at||'').slice(0,19).replace('T',' ')}</span>
      </div>`;
    }).join('')+`<div class="meta" style="font-size:10.5px;color:var(--faint);margin-top:4px">Mostrando ${Math.min(d.total,20)} de ${d.total}</div>`;
  }catch(e){ el.innerHTML='<div class="meta" style="color:var(--fail)">'+e.message+'</div>'; }
}
