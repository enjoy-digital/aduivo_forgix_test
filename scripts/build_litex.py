#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
from pathlib import Path


TARGET = "adiuvo_forgix"


def main():
    repo_root = Path(__file__).resolve().parents[1]
    default_output_dir = os.environ.get("OUTPUT_DIR", f"build/{TARGET}")

    parser = argparse.ArgumentParser(
        description="Build the Forgix LiteX SPIBone test design."
    )
    parser.add_argument(
        "--output-dir",
        default=default_output_dir,
        help=f"LiteX output directory. Defaults to {default_output_dir!r}.",
    )
    args, litex_args = parser.parse_known_args()

    output_dir = Path(args.output_dir)
    csr_csv = output_dir / "csr.csv"

    build_cmd = [
        sys.executable,
        "-m",
        f"litex_boards.targets.{TARGET}",
        "--build",
        "--with-spibone",
        "--output-dir",
        str(output_dir),
        *litex_args,
    ]

    subprocess.run(build_cmd, cwd=repo_root, check=True)
    subprocess.run(
        [
            sys.executable,
            str(repo_root / "tools" / "csr2py.py"),
            str(csr_csv),
            "--output",
            str(repo_root / "micropython" / "csr.py"),
        ],
        cwd=repo_root,
        check=True,
    )


if __name__ == "__main__":
    main()
