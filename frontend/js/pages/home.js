/* 工作台「最近检测任务」真实数据。DOM 结构与定稿原型保持一致。 */

import { tasksApi } from '../core/api.js';
import { escapeHtml, toast } from '../core/ui.js';
import {
  formatWhen,
  homeSummary,
  statusPill,
  taskBadge,
  thumbMarkup,
} from '../core/task-view.js';

function rowMarkup(task) {
  const badge = taskBadge(task);
  const showBadge = task.shotsCount > 0;
  const thumb = showBadge
    ? thumbMarkup(task.thumbnailUrl, `${task.name} 缩略图`, badge, 'row-thumb')
    : `<span class="row-thumb is-empty"><svg class="icon"><use href="#i-image"/></svg></span>`;
  return `
    <button class="task-row" data-task-id="${escapeHtml(task.id)}" data-task-status="${escapeHtml(task.status)}">
      ${thumb}
      <span class="row-main"><b>${escapeHtml(task.name)}</b><span>${escapeHtml(homeSummary(task))}</span></span>
      <span class="row-meta">${statusPill(task)}<small>${formatWhen(task.updatedAt || task.createdAt)}</small></span>
      <svg class="icon row-arrow"><use href="#i-chevron-right"/></svg>
    </button>`;
}

const EMPTY = `
  <div class="history-empty">
    <svg class="icon"><use href="#i-image"/></svg>
    <p>还没有本地检测任务</p>
  </div>`;

export async function refreshHome() {
  const container = document.querySelector('#screen-home .task-rows');
  if (!container) return;
  try {
    const data = await tasksApi.list({ limit: 3, mode: 'live' });
    container.classList.remove('is-loading');
    if (!data.items.length) {
      container.innerHTML = EMPTY;
      return;
    }
    container.innerHTML = data.items.map(rowMarkup).join('');
  } catch (error) {
    // 不展示原型演示数据；加载失败时给出明确状态。
    container.classList.remove('is-loading');
    container.innerHTML = `
      <div class="history-empty">
        <svg class="icon"><use href="#i-image"/></svg>
        <p>最近任务加载失败，请刷新页面重试</p>
      </div>`;
    console.warn('[char_cons] 最近任务加载失败：', error.message);
  }
}

export function notifyTaskRow(message) {
  toast(message);
}
