"""Step 03 (free): parse cached snapshot HTML into static tracking measures.

For each cached June-2022 snapshot, collect the third-party resource URLs
embedded in the HTML (script/img/iframe/source/embed src, link href), map them
to registered domains, and classify against the pinned DuckDuckGo Tracker
Radar table built by scripts/httparchive/04_classify_trackers.py.

Static-parse limitations, stated up front:
  - Only statically embedded resources are visible; trackers injected by
    JavaScript at runtime are missed, so every measure here UNDERCOUNTS.
    The WB-vs-HA agreement notebook quantifies exactly how much.
  - No cookie measure: static HTML cannot show Set-Cookie behavior.
  - Behavioral measures (canvas fingerprinting, session recording, key
    logging) are unobservable here, as everywhere outside a live scan.

Writes: data/wayback/wb_domain_measures.csv
  (private_domain, snapshot_ts, ddg_join_ads, ddg_known_trackers, fb_pixel,
   google_analytics, n_third_parties, n_static_urls)
"""

import gzip
import os
import re

import config
import pandas as pd
import tldextract
from bs4 import BeautifulSoup

# src/href attributes that trigger resource loads. Anchors (a[href]) are
# navigation, not loads, and are excluded.
TAG_ATTRS = [
    ("script", "src"),
    ("img", "src"),
    ("iframe", "src"),
    ("source", "src"),
    ("embed", "src"),
    ("link", "href"),
]

# Fallback for absolute URLs inside inline scripts (a common way trackers are
# referenced even statically). Conservative: http(s) URLs only.
URL_RE = re.compile(r"https?://[^\s'\"<>\\)]+")

_extract = tldextract.TLDExtract(suffix_list_urls=())  # offline PSL snapshot


def reg_domain(url):
    ext = _extract(url)
    return f"{ext.domain}.{ext.suffix}" if ext.domain and ext.suffix else None


def static_request_domains(html):
    """Registered domains of statically referenced resources."""
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for tag, attr in TAG_ATTRS:
        for el in soup.find_all(tag):
            v = el.get(attr)
            if isinstance(v, str) and v.startswith(("http://", "https://", "//")):
                urls.append("https:" + v if v.startswith("//") else v)
    for script in soup.find_all("script"):
        if script.string:
            urls.extend(URL_RE.findall(script.string))
    return {d for d in (reg_domain(u) for u in urls) if d}


def main():
    cats = pd.read_csv(config.FP_DDG_CATEGORIES)
    cat_map = {
        row.domain: (
            set(str(row.categories).split(";")) if pd.notna(row.categories) else set()
        )
        for row in cats.itertuples()
    }
    ad_domains = {d for d, c in cat_map.items() if c & config.AD_CATEGORIES}
    known_domains = set(cat_map)

    manifest = pd.read_csv(config.FP_WB_MANIFEST)
    ok = manifest.query("status == 'ok'").drop_duplicates("private_domain")

    rows = []
    for i, rec in enumerate(ok.itertuples(), 1):
        path = config.html_path(rec.private_domain)
        if not os.path.exists(path):
            continue
        with gzip.open(path, "rt", errors="ignore") as f:
            html = f.read()
        domains = static_request_domains(html)
        tp = {d for d in domains if d != rec.private_domain}
        rows.append(
            {
                "private_domain": rec.private_domain,
                "snapshot_ts": rec.snapshot_ts,
                "ddg_join_ads": len(tp & ad_domains),
                "ddg_known_trackers": len(tp & known_domains),
                "fb_pixel": int(bool(tp & config.FB_PIXEL_HOSTS)),
                "google_analytics": int(bool(tp & config.GA_HOSTS)),
                "n_third_parties": len(tp),
                "n_static_urls": len(domains),
            }
        )
        if i % 500 == 0:
            print(f"  parsed {i:,}/{len(ok):,}", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(config.FP_WB_DOMAIN_MEASURES, index=False)
    print(f"Wrote {config.FP_WB_DOMAIN_MEASURES}  ({len(out):,} domains)")
    if len(out):
        present = (
            out[
                [
                    "ddg_join_ads",
                    "ddg_known_trackers",
                    "fb_pixel",
                    "google_analytics",
                    "n_third_parties",
                ]
            ]
            > 0
        ).mean()
        print("share of parsed domains with measure present:")
        print((100 * present).round(1).to_string())


if __name__ == "__main__":
    main()
