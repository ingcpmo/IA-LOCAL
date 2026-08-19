/* W5 — cola de revisión de release candidates (U9).
   R3-T1.2/F0.4 (2026-08-12): la cola mezcla RCs reales (con diff, manifest
   en disco) y entradas `finding_review` (hallazgos de evidencia, R1.8/R2.3
   §4 -- rc_id sintético `finding-{run_id}-{req_id}`, SIN manifest, SIN
   diff). Antes de esta fecha renderReview() trataba TODO como RC: para un
   finding_review, `rc.summary?.version` era undefined y el fetch de diff
   apuntaba a un `project_id` que en realidad es el `document_id` del
   hallazgo -- fallaba en silencio (catch vacío) dejando el diffbox
   congelado en "(cargando…)" para siempre, sin error visible. */

import { API_BASE, headers } from './state.js';
import { toast } from './core.js';
import { refresh } from './refresh.js';

const DIFF_FETCH_TIMEOUT_MS = 8000;

/* ---- U9: RC review — aprobar/rechazar reales ----
   approved_by ya NO viaja en el body (Paquete 2, hallazgo M) -- el
   backend resuelve el revisor desde X-Identity-Key (headers(), state.js). */
export async function submitRCDecision(rcId, action){
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/review/'+encodeURIComponent(rcId)+'/'+action,{
      method:'POST', headers:headers(),
      body:JSON.stringify({notes:'decision_origin: human_confirmed · via Mission Control'})
    });
    if(r.ok){
      toast(action==='approve'?'RC aprobado ✓':'RC rechazado');
      setTimeout(()=>refresh('review'),600);
    } else {
      const err=await r.json().catch(()=>({}));
      toast('Error '+r.status+': '+(err.detail||'ver consola'));
    }
  }catch(e){ toast('Error de red: '+e.message); }
}

/* ---- R3-T1.2/F0.4: decisión sobre un finding_review (hallazgo de
   evidencia) -- endpoint separado, NUNCA /review/{rc_id}/approve|reject
   (esos exigen un rc_manifest.json real que un finding_review no tiene).
   reviewer ya NO viaja en el body (Paquete 2, hallazgo M). */
export async function submitFindingDecision(rcId, decision){
  const safeName=rcId.replace(/[^a-zA-Z0-9_-]/g,'_');
  const pageInp=document.getElementById('finding-page-'+safeName);
  const quoteInp=document.getElementById('finding-quote-'+safeName);
  const confirmed_page = pageInp && pageInp.value.trim() ? Number(pageInp.value.trim()) : null;
  const confirmed_quote = quoteInp && quoteInp.value.trim() ? quoteInp.value.trim() : null;
  try{
    const r=await fetch(API_BASE+'/api/v1/layer9/review/findings/'+encodeURIComponent(rcId)+'/decide',{
      method:'POST', headers:headers(),
      body:JSON.stringify({decision, confirmed_page, confirmed_quote})
    });
    if(r.ok){
      toast(decision==='confirmed'?'Hallazgo confirmado ✓':'Hallazgo rechazado');
      setTimeout(()=>refresh('review'),600);
      return;
    }
    const err=await r.json().catch(()=>({}));
    const detail = err.detail;
    if(r.status===409){
      const d = typeof detail==='object' ? detail : {};
      toast('Ya decidido antes por '+(d.previously_decided_by||'?')+' — no se puede re-decidir.');
    } else if(r.status===422){
      toast('Identidad o decisión inválida ('+r.status+'): '+(typeof detail==='string'?detail:JSON.stringify(detail||{})));
    } else if(r.status===404){
      toast('Hallazgo no encontrado ('+rcId+').');
    } else {
      toast('Error '+r.status+': '+(typeof detail==='string'?detail:'ver consola'));
    }
  }catch(e){ toast('Error de red: '+e.message); }
}

function fetchWithTimeout(url, opts, timeoutMs){
  const controller = new AbortController();
  const timer = setTimeout(()=>controller.abort(), timeoutMs);
  return fetch(url, {...opts, signal: controller.signal}).finally(()=>clearTimeout(timer));
}

