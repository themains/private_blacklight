"""Step 02 (free): estimate the BigQuery cost before running anything billed.

Runs every extraction query as a BigQuery *dry run*. A dry run fully parses and
plans the query -- so it also validates column and struct-field names against
the live schema -- but scans nothing and costs nothing. It reports the bytes
each query would scan and the dollar estimate at on-demand pricing.

Review this output before running 03_ha_extract.py.

Prereqs: gcloud auth application-default login; export BQ_BILLING_PROJECT=...
"""

import config
import ha_bigquery as hb


def main():
    targets = hb.load_target_domains()
    bq = hb.make_client()
    print(f"Billing project : {config.BQ_BILLING_PROJECT}")
    print(f"Target domains  : {len(targets):,} (reach >= {config.TARGET_MIN_REACH})")
    print(f"Price           : ${config.BQ_PRICE_PER_TIB_USD:.2f} / TiB\n")

    grand_bytes = 0
    rows = []
    for crawl_key, date in config.CRAWL_DATES.items():
        for client in config.CLIENTS:
            for label, build_sql, _ in hb.QUERY_SPECS:
                sql = build_sql()
                try:
                    n_bytes = hb.dry_run_bytes(bq, sql, date, client, targets)
                except Exception as exc:  # surface schema/SQL errors clearly
                    print(f"  ! {crawl_key:16} {client:7} {label:8}  ERROR: {exc}")
                    raise
                grand_bytes += n_bytes
                rows.append((crawl_key, date, client, label, n_bytes))
                gib = n_bytes / 2**30
                print(
                    f"  {crawl_key:16} {date}  {client:7} {label:8}  "
                    f"{gib:9.2f} GiB   ${hb.bytes_to_usd(n_bytes):7.3f}"
                )

    print("\n" + "-" * 64)
    print(
        f"  TOTAL  {grand_bytes / 2 ** 40:.4f} TiB   "
        f"${hb.bytes_to_usd(grand_bytes):.2f}   "
        f"(first 1 TiB/month is free)"
    )
    print("-" * 64)
    print(
        "\nReview the above. To extract (billed) once you approve, run:\n"
        "  python 03_ha_extract.py --confirm"
    )


if __name__ == "__main__":
    main()
