# Implementation choices and replication limits

This is a reconstruction of the supplied manuscript's main causal wavelet method. The old April code is not the manuscript implementation. No parameter was selected to fit published April counts or improve May-July results.

## Fixed manuscript settings

- Raw linear GOES XRS-B 1-8 angstrom flux, 1-minute cadence, one copy per duplicate timestamp.
- db2 DWT, level-3 detail energy (sum of squared cD3 coefficients), right-aligned 30-minute window.
- Decisions every 2 minutes, anchored at each month's 00:00 UTC.
- Trailing 6-hour quantiles: Q80 Prediction, Q95 Detection. Initial 120 minutes excluded from alerts/evaluation.
- Four elapsed minutes of above-threshold observations before issuing an alert. Same-stream alerts separated by no more than 12 minutes are merged.
- C/M/X NOAA reference peaks only; no model-derived labels.
- Prediction: chronological greedy one-to-one matching to the earliest unused NOAA peak 10-90 minutes after alert issuance, inclusive.
- Detection: chronological greedy one-to-one matching to the closest unused NOAA peak within +/-10 minutes, inclusive. Distance ties choose the earlier peak, then event ID.
- Month-level precision, recall and F1. Prediction lead quartiles use exactly the same TP pairs.
- A display-only percentile-rank priority is fixed at the confirmed event start. Priority never selects matches or changes alerts.

## Choices the manuscript does not completely specify

| Issue | Main implementation | Additional record/check |
|---|---|---|
| 'Two consecutive decision intervals (4 min)' | Requires elapsed 4 minutes: above threshold at t, t+2 and t+4; issues at t+4 | Two positive decisions, issued at t+2, are scored separately |
| Alert start vs persistence confirmation | Main `start_time` is actual confirmation/issuance; no backdating | `crossing_start_time` is retained; retrospectively scoring it is a separate sensitivity case |
| Short-gap linear interpolation vs no future information | Backfill at most 2 missing minutes only when the right endpoint arrives; never issue a decision at an unobserved right edge | Every filled sample has an `available_at` timestamp; prefix and future-perturbation tests passed |
| DWT boundary mode | PyWavelets symmetric extension, using only values inside the past/current 30-minute window; this matches the supplied code's default | Mode is explicitly recorded in configuration.json |
| Quantile estimator and current feature | NumPy linear quantile on finite decision-time features in inclusive [t-360,t], including current feature | Initial 120-minute warm-up permits a partially filled history |
| Warm-up and month boundaries | Independent monthly initialization; first 120 minutes excluded; no daily resets | Monthly matching uses NOAA peaks in the same UTC month; boundary opportunities can be truncated |
| Quality flags and unavailable windows | Nonfinite/negative flux is unavailable. Finite flagged data is retained because the paper gives no flag filter. Any unavailable feature window resets alert continuity and prevents merging across that gap | All gaps and finite flagged minutes are reported |
| Reference events during outages | All C/M/X peaks after warm-up remain in the denominator; data gaps withhold decisions, rather than silently deleting labels | Missing GOES flux at the exact NOAA peak is flagged separately |
| Threshold equality | Strictly greater than the threshold opens/continues an event; equal or lower closes it | The comparison is fixed in code |
| Baseline comparison | No SMA baseline result is claimed | The original SMA window, adaptive rule and April parameter grid are absent from the supplied materials |

The sensitivity cases are declared interpretations, not a search for the best score. Use `confirmed_4min` as the main result. Never pool or select the highest sensitivity score as though it were a single preregistered run.

## April audit

The published paper reports 122 NOAA C/M/X events, 167 Prediction alerts / 35 TP, and 101 Detection alerts / 34 TP. The official complete SWPC April archive contains 224 C/M/X peaks. This reconstruction produces 247 Prediction alerts / 86 TP and 116 Detection alerts / 69 TP. Its 39-minute Prediction median does not establish replication: the reference population, alerts and matched pairs differ.

The original April label catalog, exclusions and executable manuscript implementation are needed to reproduce the published tables exactly. The manuscript's SMA baseline cannot be reproduced from its reported scores alone.

## Data and evaluation scope

The supplied GOES CSV has four identical XRS-B/quality-flag rows per minute. One copy is retained after verifying equality. The spacecraft identity is not established by the CSV filename; the NOAA reference observatory is retained, including G17 reports.

No NOAA C/M/X peaks fall inside the initial 120-minute warm-up in these four months. The May-July reference counts therefore remain 257, 107 and 166. July includes one peak with missing GOES flux at the exact minute; it remains a reference event. NOAA event numbers reused for distinct peaks are kept separate.

Monthly resets and restricting matches to the same month are fixed for every run. A Prediction near month end can be scored as FP even if an out-of-month peak would have followed within 90 minutes. This boundary convention is not fully specified in the paper and is stated here instead of hidden.
