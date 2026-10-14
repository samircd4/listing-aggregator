"""Call one CatchBuys endpoint, print what matters, and save the response.

Usage:
    uv run python scripts/explore_catchbuys.py /some/path key=value key2=value2
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE = os.environ["CATCHBUYS_BASE_URL"].rstrip("/")
TOKEN = os.environ["CATCHBUYS_API_TOKEN"]
OUT = Path("tests/fixtures/catchbuys")

path = sys.argv[1] if len(sys.argv) > 1 else "/"
params = dict(arg.split("=", 1) for arg in sys.argv[2:])
url = BASE + "/" + path.lstrip("/")

start = time.perf_counter()
resp = httpx.get(url, params=params, headers={
                 "Authorization": f"Bearer {TOKEN}"}, timeout=30)
elapsed = time.perf_counter() - start

print(f"GET {resp.url}")
print(
    f"Status: {resp.status_code}   Time: {elapsed:.2f}s   Size: {len(resp.content)} bytes")
print(f"Content-Type: {resp.headers.get('content-type')}")

hints = ("rate", "limit", "retry", "remaining",
         "reset", "link", "total", "page", "count")
print("\nUseful headers:")
for k, v in resp.headers.items():
    if any(h in k.lower() for h in hints):
        print(f"  {k}: {v}")

try:
    data = resp.json()
except ValueError:
    print("\nResponse is not JSON. First 500 characters:\n", resp.text[:500])
    sys.exit(1)

print(f"\nTop-level type: {type(data).__name__}")
records = data
if isinstance(data, dict):
    print("Top-level keys:", list(data.keys()))
    for key, value in data.items():
        if isinstance(value, list):
            records = value
            print(f"Records found under key: '{key}'")
            break
    for key, value in data.items():
        if not isinstance(value, (list, dict)):
            print(f"  {key} = {value!r}")

if isinstance(records, list) and records:
    print(f"\nRecords on this page: {len(records)}")
    print("First record:")
    print(json.dumps(records[0], indent=2, default=str)[:3000])
    print("\nFields in first record (name: type):")
    for k, v in records[0].items():
        print(f"  {k}: {type(v).__name__}")

OUT.mkdir(parents=True, exist_ok=True)
name = path.strip("/").replace("/", "_") or "root"
file = OUT / f"{name}_{datetime.now():%Y%m%d_%H%M%S}.json"
file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
print(f"\nSaved full response to {file}")
