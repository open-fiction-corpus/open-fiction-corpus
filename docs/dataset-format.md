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
