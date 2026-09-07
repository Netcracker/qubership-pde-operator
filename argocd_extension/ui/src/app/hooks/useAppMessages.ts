export function useAppMessages() {
  const [error, setError] = React.useState("");
  const [flash, setFlash] = React.useState("");
  return {
    error,
    flash,
    setError,
    setFlash,
    clearError: React.useCallback(() => setError(""), []),
    clearFlash: React.useCallback(() => setFlash(""), []),
  };
}

export type AppMessages = ReturnType<typeof useAppMessages>;
