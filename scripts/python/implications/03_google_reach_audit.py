"""Step 03: does the concentration claim extend to the unscanned mass?

ms Figure 3 rests on scanned domains: Google is the top tracker for ~99.6%
of users. Unscanned visits were zero-filled, which can only understate
reach. Here we measure directly: among the July-2026 Blacklight scans of the
audit sample (unscanned domains), what share load at least one third-party
host owned by Google LLC (owner map: pinned DuckDuckGo Tracker Radar)? The
same statistic over the original Jan-2025 scanned population (visit-
weighted) is the comparison.

Writes: tables/implications_google_reach_audit.tex
"""

import json
import os
import sys

import pandas as pd
import tldextract
from statsmodels.stats.proportion import proportion_confint

import config

sys.path.insert(0, os.path.abspath(".."))
from utilities import pandas_to_tex  # noqa: E402

_extract = tldextract.TLDExtract(suffix_list_urls=())


def google_domains():
    ddg = pd.read_csv(config.FP_DDG_CATEGORIES)
    return set(ddg.loc[ddg["owner"] == "Google LLC", "domain"])


def has_google(path, goog):
    with open(path) as f:
        data = json.load(f)
    third = data.get("hosts", {}).get("requests", {}).get("third_party", [])
    for host in third:
        if _extract(host).top_domain_under_public_suffix.lower() in goog:
            return True
    return False


def main():
    goog = google_domains()
    print(f"Google LLC domains in Tracker Radar: {len(goog)}")

    # Original scanned population, visit-weighted
    yg = pd.read_csv(config.FP_YG_IND_DOMAIN)
    visits = yg.groupby("private_domain")["visits"].sum()
    rows = []
    n_bad = 0
    for fname in sorted(os.listdir(config.FP_BL_JSON_DIR)):
        if not fname.endswith(".json"):
            continue
        domain = fname[:-5].replace("_", ".")
        try:
            g = has_google(os.path.join(config.FP_BL_JSON_DIR, fname), goog)
        except (json.JSONDecodeError, OSError):
            n_bad += 1
            continue
        rows.append((domain, g))
    pop = pd.DataFrame(rows, columns=["private_domain", "google"])
    pop["visits"] = pop["private_domain"].map(visits).fillna(0)
    pop_share = (pop["google"] * pop["visits"]).sum() / pop["visits"].sum()
    print(f"scanned population: {len(pop):,} domains ({n_bad} unparseable)")
    print(f"  visit-weighted share with any Google third party: {pop_share:.1%}")
    print(f"  unweighted share: {pop['google'].mean():.1%}")

    # Audit sample (unscanned domains, scanned July 2026), by stratum
    sample = pd.read_csv(config.FP_AUDIT_SAMPLE)
    sample["json"] = sample["private_domain"].map(
        lambda d: os.path.join(config.FP_AUDIT_JSON_DIR, d.replace(".", "_") + ".json")
    )
    sample["scanned_now"] = sample["json"].map(os.path.exists)
    sample.loc[sample["scanned_now"], "google"] = sample.loc[
        sample["scanned_now"], "json"
    ].map(lambda p: has_google(p, goog))

    out = [
        {
            "group": "Scanned population, Jan 2025 (visit-weighted)",
            "share_pct": f"{100 * pop_share:.1f}",
            "n": f"{len(pop):,}",
            "ci95": "--",
        }
    ]
    for label, col in [
        ("Unscanned sample, visits stratum (scanned Jul 2026)", "in_visits_stratum"),
        ("Unscanned sample, uniform stratum (scanned Jul 2026)", "in_uniform_stratum"),
    ]:
        sub = sample[sample[col] & sample["scanned_now"]]
        k, n = int(sub["google"].sum()), len(sub)
        lo, hi = proportion_confint(k, n, method="wilson")
        out.append(
            {
                "group": label,
                "share_pct": f"{100 * k / n:.1f}",
                "n": str(n),
                "ci95": f"[{100 * lo:.0f}, {100 * hi:.0f}]",
            }
        )
        print(
            f"{label}: {k}/{n} = {100 * k / n:.1f}% CI[{100 * lo:.0f},{100 * hi:.0f}]"
        )

    pandas_to_tex(
        pd.DataFrame(out),
        os.path.join(config.TABLES_DIR, "implications_google_reach_audit"),
    )
    print("wrote tables/implications_google_reach_audit.tex")


if __name__ == "__main__":
    main()
