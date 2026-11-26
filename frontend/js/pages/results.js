/* 检测结果页：把后端结构化报告渲染进定稿 DOM。
   演示模式仍由原型 app.js 的本地模拟负责；本模块只在用户点击真实任务行时接管。 */

import { tasksApi } from '../core/api.js';
import { escapeHtml, toast } from '../core/ui.js';
import { formatWhen } from '../core/task-view.js';
import { showRealOptimizer } from './optimizer.js';

let report = null;
let active = false;
let selectedShot = null;
let selectedIssue = null;
let galleryFilter = 'all';
/* 原型演示页的副标题，回到演示结果时恢复，避免沿用上一份真实报告的名称。 */
const DEMO_SUBTITLE =
  document.querySelector('#screen-results')?.dataset.subtitle || '阿岚 · 第一幕 · 3 个镜头';
const REPORT_CONTEXT_KEY = 'char_cons_active_report';

function rememberReportContext(taskId) {
  try {
    localStorage.setItem(REPORT_CONTEXT_KEY, taskId);
  } catch {
    /* ignore */
  }
  try {
    const url = new URL(window.location.href);
    url.searchParams.set('report', taskId);
    history.replaceState(null, '', url);
  } catch {
    /* ignore */
  }
}

function readReportContext() {
  try {
    return localStorage.getItem(REPORT_CONTEXT_KEY) || null;
  } catch {
    return null;
  }
}

function clearReportContext() {
  try {
    localStorage.removeItem(REPORT_CONTEXT_KEY);
  } catch {
    /* ignore */
  }
  try {
    const url = new URL(window.location.href);
    url.searchParams.delete('report');
    history.replaceState(null, '', url);
  } catch {
    /* ignore */
  }
}

const VERDICT_META = {
  consistent: { status: 'ok', icon: 'check', label: '一致' },
  inconsistent: { status: 'alert', icon: 'alert', label: '不一致' },
  unknown: { status: 'muted', icon: 'help', label: '无法判断' },
  observed_only: { status: 'observed', icon: 'minus', label: '仅记录' },
  waived: { status: 'info', icon: 'info', label: '剧本豁免' },
  failed: { status: 'muted', icon: 'help', label: '观察失败' },
};

const SEVERITY = { high: '高', medium: '中', low: '低' };
const CONFIDENCE = { high: '高', medium: '中', low: '低' };
const TYPE_LABEL = { profile_violation: '违反设定', cross_shot_mismatch: '镜头间不一致' };
const STATUS_LABEL = { completed: '已完成', partial: '部分完成', failed: '分析失败' };

function icon(name) {
  return `<svg class="icon"><use href="#i-${name}"/></svg>`;
}

function pill(text, kind) {
  return `<span class="status-pill is-${kind}"><i></i>${escapeHtml(text)}</span>`;
}

function shotCodes() {
  return (report?.gallery || []).map((item) => item.shotCode);
}

function issueForShot(shotCode) {
  return (report?.issues || []).filter((item) => item.shotCode === shotCode);
}

function unknownForShot(shotCode) {
  return (report?.unknownItems || []).filter((item) => item.shotCode === shotCode);
}

function renderHeader() {
  const screen = document.querySelector('#screen-results');
  if (!screen) return;
  const name = report.task.name || report.task.characterName || '检测报告';
  const subtitle = `${name} · ${report.stats.totalShots} 个镜头`;
  screen.dataset.subtitle = subtitle;
  // 顶栏副标题不能停留在原型写死的“阿岚 · 第一幕 · 3 个镜头”，
  // 要跟随当前报告的任务名与真实镜头数。
  if (screen.classList.contains('is-active')) {
    const pageSubtitle = document.querySelector('#page-subtitle');
    if (pageSubtitle) pageSubtitle.textContent = subtitle;
  }
  const title = screen.querySelector('.report-head h2');
  if (title) title.textContent = name;

  const status = report.task.status;
  const pillKind = status === 'partial' ? 'partial' : status === 'failed' ? 'failed' : 'ok';
  const badge = report.script?.ruleBadge || '严格比对 · 无豁免';
  const meta = screen.querySelector('.report-meta');
  if (meta) {
    meta.innerHTML = `
      <span>${report.stats.totalShots} 个镜头</span>
      <span>检查于 ${escapeHtml(formatWhen(report.task.completedAt || report.task.createdAt))}</span>
      <span>剧本：${escapeHtml(badge)}</span>
      <span class="status-pill is-${pillKind}"><i></i>${escapeHtml(STATUS_LABEL[status] || '已完成')}</span>`;
  }
  // 顶栏状态胶囊同样跟随报告状态，避免“部分完成”的报告仍显示为已完成。
  const topPill = document.querySelector('#task-status-pill');
  if (topPill) {
    topPill.className = `status-pill is-${pillKind}`;
    topPill.innerHTML = `<i></i>${escapeHtml(STATUS_LABEL[status] || '已完成')}`;
  }
}

