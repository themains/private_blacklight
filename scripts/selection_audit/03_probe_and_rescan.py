"""Step 03: probe current status and run fresh Blacklight scans on the sample.

Two idempotent passes over the sampled unscanned domains, then a parse:

  probe : DNS resolve + GET (https, falling back to http; 10s) -> current
          status in {live, redirect, http_error, dead}, final URL, HTTP
          status, page <title>. "redirect" means the browser lands on a
          *different* registered domain (where-to recorded); an on-domain
          3xx that resolves is "live". Results cached per domain in
          data/selection_audit/probe_results.csv; only missing domains
          are probed on re-run.
  scan  : fresh Blacklight scan via the public API (same pattern as
          scripts/rescan/rescan_2026.py): POST {"inUrl": https://<domain>},
          retries cover transient errors and empty "groups". Resume-by-file
          in data/blacklight_json_audit/; failures logged with their last
          error to _errors.log.
  parse : per-cardType measures from each scan JSON (bigNumber where the
          card reports a count, testEventsFound as 0/1 otherwise -- the
          same semantics as data/blacklight_domain.csv), merged into
          probe_results.csv as bl_* columns plus bl_scan_success.

The scan pass takes ~1.5-2h for 200 domains; run the script detached:

  nohup ../../bl_venv/bin/python 03_probe_and_rescan.py > 03_run.log 2>&1 &
"""

import argparse
import json
import os
import socket
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
import tldextract
from bs4 import BeautifulSoup

import config

_extract = tldextract.TLDExtract(suffix_list_urls=())  # offline PSL snapshot

# A real-browser UA: default python-requests UAs are widely blocked, which
# would misclassify bot-walled sites as dead.
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
PROBE_WORKERS = 8

# The probe runs from the analyst's network, which sits behind a Meraki
# content filter: blocked categories land on wired.meraki.com. That says
# nothing about the domain beyond "filter-listed" -- flag it separately.
NETWORK_FILTER_DOMAINS = {"meraki.com"}

# cardType in the API response -> column name used in blacklight_domain.csv
CARD_COLUMNS = {
    "ddg_join_ads": "ddg_join_ads",
    "cookies": "third_party_cookies",
    "canvas_fingerprinters": "canvas_fingerprinting",
    "session_recorders": "session_recording",
    "key_logging": "key_logging",
    "fb_pixel_events": "fb_pixel",
    "ga": "google_analytics",
}


def reg_domain(url):
    ext = _extract(url)
    return ext.top_domain_under_public_suffix.lower()


# --------------------------------------------------------------------------- #
# Pass 1: live probe
# --------------------------------------------------------------------------- #
def probe_domain(domain):
    row = {
        "private_domain": domain,
        "dns_resolves": False,
        "probe_status": "dead",
        "http_status": None,
        "final_url": None,
        "page_title": None,
        "probe_error": None,
    }
    try:
        socket.getaddrinfo(domain, None)
        row["dns_resolves"] = True
    except OSError as e:
        row["probe_error"] = f"dns: {e}"
        return row

    resp = None
    for scheme in ("https", "http"):
        try:
            resp = requests.get(
                f"{scheme}://{domain}",
                timeout=config.PROBE_TIMEOUT,
                headers={"User-Agent": UA},
                allow_redirects=True,
                stream=True,
            )
            break
        except requests.RequestException as e:
            row["probe_error"] = f"{scheme}: {type(e).__name__}"

    if resp is None:
        return row

    row["http_status"] = resp.status_code
    row["final_url"] = resp.url
    try:
        head = next(resp.iter_content(chunk_size=200_000), b"")
        title = BeautifulSoup(head, "html.parser").find("title")
        if title:
            row["page_title"] = " ".join(title.get_text().split())[:200]
    except requests.RequestException:
        pass
    finally:
        resp.close()

    if reg_domain(resp.url) in NETWORK_FILTER_DOMAINS:
        row["probe_status"] = "network_filtered"
    elif reg_domain(resp.url) != domain:
        row["probe_status"] = "redirect"
    elif resp.status_code < 400:
        row["probe_status"] = "live"
    else:
        row["probe_status"] = "http_error"
    return row


