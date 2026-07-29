"""Is the change in the age gap about *which* trackers blocklists catch?

Tier C removes about 70% of tracker pairs and the age gap in ad-tracker exposure
narrows sharply. That could mean blocklists happen to target the trackers older
panelists disproportionately meet. It could equally mean that removing 70% of
anything would have done it -- that the narrowing is arithmetic, a property of
taking a big bite out of a skewed distribution, and has nothing to do with what
EasyList is aimed at.

The two are distinguishable. Build random blocklists that remove the *same
amount* of exposure as the real one but are chosen without regard to what the
real lists target, recompute the gap shift under each, and see where the real
list falls in that distribution. If it sits comfortably inside, the honest
report is that the narrowing is mechanical. Randomization inference: the
two-sided p-value is the share of placebo draws whose shift is at least as
extreme as the observed one.

Exposure is recomputed from scratch for every draw, through the same arithmetic
as 04: a domain's residual count is how many of its responsible third parties
survive, a behavioral residual is whether any survives, and a person's exposure
is their visit-weighted sum over domains. Sparse incidence matrices make a draw
a pair of matrix products rather than a rebuild.
"""

import os
import sys

import numpy as np
import pandas as pd
from scipy import sparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common as blk  # noqa: E402
import config  # noqa: E402

N_PLACEBO = 200
PLACEBO_SEED = 20250110
TIER = "C"


def build_matrices(df_scripts, visits, user_ids):
    """Sparse person-by-domain visits and per-measure domain-by-script incidence."""
    domains = pd.Index(
        sorted(df_scripts["private_domain"].unique()), name="private_domain"
    )
    scripts = pd.Index(sorted(df_scripts["script_domain"].unique()), name="script_domain")
    people = pd.Index(user_ids, name="caseid")

    v = visits[visits["private_domain"].isin(domains)]
    visit_mat = sparse.csr_matrix(
        (
            v["visits"].to_numpy(float),
            (people.get_indexer(v["caseid"]), domains.get_indexer(v["private_domain"])),
        ),
        shape=(len(people), len(domains)),
    )

    incidence = {}
    for card, (measure, kind) in config.CARD_MEASURES.items():
        sub = df_scripts[df_scripts["card_type"] == card]
        if sub.empty:
            continue
        incidence[measure] = (
            sparse.csr_matrix(
                (
                    np.ones(len(sub)),
                    (
                        domains.get_indexer(sub["private_domain"]),
                        scripts.get_indexer(sub["script_domain"]),
                    ),
                ),
                shape=(len(domains), len(scripts)),
            ),
            kind,
        )
    return visit_mat, incidence, scripts


def exposure(visit_mat, incidence_kind, survives):
    """Per-person exposure when `survives` marks the unblocked third parties."""
    incidence, kind = incidence_kind
    per_domain = incidence @ survives.astype(float)
    if kind == "any":
        per_domain = (per_domain > 0).astype(float)
    return np.asarray(visit_mat @ per_domain).ravel()


def log_ratio_from(values, is_old, is_young):
    a, b = values[is_old].mean(), values[is_young].mean()
    return np.log(a / b) if a > 0 and b > 0 else np.nan


