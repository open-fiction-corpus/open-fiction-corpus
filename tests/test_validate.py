from pathlib import Path

from open_fiction_corpus.validate import validate_repository


def test_repository_scaffold_is_valid() -> None:
    root = Path(__file__).resolve().parents[1]
    assert validate_repository(root)
