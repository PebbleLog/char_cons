/* 任务状态到定稿 UI 文案/样式令牌的映射。
   文案沿用原型：待开始 / 分析中 / 已暂停 / 已完成 / 部分完成 / 分析失败。 */

import { escapeHtml } from './ui.js';

const STATUS_META = {
  idle: { label: '待开始', pill: 'neutral' },
  running: { label: '分析中', pill: 'info' },
  retrying: { label: '重新观察中', pill: 'info' },
  paused: { label: '已暂停', pill: 'warn' },
  completed: { label: '已完成', pill: 'ok' },
  partial: { label: '部分完成', pill: 'partial' },
  failed: { label: '分析失败', pill: 'failed' },
};

export function statusMeta(status) {
  return STATUS_META[status] || STATUS_META.idle;
}

export function statusPill(task) {
  const meta = statusMeta(task.status);
  return `<span class="status-pill is-${meta.pill}"><i></i>${meta.label}</span>`;
}

export function taskBadge(task) {
  if (task.issueCount > 0) return { cls: 'is-warn', count: task.issueCount };
  if (task.unknownCount > 0) return { cls: 'is-info', count: task.unknownCount };
  return { cls: 'is-ok', count: 0 };
}

export function homeSummary(task) {
  const shots = task.shotsCount || 0;
  switch (task.status) {
    case 'completed':
      if (task.issueCount > 0) {
        return `${shots} 个镜头 · ${task.issueCount} 处确定不一致 · ${task.unknownCount} 项无法判断`;
      }
      return task.unknownCount > 0
        ? `${shots} 个镜头 · 无确定问题 · ${task.unknownCount} 项无法判断`
        : `${shots} 个镜头 · 全部一致 · 无确定问题`;
    case 'partial':
      return `${shots} 个镜头 · 部分镜头分析失败`;
    case 'failed':
      return `${shots} 个镜头 · 分析失败`;
    case 'paused':
      return `${shots} 个镜头 · 分析已暂停`;
    case 'running':
    case 'retrying':
      return `${shots} 个镜头 · 正在分析`;
    default:
      return `${shots} 个镜头 · 尚未开始分析`;
  }
}

export function historyResult(task) {
  const shots = task.shotsCount || 0;
  switch (task.status) {
    case 'completed':
      if (task.issueCount > 0) {
        return {
          pill: 'warn',
          label: `${task.issueCount} 个确定问题`,
          small: task.unknownCount > 0 ? `${task.unknownCount} 项无法判断` : '无确定问题',
        };
      }
      return task.unknownCount > 0
        ? {
            pill: 'info',
            label: '无确定问题',
            small: `${task.unknownCount} 项无法判断`,
          }
        : { pill: 'ok', label: '全部一致', small: '无确定问题' };
    case 'partial':
      return { pill: 'partial', label: '部分完成', small: `${shots} 个镜头 · 部分分析失败` };
    case 'failed':
      return {
        pill: 'failed',
        label: '分析失败',
        small: task.errorMessage || '未生成报告',
      };
    case 'paused':
      return { pill: 'warn', label: '已暂停', small: '可重新观察失败镜头' };
    case 'running':
    case 'retrying':
      return { pill: 'info', label: statusMeta(task.status).label, small: '正在观察镜头' };
    default:
      return { pill: 'neutral', label: '待开始', small: '任务已保存，尚未分析' };
  }
}

export function historyTimeSmall(task) {
  if (task.status === 'completed' || task.status === 'partial') return '本地报告';
  if (task.status === 'failed') return '未生成报告';
  if (task.status === 'idle') return '草稿';
  return '进行中';
}

export function historyDataStatus(status) {
  if (status === 'completed') return 'done';
  if (status === 'partial') return 'partial';
  if (status === 'failed') return 'failed';
  return 'pending';
}

export function formatWhen(iso) {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  const now = new Date();
  const pad = (value) => String(value).padStart(2, '0');
  const time = `${pad(date.getHours())}:${pad(date.getMinutes())}`;
  const sameDay = date.toDateString() === now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (sameDay) return `今天 ${time}`;
  if (date.toDateString() === yesterday.toDateString()) return `昨天 ${time}`;
  const base = `${date.getMonth() + 1} 月 ${date.getDate()} 日`;
  return date.getFullYear() === now.getFullYear() ? base : `${date.getFullYear()} 年 ${base}`;
}

export function formatDate(iso) {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return `${date.getMonth() + 1} 月 ${date.getDate()} 日`;
}

export function formatBytes(bytes) {
  const value = Number(bytes) || 0;
  if (value <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export function thumbMarkup(url, alt, badge, thumbClass = 'row-thumb') {
  const image = url
    ? `<img src="${escapeHtml(url)}" alt="${escapeHtml(alt)}">`
    : '<svg class="icon"><use href="#i-image"/></svg>';
  const empty = url ? '' : ' is-empty';
  return `<span class="${thumbClass}${empty}">${image}<i class="thumb-badge ${badge.cls}">${badge.count}</i></span>`;
}
