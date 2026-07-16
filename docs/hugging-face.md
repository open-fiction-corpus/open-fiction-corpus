# Publishing releases to Hugging Face

The GitHub repository is the source of truth for catalogue metadata, build code, policy, and review history. The Hugging Face dataset repository stores generated release artifacts containing the actual cleaned corpus.

## The dataset repository

The project's dataset repository is [`open-fiction-corpus/corpus`](https://huggingface.co/datasets/open-fiction-corpus/corpus), owned by the `open-fiction-corpus` organization. Its Dataset Card (`README.md`) describes provenance, rights limitations, corpus composition, intended use, and known limitations; it is maintained from [`docs/dataset-card-template.md`](dataset-card-template.md) and must be updated with each release.

Do not upload books manually until the build and rights-review process is working with a small test release.

## Local authentication

Install the current Hub client and authenticate:

```bash
pip install -U huggingface_hub
hf auth login
```

Use a dedicated, narrowly scoped token for local publishing. Never commit a token to this repository, dataset files, logs, or configuration tracked by Git.

## Manual test upload

After creating a small release under `dist/`, upload it with:

```bash
hf upload open-fiction-corpus/corpus ./dist . --repo-type dataset
```

Hugging Face also supports uploads through its web interface and Python `HfApi.upload_folder()` method.

## Automated releases

For production releases, prefer a GitHub Actions workflow configured as a Hugging Face Trusted Publisher. Trusted publishing uses GitHub's OpenID Connect identity to obtain a short-lived, repository-scoped token during the workflow rather than storing a permanent Hugging Face write token in GitHub Secrets.

The publication workflow should run only after an explicit versioned release action. It should:

1. validate the catalogue;
2. build the dataset from reviewed manifests and pinned sources;
3. produce JSONL/Parquet, pack membership, checksums, and a build manifest;
4. upload the release artifacts to the Hugging Face dataset repository;
5. record the GitHub commit and dataset version in both repositories.

This workflow exists at [`.github/workflows/release.yml`](../.github/workflows/release.yml). It runs on published GitHub releases, supports a manual dry run that skips the upload, and refuses to publish a dataset with zero rows. Before the first real release, set the `HF_DATASET_REPO` repository variable and configure trusted publishing (or an `HF_TOKEN` secret as fallback) as described in the workflow's header comment. The source-fetching step is still a placeholder until the first source adapter is implemented.

## Recommended release files

```text
README.md
books/
  <work-id>.txt
data/
  books.parquet
  books.jsonl.gz
packs/
  general-fiction.parquet
  fantasy.parquet
  mystery.parquet
release/
  build-manifest.json
  pack-membership.json
  checksums.sha256
```

Parquet is the preferred machine-readable format for the main dataset. Individual UTF-8 text files remain useful for transparent human inspection.
