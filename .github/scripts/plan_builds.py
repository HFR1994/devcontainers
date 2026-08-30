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


def load_manifests() -> dict[str, dict]:
    images: dict[str, dict] = {}
    for manifest in sorted(Path(".").glob("*/build.json")):
        folder = manifest.parent.name
        data = json.loads(manifest.read_text())
        images[folder] = {
            "folder": folder,
            "name": data.get("name", folder),
            "version": str(data["version"]),
            "type": data.get("type", "image"),
            "depends": list(data.get("depends", [])),
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

    matrix = [
        {
            "folder": images[f]["folder"],
            "name": images[f]["name"],
            "version": images[f]["version"],
            "type": images[f]["type"],
        }
        for f in order
    ]

    output_path = os.environ.get("GITHUB_OUTPUT", "/dev/stdout")
    with open(output_path, "a") as fh:
        fh.write("build_matrix=" + json.dumps(matrix, separators=(",", ":")) + "\n")
        fh.write("has_builds=" + ("true" if matrix else "false") + "\n")

    print("Directly changed:", ", ".join(sorted(directly_changed)) or "(none)")
    print("Build plan (in dependency order):")
    for m in matrix:
        print(f"  - {m['folder']} ({m['type']}) -> {m['name']}:{m['version']}")


if __name__ == "__main__":
    main()
