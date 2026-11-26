/* 真实分析工作台：把 /api/tasks/{id}/analysis 接入定稿分析页。
   本模块只构建状态、管理轮询与实时计时；DOM 更新统一交给 app.js 的
   renderAnalysisScreen 做增量渲染，避免重复写 DOM 造成闪烁/滚动跳动。 */

import { tasksApi } from '../core/api.js';
import { toast } from '../core/ui.js';

const STORAGE_KEY = 'char_cons_active_analysis';
const POLL_RUNNING_MS = 1200;
const POLL_ERROR_MS = 2000;
const ERROR_TOAST_INTERVAL_MS = 30000;

const STATUS_PHASE = {
  idle: 'idle',
  running: 'running',
  retrying: 'retrying',
  paused: 'paused',
  completed: 'complete',
  partial: 'partial',
  failed: 'failed',
};

let taskId = null;
let taskName = '';
let pollTimer = null;
let clockTimer = null;
let terminal = false;
let active = false;
let observationsCache = new Map();
let report = null;
let detailCache = null;
let lastStatus = null;
let autoFocused = false;
let lastErrorToastAt = 0;
/* 任务代次：切换/取消任务后，在途响应一律丢弃，避免旧任务状态写回。 */
let runId = 0;
/* 从新建页启动分析时，暂存已上传的本地镜头，服务端状态回来后合并回 STATE.shots。 */
let carriedCreateShots = new Map();

function isCurrent(run, id) {
  return run === runId && id === taskId;
}

function $(selector) {
  return document.querySelector(selector);
}

function state() {
  return window.__CCS?.STATE || null;
}

function setModeNote(text) {
  // 模式标记并入运行状态卡的状态胶囊，由 app.js 渲染，这里只维护状态
  const current = state();
  if (current?.analysis) current.analysis.modeNote = text;
}

function stopDemoTimers() {
  const analysis = state()?.analysis;
  if (!analysis) return;
  for (const timer of analysis.timers || []) clearTimeout(timer);
  analysis.timers = [];
}

function stopClock() {
  if (clockTimer) {
    clearTimeout(clockTimer);
    clockTimer = null;
  }
}

/* 对齐到「已用时」的整秒边界再刷新：固定 1 秒轮询会因事件循环延迟产生
   0/2 秒跳变，按取整后的下一边界调度可让秒数均匀递增。 */
function scheduleClockTick() {
  const startedAt = Date.parse(state()?.analysis?.startedAt || '');
  const aligned = Number.isFinite(startedAt);
  const elapsed = aligned ? Math.max(0, Date.now() - startedAt) : 0;
  const delay = aligned ? 1000 - (elapsed % 1000) : 1000;
  clockTimer = setTimeout(() => {
    clockTimer = null;
    const current = state();
    if (!current) return;
    if (current.screen === 'analysis') window.__CCS?.updateAnalysisClock?.();
    const running = lastStatus && ['running', 'retrying'].includes(lastStatus.status);
    if (running) scheduleClockTick();
  }, Math.min(1000, Math.max(50, delay)));
}

function startClock() {
  if (clockTimer) return;
  scheduleClockTick();
}

function rememberTask(id, name) {
  taskId = id;
  taskName = name || '';
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ taskId, taskName }));
  } catch {
    /* 浏览器禁用会话存储时不影响当前页面 */
  }
}

function forgetTask() {
  runId += 1;
  taskId = null;
  taskName = '';
  terminal = false;
  active = false;
  report = null;
  detailCache = null;
  lastStatus = null;
  autoFocused = false;
  observationsCache = new Map();
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
  stopClock();
  const current = state();
  if (current) {
    delete current.realObservations;
    const analysis = current.analysis;
    analysis.realMode = false;
    analysis.started = false;
    analysis.complete = false;
    analysis.phase = 'idle';
    analysis.statuses = [];
    analysis.observedCounts = [];
    analysis.verdictCounts = {};
    analysis.issueCount = 0;
    analysis.unknownCount = 0;
    analysis.viewIndex = 0;
    analysis.progress = 0;
    analysis.stage = 0;
    analysis.stageName = '';
    analysis.stageNames = null;
    analysis.etaSeconds = null;
    analysis.suggestionReady = 0;
    analysis.suggestionTotal = 0;
    analysis.startedAt = null;
    analysis.endedAt = null;
    analysis.connectionLost = false;
    analysis.shotErrors = {};
    analysis.subjects = {};
    window.__CCS?.resetAnalysisView?.();
  }
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

function restoreTask() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw);
    if (value && typeof value.taskId === 'string') {
      taskId = value.taskId;
      taskName = value.taskName || '';
      return value;
    }
  } catch {
    /* ignore */
  }
  return null;
}

