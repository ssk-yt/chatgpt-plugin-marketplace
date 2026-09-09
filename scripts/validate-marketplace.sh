#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
export REPO_ROOT

python3 - <<'PY'
import json
import os
import re
import sys
from pathlib import Path

root = Path(os.environ["REPO_ROOT"]).resolve()
marketplace_path = root / ".agents" / "plugins" / "marketplace.json"
errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing JSON file: {path.relative_to(root)}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path.relative_to(root)}: {exc}")
    return None


def inside_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(root)
        return True
    except ValueError:
        return False


marketplace = load_json(marketplace_path)
plugin_paths: list[Path] = []

if isinstance(marketplace, dict):
    if not isinstance(marketplace.get("name"), str) or not marketplace["name"]:
        fail("marketplace.name must be a non-empty string")
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        fail("marketplace.plugins must be a non-empty array")
        plugins = []

    names: set[str] = set()
    for index, entry in enumerate(plugins):
        label = f"plugins[{index}]"
        if not isinstance(entry, dict):
            fail(f"{label} must be an object")
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            fail(f"{label}.name must be a non-empty string")
            continue
        if name in names:
            fail(f"duplicate plugin name: {name}")
        names.add(name)

        plugin_id = entry.get("pluginId")
        if plugin_id is not None and (
            not isinstance(plugin_id, str)
            or not re.fullmatch(r"plugin_[A-Za-z0-9]+", plugin_id)
        ):
            fail(f"{name}: pluginId must use the official plugin_... format")

        source = entry.get("source")
        if not isinstance(source, dict) or source.get("source") != "local":
            fail(f"{name}: source.source must be 'local'")
            continue
        source_path = source.get("path")
        if not isinstance(source_path, str) or not source_path.startswith("./"):
            fail(f"{name}: source.path must be a ./ relative path")
            continue
        plugin_path = (root / source_path).resolve()
        if not inside_repo(plugin_path):
            fail(f"{name}: source.path escapes the repository")
            continue
        if not plugin_path.is_dir():
            fail(f"{name}: source.path does not exist: {source_path}")
            continue
        plugin_paths.append(plugin_path)

        if plugin_path.name != name:
            fail(f"{name}: directory name does not match marketplace name")

        manifest_path = plugin_path / ".codex-plugin" / "plugin.json"
        manifest = load_json(manifest_path)
        if not isinstance(manifest, dict):
            continue
        required = ("name", "version", "description", "author", "skills", "interface")
        for key in required:
            if key not in manifest:
                fail(f"{name}: manifest missing required key {key!r}")
        if manifest.get("name") != name:
            fail(f"{name}: manifest name does not match marketplace name")
        version = manifest.get("version")
        semver = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
        if not isinstance(version, str) or not semver.fullmatch(version):
            fail(f"{name}: manifest version is not SemVer")
        author = manifest.get("author")
        if not isinstance(author, dict) or not isinstance(author.get("name"), str) or not author["name"]:
            fail(f"{name}: manifest author.name must be a non-empty string")
        interface = manifest.get("interface")
        if not isinstance(interface, dict):
            fail(f"{name}: manifest interface must be an object")
        else:
            for key in ("displayName", "shortDescription"):
                if not isinstance(interface.get(key), str) or not interface[key]:
                    fail(f"{name}: manifest interface.{key} must be a non-empty string")

        skills_value = manifest.get("skills")
        if not isinstance(skills_value, str) or not skills_value.startswith("./"):
            fail(f"{name}: manifest skills must be a ./ relative path")
            skills_root = plugin_path / "skills"
        else:
            skills_root = (plugin_path / skills_value).resolve()
            if not inside_repo(skills_root) or not skills_root.is_dir():
                fail(f"{name}: manifest skills path is missing or unsafe")
        skill_files = sorted(skills_root.rglob("SKILL.md")) if skills_root.is_dir() else []
        if not skill_files:
            fail(f"{name}: no SKILL.md found below skills path")

        for skill_file in skill_files:
            text = skill_file.read_text(encoding="utf-8")
            match = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", text, re.DOTALL)
            if not match:
                fail(f"{skill_file.relative_to(root)}: missing YAML frontmatter")
                continue
            frontmatter = match.group(1)
            for key in ("name", "description"):
                if not re.search(rf"(?m)^{key}:\s*\S.+$", frontmatter):
                    fail(f"{skill_file.relative_to(root)}: frontmatter missing {key}")

            markdown_links = re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text)
            for raw_target in markdown_links:
                target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
                if not target or target.startswith(("#", "http://", "https://", "mailto:", "codex:")):
                    continue
                target_path = (skill_file.parent / target.split("#", 1)[0]).resolve()
                if not inside_repo(target_path) or not target_path.exists():
                    fail(f"{skill_file.relative_to(root)}: broken relative link {target!r}")

for path in root.rglob("*"):
    rel = path.relative_to(root)
    if path.is_symlink() and not inside_repo(path):
        fail(f"symlink escapes repository: {rel}")
    if path.name == ".DS_Store" or ".history" in rel.parts:
        fail(f"forbidden metadata path: {rel}")
    if path.is_file() and path.suffix.lower() in {".pdf", ".html", ".htm"}:
        fail(f"generated/input document must not be committed: {rel}")
    if path.is_file() and (
        path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}
        or path.name.startswith(("id_rsa", "id_ed25519"))
    ):
        fail(f"possible private key file: {rel}")

text_extensions = {".json", ".md", ".py", ".sh", ".css", ".js", ".yml", ".yaml", ".txt"}
secret_patterns = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
)
placeholder_patterns = (
    re.compile("plugin_" + "実際のID"),
    re.compile("plugin_" + "actual_id", re.IGNORECASE),
    re.compile(r"\[" + "TODO:" + r"[^\]]+\]"),
)
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in text_extensions:
        continue
    rel = path.relative_to(root)
    text = path.read_text(encoding="utf-8", errors="replace")
    if ("/" + "Users/") in text:
        fail(f"user-specific absolute path found: {rel}")
    for pattern in secret_patterns:
        if pattern.search(text):
            fail(f"possible secret found: {rel}")
    for pattern in placeholder_patterns:
        if pattern.search(text):
            fail(f"unresolved placeholder found: {rel}")

for plugin_path in plugin_paths:
    if (plugin_path / "mcp.json").exists() or (plugin_path / ".mcp.json").exists():
        fail(f"{plugin_path.name}: MCP manifest would make the plugin desktop-only")

if errors:
    print("Marketplace validation failed:", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    raise SystemExit(1)

print(f"Marketplace validation passed: {len(plugin_paths)} plugin(s)")
for plugin_path in plugin_paths:
    print(f"  - {plugin_path.name}")
PY
