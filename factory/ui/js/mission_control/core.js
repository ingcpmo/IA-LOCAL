/* W5 — helpers transversales de Mission Control (sin dependencias de vistas). */

import { state } from './state.js';

/* ---- design interactions ---- */
export function toast(msg){
  let t=document.getElementById('_toast');
  if(!t){ t=document.createElement('div'); t.id='_toast';
    t.style.cssText='position:fixed;right:22px;bottom:22px;background:#18242e;border:1px solid #26303b;color:#e8eef4;padding:11px 15px;border-radius:10px;font-size:13px;z-index:50;box-shadow:0 8px 30px rgba(0,0,0,.4)';
    document.body.appendChild(t);}
  t.textContent=msg; t.style.opacity='1';
  clearTimeout(t._h); t._h=setTimeout(()=>t.style.opacity='0',2200);
}

export function fakeSubmit(msg){ toast(msg+(state.connected?'':' · (vista de diseño)')); return false; }

/* ---- chip helpers ---- */
export function chipOk(ok){ return ok?'c-pass':'c-fail'; }
export function chipTxt(ok,a,b){ return ok?(a||'pass'):(b||'fail'); }

/* ---- escapes / filtros ---- */
export function _esc(pid){ return pid.replace(/[^a-zA-Z0-9_-]/g,'_'); }

const _FILTER_PATHS=['.pytest_cache','__pycache__','.pyc','.env','.claude','data/chroma'];
export function _filterFile(path){ return !_FILTER_PATHS.some(p=>path.includes(p)); }

export function _gmpNA(v){
  if(v===null||v===undefined||v==='no_disponible'||(Array.isArray(v)&&v.length===0)) {
    return '<span style="color:var(--faint);font-style:italic">no disponible</span>';
  }
  return v;
}
export function _gmpEscHtml(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

/* W6.1 — llena un selector de misión conservando la selección actual.
   Devuelve el project_id efectivo (seleccionado o primero). */
export function fillMissionSelect(selectId, missions){
  const sel=document.getElementById(selectId); if(!sel) return null;
  const current=sel.value;
  const ids=(missions||[]).map(m=>m.project_id);
  sel.innerHTML=ids.map(id=>'<option value="'+_esc(id)+'">'+_esc(id)+'</option>').join('')
    ||'<option value="">(sin misiones)</option>';
  if(current&&ids.includes(current)) sel.value=current;
  return sel.value||null;
}