function renderSummary() {
  const stats = report.stats;
  const set = (id, value) => {
    const el = document.querySelector(id);
    if (el) el.textContent = String(value);
  };
  set('#sum-consistent', stats.consistent);
  set('#sum-issues', stats.confirmedIssues);
  set('#sum-suspected', stats.suspectedIssues);
  set('#sum-unknown', stats.unknown);
  set('#sum-waiver', stats.waived);

  const summary = document.querySelector('#summary-text');
  if (summary) summary.textContent = report.summary;
  const iconWrap = document.querySelector('.summary-sentence .status-icon');
  if (iconWrap) {
    const hasIssue = stats.confirmedIssues > 0;
    iconWrap.className = `status-icon ${hasIssue ? 'is-alert' : 'is-ok'}`;
    iconWrap.innerHTML = icon(hasIssue ? 'alert' : 'check');
  }
  const tab = (name) => document.querySelector(`[data-tab="${name}"] span`);
  set('#tab-count-matrix', stats.totalUnits);
  set('#tab-count-issues', stats.confirmedIssues);
  set('#tab-count-suspected', stats.suspectedIssues);
  set('#tab-count-unknown', stats.unknown);
  const waiverCount = tab('waiver');
  if (waiverCount) waiverCount.textContent = String(stats.waived);
}

function galleryStatus(item) {
  if (item.analysisStatus === 'failed') return 'failed';
  return item.conclusionStatus || 'ok';
}

function renderGallery() {
  const gallery = document.querySelector('#results-gallery');
  if (!gallery) return;
  gallery.innerHTML = report.gallery.map((item) => {
    const status = galleryStatus(item);
    const flag = status === 'issue' ? 'is-alert' : status === 'unknown' ? 'is-muted' : status === 'failed' ? 'is-failed' : 'is-ok';
    const flagIcon = status === 'issue' ? 'alert' : status === 'unknown' ? 'help' : status === 'failed' ? 'alert' : 'check';
    const copy = status === 'issue'
      ? `${item.issueCount} 个问题`
      : status === 'unknown'
        ? `${item.unknownCount} 项待判断`
        : status === 'failed'
          ? '观察失败'
          : '全部一致';
    const version = item.isAdopted
      ? ` · 当前版本${item.adoptedCandidateCode ? ` ${item.adoptedCandidateCode}` : ''}`
      : '';
    return `<button class="gallery-card ${status === 'issue' ? 'is-issue' : ''} ${selectedShot === item.shotCode ? 'is-selected' : ''}"
              data-real-gallery="${escapeHtml(item.shotCode)}"
              title="${escapeHtml(item.versionLabel || (item.isAdopted ? '当前版本' : '原图'))}">
      <span class="gallery-img"><img src="${escapeHtml(item.thumbUrl)}" alt="${escapeHtml(item.shotCode)} ${item.isAdopted ? '当前版本' : '原图'}">
        <span class="shot-index">${escapeHtml(item.shotCode)}</span>
        <span class="gallery-flag ${flag}">${icon(flagIcon)}</span>
      </span>
      <span class="gallery-copy"><b>${escapeHtml(item.shotCode)}</b><span>${escapeHtml(copy + version)}</span></span>
    </button>`;
  }).join('');
  document.querySelectorAll('#screen-results [data-status-filter]').forEach((chip) => {
    chip.classList.toggle('is-active', chip.dataset.statusFilter === galleryFilter);
  });
  applyGalleryFilter();
}

