/* 统一 API 封装：CSRF、错误归一化、会话初始化。
   不把 CSRF Token 写入 localStorage / sessionStorage。 */

let csrfToken = null;
let session = null;
let sessionPromise = null;

export class ApiError extends Error {
  constructor(message, { code = 'request_failed', status = 0, retryable = false, action = null, details = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.retryable = retryable;
    this.action = action;
    this.details = details;
  }
}

async function loadSession(force = false) {
  if (session && !force) return session;
  if (!sessionPromise || force) {
    sessionPromise = fetch('/api/session', { credentials: 'same-origin', cache: 'no-store' })
      .then(async (response) => {
        if (!response.ok) throw new ApiError('无法连接本地服务，请确认服务已启动。', { status: response.status });
        const data = await response.json();
        session = data;
        csrfToken = data.csrfToken || null;
        return data;
      })
      .catch((error) => {
        sessionPromise = null;
        if (error instanceof ApiError) throw error;
        throw new ApiError('无法连接本地服务，请确认服务已启动。', { code: 'network_error' });
      });
  }
  return sessionPromise;
}

export async function initSession() {
  return loadSession();
}

export function getSession() {
  return session;
}

function buildUrl(path, params) {
  if (!params) return path;
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, value);
  });
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

async function send(method, path, { json, formData, headers = {}, signal } = {}) {
  const options = { method, credentials: 'same-origin', headers: { ...headers }, signal };
  if (json !== undefined) {
    options.headers['Content-Type'] = 'application/json; charset=utf-8';
    options.body = JSON.stringify(json);
  } else if (formData) {
    options.body = formData;
  }
  if (method !== 'GET' && method !== 'HEAD' && csrfToken) {
    options.headers['X-CSRF-Token'] = csrfToken;
  }
  return fetch(path, options);
}

async function parseError(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  const detail = payload && payload.error ? payload.error : null;
  return new ApiError(detail?.message || `请求失败（${response.status}）`, {
    code: detail?.code || 'http_error',
    status: response.status,
    retryable: Boolean(detail?.retryable),
    action: detail?.action || null,
    details: detail?.details || null,
  });
}

export async function request(method, path, options = {}) {
  await loadSession();
  let response = await send(method, path, options);
  if (response.status === 403) {
    const error = await parseError(response.clone());
    if (error.code === 'csrf_failed') {
      await loadSession(true);
      response = await send(method, path, options);
    }
  }
  if (response.status === 204) return null;
  if (!response.ok) throw await parseError(response);
  return response.json();
}

export const tasksApi = {
  create: (payload) => request('POST', '/api/tasks', { json: payload }),
  list: (params = {}) => request('GET', buildUrl('/api/tasks', params)),
  get: (taskId) => request('GET', `/api/tasks/${encodeURIComponent(taskId)}`),
  update: (taskId, payload) =>
    request('PATCH', `/api/tasks/${encodeURIComponent(taskId)}`, { json: payload }),
  remove: (taskId) => request('DELETE', `/api/tasks/${encodeURIComponent(taskId)}`),
  validate: (taskId) =>
    request('POST', `/api/tasks/${encodeURIComponent(taskId)}/validate`),
  upload: (taskId, files) => {
    const form = new FormData();
    files.forEach((file) => form.append('files', file, file.name));
    return request('POST', `/api/tasks/${encodeURIComponent(taskId)}/shots`, { formData: form });
  },
  reorder: (taskId, shotIds) =>
    request('POST', `/api/tasks/${encodeURIComponent(taskId)}/shots/reorder`, {
      json: { shotIds },
    }),
  removeShot: (taskId, shotId) =>
    request(
      'DELETE',
      `/api/tasks/${encodeURIComponent(taskId)}/shots/${encodeURIComponent(shotId)}`,
    ),
  report: (taskId) =>
    request('GET', `/api/tasks/${encodeURIComponent(taskId)}/report`),
  analysis: (taskId) =>
    request('GET', `/api/tasks/${encodeURIComponent(taskId)}/analysis`),
  startAnalysis: (taskId) =>
    request('POST', `/api/tasks/${encodeURIComponent(taskId)}/analyze`),
  cancelAnalysis: (taskId) =>
    request('POST', `/api/tasks/${encodeURIComponent(taskId)}/cancel`),
  shotObservations: (taskId, shotId) =>
    request(
      'GET',
      `/api/tasks/${encodeURIComponent(taskId)}/shots/${encodeURIComponent(shotId)}/observations`,
    ),
  note: (taskId, shotId, note) =>
    request(
      'PATCH',
      `/api/tasks/${encodeURIComponent(taskId)}/shots/${encodeURIComponent(shotId)}`,
      { json: { note } },
    ),
  shotOptimizer: (taskId, shotId) =>
    request(
      'GET',
      `/api/tasks/${encodeURIComponent(taskId)}/shots/${encodeURIComponent(shotId)}/optimizer`,
    ),
  generateShot: (taskId, shotId, candidateCount) =>
    request(
      'POST',
      `/api/tasks/${encodeURIComponent(taskId)}/shots/${encodeURIComponent(shotId)}/generate`,
      { json: { candidateCount } },
    ),
  generation: (taskId, generationId) =>
    request(
      'GET',
      `/api/tasks/${encodeURIComponent(taskId)}/generations/${encodeURIComponent(generationId)}`,
    ),
  cancelGeneration: (taskId, generationId) =>
    request(
      'POST',
      `/api/tasks/${encodeURIComponent(taskId)}/generations/${encodeURIComponent(generationId)}/cancel`,
    ),
  adopt: (taskId, generationId, candidateId) =>
    request(
      'POST',
      `/api/tasks/${encodeURIComponent(taskId)}/generations/${encodeURIComponent(generationId)}/adopt`,
      { json: { candidateId } },
    ),
  recheck: (taskId, shotId) =>
    request(
      'POST',
      `/api/tasks/${encodeURIComponent(taskId)}/shots/${encodeURIComponent(shotId)}/recheck`,
    ),
  exportReport: (taskId, format) =>
    downloadFile(
      `/api/tasks/${encodeURIComponent(taskId)}/export?format=${encodeURIComponent(format)}`,
    ),
};

function filenameFromDisposition(header) {
  if (!header) return null;
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1]);
    } catch {
      return null;
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header);
  return plain ? plain[1] : null;
}

async function downloadFile(path) {
  await loadSession();
  const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store' });
  if (!response.ok) throw await parseError(response);
  const blob = await response.blob();
  return {
    blob,
    filename: filenameFromDisposition(response.headers.get('content-disposition')),
  };
}

export const archiveApi = {
  summary: () => request('GET', '/api/archive/summary'),
};

export const settingsApi = {
  get: () => request('GET', '/api/settings'),
  update: (payload) => request('PUT', '/api/settings', { json: payload }),
  updateService: (service, payload) =>
    request('PUT', `/api/settings/services/${encodeURIComponent(service)}`, {
      json: payload,
    }),
  deleteKey: (service) =>
    request('DELETE', `/api/settings/keys/${encodeURIComponent(service)}`),
  test: (service) => request('POST', '/api/settings/test', { json: { service } }),
  storage: () => request('GET', '/api/settings/storage'),
  clearData: (confirm) =>
    request('POST', '/api/settings/clear-data', { json: { confirm } }),
};
