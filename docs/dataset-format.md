# Dataset format

The canonical dataset unit is one complete literary work. The primary export contains one row per work rather than pre-cut training chunks.

Required row fields include:

- stable work ID;
- title and authors;
- language and form;
- genre metadata;
- source provider, identifier, and pinned revision;
- rights and quality status;
- complete cleaned text.

The canonical text contains no model-specific beginning-of-sequence or end-of-sequence strings. Training code should append the selected tokenizer's actual EOS token and create context-length windows as needed.

Official releases should include compressed JSONL, optional Parquet, a build manifest, pack membership lists, and checksums. Generated outputs belong in `dist/` locally and in the separate dataset repository after release.

## Text formatting conventions (`text_format: markdown-lite`)

The corpus's `text` field is a fixed, deliberate convention, not raw Gutenberg
output — every row follows it, so it is a whole-corpus property rather than a
per-row field:

- **Emphasis is markdown-style italics.** Gutenberg's plain-text convention
  wraps italicised words or phrases in a single underscore on each side
  (`_word_`); the cleaning pipeline preserves this verbatim rather than
  stripping it. Treat a leading/trailing `_` around a word or phrase as an
  italics marker, not literal text.
- **Square brackets are original content, not corpus markup.** Where they
  appear — an author's own alternate chapter subtitle (e.g. `Chapter 9. The
  Light upon the Moor [Second Report of Dr. Watson]`), or an inline footnote
  carried over from the print edition (e.g. `[Footnote: ... —ED.]`) — they
  are part of the source work and are kept verbatim. They are never inserted
  by the pipeline as placeholders, redactions, or errors.
- Generated front matter with no literary content — tables of contents,
  publisher boilerplate, transcriber credits — is removed during cleaning
  (see [the cleaning guide](cleaning-guide.md)) so a model trained on the
  corpus does not learn to open a work with a chapter index.

No other markdown syntax (headings, bold, links, lists) is meaningful in the
`text` field.
