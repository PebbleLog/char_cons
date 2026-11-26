/* 优化提示词页：真实建议、候选生成、自动预检、采用与单镜头复检。
   复用定稿 DOM/CSS，只替换数据源与交互；演示模式仍由原型 app.js 负责。 */

import { tasksApi } from '../core/api.js';
import { ensurePrivacyAcknowledged } from '../core/privacy.js';
import { escapeHtml, toast } from '../core/ui.js';

let active = false;
let state = null;
let taskId = null;
let currentShotId = null;
let selectedCandidateId = null;
let pollTimer = null;
let pollGenerationId = null;
let busy = false;
const suggestionCache = new Map();
/* 刷新后按会话恢复真实优化页，避免退回原型演示数据 */
const CONTEXT_KEY = 'char_cons_active_optimizer';

function $(selector) {
  return document.querySelector(selector);
}

function rememberContext() {
  if (!taskId || !currentShotId) return;
  try {
    localStorage.setItem(
      CONTEXT_KEY,
      JSON.stringify({ taskId, shotId: currentShotId })
    );
  } catch {
    /* 浏览器禁用本地存储时不影响当前页面 */
  }
  try {
    const url = new URL(window.location.href);
    url.searchParams.set('task', taskId);
    url.searchParams.set('shot', currentShotId);
    history.replaceState(null, '', url);
  } catch {
    /* ignore */
  }
}

function readContext() {
  try {
    const raw = localStorage.getItem(CONTEXT_KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw);
    return saved?.taskId && saved?.shotId ? saved : null;
  } catch {
    return null;
  }
}

function clearContext() {
  try {
    localStorage.removeItem(CONTEXT_KEY);
  } catch {
    /* ignore */
  }
  try {
    const url = new URL(window.location.href);
    url.searchParams.delete('task');
    url.searchParams.delete('shot');
    history.replaceState(null, '', url);
  } catch {
    /* ignore */
  }
}

function icon(name) {
  return `<svg class="icon"><use href="#i-${name}"/></svg>`;
}

function pill(text, kind, extra = '') {
  return `<span class="status-pill is-${kind}" ${extra}><i></i>${escapeHtml(text)}</span>`;
}

function setEyebrow(text) {
  const el = $('#page-eyebrow');
  if (!el) return;
  const [root, node] = text.split(' / ');
  el.setAttribute('aria-label', text);
  el.innerHTML = node
    ? `<span class="eb-root">${escapeHtml(root)}</span><span class="eb-sep" aria-hidden="true"></span><span class="eb-node">${escapeHtml(node)}</span>`
    : `<span class="eb-root">${escapeHtml(root)}</span>`;
}

function currentShotCode() {
  return state?.issue?.shotCode || '';
}

function currentAdoption() {
  if (!state) return null;
  return state.adoption || state.shotAdoptions?.[currentShotCode()] || null;
}

function currentGeneration() {
  return state?.generation || null;
}

function currentCandidates() {
  return currentGeneration()?.candidates || [];
}

function selectedCandidate() {
  const list = currentCandidates();
  if (!list.length) return null;
  const adopted = currentAdoption()?.candidateId;
  return (
    list.find((item) => item.id === selectedCandidateId)
    || list.find((item) => item.id === adopted)
    || list.find((item) => item.recommended)
    || list[0]
  );
}

function generationPhase() {
  const gen = currentGeneration();
  if (!gen) return 'idle';
  if (gen.status === 'pending' || gen.status === 'generating') return 'generating';
  if (gen.status === 'prechecking' || gen.precheckStatus === 'running') return 'prechecking';
  if (!gen.candidates.length) return 'failed';
  return 'complete';
}

function phaseStatus() {
  const adoption = currentAdoption();
  if (adoption) {
    if (adoption.recheckStatus === 'consistent') return ['已采用并复检', 'is-ok'];
    if (adoption.recheckStatus === 'failed') return ['复检失败', 'is-failed'];
    if (adoption.recheckStatus === 'inconsistent') return ['已采用 · 仍不一致', 'is-warn'];
    if (adoption.recheckStatus === 'unknown') return ['已采用 · 无法判断', 'is-warn'];
    return ['正在复检', 'is-live'];
  }
  const gen = currentGeneration();
  const phase = generationPhase();
  if (phase === 'generating') return ['生成中', 'is-live'];
  if (phase === 'prechecking') return ['预检中', 'is-live'];
  if (phase === 'failed') return ['生成失败', 'is-failed'];
  if (gen?.precheckStatus === 'failed') return ['预检未完成', 'is-warn'];
  if (phase === 'complete') return ['预检完成 · 待采用', 'is-idle'];
  return ['待生成', 'is-idle'];
}

