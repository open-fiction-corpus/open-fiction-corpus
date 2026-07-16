from pathlib import Path

import pytest
import yaml

from open_fiction_corpus.build import build_dataset
from open_fiction_corpus.validate import validate_repository


def _write_yaml(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def _make_minimal_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()

    repo_root = Path(__file__).resolve().parents[1]
    for src in [
        "schema/work.schema.json",
        "schema/genres.yaml",
        "schema/rights-statuses.yaml",
        "schema/quality-flags.yaml",
    ]:
        src_path = repo_root / src
        dst_path = root / src
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        dst_path.write_text(src_path.read_text(encoding="utf-8"), encoding="utf-8")

    (root / "catalog" / "works").mkdir(parents=True)
    (root / "packs").mkdir(parents=True)
    return root


def _valid_pack() -> dict:
    return {
        "name": "test-pack",
        "description": "A valid test pack.",
        "version": "0.1.0",
        "filters": {
            "language": "en",
            "forms": ["novel", "novella"],
            "genres_any": ["science-fiction"],
            "quality_status": ["human-reviewed"],
            "origin": ["human"],
        },
        "exclude_flags": ["uncertain-rights"],
        "selection": {"max_works_per_author": 3},
    }


def test_repository_scaffold_is_valid() -> None:
    root = Path(__file__).resolve().parents[1]
    assert validate_repository(root)


def test_valid_pack_passes(tmp_path: Path) -> None:
    root = _make_minimal_repo(tmp_path)
    _write_yaml(root / "packs" / "valid.yaml", _valid_pack())
    assert validate_repository(root)


@pytest.mark.parametrize(
    ("field", "value", "expected_fragment"),
    [
        ("exclude_flags", ["not-a-flag"], "unknown exclude_flags"),
        (
            "filters",
            {
                "language": "en",
                "forms": ["novel"],
                "quality_status": ["not-a-status"],
                "origin": ["human"],
            },
            "unknown quality_status",
        ),
        (
            "filters",
            {
                "language": "en",
                "forms": ["not-a-form"],
                "quality_status": ["human-reviewed"],
                "origin": ["human"],
            },
            "unknown forms",
        ),
        (
            "filters",
            {
                "language": "en",
                "forms": ["novel"],
                "quality_status": ["human-reviewed"],
                "origin": ["not-an-origin"],
            },
            "unknown origin",
        ),
    ],
)
def test_invalid_pack_filter_field_fails(
    tmp_path: Path,
    field: str,
    value: object,
    expected_fragment: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _make_minimal_repo(tmp_path)
    pack = _valid_pack()
    pack[field] = value
    _write_yaml(root / "packs" / "invalid.yaml", pack)

    assert not validate_repository(root)
    assert expected_fragment in capsys.readouterr().out


def test_invalid_pack_max_works_per_author_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _make_minimal_repo(tmp_path)
    pack = _valid_pack()
    pack["selection"]["max_works_per_author"] = 0
    _write_yaml(root / "packs" / "invalid.yaml", pack)

    assert not validate_repository(root)
    assert "selection.max_works_per_author" in capsys.readouterr().out


def test_missing_classification_reports_only_schema_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _make_minimal_repo(tmp_path)
    manifest = {
        "id": "test-work",
        "title": "Test Work",
        "language": "en",
        "form": "novel",
        "authors": [{"name": "A. Author"}],
        "publication": {"original_year": 1900},
        "source": {
            "provider": "test",
            "identifier": "test",
            "revision": "1",
            "format": "txt",
        },
        "rights": {
            "status": "public-domain",
            "verified_jurisdictions": ["US"],
            "evidence": ["test"],
            "notes": "test",
        },
        "content": {
            "origin": "human",
            "ai_assistance": "none",
            "original_language": "en",
            "is_translation": False,
        },
        "quality": {
            "status": "human-reviewed",
            "flags": [],
            "reviewed_by": ["test"],
        },
        "processing": {"extractor": "test", "cleaner": "test"},
    }
    _write_yaml(root / "catalog" / "works" / "test-work.yaml", manifest)

    assert not validate_repository(root)

    captured = capsys.readouterr().out
    assert "'classification' is a required property" in captured
    assert "primary_genre must also appear in genres" not in captured
    assert "unknown primary_genre" not in captured


def test_atomic_build_leaves_no_partial_output(tmp_path: Path) -> None:
    root = _make_minimal_repo(tmp_path)

    valid_manifest = {
        "id": "work-one",
        "title": "Work One",
        "language": "en",
        "form": "novel",
        "authors": [{"name": "A. Author"}],
        "publication": {"original_year": 1900},
        "source": {
            "provider": "test",
            "identifier": "test-one",
            "revision": "1",
            "format": "txt",
        },
        "rights": {
            "status": "public-domain",
            "verified_jurisdictions": ["US"],
            "evidence": ["test"],
            "notes": "test",
        },
        "classification": {
            "primary_genre": "science-fiction",
            "genres": ["science-fiction"],
            "subgenres": [],
            "audience": ["adult"],
        },
        "content": {
            "origin": "human",
            "ai_assistance": "none",
            "original_language": "en",
            "is_translation": False,
        },
        "quality": {
            "status": "human-reviewed",
            "flags": [],
            "reviewed_by": ["test"],
        },
        "processing": {
            "extractor": "test",
            "cleaner": "test",
            "expected_min_words": 1,
        },
    }
    failing_manifest = dict(valid_manifest)
    failing_manifest["id"] = "work-two"
    failing_manifest["source"]["identifier"] = "test-two"
    failing_manifest["processing"]["expected_min_words"] = 10_000

    _write_yaml(root / "catalog" / "works" / "work-one.yaml", valid_manifest)
    _write_yaml(root / "catalog" / "works" / "work-two.yaml", failing_manifest)

    clean_dir = root / "workspace" / "clean"
    clean_dir.mkdir(parents=True)
    (clean_dir / "work-one.txt").write_text("one two three", encoding="utf-8")
    (clean_dir / "work-two.txt").write_text("one two", encoding="utf-8")

    output_path = root / "dist" / "books.jsonl.gz"
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")

    with pytest.raises(ValueError):
        build_dataset(root)

    assert not output_path.exists()
    assert not temp_path.exists()