function applyGalleryFilter() {
  document.querySelectorAll('#results-gallery [data-real-gallery]').forEach((card) => {
    const item = report.gallery.find((entry) => entry.shotCode === card.dataset.realGallery);
    const status = item ? galleryStatus(item) : 'ok';
    card.hidden = galleryFilter !== 'all' && status !== galleryFilter;
  });
}

function cellMarkup(cell) {
  const meta = VERDICT_META[cell.verdict] || VERDICT_META.muted || { status: 'muted', icon: 'info', label: '—' };
  const focused = cell.issueId && cell.issueId === selectedIssue;
  let value = cell.observed;
  if (cell.verdict === 'unknown') value = value || '—';
  if (cell.verdict === 'failed' || cell.verdict === null) value = '—';
  const note = cell.issueId || cell.unknownId || cell.waiverId || '';
  return `<td class="matrix-cell">
    <button class="cell-btn ${focused ? 'is-focused' : ''}" data-real-cell data-shot="${escapeHtml(cell.shotCode)}"
      data-issue="${escapeHtml(cell.issueId || '')}" title="${escapeHtml(cell.reason || '')}">
      <span class="status-icon is-${meta.status}">${icon(meta.icon)}</span>
      <span class="cell-copy is-${meta.status}"><b>${escapeHtml(value ?? '—')}</b><span>${escapeHtml(meta.label)}</span></span>
    </button>
    ${note ? `<span class="mono matrix-note">${escapeHtml(note)}</span>` : ''}
  </td>`;
}

function renderMatrix() {
  const thead = document.querySelector('#screen-results .matrix-table thead tr');
  if (thead) {
    thead.innerHTML = `<th>要素</th><th>设定值</th>${shotCodes().map((code) => `<th>${escapeHtml(code)}</th>`).join('')}`;
  }
  const body = document.querySelector('#matrix-body');
  if (!body) return;
  body.innerHTML = report.matrix.map((row) => `
    <tr>
      <td><span class="matrix-attr"><b>${escapeHtml(row.attributeName)}</b><span>${escapeHtml(row.attributeId)}</span></span></td>
      <td class="matrix-expect">${escapeHtml(row.expected || '设定未定义')}</td>
      ${row.cells.map(cellMarkup).join('')}
    </tr>`).join('');
}

function issueCard(issue, suspected = false) {
  const sev = SEVERITY[issue.severity] || '中';
  const conf = CONFIDENCE[issue.confidence] || '中';
  const type = TYPE_LABEL[issue.type] || issue.type || '违反设定';
  const cls = selectedIssue === issue.id ? 'is-selected' : '';
  return `
    <article class="issue-card ${cls}" data-real-${suspected ? 'suspected' : 'issue'}="${escapeHtml(issue.id)}" role="button" tabindex="0">
      <span class="issue-sev">
        <span class="status-icon ${suspected || issue.severity !== 'high' ? 'is-warn' : 'is-alert'}">${icon('alert')}</span>
        <small>${suspected ? 'SUS' : sev === '高' ? 'HIGH' : 'MED'}</small>
      </span>
      <span class="issue-copy">
        <span class="issue-top"><span class="issue-id">${escapeHtml(issue.id)}</span><span class="issue-shot">${escapeHtml(issue.shotCode)}</span><h4>${escapeHtml(issue.attributeName)}</h4></span>
        <span class="issue-values"><span class="expected">${escapeHtml(issue.expected || '—')}</span>${icon('arrow-right')}<span class="actual">${escapeHtml(issue.observed || '—')}</span></span>
        <span class="issue-evidence">证据：${escapeHtml(issue.evidence || issue.reason || '—')}</span>
      </span>
      <span class="issue-side">
        <span class="issue-meta">严重度 ${sev} · 置信度 ${conf}</span>
        ${suspected
          ? `<span class="issue-meta">疑似 · 待人工复核</span>`
          : `<button class="btn btn-ghost btn-sm" data-real-optimize="${escapeHtml(issue.id)}">优化此镜头${icon('arrow-right')}</button>`}
      </span>
    </article>`;
}