function setPageStatus(text, kind) {
  const local = $('#opt-status');
  if (local) {
    local.className = `status-pill ${kind}`;
    local.innerHTML = `<i></i>${escapeHtml(text)}`;
  }
  const top = $('#task-status-pill');
  if (top) {
    top.hidden = false;
    top.className = `status-pill ${kind}`;
    top.innerHTML = `<i></i>${escapeHtml(text)}`;
  }
}

function renderHeader() {
  const issue = state.issue;
  const shot = issue.shotCode;
  $('#opt-title').textContent = `优化 ${shot} · ${issue.attributeName}`;
  const subtitle = state.suggestion?.rationale
    ? state.suggestion.rationale
    : `把实际观察「${issue.observed || '—'}」修正为设定期望「${issue.expected || '与参考镜头一致'}」。`;
  $('#opt-subtitle').textContent = subtitle;
  $('#page-title').textContent = '优化提示词';
  $('#page-subtitle').textContent = `${shot} · ${issue.attributeName} · 修正提示词、候选图与自动预检`;
  setEyebrow(`OPTIMIZER / ${shot}`);
  const [text, kind] = phaseStatus();
  setPageStatus(text, kind);
}

function renderTabs() {
  const container = $('#opt-shot-switch');
  if (!container) return;
  const issue = state.issue;
  const tabs = [...(state.tabs || [])];
  const currentInTabs = tabs.some((tab) => tab.shotId === currentShotId);
  if (!currentInTabs) {
    tabs.unshift({
      shotId: issue.shotId,
      shotCode: issue.shotCode,
      label: `${issue.shotCode} · ${issue.attributeName}`,
      issues: [],
    });
  }
  container.innerHTML = tabs
    .map((tab) => {
      const isCurrent = tab.shotId === currentShotId;
      const adoption = state.shotAdoptions?.[tab.shotCode];
      const rechecked = adoption?.recheckStatus === 'consistent';
      return `<button class="${isCurrent ? 'is-active' : ''} ${rechecked ? 'is-rechecked' : ''}"
        data-real-shot-tab="${escapeHtml(tab.shotId)}"
        title="${rechecked ? '该镜头已完成复检，可查看更新后的报告' : ''}">${escapeHtml(tab.label)}</button>`;
    })
    .join('');
}

function renderPrompt() {
  const suggestion = state.suggestion;
  const issue = state.issue;
  const promptEl = $('#opt-prompt');
  const negativeEl = $('#opt-negative');
  if (!suggestion) {
    promptEl.value = '修正建议暂不可用；点击「重新生成」时会再次尝试生成建议。';
    negativeEl.value = '';
    $('#opt-keypoints').innerHTML = `<p>${icon('alert')}建议生成失败，可重试。</p>`;
    $('#opt-cardplan').textContent = '建议尚未生成';
  } else {
    promptEl.value = suggestion.revisedPrompt || '';
    negativeEl.value = suggestion.negativePrompt || '';
    const points = suggestion.keyPoints || [];
    $('#opt-keypoints').innerHTML = points.length
      ? points.map((point) => `<p>${icon('check')}${escapeHtml(point)}</p>`).join('')
      : `<p>${icon('minus')}暂无修改要点</p>`;
    const plan = suggestion.cardDrawPlan || {};
    const batch = plan.batchSize || state.options.batchSize;
    const refs = (plan.referenceShots || suggestion.referenceShots || []).join(' / ') || '无合格参考镜头';
    const target = (plan.selectionCriteria || [])[0] || `${issue.attributeName}与设定一致`;
    $('#opt-cardplan').textContent = `每批 ${batch} 张 · 参考 ${refs} · ${target} · 负向内容合并进正向提示词`;
  }
  const issues = state.issuesForShot?.length ? state.issuesForShot : [issue];
  const issueLines = issues
    .map(
      (item) =>
        `${item.id} · ${item.attributeName}：期望 ${item.expected || '与参考镜头一致'}，实际 ${item.observed || '—'}`
    )
    .join('<br>');
  $('#opt-issue-context').innerHTML = `
    <b>${escapeHtml(issue.shotCode)} · 本镜头 ${issues.length} 个问题</b>
    <p>${issueLines.split('<br>').map((line) => escapeHtml(line)).join('<br>')}</p>`;

  const refs = suggestion?.referenceShots || [];
  const refPills = $('.ref-pills');
  if (refPills) {
    refPills.innerHTML = refs.length
      ? refs.map((code) => `<span>${escapeHtml(code)} · 角色参考</span>`).join('')
      : '<span>无合格参考镜头</span>';
  }
}

function outcomeLabel(candidate, recommended) {
  if (!candidate) return '无结论';
  if (candidate.state === 'pass') {
    return recommended ? '建议采用' : '预检通过';
  }
  return {
    partial: '部分符合',
    fail: '不建议',
    unknown: '无结论',
  }[candidate.state] || '无结论';
}

