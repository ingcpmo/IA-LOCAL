/* W5 V2 — Decisiones humanas D1–D5.

   Vista SEPARADA a propósito de la cola de release candidates: un RC es una
   solución construida por Capa 8; estas son decisiones de gobernanza
   regulatoria sobre el corpus y las fuentes. Mezclarlas haría pasar una por
   la otra. Ver factory/services/w5_human_decisions.py. */

import { API_BASE, headers } from './state.js';
import { toast } from './core.js';

const esc = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

/* Estado de error EXPLÍCITO: un 401/403/404/500 nunca puede quedar bajo el
   placeholder genérico de "no conectado" — eso hacía indistinguible un fallo
   del backend de una sesión sin conectar. */
export function renderW5Error(status, detail){
  const el = document.getElementById('w5-list'); if(!el) return;
  const label = status===401||status===403 ? 'Sesión no autorizada'
              : status===404 ? 'Endpoint no encontrado'
              : status>=500 ? 'Error del backend'
              : 'Error';
  el.innerHTML = `<div class="card">
    <div class="meta" style="color:var(--fail);font-weight:600">
      ${esc(label)} — HTTP ${esc(status)}</div>
    <div class="meta" style="margin-top:6px">${esc(detail||'sin detalle')}</div>
    <div class="meta" style="margin-top:6px;color:var(--faint)">
      GET /api/v1/layer9/w5-decisions</div>
  </div>`;
}

function sourcesTable(sources){
  if(!sources || !sources.length) return '<div class="meta">(sin fuentes en el registry)</div>';
  return `<table class="tbl" style="width:100%;font-size:11px">
    <thead><tr>
      <th>source_id</th><th>Regulación</th><th>URL oficial</th><th>Versión</th>
      <th>SHA-256</th><th>Estado actual</th>
    </tr></thead><tbody>
    ${sources.map(s=>`<tr>
      <td class="mono">${esc(s.source_id)}</td>
      <td>${esc(s.regulation)}</td>
      <td class="mono" style="word-break:break-all;max-width:260px">${esc(s.official_source_url)}</td>
      <td>${esc(s.version)}</td>
      <td class="mono" title="${esc(s.sha256)}">${esc((s.sha256||'').slice(0,16))}…</td>
      <td><span class="chip c-human">${esc(s.current_state)}</span></td>
    </tr>`).join('')}
    </tbody></table>`;
}

function d1Card(d){
  const rec = d.recorded;
  const done = d.status === 'RECORDED';
  return `
  <div class="rc" style="margin-bottom:14px">
    <div class="rc-head">
      <span class="seal" style="width:30px;height:30px;font-size:10px">D1</span>
      <div>
        <div class="mono" style="font-weight:600">${esc(d.decision_id)}</div>
        <div class="meta">${esc(d.title)}</div>
      </div>
      <div class="spacer"></div>
      <span class="chip ${done?'c-pass':'c-human'}">${done?'registrada':'PENDIENTE'}</span>
    </div>
    <div style="padding:12px">
      ${sourcesTable(d.context?.sources)}
      ${done ? `<div class="meta" style="margin-top:10px;color:var(--pass)">
          Decidida: <b>${esc(rec.decision)}</b> por ${esc(rec.approved_by)}
          el ${esc((rec.decision_date||'').slice(0,16).replace('T',' '))}
          · cadencia ${esc(rec.reverification_cadence_months)} meses
          · autoridad ${esc(rec.reverification_authority)}</div>`
      : `
      <div class="hr"></div>
      <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:10px">
        <div class="field"><label>Fuentes aprobadas</label>
          <select id="w5-d1-sources">
            <option value="ALL">ALL — las tres fuentes</option>
            ${(d.context?.sources||[]).map(s=>`<option value="${esc(s.source_id)}">solo ${esc(s.source_id)}</option>`).join('')}
          </select></div>
        <div class="field"><label>Cadencia de reverificación (meses)</label>
          <input id="w5-d1-cadence" type="number" min="1" max="60" placeholder="p.ej. 12"></div>
        <div class="field"><label>Autoridad de reverificación</label>
          <input id="w5-d1-authority" placeholder="quién declara vigente una fuente"></div>
        <div class="field"><label>Firmado por (nombre real)</label>
          <input id="w5-d1-approver" placeholder="p.ej. Cesar" autocomplete="off"></div>
      </div>
      <div class="field"><label>Notas</label><input id="w5-d1-notes" placeholder="opcional"></div>
      <div class="actions">
        <button class="btn pass" onclick="submitW5Decision('D1_regulatory_sources','APPROVE')">APPROVE</button>
        <button class="btn" onclick="submitW5Decision('D1_regulatory_sources','PARTIAL')">PARTIAL</button>
        <button class="btn fail" onclick="submitW5Decision('D1_regulatory_sources','REJECT')">REJECT</button>
      </div>
      <div class="meta" style="margin-top:8px;color:var(--faint)">
        Registrar la decisión NO reverifica ninguna fuente ni cambia su estado a
        LOCAL_CANONICAL_COPY_VERIFIED: eso es un paso posterior y separado.</div>`}
    </div>
  </div>`;
}

