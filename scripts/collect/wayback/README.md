# Wayback Machine validity checks

Extends the HTTP Archive pipeline (`../httparchive/`) to the browsing mass
that neither Blacklight nor the June-2022 HTTP Archive crawl measured, and
supplies two supporting checks. One validity strand per notebook — see
`../validity_strands.md` for the full strand map.

- **Strand B (coverage)**: never-measured domains get June-2022 Wayback
  snapshots; a calibrated fill tightens the coverage bounds a third time.
- **Strand C (instrument)**: contemporaneous WB-vs-HA agreement (both June
  2022) quantifies what a static parse of archived HTML sees relative to a
  full request log — the undercount the calibration must absorb.
- **Strand D (missingness mechanism)**: what *is* the unmeasured mass?
  Composition (a large share is ad-tech/tracker infrastructure with no
  homepage — meter-logged redirect and sync hops, not destinations) and
  2022 liveness (dead vs merely unscannable) for the rest.

## What is fetched and saved (all gzipped, all idempotent)

- `data/wayback/cdx/<domain>.json.gz` — capture lists (CDX-shaped; a miss is
  itself data: no evidence the domain was live mid-2022).
- `data/wayback/html/<domain>.html.gz` — original archived bytes
  (`Mode.original`, no replay rewriting; verified by
  `02_fetch_snapshots.py --preflight`).
- `data/wayback/wb_manifest.csv` — one row per target: group, snapshot
  timestamp, fetch status, bytes.

All archive.org access goes through the EDGI
[`wayback`](https://wayback.readthedocs.io/) library, whose process-wide rate
limits and exponential-backoff retries follow Internet Archive guidance — a
hand-rolled multi-worker fetcher got this machine temporarily blocked, so the
library's pacing is load-bearing, not cosmetic.

Static-parse limits (stated in `03_parse_static_requests.py`): JS-injected
trackers are invisible (systematic undercount, quantified in strand C), no
cookie visibility, no behavioral measures.

## Run order

| Step | Script | Output |
|------|--------|--------|
| 1 | `01_build_wb_targets.py` | `data/wayback/wb_targets.csv` (remainder + calib_bl + calib_ha groups) |
| 2 | `02_fetch_snapshots.py` (`--preflight` first) | cdx/, html/, `wb_manifest.csv` (~2h, resumable, 6 workers) |
| 3 | `03_parse_static_requests.py` | `data/wayback/wb_domain_measures.csv` |
| 4 | `04_wb_ha_agreement.ipynb` (strand C) | `tables/wb_ha_agreement.tex` |
| 5 | `05_liveness_2022.ipynb` (strand D) | `tables/wb_liveness.tex` |
| 6 | `06_coverage_bounds_wayback.ipynb` (strand B) | `tables/coverage_bounds_wayback.tex`, `figures/coverage_bounds_wayback.*` |

`make wayback` runs steps 1–3.

## Reproducibility

- Sampling seeds, snapshot window, and worker/politeness settings pinned in
  `config.py`; classifier reuses the pinned Tracker Radar table built by
  `../httparchive/04_classify_trackers.py`.
- Everything downstream reproduces from the gzipped on-disk caches without
  touching archive.org again.
