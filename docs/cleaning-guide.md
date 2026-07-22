# Cleaning guide

Cleaning must be conservative, reproducible, and auditable.

Normally retain chapter headings, scene breaks, meaningful emphasis, letters embedded in the story, epigraphs belonging to the work, deliberate dialect, and intentional punctuation.

Normally remove platform boilerplate, navigation, publisher advertising, scanning notes, generated tables of contents, unrelated introductions, and markup that has no literary meaning.

Do not silently modernise spelling, grammar, punctuation, or vocabulary. Do not paraphrase. Do not use an LLM to rewrite or 'improve' source prose.

Punctuation is normally preserved exactly as transcribed, including stylistic choices (dashes standing in for unnamed people, spaced-out emphasis, and similar). The one narrow exception is unambiguous typographic *variants* of the same mark — for example an edition rendering an ellipsis as a spaced `. . .` in one place and the single `…` character everywhere else. Normalizing those is allowed, but only through the same auditable, per-work mechanisms as any other correction (a versioned rule or an `overrides/<work-id>.yaml` entry with a `note` that says so plainly), never silently and never by rewriting wording. The corpus's own convention is `…` (U+2026), not `. . .` or `...`.

A second known case in this category: older (pre-Unicode) Gutenberg transcriptions sometimes render every em dash as plain ASCII `--` throughout, with no real `—` (U+2014) characters anywhere in the file — a limitation of the transcription's character encoding, not an authorial or period-typesetting choice. `ofc prepare` prints a warning when it sees `--` in the cleaned text so this doesn't go unnoticed; whether it actually is this case (check: are there also single hyphens in genuinely hyphenated words, and does *any* real em dash exist elsewhere in the same file?) is a per-work judgement call before writing the override, same as the ellipsis case. Watch for doubled sequences (`----`) representing two dashes in a row, e.g. a redaction — a blind find/replace of `--` handles this correctly since a four-hyphen run is just two adjacent matches, but confirm that's actually what's happening before relying on it.

## Spelling modernisation

Archaic spellings are modernised deliberately, never as a silent cleaning side effect. A work opts in through `processing.modernizer` in its manifest; the versioned moderniser applies only the whole-word rules reviewed into [`schema/modernization-rules.yaml`](../schema/modernization-rules.yaml) (for example `to-day` → `today`, `connexion` → `connection`), preserves case, and reports a per-rule replacement count when `ofc prepare` runs. Grammar, vocabulary, dialect, punctuation, and multi-word phrases are never modernised. A work processed without a moderniser keeps its original spellings.

## Cleaner scope

`fiction_clean_v1` unwraps hard-wrapped lines within every paragraph, which flattens intentional lineation. It is therefore safe only for prose-only works. Works containing verse, songs, inscriptions, deliberately lineated letters, or similar material must not use it as-is; they need a future cleaner version with structural handling, and the limitation should be noted in the work's review notes until then.

## Where rules live

Automatic rules belong in versioned cleaners and modernisers. Work-specific corrections belong in `overrides/<work-id>.yaml`, validated against [`schema/overrides.schema.json`](../schema/overrides.schema.json): each correction records a non-empty `find`, a `replace`, a `note` explaining the change, and the exact number of expected matches (`count`), so the pipeline fails loudly if the source text shifts underneath it.

## Running the pipeline

After preparation, a human completes the [review checklist](review-checklist.md) — the rights and quality judgments that move a work from `candidate` to release-ready.

`ofc prepare <work-id>` downloads the exact artifact named by the manifest's `source.download_url` into `workspace/raw/<work-id>/`, verifies its SHA-256 against `processing.source_sha256` before anything is written (and again on `--skip-fetch` runs, together with the provenance sidecar and the same provider-specific source validation the fetch path applies), then applies the manifest's extractor, cleaner, moderniser, and overrides, writing the canonical text to `workspace/clean/<work-id>.txt` and printing its SHA-256. After human review, that hash is pinned as `quality.reviewed_text_sha256`; the release build refuses any cleaned text that no longer matches it, so regenerated output always requires re-review. The clean file is written as explicit UTF-8 bytes with LF newlines, and the released dataset row contains byte-for-byte that reviewed file content. Neither workspace directory is ever committed.

## Source access policy

Manifests are contributor input, so the fetcher treats `source.download_url` as untrusted: it only contacts the approved https origins listed per provider in `APPROVED_SOURCE_HOSTS` (currently `www.gutenberg.org`/`gutenberg.org` for `gutenberg`, default port 443 only), refuses redirects to anywhere else, caps downloads at 64 MiB, and stores raw artifacts under a project-controlled filename derived from the work id — the remote basename is never used for the local path. Adding an origin (for example an official Gutenberg mirror) is a reviewed code change.

Fetching is deliberately conservative: one HTTP request per work per invocation, a descriptive project User-Agent, no automatic retries, and no crawling. Bulk or repeated downloading of gutenberg.org is not acceptable; if the catalogue grows to need bulk retrieval, use Project Gutenberg's official mirrors and document the chosen mirror here first. A recorded hash detects upstream changes but cannot recover old bytes once a source regenerates a file, so the release process will eventually need retained, content-addressed raw artifacts outside ordinary Git history (tracked in the pilot issue).