function renderCandidatesTable(candidates, honestyNote){
  if(!candidates || !candidates.length) return '';
  const rows = candidates.map(c=>`<tr>
    <td class="mono">${c.chunk_index??'?'}</td>
    <td class="mono">${c.page_start??'?'}-${c.page_end??'?'}</td>
    <td class="mono">${c.bm25_rank??'—'}</td>
    <td class="mono">${c.embedding_rank??'—'}</td>
    <td class="mono">${c.fusion_rank??'—'}</td>
    <td class="meta" style="max-width:320px">${(c.excerpt||'').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</td>
  </tr>`).join('');
  return `
    <div class="meta" style="margin-top:8px;color:var(--warn)">${honestyNote||'Estos candidatos son RECUPERACIÓN, no evidencia validada.'}</div>
    <table class="tbl" style="width:100%;font-size:11px;margin-top:6px">
      <thead><tr><th>Chunk</th><th>Páginas</th><th>BM25</th><th>Embed</th><th>Fusión</th><th>Extracto</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

/* R3-T1.8 bloque 1 (docs_plan/R3_T1_8_VERIFICACION_Y_LIVE_MINIMA.md):
   "confirmar" no significa lo mismo para toda conclusion -- mismos dos
   conjuntos que el backend (factory/api/routes/layer9.py,
   _FINDING_QUOTE_REQUIRED_CONCLUSIONS / _NOT_APPLICABLE_CONCLUSIONS).
   Antes de esto el campo "Cita confirmada" se mostraba SIEMPRE como
   "(opcional)" sin importar la conclusion -- asi quedo la entrada de
   validacion de R3-T1.7 con quote="mejora", un dato sin sentido en un
   campo que alimenta el Golden Dataset. */
const FINDING_QUOTE_REQUIRED_CONCLUSIONS = new Set(['SUPPORTING_EVIDENCE_UNDER_REVIEW']);
const FINDING_QUOTE_NOT_APPLICABLE_CONCLUSIONS = new Set([
  'EVALUATION_INCOMPLETE', 'PROVISIONAL_GAP', 'DOCUMENTATION_GAP', 'CROSS_REFERENCE_MISSING',
]);

function renderFindingCard(rc){
  const s = rc.summary || {};
  const safeName = rc.rc_id.replace(/[^a-zA-Z0-9_-]/g,'_');
  const flags = (s.review_flags||[]).map(f=>`<span class="chip">${f}</span>`).join(' ');
  const evidencia = s.evidence_quote
    ? `<div class="meta" style="margin-top:6px">«${(s.evidence_quote||'').replace(/</g,'&lt;').replace(/>/g,'&gt;')}»${s.page?' (pág. '+s.page+')':''}</div>`
    : `<div class="meta" style="margin-top:6px;color:var(--faint)">Sin cita anclada -- ver candidatos de recuperación abajo si existen.</div>`;
  const quoteRequired = FINDING_QUOTE_REQUIRED_CONCLUSIONS.has(s.conclusion);
  const quoteNotApplicable = FINDING_QUOTE_NOT_APPLICABLE_CONCLUSIONS.has(s.conclusion);
  const quoteFields = quoteNotApplicable ? `
        <div class="meta" style="margin:6px 0;color:var(--faint)">
          Esta conclusión (<span class="mono">${s.conclusion}</span>) es una ausencia/bloqueo,
          no evidencia observada -- no hay cita que confirmar. "Confirmar" aquí significa
          aceptar el bloqueo/ausencia y la necesidad de revisión adicional.
        </div>` : `
        <div class="field"><label>Página confirmada ${quoteRequired?'':'(opcional, si señalas un candidato real)'}</label>
          <input id="finding-page-${safeName}" placeholder="p.ej. 45" autocomplete="off">
        </div>
        <div class="field"><label>Cita confirmada ${quoteRequired?'(obligatoria -- la cita real que sustenta el requisito)':'(opcional)'}</label>
          <input id="finding-quote-${safeName}" placeholder="cita textual real del candidato" autocomplete="off">
        </div>`;
  const confirmLabel = quoteNotApplicable ? 'Confirmar bloqueo/ausencia' : 'Confirmar evidencia';
  return `
  <div class="rc" style="margin-bottom:14px">
    <div class="rc-head">
      <span class="seal" style="width:30px;height:30px;font-size:10px">FND</span>
      <div>
        <div class="mono" style="font-weight:600">${s.document_id||rc.project_id} · ${s.requirement_id||'?'}</div>
        <div class="meta mono">enqueued ${(rc.enqueued_at||'').slice(0,16).replace('T',' ')}Z · ${rc.status} · ${s.conclusion||'?'}</div>
      </div>
      <div class="spacer"></div>
      <span class="chip c-human">espera humano</span>
    </div>
    <div class="rc-body">
      <div class="rc-col">
        <div class="k" style="margin-bottom:8px">Hallazgo (finding_review -- sin diff, no es un RC)</div>
        ${evidencia}
        <div style="margin-top:6px">${flags}</div>
        ${renderCandidatesTable(s.candidates, s.candidates_honesty_note)}
      </div>
      <div class="rc-col">
        <div class="k" style="margin-bottom:8px">RC ID</div>
        <div class="meta mono" style="font-size:10.5px;word-break:break-all">${rc.rc_id}</div>
        <div class="hr"></div>
        <div class="meta" style="color:var(--faint)">Revisor: resuelto de tu IDENTITY KEY de sesión (Paquete 2).</div>
        ${quoteFields}
        <div class="actions">
          <button class="btn pass" onclick="submitFindingDecision('${rc.rc_id}','confirmed')">${confirmLabel}</button>
          <button class="btn fail" onclick="submitFindingDecision('${rc.rc_id}','rejected')">Rechazar</button>
        </div>
      </div>
    </div>
  </div>`;
}

function renderRCCard(rc){
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
        <div class="meta" style="color:var(--faint)">Revisor: resuelto de tu IDENTITY KEY de sesión (Paquete 2).</div>
        <div class="actions">
          <button class="btn pass" onclick="submitRCDecision('${rc.rc_id}','approve')">Aprobar RC</button>
          <button class="btn fail" onclick="submitRCDecision('${rc.rc_id}','reject')">Rechazar</button>
        </div>
      </div>
    </div>
  </div>`;
}

