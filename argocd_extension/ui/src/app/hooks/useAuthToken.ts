import { getHost } from "../../host/registry";

export function useAuthToken() {
  const host = React.useMemo(() => getHost(), []);
  const [apiToken, setApiToken] = React.useState(host.getToken());

  const saveToken = React.useCallback(
    (value: string) => {
      setApiToken(value);
      host.setToken(value);
    },
    [host],
  );

  return { host, apiToken, saveToken };
}
