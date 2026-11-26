/* 复用定稿确认弹窗：真实流程的二次确认与首次第三方调用告知。
   不新增页面；设置页配置表单复用同一弹窗容器，但由 settings.js 自行管理。 */

import { toast } from './ui.js';

export function openConfirm({
  title,
  message,
  confirmText = '确认',
  danger = false,
  busyText = '处理中…',
  onConfirm = null,
}) {
  const backdrop = document.querySelector('#modal-backdrop');
  const titleEl = document.querySelector('#modal-title');
  const copy = document.querySelector('#modal-copy');
  const confirmBtn = document.querySelector('#modal-confirm');
  const serviceForm = document.querySelector('#service-config-form');
  const limitForm = document.querySelector('#limit-config-form');
  if (!backdrop || !titleEl || !copy || !confirmBtn) return Promise.resolve(false);

  if (serviceForm) serviceForm.hidden = true;
  if (limitForm) limitForm.hidden = true;
  copy.hidden = false;
  titleEl.textContent = title;
  copy.textContent = message;
  confirmBtn.className = `btn ${danger ? 'btn-danger' : 'btn-primary'}`;
  confirmBtn.textContent = confirmText;
  confirmBtn.disabled = false;
  backdrop.hidden = false;

  return new Promise((resolve) => {
    let settled = false;
    let busy = false;

    const cleanup = () => {
      document.removeEventListener('click', onDocumentClick, true);
      document.removeEventListener('keydown', onKeyDown, true);
      confirmBtn.onclick = null;
    };

    const finish = (value) => {
      if (settled) return;
      settled = true;
      cleanup();
      backdrop.hidden = true;
      resolve(value);
    };

    function onDocumentClick(event) {
      if (!backdrop.hidden && event.target.closest('[data-action="close-modal"]')) {
        event.preventDefault();
        event.stopPropagation();
        if (!busy) finish(false);
        return;
      }
      if (event.target === backdrop && !busy) finish(false);
    }

    function onKeyDown(event) {
      if (event.key === 'Escape' && !busy) finish(false);
    }

    confirmBtn.onclick = async () => {
      if (busy) return;
      busy = true;
      confirmBtn.disabled = true;
      confirmBtn.textContent = busyText;
      try {
        const ok = onConfirm ? await onConfirm() : true;
        if (ok === false) {
          confirmBtn.disabled = false;
          confirmBtn.textContent = confirmText;
          busy = false;
          return;
        }
        finish(true);
      } catch (error) {
        confirmBtn.disabled = false;
        confirmBtn.textContent = confirmText;
        busy = false;
        toast(error?.message || '操作失败，请稍后重试');
      }
    };

    document.addEventListener('click', onDocumentClick, true);
    document.addEventListener('keydown', onKeyDown, true);
  });
}
