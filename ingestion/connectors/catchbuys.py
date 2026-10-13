from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv


class CatchBuysClient:
    """Client for the CatchBuys listings API."""

    def __init__(
        self,
        base_url: str | None = None,
        api_token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        load_dotenv()

        self.base_url = (base_url or os.getenv("CATCHBUYS_BASE_URL", "")).rstrip("/")
        self.api_token = api_token or os.getenv("CATCHBUYS_API_TOKEN", "")
        self.timeout = timeout

        if not self.base_url:
            raise ValueError("CATCHBUYS_BASE_URL is required")
        if not self.api_token:
            raise ValueError("CATCHBUYS_API_TOKEN is required")

    async def list_listings(
        self,
        *,
        page: int = 1,
        per_page: int | None = None,
    ) -> dict[str, Any]:
        """Fetch one page of listings from CatchBuys."""
        if page < 1:
            raise ValueError("page must be greater than or equal to 1")
        if per_page is not None and per_page < 1:
            raise ValueError("per_page must be greater than or equal to 1")

        params: dict[str, int] = {"page": page}
        if per_page is not None:
            params["per_page"] = per_page

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_token}",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/listings",
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict):
            raise TypeError("CatchBuys listings response must be a JSON object")

        return payload
