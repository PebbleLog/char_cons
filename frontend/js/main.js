/* ES Modules 入口：会话、页面数据接入与新建任务流程。
   分析 / 结果 / 优化页当前仍由定稿原型的本地模拟驱动。 */

import { initSession, tasksApi } from './core/api.js';
import { openConfirm } from './core/modal.js';
import { initNotifications, refreshNotifications } from './core/notifications.js';
import { ensurePrivacyAcknowledged } from './core/privacy.js';
import { toast } from './core/ui.js';
import { initAnalysisIntegration, showRealAnalysis } from './pages/analysis.js';
import { initCreateIntegration } from './pages/create.js';
import { refreshHistory } from './pages/history.js';
import { refreshHome } from './pages/home.js';
import { initOptimizerIntegration } from './pages/optimizer.js';
import { initResultsIntegration, showRealReport } from './pages/results.js';
import { initSettingsIntegration, refreshSettings } from './pages/settings.js';

function currentScreen() {
  return window.location.hash.replace('#', '') || 'home';
}

async function openRetryTask(taskId, title, message) {
  const consented = await ensurePrivacyAcknowledged('analysis_run');
  if (!consented) return;
  await openConfirm({
    title,
    message,
    confirmText: '开始分析',
    busyText: '启动中…',
    onConfirm: async () => {
      try {
        await tasksApi.startAnalysis(taskId);
        toast('已重新开始分析；完成后可在历史报告打开');
        await refreshHistory();
        return true;
      } catch (error) {
        toast(error.message || '无法开始分析，请检查素材与服务配置');
        return false;
      }
    },
  });
}

async function handleTaskRowClick(event) {
  const row = event.target.closest('[data-task-id]');
  if (!row) return;
  event.preventDefault();
  event.stopPropagation();
  const status = row.dataset.taskStatus;
  const taskId = row.dataset.taskId;
  if (status === 'completed' || status === 'partial') {
    await showRealReport(taskId);
    return;
  }
  if (status === 'running' || status === 'retrying') {
    await showRealAnalysis(taskId);
    return;
  }
  if (status === 'idle' || status === 'failed' || status === 'paused') {
    try {
      const detail = await tasksApi.get(taskId);
      if (!detail.shots?.length) {
        toast('该任务没有可用镜头，请先在新建任务页补充素材');
        return;
      }
      const reason =
        detail.errorMessage
        || (status === 'idle' ? '任务已保存，尚未开始分析。' : '上次分析未完成。');
      const next =
        '可保留已上传素材并重新分析；若持续失败，请检查设置页的服务配置与模型 ID。';
      await openRetryTask(
        taskId,
        status === 'failed' ? '未生成报告' : '重新开始分析',
        `${detail.name || '该任务'}：${reason} ${next}`,
      );
    } catch (error) {
      toast(error.message || '任务详情加载失败');
    }
    return;
  }
  toast('分析仍在进行中，请稍后刷新历史页');
}

async function refreshForScreen(name) {
  if (name === 'home') await refreshHome();
  if (name === 'history') await refreshHistory();
  if (name === 'settings') await refreshSettings();
}

async function boot() {
  try {
    await initSession();
  } catch (error) {
    toast(error.message || '无法连接本地服务');
  }

  initAnalysisIntegration();
  initCreateIntegration();
  initNotifications();
  initResultsIntegration();
  initOptimizerIntegration();
  initSettingsIntegration();
  document.addEventListener('click', handleTaskRowClick);
  document.addEventListener('click', (event) => {
    const nav = event.target.closest('[data-nav]');
    if (!nav) return;
    const name = nav.dataset.nav;
    setTimeout(() => {
      if (currentScreen() === name) refreshForScreen(name);
    }, 0);
  });
  window.addEventListener('hashchange', () => {
    refreshForScreen(currentScreen());
    refreshNotifications();
  });

  await refreshHome();
  await refreshNotifications();
  if (currentScreen() === 'history') await refreshHistory();
  if (currentScreen() === 'settings') await refreshSettings();
  // 首页/历史的真实数据已就绪，撤掉启动遮罩；结果/优化页由各自模块移除。
  if (['home', 'history'].includes(currentScreen())) {
    document.documentElement.classList.remove('ccs-restoring');
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot, { once: true });
} else {
  boot();
}