function resetRealState() {
  const current = state();
  if (!current) return;
  current.shots = [];
  current.issues = [];
  current.unknowns = [];
  current.realObservations = {};
  current.selectedShot = null;
  const analysis = current.analysis;
  analysis.started = false;
  analysis.complete = false;
  analysis.partial = false;
  analysis.phase = 'idle';
  analysis.timers = [];
  analysis.current = 0;
  analysis.viewIndex = 0;
  analysis.progress = 0;
  analysis.stage = 0;
  analysis.statuses = [];
  analysis.observedCounts = [];
  analysis.verdictCounts = {};
  analysis.issueCount = 0;
  analysis.unknownCount = 0;
  analysis.taskName = taskName;
  analysis.characterName = '';
  analysis.realMode = true;
  analysis.modeNote = '真实任务';
  analysis.stageName = '';
  analysis.stageNames = null;
  analysis.etaSeconds = null;
  analysis.suggestionReady = 0;
  analysis.suggestionTotal = 0;
  analysis.startedAt = null;
  analysis.endedAt = null;
  analysis.connectionLost = false;
  analysis.shotErrors = {};
  analysis.subjects = {};
  analysis.errorMessage = '';
  window.__CCS?.resetAnalysisView?.();
}

function shotImageUrl(id, shotId, variant = 'current') {
  return `/api/tasks/${encodeURIComponent(id)}/shots/${encodeURIComponent(shotId)}/image?variant=${variant}`;
}

async function loadObservations(run, id, shot) {
  const cached = observationsCache.get(shot.shotId);
  if (cached) return cached;
  if (shot.analysisStatus !== 'ok') return { observations: [], subject: null };
  try {
    // 直接 fetch，避免旧模块缓存导致 tasksApi 新增方法不可用。
    const response = await fetch(
      `/api/tasks/${encodeURIComponent(id)}/shots/${encodeURIComponent(shot.shotId)}/observations`,
      { credentials: 'same-origin', cache: 'no-store' },
    );
    if (!isCurrent(run, id)) return { observations: [], subject: null };
    if (!response.ok) return { observations: [], subject: null };
    const data = await response.json();
    if (!isCurrent(run, id)) return { observations: [], subject: null };
    const value = {
      observations: data.observations || [],
      subject: data.subject || null,
    };
    if (value.observations.length) observationsCache.set(shot.shotId, value);
    return value;
  } catch {
    return { observations: [], subject: null };
  }
}

function toObservationEntries(items, verdicts = null) {
  return items.map((item) => {
    const verdict = verdicts?.get(item.attributeId) || null;
    const hidden = item.visibility === 'not_visible';
    return {
      attributeId: item.attributeId,
      name: item.attributeName || item.attributeId,
      observed: item.observedValue || '—',
      verdict,
      evidence: hidden ? item.visibilityReason || '不可见' : item.evidence || '—',
    };
  });
}

function buildReportVerdicts(data) {
  const map = new Map();
  for (const row of data.matrix || []) {
    for (const cell of row.cells || []) {
      map.set(`${cell.shotCode}:${row.attributeId}`, cell.verdict);
    }
  }
  return map;
}

async function fetchReportIfReady(run, id, status) {
  if (!['completed', 'partial'].includes(status.status)) return null;
  if (report) return report;
  try {
    const value = await tasksApi.report(id);
    if (!isCurrent(run, id)) return null;
    report = value;
    return report;
  } catch {
    return null;
  }
}

async function loadDetail(run, id) {
  if (detailCache) return detailCache;
  try {
    const value = await tasksApi.get(id);
    if (!isCurrent(run, id)) return null;
    detailCache = value;
  } catch {
    detailCache = null;
  }
  return detailCache;
}

function progressPeak(previous, next) {
  return Math.max(Number(previous) || 0, Math.min(100, Number(next) || 0));
}