function renderCompare() {
  const shot = state.shot;
  const original = $('#opt-original-img');
  original.src = shot.originalUrl;
  original.alt = `原始镜头 ${shot.shotCode}`;
  original.style.visibility = '';
  const originalTag = $('#opt-compare .compare-before .compare-tag');
  if (originalTag) originalTag.textContent = `ORIGINAL · ${shot.shotCode}`;

  const candidate = selectedCandidate();
  const after = $('#opt-after-pane');
  const handle = $('#opt-handle');
  const range = $('#opt-range');
  if (!candidate) {
    after.hidden = true;
    handle.hidden = true;
    range.hidden = true;
    $('#opt-compare-label').textContent =
      generationPhase() === 'generating' ? '生成中 · 候选图尚未返回' : '尚未生成候选图';
    $('#opt-diff-note').textContent = '等待重新生成候选图';
    return;
  }
  after.hidden = false;
  handle.hidden = false;
  range.hidden = false;
  $('#opt-candidate-img').src = candidate.imageUrl;
  $('#opt-candidate-img').alt = `候选图 ${candidate.candidateCode}`;
  const tag = after.querySelector('.compare-tag');
  if (tag) tag.textContent = `CANDIDATE · ${candidate.candidateCode}`;
  const recommended = currentGeneration()?.recommendedCandidateId === candidate.id;
  $('#opt-compare-label').textContent = `${candidate.candidateCode} · ${outcomeLabel(candidate, recommended)}`;
  const issue = state.issue;
  const issues = state.issuesForShot?.length ? state.issuesForShot : [issue];
  $('#opt-diff-note').textContent = issues
    .map(
      (item) =>
        `${item.attributeName}：${item.observed || '—'} → ${item.expected || '与参考镜头一致'}`
    )
    .join('；');
  range.value = 50;
  range.dispatchEvent(new Event('input', { bubbles: true }));
}

function stateClass(candidate) {
  if (candidate.state === 'pass') return 'is-ok';
  if (candidate.state === 'partial') return 'is-warn';
  if (candidate.state === 'fail') return 'is-bad';
  return 'is-muted';
}

function stateIcon(candidate) {
  if (candidate.state === 'pass') return icon('check');
  if (candidate.state === 'fail') return icon('alert');
  return icon('help');
}

function renderCandidates() {
  const grid = $('#opt-candidates');
  const gen = currentGeneration();
  const candidates = currentCandidates();
  const phase = generationPhase();
  const prechecking = phase === 'prechecking';
  const adopted = currentAdoption();
  const selected = selectedCandidate();
  const passCount = candidates.filter((item) => item.state === 'pass').length;

  const count = $('#candidate-count');
  if (phase === 'generating') {
    count.textContent = `生成中 · ${gen?.succeededCount || 0} / ${gen?.requestedCount || state.options.batchSize}`;
  } else if (prechecking) {
    count.textContent = `${candidates.length} 张 · 正在预检`;
  } else if (phase === 'failed') {
    count.textContent = '生成失败 · 可重试';
  } else if (gen) {
    const partial = gen.status === 'partial' ? ' · 部分成功' : '';
    count.textContent = `${candidates.length} 张 · ${passCount ? `${passCount} 张通过` : '无通过'}${partial}`;
  } else {
    count.textContent = '0 张 · 待生成';
  }

  const generateBtn = $('#opt-generate');
  if (generateBtn) {
    generateBtn.disabled = phase === 'generating' || prechecking || busy;
    generateBtn.innerHTML =
      phase === 'generating' || prechecking
        ? `${icon('refresh')}${phase === 'generating' ? '生成中…' : '预检中…'}`
        : `${icon('refresh')}重新生成`;
  }

  if (!candidates.length) {
    if (phase === 'generating' || prechecking) {
      const total = gen?.requestedCount || state.options.batchSize || 4;
      grid.innerHTML = Array.from({ length: total })
        .map(
          () =>
            '<div class="candidate-loading"><div class="candidate-skeleton"></div><div class="candidate-skeleton" style="height:24px"></div></div>'
        )
        .join('');
    } else if (phase === 'failed') {
      grid.innerHTML = `<div class="empty-state small" style="grid-column:1/-1"><span class="empty-icon">${icon('alert')}</span><h4>本批次未生成候选图</h4><p>${escapeHtml(gen?.errorMessage || '请检查生成服务配置后重试。')}</p></div>`;
    } else {
      grid.innerHTML = `<div class="empty-state small" style="grid-column:1/-1"><span class="empty-icon">${icon('image')}</span><h4>尚未生成候选图</h4><p>点击「重新生成」将按当前修正提示词生成 ${state.options.batchSize} 张候选。</p></div>`;
    }
    return;
  }

  grid.innerHTML = candidates
    .map((candidate) => {
      const comparing = selected?.id === candidate.id;
      const recommended = gen?.recommendedCandidateId === candidate.id;
      const isAdopted = adopted?.candidateId === candidate.id;
      const label = prechecking ? '预检中' : outcomeLabel(candidate, recommended);
      const tagText = isAdopted
        ? '已采用'
        : comparing && recommended
          ? '推荐 · 对比中'
          : comparing
            ? '对比中'
            : recommended
              ? '推荐'
              : '';
      const summary = candidate.precheck?.summary || candidate.summary || '预检未完成，请人工核对。';
      return `<button class="candidate-card ${comparing ? 'is-selected' : ''} ${isAdopted ? 'is-adopted' : ''}"
        data-real-candidate="${escapeHtml(candidate.id)}">
        <span class="candidate-img"><img src="${escapeHtml(candidate.thumbUrl)}" alt="候选图 ${escapeHtml(candidate.candidateCode)}">
          <span class="candidate-badge">${escapeHtml(candidate.candidateCode)}</span>
          ${tagText ? `<span class="candidate-tag ${comparing ? 'is-comparing' : 'is-reco'}">${escapeHtml(tagText)}</span>` : ''}
          <span class="candidate-state ${prechecking ? 'is-muted' : stateClass(candidate)}">${prechecking ? icon('refresh') : stateIcon(candidate)}${escapeHtml(label)}</span>
        </span>
        <span class="candidate-copy"><b>${escapeHtml(summary)}</b><span>${escapeHtml(label)}</span>${isAdopted ? `<span class="candidate-adopt-tag">${icon('check')}已采用为当前镜头</span>` : ''}</span>
      </button>`;
    })
    .join('');
}

