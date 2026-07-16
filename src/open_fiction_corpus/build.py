from __future__ import annotations

import gzip
import json
import os
import tempfile
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


def _releasable_statuses(root: Path) -> set[str]:
    doc = _load_yaml(root / "schema" / "rights-statuses.yaml")
    statuses = {
        name
        for name, details in doc.get("rights_statuses", {}).items()
        if isinstance(details, dict) and details.get("releasable") is True
    }
    if not statuses:
        raise ValueError(
            "No rights status is marked releasable in schema/rights-statuses.yaml; "
            "refusing to build an empty release policy."
        )
    return statuses


def _find_pack(root: Path, name: str) -> dict[str, Any]:
    for path in sorted((root / "packs").rglob("*.yaml")):
        pack = _load_yaml(path)
        if pack.get("name") == name:
            return pack
    raise FileNotFoundError(f"No pack named '{name}' under {root / 'packs'}")


def _pack_selects(pack: dict[str, Any], manifest: dict[str, Any]) -> bool:
    filters = pack.get("filters", {})
    language = filters.get("language")
    if language and manifest["language"] != language:
        return False
    forms = filters.get("forms")
    if forms and manifest["form"] not in forms:
        return False
    genres_any = filters.get("genres_any")
    if genres_any and not set(genres_any) & set(manifest["classification"]["genres"]):
        return False
    quality_status = filters.get("quality_status")
    if quality_status and manifest["quality"]["status"] not in quality_status:
        return False
    origin = filters.get("origin")
    if origin and manifest["content"]["origin"] not in origin:
        return False
    excluded_flags = set(pack.get("exclude_flags", []))
    if excluded_flags & set(manifest["quality"].get("flags", [])):
        return False
    return True


def _apply_author_cap(
    manifests: list[dict[str, Any]], cap: int | None
) -> list[dict[str, Any]]:
    if not cap:
        return manifests
    counts: dict[str, int] = {}
    selected = []
    for manifest in manifests:
        names = [person["name"] for person in manifest["authors"]]
        if any(counts.get(name, 0) >= cap for name in names):
            continue
        for name in names:
            counts[name] = counts.get(name, 0) + 1
        selected.append(manifest)
    return selected


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


def build_dataset(
    root: Path, *, pack: str | None = None, allow_missing_text: bool = False
) -> None:
    root = root.resolve()
    if not validate_repository(root):
        raise SystemExit("Cannot build an invalid catalogue.")

    releasable = _releasable_statuses(root)
    manifests = [
        _load_yaml(path) for path in sorted((root / "catalog" / "works").glob("*.yaml"))
    ]

    # The rights gate is unconditional: no pack configuration can reintroduce
    # a work whose redistribution basis has not been accepted.
    gated = []
    for manifest in manifests:
        status = manifest["rights"]["status"]
        if status not in releasable:
            print(f"Skipping {manifest['id']}: rights status '{status}' is not releasable.")
            continue
        gated.append(manifest)

    if pack is not None:
        pack_doc = _find_pack(root, pack)
        gated = [manifest for manifest in gated if _pack_selects(pack_doc, manifest)]
        cap = pack_doc.get("selection", {}).get("max_works_per_author")
        gated = _apply_author_cap(gated, cap)

    output_dir = root / "dist"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (f"{pack}.jsonl.gz" if pack else "books.jsonl.gz")

    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=output_dir, prefix=f".{output_path.name}.", suffix=".tmp"
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)

    written = 0
    try:
        with gzip.open(temporary_path, "wt", encoding="utf-8", newline="\n") as output:
            for manifest in gated:
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
                    raise ValueError(
                        f"{manifest['id']} has fewer than expected {minimum} words"
                    )
                output.write(json.dumps(_dataset_row(manifest, text), ensure_ascii=False))
                output.write("\n")
                written += 1
        temporary_path.replace(output_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise

    print(f"Built {written} whole-book row(s): {output_path}")
