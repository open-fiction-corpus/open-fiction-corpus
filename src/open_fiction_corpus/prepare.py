"""Fetch, extract, clean, and modernise one work's source text.

`prepare_work` writes the canonical cleaned text to workspace/clean/<work-id>.txt,
reproducible from the pinned raw source plus the versioned extractor, cleaner,
and moderniser named in the manifest and the work-specific overrides file.
"""

from __future__ import annotations

import hashlib
import re
import urllib.request
from pathlib import Path
from typing import Any, Callable

import yaml


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level value must be a mapping")
    return value


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def gutenberg_source_url(identifier: str) -> str:
    return f"https://www.gutenberg.org/cache/epub/{identifier}/pg{identifier}.txt"


def fetch_source(root: Path, manifest: dict[str, Any]) -> Path:
    """Download the raw source into workspace/raw/<work-id>/ and verify its hash."""
    source = manifest["source"]
    provider = source["provider"]
    if provider != "gutenberg":
        raise ValueError(f"No fetcher for source provider '{provider}'")

    url = gutenberg_source_url(source["identifier"])
    raw_dir = root / "workspace" / "raw" / manifest["id"]
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / url.rsplit("/", 1)[-1]

    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    raw_path.write_bytes(data)

    digest = _sha256(data)
    pinned = manifest.get("processing", {}).get("source_sha256")
    if pinned is None:
        print(f"Fetched {url}")
        print(f"Unpinned source; record processing.source_sha256: {digest}")
    elif digest != pinned:
        raise ValueError(
            f"{manifest['id']}: source hash mismatch: expected {pinned}, got {digest}"
        )
    else:
        print(f"Fetched {url} (sha256 verified)")
    return raw_path


_GUTENBERG_CREDIT = re.compile(
    r"^\s*(produced by|e-?text prepared by|transcribed (by|from)|special thanks)", re.IGNORECASE
)


def extract_gutenberg_txt(raw_text: str) -> str:
    """Return the body between the Project Gutenberg start and end markers."""
    lines = raw_text.split("\n")
    starts = [i for i, line in enumerate(lines) if line.startswith("*** START OF")]
    ends = [i for i, line in enumerate(lines) if line.startswith("*** END OF")]
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise ValueError(
            "Expected exactly one Project Gutenberg '*** START OF' marker "
            "followed by one '*** END OF' marker"
        )
    body = "\n".join(lines[starts[0] + 1 : ends[0]]).strip("\n")

    # Drop leading transcriber-credit paragraphs without reflowing anything
    # else, so blank-line structure survives for the cleaner to interpret.
    while _GUTENBERG_CREDIT.match(body):
        gap = re.search(r"\n{2,}", body)
        if gap is None:
            return ""
        body = body[gap.end() :]
    return body


def clean_fiction(text: str) -> str:
    """Normalise whitespace and unwrap hard-wrapped prose paragraphs.

    Paragraph breaks become one blank line; larger gaps (section breaks in the
    transcription) are preserved as two blank lines. Emphasis markup, headings,
    spelling, and punctuation are left untouched.
    """
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    parts = re.split(r"(\n{2,})", text.strip("\n"))
    pieces: list[str] = []
    for part in parts:
        if part.startswith("\n"):
            pieces.append("\n\n" if part == "\n\n" else "\n\n\n")
        else:
            joined = " ".join(line.strip() for line in part.split("\n"))
            pieces.append(re.sub(r"[ \t]{2,}", " ", joined).strip())
    return "".join(pieces).strip() + "\n"


