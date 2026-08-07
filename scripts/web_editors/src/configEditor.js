import { basicSetup } from "codemirror";
import { EditorView, keymap } from "@codemirror/view";
import { EditorState } from "@codemirror/state";
import { json } from "@codemirror/lang-json";
import { oneDark } from "@codemirror/theme-one-dark";

/**
 * Mount a JSON CodeMirror editor into parent.
 * @returns {{ getText, setText, focus, destroy }}
 */
export function mountConfigJsonEditor(parent, opts = {}) {
  const doc = typeof opts.doc === "string" ? opts.doc : "";
  const onChange = opts.onChange;
  const onSave = opts.onSave;
  parent.replaceChildren();

  const extensions = [
    basicSetup,
    json(),
    oneDark,
    EditorView.updateListener.of((update) => {
      if (update.docChanged && typeof onChange === "function") {
        onChange(update.state.doc.toString());
      }
    }),
    keymap.of([
      {
        key: "Mod-s",
        run: () => {
          if (typeof onSave === "function") {
            onSave();
          }
          return true;
        },
      },
    ]),
    EditorView.theme({
      "&": { height: "100%", fontSize: "0.78rem" },
      ".cm-scroller": {
        overflow: "auto",
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
      },
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
    destroy() {
      view.destroy();
    },
  };
}
