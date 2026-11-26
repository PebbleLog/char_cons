/* 新建检测任务：只接受真实图片并始终创建真实任务。

- 不再提供示例角色、示例剧本或默认镜头；
- 角色设定、镜头为空时不允许开始；
- 首次真实分析前完成第三方调用告知，随后启动真实分析并进入分析工作台。
*/

import { getSession, tasksApi } from '../core/api.js';
import { ensurePrivacyAcknowledged } from '../core/privacy.js';
import { toast } from '../core/ui.js';
import { showRealAnalysis } from './analysis.js';

let submitting = false;

function appState() {
  return window.__CCS?.STATE || null;
}

function deriveCharacterName(profile) {
  const first = profile.trim().split(/[，,。；;\s·]/)[0];
  return (first || '未命名').slice(0, 20);
}

function hasNativeFiles(state) {
  return state.shots.filter((shot) => shot.nativeFile).length;
}

async function submitRealTask(button) {
  const state = appState();
  if (!state || submitting) return;

  const profile = document.querySelector('#character-input')?.value.trim() || '';
  const script = document.querySelector('#script-input')?.value.trim() || '';
  if (!profile || !script) {
    toast('角色设定、剧本说明与至少 1 张镜头齐全后才能开始');
    return;
  }
  if (profile.length > 500) {
    toast('角色设定请控制在 500 字以内');
    return;
  }
  if (script.length > 1000) {
    toast('剧本说明请控制在 1000 字以内');
    return;
  }

  const files = state.shots.map((shot) => shot.nativeFile).filter(Boolean);
  const characterName = deriveCharacterName(profile);
  const session = getSession();

  submitting = true;
  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  try {
    const task = await tasksApi.create({
      name: `${characterName} · 新检测`,
      characterName,
      profileRaw: profile,
      scriptRaw: script,
      defaultBatchSize: session?.defaultBatchSize || 4,
    });

    let result;
    try {
      result = await tasksApi.upload(task.id, files);
    } catch (error) {
      toast(`任务已保存，但镜头上传失败：${error.message}`);
      window.location.hash = '#history';
      return;
    }

    const saved = result.shots?.length || 0;
    const errors = result.errors || [];
    const duplicates = result.duplicates || [];

    if (saved === 0) {
      const reason = errors[0] ? `${errors[0].filename} · ${errors[0].message}` : '没有可用的镜头';
      toast(`镜头上传失败：${reason}`);
      window.location.hash = '#history';
      return;
    }

    let message = `任务已保存 · ${saved} 张镜头`;
    if (errors.length) {
      message = `${saved} 张已保存，${errors.length} 张失败：${errors[0].filename} · ${errors[0].message}`;
    } else if (duplicates.length) {
      message = `任务已保存 · ${saved} 张镜头 · ${duplicates.length} 张疑似重复`;
    }

    let startError = null;
    let started = false;
    const consented = await ensurePrivacyAcknowledged('analysis_run');
    if (consented) {
      try {
        await tasksApi.startAnalysis(task.id);
        started = true;
        message += ' · 分析已开始';
      } catch (error) {
        startError = error.message;
        message += ' · 分析启动失败，可在历史页重试';
      }
    } else {
      message += ' · 可在历史页开始分析';
    }
    toast(startError ? `${message}（${startError}）` : message);
    if (started) {
      await showRealAnalysis(task.id, task.name, { keepCreateShots: true });
    } else {
      window.location.hash = '#history';
    }
  } catch (error) {
    toast(error?.message || '任务创建失败，请稍后重试');
  } finally {
    submitting = false;
    button.disabled = false;
    button.removeAttribute('aria-busy');
  }
}

export function initCreateIntegration() {
  document.addEventListener(
    'click',
    (event) => {
      const button = event.target.closest('[data-action="start-analysis"]');
      if (!button) return;
      const state = appState();
      if (!state) return;
      event.preventDefault();
      event.stopPropagation();
      if (button.disabled) return;
      const nativeCount = hasNativeFiles(state);
      if (nativeCount === 0) {
        toast('请先上传至少 1 张真实镜头图片');
        return;
      }
      if (nativeCount !== state.shots.length) {
        toast('存在未关联真实文件的镜头，请删除后重新上传');
        return;
      }
      submitRealTask(button);
    },
    true,
  );
}
