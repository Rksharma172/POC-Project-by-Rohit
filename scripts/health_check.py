"""
Quick health check script.
Usage: python scripts/health_check.py --api-url http://localhost:8000
"""
from __future__ import annotations

import asyncio
import argparse
import httpx
import json


async def check(api_url: str) -> None:
    async with httpx.AsyncClient(base_url=api_url, timeout=10) as client:
        for endpoint in ["/health", "/health/ready"]:
            resp = await client.get(endpoint)
            print(f"{endpoint}: {resp.status_code}")
            print(json.dumps(resp.json(), indent=2))
            print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8000")
    args = parser.parse_args()
    asyncio.run(check(args.api_url))
