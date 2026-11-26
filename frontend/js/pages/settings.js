/* 设置页：真实服务配置、密钥状态、连通性测试、本地数据与隐私告知。
   Key 仅提交到本地后端；页面只显示是否配置，不回显任何 Key 内容。 */

import { getSession, settingsApi } from '../core/api.js';
import { openConfirm } from '../core/modal.js';
import { refreshNotifications } from '../core/notifications.js';
import { ensurePrivacyAcknowledged } from '../core/privacy.js';
import { escapeHtml, toast } from '../core/ui.js';
import { formatBytes } from '../core/task-view.js';
import { refreshHistory } from './history.js';
import { refreshHome } from './home.js';

let settings = null;
let storage = null;
let testing = { analysis: false, generation: false };

const STATE_META = {
  connected: { pill: 'ok', code: 'READY', text: '已完成连通性测试' },
  ready: { pill: 'neutral', code: 'CONFIGURED', text: '配置已保存，尚未测试连接' },
  failed: { pill: 'failed', code: 'ERROR', text: '连接测试失败，请检查配置' },
  unconfigured: { pill: 'warn', code: 'NOT CONFIGURED', text: '请配置服务商、模型 ID 与 API Key' },
};

const PROVIDER_LABELS = {
  doubao: '火山方舟',
  mock: 'Mock（本地测试）',
};

const ERROR_MESSAGES = {
  auth_failed: '鉴权失败：请检查 API Key 或重新保存配置。',
  provider_unavailable: '网络不可达：请检查服务地址与本地网络。',
  provider_timeout: '连接超时：请稍后重试或检查网络。',
  quota_exceeded: '额度不足：请检查账号额度。',
  rate_limited: '服务限流：请稍后再试。',
  content_filtered: '内容安全拒绝：请检查提示词或素材。',
  invalid_response: '返回异常：请确认模型 ID 与服务地址是否正确。',
  keyring_unavailable: '系统凭据管理器不可用，Key 未保存。',
  internal_error: '连接测试发生未预期错误，请稍后重试。',
};

function $(selector) {
  return document.querySelector(selector);
}

function isSettingsScreen() {
  return window.location.hash.replace('#', '') === 'settings';
}

function serviceCard(service) {
  return document.querySelector(`#screen-settings .settings-card[data-service="${service}"]`);
}

function setStatusPill(service, state, label) {
  const card = serviceCard(service);
  const pill = card?.querySelector('.panel-head .status-pill');
  if (!pill) return;
  const meta = STATE_META[state] || STATE_META.unconfigured;
  pill.className = `status-pill is-${meta.pill}`;
  pill.innerHTML = `<i></i>${escapeHtml(label || meta.text)}`;
}

function renderService(service, data) {
  const card = serviceCard(service);
  if (!card) return;
  const prefix = service === 'analysis' ? 'analysis' : 'gen';
  const meta = STATE_META[data.state] || STATE_META.unconfigured;
  setStatusPill(service, data.state, data.statusLabel);
  const statusText = $(`#${prefix}-status-text`);
  if (statusText) {
    statusText.textContent =
      data.state === 'failed' && data.lastTest?.message
        ? data.lastTest.message
        : meta.text;
  }
  const statusCode = $(`#${prefix}-status-code`);
  if (statusCode) {
    statusCode.textContent = meta.code;
    statusCode.className = `mono ${data.state === 'connected' ? 'ok-text' : ''}`;
  }
  const modelText = $(`#${prefix}-model-text`);
  if (modelText) {
    if (service === 'generation') {
      modelText.textContent = data.model
        ? `${data.model} · 单次 1 张 · 负向内容合并进正向提示词`
        : '模型未配置 · 单次 1 张 · 负向内容合并进正向提示词';
    } else {
      modelText.textContent = data.model
        ? data.model
        : '未配置视觉模型 ID';
    }
  }
  const modelCode = $(`#${prefix}-model-code`);
  if (modelCode) modelCode.textContent = PROVIDER_LABELS[data.provider] || data.provider || '—';

  const keyMask = $(`#${prefix}-key-mask`);
  if (keyMask) {
    keyMask.textContent = data.hasKey ? data.keyMasked : '未配置';
    keyMask.title = data.keySource === 'env' ? '来自环境变量' : '';
  }
  const keyText = $(`#${prefix}-key-text`);
  if (keyText) {
    keyText.textContent =
      data.keySource === 'env'
        ? '来自环境变量，由本地后端读取；页面不回显 Key'
        : data.hasKey
          ? '已保存到 Windows 凭据管理器；页面不回显 Key'
          : '未配置 API Key；使用真实服务前请在配置中保存';
  }
  const configButton = $(`#${service === 'analysis' ? 'analysis' : 'generation'}-config-btn`);
  if (configButton) {
    const label = data.hasKey || data.model ? '更换配置' : '配置';
    configButton.innerHTML = `<svg class="icon"><use href="#i-settings"/></svg>${label}`;
  }
}

