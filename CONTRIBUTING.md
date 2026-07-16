# Contributing

Thank you for helping build a transparent fiction corpus.

## Good first contributions

- nominate a legally redistributable work;
- verify metadata or rights evidence;
- classify a reviewed work using the controlled vocabulary;
- report OCR, formatting, or truncation problems;
- improve validation and cleaning tools;
- propose a source adapter.

## Adding a work

1. Copy `catalog/examples/example-work.yaml` to `catalog/works/<stable-id>.yaml`.
2. Replace every example value with verified information.
3. Do not add the novel text to Git history.
4. Run `ofc validate`.
5. Open a pull request explaining the source, rights basis, classifications, and checks performed.

A stable ID should be lowercase and human-readable, for example:

```text
se-wells-the-time-machine-en
```

Do not change an ID after release unless it is objectively incorrect and a migration is included.

## Rights requirements

Do not submit:

- scraped contemporary fiction;
- fanfiction without explicit permission from every necessary rights holder;
- an edition or translation whose rights have not been checked;
- text with unknown provenance;
- a work merely because another dataset already contains it.

See `docs/rights-policy.md` and `DATA_LICENSE.md`.

## Text handling

Canonical text must preserve the complete literary work and its meaningful structure. Do not silently modernise spelling, rewrite dialect, paraphrase, or use an LLM to clean prose.

Automated corrections should be reproducible. Work-specific corrections belong in `overrides/`, not as unexplained edits to generated files.

## Classification

Use values defined in `schema/genres.yaml`. A work may have several genres but exactly one `primary_genre`. Narrative characteristics such as POV and tense are separate from genre.

## Pull requests

Keep one conceptual change per pull request where practical. CI must pass. Reviewers may request additional rights evidence or quality checks before a work enters a release pack.