def _match_case(replacement: str, matched: str) -> str:
    if matched.isupper() and len(matched) > 1:
        return replacement.upper()
    if matched[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def modernize_spelling(text: str, root: Path) -> tuple[str, dict[str, int]]:
    """Apply the whole-word spelling rules from schema/modernization-rules.yaml.

    Replacements are case-preserving and reported per rule so every change is
    auditable. Grammar, vocabulary, dialect, and punctuation are never touched.
    """
    rules_path = root / "schema" / "modernization-rules.yaml"
    rules = _load_yaml(rules_path).get("rules", {})
    counts: dict[str, int] = {}
    for old, new in rules.items():
        if not isinstance(old, str) or not isinstance(new, str):
            raise ValueError(f"{rules_path}: rules must map strings to strings")
        pattern = re.compile(rf"\b{re.escape(old)}\b", re.IGNORECASE)
        text, count = pattern.subn(lambda match: _match_case(new, match.group(0)), text)
        if count:
            counts[old] = count
    return text, counts


def apply_overrides(text: str, overrides_path: Path) -> str:
    """Apply work-specific corrections, each with a note and an exact match count."""
    corrections = _load_yaml(overrides_path).get("corrections", [])
    for index, correction in enumerate(corrections):
        find = correction.get("find")
        replace = correction.get("replace")
        note = correction.get("note")
        if not isinstance(find, str) or not isinstance(replace, str) or not note:
            raise ValueError(
                f"{overrides_path}: correction {index} needs 'find', 'replace', and 'note'"
            )
        occurrences = text.count(find)
        expected = correction.get("count", 1)
        if occurrences != expected:
            raise ValueError(
                f"{overrides_path}: correction {find!r} matched {occurrences} "
                f"time(s), expected {expected}"
            )
        text = text.replace(find, replace)
    return text


EXTRACTORS: dict[str, Callable[[str], str]] = {
    "gutenberg_txt_v1": extract_gutenberg_txt,
}

CLEANERS: dict[str, Callable[[str], str]] = {
    "fiction_clean_v1": clean_fiction,
}

MODERNIZERS: dict[str, Callable[[str, Path], tuple[str, dict[str, int]]]] = {
    "modernize_spelling_v1": modernize_spelling,
}


def _lookup(registry: dict[str, Any], name: str, kind: str) -> Any:
    if name not in registry:
        raise ValueError(f"Unknown {kind} '{name}'; known: {sorted(registry)}")
    return registry[name]


def prepare_work(root: Path, work_id: str, *, skip_fetch: bool = False) -> Path:
    root = root.resolve()
    manifest_path = root / "catalog" / "works" / f"{work_id}.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest at {manifest_path}")
    manifest = _load_yaml(manifest_path)
    processing = manifest["processing"]

    if skip_fetch:
        raw_dir = root / "workspace" / "raw" / work_id
        raw_files = sorted(raw_dir.glob("*")) if raw_dir.exists() else []
        if len(raw_files) != 1:
            raise FileNotFoundError(
                f"--skip-fetch needs exactly one raw file under {raw_dir}"
            )
        raw_path = raw_files[0]
    else:
        raw_path = fetch_source(root, manifest)

    raw_text = raw_path.read_text(encoding="utf-8")
    extractor = _lookup(EXTRACTORS, processing["extractor"], "extractor")
    cleaner = _lookup(CLEANERS, processing["cleaner"], "cleaner")
    text = cleaner(extractor(raw_text))

    modernizer_name = processing.get("modernizer")
    if modernizer_name:
        modernizer = _lookup(MODERNIZERS, modernizer_name, "modernizer")
        text, counts = modernizer(text, root)
        for old, count in sorted(counts.items()):
            print(f"Modernised {old!r}: {count} replacement(s)")

    overrides_path = root / "overrides" / f"{work_id}.yaml"
    if overrides_path.exists():
        text = apply_overrides(text, overrides_path)
        print(f"Applied overrides from {overrides_path}")

    words = len(text.split())
    minimum = processing.get("expected_min_words")
    if minimum and words < minimum:
        print(f"Warning: {words} words is below expected_min_words {minimum}")

    clean_dir = root / "workspace" / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    clean_path = clean_dir / f"{work_id}.txt"
    clean_path.write_text(text, encoding="utf-8")
    print(f"Prepared {work_id}: {words} words -> {clean_path}")
    return clean_path
