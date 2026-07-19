"""Tests for the fetch/extract/clean/modernise pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from open_fiction_corpus.prepare import (
    apply_overrides,
    clean_fiction,
    extract_gutenberg_txt,
    modernize_spelling,
    prepare_work,
)
from helpers import REPO_ROOT, make_manifest, make_root

GUTENBERG_FILE = """The Project Gutenberg eBook of Example Novel
This header must never reach the corpus.

*** START OF THE PROJECT GUTENBERG EBOOK 999 ***

Produced by Anonymous Volunteers

Example Novel

by Example Author


I.

It was a dark and stormy night, and the rain fell
in torrents upon the roof of the old house.

He said he would return to-morrow.  "To-day," she
replied, "our connexion ends."

*** END OF THE PROJECT GUTENBERG EBOOK 999 ***

Redistribution terms that must never reach the corpus.
"""


def test_extract_strips_header_footer_and_credits() -> None:
    body = extract_gutenberg_txt(GUTENBERG_FILE)
    assert "Project Gutenberg eBook of" not in body
    assert "Redistribution terms" not in body
    assert "Produced by" not in body
    assert body.startswith("Example Novel")
    assert "dark and stormy" in body


def test_extract_requires_markers() -> None:
    with pytest.raises(ValueError, match="START OF"):
        extract_gutenberg_txt("No markers here.")


def test_clean_unwraps_paragraphs_and_keeps_section_gaps() -> None:
    text = "A heading\n\n\nFirst line\nsecond line.\n\nNext  paragraph\r\nhere.\n"
    cleaned = clean_fiction(text)
    assert cleaned == "A heading\n\n\nFirst line second line.\n\nNext paragraph here.\n"


def test_modernize_preserves_case_and_word_boundaries(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    text = "To-day and to-day, TO-DAY! A connexional matter. Their connexion held.\n"
    result, counts = modernize_spelling(text, root)
    assert result == "Today and today, TODAY! A connexional matter. Their connection held.\n"
    assert counts == {"to-day": 3, "connexion": 1}


def test_overrides_require_note_and_exact_count(tmp_path: Path) -> None:
    path = tmp_path / "work.yaml"
    path.write_text(
        yaml.safe_dump(
            {"corrections": [{"find": "teh", "replace": "the", "count": 2, "note": "typo"}]}
        ),
        encoding="utf-8",
    )
    assert apply_overrides("teh cat saw teh dog", path) == "the cat saw the dog"
    with pytest.raises(ValueError, match="matched 1"):
        apply_overrides("teh cat", path)

    path.write_text(
        yaml.safe_dump({"corrections": [{"find": "a", "replace": "b"}]}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="note"):
        apply_overrides("a", path)


def test_prepare_work_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    manifest = make_manifest(
        "example-work",
        **{
            "processing.extractor": "gutenberg_txt_v1",
            "processing.modernizer": "modernize_spelling_v1",
        },
    )
    root = make_root(tmp_path, [(manifest, None)])
    raw_dir = root / "workspace" / "raw" / "example-work"
    raw_dir.mkdir(parents=True)
    (raw_dir / "pg999.txt").write_text(GUTENBERG_FILE, encoding="utf-8")

    clean_path = prepare_work(root, "example-work", skip_fetch=True)

    text = clean_path.read_text(encoding="utf-8")
    assert "Project Gutenberg" not in text
    assert "It was a dark and stormy night, and the rain fell in torrents" in text
    assert "return tomorrow." in text
    assert '"Today," she replied, "our connection ends."' in text
    output = capsys.readouterr().out
    assert "Modernised 'to-day': 1 replacement(s)" in output


def test_prepare_work_applies_overrides(tmp_path: Path) -> None:
    manifest = make_manifest(
        "example-work",
        **{"processing.extractor": "gutenberg_txt_v1", "processing.modernizer": None},
    )
    root = make_root(tmp_path, [(manifest, None)])
    raw_dir = root / "workspace" / "raw" / "example-work"
    raw_dir.mkdir(parents=True)
    (raw_dir / "pg999.txt").write_text(GUTENBERG_FILE, encoding="utf-8")
    overrides_dir = root / "overrides"
    overrides_dir.mkdir()
    (overrides_dir / "example-work.yaml").write_text(
        yaml.safe_dump(
            {
                "corrections": [
                    {
                        "find": "dark and stormy",
                        "replace": "dark and rainy",
                        "count": 1,
                        "note": "test correction",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    text = prepare_work(root, "example-work", skip_fetch=True).read_text(encoding="utf-8")
    assert "dark and rainy" in text
    # Without a modernizer configured, original spellings survive.
    assert "to-morrow" in text


def test_prepare_work_rejects_unknown_extractor(tmp_path: Path) -> None:
    manifest = make_manifest(
        "example-work", **{"processing.extractor": "no_such_extractor"}
    )
    root = make_root(tmp_path, [(manifest, None)])
    raw_dir = root / "workspace" / "raw" / "example-work"
    raw_dir.mkdir(parents=True)
    (raw_dir / "pg999.txt").write_text(GUTENBERG_FILE, encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown extractor"):
        prepare_work(root, "example-work", skip_fetch=True)


def test_time_machine_manifest_is_catalogued() -> None:
    path = REPO_ROOT / "catalog" / "works" / "h-g-wells-the-time-machine-en.yaml"
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert manifest["id"] == "h-g-wells-the-time-machine-en"
    assert manifest["processing"]["extractor"] == "gutenberg_txt_v1"
    assert manifest["processing"]["modernizer"] == "modernize_spelling_v1"
