"""Tests for the fetch/extract/clean/modernise pipeline."""

from __future__ import annotations

import hashlib
import io
import json
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


def _write_raw(root: Path, manifest: dict, text: str = GUTENBERG_FILE) -> Path:
    """Write the canonical raw artifact plus a matching provenance sidecar."""
    work_id = manifest["id"]
    raw_dir = root / "workspace" / "raw" / work_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{work_id}.txt"
    raw_path.write_text(text, encoding="utf-8")
    sidecar = {
        "provider": manifest["source"]["provider"],
        "identifier": manifest["source"]["identifier"],
        "download_url": manifest["source"].get("download_url"),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    (raw_dir / f"{work_id}.txt.provenance.json").write_text(
        json.dumps(sidecar), encoding="utf-8"
    )
    return raw_path


def _fake_network(monkeypatch: pytest.MonkeyPatch, payload: bytes) -> dict:
    """Replace the fetcher's opener; returns a dict capturing the request."""
    seen: dict = {}

    class FakeOpener:
        def open(self, request, timeout):
            seen["url"] = request.full_url
            seen["user_agent"] = request.get_header("User-agent")
            return _FakeResponse(payload)

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: FakeOpener())
    return seen


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
    _write_raw(root, manifest)

    clean_path = prepare_work(root, "example-work", skip_fetch=True)

    text = clean_path.read_text(encoding="utf-8")
    assert "Project Gutenberg" not in text
    assert "It was a dark and stormy night, and the rain fell in torrents" in text
    assert "return tomorrow." in text
    assert '"Today," she replied, "our connection ends."' in text
    output = capsys.readouterr().out
    assert "Modernised 'to-day': 1 replacement(s)" in output
    # The printed hash is exactly the hash of the file bytes (LF newlines,
    # no platform text-mode translation), which is what the build verifies.
    file_bytes = clean_path.read_bytes()
    assert b"\r" not in file_bytes
    assert hashlib.sha256(file_bytes).hexdigest() in output


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
    _write_raw(root, manifest)
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
    _write_raw(root, manifest)
    with pytest.raises(ValueError, match="Unknown extractor"):
        prepare_work(root, "example-work", skip_fetch=True)


def test_overrides_reject_missing_or_invalid_count(tmp_path: Path) -> None:
    path = tmp_path / "work.yaml"
    for bad in [{}, {"count": 0}, {"count": True}, {"count": "2"}]:
        correction = {"find": "a", "replace": "b", "note": "n", **bad}
        path.write_text(yaml.safe_dump({"corrections": [correction]}), encoding="utf-8")
        with pytest.raises(ValueError, match="positive integer 'count'"):
            apply_overrides("a", path)


def test_skip_fetch_rejects_leftover_temp_file(tmp_path: Path) -> None:
    manifest = make_manifest(
        "example-work",
        **{
            "processing.extractor": "gutenberg_txt_v1",
            "processing.source_sha256": None,
        },
    )
    root = make_root(tmp_path, [(manifest, None)])
    raw_dir = root / "workspace" / "raw" / "example-work"
    raw_dir.mkdir(parents=True)
    # Only a crash-leftover temporary from an interrupted, unpinned fetch.
    (raw_dir / "example-work.txt.tmp").write_text(GUTENBERG_FILE, encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="example-work.txt"):
        prepare_work(root, "example-work", skip_fetch=True)


def test_skip_fetch_verifies_pinned_hash(tmp_path: Path) -> None:
    manifest = make_manifest(
        "example-work", **{"processing.extractor": "gutenberg_txt_v1"}
    )  # helper default hash does not match the synthetic raw file
    root = make_root(tmp_path, [(manifest, None)])
    _write_raw(root, manifest)
    with pytest.raises(ValueError, match="hash mismatch"):
        prepare_work(root, "example-work", skip_fetch=True)


def test_fetch_uses_download_url_and_project_user_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = make_manifest(
        "example-work",
        **{
            "source.provider": "gutenberg",
            "source.identifier": "999",
            "source.url": "https://www.gutenberg.org/ebooks/999",
            "source.download_url": "https://www.gutenberg.org/cache/epub/999/pg999.txt",
            "processing.source_sha256": GUTENBERG_SHA256,
        },
    )
    root = make_root(tmp_path, [(manifest, None)])
    seen = _fake_network(monkeypatch, GUTENBERG_FILE.encode("utf-8"))

    raw_path = fetch_source(root, manifest)

    assert seen["url"] == "https://www.gutenberg.org/cache/epub/999/pg999.txt"
    assert "open-fiction-corpus" in seen["user_agent"]
    # The remote basename is ignored: the local name derives from the work id.
    assert raw_path.name == "example-work.txt"
    assert raw_path.read_text(encoding="utf-8") == GUTENBERG_FILE
    sidecar = json.loads(
        (raw_path.parent / "example-work.txt.provenance.json").read_text(encoding="utf-8")
    )
    assert sidecar["identifier"] == "999"
    assert sidecar["sha256"] == GUTENBERG_SHA256


