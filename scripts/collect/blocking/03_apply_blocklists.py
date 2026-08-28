"""Decide which responsible third-party domains each blocklist tier would stop.

Matching runs through adblock-rust, the engine Brave ships, so filter syntax --
domain anchors, third-party options, exception rules -- is honoured rather than
approximated by a substring test.

One caveat governs every number downstream. Blacklight records third-party
hostnames, not full request URLs, so a rule keyed on a path or query string can
never fire here. The Facebook pixel is the clearest case: EasyPrivacy blocks it
with ||connect.facebook.net/signals/ and two more path rules, none of which a
hostname can trigger, while Disconnect blocks the same tracker with a plain
||facebook.net^$third-party that does fire.

Rather than let that understate blocking silently, each pair is scored twice:

  blocked_X       a domain-level rule fires -- the tracker is stopped for certain
  rule_present_X  the list names this host somewhere, but only with a path
                  constraint this method cannot evaluate

The first gives an upper bound on residual exposure (block only what is certain),
the second a lower bound (assume every path rule would have fired). The truth
lies between, and 04 carries both through.
"""

import os
import re
import sys

import pandas as pd
from adblock import Engine, FilterSet

import config

# A rule this method can evaluate: an anchored host, optionally with a separator,
# carrying no path or wildcard before the options.
DOMAIN_ANCHORED = re.compile(r"^(@@)?\|\|[a-z0-9.\-_]+\^?(\$[^/]*)?$", re.I)
COSMETIC = re.compile(r"#[@?$%]?#")
# The host an anchored rule refers to, whatever follows it.
RULE_HOST = re.compile(r"^\|\|([a-z0-9.\-_]+)", re.I)


def build_engine(list_names, suffix):
    filter_set = FilterSet()
    for name in list_names:
        fp = os.path.join(config.BLOCKLIST_DIR, f"{name}_{suffix}.txt")
        with open(fp) as f:
            filter_set.add_filter_list(f.read())
    return Engine(filter_set=filter_set)


def rule_hosts(list_names, suffix):
    """Every host named by a non-exception anchored rule, path rules included."""
    hosts = set()
    for name in list_names:
        fp = os.path.join(config.BLOCKLIST_DIR, f"{name}_{suffix}.txt")
        with open(fp) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(("!", "[", "@@")) or COSMETIC.search(line):
                    continue
                m = RULE_HOST.match(line)
                if m:
                    hosts.add(m.group(1).lower().rstrip("."))
    return hosts


def host_is_named(host, named):
    """True if the host or any parent domain appears in the rule-host set."""
    parts = host.lower().rstrip(".").split(".")
    return any(".".join(parts[i:]) in named for i in range(len(parts) - 1))


def classify_rules(text):
    """Split a list into cosmetic, network, and hostname-evaluable network rules."""
    counts = {"cosmetic": 0, "network": 0, "domain_anchored": 0, "exception": 0}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("!", "[")):
            continue
        if COSMETIC.search(line):
            counts["cosmetic"] += 1
            continue
        counts["network"] += 1
        if line.startswith("@@"):
            counts["exception"] += 1
        if DOMAIN_ANCHORED.match(line):
            counts["domain_anchored"] += 1
    return counts


def rule_coverage(suffix):
    rows = []
    for name in config.LIST_SOURCES:
        fp = os.path.join(config.BLOCKLIST_DIR, f"{name}_{suffix}.txt")
        with open(fp) as f:
            counts = classify_rules(f.read())
        share = counts["domain_anchored"] / counts["network"] if counts["network"] else 0
        rows.append({"list": name, **counts, "domain_anchored_share": share})
    return pd.DataFrame(rows)


def main():
    suffix = config.PIN_DATE
    df = pd.read_csv(config.FP_SCRIPTS)

    pairs = (
        df[["private_domain", "script_domain"]].drop_duplicates().reset_index(drop=True)
    )
    print(f"Attribution rows: {len(df):,}")
    print(f"Distinct (site, third-party) pairs to evaluate: {len(pairs):,}\n")

    for tier in config.TIER_ORDER:
        label, list_names = config.TIERS[tier]
        engine = build_engine(list_names, suffix)
        print(f"Tier {tier} -- {label}")

        for request_type, col in [
            (config.REQUEST_TYPE, f"blocked_{tier}"),
            (
                config.REQUEST_TYPE_SENSITIVITY,
                f"blocked_{tier}_{config.REQUEST_TYPE_SENSITIVITY}",
            ),
        ]:
            pairs[col] = [
                engine.check_network_urls(
                    url=f"https://{s}/",
                    source_url=f"https://{d}/",
                    request_type=request_type,
                ).matched
                for d, s in zip(pairs.private_domain, pairs.script_domain)
            ]
            print(f"  {request_type:6s}: {pairs[col].mean():6.1%} of pairs blocked")

        named = rule_hosts(list_names, suffix)
        present = f"rule_present_{tier}"
        cache = {h: host_is_named(h, named) for h in pairs.script_domain.unique()}
        pairs[present] = pairs.script_domain.map(cache)
        undecided = int((pairs[present] & ~pairs[f"blocked_{tier}"]).sum())
        print(
            f"  named by a rule this method cannot evaluate: "
            f"{undecided:,} pairs ({undecided / len(pairs):6.1%})"
        )
        print(
            f"  residual bound: [{1 - pairs[present].mean():.1%}, "
            f"{1 - pairs[f'blocked_{tier}'].mean():.1%}] of pairs survive\n"
        )

    # A stricter list must block everything a looser one does. EasyList adds
    # rules to EasyPrivacy, so tier C cannot block less than tier B on any pair.
    violations = int((pairs["blocked_B"] & ~pairs["blocked_C"]).sum())
    print(f"Tier ordering check (C superset of B): {violations:,} violations")
    if violations:
        bad = pairs.loc[pairs["blocked_B"] & ~pairs["blocked_C"]].head(10)
        print(bad.to_string(index=False))
        raise AssertionError("Tier C blocks less than tier B; check list assembly.")

    os.makedirs(config.BLOCKING_DATA_DIR, exist_ok=True)
    pairs.to_csv(config.FP_BLOCKED_PAIRS, index=False)
    print(f"\nWrote {config.FP_BLOCKED_PAIRS}")

    cov = rule_coverage(suffix)
    cov.to_csv(config.FP_RULE_COVERAGE, index=False)
    print(f"Wrote {config.FP_RULE_COVERAGE}\n")
    print("Rule coverage -- what share of each list can a hostname test evaluate?")
    print(cov.to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
