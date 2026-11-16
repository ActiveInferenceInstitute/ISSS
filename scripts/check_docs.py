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
FENCE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})(?P<tail>.*)$")
SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")
DEFINITION = re.compile(
    r"^ {0,3}\[(?P<label>[^\]\n]+)\]:[ \t]*"
    r"(?:<(?P<angle>[^>\n]*)>|(?P<plain>\S+))"
    r"(?:[ \t]+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?[ \t]*$"
)
REFERENCE = re.compile(
    r"!?\[(?P<text>(?:\\.|[^\]\\\n])*)\]"
    r"(?:[ \t]*\[(?P<label>(?:\\.|[^\]\\\n])*)\])?"
)


def _escaped(text: str, position: int) -> bool:
    backslashes = 0
    while position > 0 and text[position - 1] == "\\":
        position -= 1
        backslashes += 1
    return bool(backslashes % 2)


def _blank(text: str) -> str:
    return "".join("\n" if character == "\n" else " " for character in text)


def _outside_fences(text: str) -> str:
    """Mask code without changing offsets or physical source line numbers."""
    lines = []
    opening = None
    for line in text.splitlines(keepends=True):
        match = FENCE.match(line.rstrip("\r\n"))
        if opening is not None:
            lines.append(_blank(line))
            if (match and match["fence"][0] == opening[0]
                    and len(match["fence"]) >= opening[1] and not match["tail"].strip()):
                opening = None
        elif match and not (match["fence"][0] == "`" and "`" in match["tail"]):
            opening = (match["fence"][0], len(match["fence"]))
            lines.append(_blank(line))
        else:
            lines.append(line)
    return "".join(lines)


def _outside_inline_code(text: str) -> str:
    runs = list(re.finditer(r"`+", text))
    pieces = []
    cursor = index = 0
    while index < len(runs):
        start = runs[index]
        if _escaped(text, start.start()):
            index += 1
            continue
        closing = next(
            (end for end in range(index + 1, len(runs))
             if len(runs[end].group()) == len(start.group())
             and not re.search(r"\n[ \t]*\n", text[start.end():runs[end].start()])),
            None,
        )
        if closing is None:
            index += 1
            continue
        finish = runs[closing].end()
        pieces.extend((text[cursor:start.start()], _blank(text[start.start():finish])))
        cursor = finish
        index = closing + 1
    pieces.append(text[cursor:])
    return "".join(pieces)


def _label(label: str) -> str:
    return " ".join(label.split()).casefold()


def link_targets(text: str) -> list[tuple[int, str]]:
    """Resolve only established links/images, excluding code and unused definitions."""
    lines = _outside_inline_code(_outside_fences(text)).splitlines()
    definitions = {}
    definition_lines = set()
    for number, line in enumerate(lines, start=1):
        match = DEFINITION.match(line)
        if match:
            definitions.setdefault(_label(match["label"]), match["angle"] or match["plain"] or "")
            definition_lines.add(number)
    targets = []
    for number, line in enumerate(lines, start=1):
        if number in definition_lines:
            continue
        reference_line = list(line)
        for match in LINK.finditer(line):
            if _escaped(line, match.start()):
                continue
            targets.append((number, match["target"]))
            reference_line[match.start():match.end()] = " " * (match.end() - match.start())
        for match in REFERENCE.finditer("".join(reference_line)):
            if _escaped(line, match.start()):
                continue
            label = match["label"] or match["text"]
            target = definitions.get(_label(label))
            if target is not None:
                targets.append((number, target))
    return targets


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
    text = _outside_fences(path.read_text(encoding="utf-8"))
    for line in text.splitlines():
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
    for number, raw_target in link_targets(path.read_text(encoding="utf-8")):
        target = unquote(raw_target.strip("<>"))
        if not target or SCHEME.match(target):
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
