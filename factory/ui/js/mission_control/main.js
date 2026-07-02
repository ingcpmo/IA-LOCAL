/* W5 — punto de entrada de Mission Control.
   Cablea la navegación y expone en `window` las funciones que los
   handlers inline del HTML (estático y generado) invocan por nombre
   global — los módulos ES no crean globals por sí mismos. */

import { show, connect, refresh } from './refresh.js';
import { toast, fakeSubmit } from './core.js';
import { submitCreateMission, submitMissionDecision } from './missions.js';
import { submitRCDecision } from './review.js';
import {
  viewHeadlessLogs, submitHeadlessOff, submitModelChange,
  refreshPipeline, refreshPipelineIfConnected,
} from './pipeline.js';
import {
  openMissionDetail, closeDetail, toggleGrp, toggleEv,
  loadEv_design, loadEv_code, loadEv_tests, loadEv_headless,
  loadEv_rcs, loadEv_deploy, loadEv_audit,
  loadDesignFile, loadFileContent, loadRcFile, loadDepFile,
  submitMarkCanonical, confirmF5,
} from './detail_panel.js';
import { promptRunTest, runSuite } from './tests_console.js';
import { downloadGmpReportPdf } from './gmp_dashboard.js';

Object.assign(window, {
  show, connect, refresh, toast, fakeSubmit,
  submitCreateMission, submitMissionDecision, submitRCDecision,
  viewHeadlessLogs, submitHeadlessOff, submitModelChange,
  refreshPipeline, refreshPipelineIfConnected,
  openMissionDetail, closeDetail, toggleGrp, toggleEv,
  loadEv_design, loadEv_code, loadEv_tests, loadEv_headless,
  loadEv_rcs, loadEv_deploy, loadEv_audit,
  loadDesignFile, loadFileContent, loadRcFile, loadDepFile,
  submitMarkCanonical, confirmF5,
  promptRunTest, runSuite, downloadGmpReportPdf,
});

document.querySelectorAll('#nav button').forEach(b=>{
  b.addEventListener('click',()=>show(b.dataset.v,b));
});