export function renderReview(pending){
  const el=document.getElementById('review-list'); if(!el) return;
  if(!pending.length){
    el.innerHTML='<div class="card"><div class="meta" style="color:var(--pass)">✓ Cola vac\xeda — no hay release candidates pendientes.</div></div>';
    return;
  }
  const findings = pending.filter(rc=>rc.entry_type==='finding_review');
  const rcs = pending.filter(rc=>rc.entry_type!=='finding_review');

  el.innerHTML = rcs.map(renderRCCard).join('') + findings.map(renderFindingCard).join('');

  /* Solo los RCs reales tienen diff que traer -- findings nunca lo
     necesitan (F0.4: "render por tipo, findings sin diff"). */
  rcs.forEach(async rc=>{
    const box=document.getElementById('rc-diff-'+rc.project_id);
    try{
      const r=await fetchWithTimeout(
        API_BASE+'/api/v1/layer8/missions/'+rc.project_id+'/diff',
        {headers:headers()}, DIFF_FETCH_TIMEOUT_MS,
      );
      if(!box) return;
      if(!r.ok){
        box.innerHTML='<span style="color:var(--fail)">Error HTTP '+r.status+' al cargar el diff.</span>';
        return;
      }
      const txt=await r.json();
      const lines=(typeof txt==='string'?txt:'').slice(0,1000).split('\n');
      box.innerHTML=lines.map(l=>{
        const s=l.replace(/</g,'&lt;').replace(/>/g,'&gt;');
        if(l.startsWith('+')) return '<span class="add">'+s+'</span>';
        if(l.startsWith('-')) return '<span class="del">'+s+'</span>';
        return '<span class="ctx">'+s+'</span>';
      }).join('\n');
    }catch(e){
      if(!box) return;
      const isTimeout = e.name==='AbortError';
      box.innerHTML='<span style="color:var(--fail)">'
        +(isTimeout?'Tiempo de espera agotado ('+(DIFF_FETCH_TIMEOUT_MS/1000)+'s) al cargar el diff.'
                   :'Error de red al cargar el diff: '+e.message)
        +'</span>';
    }
  });
}
