# Open Fiction Corpus

A community-built, reproducible corpus of legally redistributable fiction for continued pretraining and genre-specific language-model research.

This repository contains the **catalogue, schemas, cleaning rules, validation tools, and dataset build recipes**. It does not store released novel text in ordinary Git history. Generated datasets will be published separately to a Hugging Face dataset repository.

## Project principles

- Preserve complete works as canonical documents.
- Store each work once; represent genres and specialist corpora as reusable packs.
- Require traceable provenance and work-by-work rights metadata.
- Keep canonical prose model-independent: no tokenizer-specific EOS strings or pre-tokenization.
- Prefer human-authored fiction and clearly label all provenance.
- Make every published release reproducible from a tagged catalogue revision.

## Planned workflow

1. Add or review a work manifest under `catalog/works/`.
2. Fetch or supply the pinned upstream source into the ignored local `workspace/` directory.
3. Clean and validate the text using the project tooling.
4. Build whole-book JSONL and optional Parquet exports under the ignored `dist/` directory.
5. Publish versioned dataset files to Hugging Face.

## Repository map

- `catalog/works/` — one YAML manifest per work
- `catalog/examples/` — examples that are not part of the corpus
- `packs/` — general-fiction, genre, and experimental corpus definitions
- `schema/` — controlled vocabularies and JSON Schema
- `src/open_fiction_corpus/` — validation and build code
- `overrides/` — reproducible work-specific cleaning corrections
- `docs/` — rights, cleaning, review, dataset, and training guidance
- `.github/` — contribution templates and CI

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
ofc validate
```

To fetch and clean a catalogued work into the ignored `workspace/` directory:

```bash
ofc prepare h-g-wells-the-time-machine-en
```

This downloads the pinned source, strips platform boilerplate, unwraps hard-wrapped paragraphs, applies the deliberate spelling-modernisation rules from `schema/modernization-rules.yaml`, and applies any work-specific corrections from `overrides/` — see [the cleaning guide](docs/cleaning-guide.md). Alternatively, place a cleaned UTF-8 novel at `workspace/clean/<work-id>.txt` yourself.

Then run:

```bash
ofc build
```

Works whose rights status is not marked `releasable` in `schema/rights-statuses.yaml` (for example `uncertain` or `excluded`) are always skipped. Works that are not yet release-ready — quality status below `human-reviewed`, no recorded reviewer, an unpinned source revision, a missing source hash, or no reviewed-text hash — are also skipped, and the build refuses to ship a cleaned text whose hash no longer matches the `quality.reviewed_text_sha256` the reviewer pinned; pass `--allow-unreviewed` for local development builds only. To build a single pack's selection instead of the whole catalogue:

```bash
ofc build --pack general-fiction
```

Packs select works by criteria (language, form, genres, quality status, origin, excluded quality flags, per-author cap) and can also pin membership by work id: `exclude_works` always removes the listed works, and when `include_works` is present only the listed works are eligible — useful for hand-curated datasets. Id lists can only narrow a pack; the rights and release-readiness gates always apply first.

## Current status

The project is in its initial scaffolding phase. The first pilot work, *The Time Machine*, is moving through the pipeline end to end; no dataset has been released yet.

The planned reading list and processing status are tracked in the **[Book Backlog](docs/book-backlog.md)**. Book suggestions are open now; see **[Suggesting a book](docs/suggesting-a-book.md)** for a nontechnical contribution guide.

## Contributing

Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) before proposing a book, classification change, cleaner, or source adapter.

## Licensing

Project code is licensed under MIT. Metadata and redistributed texts may have different legal statuses; see [`DATA_LICENSE.md`](DATA_LICENSE.md).
