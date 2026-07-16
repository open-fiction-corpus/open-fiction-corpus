# Open Fiction Corpus

A community-built, reproducible corpus of legally redistributable fiction for continued pretraining and genre-specific language-model research.

This repository contains the **catalogue, schemas, cleaning rules, validation tools, and dataset build recipes**. It does not store the released novel corpus in ordinary Git history. Generated datasets will be published separately to a Hugging Face dataset repository.

## Project principles

- Preserve complete works as canonical documents.
- Store each work once; represent genres and specialist corpora as reusable packs.
- Require traceable provenance and work-by-work rights metadata.
- Keep raw prose model-independent: no tokenizer-specific EOS strings or pre-tokenization in the canonical corpus.
- Prefer human-authored fiction and clearly label all provenance.
- Make every published release reproducible from a tagged catalogue revision.

## Planned workflow

1. Add or review a work manifest under `catalog/works/`.
2. Fetch the pinned upstream source into the ignored local `workspace/` directory.
3. Clean and validate the text using the project tooling.
4. Build whole-book JSONL and Parquet exports under the ignored `dist/` directory.
5. Publish versioned dataset files to Hugging Face.

## Repository map

- `catalog/works/` — one YAML manifest per work
- `packs/` — general-fiction, genre, and experimental corpus definitions
- `schema/` — controlled vocabularies and JSON Schema
- `src/open_fiction_corpus/` — fetch, cleaning, validation, and build code
- `overrides/` — reproducible work-specific cleaning corrections
- `docs/` — rights, cleaning, review, dataset, and training guidance
- `.github/` — contribution templates and CI

## Current status

The project is in its initial scaffolding phase. No books are included yet.

## Contributing

Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) before proposing a book, classification change, cleaner, or source adapter.

## Licensing

Project code is licensed under Apache-2.0. Metadata and redistributed texts may have different legal statuses; see [`DATA_LICENSE.md`](DATA_LICENSE.md).