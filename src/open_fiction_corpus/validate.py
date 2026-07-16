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

    form_values = set(schema["properties"]["form"]["enum"])
    quality_status_values = set(schema["properties"]["quality"]["properties"]["status"]["enum"])
    origin_values = set(schema["properties"]["content"]["properties"]["origin"]["enum"])

    seen_ids: dict[str, Path] = {}
    manifest_paths = sorted((root / "catalog" / "works").glob("*.yaml"))

    for path in manifest_paths:
        try:
            manifest = _load_yaml(path)
        except Exception as exc:
            errors.append(f"{path}: cannot parse YAML: {exc}")
            continue

        schema_errors = sorted(validator.iter_errors(manifest), key=lambda item: list(item.path))
        schema_failed_sections = {error.path[0] for error in schema_errors if error.path}
        for error in schema_errors:
            if error.validator == "required" and "classification" in error.validator_value:
                schema_failed_sections.add("classification")
        for error in schema_errors:
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
        if "classification" not in schema_failed_sections:
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

        filters = pack.get("filters", {})

        requested = set(filters.get("genres_any", []))
        unknown = requested - genres
        if unknown:
            errors.append(f"{pack_path}: unknown genres: {sorted(unknown)}")

        requested_forms = set(filters.get("forms", []))
        unknown_forms = requested_forms - form_values
        if unknown_forms:
            errors.append(f"{pack_path}: unknown forms: {sorted(unknown_forms)}")

        requested_quality_status = set(filters.get("quality_status", []))
        unknown_quality_status = requested_quality_status - quality_status_values
        if unknown_quality_status:
            errors.append(f"{pack_path}: unknown quality_status: {sorted(unknown_quality_status)}")

        requested_origin = set(filters.get("origin", []))
        unknown_origin = requested_origin - origin_values
        if unknown_origin:
            errors.append(f"{pack_path}: unknown origin: {sorted(unknown_origin)}")

        requested_flags = set(pack.get("exclude_flags", []))
        unknown_flags = requested_flags - quality_flags
        if unknown_flags:
            errors.append(f"{pack_path}: unknown exclude_flags: {sorted(unknown_flags)}")

        max_works = pack.get("selection", {}).get("max_works_per_author")
        if max_works is not None and (
            not isinstance(max_works, int) or isinstance(max_works, bool) or max_works < 1
        ):
            errors.append(
                f"{pack_path}: selection.max_works_per_author must be a positive integer, got {max_works!r}"
            )

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return False

    print(f"Validation passed: {len(manifest_paths)} work manifest(s).")
    return True
