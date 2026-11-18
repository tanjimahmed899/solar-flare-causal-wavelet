# ACDSA 2027 — Independent Technical Audit

*Paper: Detection and Short-Term Prediction of Solar Flares Using a Causal Wavelet-Energy Feature*
*Audit date: 18 November 2026*

**Scope.** User-supplied camera-ready manuscript, 2022 GOES XRS archive, manuscript-reconstruction code, NOAA reports/labels for April–July 2022, original April-style code, baseline script, and available saved experiment outputs. Results below identify what was actually rerun and what remains unsubstantiated.

## Executive verdict

- **Verified exactly:** Full-year 2022 wavelet Prediction and Detection alert totals; 12-hour history Prediction alert totals; April–July reconstructed feature/threshold/alert/matching results; arithmetic consistency for the paper’s reported 2022 count-based metrics.
- **Independent but provisional:** Fixed baseline computations on available April–July NOAA labels; baseline alert volumes for full 2022. Baseline outputs depend on implementation choices that are not fully specified in the manuscript.
- **Not verified:** January–December 2022 NOAA event count/TP/FP/FN/F1 and individual sensitivity F1 claims; full-year 2023 results; 2023 8.2% false-positive mitigation; exact original April published experiment.

## 1. Input data and experimental reproducibility

- GOES 2022 archive: **12 complete calendar months**, **525,600 unique 1-minute time slots**, **2,102,400 raw rows** before deduplication (four rows per minute).
- DWT library in this environment: PyWavelets unavailable. A short independent NumPy implementation of the symmetric-extension db2 level-3 DWT was used solely for verification; energies matched saved PyWavelets-style values to near machine precision in random windows and across full available months.
- Reconstruction code explicitly documents that the original April publication was **not** exactly reproduced and that the old April script uses different preprocessing, thresholds, reference events, and matching.

### Full-year 2022 6-hour reference alerts

| Month | Prediction alerts | Detection alerts |
|---|---:|---:|
| 2022-01 | 253 | 113 |
| 2022-02 | 237 | 109 |
| 2022-03 | 266 | 109 |
| 2022-04 | 247 | 116 |
| 2022-05 | 269 | 119 |
| 2022-06 | 255 | 116 |
| 2022-07 | 278 | 119 |
| 2022-08 | 253 | 110 |
| 2022-09 | 258 | 107 |
| 2022-10 | 255 | 113 |
| 2022-11 | 275 | 107 |
| 2022-12 | 271 | 108 |
| **Total** | **3,117** | **1,346** |

**Paper comparison:** Table V reports 3,117 Prediction alerts and Table VI reports 1,346 Detection alerts. Both match exactly.

### 12-hour history mitigation

| Month | 6-hour Prediction alerts | 12-hour Prediction alerts | Reduction |
|---|---:|---:|---:|
| 2022-01 | 253 | 240 | 13 |
| 2022-02 | 237 | 222 | 15 |
| 2022-03 | 266 | 245 | 21 |
| 2022-04 | 247 | 226 | 21 |
| 2022-05 | 269 | 245 | 24 |
| 2022-06 | 255 | 237 | 18 |
| 2022-07 | 278 | 247 | 31 |
| 2022-08 | 253 | 239 | 14 |
| 2022-09 | 258 | 233 | 25 |
| 2022-10 | 255 | 243 | 12 |
| 2022-11 | 275 | 259 | 16 |
| 2022-12 | 271 | 253 | 18 |
| **Total** | **3117** | **2889** | **228** |

**Paper comparison:** In Table X, 12-hour alerts = TP 921 + FP 1,968 = **2,889**. The reconstructed pipeline produced **2,889**. This verifies alert-generation volume, not the TP/FP split.

## 2. Four-month complete rerun against saved NOAA labels

| Month | Stream | Alerts | TP | FP | FN | F1 | Feature, threshold, alert ID, matched event IDs |
|---|---|---:|---:|---:|---:|---:|---|
| 2022-04 | prediction | 247 | 86 | 161 | 138 | 0.365180 | Exact match |
| 2022-04 | detection | 116 | 69 | 47 | 155 | 0.405882 | Exact match |
| 2022-05 | prediction | 269 | 101 | 168 | 156 | 0.384030 | Exact match |
| 2022-05 | detection | 119 | 93 | 26 | 164 | 0.494681 | Exact match |
| 2022-06 | prediction | 255 | 46 | 209 | 61 | 0.254144 | Exact match |
| 2022-06 | detection | 116 | 43 | 73 | 64 | 0.385650 | Exact match |
| 2022-07 | prediction | 278 | 72 | 206 | 94 | 0.324324 | Exact match |
| 2022-07 | detection | 119 | 67 | 52 | 99 | 0.470175 | Exact match |

