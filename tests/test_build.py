import gzip
import json
from pathlib import Path
from typing import Any

import pytest
from helpers import make_manifest, make_root

from open_fiction_corpus.build import build_dataset


def read_rows(root: Path, filename: str = "books.jsonl.gz") -> list[dict[str, Any]]:
    with gzip.open(root / "dist" / filename, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def test_build_round_trip_row_fields(tmp_path: Path) -> None:
    manifest = make_manifest("author-one-book-en")
    root = make_root(tmp_path, [(manifest, "once upon a midnight dreary")])

    build_dataset(root)

    rows = read_rows(root)
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == "author-one-book-en"
    assert row["authors"] == ["Example Author"]
    assert row["rights_status"] == "public-domain"
    assert row["text"] == "once upon a midnight dreary"


@pytest.mark.parametrize("status", ["uncertain", "excluded"])
def test_build_skips_unreleasable_rights(tmp_path: Path, status: str) -> None:
    releasable = make_manifest("kept-book-en")
    blocked = make_manifest("blocked-book-en", **{"rights.status": status})
    root = make_root(
        tmp_path,
        [(releasable, "kept text stays here"), (blocked, "blocked text never ships")],
    )

    build_dataset(root)

    ids = [row["id"] for row in read_rows(root)]
    assert ids == ["kept-book-en"]


def test_rights_gate_applies_to_pack_builds(tmp_path: Path) -> None:
    blocked = make_manifest(
        "blocked-book-en",
        **{"rights.status": "excluded", "quality.status": "human-reviewed"},
    )
    root = make_root(tmp_path, [(blocked, "blocked text never ships")])

    build_dataset(root, pack="general-fiction")

    assert read_rows(root, "general-fiction.jsonl.gz") == []


def test_pack_filters_quality_origin_and_genre(tmp_path: Path) -> None:
    reviewed_fantasy = make_manifest(
        "reviewed-fantasy-en", **{"quality.status": "human-reviewed"}
    )
    unreviewed = make_manifest("unreviewed-book-en")  # quality status stays candidate
    reviewed_romance = make_manifest(
        "reviewed-romance-en",
        **{
            "quality.status": "human-reviewed",
            "classification.primary_genre": "romance",
            "classification.genres": ["romance"],
            "classification.subgenres": [],
        },
    )
    ai_generated = make_manifest(
        "ai-book-en",
        **{"quality.status": "human-reviewed", "content.origin": "ai-generated"},
    )
    works = [
        (reviewed_fantasy, "reviewed fantasy words"),
        (unreviewed, "unreviewed candidate words"),
        (reviewed_romance, "reviewed romance words"),
        (ai_generated, "machine written words"),
    ]
    root = make_root(tmp_path, works)

    build_dataset(root, pack="fantasy")

    ids = [row["id"] for row in read_rows(root, "fantasy.jsonl.gz")]
    assert ids == ["reviewed-fantasy-en"]


def test_pack_excludes_flagged_works(tmp_path: Path) -> None:
    flagged = make_manifest(
        "flagged-book-en",
        **{"quality.status": "human-reviewed", "quality.flags": ["severe-ocr-errors"]},
    )
    clean = make_manifest("clean-book-en", **{"quality.status": "human-reviewed"})
    root = make_root(tmp_path, [(flagged, "garbled scanned words"), (clean, "clean readable words")])

    build_dataset(root, pack="general-fiction")

    ids = [row["id"] for row in read_rows(root, "general-fiction.jsonl.gz")]
    assert ids == ["clean-book-en"]


def test_pack_caps_works_per_author(tmp_path: Path) -> None:
    works = []
    for index in range(7):
        manifest = make_manifest(
            f"prolific-book-{index}-en", **{"quality.status": "human-reviewed"}
        )
        works.append((manifest, f"book number {index} text"))
    root = make_root(tmp_path, works)

    build_dataset(root, pack="general-fiction")  # max_works_per_author: 3

    ids = [row["id"] for row in read_rows(root, "general-fiction.jsonl.gz")]
    assert len(ids) == 3
    assert ids == sorted(ids)


def test_unknown_pack_name_raises(tmp_path: Path) -> None:
    root = make_root(tmp_path, [(make_manifest("some-book-en"), "words")])
    with pytest.raises(FileNotFoundError):
        build_dataset(root, pack="no-such-pack")


def test_missing_text_raises_unless_allowed(tmp_path: Path) -> None:
    root = make_root(tmp_path, [(make_manifest("textless-book-en"), None)])

    with pytest.raises(FileNotFoundError):
        build_dataset(root)

    build_dataset(root, allow_missing_text=True)
    assert read_rows(root) == []


def test_short_text_raises(tmp_path: Path) -> None:
    manifest = make_manifest("short-book-en", **{"processing.expected_min_words": 100})
    root = make_root(tmp_path, [(manifest, "far too short")])
    with pytest.raises(ValueError, match="fewer than expected"):
        build_dataset(root)
