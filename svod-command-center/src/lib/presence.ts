import { apiPost } from '@/lib/api';

const CLIENT_ID_KEY = 'svod_presence_client_id_v1';

export function getPresenceClientId(): string {
  try {
    const existing = localStorage.getItem(CLIENT_ID_KEY);
    if (existing && existing.trim()) return existing;

    const id = typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `cid-${Date.now()}-${Math.random()}`;
    localStorage.setItem(CLIENT_ID_KEY, id);
    return id;
  } catch {
    return typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `cid-${Date.now()}-${Math.random()}`;
  }
}

export async function presencePing(computer?: string): Promise<void> {
  const clientId = getPresenceClientId();
  await apiPost('/presence/ping', {
    clientId,
    computer: computer?.trim() || undefined,
  });
}

export async function presenceEnd(reason?: string): Promise<void> {
  const clientId = getPresenceClientId();
  await apiPost('/presence/end', {
    clientId,
    reason: reason?.trim() || undefined,
  });
}
