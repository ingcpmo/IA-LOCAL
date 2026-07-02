/* W5 — grupo 06 del detail panel: Dashboard GMP (W4.1) + descarga de PDF.
   Capa de PRESENTACIÓN sobre W4: consolida evidencia YA existente de
   /gmp-report (read-only, no audita) en dos niveles — ejecutivo farmacéutico
   + evidencia técnica colapsable — y ofrece descarga del PDF congelado.
   Ningún dato se inventa: lo que falta llega como "no_disponible" desde el
   backend y se muestra en gris. */

import { API_BASE, headers } from './state.js';
import { toast, _esc, _gmpNA, _gmpEscHtml } from './core.js';

export async function _renderGrp6_gmpDashboard(pid){
  const el=document.getElementById('grp-gmp_dashboard'); if(!el) return;
  el.innerHTML='<div class="meta" style="color:var(--faint)">Cargando dashboard GMP…</div>';
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(pid)+'/gmp-report',{headers:headers()});
    if(!r.ok){ el.innerHTML='<div class="meta" style="color:var(--fail)">Error '+r.status+' cargando /gmp-report</div>'; return; }
    const d=await r.json();
    el.innerHTML=_renderGmpDashboard(pid, d);
  }catch(e){ el.innerHTML='<div class="meta" style="color:var(--fail)">Error de red: '+e.message+'</div>'; }
}

