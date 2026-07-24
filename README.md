## Shedding Blacklight on Online Privacy

We exploit passively collected browsing data from comScore along with https://themarkup.org/blacklight to estimate whether the websites visited by poorer people and less educated people tend to visit websites with lower privacy standards than the better-off and better-educated people. 

We also use data from https://whotracks.me/ to augment our analyses.

### Data

* [YG data](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/VIV4TS)
* [Blacklight data on YG Domains](https://doi.org/10.7910/DVN/3N7TDZ)

### Scripts

* [Scrape Blacklight Data Using Scrapy](https://github.com/themains/private_blacklight/tree/master/scripts/privacy_scraper)
* [Scrape Whotracksme Data](https://github.com/themains/private_blacklight/blob/master/scripts/get_whotracksme_privacy_data.py)

### Measurement validity

Two features of the design deserve scrutiny: browsing was observed in June
2022 but Blacklight scanned in ~January 2025, and Blacklight completed scans
for only ~53% of unique panel domains (~76% of visits). We investigated both
with independent measurements — HTTP Archive's monthly crawls (BigQuery) and
Wayback Machine snapshots — letting the data settle each question in either
direction. Full strand map: [`scripts/validity_strands.md`](scripts/validity_strands.md);
pipelines: [`scripts/httparchive/`](scripts/httparchive/) and
[`scripts/wayback/`](scripts/wayback/).

**A. Timing (does 2025 tracking represent June-2022 browsing?)** On matched
panel domains measured by the same instrument at both dates, visit-weighted
ad-tracker prevalence moved 98.1% → 95.2% between June 2022 and June 2025;
"any known tracker" barely moved (99.9% → 98.1%); header-set third-party
cookies and Facebook requests declined more (−9.5pp and −30.1pp, desktop).
Recomputing *user-level* exposure under June-2022 vs Jan-2025 measurements
(same instrument, same domains) shifts means modestly — ad trackers −6.3%,
GA −4.3%, Facebook −30%, header-set cookies +21% — while the cross-user
ordering the demographic analyses rely on is strongly preserved
(r = 0.75–0.91). Direction: 2025-era scans, if anything, *understate*
June-2022 exposure. (`tables/httparchive_drift.tex`,
`tables/temporal_user_exposure.tex`)

**B. Coverage (how much could unscanned domains move the estimates?)** The
paper's construction already treats unscanned visits as zero tracking, so
published rates are lower bounds by design. Replacing assumption with
measurement — June-2022 HTTP Archive request maps cover 62.7% of the missing
visit mass, Wayback snapshots another 3.2%, with fills calibrated to
Blacklight's own scale on jointly measured domains — narrows the ad-tracker
interval from [4.98, 11.69] (assumption alone) to [6.20, 8.27] trackers per
visit, versus 4.98 published. The same pattern holds for cookies (6.12
published; [7.56, 9.97] measured). The published estimates are conservative:
accounting for unscanned domains raises exposure, in line with the paper's
substantive claims. (`tables/coverage_imputation_bounds.tex`,
`tables/coverage_bounds_wayback.tex`)

**C. Instruments agree where they measure the same thing.** Contemporaneous
cross-checks: HTTP Archive vs Blacklight (both ~Jan 2025, mobile) agree on
ad-tracker presence for 86% of shared domains (Spearman 0.60 on counts);
Wayback static parses vs HTTP Archive (both June 2022, median snapshot 0 days
from mid-month) recover 92% of ad-tracker presence and 95% of any-tracker
presence, weaker for JS-injected measures (Facebook 47%). Construct
differences (header-set vs JS-set cookies; GA presence vs GA remarketing) are
labeled in every table. (`tables/ha_bl_agreement.tex`,
`tables/wb_ha_agreement.tex`)

**D. What the unscanned half actually is.** Among visits to domains
Blacklight could not scan, at least 66% of the visit mass (80% on the subset
we could check) was on domains demonstrably alive in mid-2022 — scan failures
reflect unscannability (bot detection, timeouts), not dead sites. And of the
never-measured remainder (8.8% of visits), a quarter of the visit mass is
ad-tech infrastructure (cookie-sync, prebid, and CDN endpoints logged as
"visits" by the meter during redirects) — not websites with unknown tracking,
but artifacts of tracking itself, for which the zero-fill is closer to a
category correction than an undercount. (`tables/wb_liveness.tex`)

A direct audit backs this up ([`scripts/selection_audit/`](scripts/selection_audit/)).
Parsing the original scraper's error log shows 95% of unscanned domains
failed with the API returning an empty result (bot walls / JS challenges /
non-HTML endpoints); a further 4.5% of domains (7.2% of unscanned visits)
failed on the *scraper's own* connection to the Blacklight API — noise, not
a domain property; and the 51 domains excluded by a reachability pre-check
carry 10.5% of unscanned visits and include plainly live major sites — false
exclusions. A seeded random sample of 200 unscanned domains (100 drawn ∝
visits, 100 uniform), each coded against a written rubric
([`CODING_RUBRIC.md`](scripts/selection_audit/CODING_RUBRIC.md)), finds the
unscanned *visit mass* is mostly ordinary user-facing content (62%, CI
[51, 70]) plus tracking/CDN infrastructure (28%); dead-with-no-trace domains
are 7% of visit mass (15% of the domain *list*). Re-scanning the sample with
Blacklight in July 2026 succeeded for 66% of it — and on those domains,
tracking measured directly is *heavier* than in the originally scanned
population (ad trackers 8.8 per visit-weighted domain, 95% CI [5.0, 13.3],
vs 6.5; third-party cookies 10.5 vs 7.7) and at least as heavy as strand B's
calibrated fill predicts (5.3). Direct measurement therefore lands on the
same side as strands B and D: excluded domains do not dilute exposure, and
zero-filling them understates it. (`tables/scan_failure_reasons.tex`,
`tables/selection_audit_composition.tex`,
`tables/selection_audit_tracking.tex`)

## 🔗 Adjacent Repositories

- [themains/reg_breach](https://github.com/themains/reg_breach) — Have I Been Pwned? Yes. Evidence from HIBP and Emails From Voter Registration Files.
- [themains/pwned_pols](https://github.com/themains/pwned_pols) — A third of the politicians have had their data breached at least once. More alarmingly, over one in five have had their sensitive data, such as bank account numbers, biometric data, browsing history, chat logs, credit card CVV, etc., breached.
- [themains/pwned](https://github.com/themains/pwned) — How Often Are Americans' Accounts Breached?
- [themains/private_gov](https://github.com/themains/private_gov) — How common are third-party cookies, trackers, key loggers, etc. on government websites?
- [themains/know-your-ip](https://github.com/themains/know-your-ip) — Know Your IP: Get location, blacklist status, shodan and censys results, and more.
