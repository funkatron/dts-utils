# `dts-util web` UI layout (humane / Raskin)

This document is the **human-readable design contract** for the loopback web UI. The shipped page is [`src/dts_util/web/templates/index.html.j2`](../src/dts_util/web/templates/index.html.j2). Colors and fonts differ from the Cursor Canvas mockup; **order, grouping, and visual weight** match.

---

## Wireframe (top → bottom)

```
┌─────────────────────────────────────────────────────────┐
│  dts-util web                              (small title) │
├─────────────────────────────────────────────────────────┤
│  CONNECTION (muted, smaller type)                         │
│  [ Host ] [ Port ] ☐ no-TLS  ☑ trust …  [ Check listener ] │
│  Listener OK — … (probe only hint below)                  │
├─────────────────────────────────────────────────────────┤
│  PROMPT  ← dominant heading + large textarea              │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                                                       │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  Profile                                                  │
│  [ zit           ▼ ]                                      │
│  [ Or custom name/path…                              ]    │
│                                                           │
│  ▸ Negative prompt, shared secret, paths  (collapsed)     │
│                                                           │
│  [ Generate ]     Done in …s (after success)              │
│                                                           │
│  RESULT PANE (#resultPane)                                │
│  · idle: “Generated images appear here…”                  │
│  · busy: spinner + elapsed                                 │
│  · done: images + Download links                           │
└─────────────────────────────────────────────────────────┘
```

---

## Interactive mock (Cursor Canvas)

Cursor can render a **live** layout preview with toggles for **idle / generating / done / error**:

1. **Command Palette** (`Cmd+Shift+P` / `Ctrl+Shift+P`) → run **Open Canvas** → pick **`dts-util-web-humane-layout`** if listed.

2. Or open the source the IDE expects (workspace canvases directory):

   `~/.cursor/projects/Users-coj-alt-sync-src-dts-utils/canvases/dts-util-web-humane-layout.canvas.tsx`

3. **Same file in-repo** (for diff/review without hunting that path): [`design/dts-util-web-humane-layout.canvas.tsx`](design/dts-util-web-humane-layout.canvas.tsx)

   Note: live Canvas preview is tied to Cursor’s `canvases/` folder; the repo copy is for **visibility and version control**. To refresh the interactive canvas after editing the repo copy, copy the file back into the path above or ask the agent to sync.

---

## DOM regions → IDs

| Region | Element IDs / notes |
|--------|---------------------|
| Connection toolbar | `host`, `port`, `noTls`, `trustCert`, `btnCheck` |
| Status line | `statusLine` (`aria-live="polite"`) |
| Prompt | `prompt` |
| Profile | `profile`, `profileCustom` |
| Advanced | inside `<details>`: `neg`, `sharedSecret`, `rootCert`, `forceTrust`, `configDir` |
| Generate | `btnGen`, `elapsed` |
| Errors | `err` (`role="alert"`) |
| Result pane | `resultPane`, `resultPlaceholder`, `resultBusy`, `busyElapsed`, `results` |

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
