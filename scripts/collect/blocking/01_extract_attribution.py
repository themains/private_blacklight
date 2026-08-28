"""Extract which third-party domains are responsible for each detected behavior.

`scripts/01_combine_blacklight.ipynb` walks the same Blacklight JSON but keeps
only each card's headline number. Every card also carries
`domainData.scripts` -- the third-party domains that produced the behavior --
which is what makes residual-after-blocking computable instead of hypothetical.

Emits one row per (domain, card, responsible script domain).

Gate: recomputing the published per-domain measures from this table must
reproduce data/blacklight_domain.csv exactly for the ad-tracker count. Anything
less means the attribution is not faithful and the residual measures downstream
are not either.
"""

import json
import os
import sys

import pandas as pd

import config


def walk_cards(payload):
    """Yield (card_type, big_number, test_events_found, scripts, owners)."""
    groups = payload.get("groups") or []
    if not groups:
        return
    for card in groups[0].get("cards") or []:
        card_type = card.get("cardType")
        if not card_type:
            continue
        domain_data = card.get("domainData") or {}
        yield (
            card_type,
            card.get("bigNumber"),
            bool(card.get("testEventsFound", False)),
            domain_data.get("scripts") or [],
            domain_data.get("owners") or [],
        )


def extract(json_dir):
    rows = []
    card_summary = []
    files = sorted(f for f in os.listdir(json_dir) if f.endswith(".json"))
    print(f"Reading {len(files):,} scan results from {json_dir}")

    for i, fname in enumerate(files, 1):
        if i % 5000 == 0:
            print(f"  {i:,}/{len(files):,}")
        stem = fname[: -len(".json")]
        try:
            with open(os.path.join(json_dir, fname)) as f:
                payload = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  skipped {fname}: {e}")
            continue

        private_domain = stem.replace("_", ".")

        for card_type, big_number, found, scripts, owners in walk_cards(payload):
            owner = owners[0] if len(owners) == 1 else ""
            card_summary.append(
                {
                    "filename": stem,
                    "card_type": card_type,
                    "big_number": big_number,
                    "test_events_found": found,
                    "n_scripts": len(scripts),
                }
            )
            if not found:
                continue

            assumed = False
            if not scripts and card_type in config.ASSUMED_ATTRIBUTION:
                scripts = config.ASSUMED_ATTRIBUTION[card_type]
                assumed = True

            for script_domain in scripts:
                rows.append(
                    {
                        "filename": stem,
                        "private_domain": private_domain,
                        "card_type": card_type,
                        "script_domain": script_domain,
                        "owner": owner,
                        "assumed_attribution": assumed,
                    }
                )

    return pd.DataFrame(rows), pd.DataFrame(card_summary)


def gate(df_scripts, df_cards, fp_published):
    """Recompute the published measures from the attribution and compare."""
    published = pd.read_csv(fp_published)

    # The published table was built when every scan result was on disk. If a
    # JSON has since gone missing, say which one rather than reporting it as an
    # attribution failure -- data/blacklight_json.tar.gz holds the originals.
    on_disk = set(df_cards["filename"])
    missing = sorted(set(published["filename"]) - on_disk)
    if missing:
        raise AssertionError(
            f"{len(missing):,} domains in {os.path.basename(fp_published)} have no "
            f"scan JSON on disk (e.g. {missing[:5]}). Restore them with:\n"
            f"  cd data && tar -xzf blacklight_json.tar.gz "
            f"blacklight_json/{missing[0]}.json"
        )

    # Ad trackers: the card's headline number is exactly the number of
    # responsible third-party domains, so attribution must reproduce it.
    recomputed = (
        df_scripts.query("card_type == 'ddg_join_ads'")
        .groupby("filename")
        .size()
        .rename("ddg_join_ads_recomputed")
    )
    check = (
        published[["filename", "ddg_join_ads"]]
        .merge(recomputed, on="filename", how="left")
        .fillna({"ddg_join_ads_recomputed": 0})
    )
    mismatch = check.query("ddg_join_ads != ddg_join_ads_recomputed")
    print(f"\nGate 1 -- ad-tracker attribution vs published ({len(check):,} domains)")
    if len(mismatch):
        print(mismatch.head(20).to_string(index=False))
        raise AssertionError(
            f"{len(mismatch):,} domains where attributed script count != published "
            "ddg_join_ads. Attribution is not faithful; do not proceed."
        )
    print("  exact match on all domains")

    # Cookies: several cookies can come from one domain, so the headline count
    # is an upper bound on the number of responsible domains. Residual cookie
    # exposure is therefore reported at the domain level, not the cookie level.
    cookies = df_cards.query("card_type == 'cookies' and test_events_found")
    bad = cookies.query("big_number < n_scripts")
    print(f"\nGate 2 -- cookie count >= responsible domains ({len(cookies):,} domains)")
    if len(bad):
        print(bad.head(20).to_string(index=False))
        raise AssertionError(
            f"{len(bad):,} domains with more cookie domains than cookies."
        )
    print("  holds on all domains")

    # Behavioral measures: presence must line up with the published flags.
    for card_type, (measure, _) in config.CARD_MEASURES.items():
        if measure not in published.columns or card_type == "ddg_join_ads":
            continue
        flagged = set(
            df_cards.query("card_type == @card_type and test_events_found")["filename"]
        )
        pub = set(published.loc[published[measure] > 0, "filename"])
        if card_type == "cookies":
            continue
        if flagged != pub:
            raise AssertionError(
                f"{measure}: {len(flagged ^ pub):,} domains disagree between "
                "re-walked cards and published flags."
            )
    print("\nGate 3 -- behavioral flags reproduce published columns: match")


def main():
    os.makedirs(config.BLOCKING_DATA_DIR, exist_ok=True)

    df_scripts, df_cards = extract(config.FP_BL_JSON_DIR)
    print(f"\nAttribution rows: {len(df_scripts):,}")
    print(
        f"Domains with at least one attributed behavior: "
        f"{df_scripts.filename.nunique():,}"
    )
    print(f"Distinct third-party domains: {df_scripts.script_domain.nunique():,}")

    gate(df_scripts, df_cards, config.FP_BLACKLIGHT)

    df_scripts.to_csv(config.FP_SCRIPTS, index=False)
    print(f"\nWrote {config.FP_SCRIPTS}")

    print("\nAttributed rows by card type:")
    summary = (
        df_scripts.groupby(["card_type", "assumed_attribution"])
        .agg(rows=("script_domain", "size"), domains=("filename", "nunique"))
        .reset_index()
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
