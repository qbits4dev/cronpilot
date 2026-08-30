#!/usr/bin/env python3
"""Fetch Smartflo call records, identify DMFT-pressed numbers, and send them to Telegram."""

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
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "-1003983572640")
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")


CONFIG = Config()


def normalize_telegram_token(token: str) -> str:
    cleaned = token.strip()
    if not cleaned:
        return ""

    if cleaned.startswith("https://"):
        match = re.search(r"/bot([^/]+)/sendMessage", cleaned)
        if match:
            cleaned = match.group(1)
        else:
            cleaned = cleaned.rsplit("/", 1)[-1]

    if cleaned.startswith("bot"):
        cleaned = cleaned[3:]

    return cleaned


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
    print(
        f"Building call records URL with start_date={start_date} and end_date={end_date}"
    )
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


def extract_dmft_numbers(records: List[Dict[str, Any]]) -> List[str]:
    numbers: List[str] = []
    for record in records:
        dtmf_input = str(record.get("dtmf_input") or "").strip()
        if not dtmf_input:
            continue

        mobile_number = None
        client_number = str(record.get("client_number") or "").strip()
        if client_number:
            mobile_number = client_number
        else:
            contact_details = record.get("contact_details") or {}
            if isinstance(contact_details, dict):
                field_0 = str(contact_details.get("field_0") or "").strip()
                if field_0:
                    mobile_number = field_0

        if mobile_number:
            numbers.append(mobile_number)
            continue

        if dtmf_input.isdigit() and len(dtmf_input) >= 1:
            numbers.append(dtmf_input)
    return numbers


def send_telegram_message(text: str) -> None:
    token = normalize_telegram_token(CONFIG.telegram_bot_token)
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in the environment.")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": CONFIG.telegram_chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    req = request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )

    try:
        with request.urlopen(req, timeout=60) as response:
            body = response.read().decode("utf-8", errors="ignore")
            result = json.loads(body) if body else {}
    except error.HTTPError as exc:
        text_body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Telegram API error: {exc.code}: {text_body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Telegram request failed: {exc}") from exc

    if not result.get("ok", False):
        raise RuntimeError(f"Telegram send failed: {result}")


def main() -> None:
    records = fetch_call_records()
    dmft_numbers = extract_dmft_numbers(records)
    if not dmft_numbers:
        print("No DMFT-pressed numbers found.")
        return
    message = (
        f"Date: {CONFIG.from_date} to {CONFIG.to_date}\nDMFT pressed numbers:\n"
        + "\n".join(dmft_numbers)
    )
    send_telegram_message(message)
    print(
        f"Sent {len(dmft_numbers)} DMFT numbers to Telegram chat {CONFIG.telegram_chat_id}"
    )


if __name__ == "__main__":
    main()