def main():
    df_scripts = pd.read_csv(config.FP_SCRIPTS)
    pairs = pd.read_csv(config.FP_BLOCKED_PAIRS)
    visits = pd.read_csv(config.FP_YG_IND_DOMAIN)
    user = blk.load_user()

    visit_mat, incidence, scripts = build_matrices(df_scripts, visits, user["caseid"])
    # Denominator is the panelist's total visits, exactly as bl_*_rate is
    # defined, so `pre` below reproduces the log-ratio reported by 05. A few
    # panelists visited no attributed domain at all; guard the division rather
    # than letting them turn every mean into a NaN.
    totals = user["tt_visits"].to_numpy(float)
    totals = np.where(totals > 0, totals, np.nan)
    is_old = (user["agegroup_lab"] == blk.OLD).to_numpy()
    is_young = (user["agegroup_lab"] == blk.YOUNG).to_numpy()

    # Both arms block at the level of a third-party host: the real list blocks a
    # host if the tier blocks it on any site, and a placebo blocks a random set
    # of hosts. Holding the unit the same is what makes the comparison fair.
    # It does mean the observed shift here differs slightly from 05, which
    # scores each (site, host) pair separately -- a host can be blocked on one
    # site and not another once $third-party and domain= options are applied.
    blocked_real = (
        pairs.groupby("script_domain")[f"blocked_{TIER}"]
        .max()
        .reindex(scripts, fill_value=False)
    ).to_numpy(bool)
    print(
        f"Third parties: {len(scripts):,}; blocked by tier {TIER}: {blocked_real.sum():,}"
    )
    print(f"Placebo draws: {N_PLACEBO}, seed {PLACEBO_SEED}\n")

    rng = np.random.default_rng(PLACEBO_SEED)
    results = []

    for measure in blk.HEADLINE_MEASURES:
        if measure not in incidence:
            continue
        all_live = np.ones(len(scripts), bool)
        base = np.nan_to_num(exposure(visit_mat, incidence[measure], all_live) / totals)
        real = np.nan_to_num(
            exposure(visit_mat, incidence[measure], ~blocked_real) / totals
        )

        pre = log_ratio_from(base, is_old, is_young)
        observed = log_ratio_from(real, is_old, is_young) - pre
        target_removed = 1 - real.mean() / base.mean()

        def removed_by(order, cut):
            """Exposure removed when the first `cut` third parties are blocked."""
            survives = np.ones(len(scripts), bool)
            survives[order[:cut]] = False
            got = np.nan_to_num(
                exposure(visit_mat, incidence[measure], survives) / totals
            )
            return 1 - got.mean() / base.mean(), got

        shifts, removed = [], []
        for _ in range(N_PLACEBO):
            order = rng.permutation(len(scripts))
            # Exposure removed is monotone in how many third parties are
            # blocked, so bisect for the cut that matches the real list rather
            # than walking the permutation.
            lo, hi = 0, len(scripts)
            while lo < hi:
                mid = (lo + hi) // 2
                got, _ = removed_by(order, mid)
                if got < target_removed:
                    lo = mid + 1
                else:
                    hi = mid
            # Bisect lands on the first cut clearing the target, which can
            # overshoot and inflate the placebo spread. Take whichever of the
            # two neighbouring cuts removes an amount closer to the target.
            cand = [lo] + ([lo - 1] if lo > 0 else [])
            best = min(cand, key=lambda c: abs(removed_by(order, c)[0] - target_removed))
            got, placebo = removed_by(order, best)
            shifts.append(log_ratio_from(placebo, is_old, is_young) - pre)
            removed.append(got)

        shifts = np.array([s for s in shifts if np.isfinite(s)])
        centre = np.median(shifts)
        # (k + 1) / (B + 1), not k / B. The observed assignment is itself one
        # draw from the randomization distribution, so excluding it lets a
        # p-value of exactly zero be reported from a finite number of draws and
        # makes the test anti-conservative by 1/(B+1). With B = 200 the smallest
        # attainable p is 1/201 = .005, so no claim below that is supportable.
        extreme = int(np.sum(np.abs(shifts - centre) >= abs(observed - centre)))
        p_value = (1 + extreme) / (1 + len(shifts))

        results.append(
            {
                "measure": blk.MEASURE_LABELS[measure],
                "measure_key": measure,
                "observed_shift": observed,
                "exposure_removed": target_removed,
                "placebo_removed_mean": float(np.mean(removed)),
                "placebo_median": centre,
                "placebo_lo": float(np.percentile(shifts, 2.5)),
                "placebo_hi": float(np.percentile(shifts, 97.5)),
                "p_value": p_value,
                "n_draws": len(shifts),
            }
        )
        r = results[-1]
        print(
            f"  {r['measure']:24s} removed {r['exposure_removed']:5.1%} "
            f"(placebo {r['placebo_removed_mean']:5.1%})  observed {observed:+.3f}  "
            f"placebo {centre:+.3f} [{r['placebo_lo']:+.3f}, {r['placebo_hi']:+.3f}]  "
            f"p={p_value:.3f}"
        )
        np.save(
            os.path.join(config.BLOCKING_DATA_DIR, f"placebo_draws_{measure}.npy"), shifts
        )

    out = pd.DataFrame(results)
    out.to_csv(os.path.join(config.BLOCKING_DATA_DIR, "placebo.csv"), index=False)

    print("\nReading: a small p-value means the real blocklist moves the age gap")
    print("differently from a random removal of the same size -- the change")
    print("reflects what the lists target. A large one means it does not.")
    slack = out["placebo_removed_mean"] - out["exposure_removed"]
    if (slack > 0.02).any():
        loose = out.loc[slack > 0.02, "measure"].tolist()
        print(f"\nPlacebo removes more than the real list for: {', '.join(loose)}.")
        print("Few third parties carry these behaviors, so blocking one more")
        print("jumps past the target. Over-removal widens the placebo spread,")
        print("which makes the test harder to reject, not easier.")

    tex = pd.DataFrame(
        {
            "Measure": out["measure"],
            # LaTeX: a bare % starts a comment and would swallow the rest of the row.
            "Exposure removed": out["exposure_removed"].map(
                lambda x: f"{x:,.1%}".replace("%", r"\%")
            ),
            "Observed shift": out["observed_shift"].map(lambda x: f"{x:+,.3f}"),
            "Placebo": out.apply(
                lambda r: f"{r['placebo_median']:+,.3f} [{r['placebo_lo']:+,.3f}, "
                f"{r['placebo_hi']:+,.3f}]",
                axis=1,
            ),
            "$p$": out["p_value"].map(lambda x: f"{x:,.3f}"),
        }
    )
    blk.pandas_to_tex(tex, blk.table_path("blocking_placebo.tex"))
    print("Wrote tables/blocking_placebo.tex")


if __name__ == "__main__":
    sys.exit(main())
