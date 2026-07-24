"""Step 01: parse the Jan-2025 scrape's error log into per-domain reasons.

data/blacklight_errors.log was written by the original Scrapy spider but never
analyzed. Three message templates cover every line:

  "'groups' key is missing or empty for <domain>. ..."   -> empty_groups
      (the Blacklight API responded but the scan produced nothing: bot walls,
       JS challenges, non-HTML endpoints -- a domain-side property)
  "Request failed for <domain>: <exception>"             -> api_network_error
      (the *scraper's* connection to the Blacklight API failed -- an
       infrastructure hiccup, not a property of the target domain)
  "Website unreachable: <domain>. Skipping..."           -> site_unreachable
      (the site itself failed a pre-scan HEAD/GET reachability check)

One row per domain (a domain retried under empty_groups keeps that reason;
a domain with several reasons keeps the most domain-side one:
site_unreachable > empty_groups > api_network_error).

Writes: data/selection_audit/failure_reasons.csv
        tables/scan_failure_reasons.tex  (composition, domain- & visit-weighted)
"""

import os
import re
import sys

import pandas as pd

import config

sys.path.insert(0, os.path.abspath(".."))
from utilities import pandas_to_tex  # noqa: E402

PATTERNS = [
    # order = precedence, least domain-side first (later wins in the dict)
    ("api_network_error", re.compile(r"^Request failed for (\S+): ")),
    ("empty_groups", re.compile(r"^'groups' key is missing or empty for (\S+)\.")),
    ("site_unreachable", re.compile(r"^Website unreachable: (\S+)\. Skipping")),
]

REASON_LABELS = {
    "empty_groups": "Scan returned nothing (bot wall / JS challenge / non-HTML)",
    "api_network_error": "Scraper-to-API network failure (not a domain property)",
    "site_unreachable": "Site unreachable at scan time",
    "not_in_error_log": "No error recorded (failure reason unknown)",
}


def parse_log():
    reasons = {}
    n_lines = n_matched = 0
    with open(config.FP_ERROR_LOG, errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            n_lines += 1
            for reason, pat in PATTERNS:
                m = pat.match(line)
                if m:
                    reasons[m.group(1).rstrip(".")] = reason
                    n_matched += 1
                    break
    print(
        f"log lines: {n_lines:,}  matched: {n_matched:,}  "
        f"unmatched: {n_lines - n_matched:,}"
    )
    return reasons


def main():
    os.makedirs(config.AUDIT_DATA_DIR, exist_ok=True)

    reasons = parse_log()

    yg = pd.read_csv(config.FP_YG_IND_DOMAIN)
    dom = (
        yg.groupby("private_domain")
        .agg(reach=("caseid", "nunique"), visits=("visits", "sum"))
        .reset_index()
    )
    scanned_files = {
        f for f in os.listdir(config.FP_BL_JSON_DIR) if f.endswith(".json")
    }
    dom["scanned"] = (
        dom["private_domain"].str.replace(".", "_", regex=False) + ".json"
    ).isin(scanned_files)

    unscanned = dom.query("not scanned").copy()
    unscanned["failure_reason"] = (
        unscanned["private_domain"].map(reasons).fillna("not_in_error_log")
    )
    out = unscanned[["private_domain", "failure_reason", "reach", "visits"]]
    out.to_csv(config.FP_FAILURE_REASONS, index=False)
    print(f"Wrote {config.FP_FAILURE_REASONS}  ({len(out):,} unscanned domains)")

    total_visits = dom["visits"].sum()
    comp = (
        out.groupby("failure_reason")
        .agg(n_domains=("private_domain", "size"), visits=("visits", "sum"))
        .reindex(REASON_LABELS.keys())
        .dropna(how="all")
    )
    comp["pct_of_unscanned_domains"] = 100 * comp["n_domains"] / len(out)
    comp["pct_of_unscanned_visits"] = 100 * comp["visits"] / out["visits"].sum()
    comp["pct_of_all_visits"] = 100 * comp["visits"] / total_visits
    comp = comp.reset_index()
    comp["failure_reason"] = comp["failure_reason"].map(REASON_LABELS)
    print(comp.round(1).to_string(index=False))

    tex = comp.copy()
    tex["n_domains"] = tex["n_domains"].map("{:,.0f}".format)
    tex["visits"] = tex["visits"].map("{:,.0f}".format)
    for c in tex.columns[3:]:
        tex[c] = tex[c].map("{:.1f}".format)
    pandas_to_tex(tex, os.path.join(config.TABLES_DIR, "scan_failure_reasons"))
    print("wrote tables/scan_failure_reasons.tex")


if __name__ == "__main__":
    main()
