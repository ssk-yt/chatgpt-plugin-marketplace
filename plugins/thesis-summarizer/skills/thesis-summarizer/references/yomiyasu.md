# Yomiyasu editorial pass

Use the bundled copy of [nanaism/yomiyasu](../vendor/yomiyasu/SKILL.md) to make
the Japanese explainer easier to read. The upstream project is MIT-licensed;
its license and Unicode notice are preserved in the vendored directory.

## Default pass

Apply these constraints to `work/content.md` after the complete draft exists
and before `pdfx build`:

- Preserve every claim, emphasis, degree of certainty, tense, technical term,
  symbol definition, number, citation, and proper name.
- Make subjects, predicates, modifiers, conditions, contrasts, and logical
  connections easy to follow. Replace vague metaphorical wording only when a
  more literal expression preserves the same meaning.
- Remove empty preview sentences, repeated conclusions, needless decoration,
  and formulaic sales copy only when they carry no scientific meaning.
- Keep naturally readable prose unchanged. Do not optimize wording merely to
  reduce linter counts.
- Return body text only. Do not insert yomiyasu's conversational sections such
  as `変えたところ` or `書き手に確かめたい点` into the explainer.

The source-link grammar has priority over prose editing:

- Do not change source IDs or the `{{source-id|visible text}}` wrapper.
- Do not move words across source-link boundaries or merge adjacent links.
- Do not change `:::...` blocks, `@crop` directives, headings, code, inline
  math delimiters, display-math lines, or TeX commands while editing prose.
- If a more natural rewrite would no longer be supported by the same exact PDF
  location, keep the original wording or split it into separately supported
  atomic claims using unused source IDs.

## Static check

Run the vendored linter with the same Python interpreter used for `pdfx`:

```text
<PY> <SKILL_DIR>/vendor/yomiyasu/scripts/yomiyasu_lint.py work/content.md --json
```

Review each finding in context. A warning is not a build failure and must not
override scientific accuracy, the one-to-one source-link invariant, or the
author's intended strength of claim. After any edits, run `pdfx build` and
`pdfx verify` as usual.

## Full upstream guidance

The complete upstream `SKILL.md`, references, and scripts are bundled under
`vendor/yomiyasu/`. Read the complete upstream skill only when the user asks
for a full yomiyasu rewrite or the compact pass cannot resolve a prose-quality
problem. Normal Thesis Summarizer runs use the compact rules above plus the
linter so they do not spend tokens loading the much larger upstream manual.
