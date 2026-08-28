"""Shared BigQuery helpers: the extraction SQL and a thin client wrapper.

The dry-run step (02) and the billed extract step (03) build the *same* SQL
here so their cost estimates and their results cannot drift apart.
"""

import config
import pandas as pd
from google.cloud import bigquery


# --------------------------------------------------------------------------- #
# Target domains
# --------------------------------------------------------------------------- #
def load_target_domains():
    """Panel registered-domains we request from HTTP Archive (reach-filtered)."""
    targets = pd.read_csv(config.FP_HA_TARGETS)
    keep = targets.loc[targets["reach"] >= config.TARGET_MIN_REACH, "private_domain"]
    return sorted(keep.dropna().unique().tolist())


# --------------------------------------------------------------------------- #
# SQL builders
# --------------------------------------------------------------------------- #
def _rank_clause(rank_cap):
    return f"  AND rank <= {int(rank_cap)}\n" if rank_cap is not None else ""


def build_requests_query(rank_cap=config.RANK_CAP):
    """One row per (page domain, request domain) with a request count.

    Scans only the `page` and `url` string columns for the given crawl slice,
    so it is the cheap query. First- vs third-party and tracker classification
    happen locally in 04. `req_domain` is NULL for data:/blob: URLs -- kept and
    treated as non-tracker downstream.

    Note: grouping by NET.REG_DOMAIN(page) unions requests across every
    crawled origin of a registered domain (news.google.com + mail.google.com
    -> google.com). That matches how the panel records visits (registered
    domain), and it is applied identically at both crawl dates; it does mean
    HA counts sit on a different scale than Blacklight's single-page scan,
    which the cross-instrument check in 05 quantifies.
    """
    return f"""
SELECT
  NET.REG_DOMAIN(page) AS page_domain,
  NET.REG_DOMAIN(url)  AS req_domain,
  COUNT(*)             AS n_requests
FROM `{config.HA_REQUESTS_TABLE}`
WHERE date = @date
  AND client = @client
  AND is_root_page = TRUE
{_rank_clause(rank_cap)}  AND NET.REG_DOMAIN(page) IN UNNEST(@targets)
GROUP BY page_domain, req_domain
"""


def build_cookies_query(rank_cap=config.COOKIE_RANK_CAP):
    """Third-party responses that set a cookie, per (page, request) domain.

    Scans `response_headers` (a large array column), so it is the expensive
    query and caps `rank` tighter. A third-party cookie is operationalized as a
    Set-Cookie header on a response whose registered domain differs from the
    page's.
    """
    return f"""
SELECT
  NET.REG_DOMAIN(page) AS page_domain,
  NET.REG_DOMAIN(url)  AS req_domain,
  COUNTIF(EXISTS(
    SELECT 1 FROM UNNEST(response_headers) h
    WHERE LOWER(h.name) = 'set-cookie'
  ))                   AS n_set_cookie_responses,
  COUNT(*)             AS n_requests
FROM `{config.HA_REQUESTS_TABLE}`
WHERE date = @date
  AND client = @client
  AND is_root_page = TRUE
{_rank_clause(rank_cap)}  AND NET.REG_DOMAIN(page) IN UNNEST(@targets)
  AND NET.REG_DOMAIN(url) != NET.REG_DOMAIN(page)
GROUP BY page_domain, req_domain
"""


# The set of (label, sql, cache-path-fn) tuples pulled for every crawl/client.
QUERY_SPECS = [
    ("requests", build_requests_query, config.raw_requests_path),
    ("cookies", build_cookies_query, config.raw_cookies_path),
]


# --------------------------------------------------------------------------- #
# Client wrapper
# --------------------------------------------------------------------------- #
def make_client():
    return bigquery.Client(project=config.require_billing_project())


def _job_config(date, client, targets, dry_run):
    return bigquery.QueryJobConfig(
        dry_run=dry_run,
        use_query_cache=not dry_run,
        query_parameters=[
            bigquery.ScalarQueryParameter("date", "DATE", date),
            bigquery.ScalarQueryParameter("client", "STRING", client),
            bigquery.ArrayQueryParameter("targets", "STRING", targets),
        ],
    )


def dry_run_bytes(bq_client, sql, date, client, targets):
    """Return bytes the query would scan, without running (or billing) it."""
    job = bq_client.query(sql, job_config=_job_config(date, client, targets, True))
    return job.total_bytes_processed


def run_query(bq_client, sql, date, client, targets):
    """Execute the query (billed). Return (DataFrame, bytes_billed)."""
    job = bq_client.query(sql, job_config=_job_config(date, client, targets, False))
    df = job.result().to_dataframe()
    return df, job.total_bytes_billed


def bytes_to_usd(n_bytes):
    return n_bytes / config.BYTES_PER_TIB * config.BQ_PRICE_PER_TIB_USD
