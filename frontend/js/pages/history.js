/* 历史报告页：真实任务列表、筛选、搜索与存档概况。
   行结构与筛选属性（data-status / data-search）沿用原型，使既有过滤逻辑继续生效。 */

import { archiveApi, tasksApi } from '../core/api.js';
import { escapeHtml } from '../core/ui.js';
import {
  formatBytes,
  formatDate,
  formatWhen,
  historyDataStatus,
  historyResult,
  historyTimeSmall,
  thumbMarkup,
} from '../core/task-view.js';

let taskCount = 0;
let loadFailed = false;
let autoRefreshTimer = null;

function scheduleAutoRefresh(items) {
  if (autoRefreshTimer) {
    clearTimeout(autoRefreshTimer);
    autoRefreshTimer = null;
  }
  const active = items.some((task) =>
    ['running', 'retrying'].includes(task.status),
  );
  if (!active) return;
  autoRefreshTimer = setTimeout(() => {
    autoRefreshTimer = null;
    if (window.location.hash.replace('#', '') === 'history') refreshHistory();
  }, 3000);
}

function rowMarkup(task) {
  const result = historyResult(task);
  const time = formatWhen(task.updatedAt || task.createdAt);
  const search = `${task.name} ${task.characterName || ''}`;
  const badge = task.issueCount > 0
    ? { cls: 'is-warn', count: task.issueCount }
    : task.unknownCount > 0
      ? { cls: 'is-info', count: task.unknownCount }
      : { cls: 'is-ok', count: 0 };
  const thumb = thumbMarkup(task.thumbnailUrl, `${task.name} 缩略图`, badge, 'history-thumb');
  const shotText = task.characterName
    ? `角色：${escapeHtml(task.characterName)} · ${task.shotsCount} 个镜头`
    : `${task.shotsCount} 个镜头`;
  return `
    <button class="history-row" data-task-id="${escapeHtml(task.id)}" data-task-status="${escapeHtml(task.status)}"
            data-status="${historyDataStatus(task.status)}" data-search="${escapeHtml(search)}">
      ${thumb}
      <span class="history-main"><b>${escapeHtml(task.name)}</b><span>${shotText}</span></span>
      <span class="history-result"><span class="status-pill is-${result.pill}"><i></i>${escapeHtml(result.label)}</span><small>${escapeHtml(result.small)}</small></span>
      <span class="history-time">${escapeHtml(time)}<small>${escapeHtml(historyTimeSmall(task))}</small></span>
      <span class="history-go"><svg class="icon"><use href="#i-arrow-right"/></svg></span>
    </button>`;
}

function currentFilter() {
  return window.__CCS?.STATE?.historyFilter || 'all';
}

export function applyHistoryFilter() {
  const search = (document.querySelector('#history-search')?.value || '').trim().toLowerCase();
  const filter = currentFilter();
  let visible = 0;
  document.querySelectorAll('#history-rows .history-row').forEach((row) => {
    const statusOk = filter === 'all' || row.dataset.status === filter;
    const searchOk = !search || (row.dataset.search || '').toLowerCase().includes(search);
    const ok = statusOk && searchOk;
    row.hidden = !ok;
    if (ok) visible += 1;
  });
  const empty = document.querySelector('#history-empty');
  if (empty) {
    empty.hidden = visible > 0;
    const copy = empty.querySelector('p');
    if (copy) {
      copy.textContent = loadFailed
        ? '历史任务加载失败，请刷新页面重试'
        : taskCount === 0
          ? '还没有本地任务'
          : '没有找到匹配的任务';
    }
  }
}

function renderSummary(data, summary) {
  const pill = document.querySelector('#screen-history .page-head .status-pill');
  if (pill) pill.innerHTML = `<i></i>本地存档 · ${summary.liveTasks} 条`;

  const stats = document.querySelectorAll('#screen-history .archive-stats div b');
  if (stats.length >= 3) {
    stats[0].textContent = String(summary.liveTasks);
    stats[1].textContent = String(summary.reports);
    stats[2].textContent = String(summary.generations);
  }
  const facts = document.querySelectorAll('#screen-history .archive-facts div b');
  if (facts.length >= 3) {
    facts[0].textContent = formatBytes(summary.storageBytes);
    facts[1].textContent = '仅本机';
    facts[2].textContent = summary.earliest ? formatDate(summary.earliest) : '—';
  }
  const foot = document.querySelector('#screen-history .history-foot span');
  if (foot) {
    foot.textContent = `共 ${summary.liveTasks} 条本地记录 · 占用约 ${formatBytes(summary.storageBytes)}`;
  }
}

export async function refreshHistory() {
  const list = document.querySelector('#history-rows');
  const empty = document.querySelector('#history-empty');
  if (!list) return;
  try {
    const [data, summary] = await Promise.all([
      tasksApi.list({ limit: 100, mode: 'live' }),
      archiveApi.summary(),
    ]);
    taskCount = data.total;
    loadFailed = false;
    list.classList.remove('is-loading');
    list.innerHTML = data.items.map(rowMarkup).join('');
    renderSummary(data, summary);
    applyHistoryFilter();
    if (!data.items.length && empty) empty.hidden = false;
    scheduleAutoRefresh(data.items);
  } catch (error) {
    // 不展示原型演示数据；加载失败时给出明确状态。
    loadFailed = true;
    taskCount = 0;
    list.classList.remove('is-loading');
    list.innerHTML = '';
    if (empty) empty.hidden = false;
    const copy = empty?.querySelector('p');
    if (copy) copy.textContent = '历史任务加载失败，请刷新页面重试';
    const pill = document.querySelector('#screen-history .page-head .status-pill');
    if (pill) pill.innerHTML = '<i></i>存档读取失败';
    const foot = document.querySelector('#screen-history .history-foot span');
    if (foot) foot.textContent = '本地存档读取失败，请刷新重试';
    console.warn('[char_cons] 历史任务加载失败：', error.message);
  }
}