function criteriaFor(candidate) {
  const plan = state.suggestion?.cardDrawPlan || {};
  const base = plan.selectionCriteria || [];
  const checked = candidate?.precheck?.criteria || [];
  if (checked.length) return checked;
  return base.map((name) => ({
    name,
    passed: null,
    evidence: '预检未返回该项。',
  }));
}

function adoptNote(adoption, candidate) {
  if (adoption) {
    if (adoption.recheckStatus === 'consistent') {
      return `${state.issue.shotCode} 复检完成：问题已关闭。原始镜头已保留，可追溯。`;
    }
    if (adoption.recheckStatus === 'inconsistent') {
      return '复检后仍不一致，问题保持开启，可继续重抽或更换候选。';
    }
    if (adoption.recheckStatus === 'unknown') {
      return '复检后无法判断，问题未显示为已修复；可重抽或人工核对。';
    }
    if (adoption.recheckStatus === 'failed') {
      return '复检失败，当前版本已回滚，问题保持开启；可重试复检。';
    }
    return '正在复检该镜头…';
  }
  if (currentGeneration()?.precheckStatus === 'failed') {
    return '自动预检未完成，候选图仍可查看和采用；是否采用由你决定。';
  }
  if (candidate && candidate.state !== 'pass') {
    return `预检不建议采用 ${candidate.candidateCode}，仍可人工采用并记录推翻预检结果。采用后将仅复检 ${state.issue.shotCode}，原图保留。`;
  }
  return `采用后将仅复检 ${state.issue.shotCode}，并更新总体报告。原图保留，不覆盖。`;
}

