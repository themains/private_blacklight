"""Step 03 (BILLED): pull the HTTP Archive request maps into local Parquet.

Refuses to run without --confirm, so it cannot bill by accident. Review the
02_ha_dryrun.py estimate first. Idempotent: any crawl/client extract already on
disk is skipped, so re-running never re-bills.

For each crawl date x client it caches two tables:
  ha_requests_<date>_<client>.parquet  (page_domain, req_domain, n_requests)
  ha_cookies_<date>_<client>.parquet   (+ n_set_cookie_responses, third-party only)

Prereqs: gcloud auth application-default login; export BQ_BILLING_PROJECT=...
"""

import argparse
import os

import config
import ha_bigquery as hb


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--confirm",
        action="store_true",
        help="Actually run the billed queries (required).",
    )
    args = ap.parse_args()
    if not args.confirm:
        raise SystemExit(
            "Refusing to run billed queries without --confirm.\n"
            "Run 02_ha_dryrun.py first, review the cost, then:\n"
            "  python 03_ha_extract.py --confirm"
        )

    os.makedirs(config.HA_DATA_DIR, exist_ok=True)
    targets = hb.load_target_domains()
    bq = hb.make_client()
    print(f"Billing project : {config.BQ_BILLING_PROJECT}")
    print(f"Target domains  : {len(targets):,}\n")

    total_billed = 0
    for crawl_key, date in config.CRAWL_DATES.items():
        for client in config.CLIENTS:
            for label, build_sql, cache_path_fn in hb.QUERY_SPECS:
                out_path = cache_path_fn(crawl_key, client)
                tag = f"{crawl_key}/{client}/{label}"
                if os.path.exists(out_path):
                    print(f"  SKIP  {tag:32}  (cached: {os.path.basename(out_path)})")
                    continue

                print(f"  RUN   {tag:32}  ...", flush=True)
                df, billed = hb.run_query(bq, build_sql(), date, client, targets)
                total_billed += billed
                df.to_parquet(out_path, index=False)
                print(
                    f"        rows={len(df):>9,}  billed={billed / 2 ** 30:7.2f} GiB "
                    f"(${hb.bytes_to_usd(billed):.3f})  -> {os.path.basename(out_path)}"
                )

    print(
        f"\nDone. Total billed this run: {total_billed / 2 ** 40:.4f} TiB "
        f"(${hb.bytes_to_usd(total_billed):.2f})."
    )


if __name__ == "__main__":
    main()
