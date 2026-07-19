from pathlib import Path

import yaml
from helpers import BASE_MANIFEST, REPO_ROOT, make_manifest, make_root, write_manifest

from open_fiction_corpus.validate import collect_errors, validate_repository


def joined_errors(root: Path) -> str:
    return "\n".join(collect_errors(root))


def test_repository_scaffold_is_valid() -> None:
    assert validate_repository(REPO_ROOT)


def test_example_manifest_stays_valid_against_schema(tmp_path: Path) -> None:
    # The template contributors copy must never drift out of sync with the
    # schema or the controlled vocabularies.
    root = make_root(tmp_path)
    write_manifest(root, BASE_MANIFEST)
    assert collect_errors(root) == []


def test_valid_manifest_passes(tmp_path: Path) -> None:
    root = make_root(tmp_path, [(make_manifest("author-book-en"), None)])
    assert collect_errors(root) == []


def test_schema_violation_is_reported_with_location(tmp_path: Path) -> None:
    manifest = make_manifest("author-book-en", title="")
    root = make_root(tmp_path, [(manifest, None)])
    assert "title" in joined_errors(root)


def test_bad_language_code(tmp_path: Path) -> None:
    manifest = make_manifest("author-book-en", language="English")
    root = make_root(tmp_path, [(manifest, None)])
    assert "language" in joined_errors(root)


def test_filename_must_match_id(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    write_manifest(root, make_manifest("author-book-en"), filename="other-name.yaml")
    assert "filename must match id 'author-book-en.yaml'" in joined_errors(root)


def test_duplicate_ids_are_reported(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    manifest = make_manifest("author-book-en")
    write_manifest(root, manifest)
    write_manifest(root, manifest, filename="another-file.yaml")
    assert "duplicate id" in joined_errors(root)


def test_unknown_genre(tmp_path: Path) -> None:
    manifest = make_manifest(
        "author-book-en", **{"classification.genres": ["fantasy", "cyberpunk"]}
    )
    root = make_root(tmp_path, [(manifest, None)])
    assert "unknown genres: ['cyberpunk']" in joined_errors(root)


def test_unknown_primary_genre(tmp_path: Path) -> None:
    manifest = make_manifest(
        "author-book-en",
        **{
            "classification.primary_genre": "cyberpunk",
            "classification.genres": ["cyberpunk"],
            "classification.subgenres": [],
        },
    )
    root = make_root(tmp_path, [(manifest, None)])
    assert "unknown primary_genre: 'cyberpunk'" in joined_errors(root)


def test_primary_genre_must_appear_in_genres(tmp_path: Path) -> None:
    manifest = make_manifest(
        "author-book-en",
        **{"classification.primary_genre": "romance", "classification.subgenres": []},
    )
    root = make_root(tmp_path, [(manifest, None)])
    assert "primary_genre must also appear in genres" in joined_errors(root)


def test_unknown_subgenre(tmp_path: Path) -> None:
    manifest = make_manifest(
        "author-book-en", **{"classification.subgenres": ["grimdark-noir"]}
    )
    root = make_root(tmp_path, [(manifest, None)])
    assert "unknown subgenres: ['grimdark-noir']" in joined_errors(root)


def test_unknown_rights_status(tmp_path: Path) -> None:
    manifest = make_manifest("author-book-en", **{"rights.status": "probably-fine"})
    root = make_root(tmp_path, [(manifest, None)])
    assert "unknown rights status: 'probably-fine'" in joined_errors(root)


def test_unknown_quality_flag(tmp_path: Path) -> None:
    manifest = make_manifest("author-book-en", **{"quality.flags": ["smudged-pages"]})
    root = make_root(tmp_path, [(manifest, None)])
    assert "unknown quality flags: ['smudged-pages']" in joined_errors(root)


def test_unparseable_manifest_yaml(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    path = root / "catalog" / "works" / "broken-book-en.yaml"
    path.write_text("{unclosed: [mapping", encoding="utf-8")
    assert "cannot parse YAML" in joined_errors(root)


def test_non_mapping_manifest_yaml(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    path = root / "catalog" / "works" / "scalar-book-en.yaml"
    path.write_text("just a string\n", encoding="utf-8")
    assert "cannot parse YAML" in joined_errors(root)


def test_pack_with_unknown_genre(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    pack_path = root / "packs" / "genres" / "fantasy.yaml"
    pack = yaml.safe_load(pack_path.read_text(encoding="utf-8"))
    pack["filters"]["genres_any"] = ["fantasy", "cyberpunk"]
    pack_path.write_text(yaml.safe_dump(pack, sort_keys=False), encoding="utf-8")
    assert "unknown genres: ['cyberpunk']" in joined_errors(root)


def test_duplicate_pack_names_are_reported(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    original = root / "packs" / "genres" / "fantasy.yaml"
    copy_path = root / "packs" / "genres" / "fantasy-copy.yaml"
    copy_path.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
    assert "duplicate pack name" in joined_errors(root)


def test_rights_status_must_declare_releasable(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    rights_path = root / "schema" / "rights-statuses.yaml"
    doc = yaml.safe_load(rights_path.read_text(encoding="utf-8"))
    del doc["rights_statuses"]["public-domain"]["releasable"]
    rights_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    assert "'public-domain' must declare releasable" in joined_errors(root)


def test_validate_repository_reports_failure(tmp_path: Path, capsys) -> None:
    manifest = make_manifest("author-book-en", **{"rights.status": "probably-fine"})
    root = make_root(tmp_path, [(manifest, None)])
    assert validate_repository(root) is False
    captured = capsys.readouterr()
    assert "Validation failed:" in captured.out
    assert "unknown rights status" in captured.out


def test_pack_work_id_lists_are_validated(tmp_path: Path) -> None:
    root = make_root(tmp_path, [(make_manifest("known-book-en"), None)])
    pack = {
        "name": "sampler",
        "description": "Hand-curated test pack.",
        "version": "0.1.0",
        "filters": {"language": "en"},
        "include_works": ["known-book-en", "ghost-book-en"],
        "exclude_works": ["known-book-en"],
    }
    (root / "packs" / "sampler.yaml").write_text(
        yaml.safe_dump(pack, sort_keys=False), encoding="utf-8"
    )

    errors = joined_errors(root)
    assert "include_works lists unknown work ids: ['ghost-book-en']" in errors
    assert (
        "work ids in both include_works and exclude_works: ['known-book-en']" in errors
    )
