#!/usr/bin/env python3
"""Vendor the latest released yomiyasu skill into Thesis Summarizer.

The script copies data only; it never imports or executes upstream Python.
Pass --source for an already checked-out release, or let it clone the latest
GitHub release into a temporary directory.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = (
    ROOT
    / "plugins"
    / "thesis-summarizer"
    / "skills"
    / "thesis-summarizer"
    / "vendor"
    / "yomiyasu"
)
REPOSITORY = "https://github.com/nanaism/yomiyasu"
REQUIRED = ("SKILL.md", "LICENSE", "UNICODE-LICENSE.txt", "references", "scripts")
VERSIONED_FILES = (
    ROOT / "plugins" / "thesis-summarizer" / ".codex-plugin" / "plugin.json",
    ROOT / "plugins" / "thesis-summarizer" / ".claude-plugin" / "plugin.json",
)
PDFX_VERSION = (
    ROOT
    / "plugins"
    / "thesis-summarizer"
    / "skills"
    / "thesis-summarizer"
    / "scripts"
    / "pdfx"
    / "__init__.py"
)
PDFX_VERSION_TEST = (
    ROOT
    / "plugins"
    / "thesis-summarizer"
    / "skills"
    / "thesis-summarizer"
    / "scripts"
    / "tests"
    / "test_math_and_links.py"
)


def run(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def latest_tag() -> str:
    request = urllib.request.Request(
        "https://api.github.com/repos/nanaism/yomiyasu/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "sskyt-sync"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    return str(payload["tag_name"])


def validate_source(source: Path) -> None:
    missing = [name for name in REQUIRED if not (source / name).exists()]
    if missing:
        raise SystemExit("Upstream skill is incomplete: " + ", ".join(missing))


def installed_commit() -> str | None:
    metadata_path = DESTINATION / "UPSTREAM.json"
    if not metadata_path.exists():
        return None
    try:
        return str(json.loads(metadata_path.read_text(encoding="utf-8"))["commit"])
    except (KeyError, TypeError, json.JSONDecodeError):
        return None


def bump_plugin_patch_version() -> str:
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in VERSIONED_FILES]
    versions = {manifest.get("version") for manifest in manifests}
    if len(versions) != 1:
        raise SystemExit("Plugin manifests have different versions")
    current = versions.pop()
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", str(current))
    if not match:
        raise SystemExit(f"Unsupported plugin version: {current}")
    major, minor, patch = (int(value) for value in match.groups())
    updated = f"{major}.{minor}.{patch + 1}"
    for path, manifest in zip(VERSIONED_FILES, manifests):
        manifest["version"] = updated
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    init_source = PDFX_VERSION.read_text(encoding="utf-8")
    init_source, replacements = re.subn(
        r'__version__\s*=\s*"[^"]+"',
        f'__version__ = "{updated}"',
        init_source,
        count=1,
    )
    if replacements != 1:
        raise SystemExit("Could not update pdfx version")
    PDFX_VERSION.write_text(init_source, encoding="utf-8")

    test_source = PDFX_VERSION_TEST.read_text(encoding="utf-8")
    test_source, replacements = re.subn(
        r'pdfx \d+\.\d+\.\d+', f"pdfx {updated}", test_source, count=1
    )
    if replacements != 1:
        raise SystemExit("Could not update pdfx version test")
    PDFX_VERSION_TEST.write_text(test_source, encoding="utf-8")
    return updated


def copy_skill(source: Path, tag: str, commit: str) -> None:
    validate_source(source)
    previous_commit = installed_commit()
    if previous_commit == commit:
        return
    parent = DESTINATION.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="yomiyasu-", dir=parent))
    try:
        for name in REQUIRED:
            item = source / name
            target = staging / name
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)
        assets = source / "assets"
        if assets.is_dir():
            shutil.copytree(assets, staging / "assets")
        metadata = {
            "repository": REPOSITORY,
            "release": tag,
            "commit": commit,
            "update_policy": "Synced by .github/workflows/sync-yomiyasu.yml",
        }
        (staging / "UPSTREAM.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        backup = DESTINATION.with_name(DESTINATION.name + ".previous")
        if backup.exists():
            shutil.rmtree(backup)
        if previous_commit is not None:
            bump_plugin_patch_version()
        if DESTINATION.exists():
            DESTINATION.replace(backup)
        staging.replace(DESTINATION)
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, help="Path to skills/yomiyasu")
    parser.add_argument("--tag", help="Release tag for --source")
    parser.add_argument("--commit", help="Commit SHA for --source")
    args = parser.parse_args()

    if args.source:
        source = args.source.resolve()
        tag = args.tag or "local"
        commit = args.commit or "unknown"
        copy_skill(source, tag, commit)
        return 0

    tag = latest_tag()
    with tempfile.TemporaryDirectory(prefix="yomiyasu-clone-") as temp:
        checkout = Path(temp) / "repository"
        run("git", "clone", "--depth", "1", "--branch", tag, REPOSITORY + ".git", str(checkout))
        commit = run("git", "rev-parse", "HEAD", cwd=checkout)
        copy_skill(checkout / "skills" / "yomiyasu", tag, commit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
