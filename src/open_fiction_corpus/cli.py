from __future__ import annotations

import argparse
from pathlib import Path

from .build import build_dataset
from .prepare import prepare_work
from .validate import validate_repository


def main() -> None:
    parser = argparse.ArgumentParser(prog="ofc")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate manifests and packs")
    validate_parser.add_argument("--root", type=Path, default=Path.cwd())

    prepare_parser = subparsers.add_parser(
        "prepare", help="Fetch, extract, clean, and modernise one work's text"
    )
    prepare_parser.add_argument("work_id")
    prepare_parser.add_argument("--root", type=Path, default=Path.cwd())
    prepare_parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Reuse the existing raw file under workspace/raw/<work-id>/",
    )

    build_parser = subparsers.add_parser("build", help="Build whole-book dataset exports")
    build_parser.add_argument("--root", type=Path, default=Path.cwd())
    build_parser.add_argument("--allow-missing-text", action="store_true")
    build_parser.add_argument(
        "--allow-unreviewed",
        action="store_true",
        help="Development builds only: include works that are not release-ready "
        "(unreviewed quality, unpinned revision, or missing source hash)",
    )
    build_parser.add_argument(
        "--pack", help="Build only works selected by the named pack definition"
    )

    args = parser.parse_args()
    if args.command == "validate":
        raise SystemExit(0 if validate_repository(args.root) else 1)
    if args.command == "prepare":
        prepare_work(args.root, args.work_id, skip_fetch=args.skip_fetch)
    if args.command == "build":
        build_dataset(
            args.root,
            pack=args.pack,
            allow_missing_text=args.allow_missing_text,
            allow_unreviewed=args.allow_unreviewed,
        )


if __name__ == "__main__":
    main()