Full rerun uses monthly saved raw-minute input and the reconstructed manuscript algorithm; it compares **every decision tick** for wavelet-energy and threshold series, not just final metrics. Independent greedy one-to-one NOAA matching and event IDs agree. Separate prefix-causality, future-flux perturbation, short-gap/long-gap, and matching-boundary checks completed successfully.

**Limits:** The NOAA catalog available with the upload covers April–July, not the entire 2022 year. Confirmed Apr–Jul TP/FP/FN cannot certify the manuscript’s January–December pooled TP/FP/FN.

## 3. Baseline reconstruction: interpretation-sensitive

### Fixed baseline formulas applied to full-year GOES 2022 for alert-volume diagnostics

| Method | Independent alerts, full 2022 |
|---|---:|
| SMA_105_x1.31 | 2,135 |
| SMA_10_x1.1 | 3,556 |
| EWMA_10_x1.05 | 4,805 |
| Slope_20_0.003545 | 4,982 |

These baseline alert counts were computed with: 2-minute decision grid; 120-minute warm-up; 4 elapsed minutes persistence; up-to-12-minute alert merging; previous-only SMA and EWMA; causal 20-minute log-slope. Reconstructed choices for EWMA initialization, missing-data handling, and gap eligibility can differ from the unpublished full-year baseline implementation.

### Provisional April–July NOAA-scored baseline results

| Method | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| EWMA_10min_x1.05 | 515 | 1007 | 239 | 0.338 | 0.683 | 0.453 |
| SMA_105min_x1.31 | 272 | 422 | 482 | 0.392 | 0.361 | 0.376 |
| SMA_10min_x1.1 | 434 | 677 | 320 | 0.391 | 0.576 | 0.465 |
| Slope_20min_gt0.003545 | 688 | 892 | 66 | 0.435 | 0.912 | 0.590 |

These scores are for **April–July only** and must not be compared as if they were the manuscript’s **January–December** results. With 2,305 NOAA events assumed for full-year 2022, the published three-decimal precision/recall pairs cannot simultaneously arise from these independently reconstructed 2022 baseline alert totals (rounding-interval check); this demonstrates **implementation mismatch or incomplete baseline protocol**, not fabrication or falsification of the manuscript results.

## 4. Camera-ready manuscript claim status

| Manuscript claim | Audit outcome |
|---|---|
| 2022 Prediction alerts = 3,117 | **Verified exactly** from original annual GOES archive |
| 2022 Detection alerts = 1,346 | **Verified exactly** from annual GOES archive |
| 12-hour Prediction alerts = 2,889 | **Verified exactly** from annual GOES archive |
| 2022 C/M/X reference events = 2,305 | Not independently verified: full-year NOAA catalog not supplied |
| 2022 Prediction TP=912 / FP=2,205 / FN=1,393 | **Arithmetic consistent**, matching not independently recreated for complete year |
| 2022 Detection TP=776 / FP=570 / FN=1,529 | **Arithmetic consistent**, matching not independently recreated for complete year |
| 12-hour TP=921 / FP=1,968 | **Arithmetic consistent** and total alerts exact, NOAA split unverified |
| 2022 Baseline F1 values | Partially checked: independent alternative implementation, exact reported values unverified |
| Full-year parameter sensitivity / ablation | Not independently reproduced |
| Frozen 2023 prediction/detection F1 and 8.2% reduction | Not verified: 2023 input, labels and saved outputs absent |

## 5. Scientific and methodological corrections needed

