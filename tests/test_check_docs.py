"""Regression checks for the offline Markdown target gate."""

import pytest

from scripts.check_docs import check_file


@pytest.mark.parametrize("prefix", ["", "!"])
@pytest.mark.parametrize(
    ("target", "filename"),
    [
        ("figure.png", "figure.png"),
        ("figure%20one.png", "figure one.png"),
        ('figure(one).png "Caption"', "figure(one).png"),
    ],
)
def test_existing_local_targets(tmp_path, prefix, target, filename):
    (tmp_path / filename).write_bytes(b"")
    page = tmp_path / "page.md"
    page.write_text(f"{prefix}[Figure]({target})\n", encoding="utf-8")

    assert check_file(page, tmp_path, {}) == []


@pytest.mark.parametrize("prefix", ["", "!"])
def test_missing_local_targets_report_path_and_line(tmp_path, prefix):
    page = tmp_path / "page.md"
    page.write_text(f"# Page\n\n{prefix}[Figure](missing.png)\n", encoding="utf-8")

    assert check_file(page, tmp_path, {}) == [f"{page}:3: missing target 'missing.png'"]


@pytest.mark.parametrize("prefix", ["", "!"])
def test_external_targets_remain_offline(tmp_path, prefix):
    page = tmp_path / "page.md"
    page.write_text(
        f"{prefix}[Figure](https://example.invalid/figure.png)\n", encoding="utf-8"
    )

    assert check_file(page, tmp_path, {}) == []


def test_markdown_anchors_still_checked(tmp_path):
    page = tmp_path / "page.md"
    page.write_text("# Page\n[valid](#page)\n[broken](#missing)\n", encoding="utf-8")

    assert check_file(page, tmp_path, {}) == [f"{page}:3: missing anchor #missing in "]
