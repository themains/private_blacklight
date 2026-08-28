"""Step 02: fetch June-2022 Wayback snapshots for the target domains.

Uses the EDGI `wayback` library, whose built-in rate limits and exponential-
backoff retries are calibrated to Internet Archive guidance (search 0.4
calls/s process-wide, mementos 8 calls/s) -- a hand-rolled 6-worker fetcher
got this machine's connections refused for hours, so the library's pacing is
the point, not an implementation detail.

Per domain:
  1. CDX search for 200/text-html captures in the window -> pick the capture
     closest to TARGET_TS. Raw capture lists are cached gzipped in
     data/wayback/cdx/ (a miss is itself data: no evidence the domain was
     live in mid-2022).
  2. Fetch the original archived bytes (Mode.original -- no replay
     rewriting) -> cached gzipped in data/wayback/html/.

Idempotent and resumable: cached CDX lists are not re-searched, cached HTML is
not re-fetched. A manifest row per domain records what happened.

Run `--preflight` first: fetches two known domains and checks the payload is
raw original HTML (no Wayback-injected markup).

Writes: data/wayback/cdx/*.json.gz, data/wayback/html/*.html.gz,
        data/wayback/wb_manifest.csv, data/wayback/_errors.log
"""

import argparse
import gzip
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import config
import pandas as pd
import wayback

# Memento downloads overlap while the library's shared limiter paces CDX
# searches, so a few workers help without exceeding any rate limit.
N_WORKERS = 3

CDX_HEADER = [
    "urlkey",
    "timestamp",
    "original",
    "mimetype",
    "statuscode",
    "digest",
    "length",
]

_local = threading.local()
_log_lock = threading.Lock()


def client():
    # One client per thread (requests sessions are not thread-safe); the
    # library's default rate limits are shared process-wide, so total request
    # rates stay within Internet Archive guidance regardless of worker count.
    if not hasattr(_local, "client"):
        _local.client = wayback.WaybackClient()
    return _local.client


def log_error(domain, msg):
    with _log_lock:
        with open(config.FP_WB_ERRORS, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {domain}\t{msg}\n")


def query_captures(domain):
    """Closest in-window capture timestamp ('YYYYmmddHHMMSS') or None."""
    path = config.cdx_path(domain)
    if os.path.exists(path):
        with gzip.open(path, "rt") as f:
            rows = json.load(f)
    else:
        records = [
            r
            for r in client().search(
                domain,
                from_date=config.WINDOW_FROM,
                to_date=config.WINDOW_TO,
                limit=200,
            )
            if r.statuscode == 200 and (r.mimetype or "").startswith("text/html")
        ]
        rows = [CDX_HEADER] + [
            [
                r.urlkey,
                r.timestamp.strftime("%Y%m%d%H%M%S"),
                r.original,
                r.mimetype,
                str(r.statuscode),
                r.digest,
                str(r.length or ""),
            ]
            for r in records
        ]
        if len(rows) == 1:  # header only -> keep same "empty" shape as CDX API
            rows = []
        with gzip.open(path, "wt") as f:
            json.dump(rows, f)

    if len(rows) < 2:
        return None
    timestamps = [row[1] for row in rows[1:]]
    target = int(config.TARGET_TS + "000000")
    return min(timestamps, key=lambda ts: abs(int(ts) - target))


def fetch_snapshot(domain, timestamp):
    """Fetch original archived bytes; cache gzipped. Returns n_bytes."""
    path = config.html_path(domain)
    if os.path.exists(path):
        return os.path.getsize(path)
    memento = client().get_memento(
        f"https://{domain}/",
        timestamp=datetime.strptime(timestamp, "%Y%m%d%H%M%S"),
        mode=wayback.Mode.original,
        exact=False,
    )
    content = memento.content[: config.MAX_HTML_BYTES]
    with gzip.open(path, "wb") as f:
        f.write(content)
    return len(content)


def preflight():
    """Verify Mode.original returns raw HTML on two known domains."""
    for domain in ("nytimes.com", "wikipedia.org"):
        ts = query_captures(domain)
        assert ts is not None, f"no 2022 capture for {domain}?!"
        n = fetch_snapshot(domain, ts)
        with gzip.open(config.html_path(domain), "rt", errors="ignore") as f:
            html = f.read()
        injected = "web-static.archive.org" in html or "wombat.js" in html
        print(
            f"  {domain}: snapshot {ts}, {n:,} bytes, "
            f"wayback-injected-markup={'YES (BAD)' if injected else 'no'}"
        )
        assert not injected, "memento fetch returned rewritten replay HTML"
    print("Pre-flight OK: Mode.original returns original bytes.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preflight", action="store_true", help="Run checks only.")
    ap.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Fetch at most N domains this run (testing).",
    )
    args = ap.parse_args()

    os.makedirs(config.CDX_DIR, exist_ok=True)
    os.makedirs(config.HTML_DIR, exist_ok=True)

    if args.preflight:
        preflight()
        return

    targets = pd.read_csv(config.FP_WB_TARGETS)
    domains = targets["private_domain"].drop_duplicates().tolist()
    if args.limit:
        domains = domains[: args.limit]
    total = len(domains)
    print(
        f"Fetching {total:,} domains -> {config.WB_DATA_DIR} "
        f"({N_WORKERS} workers, wayback-lib rate limits)",
        flush=True,
    )

    done = 0
    done_lock = threading.Lock()

    def process(domain):
        nonlocal done
        try:
            ts = query_captures(domain)
        except Exception as e:  # library exhausts its own retries first
            log_error(domain, f"search: {type(e).__name__}: {e}")
            row = {
                "private_domain": domain,
                "cdx_hit": False,
                "snapshot_ts": None,
                "status": "cdx_error",
                "bytes": 0,
            }
        else:
            if ts is None:
                row = {
                    "private_domain": domain,
                    "cdx_hit": False,
                    "snapshot_ts": None,
                    "status": "no_capture",
                    "bytes": 0,
                }
            else:
                try:
                    n = fetch_snapshot(domain, ts)
                    row = {
                        "private_domain": domain,
                        "cdx_hit": True,
                        "snapshot_ts": ts,
                        "status": "ok",
                        "bytes": n,
                    }
                except Exception as e:
                    log_error(domain, f"memento: {type(e).__name__}: {e}")
                    row = {
                        "private_domain": domain,
                        "cdx_hit": True,
                        "snapshot_ts": ts,
                        "status": "fetch_error",
                        "bytes": 0,
                    }
        with done_lock:
            done += 1
            if done % 100 == 0 or done == total:
                print(f"  [{done:>5}/{total}]", flush=True)
        return row

    with ThreadPoolExecutor(max_workers=N_WORKERS) as pool:
        rows = list(pool.map(process, domains))

    manifest = targets.merge(pd.DataFrame(rows), on="private_domain", how="left")
    manifest.to_csv(config.FP_WB_MANIFEST, index=False)
    statuses = manifest.drop_duplicates("private_domain")["status"].value_counts()
    print(f"Wrote {config.FP_WB_MANIFEST}")
    print(statuses.to_string())


if __name__ == "__main__":
    main()
