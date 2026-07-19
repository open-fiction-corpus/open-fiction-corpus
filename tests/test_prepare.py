"""Tests for the fetch/extract/clean/modernise pipeline."""

from __future__ import annotations

import hashlib
import io
import urllib.request
from pathlib import Path

import pytest
import yaml

from open_fiction_corpus.prepare import (
    apply_overrides,
    clean_fiction,
    extract_gutenberg_txt,
    fetch_source,
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

GUTENBERG_SHA256 = hashlib.sha256(GUTENBERG_FILE.encode("utf-8")).hexdigest()


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _make_response(payload: bytes) -> _FakeResponse:
    return _FakeResponse(payload)


def _fake_urlopen(monkeypatch: pytest.MonkeyPatch, payload: bytes) -> None:
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda request, timeout: _make_response(payload)
    )


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
            "processing.source_sha256": GUTENBERG_SHA256,
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
        **{
            "processing.extractor": "gutenberg_txt_v1",
            "processing.modernizer": None,
            "processing.source_sha256": GUTENBERG_SHA256,
        },
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
        "example-work",
        **{
            "processing.extractor": "no_such_extractor",
            "processing.source_sha256": GUTENBERG_SHA256,
        },
    )
    root = make_root(tmp_path, [(manifest, None)])
    raw_dir = root / "workspace" / "raw" / "example-work"
    raw_dir.mkdir(parents=True)
    (raw_dir / "pg999.txt").write_text(GUTENBERG_FILE, encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown extractor"):
        prepare_work(root, "example-work", skip_fetch=True)


def test_overrides_reject_missing_or_invalid_count(tmp_path: Path) -> None:
    path = tmp_path / "work.yaml"
    for bad in [{}, {"count": 0}, {"count": True}, {"count": "2"}]:
        correction = {"find": "a", "replace": "b", "note": "n", **bad}
        path.write_text(yaml.safe_dump({"corrections": [correction]}), encoding="utf-8")
        with pytest.raises(ValueError, match="positive integer 'count'"):
            apply_overrides("a", path)


def test_skip_fetch_verifies_pinned_hash(tmp_path: Path) -> None:
    manifest = make_manifest(
        "example-work", **{"processing.extractor": "gutenberg_txt_v1"}
    )  # helper default hash does not match the synthetic raw file
    root = make_root(tmp_path, [(manifest, None)])
    raw_dir = root / "workspace" / "raw" / "example-work"
    raw_dir.mkdir(parents=True)
    (raw_dir / "pg999.txt").write_text(GUTENBERG_FILE, encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        prepare_work(root, "example-work", skip_fetch=True)


def test_fetch_uses_download_url_and_project_user_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = make_manifest(
        "example-work",
        **{
            "source.provider": "gutenberg",
            "source.download_url": "https://example.invalid/cache/pg999.txt",
            "processing.source_sha256": GUTENBERG_SHA256,
        },
    )
    root = make_root(tmp_path, [(manifest, None)])
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["user_agent"] = request.get_header("User-agent")
        return _make_response(GUTENBERG_FILE.encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    raw_path = fetch_source(root, manifest)

    assert seen["url"] == "https://example.invalid/cache/pg999.txt"
    assert "open-fiction-corpus" in seen["user_agent"]
    assert raw_path.name == "pg999.txt"
    assert raw_path.read_text(encoding="utf-8") == GUTENBERG_FILE


def test_fetch_hash_mismatch_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = make_manifest(
        "example-work",
        **{
            "source.provider": "gutenberg",
            "source.download_url": "https://example.invalid/cache/pg999.txt",
            "processing.source_sha256": "f" * 64,
        },
    )
    root = make_root(tmp_path, [(manifest, None)])
    _fake_urlopen(monkeypatch, GUTENBERG_FILE.encode("utf-8"))

    with pytest.raises(ValueError, match="hash mismatch"):
        fetch_source(root, manifest)

    raw_dir = root / "workspace" / "raw" / "example-work"
    assert not raw_dir.exists() or list(raw_dir.iterdir()) == []


def test_fetch_requires_download_url(tmp_path: Path) -> None:
    manifest = make_manifest(
        "example-work",
        **{"source.provider": "gutenberg", "source.download_url": None},
    )
    root = make_root(tmp_path, [(manifest, None)])
    with pytest.raises(ValueError, match="download_url"):
        fetch_source(root, manifest)


def test_overrides_are_validated_by_repository_validation(tmp_path: Path) -> None:
    from open_fiction_corpus.validate import collect_errors

    manifest = make_manifest("example-work")
    root = make_root(tmp_path, [(manifest, None)])
    overrides_dir = root / "overrides"
    overrides_dir.mkdir()
    (overrides_dir / "example-work.yaml").write_text(
        yaml.safe_dump({"corrections": [{"find": "a", "replace": "b"}]}),
        encoding="utf-8",
    )
    (overrides_dir / "no-such-work.yaml").write_text(
        yaml.safe_dump({"corrections": []}), encoding="utf-8"
    )

    joined = "\n".join(collect_errors(root))
    assert "'count' is a required property" in joined
    assert "no work manifest with id 'no-such-work'" in joined


def test_validate_requires_download_url_for_gutenberg(tmp_path: Path) -> None:
    from open_fiction_corpus.validate import collect_errors

    missing = make_manifest(
        "gutenberg-book-en",
        **{"source.provider": "gutenberg", "source.download_url": None},
    )
    del missing["source"]["download_url"]
    trailing_slash = make_manifest(
        "slash-book-en", **{"source.download_url": "https://example.invalid/dir/"}
    )
    root = make_root(tmp_path, [(missing, None), (trailing_slash, None)])

    joined = "\n".join(collect_errors(root))
    assert "source.download_url is required for provider 'gutenberg'" in joined
    assert "source.download_url must end in a file name" in joined


def test_fetch_rejects_download_url_without_file_name(tmp_path: Path) -> None:
    manifest = make_manifest(
        "example-work",
        **{
            "source.provider": "gutenberg",
            "source.download_url": "https://example.invalid/dir/",
        },
    )
    root = make_root(tmp_path, [(manifest, None)])
    with pytest.raises(ValueError, match="must end in a file name"):
        fetch_source(root, manifest)


def test_failed_prepare_preserves_existing_clean_text(tmp_path: Path) -> None:
    manifest = make_manifest(
        "example-work",
        **{
            "processing.extractor": "gutenberg_txt_v1",
            "processing.source_sha256": GUTENBERG_SHA256,
        },
    )
    root = make_root(tmp_path, [(manifest, "previously valid clean text")])
    raw_dir = root / "workspace" / "raw" / "example-work"
    raw_dir.mkdir(parents=True)
    (raw_dir / "pg999.txt").write_text(GUTENBERG_FILE, encoding="utf-8")
    overrides_dir = root / "overrides"
    overrides_dir.mkdir()
    (overrides_dir / "example-work.yaml").write_text(
        yaml.safe_dump(
            {
                "corrections": [
                    {"find": "not present", "replace": "x", "count": 1, "note": "n"}
                ]
            }
        ),
        encoding="utf-8",
    )

    clean_path = root / "workspace" / "clean" / "example-work.txt"
    with pytest.raises(ValueError, match="matched 0"):
        prepare_work(root, "example-work", skip_fetch=True)

    assert clean_path.read_text(encoding="utf-8") == "previously valid clean text"
    assert list((root / "workspace" / "clean").glob("*.tmp")) == []


def test_time_machine_manifest_is_catalogued() -> None:
    path = REPO_ROOT / "catalog" / "works" / "h-g-wells-the-time-machine-en.yaml"
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert manifest["id"] == "h-g-wells-the-time-machine-en"
    assert manifest["processing"]["extractor"] == "gutenberg_txt_v1"
    assert manifest["processing"]["modernizer"] == "modernize_spelling_v1"