function renderPrecheck() {
  const overall = $('#precheck-overall');
  const body = $('#precheck-body');
  const adopt = $('#opt-adopt');
  const redraw = document.querySelector('#screen-optimizer [data-action="redraw"]');
  const phase = generationPhase();
  const candidate = selectedCandidate();
  const adoption = currentAdoption();

  if (redraw) redraw.disabled = phase === 'generating' || phase === 'prechecking' || busy;

  if (phase === 'generating') {
    overall.className = 'status-pill is-live';
    overall.innerHTML = '<i></i>生成中';
    body.innerHTML = `<div class="precheck-summary"><span class="scan-spinner"></span><div><b>正在生成 ${currentGeneration()?.requestedCount || state.options.batchSize} 张候选图</b><span>Seedream 单次只生成 1 张，后台并行调用；可部分成功</span></div></div>
      <div class="precheck-item"><span class="precheck-check">${icon('minus')}</span><div><b>等待候选图返回</b><p>返回后将自动按抽卡标准预检。</p></div></div>`;
    $('#adopt-note').textContent = '候选图返回后会自动预检。预检仅为建议，采用前需你确认。';
    adopt.disabled = true;
    adopt.innerHTML = `${icon('check')}采用为当前镜头`;
    adopt.dataset.realAction = 'adopt';
    return;
  }

  if (phase === 'prechecking') {
    overall.className = 'status-pill is-live';
    overall.innerHTML = '<i></i>预检中';
    body.innerHTML = `<div class="precheck-summary"><span class="scan-spinner"></span><div><b>正在核对 ${currentCandidates().length} 张候选图</b><span>按抽卡标准逐项输出结论与证据</span></div></div>
      ${(state.suggestion?.cardDrawPlan?.selectionCriteria || []).map((name) => `<div class="precheck-item"><span class="precheck-check">${icon('minus')}</span><div><b>${escapeHtml(name)}</b><p>等待预检返回…</p></div></div>`).join('')}`;
    $('#adopt-note').textContent = '正在预检；预检完成前不能采用。';
    adopt.disabled = true;
    adopt.innerHTML = `${icon('check')}采用为当前镜头`;
    adopt.dataset.realAction = 'adopt';
    return;
  }

  if (!candidate) {
    overall.className = 'status-pill is-idle';
    overall.innerHTML = '<i></i>尚未预检';
    const criteria = (state.suggestion?.cardDrawPlan?.selectionCriteria || []);
    body.innerHTML = `<div class="precheck-summary"><div><b>生成候选图后自动预检</b><span>预检仅作为采用建议，不会自动替换镜头。</span></div></div>
      ${criteria.map((name) => `<div class="precheck-item"><span class="precheck-check">${icon('minus')}</span><div><b>${escapeHtml(name)}</b><p>等待生成候选图。</p></div></div>`).join('')}`;
  } else {
    const precheck = candidate.precheck || {};
    const recommended = currentGeneration()?.recommendedCandidateId === candidate.id;
    const value = precheck.overall || candidate.state || 'unknown';
    const meta = {
      pass: recommended
        ? ['is-ok', '建议采用', '预检通过，可作为首选候选']
        : ['is-ok', '预检通过', '满足关键标准，可对比后采用'],
      partial: ['is-warn', '部分符合', '存在无法判断项，需人工确认'],
      fail: ['is-failed', '不建议', '未满足关键挑选标准'],
      unknown: ['is-neutral', '预检未完成', '预检信息不足，请人工核对'],
    }[value] || ['is-neutral', '预检未完成', '预检信息不足，请人工核对'];
    overall.className = `status-pill ${meta[0]}`;
    overall.innerHTML = `<i></i>${meta[1]}`;
    const tone =
      value === 'pass'
        ? { border: 'rgba(91,224,176,.16)', bg: 'rgba(91,224,176,.035)', color: 'var(--green)', icon: 'check' }
        : value === 'fail'
          ? { border: 'rgba(255,92,114,.16)', bg: 'rgba(255,92,114,.035)', color: 'var(--red)', icon: 'alert' }
          : { border: 'rgba(244,187,103,.16)', bg: 'rgba(244,187,103,.035)', color: 'var(--amber)', icon: 'warn' };
    body.innerHTML = `
      <div class="precheck-summary" style="border-color:${tone.border};background:${tone.bg}">
        <span class="status-icon is-${value === 'pass' ? 'ok' : value === 'fail' ? 'alert' : 'warn'}">${icon(tone.icon === 'warn' ? 'alert' : tone.icon)}</span>
        <div><b style="color:${tone.color}">${escapeHtml(meta[2])}</b><span>${escapeHtml(candidate.candidateCode)} · ${recommended ? '推荐候选' : '仅作采用建议'}</span></div>
      </div>
      ${criteriaFor(candidate)
        .map((item) => {
          const cls = item.passed === true ? 'is-ok' : item.passed === false ? 'is-bad' : 'is-warn';
          return `<div class="precheck-item">
            <span class="precheck-check ${cls}">${icon(item.passed === true ? 'check' : item.passed === false ? 'close' : 'minus')}</span>
            <div><b>${escapeHtml(item.name)}</b><p>${escapeHtml(item.evidence || '无法判断。')}</p></div>
          </div>`;
        })
        .join('')}`;
  }

  $('#adopt-note').textContent = adoptNote(adoption, candidate);
  adopt.dataset.realAction = adoption
    ? adoption.recheckStatus === 'failed'
      ? 'retry'
      : 'view'
    : 'adopt';
  if (adoption) {
    adopt.disabled = false;
    adopt.innerHTML =
      adoption.recheckStatus === 'failed'
        ? `${icon('refresh')}重试复检`
        : `${icon('check')}查看更新后的报告`;
  } else {
    adopt.disabled = phase !== 'complete' || !candidate || busy;
    adopt.innerHTML = `${icon('check')}采用为当前镜头`;
  }
}

function durationText(gen) {
  if (!gen?.startedAt || !gen?.finishedAt) return '';
  const start = Date.parse(gen.startedAt);
  const end = Date.parse(gen.finishedAt);
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return '';
  return `${Math.max(1, Math.round((end - start) / 1000))} 秒`;
}