def run_probe(domains):
    done = pd.DataFrame()
    if os.path.exists(config.FP_PROBE_RESULTS):
        done = pd.read_csv(config.FP_PROBE_RESULTS)
        done = done[done["private_domain"].isin(domains)]
    todo = sorted(set(domains) - set(done.get("private_domain", [])))
    print(f"probe: {len(done)} cached, {len(todo)} to fetch")
    if todo:
        with ThreadPoolExecutor(PROBE_WORKERS) as ex:
            rows = list(ex.map(probe_domain, todo))
        done = pd.concat([done, pd.DataFrame(rows)], ignore_index=True)
    filtered = (
        done["final_url"]
        .fillna("")
        .map(lambda u: bool(u) and reg_domain(u) in NETWORK_FILTER_DOMAINS)
    )
    done.loc[filtered, "probe_status"] = "network_filtered"
    done.to_csv(config.FP_PROBE_RESULTS, index=False)
    print(done["probe_status"].value_counts().to_string())
    return done


# --------------------------------------------------------------------------- #
# Pass 2: fresh Blacklight scans (rescan_2026.py pattern, threaded)
# --------------------------------------------------------------------------- #
def scan_domain(domain):
    out_path = config.scan_json_path(domain)
    if os.path.exists(out_path):
        return "cached"

    last_err = None
    for _ in range(config.SCAN_MAX_RETRIES):
        try:
            r = requests.post(
                config.BLACKLIGHT_ENDPOINT,
                json={"inUrl": f"https://{domain}"},
                timeout=config.SCAN_TIMEOUT,
            )
            r.raise_for_status()
            payload = r.json()
        except (requests.RequestException, ValueError) as e:
            last_err = f"request_exception: {e}"
            time.sleep(5)
            continue

        if payload.get("groups"):
            payload["domain_name"] = domain
            with open(out_path, "w") as f:
                json.dump(payload, f, indent=2)
            time.sleep(config.SCAN_PAUSE)
            return "ok"
        last_err = "empty_groups"
        time.sleep(5)

    with open(config.FP_SCAN_ERRORS, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {domain}\t{last_err}\n")
    return "failed"


def run_scans(domains):
    os.makedirs(config.SCAN_JSON_DIR, exist_ok=True)
    t0 = time.time()
    results = {"ok": 0, "cached": 0, "failed": 0}
    with ThreadPoolExecutor(config.SCAN_WORKERS) as ex:
        for i, status in enumerate(ex.map(scan_domain, sorted(domains)), 1):
            results[status] += 1
            print(
                f"[{i:>3}/{len(domains)}] {status:6}  "
                f"({time.time() - t0:6.0f}s elapsed)",
                flush=True,
            )
    print(f"scan: {results}")


# --------------------------------------------------------------------------- #
# Pass 3: parse scan JSONs into bl_* columns on probe_results.csv
# --------------------------------------------------------------------------- #
def parse_scan(domain):
    path = config.scan_json_path(domain)
    row = {"private_domain": domain, "bl_scan_success": os.path.exists(path)}
    if not row["bl_scan_success"]:
        return row
    with open(path) as f:
        data = json.load(f)
    row["bl_final_url"] = data.get("uri_dest")
    cards = {
        c["cardType"]: c for g in data.get("groups", []) for c in g.get("cards", [])
    }
    for card_type, col in CARD_COLUMNS.items():
        c = cards.get(card_type, {})
        big = c.get("bigNumber")
        row[f"bl_{col}"] = (
            big if big is not None else int(bool(c.get("testEventsFound")))
        )
    return row


def run_parse(domains):
    parsed = pd.DataFrame([parse_scan(d) for d in sorted(domains)])
    probe = pd.read_csv(config.FP_PROBE_RESULTS)
    probe = probe.drop(columns=[c for c in probe.columns if c.startswith("bl_")])
    merged = probe.merge(parsed, on="private_domain", how="left")
    merged.to_csv(config.FP_PROBE_RESULTS, index=False)
    n_ok = int(merged["bl_scan_success"].sum())
    print(f"parse: {n_ok}/{len(domains)} domains scanned successfully")
    print(f"Wrote {config.FP_PROBE_RESULTS}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--pass",
        dest="passes",
        choices=["probe", "scan", "parse"],
        action="append",
        help="run only these passes (default: all three, in order)",
    )
    args = ap.parse_args()
    passes = args.passes or ["probe", "scan", "parse"]

    domains = pd.read_csv(config.FP_AUDIT_SAMPLE)["private_domain"].tolist()
    print(f"{len(domains)} sampled domains")
    if "probe" in passes:
        run_probe(domains)
    if "scan" in passes:
        run_scans(domains)
    if "parse" in passes:
        run_parse(domains)


if __name__ == "__main__":
    main()
