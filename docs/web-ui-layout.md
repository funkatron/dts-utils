# `dts-util web` UI layout (humane / Raskin)

This document is the **human-readable layout contract** for the loopback web UI. The shipped page is [`src/dts_util/web/templates/index.html.j2`](../src/dts_util/web/templates/index.html.j2).

**Principles:** The **image stage** uses almost all viewport space. **Prompt + Generate** sit in a fixed **composer** strip at the bottom. Everything else (gRPC host/port/TLS, listener check, profile, advanced fields, docs links) lives behind **Setup**, which opens a modal `<dialog>`.

---

## Wireframe (top → bottom)

```
┌─────────────────────────────────────────────────────────┐
│  dts-util web                           [ Setup ]        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│                                                         │
│              IMAGE STAGE (#stage / #resultPane)          │
│         (placeholder | spinner | large img + DL)         │
│                  flex-grow, max img height ~viewport       │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  (optional error strip #err)                             │
├─────────────────────────────────────────────────────────┤
│  Prompt [ textarea……………………………………… ]  [ Generate ]        │
│                                       elapsed            │
└─────────────────────────────────────────────────────────┘

Setup → modal dialog #toolsDialog:
  Connection row, status line, profile, advanced <details>, CLI footer
```

---

## Interactive mock (Cursor Canvas)

The repo canvas [`design/dts-util-web-humane-layout.canvas.tsx`](design/dts-util-web-humane-layout.canvas.tsx) shows an **older stacked layout** (connection above prompt). The **shipped** UI is **stage + composer + Setup dialog** as in the wireframe above.

Cursor can still render the canvas for experimentation:

1. **Command Palette** (`Cmd+Shift+P` / `Ctrl+Shift+P`) → run **Open Canvas** → pick **`dts-util-web-humane-layout`** if listed.

2. Or open the IDE canvases path:

   `~/.cursor/projects/Users-coj-alt-sync-src-dts-utils/canvases/dts-util-web-humane-layout.canvas.tsx`

3. **Same file in-repo** (for diff/review): [`design/dts-util-web-humane-layout.canvas.tsx`](design/dts-util-web-humane-layout.canvas.tsx)

---

## DOM regions → IDs

| Region | Element IDs / notes |
|--------|---------------------|
| Top bar | `.app-mark`, `btnOpenSetup` (opens dialog) |
| Image stage | `#stage`, `#resultPane`, `resultPlaceholder`, `resultBusy`, `results` |
| Composer | `#prompt`, `#btnGen`, `#elapsed` |
| Errors | `#err` (`role="alert"`), thin strip above composer |
| Setup dialog | `#toolsDialog` — `host`, `port`, `noTls`, `trustCert`, `btnCheck`, `statusLine`, `profile`, `profileCustom`, advanced fields, `btnCloseSetup` |

---

## Status copy (listener probe)

| Situation | Line shown |
|-----------|------------|
| In flight | `Checking…` |
| Token missing | `Unauthorized — set DTS_WEB_TOKEN and reload.` |
| Reachable | `Listener OK — …` |
| Not reachable | `Unreachable — …` |

Probe success **does not** guarantee generation succeeds (config, `flatc`, model, TLS).

---

## Related

- Product intent: humane single-screen plan (Raskin-style) — internal planning doc if present on your machine: `.cursor/plans/humane_web_ui_50e7e05c.plan.md`
- Flags and security: [CLI.md § web](../CLI.md#web-dts-util-web)
