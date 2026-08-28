"""Step 04: assemble the coding evidence sheet and validate the codes.

Two roles, per CODING_RUBRIC.md:

  evidence : merge audit_sample.csv + probe_results.csv and extract each
             domain's June-2022 Wayback snapshot <title> from the gzipped
             HTML cache -> data/selection_audit/audit_evidence.csv. Fully
             deterministic; safe to re-run.
  codes    : if data/selection_audit/codes_claude.csv exists (one row per
             sampled domain: private_domain, category, rationale), validate
             it -- full coverage, categories from config.CATEGORIES, no
             empty rationale -- mark the seeded spot-check subset for user
             adjudication, and write audit_sample_coded.csv. If the user has
             filled `user_category` on spot-check rows (in the codes file or
             a later edit of audit_sample_coded.csv), raw agreement is
             reported.

Run after step 03's probe pass; bl_* scan columns are merged in when
present but are not needed for coding.
"""

import gzip
import os

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup

import config


def wb_title(domain):
    path = config.wb_html_path(domain)
    if not os.path.exists(path):
        return None
    try:
        with gzip.open(path, "rb") as f:
            head = f.read(300_000)
    except OSError:
        return None
    tag = BeautifulSoup(head, "html.parser").find("title")
    if tag is None:
        return None
    return " ".join(tag.get_text().split())[:200] or None


def build_evidence():
    sample = pd.read_csv(config.FP_AUDIT_SAMPLE)
    probe = pd.read_csv(config.FP_PROBE_RESULTS)
    ev = sample.merge(probe, on="private_domain", how="left", validate="1:1")
    ev["wb_title"] = ev["private_domain"].map(wb_title)
    ev.to_csv(config.FP_AUDIT_EVIDENCE, index=False)
    n_wb = ev["wb_title"].notna().sum()
    print(f"Wrote {config.FP_AUDIT_EVIDENCE} ({len(ev)} rows, {n_wb} WB titles)")
    return ev


def validate_codes(ev):
    codes = pd.read_csv(config.FP_CODES_CLAUDE)

    missing = set(ev["private_domain"]) - set(codes["private_domain"])
    extra = set(codes["private_domain"]) - set(ev["private_domain"])
    assert not missing, f"{len(missing)} sampled domains uncoded: {sorted(missing)[:5]}"
    assert not extra, f"{len(extra)} coded domains not in sample: {sorted(extra)[:5]}"
    assert not codes["private_domain"].duplicated().any(), "duplicate codes"

    bad_cat = codes[~codes["category"].isin(config.CATEGORIES)]
    assert bad_cat.empty, f"invalid categories: {bad_cat['category'].unique()}"
    blank = codes["rationale"].fillna("").str.strip() == ""
    assert not blank.any(), f"empty rationale for {codes.loc[blank, 'private_domain']}"

    coded = ev.merge(codes, on="private_domain", how="left", validate="1:1")

    rng = np.random.default_rng(config.SPOTCHECK_SEED)
    picks = rng.choice(
        coded["private_domain"].sort_values().values,
        size=config.SPOTCHECK_N,
        replace=False,
    )
    coded["spotcheck"] = coded["private_domain"].isin(picks)
    if "user_category" not in coded.columns:
        coded["user_category"] = pd.NA

    coded.to_csv(config.FP_AUDIT_CODED, index=False)
    print(f"Wrote {config.FP_AUDIT_CODED}")
    print("\nCategory composition (n domains):")
    print(coded["category"].value_counts().to_string())

    check = coded[coded["spotcheck"]]
    done = check["user_category"].notna()
    if done.any():
        agree = (check.loc[done, "user_category"] == check.loc[done, "category"]).mean()
        print(
            f"\nSpot-check: {done.sum()}/{len(check)} adjudicated, "
            f"raw agreement {agree:.0%}"
        )
    else:
        print(
            f"\nSpot-check subset marked ({len(check)} domains); "
            "fill `user_category` in audit_sample_coded.csv to score agreement."
        )


def main():
    ev = build_evidence()
    if os.path.exists(config.FP_CODES_CLAUDE):
        validate_codes(ev)
    else:
        print(f"\nNo {config.FP_CODES_CLAUDE} yet -- code the evidence sheet next.")


if __name__ == "__main__":
    main()