function renderIssues() {
  const list = document.querySelector('#issue-list');
  if (!list) return;
  if (!report.issues.length) {
    list.innerHTML = `<div class="empty-state small"><span class="empty-icon">${icon('check')}</span>
      <h4>没有确定问题</h4><p>所有可判断的「镜头 × 要素」都与角色设定一致。无法判断项仍单独展示，不计入一致结论。</p></div>`;
    return;
  }
  list.innerHTML = report.issues.map((issue) => issueCard(issue)).join('');
}

function emptyState(title, copy, iconName = 'help') {
  return `<div class="empty-state small"><span class="empty-icon">${icon(iconName)}</span><h4>${escapeHtml(title)}</h4><p>${escapeHtml(copy)}</p></div>`;
}

function renderSuspected() {
  const panel = document.querySelector('#tab-suspected');
  if (!panel) return;
  const intro = `<div class="tab-intro"><div><span class="section-kicker">SUSPECTED ISSUES</span><h3>疑似问题</h3></div><p>低置信度差异单独展示，不计入确定问题，等待人工复核。</p></div>`;
  panel.innerHTML = intro + (report.suspectedIssues.length
    ? `<div class="issue-list">${report.suspectedIssues.map((item) => issueCard(item, true)).join('')}</div>`
    : emptyState('本次没有疑似问题', '所有差异都有足够证据支撑。低置信度观察会进入此区，不会同时计入确定问题。'));
}

function renderUnknowns() {
  const list = document.querySelector('#unknown-list');
  if (!list) return;
  list.innerHTML = report.unknownItems.length
    ? report.unknownItems.map((item) => `
      <div class="unknown-item">
        <span class="status-icon is-muted">${icon('help')}</span>
        <span class="unknown-copy"><b>${escapeHtml(item.attributeName)} · ${escapeHtml(item.shotCode)}</b><p>原因：${escapeHtml(item.reason)}</p></span>
        <span class="mono">${escapeHtml(item.id)}</span>
      </div>`).join('')
    : emptyState('没有无法判断项', '所有要素在画面中均可见并有充分证据。', 'check');
}

function renderWaivers() {
  const panel = document.querySelector('#tab-waiver');
  if (!panel) return;
  const intro = `<div class="tab-intro"><div><span class="section-kicker">SCRIPT WAIVERS</span><h3>剧本豁免</h3></div><p>只有剧本明确允许、且能定位到具体镜头与要素的变化才会豁免。</p></div>`;
  panel.innerHTML = intro + (report.waivers.length
    ? `<div class="unknown-list">${report.waivers.map((item) => `
        <div class="unknown-item">
          <span class="status-icon is-info">${icon('info')}</span>
          <span class="unknown-copy"><b>${escapeHtml(item.attributeName)} · ${escapeHtml(item.shotCode)}</b><p>依据：${escapeHtml(item.scriptEvidence)}</p></span>
          <span class="mono">${escapeHtml(item.id)}</span>
        </div>`).join('')}</div>`
    : emptyState('本次没有剧本豁免', `剧本说明为「${report.task.scriptRaw}」，所有外观变化均按设定严格比对。`, 'info'));
}

