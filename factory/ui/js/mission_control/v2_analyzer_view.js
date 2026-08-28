/* WP-G -- Panel del Analizador Documental GMP V2 en Mission Control.
   docs_plan/PLAN_HARDENING_ANALIZADOR_GMP_LOCAL_V2.md WP-G ; D-6.

   SOLO LECTURA. Consume los 6 endpoints GET ya publicados en
   /api/v1/v2-analyzer/* (factory/api/routes/v2_analyzer.py). NO hay ninguna
   llamada de escritura; el front NO replica adjudicacion, riesgo, gobernanza
   ni cambio de estado -- eso vive en "Revision humana" / "Gobernanza".

   Muestra EXPLICITAMENTE (WP-G gate): el fingerprint de la corrida (WP-A), el
   estado de adecuacion por documento (WP-B) y el evidence_basis por finding
   (WP-B) -- si no, la UI reintroduce la confusion que WP-B elimina. */
import { API_BASE, headers } from './state.js';

const V2 = API_BASE + '/api/v1/v2-analyzer';

function esc(s){ return String(s ?? '').replace(/[&<>"]/g, c => (
  {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

async function _get(path){
  const r = await fetch(V2 + path, { headers: headers() });   // GET -- unica operacion
  if(!r.ok) throw new Error(path + ' -> ' + r.status);
  return r;
}

export async function refreshV2Analyzer(){
  const box = document.getElementById('v2-runs-list');
  const detail = document.getElementById('v2-run-detail');
  if(detail) detail.innerHTML = '';
  if(!box) return;
  box.innerHTML = 'cargando…';
  try{
    const runs = (await (await _get('/runs')).json()).runs || [];
    if(!runs.length){ box.innerHTML = '<p class="muted">sin corridas V2 persistidas.</p>'; return; }
    box.innerHTML = '<table class="tbl"><thead><tr>'
      + '<th>run_id</th><th>proyecto</th><th>generada</th><th>reg/func/tec</th>'
      + '<th>marca</th><th>qa_status</th><th></th></tr></thead><tbody>'
      + runs.map(r => {
          const c = r.counts || {};
          return '<tr><td><code>' + esc(r.run_id) + '</code></td>'
            + '<td>' + esc(r.project_id) + '</td>'
            + '<td>' + esc(r.generated_at) + '</td>'
            + '<td>' + esc((c.regulatory ?? '·') + ' / ' + (c.functional ?? '·') + ' / ' + (c.technical ?? '·')) + '</td>'
            + '<td><small>' + esc(r.mark) + '</small></td>'
            + '<td>' + esc(r.qa_status) + '</td>'
            + '<td><button onclick="openV2Run(\'' + esc(r.run_id) + '\')">ver</button></td></tr>';
        }).join('')
      + '</tbody></table>';
  }catch(e){ box.innerHTML = '<p class="fail">error: ' + esc(e.message) + '</p>'; }
}

export async function openV2Run(runId){
  const detail = document.getElementById('v2-run-detail');
  if(!detail) return;
  detail.innerHTML = 'cargando <code>' + esc(runId) + '</code>…';
  try{
    const run = await (await _get('/runs/' + encodeURIComponent(runId))).json();
    const fnd = await (await _get('/runs/' + encodeURIComponent(runId) + '/findings')).json();
    const a = run.audit_metadata || {};
    const man = run.manifest || {};

    // --- fingerprint de la corrida (WP-A) ---
    const fp = '<div class="v2-card"><h4>Fingerprint de la corrida (WP-A)</h4>'
      + '<div class="kv"><span>INPUT_CONFIG_FINGERPRINT</span><code>' + esc(a.input_config_fingerprint || man.input_config_fingerprint || '—') + '</code></div>'
      + '<div class="kv"><span>FINDINGS_FINGERPRINT</span><code>' + esc(a.findings_fingerprint || man.findings_fingerprint || '—') + '</code></div>'
      + '<div class="kv"><span>engine · llm_calls · egress</span><code>' + esc((a.engine || '—') + ' · ' + (a.llm_calls ?? '—') + ' · ' + (a.document_egress_bytes ?? '—')) + '</code></div>'
      + (a.run_attestation ? '<div class="kv"><span>active_engine · routing_source</span><code>'
          + esc((a.run_attestation.active_engine || '—') + ' · ' + (a.run_attestation.routing_source || '—')) + '</code></div>' : '')
      + '</div>';

    // --- adecuacion por documento (WP-B) ---
    const verdicts = a.adequacy_verdicts || {};
    const wd = a.coverage_would_degrade || {};
    const adq = '<div class="v2-card"><h4>Adecuacion de extraccion por documento (WP-B · modo '
      + esc(a.analysis_coverage_mode || 'OBSERVE') + ')</h4>'
      + (Object.keys(verdicts).length
          ? '<table class="tbl"><thead><tr><th>documento</th><th>verdict</th></tr></thead><tbody>'
            + Object.entries(verdicts).map(([d,v]) =>
                '<tr><td><code>' + esc(d) + '</code></td><td class="' + (v === 'ANALYZABLE' ? 'pass' : 'warn') + '">'
                + esc(v) + '</td></tr>').join('')
            + '</tbody></table>'
          : '<p class="muted">sin datos de adecuacion en esta corrida.</p>')
      + '<div class="kv"><span>would_degrade (informativo · 0 supresiones)</span><code>'
      + esc('true=' + (wd.would_degrade_true ?? '—') + '  false=' + (wd.would_degrade_false ?? '—')) + '</code></div>'
      + '<p class="muted">' + esc(a.wp_b_effect || '') + '</p></div>';

    // --- evidence_basis por finding (WP-B) ---
    const all = [].concat(fnd.regulatory || [], fnd.functional || [], fnd.technical || []);
    const eb = {};
    all.forEach(f => { const k = f.evidence_basis || 'null'; eb[k] = (eb[k] || 0) + 1; });
    const ebCard = '<div class="v2-card"><h4>evidence_basis (WP-B) — ' + all.length + ' findings</h4>'
      + '<div class="kv"><span>por base epistemica</span><code>'
      + esc(Object.entries(eb).map(([k,n]) => k + '=' + n).join('  ') || '—') + '</code></div>'
      + '<table class="tbl"><thead><tr><th>clase</th><th>subtype</th><th>doc</th><th>pág</th>'
      + '<th>evidence_basis</th><th>machine_state</th><th>human_state</th></tr></thead><tbody>'
      + all.slice(0, 60).map(f =>
          '<tr><td>' + esc(f.class) + '</td><td>' + esc(f.subtype) + '</td>'
          + '<td><code>' + esc(f.document) + '</code></td><td>' + esc(f.page) + '</td>'
          + '<td>' + esc(f.evidence_basis) + '</td><td>' + esc(f.machine_state) + '</td>'
          + '<td>' + esc(f.human_state) + '</td></tr>').join('')
      + '</tbody></table>'
      + (all.length > 60 ? '<p class="muted">(mostrando 60 de ' + all.length + ')</p>' : '')
      + '</div>';

    // --- marcas / estado de revision humana ---
    const hrs = run.human_review_state || {};
    const marks = '<div class="v2-card"><h4>Estado</h4>'
      + '<div class="kv"><span>marca</span><code>' + esc(man.mark) + '</code></div>'
      + '<div class="kv"><span>qa_status</span><code>' + esc(man.qa_status) + '</code></div>'
      + '<div class="kv"><span>todos UNREVIEWED</span><code>' + esc(hrs.all_unreviewed) + '</code></div>'
      + '<div class="kv"><span>estados prohibidos presentes</span><code>' + esc(hrs.forbidden_states_present) + '</code></div>'
      + '</div>';

    detail.innerHTML = '<div class="v2-detail"><h3>Corrida <code>' + esc(runId) + '</code>'
      + ' <span class="badge">SOLO LECTURA</span></h3>'
      + '<p class="muted">La adjudicacion y toda decision GMP se hacen en "Revision humana" / "Gobernanza". '
      + 'Este panel no muta ningun estado.</p>'
      + fp + adq + ebCard + marks + '</div>';
  }catch(e){ detail.innerHTML = '<p class="fail">error: ' + esc(e.message) + '</p>'; }
}
