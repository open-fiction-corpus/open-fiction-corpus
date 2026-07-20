"""Shared fixture builders for the test suite."""

from __future__ import annotations

import copy
import hashlib
import shutil
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

BASE_MANIFEST = yaml.safe_load(
    (REPO_ROOT / "catalog" / "examples" / "example-work.yaml").read_text(encoding="utf-8")
)


def make_manifest(work_id: str, **overrides: Any) -> dict[str, Any]:
    """Return a copy of the example manifest with a new id and dotted-path overrides.

    Overrides use dotted keys, e.g. make_manifest("x", **{"rights.status": "uncertain"}).
    expected_min_words defaults to 3 so tests can use short texts, and the
    manifest defaults to release-ready: human-reviewed, pinned, hashed, and
    a fully valid gutenberg source (release readiness requires a provider
    with a fetch adapter). Tests opt out via overrides.
    """
    manifest = copy.deepcopy(BASE_MANIFEST)
    manifest["id"] = work_id
    manifest["source"]["provider"] = "gutenberg"
    manifest["source"]["identifier"] = "999"
    manifest["source"]["url"] = "https://www.gutenberg.org/ebooks/999"
    manifest["source"]["download_url"] = "https://www.gutenberg.org/cache/epub/999/pg999.txt"
    manifest["processing"]["extractor"] = "gutenberg_txt_v1"
    manifest["processing"]["expected_min_words"] = 3
    manifest["processing"]["source_sha256"] = "0" * 64
    manifest["quality"]["status"] = "human-reviewed"
    manifest["quality"]["reviewed_by"] = ["test-reviewer"]
    for dotted, value in overrides.items():
        target = manifest
        *parents, leaf = dotted.split(".")
        for key in parents:
            target = target[key]
        target[leaf] = value
    return manifest


def write_manifest(root: Path, manifest: dict[str, Any], filename: str | None = None) -> Path:
    path = root / "catalog" / "works" / (filename or f"{manifest['id']}.yaml")
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return path


def make_root(
    tmp_path: Path, works: list[tuple[dict[str, Any], str | None]] = ()
) -> Path:
    """Clone the repository scaffold (schema + packs) into a temp root.

    works is a list of (manifest, text) pairs; text may be None to omit the
    cleaned text file.
    """
    root = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / "schema", root / "schema")
    shutil.copytree(REPO_ROOT / "packs", root / "packs")
    (root / "catalog" / "works").mkdir(parents=True)
    (root / "workspace" / "clean").mkdir(parents=True)
    for manifest, text in works:
        if text is not None and manifest["quality"].get("reviewed_text_sha256") is None:
            # Bind the fixture's review approval to its own text, matching
            # what a real reviewer records after inspecting the output.
            manifest["quality"]["reviewed_text_sha256"] = hashlib.sha256(
                text.encode("utf-8")
            ).hexdigest()
        write_manifest(root, manifest)
        if text is not None:
            text_path = root / "workspace" / "clean" / f"{manifest['id']}.txt"
            text_path.write_text(text, encoding="utf-8")
    return root
