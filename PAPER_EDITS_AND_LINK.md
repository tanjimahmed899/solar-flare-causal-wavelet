# Paper corrections and code-availability statement

Do **not** insert a URL until the repository has been published and tested. Replace `<USERNAME>` with the actual GitHub account/repository name.

**Conservative code-availability wording (accurate for this package):**

> A reproducible implementation of the causal wavelet-energy pipeline, together with April–July 2022 benchmark inputs, NOAA-based event matching, and validation artifacts, is available at https://github.com/<USERNAME>/solar-flare-causal-wavelet. Supporting full-year experiment materials will be released when their corresponding input data and outputs have been consolidated.

If publication requires *all full-year results* to be reproducible via the project link, this package is **not sufficient yet**: see `REPRODUCIBILITY_STATUS.md`.

Suggested manuscript corrections based on the actual reconstructed code:

1. Explain the `available_at`-tracked short-gap interpolation and the no-alert-at-interpolated-right-edge rule.
2. Explain that 120-minute warm-up is followed by a partial trailing quantile history until the configured horizon is fully populated.
3. Clarify that 4 elapsed minutes of persistence at 2-minute sampling requires three positive decision ticks; report confirmed time as alert time.
4. Call the lead time *peak-relative*; do not imply all matched alerts predate flare onset.
5. State PyWavelets db2/cD3 symmetric-extension wavelet-energy configuration and linear quantile interpolation, as in source.
6. Describe NOAA peak matching as retrospective evaluation rather than online model input.
7. Clarify baseline calibration, and do not describe one-factor parameter sensitivity as complete component ablation.
8. Ensure the manuscript's 2023 claims are supported by frozen 2023 code/input/labels/results before calling the repository a full replication package.

When adding the link to an IEEE two-column paper, use a brief Code Availability sentence at the end of Methodology or just before References, respecting the conference's page limit and publisher policy. Confirm all authors approve any public release.