async function buildState(status, run, id) {
  const current = state();
  if (!current || !isCurrent(run, id)) return;
  const previousView = Number.isInteger(current.analysis?.viewIndex)
    ? current.analysis.viewIndex
    : 0;

  const detail = await loadDetail(run, id);
  if (!isCurrent(run, id)) return;
  if (detail) {
    taskName = detail.name || detail.characterName || taskName;
  }

  const shots = status.shots || [];
  const reportData = await fetchReportIfReady(run, id, status);
  if (!isCurrent(run, id)) return;
  const byCurrent = status.currentShot
    ? { [status.currentShot.shotCode]: status.currentShot.observations || [] }
    : {};

  const observations = {};
  const subjects = {};
  const shotErrors = {};
  const shotModels = [];
  const verdictCounts = {};
  // 分析页会用服务端镜头模型替换 STATE.shots；保留新建页已上传的本地文件与展示字段，
  // 否则返回新建页时图片还在、但「开始检查」会以“没有真实图片”拒绝。
  const previousShots = carriedCreateShots;
  for (const shot of shots) {
    const loaded = await loadObservations(run, id, shot);
    if (!isCurrent(run, id)) return;
    let items = loaded.observations;
    if (!items.length && byCurrent[shot.shotCode]) {
      items = byCurrent[shot.shotCode];
    }
    // 判定结果由状态接口随判定完成逐步返回，不再等到整份报告完成。
    const verdicts = new Map(Object.entries(shot.verdicts || {}));
    if (!verdicts.size) {
      for (const row of reportData?.matrix || []) {
        const cell = row.cells?.find((entry) => entry.shotCode === shot.shotCode);
        if (cell?.verdict) verdicts.set(row.attributeId, cell.verdict);
      }
    }
    observations[shot.shotCode] = toObservationEntries(items, verdicts);
    subjects[shot.shotCode] = loaded.subject || null;
    shotErrors[shot.shotCode] = {
      code: shot.errorCode || null,
      message: shot.errorMessage || null,
    };
    verdictCounts[shot.shotCode] = {
      inconsistent: Number(shot.inconsistent) || 0,
      unknown: Number(shot.unknown) || 0,
      judged: Boolean(shot.judged || verdicts.size),
    };
    const previous = previousShots.get(shot.shotCode);
    shotModels.push({
      id: shot.shotCode,
      shotId: shot.shotId,
      image: shotImageUrl(id, shot.shotId, 'current'),
      thumb: shotImageUrl(id, shot.shotId, 'thumb'),
      nativeFile: previous ? previous.nativeFile : null,
      ...(previous
        ? {
            file: previous.file,
            note: previous.note,
            quality: previous.quality,
            qualityLabel: previous.qualityLabel,
            progress: previous.progress,
          }
        : {}),
    });
  }

  // 所有异步读取完成后再校验一次，旧任务的迟到响应不得写入当前状态。
  if (!isCurrent(run, id)) return;

  current.shots = shotModels;
  current.issues = (reportData?.issues || []).map((item) => ({
    id: item.id,
    shot: item.shotCode,
  }));
  current.unknowns = (reportData?.unknownItems || []).map((item) => ({
    id: item.id,
    shot: item.shotCode,
  }));
  current.realObservations = observations;

  const analysis = current.analysis;
  const isTerminal = ['completed', 'partial', 'failed'].includes(status.status);
  analysis.started = status.status !== 'idle';
  analysis.realMode = true;
  analysis.taskName = taskName;
  analysis.characterName = detail?.characterName || analysis.characterName || '';
  analysis.statusText = status.status;
  analysis.phase = STATUS_PHASE[status.status] || 'running';
  analysis.complete = ['completed', 'partial'].includes(status.status);
  analysis.partial = status.status === 'partial';
  analysis.timers = [];
  analysis.progress = progressPeak(analysis.progress, status.progress);
  const stageIndex = Math.max(0, Math.min(5, Number(status.stage?.index || 1) - 1));
  analysis.stage = stageIndex;
  analysis.stageName = status.stage?.name || '';
  analysis.stageNames = Array.isArray(status.stages) && status.stages.length
    ? status.stages.map((item) => item.name)
    : null;
  const rawEta = status.etaSeconds;
  const etaValue = rawEta === null || rawEta === undefined || rawEta === ''
    ? null
    : Number(rawEta);
  analysis.etaSeconds = Number.isFinite(etaValue) && etaValue >= 0 ? etaValue : null;
  analysis.suggestionReady = Number(status.suggestions?.ready) || 0;
  analysis.suggestionTotal = Number(status.suggestions?.total) || 0;
  analysis.startedAt = status.startedAt || analysis.startedAt;
  analysis.endedAt = isTerminal || status.status === 'paused'
    ? status.updatedAt || analysis.endedAt || new Date().toISOString()
    : null;
  analysis.connectionLost = false;
  analysis.shotErrors = shotErrors;
  analysis.subjects = subjects;
  analysis.errorMessage = status.error?.message || '';
  analysis.modeNote = '真实任务';
  analysis.statuses = shots.map((shot) => {
    if (shot.analysisStatus === 'failed') return 'failed';
    // 服务重启会把任务置 paused，但在途镜头可能仍是 analyzing；不要显示永久转圈。
    if (status.status === 'paused' && shot.analysisStatus === 'analyzing') return 'pending';
    if (shot.analysisStatus === 'analyzing') return 'analyzing';
    if (shot.analysisStatus !== 'ok') return 'pending';
    return verdictCounts[shot.shotCode]?.inconsistent > 0 ? 'issue' : 'ok';
  });
  analysis.observedCounts = shots.map(
    (shot) => (observations[shot.shotCode] || []).length,
  );
  analysis.verdictCounts = verdictCounts;
  analysis.issueCount = shots.reduce(
    (sum, shot) => sum + (Number(shot.inconsistent) || 0),
    0,
  );
  analysis.unknownCount = shots.reduce(
    (sum, shot) => sum + (Number(shot.unknown) || 0),
    0,
  );

  const analyzingIndex = shots.findIndex((shot) => shot.analysisStatus === 'analyzing');
  const firstPending = shots.findIndex((shot) => shot.analysisStatus === 'pending');
  const focus = analyzingIndex >= 0
    ? analyzingIndex
    : firstPending >= 0
      ? firstPending
      : Math.max(0, shots.length - 1);
  analysis.current = Math.max(0, focus);
  // 构建期间用户可能已点选其他镜头：以最新选择为准，避免被本轮状态覆盖。
  const latestView = Number.isInteger(current.analysis?.viewIndex)
    ? current.analysis.viewIndex
    : previousView;
  let viewIndex = Number.isInteger(latestView) ? latestView : analysis.current;
  viewIndex = Math.max(0, Math.min(Math.max(0, shots.length - 1), viewIndex));
  if (!autoFocused && analyzingIndex >= 0) {
    viewIndex = analyzingIndex;
    autoFocused = true;
  } else if (!autoFocused && shots.length) {
    autoFocused = true;
  }
  analysis.viewIndex = viewIndex;
}