function renderSuggestions() {
  const grid = document.querySelector('#suggestion-grid');
  if (!grid) return;
  if (!report.issues.length) {
    grid.innerHTML = emptyState(
      '当前没有待修正问题',
      '问题关闭后，对应的修正提示词与抽卡方案会从活动建议中移除。',
      'check'
    );
    return;
  }
  const suggestions = report.suggestions || [];
  if (!suggestions.length) {
    grid.innerHTML = emptyState(
      '修正建议暂不可用',
      '可重新分析任务，或在问题卡片上点击「优化此镜头」重试建议生成。',
      'info'
    );
    return;
  }
  grid.innerHTML = suggestions
    .map((item) => {
      const ready = item.status === 'ready';
      const plan = item.cardDrawPlan || {};
      const refs = (plan.referenceShots || item.referenceShots || []).join(' / ') || '无合格参考';
      const batch = plan.batchSize || 4;
      const source = item.source === 'ai' ? '模型建议' : '本地规则建议';
      return `<article class="suggestion-card">
        <div class="suggestion-top">
          <div><span class="mono">${escapeHtml(item.issueId)} · ${escapeHtml(item.shotCode)}</span><h4>${escapeHtml(suggestionTitle(item))}</h4></div>
          ${ready ? pill('可直接使用', 'ok') : pill('建议生成失败', 'warn')}
        </div>
        <div class="suggestion-prompt">${escapeHtml(ready ? item.revisedPrompt : (item.errorMessage || '建议生成失败，可进入优化页重试。'))}</div>
        <div class="suggestion-foot">
          <span>参考 ${escapeHtml(refs)} · 每批 ${escapeHtml(String(batch))} 张 · ${escapeHtml(source)}</span>
          <span class="suggestion-actions">
            <button class="btn btn-ghost btn-sm" data-real-copy-suggestion="${escapeHtml(item.issueId)}">${icon('copy')}复制</button>
            <button class="btn btn-primary btn-sm" data-real-optimize="${escapeHtml(item.issueId)}">优化</button>
          </span>
        </div>
      </article>`;
    })
    .join('');
}

function suggestionTitle(item) {
  const issue = (report.issues || []).find((entry) => entry.id === item.issueId);
  return issue ? `修正 ${issue.attributeName}` : '修正提示词';
}

async function copySuggestion(issueId) {
  const item = (report.suggestions || []).find((entry) => entry.issueId === issueId);
  if (!item || !item.revisedPrompt) {
    toast('该建议暂未生成，请进入优化页重试');
    return;
  }
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(item.revisedPrompt);
      toast('修正提示词已复制');
    } else {
      toast('复制失败，请进入优化页手动复制');
    }
  } catch {
    toast('复制失败，请进入优化页手动复制');
  }
}