function renderLog() {
  const gen = currentGeneration();
  const adoption = currentAdoption();
  const phase = generationPhase();
  const candidates = currentCandidates();
  const counts = {
    pass: candidates.filter((item) => item.state === 'pass').length,
    partial: candidates.filter((item) => item.state === 'partial').length,
    fail: candidates.filter((item) => item.state === 'fail').length,
    unknown: candidates.filter((item) => item.state === 'unknown').length,
  };
  $('#gen-log-meta').textContent = gen
    ? `${gen.id} · ${currentShotCode()} · 本地记录`
    : `${currentShotCode()} · 尚未生成`;
  const precheckValue =
    phase === 'prechecking'
      ? '进行中…'
      : phase === 'generating'
        ? '等待中'
        : gen?.precheckStatus === 'failed'
          ? '预检未完成'
          : `${counts.pass} 通过 · ${counts.partial} 部分 · ${counts.fail} 不建议 · ${counts.unknown} 无结论`;
  const recheckValue = adoption
    ? {
        consistent: `${currentShotCode()} · 问题关闭`,
        inconsistent: `${currentShotCode()} · 仍不一致`,
        unknown: `${currentShotCode()} · 无法判断`,
        failed: `${currentShotCode()} · 复检失败`,
        running: `${currentShotCode()} · 复检中`,
      }[adoption.recheckStatus] || `${currentShotCode()} · 已采用`
    : '未开始';
  const steps = [
    {
      label: '修正提示词',
      value: state.suggestion ? '已锁定期望值' : '待生成',
      note: state.suggestion?.source === 'ai' ? '模型建议' : '本地规则建议',
      state: state.suggestion ? 'done' : '',
    },
    {
      label: '生成候选',
      value:
        phase === 'generating'
          ? '生成中…'
          : gen
            ? `${gen.succeededCount} / ${gen.requestedCount} 张${durationText(gen) ? ` · ${durationText(gen)}` : ''}`
            : '未开始',
      note: '单次 1 张并行',
      state: phase === 'generating' ? 'active' : gen ? 'done' : '',
    },
    {
      label: '自动预检',
      value: precheckValue,
      note: gen?.precheckMode === 'per_candidate' ? '逐张降级预检' : '按挑选标准逐项核对',
      state:
        phase === 'prechecking'
          ? 'active'
          : gen?.precheckStatus === 'completed' || gen?.precheckStatus === 'failed'
            ? 'done'
            : '',
    },
    {
      label: '用户采用',
      value: adoption
        ? `${candidates.find((item) => item.id === adoption.candidateId)?.candidateCode || '候选'} · 已采用`
        : '待确认',
      note: adoption
        ? adoption.overriddenPrecheck
          ? '已记录推翻预检结果'
          : '原图保留'
        : '预检不自动采用',
      state: adoption ? 'done' : candidates.length ? 'active' : '',
    },
    {
      label: '单镜头复检',
      value: recheckValue,
      note: adoption ? '仅复检该镜头' : '采用后触发',
      state: adoption?.recheckStatus === 'consistent' ? 'done' : adoption ? 'active' : '',
    },
  ];
  $('#gen-log-track').innerHTML = steps
    .map(
      (step) => `<div class="log-step ${step.state}">
        <span>${step.label}</span><b>${escapeHtml(String(step.value))}</b><small>${escapeHtml(step.note)}</small>
      </div>`
    )
    .join('');
}

/* 真实数据返回前盖住原型演示内容，避免刷新/flash 时被误认为真实结果 */
function renderLoading() {
  const setText = (selector, text) => {
    const el = $(selector);
    if (el) el.textContent = text;
  };
  setText('#opt-title', '正在载入优化数据…');
  setText('#opt-subtitle', '正在读取本镜头的真实问题、建议与候选图');
  setText('#opt-compare-label', '载入中…');
  setText('#opt-cardplan', '载入中…');
  const issue = $('#opt-issue-context');
  if (issue) issue.innerHTML = '';
  const prompt = $('#opt-prompt');
  if (prompt) prompt.value = '';
  const negative = $('#opt-negative');
  if (negative) negative.value = '';
  const keypoints = $('#opt-keypoints');
  if (keypoints) keypoints.innerHTML = '<p>载入中…</p>';
  const tabs = $('#opt-shot-switch');
  if (tabs) tabs.innerHTML = '';
  const original = $('#opt-original-img');
  if (original) original.style.visibility = 'hidden';
  ['#opt-after-pane', '#opt-handle', '#opt-range'].forEach((selector) => {
    const el = $(selector);
    if (el) el.hidden = true;
  });
  const candidates = $('#opt-candidates');
  if (candidates) {
    candidates.innerHTML = '<div class="empty-state small" style="grid-column:1/-1"><h4>正在载入真实候选与预检结果…</h4></div>';
  }
  const overall = $('#precheck-overall');
  if (overall) {
    overall.className = 'status-pill is-idle';
    overall.innerHTML = '<i></i>载入中';
  }
  const body = $('#precheck-body');
  if (body) body.innerHTML = '';
}

function render() {
  if (!state) return;
  renderHeader();
  renderTabs();
  renderPrompt();
  renderCompare();
  renderCandidates();
  renderPrecheck();
  renderLog();
}

