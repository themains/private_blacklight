"""Fetch the blocklists, pinned to the Blacklight scan window.

Each list is pulled at the commit nearest config.PIN_DATE so the defense being
modelled is the one a user could actually have installed when the sites were
measured, not today's version of it. The manifest records repo, commit, date and
sha256 so a rerun either reproduces the same bytes or fails loudly.

Disconnect ships a JSON of tracker hosts rather than filter syntax, so it is
converted to third-party domain rules -- the form Firefox's tracking protection
applies it in.

  --current   fetch today's lists instead of the pinned ones (robustness variant)
"""

import argparse
import hashlib
import json
import os
import sys

import requests

import config

GITHUB_API = "https://api.github.com"
RAW_BASE = "https://raw.githubusercontent.com"
TIMEOUT = 60

# Firefox's tracking protection applies these Disconnect categories by default.
# "Content" (the strict-mode addition) is excluded: it blocks whole content CDNs
# and would overstate what a typical protected user actually blocks.
DISCONNECT_CATEGORIES = [
    "Advertising",
    "Analytics",
    "Social",
    "Fingerprinting",
    "FingerprintingInvasive",
    "FingerprintingGeneral",
    "Cryptomining",
]


def resolve_commit(repo, path, until):
    """Newest commit touching `path` at or before `until` (None = latest)."""
    params = {"path": path, "per_page": 1}
    if until:
        params["until"] = f"{until}T23:59:59Z"
    r = requests.get(f"{GITHUB_API}/repos/{repo}/commits", params=params, timeout=TIMEOUT)
    r.raise_for_status()
    commits = r.json()
    if not commits:
        raise RuntimeError(f"No commit for {repo}:{path} at or before {until}")
    head = commits[0]
    return head["sha"], head["commit"]["committer"]["date"]


def fetch(repo, sha, path):
    r = requests.get(f"{RAW_BASE}/{repo}/{sha}/{path}", timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


def list_dir(repo, sha, path):
    """Names of the .txt files in `path` at `sha`."""
    r = requests.get(
        f"{GITHUB_API}/repos/{repo}/contents/{path}", params={"ref": sha}, timeout=TIMEOUT
    )
    r.raise_for_status()
    return sorted(
        e["path"] for e in r.json() if e["type"] == "file" and e["name"].endswith(".txt")
    )


def fetch_fragments(repo, sha, path):
    """Concatenate every fragment in a source directory, as the build does."""
    paths = list_dir(repo, sha, path)
    print(f"    {len(paths)} fragments")
    return "\n".join(fetch(repo, sha, p) for p in paths) + "\n", len(paths)


def disconnect_to_rules(services_json):
    """Convert Disconnect's services.json into third-party domain block rules.

    The file nests category -> [ {company: {url: [hosts...]}} ]. Everything under
    a blocked category becomes ||host^$third-party, which is how the list is
    enforced in a browser: requests to the host are blocked unless it is the site
    you are on.
    """
    data = json.loads(services_json)
    categories = data.get("categories", {})
    hosts = set()
    kept, skipped = [], []

    for category, entries in categories.items():
        if category not in DISCONNECT_CATEGORIES:
            skipped.append(category)
            continue
        kept.append(category)
        for entry in entries:
            for _company, sites in entry.items():
                if not isinstance(sites, dict):
                    continue
                for _url, domains in sites.items():
                    if isinstance(domains, list):
                        hosts.update(d.strip().lower() for d in domains if d)

    print(f"    categories used: {', '.join(sorted(kept))}")
    print(f"    categories skipped: {', '.join(sorted(skipped))}")
    rules = [f"||{h}^$third-party" for h in sorted(hosts)]
    return "\n".join(rules) + "\n", len(hosts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--current",
        action="store_true",
        help="fetch current lists instead of the pinned commit",
    )
    args = ap.parse_args()

    until = None if args.current else config.PIN_DATE
    label = "current" if args.current else f"pinned to {config.PIN_DATE}"
    os.makedirs(config.BLOCKLIST_DIR, exist_ok=True)
    print(f"Fetching blocklists ({label})\n")

    manifest = {"pin_date": until, "lists": {}}

    for name, (repo, path) in config.LIST_SOURCES.items():
        print(f"  {name}: {repo}/{path}")
        sha, committed = resolve_commit(repo, path, until)
        print(f"    commit {sha[:10]} ({committed})")

        n_hosts = n_fragments = None
        if path.endswith(".json"):
            text, n_hosts = disconnect_to_rules(fetch(repo, sha, path))
        else:
            text, n_fragments = fetch_fragments(repo, sha, path)

        suffix = "current" if args.current else config.PIN_DATE
        out = os.path.join(config.BLOCKLIST_DIR, f"{name}_{suffix}.txt")
        with open(out, "w") as f:
            f.write(text)

        digest = hashlib.sha256(text.encode()).hexdigest()
        n_lines = text.count("\n")
        manifest["lists"][name] = {
            "repo": repo,
            "path": path,
            "commit": sha,
            "committed": committed,
            "file": os.path.basename(out),
            "sha256": digest,
            "lines": n_lines,
            "hosts": n_hosts,
            "fragments": n_fragments,
        }
        print(f"    {n_lines:,} lines -> {os.path.basename(out)}")
        print(f"    sha256 {digest[:16]}...\n")

    fp = (
        config.FP_MANIFEST
        if not args.current
        else config.FP_MANIFEST.replace(".json", "_current.json")
    )
    with open(fp, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Wrote {fp}")


if __name__ == "__main__":
    sys.exit(main())
