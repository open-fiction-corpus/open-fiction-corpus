# Working in this repository

Open Fiction Corpus is a community-built, reproducible corpus of **legally
redistributable fiction**. This repo holds the catalogue, schemas, cleaning
rules, validation/build tooling, and review history — **never the book text
itself**. Generated datasets are published separately to Hugging Face.

## Invariants (do not break these)

- **No book text in git.** Cleaned and raw texts live under `workspace/` and
  built datasets under `dist/`; both are gitignored. Never commit either.
- **Two unconditional build gates.** `ofc build` ships a work only if it
  passes both: the **rights gate** (`rights.status` is releasable) and the
  **release-readiness gate** (`human-reviewed` quality + recorded reviewer +
  pinned `source.revision` + `processing.source_sha256` +
  `quality.reviewed_text_sha256` + a source provider with a fetch adapter).
  No pack config can reintroduce a gated work. `--allow-unreviewed` is for
  local development only.
- **Provenance is hash-bound end to end.** Pinned source bytes → provenance
  sidecar → reviewed clean-text hash → build. The build refuses any cleaned
  text whose hash no longer matches the pinned `reviewed_text_sha256`, so
  regenerating output forces re-review.
- **Modernisation is deliberate and opt-in**, never a silent cleaning side
  effect: whole-word, case-preserving rules in
  `schema/modernization-rules.yaml`, enabled per work via
  `processing.modernizer`. Never modernise grammar, dialect, punctuation, or
  multi-word phrases. Never use an LLM to rewrite source prose.
- **Manifests are untrusted input.** The fetcher only contacts approved
  provider origins (`APPROVED_SOURCE_HOSTS`) over https:443, pins redirects,
  caps downloads, derives local paths from the work id, and binds Gutenberg
  `source.identifier` to its exact landing page and artifact.
- **Releases are byte-reproducible** from the tagged revision (fixed gzip
  mtime/no stored filename; build timestamp from `--built-at`/
  `SOURCE_DATE_EPOCH`). Keep them that way.
- **Releasing ≠ finishing.** A fully reviewed work can still be
  non-releasable (jurisdiction terms). Never force a work past the rights
  gate to publish early.

## Layout

- `catalog/works/<id>.yaml` — one manifest per work (`catalog/examples/` is
  never built).
- `packs/` — dataset definitions: criteria filters plus optional
  `include_works`/`exclude_works` id lists. One `.jsonl.gz` per pack.
- `schema/` — JSON Schema + controlled vocabularies (genres, rights
  statuses, quality flags, modernisation rules, overrides).
- `src/open_fiction_corpus/` — `prepare.py` (fetch/extract/clean/modernise),
  `build.py` (gates + export), `validate.py`, `cli.py`.
- `overrides/<id>.yaml` — reproducible work-specific corrections.
- `docs/` — `cleaning-guide.md`, `review-checklist.md` (the human
  rights+quality review), rights policy, dataset format, Hugging Face setup.
- `.github/workflows/` — `prepare.yml` (manual fetch, uploads provenance
  metadata only, never text), `release.yml` (gated prepare → build → assemble
  → publish).

## Workflow

```bash
python -m venv .venv && source .venv/bin/activate   # see dev note below
pip install -e ".[dev]"
ofc validate
ofc prepare <work-id>     # needs gutenberg.org reachable; prints the two hashes to pin
ofc build                 # or: ofc build --pack <name>
pytest && ruff check .
```

A work moves from `candidate` to release-ready only after a human completes
`docs/review-checklist.md` (read the raw artifact for third-party material;
read the clean text for truncation/structure/samples; pin the hashes; flip
`rights.status` only if clean and no jurisdiction bars release).

## Dev environment notes

- **Use a virtualenv.** System pip cannot uninstall the distro PyYAML; create
  a venv (a scratchpad dir works) and `pip install -e ".[dev]"` there.
- **`ofc prepare` needs network access to `www.gutenberg.org`.** If it 403s,
  the environment's network policy is blocking it (Trusted default) — needs
  Full or a Custom allowlist including gutenberg.org.
- GitHub git pushes are proxy-restricted to the current working branch;
  branch deletion from inside the sandbox is blocked (use the web UI).

## Live task state

Task state is tracked in **GitHub issues, not in this file** (which stays
durable):

- **#12** — The Time Machine (pipeline pilot; parked non-releasable until
  2027 due to Spain's 80-year term).
- **#15** — The Hound of the Baskervilles (the intended **first public
  release**; public domain in every reviewed jurisdiction).

Both are catalogued and gated; the next step for each is
`ofc prepare` → human review → pin, once gutenberg.org is reachable.
