# dts-utils web UI layout

Layout contract for the loopback browser UI shipped by **`dts-utils web`**. Page shell: [`src/dts_utils/web/templates/index.html.j2`](../src/dts_utils/web/templates/index.html.j2); markup/CSS/JS live in [`templates/partials/`](../src/dts_utils/web/templates/partials/) (`_styles.html.j2`, `_fabs.html.j2`, `_stage.html.j2`, `_composer.html.j2`, `_dialogs.html.j2`, `_script.html.j2`). CLI flags, HTTP routes, and env vars: [CLI.md § web](../CLI.md#web-dts-utils-web).

## Contents

- [Design principles](#design-principles)
- [Screen map](#screen-map)
- [Interaction](#interaction)
- [DOM regions](#dom-regions)
- [History storage](#history-storage)
- [Listener status copy](#listener-status-copy)
- [Canvas mock](#canvas-mock)
- [See also](#see-also)

---

## Design principles

1. **Stage first** — the image/video result uses almost all viewport height.
2. **Composer fixed at bottom** — prompt, runs, and Generate/Stop stay one thumb-reach away.
3. **Progressive disclosure** — connection, TLS, secrets, and paths live in Setup (**`#toolsDialog`**); recent outputs in History (**`#historyDialog`**). Product name **`dts-utils web`** is **`.sr-only`** for tests and assistive tech.

---

## Screen map

```
┌─────────────────────────────────────────────────────────┐
│  clock                         fab-history · fab-setup │
│                                                         │
│              IMAGE STAGE (#stage / #resultPane)          │
│     placeholder | busy bar | stacked generation groups │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  #err (errors)                                           │
│  composer: mode · profile · listener · neg · prompt      │
│            [ runs ▾ | Generate / Stop ]        #elapsed   │
└─────────────────────────────────────────────────────────┘

Setup (#toolsDialog)     History (#historyDialog)
Connection + advanced    Server-side PNG list, Reuse, Clear all
```

**FABs** (fixed top-right): Setup (building icon) opens connection/advanced; History (stacked below) opens generation history. **Lightbox** (`#dtsLightbox`) overlays fullscreen when a thumbnail is opened.

---

## Interaction

| Action | Behavior |
| --- | --- |
| **Generate** | **⌘↵** (macOS) or **Ctrl+Enter** from **`#prompt`** |
| **Stop** | **`#btnStop`** while busy → **`POST /api/generate/cancel`** + abort fetch (between runs only) |
| **Output mode** | Image vs Video toggle (**`#outputModeImage`** / **`#outputModeVideo`**) — video uses pipeline profiles |
| **Profile** | Grouped **`#profile`** menu; default **`default`** (image). **`#profileCustom`** overrides when set |
| **Runs** | **`#generations`** 1–25 (image mode); hidden for single-run video pipelines |
| **Negative prompt** | Optional **`#neg`** above the main prompt |
| **Setup** | Host, port, no-TLS, trust loopback, Check listener, shared secret, cert paths, config dir, web log tail hint |
| **History** | Wide viewport-height dialog; each job has a responsive thumbnail-card grid with overlaid **i**, one Download action, and Reuse. Prompt + configuration metadata stays above its grid; **Clear all** deletes server history files |
| **Fullscreen** | Click a results or History thumbnail → **`#dtsLightbox`**. **Escape** or backdrop closes. **← / →**, side zones, swipe. In History, arrows walk **across** generation groups. **F** = Fit vs Fill |
| **Generation info** | Select a tile’s **i** button → **`#generationInfoDialog`** with original + expanded prompts, profile, run, timing, dimensions |
| **Busy state** | Compact progress bar; **Request details** opens redacted request JSON in the details dialog. Preview frames update the active result tile (loading → preview → final) |
| **Video done** | **`#videoDonePanel`** shows run folder with **Copy path** |
| **Persistence** | Last mode/profile in **`localStorage`** key **`dts_web_ui_v1`** |

Listener dot on the Setup FAB reflects the last probe (**`#statusComposerListener`** in the composer shows a short summary).

---

## DOM regions

| Region | IDs / notes |
| --- | --- |
| **Setup FAB** | **`#btnOpenSetup`** → **`#toolsDialog`** |
| **History FAB** | **`#btnOpenHistory`** → **`#historyDialog`** |
| **Stage** | **`#stage`**, **`#resultPane`**, **`#resultPlaceholder`**, **`#resultBusy`** (**`#btnRequestDetails`**), **`#videoDonePanel`**, **`#results`** (stacked **`.result-group`** batches; newest prepended; pending slots at request start; header timestamp + Request / response link when done) |
| **Composer** | **`#composerStatus`** (mode, **`#profile`**, **`#statusComposerListener`**), **`#neg`**, **`#prompt`**, **`#generations`**, **`#btnGen`**, **`#btnStop`** (replaces Generate while busy), **`#elapsed`**, **`#composerShortcutHint`** |
| **Errors** | **`#err`** (`role="alert"`) |
| **Setup dialog** | **`#host`**, **`#port`**, **`#noTls`**, **`#trustCert`**, **`#btnCheck`**, **`#statusLine`**, **`#profileCustom`**, **`#sharedSecret`**, **`#rootCert`**, **`#forceTrust`**, **`#configDir`**, **`#webLogFilePath`**, **`#btnCloseSetup`** |
| **History dialog** | **`#historyList`**, per-row Reuse, **`#historyStatus`**, **`#btnClearHistory`**, **`#btnCloseHistory`** |
| **Lightbox** | **`#dtsLightbox`**, **`#dtsLightboxImg`**, **`#dtsLightboxPrev`**, **`#dtsLightboxNext`**, **`#dtsLightboxClose`**, **`#dtsLightboxCounter`** |
| **Generation details** | **`#generationInfoDialog`**, **`#generationInfoGrid`**, **`#btnCloseGenerationInfo`** |

---

## History storage

Server writes PNGs and metadata under **`web-history/`** in the **`dts-utils`** config directory (**`dts-utils configs path`**). History is uncapped. Its **`index.json`** stores metadata only; PNGs remain separate files and are not embedded as image arrays or base64 strings. Override with **`DTS_WEB_HISTORY_DIR`**.

On first History open, the obsolete browser-only **`localStorage`** key **`dts_web_gen_history_v1`** is cleared. The browser reads artifact URLs from **`/api/history/{item_id}/artifacts`**; files are served at **`/history/{item_id}/{filename}`**.

**Reuse** restores optional fields only when the composer is still “clean” (**`#neg`** empty and **`#generations`** still **`1`**).

---

## Listener status copy

Shown in Setup (**`#statusLine`**) and summarized in the composer (**`#statusComposerListener`**).

| Situation | Copy |
| --- | --- |
| In flight | `Checking…` |
| Token missing | `Unauthorized — set DTS_WEB_TOKEN and reload.` |
| Reachable | `Listener OK — …` |
| Not reachable | `Unreachable — …` |

A successful probe does not guarantee generation (saved config, **`flatc`**, model, TLS mismatch).

---

## Canvas mock

Interactive preview for layout review: [`design/dts-util-web-humane-layout.canvas.tsx`](design/dts-util-web-humane-layout.canvas.tsx) (same regions as the shipped template). In Cursor: **Command Palette** → **Open Canvas** → **`dts-util-web-humane-layout`**, or open the file under **`design/`** in-repo. State pills preview idle, generating, done, and error.

---

## See also

| Document | Contents |
| --- | --- |
| [CLI.md § web](../CLI.md#web-dts-utils-web) | **`dts-utils web`** flags, HTTP API, env vars |
| [README.md](../README.md) | Quickstart including **`web --open`** |
| [tests/README.md](../tests/README.md) | Manual web smoke |