def test_fetch_hash_mismatch_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = make_manifest(
        "example-work",
        **{
            "source.provider": "gutenberg",
            "source.identifier": "999",
            "source.url": "https://www.gutenberg.org/ebooks/999",
            "source.download_url": "https://www.gutenberg.org/cache/epub/999/pg999.txt",
            "processing.source_sha256": "f" * 64,
        },
    )
    root = make_root(tmp_path, [(manifest, None)])
    _fake_network(monkeypatch, GUTENBERG_FILE.encode("utf-8"))

    with pytest.raises(ValueError, match="hash mismatch"):
        fetch_source(root, manifest)

    raw_dir = root / "workspace" / "raw" / "example-work"
    assert not raw_dir.exists() or list(raw_dir.iterdir()) == []


@pytest.mark.parametrize(
    "url",
    [
        "https://localhost/pg999.txt",
        "https://127.0.0.1/pg999.txt",
        "https://192.168.1.10/pg999.txt",
        "https://evil.example/pg999.txt",
        "http://www.gutenberg.org/cache/epub/999/pg999.txt",
        "https://www.gutenberg.org:8443/cache/epub/999/pg999.txt",
    ],
)
def test_fetch_rejects_unapproved_origins(tmp_path: Path, url: str) -> None:
    manifest = make_manifest(
        "example-work",
        **{"source.provider": "gutenberg", "source.download_url": url},
    )
    root = make_root(tmp_path, [(manifest, None)])
    with pytest.raises(ValueError, match="approved 'gutenberg' host"):
        fetch_source(root, manifest)


def test_redirects_to_unapproved_locations_are_refused() -> None:
    from open_fiction_corpus.prepare import _ApprovedRedirects

    path = "/cache/epub/35/pg35.txt"
    handler = _ApprovedRedirects(frozenset({"www.gutenberg.org", "gutenberg.org"}), path)
    request = urllib.request.Request(f"https://www.gutenberg.org{path}")
    for bad in [
        "https://evil.example" + path,
        "http://www.gutenberg.org" + path,
        "https://www.gutenberg.org:8443" + path,
        # Same approved host but a different artifact path.
        "https://www.gutenberg.org/cache/epub/2701/pg2701.txt",
        # Same path but a query string sneaks in.
        f"https://www.gutenberg.org{path}?evil=1",
    ]:
        with pytest.raises(ValueError, match="unapproved location"):
            handler.redirect_request(request, None, 302, "Found", {}, bad)
    allowed = handler.redirect_request(
        request, None, 302, "Found", {}, f"https://gutenberg.org{path}"
    )
    assert allowed.full_url == f"https://gutenberg.org{path}"


def test_fetch_rejects_oversized_downloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from open_fiction_corpus import prepare as prepare_module

    manifest = make_manifest(
        "example-work",
        **{
            "source.provider": "gutenberg",
            "source.identifier": "999",
            "source.url": "https://www.gutenberg.org/ebooks/999",
            "source.download_url": "https://www.gutenberg.org/cache/epub/999/pg999.txt",
            "processing.source_sha256": None,
        },
    )
    root = make_root(tmp_path, [(manifest, None)])
    monkeypatch.setattr(prepare_module, "_MAX_DOWNLOAD_BYTES", 8)
    _fake_network(monkeypatch, b"more than eight bytes")

    with pytest.raises(ValueError, match="download limit"):
        fetch_source(root, manifest)

    raw_dir = root / "workspace" / "raw" / "example-work"
    assert not raw_dir.exists() or list(raw_dir.iterdir()) == []


def test_fetch_rejects_urls_not_bound_to_the_identifier(tmp_path: Path) -> None:
    # Hostile basenames and identifier/URL mismatches both fail the binding
    # check before any network request; local paths never use the remote name.
    for bad_url in [
        "https://www.gutenberg.org/a/..%5C..%5CCON.txt",
        "https://www.gutenberg.org/cache/epub/2701/pg2701.txt",
    ]:
        manifest = make_manifest(
            "example-work",
            **{
                "source.provider": "gutenberg",
                "source.identifier": "999",
                "source.url": "https://www.gutenberg.org/ebooks/999",
                "source.download_url": bad_url,
            },
        )
        root = make_root(tmp_path / bad_url[-9:-4], [(manifest, None)])
        with pytest.raises(ValueError, match="pg999"):
            fetch_source(root, manifest)