function renderBatch() {
  const active = settings?.limits?.defaultBatchSize || 4;
  document.querySelectorAll('#batch-seg [data-count]').forEach((button) => {
    button.classList.toggle('is-active', Number(button.dataset.count) === active);
  });
}

function renderStorage() {
  if (!storage) return;
  const size = $('#settings-storage-size');
  if (size) size.textContent = `约 ${formatBytes(storage.storageBytes)}`;
  const reports = $('#settings-report-stats');
  if (reports) {
    reports.textContent = `${storage.liveTasks || 0} 条任务记录 · ${storage.reports || 0} 份完整报告`;
  }
  const generations = $('#settings-gen-stats');
  if (generations) {
    generations.textContent = `${storage.generations || 0} 条生成记录 · ${storage.candidates || 0} 张候选图`;
  }
}

function renderMeta() {
  const limitButton = $('#upload-limit-btn');
  if (limitButton) limitButton.textContent = `${settings?.limits?.uploadMaxMb || 20} MB`;
  const note = $('#settings-mode-note');
  if (note) {
    note.innerHTML = `<svg class="icon"><use href="#i-info"/></svg>真实模式：服务配置与密钥仅保存在本机；${
      settings?.privacyAcknowledged
        ? '已确认第三方调用告知'
        : '首次重新生成前会提示第三方调用告知'
    }。`;
  }
}

function render() {
  if (!settings) return;
  renderService('analysis', settings.services.analysis);
  renderService('generation', settings.services.generation);
  renderBatch();
  renderStorage();
  renderMeta();
}

export async function refreshSettings() {
  if (!$('#screen-settings')) return;
  try {
    const [data, summary] = await Promise.all([settingsApi.get(), settingsApi.storage()]);
    settings = data;
    storage = summary;
    render();
  } catch (error) {
    console.warn('[char_cons] 设置加载失败：', error.message);
  }
}

function resetModalForm() {
  const copy = $('#modal-copy');
  if (copy) copy.hidden = false;
  const serviceForm = $('#service-config-form');
  if (serviceForm) serviceForm.hidden = true;
  const limitForm = $('#limit-config-form');
  if (limitForm) limitForm.hidden = true;
}

function openServiceConfig(service) {
  const data = settings?.services?.[service];
  if (!data) return;
  resetModalForm();
  $('#modal-title').textContent = `配置${service === 'analysis' ? '分析' : '图像生成'}服务`;
  $('#modal-copy').hidden = true;
  const form = $('#service-config-form');
  if (form) form.hidden = false;
  $('#config-service').value = service;
  $('#config-provider').value = data.provider || 'doubao';
  $('#config-model').value = data.model || '';
  $('#config-base').value = data.baseUrl || '';
  $('#config-key').value = '';
  $('#config-key').placeholder = data.hasKey
    ? '已配置；留空则保持不变'
    : '粘贴 API Key（仅提交到本地后端）';
  const sizeRow = $('#config-size-row');
  if (sizeRow) sizeRow.hidden = service !== 'generation';
  $('#config-size').value = data.size || '';
  const keyHint =
    data.keySource === 'env'
      ? '检测到环境变量 Key，优先级高于凭据管理器；在页面保存或删除 Key 不会覆盖环境变量。'
      : 'Key 仅提交到本地后端并保存到 Windows 凭据管理器；页面、导出、日志都不会包含 Key。';
  $('#config-hint').textContent =
    service === 'generation'
      ? `${keyHint} 测试连接会发起 1 次最小生成请求，可能产生费用。`
      : keyHint;
  const deleteButton = $('#config-delete-key');
  if (deleteButton) {
    deleteButton.hidden = !data.hasKey || data.keySource === 'env';
    deleteButton.dataset.service = service;
  }
  const confirm = $('#modal-confirm');
  confirm.className = 'btn btn-primary';
  confirm.textContent = '保存配置';
  confirm.disabled = false;
  confirm.onclick = saveServiceConfig;
  $('#modal-backdrop').hidden = false;
}

