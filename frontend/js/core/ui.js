/* 复用定稿页面的 Toast 元素；不新增浮层或页面。 */

let toastTimer = null;

export function toast(message) {
  const el = document.querySelector('#toast');
  const text = document.querySelector('#toast-text');
  if (!el || !text) return;
  text.textContent = message;
  el.classList.add('is-visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('is-visible'), 2600);
}

export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[char]));
}
