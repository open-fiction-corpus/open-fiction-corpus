# Reviewing a work

A catalogued work moves from `candidate` to release-ready only after a human
completes this checklist. It has two independent judgments — **rights** (is
the exact fetched artifact legally clear?) and **quality** (is the cleaned
text faithful and complete?) — plus the mechanical **pinning** that binds
your approval to specific bytes.

Nothing here can be automated away: the tooling fetches, cleans, hashes, and
gates, but a person must read the text and make the calls.

## 0. Prepare the text

Run `ofc prepare <work-id>` — locally, or via the **Prepare work** GitHub
Action. It fetches the pinned artifact, cleans it, and prints two hashes:

- the **raw source** SHA-256 (record as `processing.source_sha256`);
- the **cleaned text** SHA-256 (record as `quality.reviewed_text_sha256`).

Both files land under the ignored `workspace/` directory. The public Action
uploads only the provenance sidecar, never the text, so the reading steps
below require a local prepare run.

## 1. Rights — inspect the exact artifact

Open `workspace/raw/<work-id>/<work-id>.txt` and confirm it contains **only
the author's own text plus Project Gutenberg boilerplate** (which the
extractor strips). Specifically, there must be no third-party:

- introduction, preface, or foreword by an editor;
- explanatory notes, footnotes, or annotations;
- glossary, critical apparatus, or appended essays.

If any such material is present, it must be excluded by the extractor (or the
work deferred) — do not simply accept it into the corpus. Re-confirm the
author, edition hints, and dates against the rights evidence already recorded
in the manifest.

## 2. Quality — inspect the cleaned text

Open `workspace/clean/<work-id>.txt`:

- **Beginning**: starts with the actual work (title / first chapter); no
  licence text, no "Produced by".
- **End**: ends on the final sentence of the story, including any epilogue;
  no trailing Gutenberg boilerplate or appended material.
- **Structure**: skim the chapter headings — right count, right order, none
  missing or duplicated.
- **Samples**: read 3–4 paragraphs from random interior spots. Intact prose,
  no mid-sentence truncation, no mangled paragraph unwrapping, no leftover
  page numbers or `[Illustration]` markers.
- **Modernisation counts**: the `ofc prepare` log prints per-rule replacement
  counts. Sanity-check them (a handful of `to-day`/`connexion`, not
  hundreds).
- **Cross-check**: if a Standard Ebooks edition exists, diff a chapter
  against it. Spelling and typography will differ by design, but missing or
  garbled sentences jump out — a cheap way to catch transcription errors.

Any work-specific correction goes in `overrides/<work-id>.yaml` (`find`,
`replace`, `count`, `note`); re-run `ofc prepare` and re-review the affected
spot. The cleaned-text hash changes when you do, which is the point.

## 3. Pin and record

Edit the manifest:

- `source.revision` — the pinned source revision (e.g. Gutenberg's "most
  recently updated" date, or a retained snapshot id).
- `processing.source_sha256` — the raw hash from the prepare log.
- `quality.reviewed_text_sha256` — the cleaned-text hash from the prepare log.
- `quality.status` — `human-reviewed`.
- `quality.reviewed_by` — add yourself.
- `quality.review_notes` — what you checked and anything notable (e.g. the
  chapter structure or edition lineage you observed).
- `rights.status` — flip to `public-domain` (and set the verified/unverified
  jurisdiction lists) **only if** the artifact inspection was clean **and**
  no jurisdiction bars release; drop the `uncertain-rights` flag.

## 4. What the gates then enforce

Once pinned, `ofc validate` and `ofc build` take over. The build recomputes
the cleaned text's hash and **refuses any text that no longer matches** your
pinned `reviewed_text_sha256`, so regenerating the output (new cleaner
version, changed rules or overrides, changed source) forces a re-review. The
rights gate keeps a non-releasable work out of every export regardless.

## Releasing is not the same as finishing

A fully reviewed work can still be non-releasable — for example a work whose
author's term has not expired in every target jurisdiction. "Finished and
parked" means the review is complete, the rights status is honest, and the
gate is holding until the work becomes releasable. Do not force a work past
the rights gate to publish it early.
