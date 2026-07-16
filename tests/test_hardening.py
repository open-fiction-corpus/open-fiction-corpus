from __future__ import annotations

import copy
import gzip
import json
import shutil
from pathlib import Path

import pytest
import yaml

from open_fiction_corpus.build import build_dataset
from open_fiction_corpus.validate import validate_repository

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_MANIFEST = yaml.safe_load(
    (REPO_ROOT / "catalog" / "examples" / "example-work.yaml").read_text(encoding="utf-8")
)


def make_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / "schema", root / "schema")
    shutil.copytree(REPO_ROOT / "packs", root / "packs")
    (root / "catalog" / "works").mkdir(parents=True)
    (root / "workspace" / "clean").mkdir(parents=True)
    return root


def write_manifest(root: Path, manifest: dict) -> Path:
    path = root / "catalog" / "works" / f"{manifest['id']}.yaml"
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return path


def manifest(work_id: str = "example-book-en") -> dict:
    value = copy.deepcopy(BASE_MANIFEST)
    value["id"] = work_id
    value["processing"]["expected_min_words"] = 3
    return value


@pytest.mark.parametrize(
    "bad_url",
    [
        "not a url at all",
        "/relative/path",
        "ftp://example.test/book.txt",
        "https://",
        "https://example.test/a path",
        "https://example.test:not-a-port/book",
    ],
)
def test_validate_rejects_invalid_source_urls(tmp_path: Path, capsys, bad_url: str) -> None:
    root = make_root(tmp_path)
    value = manifest()
    value["source"]["url"] = bad_url
    write_manifest(root, value)

    assert not validate_repository(root)
    assert "source.url must be an absolute http(s) URL" in capsys.readouterr().out


def test_validate_accepts_absolute_https_source_url(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    write_manifest(root, manifest())
    assert validate_repository(root)


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (("exclude_flags", ["typo-flag"]), "unknown quality flags"),
        (("filters.forms", ["screenplay"]), "unknown forms"),
        (("filters.quality_status", ["approved"]), "unknown quality statuses"),
        (("filters.origin", ["synthetic"]), "unknown content origins"),
        (("selection.max_works_per_author", 0), "less than the minimum of 1"),
    ],
)
def test_validate_rejects_bad_pack_fields(tmp_path: Path, capsys, mutation, expected: str) -> None:
    root = make_root(tmp_path)
    pack_path = root / "packs" / "general-fiction.yaml"
    pack = yaml.safe_load(pack_path.read_text(encoding="utf-8"))
    dotted, replacement = mutation
    target = pack
    *parents, leaf = dotted.split(".")
    for parent in parents:
        target = target[parent]
    target[leaf] = replacement
    pack_path.write_text(yaml.safe_dump(pack, sort_keys=False), encoding="utf-8")

    assert not validate_repository(root)
    assert expected in capsys.readouterr().out


def test_missing_classification_does_not_emit_secondary_vocabulary_errors(
    tmp_path: Path, capsys
) -> None:
    root = make_root(tmp_path)
    value = manifest()
    value.pop("classification")
    write_manifest(root, value)

    assert not validate_repository(root)
    output = capsys.readouterr().out
    assert "'classification' is a required property" in output
    assert "primary_genre must also appear" not in output
    assert "unknown primary_genre" not in output


def test_failed_build_preserves_previous_output(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    value = manifest()
    value["quality"]["status"] = "human-reviewed"
    path = write_manifest(root, value)
    text_path = root / "workspace" / "clean" / f"{value['id']}.txt"
    text_path.write_text("three valid words", encoding="utf-8")

    build_dataset(root)
    output_path = root / "dist" / "books.jsonl.gz"
    original = output_path.read_bytes()
    with gzip.open(output_path, "rt", encoding="utf-8") as handle:
        assert json.loads(next(handle))["id"] == value["id"]

    value["processing"]["expected_min_words"] = 100
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="fewer than expected"):
        build_dataset(root)

    assert output_path.read_bytes() == original
    assert list((root / "dist").glob(".books.jsonl.gz.*.tmp")) == []
