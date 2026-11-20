class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function errorMessage(status, detail) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map(({ loc, msg }) => `${loc.slice(1).join('.') || 'Запрос'} — ${msg}`).join('\n');
  }
  if (status === 500) return 'Сервер не смог выполнить операцию. Попробуйте снова.';
  return `Ошибка запроса (${status})`;
}

async function request(path, { method = 'GET', body, signal, blob = false } = {}) {
  const multipart = body instanceof FormData;
  let response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      body: body === undefined || multipart ? body : JSON.stringify(body),
      headers: body === undefined || multipart ? undefined : { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      signal,
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError(0, 'Сервер недоступен. Проверьте подключение и попробуйте снова.');
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    if (response.status === 401 && !path.startsWith('/auth/')) {
      window.dispatchEvent(new Event('filemanager:session-expired'));
    }
    throw new ApiError(response.status, errorMessage(response.status, data.detail));
  }
  if (response.status === 204) return undefined;
  return blob ? response.blob() : response.json();
}

const post = (path, body) => request(path, { method: 'POST', body });

function fileBody(file) {
  const body = new FormData();
  body.set('file', file);
  return body;
}

export const api = {
  me: (signal) => request('/auth/me', { signal }),
  login: (credentials) => post('/auth/login', credentials),
  register: (credentials) => post('/auth/register', credentials),
  logout: () => post('/auth/logout'),
  directory: (id, signal) => request(id == null ? '/files/dirs' : `/files/dirs?directory_id=${id}`, { signal }),
  usage: (signal) => request('/files/usage', { signal }),
  files: (signal) => request('/files', { signal }),
  file: (id, signal) => request(`/files/${id}`, { signal }),
  history: (signal) => request('/files/operations?limit=100', { signal }),
  createDirectory: (parent_id, name) => post('/files/dirs', { parent_id, name }),
  createFile: (directory_id, filename, content) => post('/files/create', { directory_id, filename, content }),
  async upload(directoryId, file) {
    const body = fileBody(file);
    body.set('directory_id', String(directoryId));
    return post('/files/upload', body);
  },
  rename: (file_id, new_name) => request('/files/rename', { method: 'PATCH', body: { file_id, new_name } }),
  replace: (id, file) => request(`/files/content?file_id=${id}`, { method: 'PUT', body: fileBody(file) }),
  removeFile: (id) => request(`/files?file_id=${id}`, { method: 'DELETE' }),
  removeDirectory: (id, recursive) => request(`/files/dirs?directory_id=${id}&recursive=${recursive}`, { method: 'DELETE' }),
  archive: (directory_id, filename, sources) => post('/files/zip', { directory_id, filename, sources }),
  extract: (file_id, directory_id, name) => post('/files/zip/extract', { file_id, directory_id, name: name || undefined }),
  content: (id, signal) => request(`/files/${id}/download`, { signal, blob: true }),
};

export async function downloadFile(file) {
  const data = await api.content(file.id);
  const url = URL.createObjectURL(data);
  const link = document.createElement('a');
  link.href = url;
  link.download = file.filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function readDirectory(id, signal) {
  const directory = await api.directory(id, signal);
  const trail = [directory];
  let parent = directory.parent_id;
  while (parent !== null) {
    const ancestor = await api.directory(parent, signal);
    trail.unshift(ancestor);
    parent = ancestor.parent_id;
  }
  return { directory, trail };
}
