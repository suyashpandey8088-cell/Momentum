export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; this.name = 'ApiError'; }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('X-Momentum-Client', 'web');
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  let response: Response;
  try { response = await fetch(`/api${path}`, { ...options, headers, credentials: 'same-origin', cache: 'no-store' }); }
  catch { throw new ApiError('The server is unreachable. Check your connection and try again.', 0); }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const message = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((item: { msg: string }) => item.msg.replace('Value error, ', '')).join(' ') : 'Something went wrong. Please try again.';
    throw new ApiError(message, response.status);
  }
  return data as T;
}
export const post = <T>(path: string, body?: unknown) => api<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });
export const patch = <T>(path: string, body: unknown) => api<T>(path, { method: 'PATCH', body: JSON.stringify(body) });
export const remove = <T>(path: string) => api<T>(path, { method: 'DELETE' });
