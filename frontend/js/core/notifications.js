/* 顶栏通知浮层：由真实本地任务的终态记录派生，不展示写死的示例数据。
   时间与问题数直接来自 /api/tasks；已读时间只记录在本机浏览器。 */

import { tasksApi } from './api.js';
import { escapeHtml } from './ui.js';
import { formatWhen } from './task-view.js';

const SEEN_KEY = 'char_cons_notify_seen';
const MAX_ITEMS = 3;
const REPORTABLE = new Set(['completed', 'partial']);

const ENTRY = {
  completed: { icon: 'is-ok', glyph: 'i-check', title: '分析已完成' },
  partial: { icon: 'is-warn', glyph: 'i-alert', title: '分析部分完成' },
  failed: { icon: 'is-alert', glyph: 'i-alert', title: '分析失败' },
};

/* 当前列表中最新的通知时间（毫秒），用于红点判定 */
let latestAt = 0;

function readSeen() {
  try {
    return Number(localStorage.getItem(SEEN_KEY)) || 0;
  } catch {
    return 0;
  }
}

function saveSeen(value) {
  try {
    localStorage.setItem(SEEN_KEY, String(value));
  } catch {
    /* 浏览器禁用存储时红点仅影响本次会话 */
  }
}

function popoverOpen() {
  const popover = document.querySelector('#notify-popover');
  return Boolean(popover && !popover.hidden);
}

function detailFor(task) {
  if (task.status === 'completed') {
    return task.issueCount > 0
      ? `${task.name} · ${task.issueCount} 处确定问题`
      : `${task.name} · 无确定问题`;
  }
  if (task.status === 'partial') return `${task.name} · 部分镜头分析失败`;
  return `${task.name} · 未生成报告`;
}

function itemMarkup({ icon, glyph, title, detail, at }) {
  return `
    <div class="notify-item">
      <span class="status-icon ${icon}"><svg class="icon"><use href="#${glyph}"/></svg></span>
      <div><b>${escapeHtml(title)}</b><p>${escapeHtml(detail)}</p><small>${escapeHtml(formatWhen(at))}</small></div>
    </div>`;
}

function buildItems(tasks) {
  const terminal = tasks
    .filter((task) => ENTRY[task.status])
    .map((task) => ({ task, at: task.completedAt || task.updatedAt }))
    .filter((entry) => entry.at)
    .sort((a, b) => (Date.parse(b.at) || 0) - (Date.parse(a.at) || 0));

  const items = terminal.slice(0, MAX_ITEMS).map(({ task, at }) => ({
    ...ENTRY[task.status],
    detail: detailFor(task),
    at,
  }));

  const latestReport = terminal.find(({ task }) => REPORTABLE.has(task.status));
  if (latestReport) {
    items.push({
      icon: 'is-info',
      glyph: 'i-info',
      title: '历史报告已保存',
      detail: '报告仅保存在本机，可随时导出',
      at: latestReport.task.updatedAt || latestReport.at,
    });
  }
  return items;
}

function syncDot(markSeen = false) {
  const button = document.querySelector('#notify-btn');
  if (!button) return;
  let unread = latestAt > 0 && latestAt > readSeen();
  if (markSeen || popoverOpen()) {
    if (unread) saveSeen(latestAt);
    unread = false;
  }
  button.classList.toggle('has-dot', unread);
}

function render(tasks) {
  const list = document.querySelector('#notify-list');
  if (!list) return;
  const items = buildItems(tasks);
  list.innerHTML = items.length
    ? items.map(itemMarkup).join('')
    : '<div class="notify-empty">暂无通知</div>';
  latestAt = items.reduce((max, item) => Math.max(max, Date.parse(item.at) || 0), 0);
  syncDot();
}

export async function refreshNotifications() {
  try {
    const data = await tasksApi.list({ limit: 20, mode: 'live' });
    render(data.items || []);
  } catch (error) {
    // 不覆盖当前内容：后端暂时不可用时保留上一次可用的通知
    console.warn('[char_cons] 通知加载失败：', error.message);
  }
}

export function initNotifications() {
  document.addEventListener('click', (event) => {
    if (!event.target.closest('#notify-btn') || !popoverOpen()) return;
    // app.js 先切换浮层显隐，这里再按最终状态更新已读红点并拉取最新结果
    syncDot(true);
    refreshNotifications();
  });
  window.addEventListener('char_cons:notifications-changed', () => {
    refreshNotifications();
  });
}
