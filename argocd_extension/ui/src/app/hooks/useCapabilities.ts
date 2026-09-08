import { apiJson } from "../../api/client";
import { getHost } from "../../host/registry";

export type Capabilities = {
  canWrite: boolean;
  username: string;
  loaded: boolean;
};

export function useCapabilities(): Capabilities {
  const standalone = getHost().tokenField;
  const [canWrite, setCanWrite] = React.useState(standalone);
  const [username, setUsername] = React.useState("");
  const [loaded, setLoaded] = React.useState(standalone);

  React.useEffect(() => {
    if (standalone) return;
    let cancelled = false;
    void apiJson("/capabilities")
      .then((body: any) => {
        if (cancelled) return;
        setCanWrite(!!body?.canWrite);
        setUsername(typeof body?.username === "string" ? body.username : "");
        setLoaded(true);
      })
      .catch(() => {
        if (cancelled) return;
        setCanWrite(false);
        setUsername("");
        setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [standalone]);

  return { canWrite, username, loaded };
}
