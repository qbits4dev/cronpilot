#!/usr/bin/env python3
"""Fetch Smartflo call records and export them to a flattened CSV file."""

import csv
import json
import os
from datetime import datetime, timedelta, timezone
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
        self.output_path = os.getenv(
            "SMARTFLO_OUTPUT_PATH", os.path.join(os.getcwd(), "call_records.csv")
        )


CONFIG = Config()


def _get_api_token() -> str:
    for key in ("SMARTFLO_API_TOKEN", "SMARTFLO_TOKEN", "API_TOKEN"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    return ""


def _format_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def build_call_records_url(page: int = 1) -> str:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    start_date = CONFIG.from_date or _format_datetime(today_start)
    end_date = CONFIG.to_date or _format_datetime(today_end)
    params = [
        f"from_date={parse.quote(start_date)}",
        f"to_date={parse.quote(end_date)}",
        f"limit={CONFIG.page_size}",
        f"page={page}",
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


def flatten_record(record: Dict[str, Any], parent_key: str = "") -> Dict[str, Any]:
    flattened: Dict[str, Any] = {}
    for key, value in record.items():
        full_key = f"{parent_key}.{key}" if parent_key else key
        if isinstance(value, dict):
            flattened.update(flatten_record(value, full_key))
        elif isinstance(value, list):
            flattened[full_key] = json.dumps(value, ensure_ascii=False)
        else:
            flattened[full_key] = value
    return flattened


def write_flattened_csv(records: List[Dict[str, Any]], output_path: str) -> None:
    flattened_records = [flatten_record(record) for record in records]
    fieldnames = sorted({key for record in flattened_records for key in record.keys()})

    directory = os.path.dirname(output_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flattened_records)


def main() -> None:
    records = fetch_call_records()
    write_flattened_csv(records, CONFIG.output_path)
    print(f"Exported {len(records)} call records to {CONFIG.output_path}")


if __name__ == "__main__":
    main()
