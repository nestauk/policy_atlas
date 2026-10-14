"""Keep the eval datasets and run results in step with S3, with the AWS command-line tool.

Two areas, ``search`` and ``screening``. Each has a datasets prefix (the ground
truth the scripts read, kept out of git) and a results prefix (one folder per
run). The bucket is the one the earlier prototype used.

Uses the default AWS profile. Log in the way you usually do before running this:
``aws sts get-caller-identity`` should print your account.

    # fetch an area's datasets into the local folders the scripts read
    uv run --project backend python scripts/evals/sync_s3.py screening download
    uv run --project backend python scripts/evals/sync_s3.py search download

    # push the local dataset files to S3, after fetching or sampling again
    uv run --project backend python scripts/evals/sync_s3.py search upload-datasets

    # push one run folder to the area's results prefix
    uv run --project backend python scripts/evals/sync_s3.py screening upload results/runs/<folder>

``--dry-run`` lists what would be copied and copies nothing. A sync never deletes:
a file removed on one side stays on the other.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

BUCKET = "discovery-policy-atlas"
ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class _Folder:
    """One local folder mirrored to one S3 prefix.

    Args:
        local: The folder on disk.
        prefix: The key prefix in the bucket, with a trailing slash.
        only: Patterns to copy and nothing else (``aws s3 sync --include``).
        skip: Patterns to leave out (``aws s3 sync --exclude``).
    """

    local: Path
    prefix: str
    only: tuple[str, ...] = ()
    skip: tuple[str, ...] = ()

    def uri(self) -> str:
        return f"s3://{BUCKET}/{self.prefix}"

    def filters(self) -> list[str]:
        args: list[str] = []
        if self.only:
            args += ["--exclude", "*"]
            for pattern in self.only:
                args += ["--include", pattern]
        for pattern in self.skip:
            args += ["--exclude", pattern]
        return args


@dataclass(frozen=True)
class _Area:
    datasets: tuple[_Folder, ...]
    results_prefix: str


AREAS: dict[str, _Area] = {
    "screening": _Area(
        datasets=(
            _Folder(ROOT / "screening" / "datasets", "eval/datasets/screening/"),
        ),
        results_prefix="eval/results/screening/",
    ),
    "search": _Area(
        datasets=(
            # The fetched collections and the two samples. raw/ holds the 1.6 GB
            # SR4ALL file, which has its own DOI (10.5281/zenodo.18431942).
            _Folder(
                ROOT / "search" / "results" / "ground_truth",
                "eval/datasets/search/ground_truth/",
                skip=("raw/*",),
            ),
            # The policy-side ground truth (task 049), read by experiments/policy_gt.py.
            _Folder(
                ROOT / "search" / "ground_truth",
                "eval/datasets/search/policy_gt/",
                only=("policy_gt_specific*",),
            ),
        ),
        results_prefix="eval/results/search/",
    ),
}


def _aws(*args: str, dry_run: bool) -> None:
    if shutil.which("aws") is None:
        raise SystemExit(
            "The AWS command-line tool is not on PATH. Install it, then log in."
        )
    # Finder's .DS_Store files never belong in the bucket.
    command = [
        "aws",
        *args,
        "--exclude",
        "*.DS_Store",
        *(["--dryrun"] if dry_run else []),
    ]
    logger.info("Running: %s", " ".join(command))
    subprocess.run(command, check=True)


def download(area: _Area, *, dry_run: bool) -> None:
    """Copy the area's dataset prefixes into the local folders the scripts read."""
    for folder in area.datasets:
        folder.local.mkdir(parents=True, exist_ok=True)
        _aws(
            "s3",
            "sync",
            folder.uri(),
            str(folder.local),
            *folder.filters(),
            dry_run=dry_run,
        )
        logger.info("Downloaded %s to %s", folder.uri(), folder.local)


def upload_datasets(area: _Area, *, dry_run: bool) -> None:
    """Copy the local dataset folders to the area's dataset prefixes."""
    for folder in area.datasets:
        if not folder.local.is_dir():
            raise SystemExit(f"Dataset folder not found: {folder.local}")
        _aws(
            "s3",
            "sync",
            str(folder.local),
            folder.uri(),
            *folder.filters(),
            dry_run=dry_run,
        )
        logger.info("Uploaded %s to %s", folder.local, folder.uri())


def upload(area: _Area, run_dir: Path, *, dry_run: bool) -> None:
    """Copy one local run folder to the area's results prefix.

    Args:
        area: The eval area.
        run_dir: A run folder. Its name becomes the S3 prefix, so a second
            upload of the same folder overwrites it.
        dry_run: List what would be copied and copy nothing.

    Raises:
        SystemExit: If ``run_dir`` is not a directory.
    """
    run_dir = run_dir.resolve()
    if not run_dir.is_dir():
        raise SystemExit(f"Run folder not found: {run_dir}")
    destination = f"s3://{BUCKET}/{area.results_prefix}{run_dir.name}/"
    _aws("s3", "sync", str(run_dir), destination, dry_run=dry_run)
    logger.info("Uploaded %s to %s", run_dir, destination)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("area", choices=sorted(AREAS), help="Which eval's files")
    parser.add_argument("--dry-run", action="store_true", help="List, copy nothing")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("download", help="Sync the dataset prefixes into the local folders")
    sub.add_parser("upload-datasets", help="Sync the local dataset folders to S3")
    upload_parser = sub.add_parser(
        "upload", help="Sync one run folder to the results prefix"
    )
    upload_parser.add_argument("run_dir", type=Path, help="Local run folder to upload")

    args = parser.parse_args()
    area = AREAS[args.area]
    if args.command == "download":
        download(area, dry_run=args.dry_run)
    elif args.command == "upload-datasets":
        upload_datasets(area, dry_run=args.dry_run)
    else:
        upload(area, args.run_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