function genericCard(d, idx){
  const rec = d.recorded, done = d.status === 'RECORDED';
  const ctx = d.context || {};
  const rows = Object.entries(ctx)
    .filter(([k])=>!['sources','packs'].includes(k))
    .map(([k,v])=>`<div class="meta"><b>${esc(k)}</b>: ${esc(Array.isArray(v)?v.join(' · '):v)}</div>`)
    .join('');
  const packs = ctx.packs ? `<div class="meta">${ctx.packs.length} Evidence Packs · catálogo ${esc(ctx.catalog_version)} ·
      todos en <span class="mono">${esc(ctx.packs[0]?.source_verification_status||'')}</span></div>` : '';
  return `
  <div class="rc" style="margin-bottom:14px">
    <div class="rc-head">
      <span class="seal" style="width:30px;height:30px;font-size:10px">D${idx+1}</span>
      <div>
        <div class="mono" style="font-weight:600">${esc(d.decision_id)}</div>
        <div class="meta">${esc(d.title)}</div>
      </div>
      <div class="spacer"></div>
      <span class="chip ${done?'c-pass':'c-human'}">${done?'registrada':'PENDIENTE'}</span>
    </div>
    <div style="padding:12px">
      ${packs}${rows}
      ${done ? `<div class="meta" style="margin-top:10px;color:var(--pass)">
          Decidida: <b>${esc(rec.decision)}</b> por ${esc(rec.approved_by)}
          el ${esc((rec.decision_date||'').slice(0,16).replace('T',' '))}</div>`
      : `<div class="hr"></div>
      <div class="field"><label>Firmado por (nombre real)</label>
        <input id="w5-${esc(d.decision_id)}-approver" placeholder="p.ej. Cesar" autocomplete="off"></div>
      <div class="field"><label>Notas</label>
        <input id="w5-${esc(d.decision_id)}-notes" placeholder="opcional"></div>
      <div class="actions">
        <button class="btn pass" onclick="submitW5Decision('${esc(d.decision_id)}','APPROVE')">APPROVE</button>
        <button class="btn" onclick="submitW5Decision('${esc(d.decision_id)}','PARTIAL')">PARTIAL</button>
        <button class="btn fail" onclick="submitW5Decision('${esc(d.decision_id)}','REJECT')">REJECT</button>
      </div>`}
    </div>
  </div>`;
}

export function renderW5Decisions(data){
  const el = document.getElementById('w5-list'); if(!el) return;
  const decisions = data?.decisions || [];
  if(!decisions.length){
    el.innerHTML = '<div class="card"><div class="meta">(el backend no devolvió decisiones)</div></div>';
    return;
  }
  const g = data.governance || {};
  el.innerHTML =
    `<div class="card" style="margin-bottom:12px">
       <div class="meta"><b>${decisions.length}</b> decisiones ·
       <b style="color:var(--warn)">${data.pending_count}</b> pendientes ·
       ${data.recorded_count} registradas</div>
       <div class="meta mono" style="margin-top:6px;color:var(--faint)">
         FORMAL_RELEASE_GATE=${esc(g.FORMAL_RELEASE_GATE)} ·
         REGULATORY_COMPLIANCE=${esc(g.REGULATORY_COMPLIANCE)} ·
         PRODUCTION_ENABLEMENT=${esc(g.PRODUCTION_ENABLEMENT)}</div>
     </div>` +
    decisions.map((d,i)=> d.decision_id==='D1_regulatory_sources' ? d1Card(d) : genericCard(d,i)).join('');
}

export async function submitW5Decision(decisionId, decision){
  const val = id => (document.getElementById(id)?.value || '').trim();
  const approver = decisionId==='D1_regulatory_sources'
    ? val('w5-d1-approver') : val('w5-'+decisionId+'-approver');
  if(!approver){ toast('Ingresa el nombre real de quien firma la decisión.'); return; }

  const body = {
    decision,
    approved_by: approver,
    notes: decisionId==='D1_regulatory_sources' ? val('w5-d1-notes') : val('w5-'+decisionId+'-notes'),
  };
  if(decisionId==='D1_regulatory_sources'){
    body.approved_source_ids = val('w5-d1-sources') === 'ALL' ? 'ALL' : [val('w5-d1-sources')];
    const cad = val('w5-d1-cadence');
    if(!cad){ toast('Indica la cadencia de reverificación en meses.'); return; }
    body.reverification_cadence_months = parseInt(cad, 10);
    body.reverification_authority = val('w5-d1-authority');
    if(!body.reverification_authority){ toast('Indica la autoridad de reverificación.'); return; }
  }
  try{
    const r = await fetch(API_BASE+'/api/v1/layer9/w5-decisions/'+encodeURIComponent(decisionId),
      {method:'POST', headers:headers(), body:JSON.stringify(body)});
    if(r.ok){
      toast(decisionId+' registrada: '+decision+' · '+approver);
      const { refresh } = await import('./refresh.js');
      setTimeout(()=>refresh('w5'), 600);
    } else {
      const err = await r.json().catch(()=>({}));
      const detail = typeof err.detail==='string' ? err.detail : JSON.stringify(err.detail||{});
      toast('Error '+r.status+': '+detail);
    }
  }catch(e){ toast('Error de red: '+e.message); }
}
