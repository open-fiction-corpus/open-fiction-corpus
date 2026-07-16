"""Shared fixture builders for the test suite."""

from __future__ import annotations

import copy
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
    expected_min_words defaults to 3 so tests can use short texts.
    """
    manifest = copy.deepcopy(BASE_MANIFEST)
    manifest["id"] = work_id
    manifest["processing"]["expected_min_words"] = 3
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
        write_manifest(root, manifest)
        if text is not None:
            text_path = root / "workspace" / "clean" / f"{manifest['id']}.txt"
            text_path.write_text(text, encoding="utf-8")
    return root
