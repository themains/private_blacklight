# Residual exposure under best-available defenses

What tracking would a panelist still have met if they had browsed behind the
best defense available when the sites were measured?

The paper measures exposure unprotected. Blocker-efficacy studies, meanwhile,
are crawl-based: a browser experiment over a sample of ad-supported sites. What
neither answers is what blocking does to a real person's month of browsing.
Because Blacklight names the third-party domains responsible for each behavior
it detects, that question is answerable by computation rather than simulation.

## Pipeline

| Step | Does | Writes |
|---|---|---|
| `01_extract_attribution.py` | Re-walks all 34,078 scan results keeping `domainData.scripts`, the domains responsible for each detected behavior | `data/blocking/bl_domain_scripts.csv` |
| `02_fetch_blocklists.py` | Fetches EasyList, EasyPrivacy and Disconnect at the commit nearest the scan window; converts Disconnect's JSON to third-party domain rules | `data/blocklists/`, `manifest.json` |
| `03_apply_blocklists.py` | Scores every (site, third-party) pair through adblock-rust; audits how much of each list a hostname test can evaluate | `data/blocking/blocked_pairs.csv`, `rule_coverage.csv` |
| `04_residual_measures.py` | Residual per domain and per person, unblocked figures gated against the published files | `data/blocking/blacklight_domain_residual.csv`, `combined_residual.csv` |
| `05_residual_analysis.py` | Levels, the Table 5 age gradient re-estimated on residuals, bootstrap interval on the change in relative gap | `tables/residual_levels.tex`, `tables/residual_age_gap.tex` |

Run with `make blocking`.

## Defense tiers

| Tier | List | Stands for |
|---|---|---|
| A | Disconnect (Advertising, Analytics, Social, Fingerprinting, Cryptomining) | Firefox Enhanced Tracking Protection |
| B | EasyPrivacy | Privacy-only filtering |
| C | EasyList + EasyPrivacy | uBlock Origin's default pairing |

Lists are pinned to the commit nearest `config.PIN_DATE` (2025-01-10), inside the
Blacklight scan window, so the defense is contemporaneous with the measurement.
`02_fetch_blocklists.py --current` refetches today's lists as a robustness
variant. EasyList versions source fragments rather than built lists, so a
directory of fragments is concatenated at the pinned commit, allowlist
(exception) fragments included.

DuckDuckGo Tracker Radar is deliberately **not** a tier. Blacklight's ad-tracker
count is defined by Tracker Radar, so blocking with it would drive that measure
to zero by construction. The behavioral measures — session recording, key
logging, canvas fingerprinting — are detected by what the page does rather than
by list membership, so they carry no such circularity.

## The hostname problem, and why results are intervals

Blacklight records third-party hostnames, not full request URLs. A filter rule
keyed on a path can never fire against a hostname. The Facebook pixel is the
clean illustration: EasyPrivacy stops it with `||connect.facebook.net/signals/`
and two sibling path rules, none of which a hostname can trigger, while
Disconnect stops the same tracker with `||facebook.net^$third-party`, which does.

Every pair is therefore scored twice, and every downstream measure is an
interval:

- **upper bound on residual** — block only what a domain-level rule certainly stops
- **lower bound on residual** (`_lo`) — additionally credit every host the list
  names with a path rule

Most of each list turns out to be evaluable: 92% of EasyList's network rules,
86% of EasyPrivacy's and 99.8% of Disconnect's are domain-anchored.

## Gates

Failures here are hard errors, not warnings.

1. Attributed ad-tracker domains reproduce published `ddg_join_ads` **exactly**
   on all 34,078 domains.
2. Cookie counts are at least the number of cookie-setting domains, so cookie
   residuals are reported per domain, never per cookie.
3. Behavioral flags re-walked from the JSON match the published columns.
4. Residual never exceeds published, on any domain, measure or tier.
5. Tier C blocks a superset of tier B on every pair.
6. Person-level exposure rebuilt from `yg_ind_domain.csv` reproduces the
   published person file exactly, before any residual is computed.

Gate 1 needs every scan JSON present. If one has gone missing, 01 says which and
how to restore it from `data/blacklight_json.tar.gz`.

## Reading the output

Two measures are held out of the headline. Facebook Pixel and Google Analytics
cards carry no `domainData.scripts`, so their attribution is assumed rather than
observed, and the lists happen to block both largely through path rules. Their
residuals are reported but should not be read as efficacy estimates.

Cookie residuals count unblocked cookie-setting domains, not cookies. Several
cookies can come from one domain and the scan does not say which.
