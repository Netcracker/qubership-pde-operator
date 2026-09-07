import {
  DEFAULT_USER_PREFERENCES,
  clearUserPreferencesStorage,
  loadUserPreferences,
  normalizeUserPreferences,
  saveUserPreferences,
  type UserPreferences,
} from "../../lib/userPreferences";

export function useUserPreferences() {
  const [preferences, setPreferences] = React.useState<UserPreferences>(() => loadUserPreferences());

  const updatePreferences = React.useCallback((patch: Partial<UserPreferences>) => {
    setPreferences((prev) => {
      const next = normalizeUserPreferences({ ...prev, ...patch });
      saveUserPreferences(next);
      return next;
    });
  }, []);

  const resetPreferences = React.useCallback(() => {
    clearUserPreferencesStorage();
    setPreferences({ ...DEFAULT_USER_PREFERENCES });
  }, []);

  return {
    preferences,
    setAdminMode: (adminMode: boolean) => updatePreferences({ adminMode }),
    setAutoRefresh: (autoRefresh: boolean) => updatePreferences({ autoRefresh }),
    setAutoRefreshIntervalMs: (autoRefreshIntervalMs: number) => updatePreferences({ autoRefreshIntervalMs }),
    resetPreferences,
  };
}

export type UserPreferencesState = ReturnType<typeof useUserPreferences>;
