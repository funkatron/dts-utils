# Web editors (CodeMirror 6)

Source for the offline ESM bundle served as `/static/config_editor.mjs`.

Exports:

- `mountConfigJsonEditor` — Edit profile JSON dialog
- `mountPromptEditor` — Composer prompt (wildcard highlight, brace close/wrap)

## Rebuild

```bash
cd scripts/web_editors
npm install
node build.mjs
```

Or from the repo root:

```bash
node scripts/web_editors/build.mjs
```

Commit the regenerated `src/dts_utils/web/static/config_editor.mjs` with source changes.
