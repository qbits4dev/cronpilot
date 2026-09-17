#!/usr/bin/env python3
"""Fetch Smartflo call records and print DMFT-9 numbers from the CDR dataset."""

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib import error, parse, request


class Config:
    def __init__(self) -> None:
        self.base_url = os.getenv(
            "SMARTFLO_BASE_URL", "https://api-smartflo.tatateleservices.com"
        )
        self.request_timeout_seconds = int(
            os.getenv("SMARTFLO_REQUEST_TIMEOUT_SECONDS", "180")
        )
        self.max_retries = int(os.getenv("SMARTFLO_MAX_RETRIES", "3"))
        self.page_size = int(os.getenv("SMARTFLO_CALL_RECORDS_PAGE_SIZE", "100"))
        self.from_date = os.getenv("SMARTFLO_FROM_DATE", "")
        self.to_date = os.getenv("SMARTFLO_TO_DATE", "")
        self.broadcast_id = os.getenv("SMARTFLO_BROADCAST_ID", "170861")
        self.dnd_list_id = os.getenv("SMARTFLO_DND_LIST_ID", "4394")


CONFIG = Config()


def _get_api_token() -> str:
    for key in ("SMARTFLO_API_TOKEN", "SMARTFLO_TOKEN", "API_TOKEN"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    return ""


def _format_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def call_api(method: str, url: str, payload: Dict[str, Any] | None = None) -> Any:
    """Call the Smartflo API with the configured bearer token."""
    token = _get_api_token()
    if not token:
        raise RuntimeError(
            "SMARTFLO_API_TOKEN is not set in the environment. Export it before running this script."
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method=method)

    last_error: Any = None
    for attempt in range(1, CONFIG.max_retries + 1):
        try:
            with request.urlopen(
                req, timeout=CONFIG.request_timeout_seconds
            ) as response:
                body = response.read().decode("utf-8", errors="ignore")
                return json.loads(body) if body else {}
        except error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="ignore")
            if (
                exc.code in {408, 429, 500, 502, 503, 504}
                and attempt < CONFIG.max_retries
            ):
                continue
            raise RuntimeError(f"HTTP {exc.code}: {text}") from exc
        except (error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < CONFIG.max_retries:
                continue
            raise RuntimeError(
                f"Request failed after {CONFIG.max_retries} attempts: {exc}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON from Smartflo API: {exc}") from exc

    if last_error is not None:
        raise RuntimeError(
            f"Request failed after {CONFIG.max_retries} attempts: {last_error}"
        )
    raise RuntimeError("Request failed without a captured error")


def build_call_records_url(page: int = 1) -> str:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    start_date = CONFIG.from_date or _format_datetime(today_start)
    end_date = CONFIG.to_date or _format_datetime(today_end)
    CONFIG.from_date = start_date
    CONFIG.to_date = end_date

    params = [
        f"from_date={parse.quote(start_date)}",
        f"to_date={parse.quote(end_date)}",
        f"limit={CONFIG.page_size}",
        f"page={page}",
        f"broadcast={parse.quote(CONFIG.broadcast_id)}",
    ]
    return f"{CONFIG.base_url}/v1/call/records?{'&'.join(params)}"


def fetch_call_records() -> List[Dict[str, Any]]:
    token = _get_api_token()
    if not token:
        raise RuntimeError(
            "SMARTFLO_API_TOKEN is not set in the environment. Export it before running this script."
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    records: List[Dict[str, Any]] = []
    page = 1

    while True:
        url = build_call_records_url(page)
        req = request.Request(url, headers=headers, method="GET")

        for attempt in range(1, CONFIG.max_retries + 1):
            try:
                with request.urlopen(
                    req, timeout=CONFIG.request_timeout_seconds
                ) as response:
                    body = response.read().decode("utf-8", errors="ignore")
                    payload = json.loads(body) if body else {}
                    results = payload.get("results", [])
                    if not isinstance(results, list):
                        return records

                    page_records = [item for item in results if isinstance(item, dict)]
                    if not page_records:
                        return records

                    records.extend(page_records)
                    if len(page_records) < CONFIG.page_size:
                        return records
                    page += 1
                    break
            except error.HTTPError as exc:
                text = exc.read().decode("utf-8", errors="ignore")
                if (
                    exc.code in {408, 429, 500, 502, 503, 504}
                    and attempt < CONFIG.max_retries
                ):
                    continue
                raise RuntimeError(f"HTTP {exc.code}: {text}") from exc
            except (error.URLError, TimeoutError, OSError) as exc:
                if attempt < CONFIG.max_retries:
                    continue
                raise RuntimeError(
                    f"Request failed after {CONFIG.max_retries} attempts: {exc}"
                ) from exc

    raise RuntimeError("Request failed without a captured error")


def extract_dmft_numbers(
    records: List[Dict[str, Any]], dmft_key: str = "9"
) -> List[str]:
    """Return the phone numbers associated with a specific DTMF key from CDR records."""
    numbers: List[str] = []
    for record in records:
        dtmf_input = str(record.get("dtmf_input") or "").strip()
        if dtmf_input != dmft_key:
            continue

        client_number = str(record.get("client_number") or "").strip()
        contact_details = record.get("contact_details") or {}
        field_0 = ""
        if isinstance(contact_details, dict):
            field_0 = str(contact_details.get("field_0") or "").strip()

        if client_number:
            numbers.append(client_number)
        elif field_0:
            numbers.append(field_0)

    return numbers


def fetch_dnd_numbers(list_id: str) -> List[str]:
    """Fetch all numbers already in a Smartflo DND list to avoid duplicate inserts."""
    url = f"{CONFIG.base_url}/v1/broadcast/dnd/leads?list_id={parse.quote(str(list_id))}&limit=100"
    payload = call_api("GET", url)
    data = payload.get("data", []) if isinstance(payload, dict) else []
    numbers: List[str] = []
    for item in data:
        if isinstance(item, dict):
            number = str(item.get("number") or "").strip()
            if number:
                numbers.append(number)
    return numbers


def add_dnd_number(number: str, list_id: str) -> None:
    """Add a single number to the configured Smartflo account DND list."""
    url = f"{CONFIG.base_url}/v1/broadcast/dnd/lead"
    body: Dict[str, Any] = {"number": number, "type": "number"}
    if list_id:
        body["list_id"] = list_id
    response = call_api("POST", url, body)
    if isinstance(response, dict) and response.get("success") is False:
        raise RuntimeError(f"Failed to add {number} to DND list {list_id}: {response}")


def sync_dmft_numbers_to_dnd_list(dmft_numbers: List[str], list_id: str) -> List[str]:
    """Add new DMFT-9 numbers to the target account DND list and return the inserted numbers."""
    existing = set(fetch_dnd_numbers(list_id))
    inserted: List[str] = []
    for number in dmft_numbers:
        normalized = str(number).strip()
        if not normalized or normalized in existing:
            continue
        add_dnd_number(normalized, list_id)
        inserted.append(normalized)
        existing.add(normalized)
    return inserted


def main() -> None:
    records = fetch_call_records()
    dmft_numbers = extract_dmft_numbers(records, dmft_key="9")
    unique_numbers = []
    seen = set()
    for number in dmft_numbers:
        normalized = str(number).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_numbers.append(normalized)

    if not unique_numbers:
        print("No DMFT-9 pressed numbers found.")
        return

    print(f"Date: {CONFIG.from_date} to {CONFIG.to_date}")
    print(f"Count: {len(unique_numbers)}")
    print("DMFT 9 pressed numbers:")
    for number in unique_numbers:
        print(number)

    inserted = sync_dmft_numbers_to_dnd_list(unique_numbers, CONFIG.dnd_list_id)
    if inserted:
        print(f"Added {len(inserted)} new numbers to DND list {CONFIG.dnd_list_id}")
    else:
        print(
            f"No new numbers were added; DND list {CONFIG.dnd_list_id} already contains these entries."
        )


if __name__ == "__main__":
    main()
