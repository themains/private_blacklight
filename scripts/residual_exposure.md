# Residual exposure: what defenses leave behind, and for whom

The paper measures what tracking panelists met while browsing unprotected. This
module asks the next question: **how much of it would a defense have removed, and
was the leftover shared evenly?**

It is a separate question from the validity strands in `validity_strands.md`.
Those bound the paper's existing estimand. These scripts measure something new.

The measurement is possible because Blacklight names the third-party domains
responsible for each behavior it detects. Applying a blocklist to those domains
and recomputing exposure is arithmetic, not simulation. Prior blocker-efficacy
work is crawl-based -- a browser experiment over a sample of ad-supported sites --
and so cannot say what blocking does to a real person's month of browsing.

## Modules

| Module | Question | Scripts | Artifacts |
|---|---|---|---|
| **Residual exposure** | How much exposure survives each defense, and does the age gap survive with it? | `blocking/01`–`05` | `tables/residual_levels.tex`, `tables/residual_age_gap.tex` |
| **Robustness** | Does the age result depend on the `<25` reference cell, or on reading intensity rather than reach? | `blocking/06_robustness.py` | `tables/robustness_age_coding.tex` |
| **Placebo** | Would a random blocklist of the same size have moved the gap the same way? | `blocking/07_placebo.py` | `tables/blocking_placebo.tex`, `figures/blocking_placebo` |
| **Sensitive categories** | Of people who browsed health, finance or job pages, how many were recorded doing it? | `10_sensitive_categories.py` | `tables/sensitive_category_exposure.tex` |
| **Age-gap mechanism** | Are older panelists more exposed because of *what* they browse or *which sites* they pick? | `11_age_gap_decomposition.py` | `tables/age_gap_decomposition.tex` |
| **Device** | Is the age gap an artifact of which device people were metered on? | `12_device_age_gradient.py` | `tables/device_age_gradient.tex` |
| **Security linkage** | Do the same people bear both tracking and security risk? | `13_security_privacy_link.py` | `tables/security_privacy_link.tex` |
| **Population projection** | How many US adults does this correspond to? | `14_poststrat_weights.py` | `tables/population_projection.tex` |

`09_build_visit_panel.py` prepares the visit-level panel the middle four share,
and `blocking/08_figures.py` draws every figure from the result files so a
restyle can never move a number. Run `make blocking` then `make residual`.

**The estimand.** Residual exposure is the tracking a panelist would have met had
a blocklist been enforced on their observed browsing. It is an accounting
counterfactual, not the causal effect of installing a blocker, and it assumes no
behavioral response (browsing held fixed), no site adaptation (no anti-adblock
walls, no CNAME cloaking), and deterministic rule application.

## What the results say

The age gap is reported as a **log-ratio** -- how many times the 65+ mean exceeds
the under-25 mean -- rather than as a coefficient divided by a mean. The latter
divides one noisy estimate by another whose denominator is 0.004 for session
recording, and reporting whichever measure clears significance inflates its own
magnitude. See `blocking/05_residual_analysis.py`.

**Blocking mostly works, and mostly equalizes.** EasyList+EasyPrivacy removes 77%
of ad-tracker exposure and 84% of third-party cookies. The 65+ group went from
1.90x the youngest group's ad-tracker exposure to 1.26x, and from 1.79x to 1.19x
on cookies. A placebo confirms this is not arithmetic: random blocklists removing
the same amount of exposure do *not* narrow the gap the same way (p = .05 for ad
trackers, p < .001 for cookies). Blocklists really do target what older panelists
disproportionately meet.

**Canvas fingerprinting is the exception it was designed to be.** 93% survives
the strongest defense modelled, and the 65+ coefficient does not move
(0.0327 → 0.0335; the change in log-ratio is +0.067, interval [-0.006, +0.177],
covering zero). Blacklight's own card describes these scripts as built to evade
blockers, and the data agrees. This is the most robust finding here: it is a
claim about a *level*, it holds under all three age codings (102-105% of the
unblocked effect), and no ratio with a small denominator is doing any work.

**The session-recording result does not survive its own placebo.** Levels fall
89% and the log-ratio gap appears to widen sharply (1.66x → 4.58x). But random
blocklists removing the same amount of exposure produce shifts spanning
[-1.35, +2.28], and the observed +1.02 sits comfortably inside that range
(p = .31). Removing ~90% of a skewed distribution moves a ratio around a great
deal on its own. **This should not be reported as evidence that protection is
regressive.** What can be said is narrower and rests on reach rather than
intensity: session-recording reach falls from 90% to 44% of panelists, and among
those still exposed the 65+ gap nearly triples (+0.091 → +0.247).

**The age gap is about site choice, not category mix.** Shift-share puts 85% of
the ad-tracker gap on which sites older panelists choose *within* categories and
7% on which categories they browse. Same for cookies (85%/13%).

**Device does not explain it.** The 65+ coefficient is 2.809 pooled and 2.804
with device controlled, significant separately among desktop (n=680) and mobile
(n=439) panelists. Device composition can arithmetically account for 0.4-11% of
the raw gap.

**Projected to the population**: 215M US adults [210, 221] met a keylogging
script in the month and 190M [184, 197] would still have behind a blocker; 233M
[229, 238] met canvas fingerprinting and 232M [227, 236] still would. Intervals
bootstrap panelists and re-rake inside each replicate.

**The two online risks fall on different people.** Tracking exposure rises with
age; the rate of visits to antivirus-flagged domains falls with it. Conditioning
on demographics and browsing volume, the flagged-domain rate predicts *lower*
tracking exposure. The positive raw correlation (r = .26) is a browsing-volume
artifact.

## What these numbers cannot do

- **Hostname-only matching.** Blacklight stores third-party hostnames, not full
  request URLs, so path-keyed filter rules cannot fire. Every residual is
  reported as an interval between "block only what a domain rule certainly
  stops" and "credit every host the list names". See `blocking/README.md`.
- **Two measures are not identified.** Facebook Pixel and Google Analytics cards
  carry no responsible-domain list, so their attribution is assumed. They are
  excluded from every headline.
- **Cookies are attributed per domain, not per cookie.**
- **Category coverage.** Categories are read per visit, which covers all 1,134
  panelists but 29.5% of their visits; the rest sit in a RealityMine file that is
  restricted on Dataverse. `11` gates on the subsample gap tracking the published
  full-sample gap before decomposing.
- **No within-person device comparison exists.** The device files partition the
  sample (695 desktop, 454 mobile, 15 both), so device is a person-level
  attribute here and the device checks are between-person.
- **Raking fixes margins, not selection.** Post-stratification corrects age,
  gender, education and race composition and nothing else.
- **Multiplicity.** The residual age-gap family is 7 measures x 3 tiers = 21
  tests. Following `07_demo_differences.R`, raw-p stars stay in the tables and a
  Bonferroni check at 0.05/21 is printed to the console; 9 of 21 survive it.
- **Unscanned domains still contribute zero**, so residual levels inherit the
  paper's lower-bound convention.