def test_skip_fetch_rejects_stale_source_provenance(tmp_path: Path) -> None:
    gutenberg_999 = {
        "source.provider": "gutenberg",
        "source.identifier": "999",
        "source.url": "https://www.gutenberg.org/ebooks/999",
        "source.download_url": "https://www.gutenberg.org/cache/epub/999/pg999.txt",
        "processing.extractor": "gutenberg_txt_v1",
        "processing.source_sha256": None,
    }
    manifest = make_manifest("example-work", **gutenberg_999)
    root = make_root(tmp_path, [(manifest, None)])
    _write_raw(root, manifest)

    # The manifest moves to a different ebook while the old, unpinned raw
    # file is still on disk.
    from helpers import write_manifest

    changed = make_manifest(
        "example-work",
        **{
            **gutenberg_999,
            "source.identifier": "1000",
            "source.url": "https://www.gutenberg.org/ebooks/1000",
            "source.download_url": "https://www.gutenberg.org/cache/epub/1000/pg1000.txt",
        },
    )
    write_manifest(root, changed)

    with pytest.raises(ValueError, match="provenance does not match"):
        prepare_work(root, "example-work", skip_fetch=True)


def test_skip_fetch_runs_provider_preflight(tmp_path: Path) -> None:
    """A stale raw+sidecar must not be preparable once the manifest's
    provider-bound fields (e.g. the landing URL) are made invalid."""
    gutenberg_999 = {
        "source.provider": "gutenberg",
        "source.identifier": "999",
        "source.url": "https://www.gutenberg.org/ebooks/999",
        "source.download_url": "https://www.gutenberg.org/cache/epub/999/pg999.txt",
        "processing.extractor": "gutenberg_txt_v1",
        "processing.source_sha256": None,
    }
    manifest = make_manifest("example-work", **gutenberg_999)
    root = make_root(tmp_path, [(manifest, None)])
    _write_raw(root, manifest)

    from helpers import write_manifest

    changed = make_manifest(
        "example-work",
        **{**gutenberg_999, "source.url": "https://evil.example/ebooks/999"},
    )
    write_manifest(root, changed)

    with pytest.raises(ValueError, match="landing page"):
        prepare_work(root, "example-work", skip_fetch=True)


def test_skip_fetch_requires_provenance_sidecar(tmp_path: Path) -> None:
    manifest = make_manifest(
        "example-work", **{"processing.source_sha256": None}
    )
    root = make_root(tmp_path, [(manifest, None)])
    raw_dir = root / "workspace" / "raw" / "example-work"
    raw_dir.mkdir(parents=True)
    (raw_dir / "example-work.txt").write_text(GUTENBERG_FILE, encoding="utf-8")

    with pytest.raises(ValueError, match="provenance sidecar"):
        prepare_work(root, "example-work", skip_fetch=True)


def test_gutenberg_binding_requires_exact_landing_page_and_txt(tmp_path: Path) -> None:
    from open_fiction_corpus.prepare import gutenberg_artifact_error

    base = {
        "provider": "gutenberg",
        "identifier": "35",
        "format": "txt",
        "url": "https://www.gutenberg.org/ebooks/35",
        "download_url": "https://www.gutenberg.org/cache/epub/35/pg35.txt",
        "revision": "r",
    }
    assert gutenberg_artifact_error(base) is None

    for change, expected in [
        ({"url": "https://evil.example/ebooks/35"}, "landing page"),
        ({"url": "http://www.gutenberg.org/ebooks/35"}, "landing page"),
        ({"url": None}, "landing page"),
        ({"url": "https://www.gutenberg.org/ebooks/35?x=1"}, "landing page"),
        ({"format": "epub"}, "format: txt"),
        (
            {"download_url": "https://www.gutenberg.org/cache/epub/35/pg35.epub"},
            "pg35.txt",
        ),
        (
            {"download_url": "https://www.gutenberg.org/cache/epub/35/pg35.txt?x=1"},
            "no query",
        ),
    ]:
        error = gutenberg_artifact_error({**base, **change})
        assert error is not None and expected in error, (change, error)


