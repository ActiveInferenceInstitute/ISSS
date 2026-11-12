#!/usr/bin/env python3
"""Relative-link check for the repository's Markdown.

The repository declares no documentation toolchain (no mkdocs, no
markdown-link-check), so this file is the documentation gate: it resolves every
relative link, image target and Markdown anchor in the tracked ``*.md`` files
and reports the ones that do not exist. External URLs are not fetched — the gate stays offline.

    python scripts/check_docs.py            # check the whole repository
    python scripts/check_docs.py docs/a.md  # check one file

Exit code 0 means every relative target and anchor resolves; 1 lists the
failures as ``path:line: reason``.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

LINK = re.compile(r"!?\[(?P<text>[^\]]*)\]\((?P<target>[^()\s]*(?:\([^()\s]*\)[^()\s]*)*)"
                  r"(?:\s+\"[^\"]*\")?\)")
HEADING = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.+?)\s*$")
FENCE = re.compile(r"^(?P<fence>```+|~~~+)")
ABSOLUTE = ("http://", "https://", "mailto:", "tel:", "ftp://")


def tracked_markdown(root: Path) -> list[Path]:
    """Every tracked ``*.md`` file, or a walk when git is unavailable."""
    try:
        output = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--", "*.md"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return sorted(root.rglob("*.md"))
    return [root / name for name in output.split("\0") if name]


def anchors(path: Path) -> set[str]:
    """GitHub-style heading slugs for one Markdown file, fenced code ignored."""
    slugs: set[str] = set()
    counts: dict[str, int] = {}
    in_fence: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        fence = FENCE.match(line)
        if fence:
            marker = fence.group("fence")[:3]
            if in_fence is None:
                in_fence = marker
            elif in_fence == marker:
                in_fence = None
            continue
        if in_fence is not None:
            continue
        heading = HEADING.match(line)
        if not heading:
            continue
        slug = re.sub(r"[^\w\- ]", "", heading.group("text").lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        slugs.add(slug if count == 0 else f"{slug}-{count}")
    return slugs


def check_file(path: Path, root: Path, cache: dict[Path, set[str]]) -> list[str]:
    failures: list[str] = []
    cache_key = path.resolve()
    if cache_key not in cache:
        cache[cache_key] = anchors(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, start=1):
        for match in LINK.finditer(line):
            target = unquote(match.group("target").strip("<>"))
            if not target or target.startswith(ABSOLUTE):
                continue
            location, _, anchor = target.partition("#")
            destination = (path.parent / location).resolve() if location else cache_key
            if not destination.exists():
                failures.append(f"{path}:{number}: missing target {location!r}")
                continue
            if not anchor or destination.suffix != ".md":
                continue
            if destination not in cache:
                cache[destination] = anchors(destination)
            if anchor not in cache[destination]:
                failures.append(f"{path}:{number}: missing anchor #{anchor} in {location}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", help="Markdown files; default is every tracked file")
    parser.add_argument("--root", default=None, help="repository root (default: parent of scripts/)")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent
    files = [Path(item).resolve() for item in args.paths] or tracked_markdown(root)
    cache: dict[Path, set[str]] = {}
    failures: list[str] = []
    for path in files:
        if not path.is_file():
            failures.append(f"{path}: not a file")
            continue
        failures.extend(check_file(path, root, cache))

    for failure in failures:
        print(failure)
    print(f"checked {len(files)} Markdown file(s); {len(failures)} broken link(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
