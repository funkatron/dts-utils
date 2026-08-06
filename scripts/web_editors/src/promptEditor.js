import {
  EditorView,
  keymap,
  placeholder as cmPlaceholder,
  drawSelection,
  highlightActiveLine,
} from "@codemirror/view";
import { EditorState } from "@codemirror/state";
import {
  defaultKeymap,
  history,
  historyKeymap,
  insertNewlineAndIndent,
} from "@codemirror/commands";
import {
  closeBrackets,
  closeBracketsKeymap,
} from "@codemirror/autocomplete";
import { bracketMatching } from "@codemirror/language";
import { wildcardHighlight, countTopLevelBraceGroups } from "./wildcardHighlight.js";

const promptTheme = EditorView.theme({
  "&": {
    height: "100%",
    fontSize: "0.88rem",
    backgroundColor: "transparent",
  },
  "&.cm-focused": {
    outline: "none",
  },
  ".cm-scroller": {
    overflow: "auto",
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
    lineHeight: "1.35",
  },
  ".cm-content": {
    padding: "0.5rem 0.6rem",
    caretColor: "var(--accent, #4a9eff)",
  },
  ".cm-line": {
    padding: "0",
  },
  ".cm-cursor, .cm-dropCursor": {
    borderLeftColor: "var(--accent, #4a9eff)",
  },
  "&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection":
    {
      backgroundColor: "rgba(74, 158, 255, 0.28)",
    },
  ".cm-dts-wildcard": {
    color: "#2AA198",
    backgroundColor: "rgba(42, 161, 152, 0.12)",
    borderRadius: "2px",
  },
  ".cm-dts-wildcard-sep": {
    color: "#CB4B16",
    backgroundColor: "rgba(203, 75, 22, 0.22)",
    borderRadius: "3px",
    padding: "0 0.18em",
    margin: "0 0.05em",
    fontWeight: "700",
    boxShadow: "inset 0 0 0 1px rgba(203, 75, 22, 0.35)",
  },
});

/**
 * Close-bracket behavior for `{` / `}` (default ON):
 * - empty caret: `{` inserts `{}` with cursor between
 * - non-empty selection: `{` wraps as `{selected}`
 * - `}` skips an existing close when appropriate (via closeBrackets)
 */
const promptCloseBrackets = closeBrackets();

/**
 * Mount a prompt CodeMirror editor (Raskin-style / Aza: focus expands chrome; content always legible).
 * @returns {{ getText, setText, focus, blur, destroy, setFocusedChrome, countBraceGroups }}
 */
export function mountPromptEditor(parent, opts = {}) {
  const doc = typeof opts.doc === "string" ? opts.doc : "";
  const onChange = opts.onChange;
  const onGenerate = opts.onGenerate;
  const onFocusChange = opts.onFocusChange;
  parent.replaceChildren();

  let focusedChrome = false;

  const extensions = [
    history(),
    drawSelection(),
    highlightActiveLine(),
    bracketMatching(),
    promptCloseBrackets,
    EditorState.allowMultipleSelections.of(true),
    EditorView.lineWrapping,
    wildcardHighlight,
    cmPlaceholder(typeof opts.placeholder === "string" ? opts.placeholder : ""),
    keymap.of([
      ...closeBracketsKeymap,
      {
        key: "Mod-Enter",
        run: () => {
          if (typeof onGenerate === "function") {
            onGenerate();
          }
          return true;
        },
      },
      {
        key: "Escape",
        run: (view) => {
          view.contentDOM.blur();
          return true;
        },
      },
      {
        key: "Enter",
        run: insertNewlineAndIndent,
      },
      ...defaultKeymap,
      ...historyKeymap,
    ]),
    EditorView.updateListener.of((update) => {
      if (update.docChanged && typeof onChange === "function") {
        onChange(update.state.doc.toString());
      }
    }),
    EditorView.domEventHandlers({
      focus: () => {
        focusedChrome = true;
        if (typeof onFocusChange === "function") {
          onFocusChange(true);
        }
        return false;
      },
      blur: () => {
        focusedChrome = false;
        if (typeof onFocusChange === "function") {
          onFocusChange(false);
        }
        return false;
      },
    }),
    promptTheme,
    EditorView.contentAttributes.of({
      "aria-label": "Prompt",
    }),
  ];

  const view = new EditorView({
    state: EditorState.create({ doc, extensions }),
    parent,
  });

  return {
    getText() {
      return view.state.doc.toString();
    },
    setText(text) {
      const next = typeof text === "string" ? text : "";
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: next },
      });
    },
    focus() {
      view.focus();
    },
    blur() {
      view.contentDOM.blur();
    },
    destroy() {
      view.destroy();
    },
    setFocusedChrome(on) {
      focusedChrome = !!on;
      return focusedChrome;
    },
    countBraceGroups() {
      return countTopLevelBraceGroups(view.state.doc.toString());
    },
  };
}
