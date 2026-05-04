# `dts-util web` UI layout (humane / Raskin)

This document is the **human-readable layout contract** for the loopback web UI. The shipped page is [`src/dts_util/web/templates/index.html.j2`](../src/dts_util/web/templates/index.html.j2).

**Principles:** The **image stage** uses almost all viewport space. **Prompt + Generate** sit in a fixed **composer** strip at the bottom. Everything else lives behind a **floating Setup control** (fixed top-right, building icon) that opens a modal `<dialog>`. The string `dts-util web` remains in a screen-reader-only span for tests and assistive tech.

---

## Wireframe (top → bottom)

```
┌─────────────────────────────────────────────────────────┐
│                          clock · fab-history              │
│                                          building · fab-setup │
│                                                         │
│              IMAGE STAGE (#stage / #resultPane)          │
│         (placeholder | spinner | large img + DL)         │
│                  flex-grow, max img height ~viewport       │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  (optional error strip #err)                             │
├─────────────────────────────────────────────────────────┤
│  Prompt row + shortcut hint                                │
│  [ textarea…………………………… ] [Runs▾| hammer]   ← split-run-gen │
│                                      #elapsed               │
└─────────────────────────────────────────────────────────┘

Setup → modal dialog #toolsDialog:
  Connection row, status line, profile, advanced <details>, CLI footer

History → modal dialog #historyDialog (#historyList, Clear all / Close):
  Recent PNG generations (browser localStorage only); per-image download links
```

---

## Interactive mock (Cursor Canvas)

The repo canvas [`design/dts-util-web-humane-layout.canvas.tsx`](design/dts-util-web-humane-layout.canvas.tsx) is kept **in sync with the shipped template** ([`index.html.j2`](../src/dts_util/web/templates/index.html.j2)): stage-first viewport, Setup + History FABs, footer composer (**Prompt** + `.split-run-gen`: **Runs** dropdown `#generations` 1–25, hammer **Generate** `#btnGen`; **elapsed** under the split), and collapsible sections for **toolsDialog** / **historyDialog**. Use the pills to preview idle / generating / done / error.

Cursor can render it beside the chat:

1. **Command Palette** (`Cmd+Shift+P` / `Ctrl+Shift+P`) → **Open Canvas** → **`dts-util-web-humane-layout`**.

2. Or open the IDE canvases path:

   `~/.cursor/projects/Users-coj-alt-sync-src-dts-utils/canvases/dts-util-web-humane-layout.canvas.tsx`

3. **In-repo copy** (diff/review): [`design/dts-util-web-humane-layout.canvas.tsx`](design/dts-util-web-humane-layout.canvas.tsx)

---

## DOM regions → IDs

| Region | Element IDs / notes |
|--------|---------------------|
| Top bar | _(none)_ — product name in `.sr-only` for tests / AT |
| Floating setup | `#btnOpenSetup` — fixed top-right, opens `#toolsDialog` (building icon) |
| History | `#btnOpenHistory` — stacked below setup FAB, opens `#historyDialog` |
| Image stage | `#stage`, `#resultPane`, `resultPlaceholder`, `resultBusy`, `results` |
| Composer | One row: `#prompt` textarea + `.split-run-gen` (`#generations` select 1–25, `#btnGen` hammer icon). Shortcut hint above; `#elapsed` below right |
| Errors | `#err` (`role="alert"`), thin strip above composer |
| Setup dialog | `#toolsDialog` — `host`, `port`, `noTls`, `trustCert`, `btnCheck`, `statusLine`, `profile`, `profileCustom`, advanced fields, `btnCloseSetup` |
| History dialog | `#historyDialog` — `#historyList`, `#btnClearHistory`, `#btnCloseHistory` |

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
