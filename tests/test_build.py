import gzip
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
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
    unreviewed = make_manifest("unreviewed-book-en", **{"quality.status": "candidate"})
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


def _write_pack(root: Path, name: str, **extra: Any) -> None:
    pack = {
        "name": name,
        "description": "Hand-curated test pack.",
        "version": "0.1.0",
        "filters": {"language": "en"},
        **extra,
    }
    (root / "packs" / f"{name}.yaml").write_text(
        yaml.safe_dump(pack, sort_keys=False), encoding="utf-8"
    )


def test_pack_exclude_works_always_removes_listed_ids(tmp_path: Path) -> None:
    kept = make_manifest("kept-book-en")
    dropped = make_manifest("dropped-book-en")
    root = make_root(tmp_path, [(kept, "kept text words"), (dropped, "dropped text words")])
    _write_pack(root, "sampler", exclude_works=["dropped-book-en"])

    build_dataset(root, pack="sampler")

    assert [row["id"] for row in read_rows(root, "sampler.jsonl.gz")] == ["kept-book-en"]


def test_pack_include_works_is_an_allowlist(tmp_path: Path) -> None:
    picked = make_manifest("picked-book-en")
    other = make_manifest("other-book-en")
    root = make_root(tmp_path, [(picked, "picked text words"), (other, "other text words")])
    _write_pack(root, "sampler", include_works=["picked-book-en"])

    build_dataset(root, pack="sampler")

    assert [row["id"] for row in read_rows(root, "sampler.jsonl.gz")] == ["picked-book-en"]


def test_pack_include_works_cannot_reintroduce_gated_works(tmp_path: Path) -> None:
    blocked = make_manifest("blocked-book-en", **{"rights.status": "uncertain"})
    root = make_root(tmp_path, [(blocked, "blocked text never ships")])
    _write_pack(root, "sampler", include_works=["blocked-book-en"])

    build_dataset(root, pack="sampler")

    assert read_rows(root, "sampler.jsonl.gz") == []


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


def test_release_gate_requires_supported_fetch_adapter(tmp_path: Path) -> None:
    """A fully reviewed, pinned work from an adapterless provider is
    consistently excluded by both the planner and the build - it can
    neither abort release preparation nor fail the build on missing text."""
    from open_fiction_corpus.build import releasable_work_ids

    ready = make_manifest("ready-book-en")
    manual = make_manifest("manual-book-en", **{"source.provider": "manual-scan"})
    root = make_root(
        tmp_path, [(ready, "ready text ships"), (manual, "manually acquired text")]
    )

    assert releasable_work_ids(root) == ["ready-book-en"]

    build_dataset(root)

    assert [row["id"] for row in read_rows(root)] == ["ready-book-en"]


def test_releasable_work_ids_ignores_blocked_and_broken_works(tmp_path: Path) -> None:
    from open_fiction_corpus.build import releasable_work_ids

    ready = make_manifest("ready-book-en")
    blocked = make_manifest(
        "blocked-book-en",
        **{"rights.status": "uncertain", "source.provider": "no-such-provider"},
    )
    root = make_root(tmp_path, [(ready, "ready text ships"), (blocked, "never used")])

    assert releasable_work_ids(root) == ["ready-book-en"]


def test_release_preparation_is_not_blocked_by_unfetchable_works(tmp_path: Path) -> None:
    from test_prepare import GUTENBERG_FILE, GUTENBERG_SHA256, _write_raw

    from open_fiction_corpus.build import releasable_work_ids
    from open_fiction_corpus.prepare import prepare_work

    ready = make_manifest(
        "ready-book-en", **{"processing.source_sha256": GUTENBERG_SHA256}
    )
    # Non-releasable AND unfetchable: must never enter the preparation plan.
    blocked = make_manifest(
        "blocked-book-en",
        **{"rights.status": "uncertain", "source.provider": "no-such-provider"},
    )
    root = make_root(tmp_path, [(ready, "reviewed text"), (blocked, "never used")])
    _write_raw(root, ready, GUTENBERG_FILE)

    for work_id in releasable_work_ids(root):
        prepare_work(root, work_id, skip_fetch=True)

    assert (root / "workspace" / "clean" / "ready-book-en.txt").exists()


def test_unknown_pack_name_raises(tmp_path: Path) -> None:
    root = make_root(tmp_path, [(make_manifest("some-book-en"), "words")])
    with pytest.raises(FileNotFoundError):
        build_dataset(root, pack="no-such-pack")


def test_missing_text_raises_unless_allowed(tmp_path: Path) -> None:
    manifest = make_manifest(
        "textless-book-en", **{"quality.reviewed_text_sha256": "0" * 64}
    )
    root = make_root(tmp_path, [(manifest, None)])

    with pytest.raises(FileNotFoundError):
        build_dataset(root)

    build_dataset(root, allow_missing_text=True)
    assert read_rows(root) == []