async function saveServiceConfig() {
  const service = $('#config-service').value;
  const provider = $('#config-provider').value;
  const model = $('#config-model').value.trim();
  const baseUrl = $('#config-base').value.trim();
  const apiKey = $('#config-key').value.trim();
  const size = $('#config-size').value.trim();
  if (provider === 'doubao' && !model) {
    toast('请填写控制台中的模型 ID');
    return;
  }
  const confirm = $('#modal-confirm');
  confirm.disabled = true;
  confirm.textContent = '保存中…';
  try {
    const payload = { provider, model };
    if (baseUrl) payload.baseUrl = baseUrl;
    if (apiKey) payload.apiKey = apiKey;
    if (service === 'generation') payload.size = size;
    settings = await settingsApi.updateService(service, payload);
    storage = await settingsApi.storage();
    $('#config-key').value = '';
    $('#modal-backdrop').hidden = true;
    render();
    toast(`${service === 'analysis' ? '分析' : '图像生成'}服务配置已保存`);
  } catch (error) {
    toast(error.message || '配置保存失败');
  } finally {
    confirm.disabled = false;
    confirm.textContent = '保存配置';
  }
}

async function deleteServiceKey() {
  const service = $('#config-delete-key')?.dataset.service;
  if (!service) return;
  try {
    settings = await settingsApi.deleteKey(service);
    storage = await settingsApi.storage();
    $('#modal-backdrop').hidden = true;
    render();
    toast('已删除保存的 API Key');
  } catch (error) {
    toast(error.message || '删除 Key 失败');
  }
}

function openUploadLimit() {
  if (!settings) return;
  resetModalForm();
  $('#modal-title').textContent = '单张文件上限';
  $('#modal-copy').hidden = true;
  const form = $('#limit-config-form');
  if (form) form.hidden = false;
  $('#limit-upload').value = settings.limits.uploadMaxMb || 20;
  const confirm = $('#modal-confirm');
  confirm.className = 'btn btn-primary';
  confirm.textContent = '保存上限';
  confirm.disabled = false;
  confirm.onclick = saveUploadLimit;
  $('#modal-backdrop').hidden = false;
}

async function saveUploadLimit() {
  const value = Number($('#limit-upload').value);
  if (!Number.isInteger(value) || value < 1 || value > 100) {
    toast('单张文件上限必须是 1–100 的整数');
    return;
  }
  const confirm = $('#modal-confirm');
  confirm.disabled = true;
  confirm.textContent = '保存中…';
  try {
    settings = await settingsApi.update({ uploadMaxMb: value });
    const session = getSession();
    if (session) session.maxUploadMb = value;
    applyBatchToSession();
    $('#modal-backdrop').hidden = true;
    render();
    toast(`单张文件上限已保存为 ${value} MB`);
  } catch (error) {
    toast(error.message || '保存失败');
  } finally {
    confirm.disabled = false;
    confirm.textContent = '保存上限';
  }
}

function applyBatchToSession() {
  const session = getSession();
  if (session && settings?.limits?.defaultBatchSize) {
    session.defaultBatchSize = settings.limits.defaultBatchSize;
  }
}

async function updateBatchSize(count) {
  try {
    settings = await settingsApi.update({ defaultBatchSize: count });
    applyBatchToSession();
    renderBatch();
    toast(`默认生成张数已设为 ${count} 张`);
  } catch (error) {
    toast(error.message || '保存生成张数失败');
    renderBatch();
  }
}

function testResultElement(service) {
  return $(`#test-${service === 'analysis' ? 'analysis' : 'generation'}-result`);
}

function showTestPending(service) {
  const el = testResultElement(service);
  if (!el) return;
  el.hidden = false;
  el.className = 'test-result';
  el.textContent =
    service === 'generation'
      ? '正在测试鉴权、网络可达性与额度…测试会发起 1 次最小生成请求，可能产生费用。'
      : '正在测试鉴权、网络可达性与额度…';
}