function renderInspector() {
  const container = document.querySelector('#results-inspector');
  if (!container) return;
  if (selectedIssue) {
    const issue = [...report.issues, ...report.suspectedIssues].find((item) => item.id === selectedIssue);
    if (issue) {
      const suspected = !report.issues.some((item) => item.id === issue.id);
      const sev = SEVERITY[issue.severity] || '中';
      const conf = CONFIDENCE[issue.confidence] || '中';
      const type = TYPE_LABEL[issue.type] || (suspected ? '疑似问题' : '违反设定');
      container.innerHTML = `
        <section class="inspector-card">
          <div class="inspector-head">
            <div><span class="mono">${escapeHtml(issue.id)} · ${escapeHtml(issue.shotCode)}</span><h3>${escapeHtml(issue.attributeName)}</h3></div>
            <span class="status-icon ${suspected ? 'is-warn' : 'is-alert'}">${icon('alert')}</span>
          </div>
          <div class="inspector-pill-row">
            ${pill(`严重度 ${sev}`, suspected ? 'warn' : issue.severity === 'high' ? 'failed' : 'warn')}
            ${pill(`置信度 ${conf}`, 'ok')}
            ${pill(type, 'neutral')}
            ${suspected ? pill('疑似 · 待复核', 'warn') : ''}
          </div>
          <div class="inspector-section">
            <span class="inspector-label">EXPECTED / OBSERVED</span>
            <div class="compare-values">
              <div class="compare-value"><span>设定期望</span><b>${escapeHtml(issue.expected || '—')}</b></div>
              <div class="compare-value is-bad"><span>实际观察</span><b>${escapeHtml(issue.observed || '—')}</b></div>
            </div>
          </div>
          <div class="inspector-section">
            <span class="inspector-label">EVIDENCE</span>
            <div class="evidence-quote">“${escapeHtml(issue.evidence || issue.reason || '—')}”</div>
          </div>
          <div class="inspector-section">
            <span class="inspector-label">SCRIPT CONTEXT</span>
            <div class="waiver-trace">${escapeHtml(report.script?.ruleBadge || '严格比对 · 无豁免')}。本条未命中剧本豁免。</div>
          </div>
          <div class="inspector-actions">
            ${suspected ? '' : `<button class="btn btn-primary" data-real-optimize="${escapeHtml(issue.id)}">${icon('refresh')}优化此镜头</button>`}
            <button class="btn btn-ghost" data-real-locate="${escapeHtml(issue.shotCode)}">${icon('image')}定位到 ${escapeHtml(issue.shotCode)}</button>
          </div>
        </section>
        <div class="inspector-nav"><span>镜头状态</span><b>${escapeHtml(issue.shotCode)} · ${issueForShot(issue.shotCode).length} 个确定问题</b></div>`;
      return;
    }
  }
  const galleryItem = report.gallery.find((item) => item.shotCode === selectedShot) || report.gallery[0];
  if (!galleryItem) {
    container.innerHTML = '';
    return;
  }
  selectedShot = galleryItem.shotCode;
  const rows = report.matrix.map((row) => {
    const cell = row.cells.find((item) => item.shotCode === galleryItem.shotCode);
    const value = cell?.verdict === 'unknown' || cell?.verdict === 'failed' || !cell?.observed
      ? '无法判断'
      : cell.observed;
    return `<div class="compare-value" style="margin-bottom:4px"><span>${escapeHtml(row.attributeName)}</span><b>${escapeHtml(value)}</b></div>`;
  }).join('');
  const status = galleryStatus(galleryItem);
  const statusText = status === 'issue' ? '存在问题' : status === 'unknown' ? '存在无法判断' : status === 'failed' ? '观察失败' : '全部一致';
  container.innerHTML = `
    <section class="inspector-card">
      <div class="inspector-head">
        <div><span class="mono">${escapeHtml(galleryItem.shotCode)} · SHOT SUMMARY</span><h3>${escapeHtml(galleryItem.shotCode)} 镜头结论</h3></div>
        <span class="status-icon ${status === 'issue' ? 'is-alert' : status === 'unknown' ? 'is-muted' : status === 'failed' ? 'is-failed' : 'is-ok'}">${icon(status === 'issue' || status === 'failed' ? 'alert' : status === 'unknown' ? 'help' : 'check')}</span>
      </div>
      <div class="inspector-pill-row">${pill(statusText, status === 'issue' ? 'failed' : status === 'unknown' ? 'neutral' : status === 'failed' ? 'failed' : 'ok')}${pill(galleryItem.versionLabel || (galleryItem.isAdopted ? '当前版本' : '原图'), 'neutral')}</div>
      <div class="inspector-section">
        <span class="inspector-label">OBSERVATIONS</span>
        ${rows}
      </div>
      <div class="inspector-actions">
        <button class="btn btn-ghost" data-real-lightbox="${escapeHtml(galleryItem.shotCode)}">${icon('image')}查看大图</button>
        ${galleryItem.isAdopted ? `<button class="btn btn-ghost" data-real-lightbox-original="${escapeHtml(galleryItem.shotCode)}">${icon('image')}查看原图</button>` : ''}
      </div>
    </section>
    <div class="inspector-nav"><span>镜头状态</span><b>${escapeHtml(statusText)}</b></div>`;
}

function renderTabs() {
  const tab = window.__CCS?.STATE?.resultTab || 'matrix';
  document.querySelectorAll('#screen-results .tab').forEach((button) => {
    const activeTab = button.dataset.tab === tab;
    button.classList.toggle('is-active', activeTab);
    button.setAttribute('aria-selected', activeTab ? 'true' : 'false');
  });
  document.querySelectorAll('#screen-results .tab-panel').forEach((panel) => {
    panel.classList.toggle('is-active', panel.id === `tab-${tab}`);
  });
}

function renderAll() {
  selectedShot = selectedShot || report.gallery[0]?.shotCode || null;
  renderHeader();
  renderSummary();
  renderGallery();
  renderMatrix();
  renderIssues();
  renderSuspected();
  renderUnknowns();
  renderWaivers();
  renderSuggestions();
  renderInspector();
  renderTabs();
}

