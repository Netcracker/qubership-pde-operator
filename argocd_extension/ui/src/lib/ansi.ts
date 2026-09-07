function escapeHtml(text: string): string {
  return text.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function xterm256(n: number): string {
  if (n < 0 || n > 255) return "";
  if (n < 16) {
    const basic = [
      [0, 0, 0],
      [205, 0, 0],
      [0, 205, 0],
      [205, 205, 0],
      [0, 0, 238],
      [205, 0, 205],
      [0, 205, 205],
      [229, 229, 229],
      [127, 127, 127],
      [255, 0, 0],
      [0, 255, 0],
      [255, 255, 0],
      [92, 92, 255],
      [255, 0, 255],
      [0, 255, 255],
      [255, 255, 255],
    ];
    const [r, g, b] = basic[n];
    return `rgb(${r},${g},${b})`;
  }
  if (n >= 232) {
    const v = 8 + (n - 232) * 10;
    return `rgb(${v},${v},${v})`;
  }
  const idx = n - 16;
  const level = (c: number) => (c === 0 ? 0 : 55 + c * 40);
  const r = level(Math.floor(idx / 36));
  const g = level(Math.floor((idx % 36) / 6));
  const b = level(idx % 6);
  return `rgb(${r},${g},${b})`;
}

function applySgr(params: number[], state: { color: string | null }): void {
  if (params.length === 0) {
    state.color = null;
    return;
  }
  let i = 0;
  while (i < params.length) {
    const code = params[i];
    if (code === 0 || code === 39) {
      state.color = null;
      i += 1;
      continue;
    }
    if (code === 38 && params[i + 1] === 5 && params[i + 2] !== undefined) {
      state.color = xterm256(params[i + 2]) || null;
      i += 3;
      continue;
    }
    i += 1;
  }
}

export function ansiToHtml(text: string): string {
  const token = /\x1b\[([0-9;]*)([A-Za-z])|\x1b./g;
  let html = "";
  let last = 0;
  let open = false;
  const state = { color: null as string | null };

  const close = () => {
    if (open) {
      html += "</span>";
      open = false;
    }
  };

  const openColor = () => {
    close();
    if (state.color) {
      html += `<span style="color:${state.color}">`;
      open = true;
    }
  };

  let match: RegExpExecArray | null;
  while ((match = token.exec(text))) {
    html += escapeHtml(text.slice(last, match.index));
    last = match.index + match[0].length;

    const finalByte = match[2];
    if (finalByte === "m") {
      const raw = match[1];
      const params = raw ? raw.split(";").map((p) => Number(p) || 0) : [0];
      const prev = state.color;
      applySgr(params, state);
      if (state.color !== prev) openColor();
    }
  }

  html += escapeHtml(text.slice(last));
  close();
  return html;
}