1. **Interpolation and causality.** The reconstruction backfills short missing gaps after the right-hand observed endpoint becomes available and records `available_at`; it does not use an unobserved right edge for alerts. The manuscript should explain this precisely instead of claiming linear interpolation and no look-ahead without implementation detail. Distinguish the reconstruction from an original unpublished implementation.
2. **Warm-up versus horizon.** The reconstruction begins scoring after 120 minutes with partial trailing quantile history even when the configured horizon is 6 or 12 hours. The paper must disclose this initialization strategy.
3. **4-minute persistence.** At two-minute cadence, the reconstruction requires positive tests at t, t+2, and t+4; the action time and reported lead are the *confirmed alert time*, not the first threshold crossing.
4. **Peak-relative rather than onset-relative lead.** NOAA peak minus alert timestamp is not necessarily a true pre-flare onset lead. The supplied May–July onset audit records 198/219 matches before the reported flare start and 21/219 at/after start.
5. **DWT implementation.** Specify `db2`, decomposition level 3, `symmetric` boundary extension, use of the level-3 detail cD3, and squared-energy calculation.
6. **Quantile convention.** State that current valid energy is included in the inclusive trailing [t−T,t] decision history and that the quantile interpolation method is `linear`.
7. **Quality flags.** The reconstruction retains finite flux with nonzero XRS quality flags; mention this or implement and evaluate an explicit quality filter.
8. **Baseline protocol.** Provide the exact script, tuned parameter-selection window, definitions for EWMA initialization and missing data, and matched events for each full-year baseline. Do not substitute reconstructed April–July baseline F1 for the paper’s full-year values.
9. **Ablation.** One-factor-at-a-time parameter sensitivity is not a component-ablation experiment. Rename the section or add true component ablations.
10. **Independent 2023.** Without the complete GOES 2023 input and NOAA 2023 event catalog, the claimed out-of-sample results are unverified and should be supported by source data and per-month TP/FP/FN.

## 6. Reviewer compliance (evidence-qualified)

| Reviewer issue | Manuscript response | Verification |
|---|---|---|
| One-month evaluation | Full 2022 evaluation claimed | Full-year **alert counts verified**; full-year NOAA scores pending |
| High false positives | 12h history and discussion | 12h **alert volume verified**; TP/FP split pending |
| Low standalone F1 | Explicit limitation and 2022 tables | Arithmetic checks pass; full-year NOAA matching pending |
| Insufficient baselines | SMA, EWMA, slope added | Alternative Apr–Jul independent tests; exact full-year baselines pending |
| No independent temporal validation | Frozen 2023 claimed | **Cannot verify** without 2023 inputs/labels/results |
| Sensitivity and ablation | Table VIII and discussion | One-factor-at-a-time results not reproduced; component ablation not demonstrated |
| Evaluation protocol | Expanded sections | Must clarify partial history, confirmation time, label matching, and peak vs onset |

## 7. Files still needed for a final signoff

- Raw **GOES 2023** 1-minute XRS-B source and quality metadata, or the exact preprocessed 2023 dataset used.
- Independent NOAA C/M/X flare-event catalogs for **all months Jan–Dec 2022 and 2023**, with start/peak times, class and event identifiers, produced by the same catalog-cleaning rules.
- The scripts and saved per-month outputs for **full-year baseline comparison, full-year parameter sensitivity and the 2023 frozen-parameter validation**.
- Published/accepted original April output or code if exact historical reproduction is a requirement.

## 8. Reproduction inventory and checksums

| Uploaded file | SHA-256 prefix |
|---|---|
| `GOES_2022_FULL.zip` | `67b63eae17245227ccc51b77…` |
| `Solar_Flare_Paper_Code.zip` | `e0c5028cb66f5e57e767f8bf…` |
| `NOAA_Flare_Events_May_June_July_2022.zip` | `1e62db93060625810b6beb10…` |
| `Solar_Flare_Manuscript_Extension_May_June_July_2022 (2).zip` | `fc04075851a057534f7718ef…` |
| `run_solar_flare.py` | `67267bf0a790f32fde3387a5…` |
| `moving_average_baseline_may_june_july.py` | `8d51c86edfd744ad9d465fd0…` |
| `ACDSA2027_Camera_Ready_Source.docx` | `71eb43b615d0a480ecbf169c…` |

### Methods used in this audit

- `reproduce_four_months.py`: recomputes feature energy, trailing quantiles, eventization and NOAA event matching for all provided months; comparison against saved outputs.
- `year_2022_counts.py`: recomputes full-year 6-hour wavelet Prediction/Detection alert counts.
- `year_2022_12h_batch.py`: independently reruns full-year 12-hour wavelet alert volumes.
- `available_baseline_audit.py`: reconstructs fixed causal baseline metrics on provided four months.
- `year_2022_baseline_alert_counts.py`: evaluates fixed-method baseline alert volumes for all 2022.
- `shim/pywt.py`: explicitly limited independent NumPy implementation of the db2/symmetric/level3 DWT, validated against saved reference energy values; not the official PyWavelets distribution.

### Conclusion

**The paper has meaningful computational support for its 2022 wavelet alert-generation counts and the claimed change in total 12-hour alert volume. This does not establish the 2022 full-year NOAA precision/recall/F1 values, exact baseline scores, parameter-sensitivity F1, or 2023 validation. Do not describe these remaining claims as independently verified until their missing inputs and analysis outputs are available.**
