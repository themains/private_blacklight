# HTTP Archive validity checks

Two questions bear on whether the paper's exposure estimates are measuring what
we think they are. This pipeline investigates both honestly, using HTTP
Archive's monthly crawls (stored in BigQuery), and lets the data settle them
either way — including if it surfaces real bias.

1. **Does 2025 tracking represent the 2022 browsing window?** Browsing was
   observed in June 2022 but Blacklight scanned in ~Jan 2025. We pull the
   June-2022, Jan-2025, and June-2025 crawls, reconstruct per-domain tracking
   from the request maps, and (a) measure how domain-level prevalence changed
   over the window, then (b) recompute *user-level* exposure twice from the
   same instrument — once with June-2022 measurements, once with Jan-2025 —
   so the difference isolates time, not instrument scale.
2. **Does the ~53% of scannable domains represent real browsing?** Blacklight
   completed scans for only ~53% of unique domains. We quantify how much
   user-level exposure could shift under best-/worst-case assumptions about
   the unscanned visits, then replace assumption with measurement where the
   June-2022 crawl covers an unscanned domain, using a fill *calibrated to the
   Blacklight scale* (expected Blacklight count given HTTP Archive presence,
   estimated on domains both instruments measured).

The point is to find out what is true, not to defend a prior conclusion.

## What HTTP Archive can and cannot recover

HTTP Archive loads one root page per origin (like Blacklight's single-page
scan) and records every request. From the request map we can independently
reconstruct **4 of the 7** Blacklight measures — ad trackers, third-party
cookies, Facebook Pixel, Google Analytics. The three *behavioral* measures
(canvas fingerprinting, session recording, key logging) cannot be recovered
from a static request map and stay Blacklight-only, examined through the
over-time comparison instead.

## Authentication (do this first)

BigQuery query jobs need **Application Default Credentials**, *not* an API key
(an `AIza…` key cannot run BigQuery jobs). One-time setup:

```bash
gcloud auth application-default login          # opens a browser
export BQ_BILLING_PROJECT=your-gcp-project-id  # your project, billed for scans
```

> Security: never paste keys into chat, commit them, or store them here. If a
> key was ever exposed, rotate it in the Cloud Console.

## Cost control

Every billed query is preceded by a **dry run** that prints the exact bytes to
be scanned and the dollar estimate (`$6.25 / TiB`). BigQuery also gives 1 TiB
free per month. Levers, all in `config.py`:

- Queries select only the columns needed (`page`, `url`), never the huge
  `response_body`/`summary` columns.
- `RANK_CAP` / `COOKIE_RANK_CAP` prune bytes via the table's `rank` clustering.
  The Set-Cookie scan reads `response_headers` (large), so it caps tighter.

Run `02_ha_dryrun.py` and review the estimate **before** `03_ha_extract.py`.

## Run order

Steps 1–4 acquire and classify the data; notebooks 5–8 are one validity
strand each (see `../validity_strands.md` for the strand map).

| Step | Script | Billed? | Output |
|------|--------|---------|--------|
| 1 | `01_build_ha_targets.py` | no | `data/httparchive/ha_targets.csv` + visit-coverage curve |
| 2 | `02_ha_dryrun.py` | no (dry run) | prints per-query byte/$ estimate |
| 3 | `03_ha_extract.py --confirm` | **yes** | `data/httparchive/ha_requests_*.parquet`, `ha_cookies_*.parquet` |
| 4 | `04_classify_trackers.py` | no | `data/tracker_lists/*`, `data/httparchive/ha_domain_measures.csv` |
| 5 | `05_temporal_domain_drift.ipynb` (strand A) | no | `tables/httparchive_drift.tex`, `figures/ha_drift.*` |
| 6 | `06_temporal_user_exposure.ipynb` (strand A) | no | `tables/temporal_user_exposure.tex`, `figures/temporal_user_exposure.*` |
| 7 | `07_coverage_bounds.ipynb` (strand B) | no | `tables/coverage_imputation_bounds.tex`, `figures/coverage_bounds.*` |
| 8 | `08_instrument_agreement_ha_bl.ipynb` (strand C) | no | `tables/ha_bl_agreement.tex` |

All steps are idempotent: cached parquet/CSV outputs are reused, so re-running
never re-bills. `make httparchive` runs steps 1–2 (then stops for sign-off).

## Reproducibility

- All crawl dates, clients, rank caps, and the DDG Tracker Radar ref are pinned
  in `config.py`.
- Pin `DDG_TRACKER_RADAR_REF` to a commit SHA (not `main`) to freeze tracker
  classification for the final run.
- Raw BigQuery extracts are cached to Parquet so the analysis reproduces from
  disk without re-querying.
