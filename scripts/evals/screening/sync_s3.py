"""Download the screening ground truth and upload a run, with the AWS command-line tool.

Uses the default AWS profile. Log in the way you usually do before running this:
``aws sts get-caller-identity`` should print your account.

    uv run --project backend python scripts/evals/screening/sync_s3.py download
    uv run --project backend python scripts/evals/screening/sync_s3.py upload results/runs/<folder>
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

BUCKET = "discovery-policy-atlas"
DATASET_URI = f"s3://{BUCKET}/eval/datasets/screening/"
RESULTS_URI = f"s3://{BUCKET}/eval/results/screening/"

ROOT = Path(__file__).resolve().parent
DATASETS = ROOT / "datasets"


def _aws(*args: str) -> None:
    if shutil.which("aws") is None:
        raise SystemExit(
            "The AWS command-line tool is not on PATH. Install it, then log in."
        )
    command = ["aws", *args]
    logger.info("Running: %s", " ".join(command))
    subprocess.run(command, check=True)


def download() -> None:
    """Copy the screening datasets from S3 into ``datasets/``."""
    DATASETS.mkdir(parents=True, exist_ok=True)
    _aws("s3", "sync", DATASET_URI, str(DATASETS))
    logger.info("Downloaded %s to %s", DATASET_URI, DATASETS)


def upload(run_dir: Path) -> None:
    """Copy one local run folder to the results prefix on S3.

    Args:
        run_dir: A folder under ``results/runs/``. The folder name becomes
            the S3 prefix, so a second upload of the same folder overwrites it.

    Raises:
        SystemExit: If ``run_dir`` is not a directory.
    """
    run_dir = run_dir.resolve()
    if not run_dir.is_dir():
        raise SystemExit(f"Run folder not found: {run_dir}")
    destination = f"{RESULTS_URI}{run_dir.name}/"
    _aws("s3", "sync", str(run_dir), destination)
    logger.info("Uploaded %s to %s", run_dir, destination)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("download", help="Sync the ground-truth prefix into datasets/")
    upload_parser = sub.add_parser(
        "upload", help="Sync one run folder to the results prefix"
    )
    upload_parser.add_argument("run_dir", type=Path, help="Local run folder to upload")

    args = parser.parse_args()
    if args.command == "download":
        download()
    else:
        upload(args.run_dir)


if __name__ == "__main__":
    main()
