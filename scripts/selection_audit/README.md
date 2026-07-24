# Selection-bias audit of unscanned domains (strand D, deepened)

Blacklight produced no scan for ~47% of unique panel domains (23.6% of
visits). Strands B and D bound and characterize that missing mass
indirectly; this module examines it **directly**: parse why every scan
failed, draw a seeded random sample of unscanned domains, code what each one
actually is against a written rubric, probe its current status, and re-scan
it with Blacklight now. Findings are reported in whichever direction they
point.

## Design

- **Sample** (`SAMPLE_SEED = 20250112`): two draws from the same unscanned
  pool, without replacement — 100 proportional to panel visits (composition
  of unscanned *visit mass*) and 100 uniform (composition of the unscanned
  *domain list*). Unscanned-only invariant asserted in code.
- **Coding**: rubric in [`CODING_RUBRIC.md`](CODING_RUBRIC.md); one category
  + cited rationale per domain in `data/selection_audit/codes_claude.csv`;
  a seeded 20-domain subset (`SPOTCHECK_SEED`) is flagged in
  `audit_sample_coded.csv` for independent user adjudication
  (`user_category` column; agreement reported by `04_code_sample.py`).
- **Re-measurement**: live probe (DNS + GET) and a fresh Blacklight scan of
  all 200 via the public API, July 2026.

## Run order

```bash
python 01_parse_scan_errors.py   # error log -> per-domain failure reasons
python 02_draw_audit_sample.py   # seeded 2x100 sample + evidence columns
python 03_probe_and_rescan.py    # probe + Blacklight rescan + parse (slow; nohup)
python 04_code_sample.py         # evidence sheet; validate codes; spot-check
jupyter nbconvert --to notebook --execute --inplace 05_selection_audit.ipynb
```

## Outputs

| artifact | content |
|---|---|
| `data/selection_audit/failure_reasons.csv` | per-domain failure reason, reach, visits |
| `data/selection_audit/audit_sample.csv` | the 200 sampled domains + evidence columns |
| `data/selection_audit/probe_results.csv` | probe status/title + fresh `bl_*` scan measures |
| `data/selection_audit/audit_sample_coded.csv` | evidence + category + rationale + spot-check flags |
| `data/blacklight_json_audit/` | raw July-2026 Blacklight JSONs |
| `tables/scan_failure_reasons.tex` | failure-cause composition, domain- and visit-weighted |
| `tables/selection_audit_composition.tex` | coded category shares by stratum, Wilson CIs |
| `tables/selection_audit_tracking.tex` | direct tracking on unscanned domains vs scanned population vs strand-B fill |
| `figures/selection_audit_tracking.{pdf,png}` | the same comparison, visually |

Caveats carried through the notebook: 2026-scannability is a selected
subset of the unscanned pool; fresh scans measure July-2026 tracking (strand
A bounds the drift); probe ran behind a content-filtering network
(`network_filtered` rows are classified from other evidence).
