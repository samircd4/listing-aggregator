import os

import httpx
from dotenv import load_dotenv

load_dotenv()
base = os.environ["CATCHBUYS_BASE_URL"].rstrip("/")
headers = {"Authorization": f"Bearer {os.environ['CATCHBUYS_API_TOKEN']}"}

with httpx.Client(headers=headers, timeout=30) as client:
    for i in range(1, 71):
        r = client.get(f"{base}/listings", params={"per_page": 1})
        print(i, r.status_code, r.headers.get(
            "X-RateLimit-Remaining"), r.headers.get("Retry-After"))
        if r.status_code == 429:
            print(dict(r.headers))
            print(r.text[:300])
            break