async function render(status, run = runId, id = taskId) {
  if (!isCurrent(run, id)) return;
  lastStatus = status;
  await buildState(status, run, id);
  if (!isCurrent(run, id)) return;
  const current = state();
  if (!current) return;
  if (current.screen === 'analysis') {
    window.__CCS.renderAnalysisScreen();
    window.__CCS.updateAnalysisClock?.();
  }
  if (['running', 'retrying'].includes(status.status)) startClock();
  else stopClock();
}

async function poll(run = runId) {
  const id = taskId;
  if (!id || !window.__CCS || !isCurrent(run, id)) return;
  try {
    const status = await tasksApi.analysis(id);
    if (!isCurrent(run, id)) return;
    await render(status, run, id);
    if (!isCurrent(run, id)) return;
    if (!['running', 'retrying'].includes(status.status)) {
      terminal = true;
      if (pollTimer) {
        clearTimeout(pollTimer);
        pollTimer = null;
      }
      // 通知浮层据此刷新红点；只在本次任务结束时触发一次
      window.dispatchEvent(new CustomEvent('char_cons:notifications-changed'));
      return;
    }
    pollTimer = setTimeout(() => poll(run), POLL_RUNNING_MS);
  } catch (error) {
    if (!isCurrent(run, id)) return;
    const current = state();
    if (current?.analysis) current.analysis.connectionLost = true;
    if (current?.screen === 'analysis') {
      window.__CCS.renderAnalysisScreen();
      window.__CCS.updateAnalysisClock?.();
    }
    const now = Date.now();
    if (now - lastErrorToastAt > ERROR_TOAST_INTERVAL_MS) {
      lastErrorToastAt = now;
      toast(error.message || '分析状态查询失败，正在自动重试');
    }
    pollTimer = setTimeout(() => poll(run), POLL_ERROR_MS);
  }
}

