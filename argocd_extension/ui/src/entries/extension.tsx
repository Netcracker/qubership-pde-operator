import "../host/bootstrap-argo";
import { PdeExtensionApp } from "../app/App";
import mainCss from "../styles.css";
import pvCss from "../components/pipeline-viewer/styles.css";
import xyflowCss from "@xyflow/react/dist/style.css";
import { EXT_ICON, EXT_PATH, EXT_TITLE } from "../lib/constants";

const css = [mainCss, pvCss, xyflowCss].join("\n");

const REGISTER_TIMEOUT_MS = 15_000;

let registered = false;

function injectStyles() {
  if (document.getElementById("pde-argo-extension-styles")) return;
  const el = document.createElement("style");
  el.id = "pde-argo-extension-styles";
  el.textContent = css;
  document.head.appendChild(el);
}

function extensionsApiReady(): boolean {
  return typeof (window as any).extensionsAPI?.registerSystemLevelExtension === "function";
}

/** App attaches the systemLevel listener in its constructor (before first paint into #app). */
function argoAppMounted(): boolean {
  const root = document.getElementById("app");
  return !!root && root.childElementCount > 0;
}

function registerOnce(): boolean {
  if (registered) return true;
  if (!extensionsApiReady() || !argoAppMounted()) return false;
  (window as any).extensionsAPI.registerSystemLevelExtension(PdeExtensionApp, EXT_TITLE, EXT_PATH, EXT_ICON);
  registered = true;
  console.info("[pde-argo-extension] registered system-level extension", EXT_PATH);
  return true;
}

function scheduleRegistration() {
  const started = Date.now();
  let observer: MutationObserver | null = null;

  const stop = () => {
    observer?.disconnect();
    observer = null;
  };

  const tryRegister = () => {
    if (registerOnce()) {
      stop();
      return true;
    }
    if (Date.now() - started > REGISTER_TIMEOUT_MS) {
      console.error(
        "[pde-argo-extension] failed to register within 15s;",
        "api=",
        extensionsApiReady(),
        "appMounted=",
        argoAppMounted(),
      );
      stop();
      return true;
    }
    return false;
  };

  if (tryRegister()) return;

  const timer = window.setInterval(() => {
    if (tryRegister()) window.clearInterval(timer);
  }, 50);

  observer = new MutationObserver(() => tryRegister());
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.setTimeout(() => observer?.disconnect(), REGISTER_TIMEOUT_MS);
}

injectStyles();
scheduleRegistration();