async function loadOptimizer(shotId) {
  stopPolling();
  busy = false;
  const data = await tasksApi.shotOptimizer(taskId, shotId);
  if (!data.suggestion && suggestionCache.has(shotId)) {
    data.suggestion = suggestionCache.get(shotId);
  } else if (data.suggestion) {
    suggestionCache.set(shotId, data.suggestion);
  }
  state = data;
  currentShotId = shotId;
  selectedCandidateId = null;
  rememberContext();
  render();
}

export async function showRealOptimizer(taskIdArg, shotId, options = {}) {
  taskId = taskIdArg;
  active = true;
  currentShotId = shotId;
  selectedCandidateId = null;
  rememberContext();
  // 先走原型 showScreen（会渲染一次演示数据），随后立即用加载态盖住
  if (window.__CCS?.showScreen) window.__CCS.showScreen('optimizer');
  renderLoading();
  try {
    await loadOptimizer(shotId);
    if (!options.silent) {
      toast('已载入本镜头问题与合并修正建议');
    }
  } catch (error) {
    toast(error.message || '优化页加载失败');
    active = false;
    clearContext();
    try {
      const { showRealReport } = await import('./results.js');
      await showRealReport(taskIdArg);
    } catch {
      window.__CCS?.showScreen('history');
      const { refreshHistory } = await import('./history.js');
      await refreshHistory().catch(() => {});
    }
  } finally {
    document.documentElement.classList.remove('ccs-restoring');
  }
}

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
  pollGenerationId = null;
}

function deactivate() {
  active = false;
  stopPolling();
  busy = false;
}

function pollGeneration(generationId) {
  if (!active) return;
  stopPolling();
  pollGenerationId = generationId;
  const tick = async () => {
    if (!active || pollGenerationId !== generationId) return;
    try {
      const data = await tasksApi.generation(taskId, generationId);
      if (!active || pollGenerationId !== generationId) return;
      state.generation = data.generation;
      state.adoption = data.adoption;
      if (data.adoption) {
        state.shotAdoptions = {
          ...(state.shotAdoptions || {}),
          [currentShotCode()]: data.adoption,
        };
      }
      render();
      const gen = data.generation;
      const terminal =
        !['pending', 'generating', 'prechecking'].includes(gen.status)
        && gen.precheckStatus !== 'running';
      if (terminal) {
        pollTimer = null;
        pollGenerationId = null;
        busy = false;
        if (gen.candidates.length) {
          const recommended = gen.candidates.find((item) => item.id === gen.recommendedCandidateId);
          toast(
            recommended
              ? `预检完成：${recommended.candidateCode} 建议采用`
              : '预检完成：本批无通过候选，可重抽或人工核对'
          );
        } else {
          toast(gen.errorMessage || '生成失败，可重试');
        }
        return;
      }
      pollTimer = setTimeout(tick, 650);
    } catch (error) {
      pollTimer = null;
      pollGenerationId = null;
      busy = false;
      toast(error.message || '生成状态查询失败');
    }
  };
  pollTimer = setTimeout(tick, 350);
}

async function startGeneration() {
  if (busy) return;
  const phase = generationPhase();
  if (phase === 'generating' || phase === 'prechecking') return;
  const consented = await ensurePrivacyAcknowledged('generation');
  if (!consented) return;
  busy = true;
  render();
  try {
    const count = state.suggestion?.cardDrawPlan?.batchSize || state.options.batchSize;
    const generation = await tasksApi.generateShot(taskId, currentShotId, count);
    state.generation = generation;
    state.adoption = null;
    selectedCandidateId = null;
    const shotCode = currentShotCode();
    if (state.shotAdoptions) delete state.shotAdoptions[shotCode];
    busy = false;
    render();
    toast(`正在为 ${shotCode} 生成 ${count} 张候选图`);
    pollGeneration(generation.id);
  } catch (error) {
    busy = false;
    render();
    toast(error.message || '生成启动失败');
  }
}

