import csv
import json
import os
import time
import requests

BLACKLIGHT_ENDPOINT = "https://blacklight-us-ca.api.themarkup.org"
TARGETS_CSV = "../../data/rescan_targets_2026.csv"
OUTPUT_DIR = "../../data/blacklight_json_2026"
ERROR_LOG = os.path.join(OUTPUT_DIR, "_errors.log")

TARGET_SUCCESSES = 500   # stop once we've accumulated this many valid scans
MAX_RETRIES = 3          # total attempts per domain (covers transient errors + empty groups)
REQUEST_TIMEOUT = 300    # seconds — Blacklight scans can take 2+ minutes
PAUSE_BETWEEN = 2        # polite pause between successful calls

os.makedirs(OUTPUT_DIR, exist_ok=True)
with open(TARGETS_CSV) as f:
    targets = sorted(csv.DictReader(f), key=lambda r: int(r["rank_by_reach"]))
total = len(targets)
done = skipped = failed = 0

# Running tally: successes already on disk count toward TARGET_SUCCESSES
successes_on_disk = sum(
    1 for row in targets
    if os.path.exists(os.path.join(OUTPUT_DIR, row["private_domain"].replace(".", "_") + ".json"))
)
print(f"Rescan: {total} targets -> {OUTPUT_DIR}")
print(f"Target = {TARGET_SUCCESSES} successes; already on disk = {successes_on_disk}")

for row in targets:
    if successes_on_disk + done >= TARGET_SUCCESSES:
        print(f"Reached {TARGET_SUCCESSES} successes — stopping.")
        break

    domain = row["private_domain"]
    out_path = os.path.join(OUTPUT_DIR, domain.replace(".", "_") + ".json")

    if os.path.exists(out_path):
        skipped += 1
        print(f"[{skipped+done+failed:>3}/{total}] SKIP  {domain} (already done)")
        continue

    print(f"[{skipped+done+failed+1:>3}/{total}] FETCH {domain} ...", flush=True)
    t0 = time.time()
    data = None
    last_err = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(BLACKLIGHT_ENDPOINT,
                              json={"inUrl": f"https://{domain}"},
                              timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            payload = r.json()
        except requests.RequestException as e:
            last_err = f"request_exception: {e}"
            time.sleep(5)
            continue

        if payload.get("groups"):
            data = payload
            break
        last_err = "empty_groups"
        time.sleep(5)

    dt = time.time() - t0

    if data is None:
        failed += 1
        with open(ERROR_LOG, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {domain}\t{last_err}\n")
        print(f"    FAIL in {dt:.1f}s  ({last_err})")
        continue

    data["domain_name"] = domain
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
    done += 1
    cards = sum(len(g.get("cards", [])) for g in data.get("groups", []))
    print(f"    OK   {dt:5.1f}s   groups={len(data['groups'])} cards={cards}")
    time.sleep(PAUSE_BETWEEN)

print(f"\nFinished this run. new scans={done}  skipped={skipped}  failed={failed}")
print(f"Cumulative successes on disk: {successes_on_disk + done} / {TARGET_SUCCESSES} target")
