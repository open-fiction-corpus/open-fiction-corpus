# Dataset card template

Copy everything below the horizontal rule into the Hugging Face dataset repository as its `README.md`, then replace every `{{PLACEHOLDER}}`. Keep the card in sync with each release: the reproducibility section must always name the exact tag and commit the artifacts were built from.

---

```yaml
---
pretty_name: Open Fiction Corpus
license: other
license_name: per-work-rights-metadata
license_link: https://github.com/{{GITHUB_OWNER}}/open-fiction-corpus/blob/main/DATA_LICENSE.md
language:
  - en
task_categories:
  - text-generation
tags:
  - fiction
  - books
  - novels
  - long-form
  - continued-pretraining
  - markdown-lite
size_categories:
  - {{SIZE_CATEGORY}} # e.g. n<1K — one row is one complete work
---
```

# Open Fiction Corpus

A community-built, reproducible corpus of legally redistributable fiction for continued pretraining and genre-specific language-model research. Each row is one **complete literary work** with provenance and rights metadata — not pre-cut training chunks.

The catalogue, schemas, cleaning rules, and build code live in the GitHub repository: https://github.com/{{GITHUB_OWNER}}/open-fiction-corpus. This Hugging Face repository stores only generated release artifacts. Nothing here is hand-edited.

## Dataset structure

### Files

- `data/books.jsonl.gz` — every released work, one JSON object per line
- `packs/<pack>.jsonl.gz` — curated subsets (general fiction, genre packs) selected by the pack definitions in the source repository
- `release/build-manifest.json` — release version, catalogue commit, and the exact work IDs in every file
- `release/checksums.sha256` — SHA-256 checksums of all data files

### Row fields

| Field | Description |
|---|---|
| `id` | Stable work identifier, e.g. `se-wells-the-time-machine-en` |
| `title` | Work title |
| `authors` | List of author names |
| `language` | BCP-47-style language code |
| `form` | `novel`, `novella`, `short-story`, or `short-story-collection` |
| `primary_genre` | Exactly one genre from the controlled vocabulary |
| `genres` | All applicable genres |
| `subgenres` | Subgenres from the controlled vocabulary |
| `rights_status` | Reviewed redistribution basis, e.g. `public-domain` |
| `quality_status` | Review state, e.g. `human-reviewed` |
| `source_provider` / `source_identifier` / `source_revision` | Pinned upstream source |
| `text` | The complete cleaned text of the work |

The text contains **no model-specific BOS/EOS strings** and is not pre-tokenized. Training code should append the selected tokenizer's real EOS token and create context windows itself, without crossing document boundaries unless the framework supports document-aware packing.

**Text format: `markdown-lite`.** The only markdown syntax used in `text` is underscore-delimited italics (`_word_`), carried over verbatim from the source transcription's emphasis convention — no other markdown (headings, bold, links, lists) is meaningful. Square brackets in the text are original content (an author's alternate chapter subtitle, an inline footnote from the print edition) and are never corpus-generated placeholders. See [dataset-format.md](https://github.com/{{GITHUB_OWNER}}/open-fiction-corpus/blob/main/docs/dataset-format.md#text-formatting-conventions-text_format-markdown-lite) for the full convention.

## Provenance and rights

Every work passed a per-work rights review before release. The catalogue records the upstream source and pinned revision, the asserted rights status, the jurisdictions actually reviewed, and the supporting evidence. Works with uncertain rights are excluded from builds by the tooling itself.

**Important:** public-domain status is jurisdiction-specific. A work may be public domain where this release was reviewed ({{REVIEWED_JURISDICTIONS}}) and still protected elsewhere. Translations and edited editions can carry independent copyright even when the original is public domain. See [DATA_LICENSE.md](https://github.com/{{GITHUB_OWNER}}/open-fiction-corpus/blob/main/DATA_LICENSE.md). Dataset users remain responsible for evaluating their own use and location; this card is not legal advice.

## Composition

{{COMPOSITION_SUMMARY}} <!-- e.g. "This release contains N works: N novels, N short-story collections; N% women-authored; genre breakdown ..." — the work IDs per file are in release/build-manifest.json -->

Release packs restrict `content.origin` to `human`, so AI-generated works are excluded. Each work also records `content.ai_assistance` (`none`, `proofreading`, `substantive`, or `unknown`); packs do not currently filter on that field, so downstream users who need stricter guarantees should filter rows on it themselves.

## Intended use

Causal-language-model continued pretraining on complete fiction, genre-specific fine-tuning, and prose-style research — especially for Small Language Models. See the [training guide](https://github.com/{{GITHUB_OWNER}}/open-fiction-corpus/blob/main/docs/training-guide.md).

Out of scope: the corpus does not teach instruction following, dialogue-format chat, or outline-to-prose conversion by itself; those need separate task-tuning stages.

## Limitations and biases

- Because rights review favours older works, the corpus over-represents pre-1930s prose, vocabulary, and social attitudes, including period racial language and colonial framing in some works. Works with such content are flagged in the catalogue rather than silently edited.
- Early releases skew toward British and US literature in English.
- OCR-derived sources may retain minor transcription errors; severe cases are excluded by quality flags.
- Corpus-balance targets (author caps, women-authored share, short-fiction share) are enforced per release and documented in the source repository's book backlog.

## Reproducibility

This release was built from:

- **Release version:** `{{RELEASE_TAG}}`
- **Catalogue commit:** [`{{CATALOGUE_COMMIT}}`](https://github.com/{{GITHUB_OWNER}}/open-fiction-corpus/commit/{{CATALOGUE_COMMIT}})
- **Build tooling:** `open-fiction-corpus` Python package at the same commit

Rebuilding from that commit with `ofc build` reproduces these artifacts. The exact work IDs included in every file are listed in `release/build-manifest.json`.

## Contributing and reporting problems

Nominate works, dispute classifications, or report text problems via GitHub issues: https://github.com/{{GITHUB_OWNER}}/open-fiction-corpus/issues. A work being in another dataset is not sufficient grounds for inclusion here.

## Citation

```bibtex
@misc{openfictioncorpus{{RELEASE_YEAR}},
  title  = {Open Fiction Corpus},
  author = {{Open Fiction Corpus contributors}},
  year   = {{{RELEASE_YEAR}}},
  url    = {https://huggingface.co/datasets/{{HF_DATASET_REPO}}},
  note   = {Release {{RELEASE_TAG}}, catalogue commit {{CATALOGUE_COMMIT}}}
}
```