async function adoptSelected() {
  const candidate = selectedCandidate();
  const gen = currentGeneration();
  if (!candidate || !gen || busy) return;
  busy = true;
  const btn = $('#opt-adopt');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="scan-spinner" style="width:14px;height:14px"></span>正在复检 ${currentShotCode()}…`;
  }
  try {
    const data = await tasksApi.adopt(taskId, gen.id, candidate.id);
    state.generation = data.generation;
    state.adoption = data.adoption;
    if (data.adoption) {
      state.shotAdoptions = {
        ...(state.shotAdoptions || {}),
        [currentShotCode()]: data.adoption,
      };
    }
    busy = false;
    render();
    const status = data.adoption?.recheckStatus;
    if (status === 'consistent') {
      toast(`${candidate.candidateCode} 已采用，${currentShotCode()} 复检完成，问题关闭`);
    } else if (status === 'failed') {
      toast('候选已记录，但复检失败，问题保持开启；可重试复检');
    } else {
      toast(`${candidate.candidateCode} 已采用并复检：${status === 'inconsistent' ? '仍然不一致' : '无法判断'}`);
    }
  } catch (error) {
    busy = false;
    render();
    toast(error.message || '采用失败');
  }
}

async function retryRecheck() {
  if (busy) return;
  const shotId = state.issue.shotId;
  busy = true;
  render();
  try {
    const previousSuggestion = state.suggestion;
    const data = await tasksApi.recheck(taskId, shotId);
    if (!data.suggestion && previousSuggestion) data.suggestion = previousSuggestion;
    state = data;
    if (data.suggestion) suggestionCache.set(currentShotId, data.suggestion);
    busy = false;
    render();
    toast(
      data.adoption?.recheckStatus === 'consistent'
        ? '复检完成，问题已关闭'
        : '复检完成，问题仍未关闭，可继续重抽'
    );
  } catch (error) {
    busy = false;
    render();
    toast(error.message || '复检重试失败');
  }
}

async function showUpdatedReport() {
  stopPolling();
  active = false;
  const { showRealReport } = await import('./results.js');
  await showRealReport(taskId);
}

async function handleAdoptClick() {
  const adoption = currentAdoption();
  if (adoption) {
    if (adoption.recheckStatus === 'failed') await retryRecheck();
    else await showUpdatedReport();
    return;
  }
  await adoptSelected();
}

/* 刷新恢复顺序：URL 参数 → 本地上下文 → 最近一个含问题的真实任务。
   最后一步保证修复前就打开的页面也能立即回到真实数据，而不是停在演示内容。 */
async function restoreOptimizerOnBoot() {
  let saved = null;
  try {
    const params = new URLSearchParams(window.location.search);
    const task = params.get('task');
    const shot = params.get('shot');
    if (task && shot) saved = { taskId: task, shotId: shot };
  } catch {
    /* ignore */
  }
  saved = saved || readContext();
  if (saved) {
    await showRealOptimizer(saved.taskId, saved.shotId, {
      silent: true,
      restoring: true,
    });
    return;
  }

  try {
    const listed = await tasksApi.list({ limit: 10 });
    const tasks = (listed.items || []).filter(
      (task) =>
        ['completed', 'partial'].includes(task.status)
        && Number(task.issueCount) > 0
    );
    for (const task of tasks.slice(0, 3)) {
      try {
        const data = await tasksApi.report(task.id);
        const issue = (data.issues || [])[0];
        if (issue?.shotId) {
          await showRealOptimizer(task.id, issue.shotId, {
            silent: true,
            restoring: true,
          });
          return;
        }
      } catch {
        /* 尝试下一个任务 */
      }
    }
  } catch {
    /* 保持原型演示 */
  }
  document.documentElement.classList.remove('ccs-restoring');
}

export function initOptimizerIntegration() {
  document.addEventListener(
    'click',
    async (event) => {
      if (!active) return;
      const nav = event.target.closest('[data-nav]');
      if (nav) {
        if (nav.dataset.nav === 'results') {
          event.preventDefault();
          event.stopPropagation();
          await showUpdatedReport();
        } else if (nav.dataset.nav !== 'optimizer') {
          deactivate();
        }
        return;
      }

      const tab = event.target.closest('[data-real-shot-tab]');
      if (tab) {
        event.preventDefault();
        event.stopPropagation();
        if (busy) return;
        try {
          await loadOptimizer(tab.dataset.realShotTab);
        } catch (error) {
          toast(error.message || '切换镜头失败');
        }
        return;
      }

      const candidate = event.target.closest('[data-real-candidate]');
      if (candidate) {
        event.preventDefault();
        event.stopPropagation();
        selectedCandidateId = candidate.dataset.realCandidate;
        render();
        return;
      }

      if (event.target.closest('#opt-generate')) {
        event.preventDefault();
        event.stopPropagation();
        await startGeneration();
        return;
      }

      if (event.target.closest('[data-action="redraw"]')) {
        event.preventDefault();
        event.stopPropagation();
        await startGeneration();
        return;
      }

      if (event.target.closest('#opt-adopt')) {
        event.preventDefault();
        event.stopPropagation();
        await handleAdoptClick();
      }
    },
    true
  );

  // 进入原型演示优化页时清掉真实上下文，避免刷新后把演示当成真实数据恢复
  document.addEventListener(
    'click',
    (event) => {
      if (active) return;
      if (
        event.target.closest('[data-optimize-issue], [data-action="open-optimizer"]')
      ) {
        clearContext();
      }
    },
    true
  );

  // 刷新时若 URL 仍在优化页，恢复真实数据，而不是停在原型演示内容
  if (window.location.hash.replace('#', '') === 'optimizer') {
    restoreOptimizerOnBoot();
  }

  window.addEventListener('hashchange', () => {
    const name = window.location.hash.replace('#', '');
    if (active && name !== 'optimizer') deactivate();
  });
}
