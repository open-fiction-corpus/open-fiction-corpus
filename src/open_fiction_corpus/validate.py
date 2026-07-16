from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml
from jsonschema import Draft202012Validator


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError("top-level value must be a mapping")
    return value


def _append_schema_errors(
    errors: list[str], path: Path, validator: Draft202012Validator, document: dict[str, Any]
) -> None:
    for error in sorted(validator.iter_errors(document), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"{path}:{location}: {error.message}")


def _is_absolute_http_url(value: str) -> bool:
    if not value or any(character.isspace() for character in value):
        return False
    try:
        parsed = urlsplit(value)
        # Accessing port catches malformed values such as https://example.test:not-a-port/.
        _ = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.netloc)
        and parsed.hostname is not None
    )


def _string_set(value: object) -> set[str] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return set(value)


def validate_repository(root: Path) -> bool:
    root = root.resolve()
    errors: list[str] = []

    schema_path = root / "schema" / "work.schema.json"
    pack_schema_path = root / "schema" / "pack.schema.json"
    genres_path = root / "schema" / "genres.yaml"
    rights_path = root / "schema" / "rights-statuses.yaml"
    flags_path = root / "schema" / "quality-flags.yaml"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    pack_schema = json.loads(pack_schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    pack_validator = Draft202012Validator(pack_schema)
    genres_doc = _load_yaml(genres_path)
    rights_doc = _load_yaml(rights_path)
    flags_doc = _load_yaml(flags_path)

    genres = set(genres_doc.get("genres", {}))
    subgenres = {
        item
        for details in genres_doc.get("genres", {}).values()
        if isinstance(details, dict)
        for item in details.get("subgenres", [])
    }
    rights_statuses = set(rights_doc.get("rights_statuses", {}))
    for status_name, details in rights_doc.get("rights_statuses", {}).items():
        if not isinstance(details, dict) or not isinstance(details.get("releasable"), bool):
            errors.append(
                f"{rights_path}: rights status '{status_name}' must declare releasable: true|false"
            )
    quality_flags = set(flags_doc.get("quality_flags", []))

    work_properties = schema.get("properties", {})
    forms = set(work_properties.get("form", {}).get("enum", []))
    quality_statuses = set(
        work_properties.get("quality", {}).get("properties", {}).get("status", {}).get("enum", [])
    )
    content_origins = set(
        work_properties.get("content", {}).get("properties", {}).get("origin", {}).get("enum", [])
    )

    seen_ids: dict[str, Path] = {}
    manifest_paths = sorted((root / "catalog" / "works").glob("*.yaml"))

    for path in manifest_paths:
        try:
            manifest = _load_yaml(path)
        except Exception as exc:
            errors.append(f"{path}: cannot parse YAML: {exc}")
            continue

        _append_schema_errors(errors, path, validator, manifest)

        work_id = manifest.get("id")
        if isinstance(work_id, str):
            if path.stem != work_id:
                errors.append(f"{path}: filename must match id '{work_id}.yaml'")
            if work_id in seen_ids:
                errors.append(f"{path}: duplicate id also used by {seen_ids[work_id]}")
            seen_ids[work_id] = path

        source = manifest.get("source")
        if isinstance(source, dict):
            source_url = source.get("url")
            if isinstance(source_url, str) and not _is_absolute_http_url(source_url):
                errors.append(f"{path}: source.url must be an absolute http(s) URL")

        classification = manifest.get("classification")
        if isinstance(classification, dict):
            work_genres = _string_set(classification.get("genres"))
            primary_genre = classification.get("primary_genre")
            if work_genres is not None:
                unknown_genres = work_genres - genres
                if unknown_genres:
                    errors.append(f"{path}: unknown genres: {sorted(unknown_genres)}")
                if isinstance(primary_genre, str) and primary_genre not in work_genres:
                    errors.append(f"{path}: primary_genre must also appear in genres")
            if isinstance(primary_genre, str) and primary_genre not in genres:
                errors.append(f"{path}: unknown primary_genre: {primary_genre!r}")

            work_subgenres = _string_set(classification.get("subgenres"))
            if work_subgenres is not None:
                unknown_subgenres = work_subgenres - subgenres
                if unknown_subgenres:
                    errors.append(f"{path}: unknown subgenres: {sorted(unknown_subgenres)}")

        rights = manifest.get("rights")
        if isinstance(rights, dict):
            status = rights.get("status")
            if isinstance(status, str) and status not in rights_statuses:
                errors.append(f"{path}: unknown rights status: {status!r}")

        quality = manifest.get("quality")
        if isinstance(quality, dict):
            work_flags = _string_set(quality.get("flags"))
            if work_flags is not None:
                unknown_flags = work_flags - quality_flags
                if unknown_flags:
                    errors.append(f"{path}: unknown quality flags: {sorted(unknown_flags)}")

    seen_pack_names: dict[str, Path] = {}
    for pack_path in sorted((root / "packs").rglob("*.yaml")):
        try:
            pack = _load_yaml(pack_path)
        except Exception as exc:
            errors.append(f"{pack_path}: cannot parse YAML: {exc}")
            continue

        _append_schema_errors(errors, pack_path, pack_validator, pack)

        pack_name = pack.get("name")
        if isinstance(pack_name, str):
            if pack_name in seen_pack_names:
                errors.append(
                    f"{pack_path}: duplicate pack name also used by {seen_pack_names[pack_name]}"
                )
            seen_pack_names[pack_name] = pack_path

        filters = pack.get("filters")
        if isinstance(filters, dict):
            requested_genres = _string_set(filters.get("genres_any"))
            if requested_genres is not None:
                unknown = requested_genres - genres
                if unknown:
                    errors.append(f"{pack_path}: unknown genres: {sorted(unknown)}")

            requested_forms = _string_set(filters.get("forms"))
            if requested_forms is not None:
                unknown = requested_forms - forms
                if unknown:
                    errors.append(f"{pack_path}: unknown forms: {sorted(unknown)}")

            requested_statuses = _string_set(filters.get("quality_status"))
            if requested_statuses is not None:
                unknown = requested_statuses - quality_statuses
                if unknown:
                    errors.append(f"{pack_path}: unknown quality statuses: {sorted(unknown)}")

            requested_origins = _string_set(filters.get("origin"))
            if requested_origins is not None:
                unknown = requested_origins - content_origins
                if unknown:
                    errors.append(f"{pack_path}: unknown content origins: {sorted(unknown)}")

        excluded_flags = _string_set(pack.get("exclude_flags"))
        if excluded_flags is not None:
            unknown = excluded_flags - quality_flags
            if unknown:
                errors.append(f"{pack_path}: unknown quality flags: {sorted(unknown)}")

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return False

    print(f"Validation passed: {len(manifest_paths)} work manifest(s).")
    return True
