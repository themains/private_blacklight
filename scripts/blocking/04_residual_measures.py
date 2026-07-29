"""Turn blocked/unblocked pairs into residual exposure, per domain and per person.

A count measure's residual is the number of responsible third-party domains a
tier fails to stop. A behavioural measure's residual is whether *any* responsible
domain survives -- blocking two of three session recorders still leaves the site
recording.

Each measure comes as an interval, following 03: the point estimate blocks only
what a domain-level rule certainly stops, and the `_lo` variant additionally
credits every host the list names with a path rule. Real blocking sits between.

Person-level exposure follows the paper's construction exactly -- each visit
contributes its domain's measured tracking, unscanned domains contribute zero --
and a gate confirms the rebuilt unblocked figures reproduce the published ones
before any residual is computed.
"""

import os
import sys

import pandas as pd

import config


def domain_residual(df_scripts, pairs):
    """Residual per (domain, measure, tier)."""
    df = df_scripts.merge(pairs, on=["private_domain", "script_domain"], how="left")
    if df[[f"blocked_{t}" for t in config.TIER_ORDER]].isna().any().any():
        raise AssertionError("Attribution rows with no blocking verdict; rerun 03.")

    out = df[["filename"]].drop_duplicates().set_index("filename")

    for card, (measure, kind) in config.CARD_MEASURES.items():
        sub = df[df["card_type"] == card]
        for tier in config.TIER_ORDER:
            for suffix, col in [("", f"blocked_{tier}"), ("_lo", f"rule_present_{tier}")]:
                survives = ~sub[col].astype(bool)
                grp = sub.assign(_s=survives).groupby("filename")["_s"]
                value = grp.sum() if kind == "count" else (grp.max() > 0).astype(int)
                out[f"{measure}_resid_{tier}{suffix}"] = value

    return out.fillna(0).reset_index()


def gate_person_level(user, published):
    """The rebuilt unblocked exposure must reproduce the published person file."""
    check = published.merge(user, on="caseid", how="inner", suffixes=("_pub", "_new"))
    print(f"\nGate -- rebuilt vs published person-level ({len(check):,} panelists)")

    problems = []
    for col in ["tt_visits"] + [
        f"bl_{m}" for m in config.MEASURES if m != "third_party_cookies"
    ]:
        pub, new = f"{col}_pub", f"{col}_new"
        if pub not in check.columns or new not in check.columns:
            continue
        diff = (check[pub] - check[new]).abs()
        worst = diff.max()
        status = "match" if worst < 1e-6 else f"MAX DIFF {worst:,.4f}"
        print(f"  {col:32s} {status}")
        if worst >= 1e-6:
            problems.append((col, worst))

    if problems:
        raise AssertionError(
            "Rebuilt person-level exposure does not reproduce the published file: "
            + ", ".join(f"{c} (max diff {d:,.4f})" for c, d in problems)
        )


def main():
    df_scripts = pd.read_csv(config.FP_SCRIPTS)
    pairs = pd.read_csv(config.FP_BLOCKED_PAIRS)
    published_domain = pd.read_csv(config.FP_BLACKLIGHT)

    print("Building domain-level residual measures")
    resid = domain_residual(df_scripts, pairs)
    resid = published_domain.merge(resid, on="filename", how="left").fillna(0)

    # Blocking can only remove exposure. A residual above the published value
    # means the attribution or the join is wrong.
    for measure in config.MEASURES:
        for tier in config.TIER_ORDER:
            for suffix in ("", "_lo"):
                col = f"{measure}_resid_{tier}{suffix}"
                base = resid[measure] if measure != "third_party_cookies" else None
                if base is None:
                    continue
                bad = int((resid[col] > base).sum())
                if bad:
                    raise AssertionError(
                        f"{col} exceeds published {measure} on {bad:,} domains."
                    )
    print("  monotonicity holds: residual <= published on every domain and tier")

    # Cookies are counted per cookie but attributed per domain, so the residual
    # is a count of cookie-setting domains left unblocked. Carry the published
    # cookie count alongside it rather than pretending the two are comparable.
    n_cookie_domains = (
        df_scripts.query("card_type == 'cookies'").groupby("filename").size()
    )
    resid["third_party_cookie_domains"] = (
        resid.filename.map(n_cookie_domains).fillna(0).astype(int)
    )

    os.makedirs(config.BLOCKING_DATA_DIR, exist_ok=True)
    resid.to_csv(config.FP_DOMAIN_RESIDUAL, index=False)
    print(f"Wrote {config.FP_DOMAIN_RESIDUAL}")

    # ---------------------------------------------------------------- person
    print("\nBuilding person-level residual exposure")
    visits = pd.read_csv(config.FP_YG_IND_DOMAIN)
    resid["private_domain"] = resid["filename"].str.replace("_", ".", regex=False)

    value_cols = [c for c in resid.columns if c not in ("filename", "private_domain")]
    merged = visits.merge(
        resid[["private_domain"] + value_cols], on="private_domain", how="left"
    )

    weighted = merged[value_cols].mul(merged["visits"], axis=0)
    weighted["caseid"] = merged["caseid"]
    user = weighted.groupby("caseid", as_index=False).sum()
    user = user.rename(columns={str(c): f"bl_{c}" for c in value_cols})
    user["tt_visits"] = merged.groupby("caseid")["visits"].sum().values
    user["tt_domains"] = merged.groupby("caseid")["private_domain"].nunique().values

    published_user = pd.read_csv(config.FP_COMBINED)
    gate_person_level(user, published_user)

    for col in [c for c in user.columns if c.startswith("bl_")]:
        user[f"{col}_rate"] = user[col] / user["tt_visits"]

    demo = published_user[
        ["caseid", "gender_lab", "race_lab", "educ_lab", "agegroup_lab", "birthyr"]
    ]
    user = user.merge(demo, on="caseid", how="inner")
    user.to_csv(config.FP_USER_RESIDUAL, index=False)
    print(f"\nWrote {config.FP_USER_RESIDUAL} ({len(user):,} panelists)")

    print("\nMean per-user exposure rate (trackers per visit), unblocked vs residual:")
    rows = []
    for measure in config.MEASURES:
        row = {"measure": measure, "unblocked": user[f"bl_{measure}_rate"].mean()}
        for tier in config.TIER_ORDER:
            row[f"tier_{tier}"] = user[f"bl_{measure}_resid_{tier}_rate"].mean()
            row[f"tier_{tier}_lo"] = user[f"bl_{measure}_resid_{tier}_lo_rate"].mean()
        rows.append(row)
    summary = pd.DataFrame(rows)
    summary["pct_left_C"] = 100 * summary["tier_C"] / summary["unblocked"]
    print(summary.to_string(index=False, float_format="%.4f"))


if __name__ == "__main__":
    sys.exit(main())