export function _renderGmpDashboard(pid, d){
  const meta=d.meta||{};
  const mo=d.mission_objective||{};
  const pc=d.pharma_case;
  const ae=d.agents_evaluated||{};
  const rba=d.results_by_agent||[];
  const gi=d.gmp_implication||{};
  const rv=d.rules_vs_llm||{};
  const at=d.audit_traceability||{};
  const depCls=meta.deployment_status==='desplegado'?'c-pass':'c-warn';

  let html=`<div class="between" style="margin-bottom:10px;align-items:flex-start">
    <div class="meta mono" style="line-height:1.9;font-size:11px">
      cliente &nbsp; ${_gmpNA(meta.client_type)}<br>
      RC canónico &nbsp; ${_gmpNA(meta.canonical_rc)}<br>
      deployment &nbsp; <span class="chip ${depCls}" style="font-size:9px">${meta.deployment_status||'—'}</span>
    </div>
    <button class="btn ghost" id="gmp-pdf-btn-${_esc(pid)}" style="font-size:11px;padding:6px 14px"
      onclick="downloadGmpReportPdf('${_esc(pid)}')">⬇ Generar / Descargar PDF</button>
  </div>`;

  html+=`<div class="dp-sub">Resumen ejecutivo</div>
    <div class="card" style="padding:10px 12px;margin-bottom:10px">${_gmpEscHtml(d.executive_summary)}</div>`;

  html+=`<div class="dp-sub">Objetivo de la misión</div>
    <div class="card" style="padding:10px 12px;margin-bottom:10px">
      <div style="margin-bottom:6px">${_gmpNA(mo.objective ? _gmpEscHtml(mo.objective) : null)}</div>
      ${(mo.regulatory_scope||[]).length ? '<div>'+mo.regulatory_scope.map(s=>`<span class="chip c-info" style="font-size:9px;margin:2px">${_gmpEscHtml(s)}</span>`).join('')+'</div>' : ''}
    </div>`;

  html+=`<div class="dp-sub">Caso farmacéutico planteado</div>
    <div class="card" style="padding:10px 12px;margin-bottom:10px">`;
  if(pc && typeof pc==='object'){
    html+=`<div style="margin-bottom:6px">${_gmpEscHtml(pc.raw_objective)}</div>
      ${(pc.domains||[]).map(s=>`<span class="chip c-mute" style="font-size:9px;margin:2px">${_gmpEscHtml(s)}</span>`).join('')}`;
  } else {
    html+=_gmpNA(pc);
  }
  html+=`</div>`;

  html+=`<div class="dp-sub">Agentes evaluados</div>
    <div class="card" style="padding:10px 12px;margin-bottom:10px">
      <div style="margin-bottom:5px"><span class="meta" style="font-size:10.5px">Perfiles heredados:</span>
        ${(ae.profiles_inherited||[]).map(a=>`<span class="chip c-accent" style="font-size:9px;margin:2px">${_gmpEscHtml(a)}</span>`).join('')||_gmpNA(null)}</div>
      <div><span class="meta" style="font-size:10.5px">Agentes nuevos:</span>
        ${(ae.new_agents||[]).map(a=>`<span class="chip c-info" style="font-size:9px;margin:2px">${_gmpEscHtml(a)}</span>`).join('')||_gmpNA(null)}</div>
    </div>`;

  html+=`<div class="dp-sub">Resultados por agente</div>`;
  if(!rba.length){
    html+=`<div class="meta" style="color:var(--faint);margin-bottom:10px">No se han ejecutado pruebas funcionales aún para esta misión.</div>`;
  }
  html+=rba.map(block=>{
    const passed=block.tests.filter(t=>t.result==='PASS').length;
    return `<div class="card" style="padding:10px 12px;margin-bottom:8px">
      <div class="between" style="margin-bottom:6px">
        <span class="k mono">${_gmpEscHtml(block.agent_id)}</span>
        <span class="chip ${passed===block.tests.length?'c-pass':'c-warn'}" style="font-size:9px">${passed}/${block.tests.length} PASS</span>
      </div>`+
      block.tests.map(t=>{
        const cls=t.result==='PASS'?'c-pass':t.result==='FAIL'?'c-fail':'c-warn';
        return `<div class="gate-line" style="flex-direction:column;align-items:stretch;gap:2px">
          <div class="between"><span style="font-size:11px">${_gmpEscHtml(t.title)}</span>
            <span class="chip ${cls}" style="font-size:9px">${t.result}</span></div>
          <div class="meta mono" style="font-size:10px;color:var(--faint)">${_gmpEscHtml(t.endpoint)} · dato relevante: ${_gmpEscHtml(JSON.stringify(t.relevant_datum))}</div>
          <div class="meta" style="font-size:9.5px;color:var(--faint)">run_by: ${_gmpNA(t.run_by)} · ${(t.run_at||'').toString().slice(0,19).replace('T',' ')} · ${t.uses_llm?'<span class=\"chip c-info\" style=\"font-size:8px\">LLM LOCAL</span>':'<span class=\"chip c-mute\" style=\"font-size:8px\">REGLAS PYTHON</span>'}</div>
        </div>`;
      }).join('')+
    `</div>`;
  }).join('');

  html+=`<div class="dp-sub">Interpretación farmacéutica</div>
    <div class="card" style="padding:10px 12px;margin-bottom:10px">
      ${(d.pharma_interpretation||[]).map(s=>`<div style="margin-bottom:4px;font-size:11px">• ${_gmpEscHtml(s)}</div>`).join('')}
    </div>`;

  html+=`<div class="dp-sub">Implicación GMP</div>
    <div class="card" style="padding:10px 12px;margin-bottom:10px">
      <div style="margin-bottom:4px;font-size:11px"><b>OOS:</b> ${_gmpNA(gi.oos && _gmpEscHtml(gi.oos))}</div>
      <div style="margin-bottom:4px;font-size:11px"><b>HPLC/SST:</b> ${_gmpNA(gi.hplc && _gmpEscHtml(gi.hplc))}</div>
      <div style="font-size:11px"><b>ALCOA+:</b> ${_gmpNA(gi.alcoa && _gmpEscHtml(gi.alcoa))}</div>
    </div>`;

  html+=`<div class="dp-sub">Reglas Python vs LLM local (Ollama)</div>
    <div class="card" style="padding:10px 12px;margin-bottom:10px">
      <div class="meta" style="font-size:10.5px;margin-bottom:6px">${_gmpEscHtml(rv.explanation||'')}</div>
      <div style="margin-bottom:4px">${(rv.deterministic_endpoints||[]).map(e=>`<span class="chip c-mute" style="font-size:8.5px;margin:2px">REGLAS · ${_gmpEscHtml(e)}</span>`).join('')}</div>
      <div>${(rv.llm_endpoints||[]).map(e=>`<span class="chip c-info" style="font-size:8.5px;margin:2px">LLM LOCAL · ${_gmpEscHtml(e)}</span>`).join('')||_gmpNA(null)}</div>
    </div>`;

  html+=`<div class="dp-sub">Impacto operativo esperado <span class="chip c-warn" style="font-size:8px">ESTIMACIÓN</span></div>
    <div class="card" style="padding:10px 12px;margin-bottom:10px;font-size:10.5px">${_gmpEscHtml(d.operational_impact)}</div>`;

  html+=`<div class="dp-sub">Limitaciones</div>
    <div class="card" style="padding:10px 12px;margin-bottom:10px">
      ${(d.limitations||[]).map(s=>`<div style="margin-bottom:3px;font-size:11px">• ${_gmpEscHtml(s)}</div>`).join('')}
    </div>`;

  html+=`<div class="dp-sub">Pendientes antes de go-live</div>
    <div class="card" style="padding:10px 12px;margin-bottom:10px">
      ${(d.pending_before_golive||[]).map(s=>`<div style="margin-bottom:3px;font-size:11px">• ${_gmpEscHtml(s)}</div>`).join('')}
    </div>`;

  html+=`<div class="dp-sub">Conclusión</div>
    <div class="card" style="padding:10px 12px;margin-bottom:10px;border-color:var(--accent);font-size:10.5px">${_gmpEscHtml(d.conclusion)}</div>`;

  // ── Nivel 2: evidencia técnica colapsable ──
  html+=`<details style="margin-top:6px">
    <summary style="cursor:pointer;font-size:11px;color:var(--faint)">▶ Ver evidencia técnica</summary>
    <div style="margin-top:8px">
      <div class="meta mono" style="font-size:10.5px;line-height:1.8">
        RC canónico &nbsp; ${_gmpNA(at.canonical_rc)}<br>
        eventos de prueba auditados &nbsp; ${at.test_events_count!=null?at.test_events_count:'0'}
      </div>
      <div class="dp-sub" style="margin-top:8px">RC sha256sums</div>
      <pre style="background:var(--panel-2);border:1px solid var(--line);border-radius:6px;padding:8px;
        font-size:9.5px;max-height:120px;overflow:auto;margin:4px 0">${_gmpEscHtml(JSON.stringify(at.rc_sha256,null,2))}</pre>
      <div class="dp-sub" style="margin-top:8px">Últimos eventos de auditoría</div>
      <pre style="background:var(--panel-2);border:1px solid var(--line);border-radius:6px;padding:8px;
        font-size:9.5px;max-height:180px;overflow:auto;margin:4px 0">${_gmpEscHtml(JSON.stringify(at.last_audit_events,null,2))}</pre>
      <div class="dp-sub" style="margin-top:8px">JSON completo de /gmp-report (soporte técnico, read-only)</div>
      <pre style="background:var(--panel-2);border:1px solid var(--line);border-radius:6px;padding:8px;
        font-size:9.5px;max-height:280px;overflow:auto;margin:4px 0;user-select:text">${_gmpEscHtml(JSON.stringify(d,null,2))}</pre>
    </div>
  </details>`;

  return html;
}

export async function downloadGmpReportPdf(pid){
  const btn=document.getElementById('gmp-pdf-btn-'+_esc(pid));
  if(btn){ btn.disabled=true; btn.textContent='Generando…'; }
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/missions/'+encodeURIComponent(pid)+'/gmp-report.pdf',{headers:headers()});
    if(!r.ok){
      const t=await r.text().catch(()=>'');
      toast('Error '+r.status+' generando PDF'+(t?': '+t.slice(0,120):''));
      return;
    }
    const blob=await r.blob();
    const ts=new Date().toISOString().slice(0,16).replace(/[-:]/g,'').replace('T','-');
    const filename='informe_gmp_'+pid+'_'+ts+'.pdf';
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=url; a.download=filename; document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast('PDF descargado: '+filename);
  }catch(e){
    toast('Error de red generando PDF: '+e.message);
  }finally{
    if(btn){ btn.disabled=false; btn.textContent='⬇ Generar / Descargar PDF'; }
  }
}
