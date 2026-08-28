# Coding rubric: what is each unscanned domain?

Unit: one sampled domain (`audit_sample.csv`). The code describes the domain's
**function** — what kind of endpoint a panelist's browser was talking to —
using all available evidence, current and archival. A domain that is dead
today but was clearly a shopping site in 2022 is coded `content_site`, not
`dead`; today's status is captured separately by `probe_status`.

## Evidence, in order of weight

1. **Live probe** (`probe_status`, `final_url`, `page_title`, `http_status`)
   — what the domain serves right now. A 403 "Access Denied"/"Just a moment…"
   is a *bot wall*: the site is alive and user-facing, and this is itself the
   likely reason Blacklight's scan failed. `network_filtered` means the
   *probe vantage's* Meraki content filter intercepted the request — the
   domain is filter-listed (typically adult/piracy/ad categories) but its
   own status is unobserved from here; the Blacklight rescan (run from The
   Markup's servers) is the authoritative liveness signal for these.
2. **Wayback June-2022 snapshot title** (`wb_title`) — what it served during
   the panel window; decisive when the domain is dead or parked today.
3. **DuckDuckGo Tracker Radar** (`is_ddg_tracker`, `ddg_categories`,
   `ddg_owner`) — third-party request roles observed at crawl scale.
4. **Domain-name morphology and brand knowledge** — supporting evidence.
   An otherwise evidence-free domain is coded by name alone only when the
   pattern is unambiguous infrastructure (`-sync`, `trk`, `prebid`, `cdn`,
   numbered hosts); a merely *suggestive* content-sounding name with no
   corroboration (no Wayback capture, not HTTP-Archive-measured, no
   recognizable real-world brand) stays `dead`/`unknown`. Coder knowledge of
   a real brand (e.g. a known defunct retailer) counts as corroboration and
   is cited in the rationale.

## Categories (mutually exclusive; precedence top to bottom)

| code | definition | typical evidence |
|---|---|---|
| `adult_content` | User-facing adult site. | title/brand; WB title |
| `adtech_infrastructure` | Endpoint whose function is ad delivery, tracking, cookie-sync, or affiliate/redirect plumbing; appears in browsing logs via redirects and sync hops, not deliberate visits. | DDG listing with ad/tracking categories; sync/prebid/offer-feed URLs; redirect landers |
| `cdn_api_host` | Serves assets or APIs for other properties (CDN hosts, app backends, login/SSO endpoints); no user-facing homepage *by design*. | `cdn`/`api`/`static` host serving bare files or JSON; owned by a platform whose main site is elsewhere |
| `parked_or_forsale` | Parking/for-sale lander, or registrar default page, with no evidence of substantive content during the panel window. | parking template title; for-sale marketplace redirect |
| `content_site` | Ordinary user-facing website: news, shopping, forums, services, corporate, government, games, streaming. | recognizable brand; substantive title today or in WB-2022 |
| `dead` | Unreachable today **and** no informative evidence of prior function (no WB capture, no DDG listing, uninformative name). | NXDOMAIN + nothing else |
| `unknown` | Reachable or not, but evidence insufficient to assign a function. | blank page, ambiguous name, no archival record |

Rules of thumb:

- The main-site/CDN split follows the *sampled domain's* role, not the brand:
  `fbcdn.net` would be `cdn_api_host` even though facebook.com is a content
  site.
- A content brand's *tracking* domain (e.g. a retailer's `metrics.` reg
  domain) is `adtech_infrastructure`.
- Redirect-to-elsewhere today + no 2022 evidence: code by where the redirect
  goes only if it is clearly the same operation (rebrand/consolidation);
  otherwise `unknown`.
- When torn between two codes, take the one **higher in the precedence
  list**, and say so in the rationale.

## Procedure

1. `04_code_sample.py` assembles the evidence sheet
   (`data/selection_audit/audit_evidence.csv`), one row per sampled domain.
2. The coder (Claude) assigns `category` + a one-line `rationale` per domain
   in `data/selection_audit/codes_claude.csv`. Every rationale must cite the
   deciding evidence ("WB-2022 title: …", "DDG: Ad Motivated Tracking", …).
3. Re-running `04_code_sample.py` validates the codes (coverage, category
   vocabulary, non-empty rationales), marks a seeded spot-check subset
   (`SPOTCHECK_N = 20`, `SPOTCHECK_SEED` in `config.py`), and writes
   `audit_sample_coded.csv`.
4. The user fills `user_category` for spot-check rows; the script then
   reports raw agreement. Disagreements are resolved in the user's favor and
   noted in the rationale.
