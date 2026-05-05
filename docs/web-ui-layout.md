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
│  [ textarea…………………………… ] [Runs▾| hammer / stop]            │
│                                      #elapsed               │
└─────────────────────────────────────────────────────────┘

Setup → modal dialog #toolsDialog:
  Connection row, status line, profile, advanced <details>, CLI footer

History → modal dialog #historyDialog (#historyList, Clear all / Close):
  Recent PNG generations (server-side web history); Reuse restores the prompt
  to the composer; per-image download links remain available
```

---

## Interactive mock (Cursor Canvas)

The repo canvas [`design/dts-util-web-humane-layout.canvas.tsx`](design/dts-util-web-humane-layout.canvas.tsx) is the **interactive mock** (Cursor Canvas): same structure as the shipped template ([`index.html.j2`](../src/dts_util/web/templates/index.html.j2)) — stage-first viewport, Setup + History FABs, footer composer (**Prompt** + `.split-run-gen`: `#generations` 1–25, hammer `#btnGen` / stop `#btnStop` when busy, stretched to match `#prompt` height; **`#elapsed`** on the row below, right-aligned). Collapsible sections for **toolsDialog** / **historyDialog**. Use the pills to preview idle / generating / done / error.

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
| Composer | `#prompt` + `.split-run-gen` (`#generations`, `#btnGen`, **`#btnStop`** replaces Generate while busy) — split stretches to textarea height; `#elapsed` below. Shortcut hint above |
| Errors | `#err` (`role="alert"`), thin strip above composer |
| Setup dialog | `#toolsDialog` — `host`, `port`, `noTls`, `trustCert`, `btnCheck`, `statusLine`, `profile`, `profileCustom`, advanced fields, `btnCloseSetup` |
| History dialog | `#historyDialog` — `#historyList`, row-level Reuse buttons, `#historyStatus`, `#btnClearHistory`, `#btnCloseHistory` |

## History storage

History is stored by the web server under `web-history` in the dts-util user config directory. Set `DTS_WEB_HISTORY_DIR` to override that location. The browser imports legacy `localStorage` entries from `dts_web_gen_history_v1` the first time History opens, then clears that old browser-only key. Server entries include prompt metadata plus PNG filenames exposed through `/history/{item_id}/{filename}`. Reuse restores optional fields only when the current composer values are still clean (`#neg` blank and `#generations` still `1`).

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
