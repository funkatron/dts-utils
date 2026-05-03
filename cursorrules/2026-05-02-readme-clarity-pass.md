# 2026-05-02 — README clarity pass

## Trigger

User said: "we need to really make the README.md helpful to the user. I think it's hard to follow."

## Diagnosis

The README had drifted into a hard-to-scan state for six concrete reasons:

1. Most flags, paths, and terms were wrapped in `**bold**`, so nothing visually stood out.
2. "How to use it" appeared before "Installation"; "Requirements" was buried inside it.
3. The first quickstart was followed immediately by a TLS scare paragraph.
4. `--configuration` resolution rules were repeated in three places.
5. A "Reading map" table mapped section names to section names.
6. Internal-style scanability formatting (heavy bolding, inline cross-references) leaked into a user-facing doc, against the workspace `three-lens-external-docs` rule.

## What changed

- Rewrote `README.md` end to end. New top-to-bottom flow:
  What it is → Requirements → Install → Quickstart → Configuration files → TLS → Server lifecycle → Remote/existing servers → Generation tasks → Model inspector → Troubleshooting → Repo layout → Related docs → Development → License → Contributing.
- Removed every `**bold**` from the body. Kept code spans for flags, paths, command names.
- One canonical home per topic. `--configuration` rules live only in **Configuration files**; TLS flag selection lives only in **TLS**.
- Quickstart is now three commands followed by a numbered list of "what each step does", and a one-line pointer to the remote-server section for users whose setup is different.
- Dropped the "Reading map" table, the duplicate "Installation" section, the "Behind the scenes" implementation paragraph (already in the gRPC API notes doc), and the Python helper snippet that did not actually demonstrate anything (`pass` in a `with` block).
- Line count went from 293 to 237.

## What was preserved verbatim (just relocated)

- TLS flag selection table.
- `--configuration` resolution table.
- Server lifecycle command table.
- Troubleshooting symptom table.
- Model inspector output paths table.

## Skills updated

- Created `~/.cursor/skills/FUNK-readme-clarity-pass/SKILL.md` capturing the page-level pattern: read order, bold rules, dedup rule, quickstart contract, section budget (~150–300 lines), and the anti-patterns table.
- Cross-linked from `FUNK-cli-docs-task-first/SKILL.md` and `FUNK-documentation-prose/SKILL.md` so the three layer cleanly:
  - `FUNK-readme-clarity-pass` — page-level structure.
  - `FUNK-cli-docs-task-first` — per-command section template inside reference sections.
  - `FUNK-documentation-prose` — voice and tone.

## Verification

- `ReadLints` clean.
- All internal anchor links resolve (`#tls`, `#remote-or-existing-servers`).
- `rg '\*\*'` against the body returns no matches.

## Not done

- No commit yet — pending user review.
- No push.