def test_extractor_format_compatibility_is_enforced(tmp_path: Path) -> None:
    from open_fiction_corpus.validate import collect_errors

    # A non-Gutenberg provider escapes the Gutenberg binding, but the
    # extractor still cannot consume a binary EPUB.
    manifest = make_manifest(
        "epub-book-en",
        **{
            "source.provider": "manual-scan",
            "source.format": "epub",
            "processing.extractor": "plain_text_v1",
        },
    )
    root = make_root(tmp_path, [(manifest, None)])

    joined = "\n".join(collect_errors(root))
    assert "cannot consume source format 'epub'" in joined

    raw_dir = root / "workspace" / "raw" / "epub-book-en"
    raw_dir.mkdir(parents=True)
    (raw_dir / "epub-book-en.epub").write_text("fake", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot consume source format"):
        prepare_work(root, "epub-book-en", skip_fetch=True)


def test_prepare_rejects_provider_incompatible_extractor(tmp_path: Path) -> None:
    manifest = make_manifest(
        "example-work",
        **{
            "source.provider": "gutenberg",
            "source.identifier": "999",
            "source.url": "https://www.gutenberg.org/ebooks/999",
            "source.download_url": "https://www.gutenberg.org/cache/epub/999/pg999.txt",
            "processing.extractor": "plain_text_v1",
        },
    )
    root = make_root(tmp_path, [(manifest, None)])
    with pytest.raises(ValueError, match="requires an extractor"):
        prepare_work(root, "example-work", skip_fetch=True)


def test_prepare_rejects_invalid_or_mismatched_work_ids(tmp_path: Path) -> None:
    from helpers import write_manifest

    manifest = make_manifest("example-work")
    root = make_root(tmp_path, [(manifest, None)])

    with pytest.raises(ValueError, match="Invalid work id"):
        prepare_work(root, "../evil")

    # A well-named manifest file whose id tries to traverse out of workspace/.
    traversal = make_manifest("example-work")
    traversal["id"] = "../../docs/cleaning-guide"
    write_manifest(root, traversal, filename="safe.yaml")
    with pytest.raises(ValueError, match="does not match"):
        prepare_work(root, "safe")


def test_raw_source_path_rejects_hostile_manifests(tmp_path: Path) -> None:
    from open_fiction_corpus.prepare import raw_source_path

    traversal = make_manifest("example-work")
    traversal["id"] = "../../docs/cleaning-guide"
    with pytest.raises(ValueError, match="Invalid work id"):
        raw_source_path(tmp_path, traversal)

    bad_format = make_manifest("example-work", **{"source.format": "pdf"})
    with pytest.raises(ValueError, match="unknown source format"):
        raw_source_path(tmp_path, bad_format)


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
        "slash-book-en",
        **{
            "source.provider": "manual-scan",
            "source.download_url": "https://example.invalid/dir/",
        },
    )
    unapproved = make_manifest(
        "unapproved-book-en",
        **{
            "source.provider": "gutenberg",
            "source.download_url": "https://evil.example/pg35.txt",
        },
    )
    odd_port = make_manifest(
        "odd-port-book-en",
        **{
            "source.provider": "gutenberg",
            "source.download_url": "https://www.gutenberg.org:8443/pg35.txt",
        },
    )
    mismatch = make_manifest(
        "mismatch-book-en",
        **{
            "source.provider": "gutenberg",
            "source.identifier": "35",
            "source.url": "https://www.gutenberg.org/ebooks/35",
            "source.download_url": "https://www.gutenberg.org/cache/epub/2701/pg2701.txt",
        },
    )
    root = make_root(
        tmp_path,
        [
            (missing, None),
            (trailing_slash, None),
            (unapproved, None),
            (odd_port, None),
            (mismatch, None),
        ],
    )

    joined = "\n".join(collect_errors(root))
    assert "source.download_url is required for provider 'gutenberg'" in joined
    assert "source.download_url must end in a file name" in joined
    # Both the foreign host and the nonstandard port fail the origin check.
    assert joined.count("approved 'gutenberg' host") == 2
    assert "on port 443" in joined
    # The identifier is bound to the artifact path.
    assert "/cache/epub/35/pg35" in joined


def test_failed_prepare_preserves_existing_clean_text(tmp_path: Path) -> None:
    manifest = make_manifest(
        "example-work",
        **{
            "processing.extractor": "gutenberg_txt_v1",
            "processing.source_sha256": GUTENBERG_SHA256,
        },
    )
    root = make_root(tmp_path, [(manifest, "previously valid clean text")])
    _write_raw(root, manifest)
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