function showTestResult(service, result) {
  const el = testResultElement(service);
  if (!el) return;
  el.hidden = false;
  if (result.ok) {
    el.className = 'test-result';
    const suffix = result.mock ? '' : ` · 响应 ${result.latencyMs} ms`;
    el.textContent = `${result.message}${suffix}`;
  } else {
    el.className = 'test-result is-error';
    const friendly = ERROR_MESSAGES[result.code] || result.message || '连接测试失败';
    el.textContent = `${friendly}${result.latencyMs != null ? ` · 响应 ${result.latencyMs} ms` : ''}`;
  }
}

async function runConnectionTest(service) {
  if (testing[service]) return;
  const consented = await ensurePrivacyAcknowledged(
    service === 'analysis' ? 'analysis' : 'generation_test',
  );
  if (!consented) return;
  testing[service] = true;
  const button = document.querySelector(
    `#screen-settings [data-action="test-${service === 'analysis' ? 'analysis' : 'generation'}"]`,
  );
  const original = button?.innerHTML;
  if (button) {
    button.disabled = true;
    button.innerHTML = `${'<svg class="icon"><use href="#i-refresh"/></svg>'}测试中…`;
  }
  showTestPending(service);
  try {
    const { result, settings: view } = await settingsApi.test(service);
    settings = view;
    storage = await settingsApi.storage();
    render();
    showTestResult(service, result);
    toast(result.ok ? '服务连接测试通过' : '服务连接测试未通过，请查看原因');
  } catch (error) {
    showTestResult(service, {
      ok: false,
      code: error.code || 'internal_error',
      message: error.message,
    });
    toast(error.message || '连接测试失败');
  } finally {
    testing[service] = false;
    if (button) {
      button.disabled = false;
      button.innerHTML = original;
    }
  }
}

async function clearLocalData() {
  await openConfirm({
    title: '清除本地数据',
    message:
      '将删除历史任务、候选图与生成记录。此操作不可撤销；API Key 与本地设置会保留。',
    confirmText: '确认清除',
    danger: true,
    busyText: '清除中…',
    onConfirm: async () => {
      try {
        await settingsApi.clearData(true);
        await refreshSettings();
        await refreshHistory();
        await refreshHome();
        await refreshNotifications();
        toast('本地任务数据已清除');
        return true;
      } catch (error) {
        toast(error.message || '清除失败，请稍后重试');
        return false;
      }
    },
  });
}

export function initSettingsIntegration() {
  document.addEventListener(
    'click',
    async (event) => {
      if (!isSettingsScreen()) return;

      if (event.target.closest('[data-action="close-modal"]')) {
        const keyInput = $('#config-key');
        if (keyInput) keyInput.value = '';
        return;
      }

      const batch = event.target.closest('#batch-seg [data-count]');
      if (batch) {
        event.preventDefault();
        event.stopPropagation();
        await updateBatchSize(Number(batch.dataset.count));
        return;
      }

      const configButton = event.target.closest('[data-action="config-service"]');
      if (configButton) {
        event.preventDefault();
        event.stopPropagation();
        openServiceConfig(configButton.dataset.service);
        return;
      }

      const testButton = event.target.closest(
        '[data-action="test-analysis"], [data-action="test-generation"]',
      );
      if (testButton) {
        event.preventDefault();
        event.stopPropagation();
        const service =
          testButton.dataset.action === 'test-analysis' ? 'analysis' : 'generation';
        await runConnectionTest(service);
        return;
      }

      if (event.target.closest('[data-action="delete-key"]')) {
        event.preventDefault();
        event.stopPropagation();
        await deleteServiceKey();
        return;
      }

      if (event.target.closest('[data-action="edit-upload-limit"]')) {
        event.preventDefault();
        event.stopPropagation();
        openUploadLimit();
        return;
      }

      if (event.target.closest('[data-action="clear-data"]')) {
        event.preventDefault();
        event.stopPropagation();
        await clearLocalData();
      }
    },
    true,
  );

  window.addEventListener('hashchange', () => {
    if (window.location.hash.replace('#', '') === 'settings') refreshSettings();
  });
}
