export type UserPreferences = {
  adminMode: boolean;
  autoRefresh: boolean;
  autoRefreshIntervalMs: number;
};

export const DEFAULT_USER_PREFERENCES: UserPreferences = {
  adminMode: false,
  autoRefresh: true,
  autoRefreshIntervalMs: 5000,
};

export const USER_PREFERENCES_STORAGE_KEY = "pde_operator_ui_prefs";

const MIN_AUTO_REFRESH_INTERVAL_MS = 1000;
const MAX_AUTO_REFRESH_INTERVAL_MS = 300_000;

export function normalizeUserPreferences(raw: Partial<UserPreferences> | null | undefined): UserPreferences {
  const interval = Number(raw?.autoRefreshIntervalMs ?? DEFAULT_USER_PREFERENCES.autoRefreshIntervalMs);
  return {
    adminMode: !!raw?.adminMode,
    autoRefresh: raw?.autoRefresh ?? DEFAULT_USER_PREFERENCES.autoRefresh,
    autoRefreshIntervalMs: Number.isFinite(interval)
      ? Math.min(MAX_AUTO_REFRESH_INTERVAL_MS, Math.max(MIN_AUTO_REFRESH_INTERVAL_MS, Math.round(interval)))
      : DEFAULT_USER_PREFERENCES.autoRefreshIntervalMs,
  };
}

export function loadUserPreferences(): UserPreferences {
  try {
    const raw = localStorage.getItem(USER_PREFERENCES_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_USER_PREFERENCES };
    return normalizeUserPreferences(JSON.parse(raw) as Partial<UserPreferences>);
  } catch {
    return { ...DEFAULT_USER_PREFERENCES };
  }
}

export function saveUserPreferences(prefs: UserPreferences): void {
  try {
    localStorage.setItem(USER_PREFERENCES_STORAGE_KEY, JSON.stringify(normalizeUserPreferences(prefs)));
  } catch {
    // ignore quota / private mode
  }
}

export function clearUserPreferencesStorage(): void {
  try {
    localStorage.removeItem(USER_PREFERENCES_STORAGE_KEY);
  } catch {
    // ignore
  }
}
