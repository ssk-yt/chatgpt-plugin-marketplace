# sskyt Plugins

Marketplace for `sskyt` plugins. It currently contains `thesis-summarizer`.

One repository serves two ecosystems. The plugin payload — `SKILL.md`, the
bundled `pdfx` CLI, and the reference docs — is shared; only the manifests
differ.

## Repository layout

- `.agents/plugins/marketplace.json`: marketplace catalog for ChatGPT / Codex
- `.claude-plugin/marketplace.json`: marketplace catalog for Claude Code
- `plugins/thesis-summarizer/`: self-contained plugin package
  - `.codex-plugin/plugin.json`: manifest read by ChatGPT / Codex
  - `.claude-plugin/plugin.json`: manifest read by Claude Code
  - `skills/thesis-summarizer/`: the shared skill, read by both
- `scripts/sync-yomiyasu.py`: vendors the latest released yomiyasu skill
- `scripts/validate-marketplace.sh`: local and CI validation for both catalogs

Generated HTML, input PDFs, screenshots, credentials, and other user data do
not belong in this repository.

## Yomiyasu integration

Thesis Summarizer applies a compact yomiyasu editorial pass to `content.md`
and runs the upstream static linter before building the explainer. Source IDs,
evidence boundaries, equations, and authoring directives remain under the
stricter Thesis Summarizer rules.

The complete MIT-licensed upstream skill is vendored under
`skills/thesis-summarizer/vendor/yomiyasu/`. A daily GitHub Actions job checks
the latest `nanaism/yomiyasu` release and opens or updates a synchronization
pull request when it changes. Merging that reviewed PR publishes the new rules
and linter with an automatically incremented plugin patch version; no network
access is needed while generating an explainer.

## Install in Claude Code

Register the marketplace once, then install the plugin:

```sh
/plugin marketplace add ssk-yt/chatgpt-plugin-marketplace
/plugin install thesis-summarizer@sskyt-plugins
```

Both commands also work outside a session as `claude plugin marketplace add ...`
and `claude plugin install ...`.

### Updating

The Claude marketplace entry deliberately carries no `version` field, so Claude
Code tracks the resolved commit SHA. Every push to `main` is therefore a new
version, and no manifest bump is needed to publish one.

Turn on background updates once, in `/plugin` under **Marketplaces** ->
`sskyt-plugins` -> **Enable auto-update**. After that, Claude Code refreshes the
catalog and updates the installed plugin shortly after each session starts, and
prompts for `/reload-plugins` when a new version landed. Third-party
marketplaces have auto-update off by default, so this toggle is what makes
updates automatic.

To pull an update immediately instead:

```sh
/plugin marketplace update sskyt-plugins
```

## Install in ChatGPT / Codex

Unchanged. The `.agents/plugins/marketplace.json` catalog and the
`.codex-plugin/plugin.json` manifest are untouched by the Claude Code support.

## Supported platforms

The plugin runs on Linux, macOS, and Windows. `pdfx` is invoked through
`skills/thesis-summarizer/scripts/run_pdfx.py`, which puts its own directory on
`sys.path`, so no `PYTHONPATH` and no shell-specific environment prefix is
needed and one spelling works in bash, zsh, PowerShell, and cmd:

```text
<PY> "<SKILL_DIR>/scripts/run_pdfx.py" init paper.pdf -o work/
```

`<PY>` is `python3` on macOS and Linux, and `python` or `py -3` on Windows,
which ships no `python3`. Python 3.10 or newer is required.

CI runs the test suite on all three operating systems against Python 3.10 and
3.13, so a change that breaks one of them fails the build.

## Validate locally

From the repository root:

```sh
./scripts/validate-marketplace.sh
```

It checks both catalogs and fails if the two manifests drift apart in `name`,
`version`, `description`, or `skills` path. `claude plugin validate .`
additionally checks the Claude catalog against the official schema.

Run the plugin's own tests from
`plugins/thesis-summarizer/skills/thesis-summarizer/scripts`:

```sh
python -m pip install pypdfium2 pillow
PYTHONPATH=. python -m unittest discover -s tests -v
```

Test changes with a temporary PDF and inspect the generated HTML at desktop and
mobile widths. Do not commit input PDFs or generated HTML.

## Release workflow

1. Update the plugin source.
2. Increment `version` in **all three** of `.codex-plugin/plugin.json`,
   `.claude-plugin/plugin.json`, and `scripts/pdfx/__init__.py`. The validator
   rejects a mismatch between the first two.
3. Run `./scripts/validate-marketplace.sh` and a PDF-to-HTML smoke test.
4. Push the reviewed change to `main`.
5. Upgrade the installed plugin in each client and verify it in a new session.