export function resetRealReport() {
  active = false;
  report = null;
  selectedIssue = null;
  clearReportContext();
  const screen = document.querySelector('#screen-results');
  if (screen) screen.dataset.subtitle = DEMO_SUBTITLE;
}

export async function showRealReport(taskIdArg, options = {}) {
  const screen = document.querySelector('#screen-results');
  if (screen) screen.style.visibility = 'hidden';
  const subtitle = document.querySelector('#page-subtitle');
  if (subtitle && window.__CCS?.STATE?.screen === 'results') {
    subtitle.textContent = '正在载入检测结果…';
  }
  try {
    const data = await tasksApi.report(taskIdArg);
    report = data;
    active = true;
    // 检测完成后不默认选中任何问题；先展示第一个镜头的摘要，由用户点击决定焦点。
    selectedShot = report.gallery[0]?.shotCode || null;
    selectedIssue = null;
    window.__CCS.STATE.resultTab = 'matrix';
    window.__CCS.STATE.selectedShot = selectedShot;
    window.__CCS.STATE.selectedIssue = null;
    // 先走原型的 showScreen（其中会调用一次演示 renderResults），再渲染真实报告，
    // 避免原型在 hashchange 时把真实结果覆盖回演示数据。
    window.__CCS.showScreen('results');
    renderAll();
    rememberReportContext(taskIdArg);
  } catch (error) {
    toast(error.message || '报告加载失败');
    active = false;
    report = null;
    clearReportContext();
    if (options.restoring) {
      window.__CCS?.showScreen('history');
      const { refreshHistory } = await import('./history.js');
      await refreshHistory().catch(() => {});
    }
  } finally {
    if (screen) screen.style.visibility = '';
    document.documentElement.classList.remove('ccs-restoring');
  }
}

/* 刷新恢复顺序：URL 的 report 参数 → 本地记录 → 最近一个已完成任务。
   这样修复前打开的页面只需刷新，也不会停在原型演示结果。 */
async function restoreReportOnBoot() {
  let taskId = null;
  try {
    taskId = new URLSearchParams(window.location.search).get('report');
  } catch {
    /* ignore */
  }
  taskId = taskId || readReportContext();
  if (taskId) {
    await showRealReport(taskId, { restoring: true });
    return;
  }
  try {
    const listed = await tasksApi.list({ limit: 10 });
    const task = (listed.items || []).find((item) =>
      ['completed', 'partial'].includes(item.status)
    );
    if (task) await showRealReport(task.id, { restoring: true });
  } catch {
    /* 保持原型演示 */
  }
  document.documentElement.classList.remove('ccs-restoring');
}

function selectShot(code) {
  selectedShot = code;
  selectedIssue = null;
  if (window.__CCS?.STATE) {
    window.__CCS.STATE.selectedShot = code;
    window.__CCS.STATE.selectedIssue = null;
  }
  renderGallery();
  renderMatrix();
  renderInspector();
}

function selectIssue(id) {
  const issue = [...report.issues, ...report.suspectedIssues].find((item) => item.id === id);
  if (!issue) return;
  selectedIssue = id;
  selectedShot = issue.shotCode;
  if (window.__CCS?.STATE) {
    window.__CCS.STATE.selectedIssue = id;
    window.__CCS.STATE.selectedShot = issue.shotCode;
  }
  renderGallery();
  renderMatrix();
  renderInspector();
}

