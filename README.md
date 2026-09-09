# sskyt Plugins

GitHub marketplace for `sskyt` plugins. It currently contains
`thesis-summarizer`.

## Repository layout

- `.agents/plugins/marketplace.json`: marketplace catalog
- `plugins/thesis-summarizer/`: self-contained plugin package
- `scripts/validate-marketplace.sh`: local and CI validation

Generated HTML, input PDFs, screenshots, credentials, and other user data do
not belong in this repository.

## Validate locally

From the repository root:

```sh
./scripts/validate-marketplace.sh
```

Test changes with a temporary PDF and inspect the generated HTML at desktop and
mobile widths. Do not commit input PDFs or generated HTML.

## Release workflow

1. Update the plugin source and increment `.codex-plugin/plugin.json`.
2. Run `./scripts/validate-marketplace.sh` and a PDF-to-HTML smoke test.
3. Push the reviewed change to `main`.
4. Upgrade the installed plugin and verify it in a new chat.
