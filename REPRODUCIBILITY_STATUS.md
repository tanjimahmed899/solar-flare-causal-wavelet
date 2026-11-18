# Manuscript results: independent verification status

Checked against the user-supplied 18 November 2026 research archive; see `INDEPENDENT_TECHNICAL_AUDIT.md` for detail.

| Claim | Verification result |
|---|---|
| Full-year 2022 reference Prediction alert total = 3,117 | Exactly reproduced from original annual GOES input (annual dataset not bundled here) |
| Full-year 2022 Detection alert total = 1,346 | Exactly reproduced (annual dataset not bundled here) |
| 12-h history 2022 Prediction alert total = 2,889 | Exactly reproduced (annual dataset not bundled here) |
| April–July 2022 NOAA-scored results | Independently reproduced end to end, feature series through matched NOAA event IDs |
| January–December 2022 total 2,305 NOAA events / pooled TP, FP, FN, F1 | Not independently reproduced: 8 months of NOAA labels not supplied |
| Published full-year SMA, EWMA and log-flux-slope metrics | Not exactly reproduced: original baseline implementation/details not supplied |
| Full-year parameter sensitivity and proposed ablation | Not independently reproduced |
| All 2023 held-out / out-of-sample claims | Not independently reproduced: 2023 data, NOAA labels, and frozen code/output missing |

### Why the older April code is not included

The older script (`run_solar_flare.py`) uses daily first-70%-based thresholds, wavelet energy on log-transformed flux and its own detections as match references. These differ materially from the camera-ready manuscript. Including it under the main code path would mislead readers into treating two incompatible evaluations as identical.

### Minimum additional artifacts for full-paper reproduction

- 2022 January–December NOAA C/M/X event catalog and its original provenance
- 2023 GOES flux and full-year NOAA C/M/X catalog
- Exact 2022/2023 frozen-configuration run scripts and per-month TP/FP/FN and alert matches
- Original EWMA, short/long SMA, log-flux slope, sensitivity and 12-hour mitigation experiment scripts/outputs
- Parameter-tuning protocol and calibration period recorded before test evaluation
