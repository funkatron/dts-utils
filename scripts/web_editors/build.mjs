#!/usr/bin/env node
/**
 * Rebuild the offline editors bundle served at /static/config_editor.mjs
 *
 *   node scripts/web_editors/build.mjs
 *
 * From this directory: npm install && node build.mjs
 */
import * as esbuild from "esbuild";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../..");
const outfile = path.join(root, "src/dts_utils/web/static/config_editor.mjs");

await esbuild.build({
  entryPoints: [path.join(here, "src/index.js")],
  bundle: true,
  format: "esm",
  outfile,
  platform: "browser",
  target: ["es2020"],
  minify: true,
  legalComments: "none",
  banner: {
    js: "/* Vendored CodeMirror 6 bundle (offline). Rebuild: node scripts/web_editors/build.mjs */",
  },
});

console.log("Wrote", outfile);
