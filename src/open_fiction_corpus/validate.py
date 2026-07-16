from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError("top-level value must be a mapping")
    return value


def validate_repository(root: Path) -> bool:
    root = root.resolve()
    errors: list[str] = []

    schema_path = root / "schema" / "work.schema.json"
    genres_path = root / "schema" / "genres.yaml"
    rights_path = root / "schema" / "rights-statuses.yaml"
    flags_path = root / "schema" / "quality-flags.yaml"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    genres_doc = _load_yaml(genres_path)
    rights_doc = _load_yaml(rights_path)
    flags_doc = _load_yaml(flags_path)

    genres = set(genres_doc.get("genres", {}))
    subgenres = {
        item
        for details in genres_doc.get("genres", {}).values()
        for item in details.get("subgenres", [])
    }
    rights_statuses = set(rights_doc.get("rights_statuses", {}))
    quality_flags = set(flags_doc.get("quality_flags", []))

    seen_ids: dict[str, Path] = {}
    manifest_paths = sorted((root / "catalog" / "works").glob("*.yaml"))

    for path in manifest_paths:
        try:
            manifest = _load_yaml(path)
        except Exception as exc:
            errors.append(f"{path}: cannot parse YAML: {exc}")
            continue

        for error in sorted(validator.iter_errors(manifest), key=lambda item: list(item.path)):
            location = ".".join(str(part) for part in error.path) or "<root>"
            errors.append(f"{path}:{location}: {error.message}")

        work_id = manifest.get("id")
        if isinstance(work_id, str):
            if path.stem != work_id:
                errors.append(f"{path}: filename must match id '{work_id}.yaml'")
            if work_id in seen_ids:
                errors.append(f"{path}: duplicate id also used by {seen_ids[work_id]}")
            seen_ids[work_id] = path

        classification = manifest.get("classification", {})
        work_genres = set(classification.get("genres", []))
        primary_genre = classification.get("primary_genre")
        unknown_genres = work_genres - genres
        if unknown_genres:
            errors.append(f"{path}: unknown genres: {sorted(unknown_genres)}")
        if primary_genre not in work_genres:
            errors.append(f"{path}: primary_genre must also appear in genres")
        if primary_genre not in genres:
            errors.append(f"{path}: unknown primary_genre: {primary_genre!r}")

        unknown_subgenres = set(classification.get("subgenres", [])) - subgenres
        if unknown_subgenres:
            errors.append(f"{path}: unknown subgenres: {sorted(unknown_subgenres)}")

        status = manifest.get("rights", {}).get("status")
        if status not in rights_statuses:
            errors.append(f"{path}: unknown rights status: {status!r}")

        unknown_flags = set(manifest.get("quality", {}).get("flags", [])) - quality_flags
        if unknown_flags:
            errors.append(f"{path}: unknown quality flags: {sorted(unknown_flags)}")

    for pack_path in sorted((root / "packs").rglob("*.yaml")):
        try:
            pack = _load_yaml(pack_path)
        except Exception as exc:
            errors.append(f"{pack_path}: cannot parse YAML: {exc}")
            continue
        requested = set(pack.get("filters", {}).get("genres_any", []))
        unknown = requested - genres
        if unknown:
            errors.append(f"{pack_path}: unknown genres: {sorted(unknown)}")

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return False

    print(f"Validation passed: {len(manifest_paths)} work manifest(s).")
    return True
