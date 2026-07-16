from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
from typing import Any

import yaml

from .validate import validate_repository


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level value must be a mapping")
    return value


def _dataset_row(manifest: dict[str, Any], text: str) -> dict[str, Any]:
    return {
        "id": manifest["id"],
        "title": manifest["title"],
        "authors": [person["name"] for person in manifest["authors"]],
        "language": manifest["language"],
        "form": manifest["form"],
        "primary_genre": manifest["classification"]["primary_genre"],
        "genres": manifest["classification"]["genres"],
        "subgenres": manifest["classification"]["subgenres"],
        "rights_status": manifest["rights"]["status"],
        "quality_status": manifest["quality"]["status"],
        "source_provider": manifest["source"]["provider"],
        "source_identifier": manifest["source"]["identifier"],
        "source_revision": manifest["source"]["revision"],
        "text": text,
    }


def build_dataset(root: Path, *, allow_missing_text: bool = False) -> None:
    root = root.resolve()
    if not validate_repository(root):
        raise SystemExit("Cannot build an invalid catalogue.")

    output_dir = root / "dist"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "books.jsonl.gz"
    manifests = sorted((root / "catalog" / "works").glob("*.yaml"))

    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    written = 0
    try:
        with gzip.open(temp_path, "wt", encoding="utf-8", newline="\n") as output:
            for manifest_path in manifests:
                manifest = _load_yaml(manifest_path)
                text_path = root / "workspace" / "clean" / f"{manifest['id']}.txt"
                if not text_path.exists():
                    if allow_missing_text:
                        continue
                    raise FileNotFoundError(
                        f"Missing cleaned text for {manifest['id']}: {text_path}"
                    )
                text = text_path.read_text(encoding="utf-8").strip()
                minimum = manifest.get("processing", {}).get("expected_min_words")
                if minimum and len(text.split()) < minimum:
                    raise ValueError(f"{manifest['id']} has fewer than expected {minimum} words")
                output.write(json.dumps(_dataset_row(manifest, text), ensure_ascii=False))
                output.write("\n")
                written += 1
        os.replace(temp_path, output_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    print(f"Built {written} whole-book row(s): {output_path}")
