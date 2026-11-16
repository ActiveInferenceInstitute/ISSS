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


@pytest.mark.parametrize('prefix', ['', '!'])
@pytest.mark.parametrize('reference', ['[caption][manual key]', '[manual key][]', '[manual key]'])
def test_used_reference_links_and_images_report_use_site(tmp_path, prefix, reference):
    page = tmp_path / 'page.md'
    page.write_text(f'# Page\n\n{prefix}{reference}\n\n[ Manual   KEY ]: missing.png\n')
    assert check_file(page, tmp_path, {}) == [f"{page}:3: missing target 'missing.png'"]


@pytest.mark.parametrize('prefix', ['', '!'])
@pytest.mark.parametrize(
    ('target', 'filename'),
    [
        ('figure%20one.png', 'figure one.png'),
        ('<figure one.png> \"Title\"', 'figure one.png'),
        ('figure(one).png \"Caption\"', 'figure(one).png'),
    ],
)
def test_reference_destinations_keep_existing_filename_rules(tmp_path, prefix, target, filename):
    (tmp_path / filename).write_bytes(b'fixture')
    page = tmp_path / 'page.md'
    page.write_text(f'{prefix}[caption][m]\n[m]: {target}\n')
    assert check_file(page, tmp_path, {}) == []


def test_reference_markdown_fragments_use_the_same_anchor_contract(tmp_path):
    (tmp_path / 'guide.md').write_text('# Known\n')
    page = tmp_path / 'page.md'
    page.write_text(
        '[good][one]\n[bad][two]\n[one]: guide.md#known\n[two]: guide.md#missing\n'
    )
    assert check_file(page, tmp_path, {}) == [
        f'{page}:2: missing anchor #missing in guide.md'
    ]


def test_unused_definitions_and_undefined_brackets_are_not_links(tmp_path):
    page = tmp_path / 'page.md'
    page.write_text('[ordinary brackets]\n[undefined][label]\n[unused]: missing.md\n')
    assert check_file(page, tmp_path, {}) == []


def test_first_normalized_definition_wins_and_inline_link_is_not_a_shortcut(tmp_path):
    (tmp_path / 'exists.md').write_text('# Exists\n')
    page = tmp_path / 'page.md'
    page.write_text(
        '[caption][M]\n[m]: exists.md\n[M]: missing.md\n'
        '[caption](exists.md)\n[caption]: also-missing.md\n'
    )
    assert check_file(page, tmp_path, {}) == []


def test_external_reference_links_and_images_are_offline(tmp_path):
    page = tmp_path / 'page.md'
    page.write_text(
        '[caption][remote]\n![image][remote]\n'
        '[remote]: https://example.invalid/no-network.png\n'
    )
    assert check_file(page, tmp_path, {}) == []


@pytest.mark.parametrize('marker', ['````', '~~~~'])
@pytest.mark.parametrize('indent', ['', '   '])
def test_fences_ignore_links_definitions_and_shorter_closing_runs(tmp_path, marker, indent):
    page = tmp_path / 'page.md'
    page.write_text(
        f'{indent}{marker}python\n[ignored](missing.md)\n{marker[:3]}\n'
        f'[m]: hidden.md\n[hidden][m]\n{indent}{marker}\n[real](real-missing.md)\n'
    )
    assert check_file(page, tmp_path, {}) == [f"{page}:7: missing target 'real-missing.md'"]


@pytest.mark.parametrize('code', [
    '`[ignored](missing.md)`',
    '``[ignored](missing.md) with ` inside``',
    '`[ignored][m]\n[m]: missing.md`',
    '`[ignored](missing.md)\ncontinued`',
])
def test_matched_inline_code_spans_do_not_hide_later_prose_errors(tmp_path, code):
    page = tmp_path / 'page.md'
    page.write_text(f'# Page\n{code}\n[real](broken.md)\n')
    line = 3 + code.count('\n')
    assert check_file(page, tmp_path, {}) == [f"{page}:{line}: missing target 'broken.md'"]


def test_unmatched_backticks_do_not_hide_following_links(tmp_path):
    page = tmp_path / 'page.md'
    page.write_text('`unmatched\n[real](broken.md)\n')
    assert check_file(page, tmp_path, {}) == [f"{page}:2: missing target 'broken.md'"]


def test_heading_code_words_and_duplicate_slugs_survive_fence_filtering(tmp_path):
    page = tmp_path / 'page.md'
    page.write_text(
        '# Heading `code`\n# Heading `code`\n```\n# Hidden\n```\n'
        '[one](#heading-code)\n[two](#heading-code-1)\n[bad](#hidden)\n'
    )
    assert check_file(page, tmp_path, {}) == [f'{page}:8: missing anchor #hidden in ']


@pytest.mark.parametrize('text', [
    '`\\` [broken](missing.md) `next`',
    '``\\`` [broken](missing.md) ``next``',
    '\\` [broken](missing.md) `next`',
])
def test_backslashes_do_not_escape_closing_code_delimiters(tmp_path, text):
    page = tmp_path / 'page.md'
    page.write_text(text + '\n')
    assert check_file(page, tmp_path, {}) == [f"{page}:1: missing target 'missing.md'"]
