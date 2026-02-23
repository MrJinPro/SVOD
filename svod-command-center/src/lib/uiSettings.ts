export const SETTINGS_KEY = 'svod_settings_v1';

export type UiSettings = {
  apiUrl: string;
  apiTimeoutSec: number;
  pushEnabled: boolean;
  soundEnabled: boolean;
  emailEnabled: boolean;
  sessionTimeoutMin: number;
  autoLogout: boolean;
  refreshIntervalSec: number;
  autoRefresh: boolean;

  // Reports: shift boundaries (HH:MM)
  shiftDayStart: string;
  shiftNightStart: string;
};

export const defaultUiSettings: UiSettings = {
  apiUrl: 'http://localhost:8000/api/v1',
  apiTimeoutSec: 30,
  pushEnabled: true,
  soundEnabled: true,
  emailEnabled: false,
  sessionTimeoutMin: 60,
  autoLogout: true,
  refreshIntervalSec: 30,
  autoRefresh: true,

  shiftDayStart: '08:00',
  shiftNightStart: '20:00',
};

export function loadUiSettings(): UiSettings {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return defaultUiSettings;
    const parsed = JSON.parse(raw) as Partial<UiSettings>;
    return { ...defaultUiSettings, ...parsed };
  } catch {
    return defaultUiSettings;
  }
}

export function saveUiSettings(settings: UiSettings) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}
