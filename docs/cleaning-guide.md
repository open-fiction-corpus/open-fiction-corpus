# Cleaning guide

Cleaning must be conservative, reproducible, and auditable.

Normally retain chapter headings, scene breaks, meaningful emphasis, letters embedded in the story, epigraphs belonging to the work, deliberate dialect, and intentional punctuation.

Normally remove platform boilerplate, navigation, publisher advertising, scanning notes, generated tables of contents, unrelated introductions, and markup that has no literary meaning.

Do not silently modernise spelling, grammar, punctuation, or vocabulary. Do not paraphrase. Do not use an LLM to rewrite or 'improve' source prose.

## Spelling modernisation

Archaic spellings are modernised deliberately, never as a silent cleaning side effect. A work opts in through `processing.modernizer` in its manifest; the versioned moderniser applies only the whole-word rules reviewed into [`schema/modernization-rules.yaml`](../schema/modernization-rules.yaml) (for example `to-day` → `today`, `connexion` → `connection`), preserves case, and reports a per-rule replacement count when `ofc prepare` runs. Grammar, vocabulary, dialect, punctuation, and multi-word phrases are never modernised. A work processed without a moderniser keeps its original spellings.

## Where rules live

Automatic rules belong in versioned cleaners and modernisers. Work-specific corrections belong in `overrides/<work-id>.yaml`: each correction records `find`, `replace`, a `note` explaining the change, and the exact number of expected matches, so the pipeline fails loudly if the source text shifts underneath it.

## Running the pipeline

`ofc prepare <work-id>` fetches the pinned raw source into `workspace/raw/<work-id>/`, verifies its SHA-256 when `processing.source_sha256` is set, then applies the manifest's extractor, cleaner, moderniser, and overrides, writing the canonical text to `workspace/clean/<work-id>.txt`. Neither directory is ever committed.
