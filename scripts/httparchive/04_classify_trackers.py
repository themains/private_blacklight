"""Step 04 (free): classify HTTP Archive request maps into tracking measures.

Two parts:
  A. Build a compact domain -> categories table from DuckDuckGo Tracker Radar
     (the list Blacklight uses). Streamed from a pinned commit; cached to
     data/tracker_lists/ddg_categories.csv.
  B. Turn the cached request/cookie extracts (from 03) into a tidy per-(crawl,
     client, domain) table with Blacklight-shaped measures:
       ddg_join_ads        distinct third-party advertising domains
       ddg_known_trackers  distinct third-party domains profiled in Tracker Radar
       third_party_cookies distinct third-party domains that set a cookie
       fb_pixel            1 if a Facebook pixel/SDK request is present
       google_analytics    1 if a Google Analytics/Tag Manager request present
       n_third_parties     distinct third-party domains (generic exposure)
     Canvas fingerprinting / session recording / key logging are behavioral and
     cannot be recovered from a request map, so they are intentionally absent.

Writes: data/tracker_lists/ddg_categories.csv
        data/httparchive/ha_domain_measures.csv
"""

import glob
import io
import json
import os
import tarfile

import config
import pandas as pd
import requests


# --------------------------------------------------------------------------- #
# Part A: DuckDuckGo Tracker Radar categories
# --------------------------------------------------------------------------- #
def build_ddg_categories():
    """Return {domain: set(categories)}, building/caching the CSV on first run."""
    if os.path.exists(config.FP_DDG_CATEGORIES):
        df = pd.read_csv(config.FP_DDG_CATEGORIES)
        return {
            row.domain: (
                set(str(row.categories).split(";"))
                if pd.notna(row.categories)
                else set()
            )
            for row in df.itertuples()
        }

    os.makedirs(config.TRACKER_LIST_DIR, exist_ok=True)
    url = config.DDG_TARBALL_URL.format(ref=config.DDG_TRACKER_RADAR_REF)
    print(f"Downloading Tracker Radar @ {config.DDG_TRACKER_RADAR_REF} ...")
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()

    cats, owners = {}, {}
    with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz") as tar:
        for member in tar:
            # domains/<region>/<domain>.json
            parts = member.name.split("/")
            if (
                len(parts) < 4
                or parts[1] != "domains"
                or not member.name.endswith(".json")
            ):
                continue
            fobj = tar.extractfile(member)
            if fobj is None:
                continue
            rec = json.load(fobj)
            dom = rec.get("domain")
            if not dom:
                continue
            cats.setdefault(dom, set()).update(rec.get("categories") or [])
            owner = (rec.get("owner") or {}).get("name")
            if owner:
                owners[dom] = owner

    rows = [
        {
            "domain": dom,
            "categories": ";".join(sorted(c)),
            "owner": owners.get(dom, ""),
            "is_ad": bool(c & config.AD_CATEGORIES),
        }
        for dom, c in sorted(cats.items())
    ]
    pd.DataFrame(rows).to_csv(config.FP_DDG_CATEGORIES, index=False)
    n_ad = sum(r["is_ad"] for r in rows)
    print(f"Wrote {config.FP_DDG_CATEGORIES}")
    print(f"  {len(rows):,} domains ({n_ad:,} advertising-categorized)")
    return cats


# --------------------------------------------------------------------------- #
# Part B: classify the extracts
# --------------------------------------------------------------------------- #
def _load_extracts(path_fn):
    """Concatenate every cached crawl/client parquet, tagged with crawl+client."""
    frames = []
    for crawl_key in config.CRAWL_DATES:
        for client in config.CLIENTS:
            path = path_fn(crawl_key, client)
            if os.path.exists(path):
                df = pd.read_parquet(path)
                df["crawl"] = crawl_key
                df["client"] = client
                frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def classify(cats):
    # Narrow: domains DDG explicitly categorizes as advertising (mirrors
    # ddg_join_ads). Broad: any domain profiled in Tracker Radar at all (a
    # known tracker) -- Tracker Radar leaves most domains uncategorized, so the
    # broad measure is closer to Blacklight's overall tracker detection. 05
    # checks which aligns with Blacklight.
    ad_domains = {d for d, c in cats.items() if c & config.AD_CATEGORIES}
    known_domains = set(cats)

    reqs = _load_extracts(config.raw_requests_path)
    if reqs.empty:
        raise SystemExit(
            "No request extracts found. Run 03_ha_extract.py --confirm first."
        )

    reqs = reqs[reqs["req_domain"].notna()].copy()
    tp = reqs[reqs["req_domain"] != reqs["page_domain"]].copy()
    tp["is_ad"] = tp["req_domain"].isin(ad_domains)
    tp["is_known"] = tp["req_domain"].isin(known_domains)
    tp["is_fb"] = tp["req_domain"].isin(config.FB_PIXEL_HOSTS)
    tp["is_ga"] = tp["req_domain"].isin(config.GA_HOSTS)

    grp = ["crawl", "client", "page_domain"]

    def _n_unique_where(sub, flag):
        """Distinct third-party domains in a group whose flag is True."""
        return sub.loc[sub[flag], "req_domain"].nunique()

    measures = tp.groupby(grp).apply(
        lambda g: pd.Series(
            {
                "ddg_join_ads": _n_unique_where(g, "is_ad"),
                "ddg_known_trackers": _n_unique_where(g, "is_known"),
                "n_third_parties": g["req_domain"].nunique(),
                "fb_pixel": int(g["is_fb"].any()),
                "google_analytics": int(g["is_ga"].any()),
            }
        ),
        include_groups=False,
    )
    # n_requests over ALL requests (first- and third-party) for context.
    measures["n_requests"] = reqs.groupby(grp)["n_requests"].sum()
    measures = measures.reset_index()

    # Third-party cookies from the (already third-party) cookie extracts.
    cookies = _load_extracts(config.raw_cookies_path)
    if not cookies.empty:
        setters = cookies[cookies["n_set_cookie_responses"] > 0]
        tpc = (
            setters.groupby(grp)["req_domain"]
            .nunique()
            .reset_index(name="third_party_cookies")
        )
        measures = measures.merge(tpc, on=grp, how="left")
    else:
        measures["third_party_cookies"] = pd.NA
    measures["third_party_cookies"] = (
        measures["third_party_cookies"].fillna(0).astype(int)
    )

    out = measures.rename(columns={"page_domain": "private_domain"})[
        [
            "crawl",
            "client",
            "private_domain",
            "ddg_join_ads",
            "ddg_known_trackers",
            "third_party_cookies",
            "fb_pixel",
            "google_analytics",
            "n_third_parties",
            "n_requests",
        ]
    ]
    out.to_csv(config.FP_HA_DOMAIN_MEASURES, index=False)
    print(f"Wrote {config.FP_HA_DOMAIN_MEASURES}  ({len(out):,} rows)")
    for (crawl, client), n in out.groupby(["crawl", "client"]).size().items():
        print(f"  {crawl:16} {client:7} {n:>7,} domains")


def main():
    cats = build_ddg_categories()
    if glob.glob(os.path.join(config.HA_DATA_DIR, "ha_requests_*.parquet")):
        classify(cats)
    else:
        print(
            "\nCategories cached. Run 03_ha_extract.py --confirm, "
            "then re-run this to classify."
        )


if __name__ == "__main__":
    main()
