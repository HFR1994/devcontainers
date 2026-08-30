#!/usr/bin/env python3
"""Compute which images need (re)building and in what order.

Reads a `build.json` manifest from each top-level image folder:

    {
      "name": "python",          # published image -> ghcr.io/<owner>/<name>
      "version": "0.0.1",        # pinned tag (pushing overrides an existing tag)
      "type": "devcontainer",    # "devcontainer" | "image"
      "depends": ["debian"]      # sibling folders that must build first (chainable)
    }

A folder is scheduled to build when its own files change, OR when anything it
(transitively) depends on is scheduled. The `depends` edge lives in the
*dependent* manifest, so the graph is discovered without any parent-side config.

Emits `build_matrix` (topologically ordered) and `has_builds` to GITHUB_OUTPUT.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def sh(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=False).stdout


def changed_files() -> list[str]:
    """Files changed across the whole push, with safe fallbacks."""
    before = os.environ.get("BEFORE_SHA", "")
    after = os.environ.get("AFTER_SHA", "HEAD") or "HEAD"

    before_exists = bool(before) and subprocess.run(
        ["git", "cat-file", "-e", before], capture_output=True, check=False
    ).returncode == 0

    # New branch (all-zero before) or history we can't reach -> treat everything as changed.
    if not before or set(before) <= {"0"} or not before_exists:
        out = sh("git", "ls-files")
    else:
        out = sh("git", "diff", "--name-only", before, after)
    return [line for line in out.splitlines() if line]


def normalize_variants(data: dict) -> list[dict]:
    """Return the list of variants for a manifest.

    A manifest without `variants` builds a single default image. When variants
    are declared but none is flagged `default`, the first one becomes default
    (it owns the plain `latest` / `<version>` tags).
    """
    variants = data.get("variants")
    if not variants:
        return [{"suffix": "", "args": {}, "default": True}]

    normalized = [
        {
            "suffix": str(v.get("suffix", "")),
            "args": dict(v.get("args", {})),
            "default": bool(v.get("default", False)),
        }
        for v in variants
    ]
    if not any(v["default"] for v in normalized):
        normalized[0]["default"] = True
    return normalized


def load_manifests() -> dict[str, dict]:
    images: dict[str, dict] = {}
    for manifest in sorted(Path(".").glob("*/build.json")):
        folder = manifest.parent.name
        data = json.loads(manifest.read_text())
        variants = normalize_variants(data)
        version = str(data["version"]) if "version" in data else ""
        # `version` supplies the pinned tag; it's only needed when there are no named
        # variants (a lone default with an empty suffix would otherwise have no tag).
        if not version and any(not v["suffix"] for v in variants):
            raise SystemExit(f"::error::{folder}/build.json needs a \"version\" (no variants declared)")
        images[folder] = {
            "folder": folder,
            "name": data.get("name", folder),
            "version": version,
            "type": data.get("type", "image"),
            "depends": list(data.get("depends", [])),
            "variants": variants,
        }
    return images


def main() -> None:
    files = changed_files()
    images = load_manifests()

    # Folders whose own files changed.
    directly_changed = {
        folder
        for folder in images
        if any(f == folder or f.startswith(folder + "/") for f in files)
    }

    # Reverse edges: dep -> folders that depend on it.
    dependents: dict[str, set[str]] = {folder: set() for folder in images}
    for folder, meta in images.items():
        for dep in meta["depends"]:
            if dep not in images:
                print(f"::warning::{folder} depends on unknown folder '{dep}'")
                continue
            dependents[dep].add(folder)

    # Transitive closure: a changed folder drags all its (chained) dependents along.
    to_build: set[str] = set()
    stack = list(directly_changed)
    while stack:
        cur = stack.pop()
        if cur in to_build:
            continue
        to_build.add(cur)
        stack.extend(dependents.get(cur, ()))

    # Kahn topological sort, restricted to the build set (deps outside it are already published).
    indegree = {
        folder: sum(1 for dep in images[folder]["depends"] if dep in to_build)
        for folder in to_build
    }
    ready = sorted(folder for folder in to_build if indegree[folder] == 0)
    order: list[str] = []
    while ready:
        folder = ready.pop(0)
        order.append(folder)
        for dependent in sorted(dependents.get(folder, ())):
            if dependent in indegree:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
                    ready.sort()

    if len(order) != len(to_build):
        cyclic = sorted(to_build - set(order))
        print(f"::error::Dependency cycle detected among: {', '.join(cyclic)}", file=sys.stderr)
        sys.exit(1)

    def tags_for(version: str, variant: dict) -> list[str]:
        suffix = variant["suffix"]
        if suffix:
            # Named variant: rolling suffix tag only (no version number).
            # The default variant additionally owns `latest`.
            return [suffix, "latest"] if variant["default"] else [suffix]
        # No variants declared: keep the version-pinned tag plus `latest`.
        return [version, "latest"]

    def entries(folder: str) -> list[dict]:
        meta = images[folder]
        out = []
        for variant in meta["variants"]:
            suffix = variant["suffix"]
            out.append({
                "folder": meta["folder"],
                "name": meta["name"],
                "version": meta["version"],
                "type": meta["type"],
                "suffix": suffix,
                # Unique per variant: used for job titles and cache scoping.
                "id": f"{meta['folder']}-{suffix}" if suffix else meta["folder"],
                # Newline-delimited KEY=VALUE for docker build-args / env export.
                "build_args": "\n".join(f"{k}={v}" for k, v in variant["args"].items()),
                # Comma-delimited bare tags (used directly as devcontainers/ci imageTag).
                "tags": ",".join(tags_for(meta["version"], variant)),
            })
        return out

    # Global topological order, then partitioned by type. Each folder fans out into
    # one entry per variant; variants of a folder stay contiguous and ahead of dependents.
    image_matrix = [e for f in order if images[f]["type"] == "image" for e in entries(f)]
    devcontainer_matrix = [e for f in order if images[f]["type"] == "devcontainer" for e in entries(f)]

    output_path = os.environ.get("GITHUB_OUTPUT", "/dev/stdout")
    with open(output_path, "a") as fh:
        fh.write("image_matrix=" + json.dumps(image_matrix, separators=(",", ":")) + "\n")
        fh.write("devcontainer_matrix=" + json.dumps(devcontainer_matrix, separators=(",", ":")) + "\n")
        fh.write("has_images=" + ("true" if image_matrix else "false") + "\n")
        fh.write("has_devcontainers=" + ("true" if devcontainer_matrix else "false") + "\n")

    print("Directly changed:", ", ".join(sorted(directly_changed)) or "(none)")
    print("Build plan (in dependency order):")
    for m in (image_matrix + devcontainer_matrix):
        print(f"  - {m['id']} ({m['type']}) -> {m['name']}:[{m['tags']}]")


if __name__ == "__main__":
    main()