def test_build_output_is_byte_reproducible(tmp_path: Path) -> None:
    import time

    manifest = make_manifest("repro-book-en")
    root = make_root(tmp_path, [(manifest, "identical inputs identical bytes")])

    build_dataset(root)
    first = (root / "dist" / "books.jsonl.gz").read_bytes()
    time.sleep(1.1)  # a changed wall clock must not change the output
    build_dataset(root)
    second = (root / "dist" / "books.jsonl.gz").read_bytes()

    assert first == second
    # No stored filename or mtime in the gzip header (bytes 3-7 are flags+mtime).
    assert first[3] == 0 and first[4:8] == b"\x00\x00\x00\x00"


def test_release_assembly_is_byte_reproducible(tmp_path: Path) -> None:
    import subprocess
    import sys

    manifest = make_manifest("repro-book-en")
    root = make_root(tmp_path, [(manifest, "identical inputs identical bytes")])
    build_dataset(root)

    script = Path(__file__).resolve().parents[1] / "scripts" / "assemble_release.py"

    def assemble(output: Path) -> None:
        subprocess.run(
            [
                sys.executable, str(script),
                "--version", "v0.1.0",
                "--commit", "deadbeef",
                "--built-at", "2026-07-20T00:00:00+00:00",
                "--dist", str(root / "dist"),
                "--output", str(output),
            ],
            check=True,
        )

    assemble(root / "release-a")
    assemble(root / "release-b")

    for relative in [
        "data/books.jsonl.gz",
        "release/build-manifest.json",
        "release/checksums.sha256",
    ]:
        assert (root / "release-a" / relative).read_bytes() == (
            root / "release-b" / relative
        ).read_bytes(), relative


def test_short_text_raises(tmp_path: Path) -> None:
    manifest = make_manifest("short-book-en", **{"processing.expected_min_words": 100})
    root = make_root(tmp_path, [(manifest, "far too short")])
    with pytest.raises(ValueError, match="fewer than expected"):
        build_dataset(root)


def test_build_refuses_clean_text_changed_after_review(tmp_path: Path) -> None:
    manifest = make_manifest("tampered-book-en")
    root = make_root(tmp_path, [(manifest, "the text the reviewer approved")])
    text_path = root / "workspace" / "clean" / "tampered-book-en.txt"
    text_path.write_text("regenerated text nobody reviewed", encoding="utf-8")

    with pytest.raises(ValueError, match="changed after review"):
        build_dataset(root)

    # Development builds may still use the unreviewed text explicitly.
    build_dataset(root, allow_unreviewed=True)
    rows = read_rows(root)
    assert rows[0]["text"] == "regenerated text nobody reviewed"


@pytest.mark.parametrize(
    "override",
    [
        {"quality.status": "candidate"},
        {"quality.reviewed_by": []},
        {"source.revision": "unpinned"},
        {"processing.source_sha256": None},
    ],
)
def test_release_gate_skips_unready_works(tmp_path: Path, override: dict) -> None:
    ready = make_manifest("ready-book-en")
    unready = make_manifest("unready-book-en", **override)
    root = make_root(
        tmp_path, [(ready, "ready text ships"), (unready, "unready text stays local")]
    )

    build_dataset(root)

    assert [row["id"] for row in read_rows(root)] == ["ready-book-en"]


def test_release_gate_requires_reviewed_text_hash(tmp_path: Path) -> None:
    from helpers import write_manifest

    ready = make_manifest("ready-book-en")
    unready = make_manifest("unready-book-en")
    root = make_root(
        tmp_path, [(ready, "ready text ships"), (unready, "unready text stays local")]
    )
    # Clear the hash the fixture recorded: review without a pinned text.
    unready["quality"]["reviewed_text_sha256"] = None
    write_manifest(root, unready)

    build_dataset(root)

    assert [row["id"] for row in read_rows(root)] == ["ready-book-en"]


def test_release_gate_applies_to_pack_builds(tmp_path: Path) -> None:
    unready = make_manifest("unready-book-en", **{"source.revision": "unpinned"})
    root = make_root(tmp_path, [(unready, "unready text stays local")])

    build_dataset(root, pack="general-fiction")

    assert read_rows(root, "general-fiction.jsonl.gz") == []


def test_allow_unreviewed_includes_candidate_works(tmp_path: Path) -> None:
    unready = make_manifest(
        "unready-book-en",
        **{"quality.status": "candidate", "processing.source_sha256": None},
    )
    root = make_root(tmp_path, [(unready, "development build text")])

    build_dataset(root, allow_unreviewed=True)

    assert [row["id"] for row in read_rows(root)] == ["unready-book-en"]
