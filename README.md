# Solar-flare warning: causal wavelet-energy reconstruction

Source code, benchmark input and independently NOAA-scored April–July 2022 results for the manuscript **“Detection and Short-Term Prediction of Solar Flares Using a Causal Wavelet-Energy Feature”** (ACDSA 2027 submission).

> **Scope / reproducibility notice.** This public package implements the *documented manuscript reconstruction* and supports an April–July 2022 experiment. It is **not** a complete reproduction of the original April-style code or the manuscript's full January–December 2022 NOAA-matched metrics, complete baseline/sensitivity tables, or 2023 out-of-sample results. The latter need their corresponding original source scripts, NOAA labels, data and saved outputs. Do not cite this repository as proof those missing experiments have been reproduced.

## Contents

- `run_manuscript_pipeline.py`: primary right-aligned db2/cD3 wavelet-energy, trailing percentile, 4-minute confirmation, eventization, matching to independent NOAA peak records
- `validate_manuscript_pipeline.py`: matching, causality and metrics checks
- `build_manuscript_deliverables.py`: report and figure generation
- `run_paper_workflow.py`: convenient orchestration for the above three scripts
- `notebooks/`: accompanying notebook
- `data/GOES_XRSB_April_July_2022.csv`: deduplicated one-minute GOES XRS-B input for the 4-month benchmark
- `noaa/catalogs/`: NOAA-derived C/M/X reference catalog (with context events)
- `results/april_july_2022/`: recorded outputs for this benchmark
- `audit_evidence/`: separately reproduced verification outputs (some 2022 *alert totals* extend across the full year)
- `docs/`: methodology notes and independent audit with unresolved verification limits

## Quick start

Recommended: Python 3.12 in a new virtual environment. Install the pinned dependencies:

```bash
python -m pip install -r requirements.txt
```

Re-run the April–July 2022 benchmark with the bundled small input:

```bash
python run_paper_workflow.py --skip-figures
```

For figures, omit `--skip-figures`:

```bash
python run_paper_workflow.py
```

Results are generated under `my_results/` (excluded from Git by `.gitignore`). For explicit control:

```bash
python run_manuscript_pipeline.py \
  --goes data/GOES_XRSB_April_July_2022.csv \
  --noaa noaa/catalogs/NOAA_XRA_context_2022_03_31_to_08_01.csv \
  --out my_results
python validate_manuscript_pipeline.py --results my_results --code run_manuscript_pipeline.py
```

The exact single-file GOES annual archive is intentionally **not included**. See `docs/REPRODUCIBILITY_STATUS.md` for the claims that are and are not supported. Source-data URLs and release identifiers should be added once confirmed by the authors.

## Key method distinctions

1. The primary input is **linear GOES flux**, not the `log10` flux used in the original April-style notebook. The wavelet energy uses a right-aligned 30-minute window with db2, level-3 detail coefficients, symmetric boundary extension.
2. The percentile history is trailing and includes the current eligible feature; at 120-minute warm-up the history is **partially filled**, not a complete 6-hour buffer.
3. Short missing gaps may be interpolated retrospectively, but values only become eligible at/after the right-hand observed endpoint (availability tracked); no alert is generated on an interpolated right edge.
4. Four elapsed minutes at a 2-minute cadence requires above-threshold decisions at `t`, `t+2`, `t+4`; the actionable alert timestamp is the confirmed start time.
5. The prediction lead measures **alert-to-NOAA-peak**, not necessarily lead before flare onset. NOAA matching is offline evaluation, never part of the alert-generation decision.

## Status and permissions

The original uploaded material's author ownership and software license have not been confirmed; no license is granted by this package itself. Before making the repository public, **confirm all coauthors approve the release and choose an appropriate LICENSE for original code**. NOAA-origin data should be attributed separately. Check for institution policies, unpublished material, credentials, and personally identifying information before public upload.

If you change code or input data, commit the exact version that produced the released outputs. For scholarly citation, consider tagging a release and archiving it with Zenodo after the contents are final.
