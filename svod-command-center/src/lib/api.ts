function getDefaultApiBaseUrl(): string {
  // Dev-friendly default: same host as the UI, API on port 8000.
  // This prevents "localhost" from being used when UI is opened over LAN.
  if (typeof window !== 'undefined' && window.location?.hostname) {
    return `${window.location.protocol}//${window.location.hostname}:8000/api/v1`;
  }

  return 'http://localhost:8000/api/v1';
}

export const API_BASE_URL: string = (import.meta as any).env?.VITE_API_BASE_URL || getDefaultApiBaseUrl();
const API_TOKEN: string | undefined = (import.meta as any).env?.VITE_API_TOKEN;

function getAuthToken(): string | undefined {
  // Prefer runtime token from login; fallback to build-time token.
  try {
    const stored = localStorage.getItem('svod_access_token');
    if (stored && stored.trim()) return stored;
  } catch {
    // ignore
  }
  return API_TOKEN;
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;
  const token = getAuthToken();
  const res = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  });

  if (!res.ok) {
    let body: any = null;
    try {
      body = await res.json();
    } catch {
      // ignore
    }
    const message = body?.message || body?.detail?.message || res.statusText;
    throw new Error(message);
  }

  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body?: unknown, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;
  const token = getAuthToken();
  const res = await fetch(url, {
    method: 'POST',
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!res.ok) {
    let body: any = null;
    try {
      body = await res.json();
    } catch {
      // ignore
    }
    const message = body?.message || body?.detail?.message || res.statusText;
    throw new Error(message);
  }

  return (await res.json()) as T;
}

export async function apiPatch<T>(path: string, body?: unknown, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;
  const token = getAuthToken();
  const res = await fetch(url, {
    method: 'PATCH',
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!res.ok) {
    let body: any = null;
    try {
      body = await res.json();
    } catch {
      // ignore
    }
    const message = body?.message || body?.detail?.message || res.statusText;
    throw new Error(message);
  }

  return (await res.json()) as T;
}

export async function apiDelete<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;
  const token = getAuthToken();
  const res = await fetch(url, {
    method: 'DELETE',
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  });

  if (!res.ok) {
    let body: any = null;
    try {
      body = await res.json();
    } catch {
      // ignore
    }
    const message = body?.message || body?.detail?.message || res.statusText;
    throw new Error(message);
  }

  // Some DELETE endpoints may return empty body
  const text = await res.text();
  if (!text) return {} as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    return {} as T;
  }
}