async function exportCurrent(format) {
  try {
    const { blob, filename } = await tasksApi.exportReport(report.task.id, format);
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename || `一致性检查_${format === 'json' ? 'report.json' : 'report.md'}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
    toast(`已导出 ${format === 'json' ? 'JSON' : 'Markdown'} 报告`);
  } catch (error) {
    toast(error.message || '导出失败，请重试');
  }
}

function openLightbox(code, original = false) {
  const item = report.gallery.find((entry) => entry.shotCode === code);
  if (!item) return;
  const lightbox = document.querySelector('#lightbox');
  const img = document.querySelector('#lightbox-img');
  if (!lightbox || !img) return;
  img.src = original ? item.imageUrl : (item.currentUrl || item.imageUrl);
  img.alt = `${code} ${original ? '原图' : '当前版本'}大图`;
  document.querySelector('#lightbox-id').textContent = code;
  document.querySelector('#lightbox-name').textContent =
    `${report.task.name || ''}${original ? ' · 原图' : ' · 当前版本'}`;
  lightbox.hidden = false;
}

export function initResultsIntegration() {
  document.addEventListener('click', async (event) => {
    const demoTrigger = event.target.closest('[data-nav="results"], [data-action="load-demo"], [data-action="start-analysis"]');
    if (demoTrigger && !event.target.closest('[data-task-id]')) {
      resetRealReport();
    }
    if (!active) return;

    const tab = event.target.closest('#screen-results .tab');
    if (tab) {
      event.preventDefault();
      event.stopPropagation();
      window.__CCS.STATE.resultTab = tab.dataset.tab;
      renderTabs();
      return;
    }

    const filter = event.target.closest('#screen-results [data-status-filter]');
    if (filter) {
      event.preventDefault();
      event.stopPropagation();
      galleryFilter = filter.dataset.statusFilter;
      renderGallery();
      return;
    }

    const gallery = event.target.closest('[data-real-gallery]');
    if (gallery) {
      event.preventDefault();
      event.stopPropagation();
      selectShot(gallery.dataset.realGallery);
      return;
    }

    const copySuggestionButton = event.target.closest('[data-real-copy-suggestion]');
    if (copySuggestionButton) {
      event.preventDefault();
      event.stopPropagation();
      await copySuggestion(copySuggestionButton.dataset.realCopySuggestion);
      return;
    }

    const optimizeButton = event.target.closest('[data-real-optimize]');
    if (optimizeButton) {
      event.preventDefault();
      event.stopPropagation();
      const issueId = optimizeButton.dataset.realOptimize;
      if (!issueId) return;
      const issue = [...report.issues, ...report.suspectedIssues].find(
        (item) => item.id === issueId
      );
      const shotId =
        issue?.shotId
        || report.gallery.find((item) => item.shotCode === issue?.shotCode)?.shotId;
      if (!shotId) {
        toast('找不到该问题对应的镜头');
        return;
      }
      active = false;
      await showRealOptimizer(report.task.id, shotId);
      return;
    }

    const issueTarget = event.target.closest('[data-real-issue], [data-real-suspected]');
    if (issueTarget) {
      event.preventDefault();
      event.stopPropagation();
      selectIssue(issueTarget.dataset.realIssue || issueTarget.dataset.realSuspected);
      return;
    }

    const cell = event.target.closest('[data-real-cell]');
    if (cell) {
      event.preventDefault();
      event.stopPropagation();
      if (cell.dataset.issue) selectIssue(cell.dataset.issue);
      else selectShot(cell.dataset.shot);
      return;
    }

    const locate = event.target.closest('[data-real-locate]');
    if (locate) {
      event.preventDefault();
      event.stopPropagation();
      selectShot(locate.dataset.realLocate);
      return;
    }

    const originalLightbox = event.target.closest('[data-real-lightbox-original]');
    if (originalLightbox) {
      event.preventDefault();
      event.stopPropagation();
      openLightbox(originalLightbox.dataset.realLightboxOriginal, true);
      return;
    }

    const lightbox = event.target.closest('[data-real-lightbox]');
    if (lightbox) {
      event.preventDefault();
      event.stopPropagation();
      openLightbox(lightbox.dataset.realLightbox);
      return;
    }

    const exportButton = event.target.closest('[data-export]');
    if (exportButton) {
      event.preventDefault();
      event.stopPropagation();
      const format = exportButton.dataset.export === 'json' ? 'json' : 'md';
      await exportCurrent(format);
      return;
    }

    if (event.target.closest('[data-action="copy-report"]')) {
      event.preventDefault();
      event.stopPropagation();
      const text = report.summary;
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => toast('报告摘要已复制')).catch(() => toast('复制失败'));
      } else {
        toast('复制失败，请手动选择摘要文本');
      }
      return;
    }
  }, true);

  if (window.location.hash.replace('#', '') === 'results') {
    restoreReportOnBoot();
  }
}
