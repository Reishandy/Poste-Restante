"""
Builds directory/directory.json from directory/seed.txt.

TODO: Consider proper workflows once this is not considered demo anymore
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

SEED_PATH = Path(__file__).parent / "seed.txt"
OUTPUT_PATH = Path(__file__).parent / "directory.json"
TIMEOUT_SECONDS = 10


def fetch_node(hostname: str) -> dict | None:
    url = f"https://{hostname}/"
    try:
        resp = httpx.get(url, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print(f"  SKIP {hostname}: unreachable ({exc})", file=sys.stderr)
        return None

    role = data.get("service")
    if role not in ("storage", "relay"):
        print(f"  SKIP {hostname}: unexpected service field {role!r}", file=sys.stderr)
        return None

    node = {"hostname": hostname, "role": role}
    if role == "storage":
        pubkey = data.get("hpke_public_key")
        if not pubkey:
            print(f"  SKIP {hostname}: storage node missing hpke_public_key", file=sys.stderr)
            return None
        node["public_key"] = pubkey

    print(f"  OK   {hostname} -> {role}")
    return node


def main() -> None:
    seeds = [
        line.strip()
        for line in SEED_PATH.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    print(f"Checking {len(seeds)} seed hosts...")
    nodes = [n for n in (fetch_node(h) for h in seeds) if n is not None]

    if not nodes:
        print("No reachable nodes - refusing to publish an empty directory", file=sys.stderr)
        sys.exit(1)

    payload = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "nodes": nodes,
    }

    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {OUTPUT_PATH} with {len(nodes)} node(s)")


if __name__ == "__main__":
    main()
