/**
 * Brace-wildcard decorations aligned with dts_utils.prompt_wildcards nesting:
 * highlight balanced `{…}` spans; mark `|` separators only at depth >= 1.
 */
import { Decoration, ViewPlugin } from "@codemirror/view";
import { RangeSetBuilder } from "@codemirror/state";

const wildcardMark = Decoration.mark({ class: "cm-dts-wildcard" });
const sepMark = Decoration.mark({ class: "cm-dts-wildcard-sep" });

export function scanWildcardRanges(text) {
  const ranges = [];
  const n = text.length;
  let i = 0;
  while (i < n) {
    if (text[i] !== "{") {
      i += 1;
      continue;
    }
    const start = i;
    let depth = 1;
    let k = i + 1;
    while (k < n && depth > 0) {
      const c = text[k];
      if (c === "{") {
        depth += 1;
      } else if (c === "}") {
        depth -= 1;
      }
      k += 1;
    }
    if (depth !== 0) {
      break;
    }
    const end = k;
    ranges.push({ from: start, to: end, kind: "block" });
    let d = 0;
    for (let j = start; j < end; j += 1) {
      const c = text[j];
      if (c === "{") {
        d += 1;
      } else if (c === "}") {
        d -= 1;
      } else if (c === "|" && d >= 1) {
        ranges.push({ from: j, to: j + 1, kind: "sep" });
      }
    }
    i = end;
  }
  return ranges;
}

export function countTopLevelBraceGroups(text) {
  let count = 0;
  const n = text.length;
  let i = 0;
  while (i < n) {
    if (text[i] !== "{") {
      i += 1;
      continue;
    }
    let depth = 1;
    let k = i + 1;
    while (k < n && depth > 0) {
      const c = text[k];
      if (c === "{") {
        depth += 1;
      } else if (c === "}") {
        depth -= 1;
      }
      k += 1;
    }
    if (depth !== 0) {
      break;
    }
    count += 1;
    i = k;
  }
  return count;
}

function buildDecorations(view) {
  const builder = new RangeSetBuilder();
  const text = view.state.doc.toString();
  const ranges = scanWildcardRanges(text);
  ranges.sort((a, b) => {
    if (a.from !== b.from) {
      return a.from - b.from;
    }
    if (a.to !== b.to) {
      return a.to - b.to;
    }
    if (a.kind === "sep" && b.kind !== "sep") {
      return 1;
    }
    if (a.kind !== "sep" && b.kind === "sep") {
      return -1;
    }
    return 0;
  });
  for (const r of ranges) {
    if (r.kind === "block") {
      builder.add(r.from, r.to, wildcardMark);
    } else {
      builder.add(r.from, r.to, sepMark);
    }
  }
  return builder.finish();
}

export const wildcardHighlight = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.decorations = buildDecorations(view);
    }
    update(update) {
      if (update.docChanged || update.viewportChanged) {
        this.decorations = buildDecorations(update.view);
      }
    }
  },
  {
    decorations: (v) => v.decorations,
  },
);
