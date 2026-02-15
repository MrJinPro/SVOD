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

function handleUnauthorized() {
  try {
    localStorage.removeItem('svod_access_token');
  } catch {
    // ignore
  }

  // Force navigation even if the app is currently on a protected route.
  if (typeof window !== 'undefined') {
    try {
      window.location.assign('/login');
    } catch {
      // ignore
    }
  }
}

export function getAuthToken(): string | undefined {
  // Prefer runtime token from login; fallback to build-time token.
  try {
    const stored = localStorage.getItem('svod_access_token');
    if (stored && stored.trim()) return stored;
  } catch {
    // ignore
  }
  return API_TOKEN;
}

async function safeFetch(url: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch {
    // Browser throws TypeError("Failed to fetch") on network/CORS/mixed-content.
    // Include URL to simplify debugging in the UI.
    throw new Error(`Failed to fetch: ${url}`);
  }
}

export async function apiFetchRaw(path: string, init?: RequestInit): Promise<Response> {
  const url = `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;
  const token = getAuthToken();
  const res = await safeFetch(url, {
    ...init,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  });

  if (res.status === 401) {
    handleUnauthorized();
  }

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

  return res;
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;
  const token = getAuthToken();
  const res = await safeFetch(url, {
    ...init,
    headers: {
      // Do NOT set Content-Type for GET. It triggers CORS preflight and is unnecessary.
      'Accept': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  });

  if (res.status === 401) {
    handleUnauthorized();
  }

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
  const res = await safeFetch(url, {
    method: 'POST',
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (res.status === 401) {
    handleUnauthorized();
  }

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
  const res = await safeFetch(url, {
    method: 'PATCH',
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (res.status === 401) {
    handleUnauthorized();
  }

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
  const res = await safeFetch(url, {
    method: 'DELETE',
    ...init,
    headers: {
      'Accept': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  });

  if (res.status === 401) {
    handleUnauthorized();
  }

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
