"""Rerun the manuscript analysis, checks, and scientific figures."""
from pathlib import Path
import argparse
import os
import runpy
import sys


def run_script(path, arguments):
    previous = sys.argv[:]
    sys.argv = [str(path), *map(str, arguments)]
    try:
        runpy.run_path(str(path), run_name="__main__")
    finally:
        sys.argv = previous


def main():
    root = Path(__file__).resolve().parent
    candidates = [root / "data/GOES_XRSB_April_July_2022.csv",
                  root / "GOES_2022_FULL.zip", root / "GOES_2022_FULL.csv"]
    default_goes = next((p for p in candidates if p.is_file()), candidates[0])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goes", type=Path,
                        default=default_goes)
    parser.add_argument("--noaa", type=Path,
                        default=root / "noaa/catalogs/NOAA_XRA_context_2022_03_31_to_08_01.csv")
    parser.add_argument("--out", type=Path, default=root / "my_results")
    parser.add_argument("--skip-figures", action="store_true")
    args = parser.parse_args()
    for path in (args.goes, args.noaa):
        if not path.is_file():
            parser.error(f"Input file not found: {path}")
    args.out = args.out.resolve()
    os.environ.setdefault("MPLBACKEND", "Agg")
    run_script(root / "run_manuscript_pipeline.py",
               ["--goes", args.goes.resolve(), "--noaa", args.noaa.resolve(),
                "--out", args.out])
    run_script(root / "validate_manuscript_pipeline.py",
               ["--results", args.out, "--code", root / "run_manuscript_pipeline.py"])
    if not args.skip_figures:
        run_script(root / "build_manuscript_deliverables.py", ["--results", args.out])
    print(f"Finished. Your results are in: {args.out}")


if __name__ == "__main__":
    main()