export async function showRealAnalysis(id, name = '', options = {}) {
  const run = ++runId;
  rememberTask(id, name);
  carriedCreateShots = options.keepCreateShots
    ? new Map(
        (state()?.shots || [])
          .filter((shot) => shot.nativeFile)
          .map((shot) => [shot.id, shot]),
      )
    : new Map();
  active = true;
  terminal = false;
  report = null;
  detailCache = null;
  lastStatus = null;
  autoFocused = false;
  lastErrorToastAt = 0;
  observationsCache = new Map();
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
  stopClock();
  stopDemoTimers();
  resetRealState();
  window.__CCS?.showScreen('analysis');
  stopDemoTimers();
  setModeNote('真实任务');
  const demoButton = document.querySelector('[data-action="simulate-partial"]');
  if (demoButton) demoButton.hidden = true;
  window.__CCS?.renderAnalysisScreen?.();
  await poll(run);
}

function openRealReport() {
  if (!taskId) return false;
  const status = lastStatus;
  if (!status || !['completed', 'partial'].includes(status.status)) {
    toast('分析尚未完成，请稍候');
    return true;
  }
  active = false;
  stopClock();
  import('./results.js').then(({ showRealReport }) => showRealReport(taskId));
  return true;
}

async function cancelRealAnalysis() {
  const id = taskId;
  const run = runId;
  if (!id) return;
  try {
    const result = await tasksApi.cancelAnalysis(id);
    if (!isCurrent(run, id)) return;
    // 进程重启后的 paused 任务后端不会复位；不要谎报“已取消”。
    if (result && result.status && result.status !== 'idle') {
      toast('任务当前为已暂停，无法直接取消；请在历史报告重新开始分析');
      return;
    }
    forgetTask();
    toast('分析已取消，任务保留在历史报告');
    window.__CCS?.showScreen('history');
    import('./history.js').then(({ refreshHistory }) => refreshHistory());
  } catch (error) {
    toast(error.message || '取消失败');
  }
}

export function initAnalysisIntegration() {
  const restored = restoreTask();
  const applyRestoredOnBoot = () => {
    if (restored && window.location.hash.replace('#', '') === 'analysis') {
      showRealAnalysis(restored.taskId, restored.taskName);
    }
  };

  document.addEventListener(
    'click',
    async (event) => {
      const start = event.target.closest('[data-action="start-analysis"]');
      if (start) {
        const shots = window.__CCS?.STATE?.shots || [];
        if (!shots.some((shot) => shot.nativeFile)) {
          forgetTask();
        }
        return;
      }

      const navAnalysisWithoutTask = event.target.closest('[data-nav="analysis"]');
      if (navAnalysisWithoutTask && !taskId) {
        event.preventDefault();
        event.stopPropagation();
        stopDemoTimers();
        toast('请先新建检测任务并上传真实镜头');
        window.__CCS?.showScreen('create');
        return;
      }

      if (!taskId) return;
      const navAnalysis = event.target.closest('[data-nav="analysis"]');
      if (navAnalysis) {
        event.preventDefault();
        event.stopPropagation();
        stopDemoTimers();
        if (window.__CCS.STATE.screen !== 'analysis') {
          window.__CCS.showScreen('analysis');
        }
        stopDemoTimers();
        setModeNote('真实任务');
        if (lastStatus) {
          await render(lastStatus);
        } else {
          window.__CCS.renderAnalysisScreen();
          window.__CCS.updateAnalysisClock?.();
        }
        if (!terminal && !pollTimer) pollTimer = setTimeout(() => poll(runId), 300);
        return;
      }

      const navResults = event.target.closest('[data-nav="results"]');
      if (navResults && window.__CCS?.STATE?.screen === 'analysis') {
        event.preventDefault();
        event.stopPropagation();
        openRealReport();
        return;
      }

      if (event.target.closest('[data-action="cancel-analysis"]')) {
        event.preventDefault();
        event.stopPropagation();
        await cancelRealAnalysis();
        return;
      }
      if (event.target.closest('[data-action="retry-shot"]')) {
        event.preventDefault();
        event.stopPropagation();
        toast('单镜头重新观察尚未接入；请在历史报告重试整个任务');
      }
    },
    true,
  );

  window.addEventListener('hashchange', () => {
    if (window.location.hash.replace('#', '') === 'analysis' && taskId && active) {
      window.__CCS?.showScreen('analysis');
      if (lastStatus) render(lastStatus);
      else {
        window.__CCS.renderAnalysisScreen();
        window.__CCS.updateAnalysisClock?.();
      }
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applyRestoredOnBoot, { once: true });
  } else {
    setTimeout(applyRestoredOnBoot, 0);
  }
}
