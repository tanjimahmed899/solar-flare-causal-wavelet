# Data provenance and use

**GOES input:** `data/GOES_XRSB_April_July_2022.csv` is the original uploaded compact four-month benchmark extracted from a larger NOAA GOES XRS-B archive. It contains UTC minute timestamps, XRS-B flux, channel identifier and quality flags. It is distributed here to support the four-month reconstruction only; it is not full-year 2022 or 2023 input. See `docs/METHOD_NOTES.md` and the source manuscript for processing details.

**NOAA labels:** `noaa/catalogs/NOAA_XRA_context_2022_03_31_to_08_01.csv` is a NOAA/SWPC-derived event reference catalog with the surrounding dates used in the April–July benchmark. The original upstream NOAA event reports and any transformation/selection rules should be cited and linked in the public README before publication.

**Research code:** The core pipeline is copied byte-for-byte from `Solar_Flare_Paper_Code.zip`, without modifying algorithm parameters or metrics. Secondary files under `audit_evidence/` are verification summaries, not a replacement for the main pipeline.

**Source integrity:** See `CODE_PROVENANCE.json` for original code-file SHA-256 digests and `MANIFEST_SHA256.txt` for this package's bytes. The package does not claim verification of the manuscript's 2023 validation numbers.
