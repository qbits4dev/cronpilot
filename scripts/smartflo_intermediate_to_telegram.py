#!/usr/bin/env python3
"""Fetch Smartflo leads from the intermediate lead list, filter by dmft_press=true,
and send the matching leads to a Telegram group."""

import csv
import json
import os
import socket
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib import error, parse, request


class Config:
    def __init__(self) -> None:
        self.base_url = os.getenv(
            "SMARTFLO_BASE_URL", "https://api-smartflo.tatateleservices.com"
        )
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "5550741389")
        self.request_timeout_seconds = int(
            os.getenv("SMARTFLO_REQUEST_TIMEOUT_SECONDS", "180")
        )
        self.max_retries = int(os.getenv("SMARTFLO_MAX_RETRIES", "3"))
        self.leads_page_size = os.getenv("SMARTFLO_LEADS_PAGE_SIZE", "4")
        self.broadcast_id = os.getenv("SMARTFLO_BROADCAST_ID", "")
        self.smartflo_api_token = os.getenv(
            "SMARTFLO_API_TOKEN",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4MDY4NzIiLCJjciI6ZmFsc2UsImlzcyI6Imh0dHA6Ly9jbG91ZHBob25lLnRhdGF0ZWxlc2VydmljZXMuY29tL2Nvbm5lY3QvYXBpL3YxL2FwaS10b2tlbiIsImlhdCI6MTc4NzkxMTE3OSwibmJmIjoxNzg3OTExMTc5LCJleHAiOjE3OTU2ODcxNzksImp0aSI6IndOWDNoaE1icEgxQ0ZpQlAifQ.z01zDB0wEiF8Bzyh7rWAm1qF563hGuFc94yTMgewM54",
        )
        self.telegram_bot_token = os.getenv(
            "TELEGRAM_BOT_TOKEN", "8139116469:AAHtKDSAjB6c0au7HnyJ62xgII5UWuLe1sg"
        )


CONFIG = Config()


def normalize_bool_value(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if value is None:
        return None

    text = str(value).strip().lower()
    if text in {"true", "yes", "y", "1", "on"}:
        return True
    if text in {"false", "no", "n", "0", "off", ""}:
        return False
    return None


def call_api(method: str, url: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    if not CONFIG.smartflo_api_token:
        raise RuntimeError(
            "SMARTFLO_API_TOKEN is not set. Export it before running this script."
        )

    headers = {
        "Authorization": f"Bearer {CONFIG.smartflo_api_token}",
        "Content-Type": "application/json",
    }
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method=method)

    last_error: Optional[Exception] = None
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
                print(
                    f"Smartflo request failed with HTTP {exc.code}; retrying ({attempt}/{CONFIG.max_retries})..."
                )
                continue
            raise RuntimeError(f"HTTP {exc.code}: {text}") from exc
        except (error.URLError, TimeoutError, socket.timeout) as exc:
            last_error = exc
            if attempt < CONFIG.max_retries:
                print(
                    f"Smartflo request timed out; retrying ({attempt}/{CONFIG.max_retries})..."
                )
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


def build_call_records_url() -> str:
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    params = [
        f"from_date={parse.quote(start_date)}",
        f"to_date={parse.quote(end_date)}",
        f"limit={CONFIG.leads_page_size}",
        "broadcast=true",
        "page=1",
    ]
    if CONFIG.broadcast_id:
        params.append(f"broadcast_id={parse.quote(CONFIG.broadcast_id)}")
    return f"{CONFIG.base_url}/v1/call/records?{'&'.join(params)}"


def extract_dtmf_records(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        results = payload.get("results")
        if isinstance(results, list):
            return [
                item
                for item in results
                if isinstance(item, dict) and str(item.get("dtmf_input") or "").strip()
            ]

    return []


def write_records_to_csv(records: List[Dict[str, Any]], output_path: str) -> None:
    if not records:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            handle.write("")
        return

    flattened_records: List[Dict[str, Any]] = []
    for record in records:
        flattened: Dict[str, Any] = {}
        for key, value in record.items():
            if isinstance(value, (dict, list)):
                flattened[key] = json.dumps(value, ensure_ascii=False)
            else:
                flattened[key] = value
        flattened_records.append(flattened)

    fieldnames = sorted({key for record in flattened_records for key in record.keys()})

    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flattened_records)


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps(
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
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
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON from Telegram API: {body}") from exc

    if not result.get("ok", False):
        raise RuntimeError(f"Telegram send failed: {result}")


def main() -> None:
    chat_id = CONFIG.telegram_chat_id

    if not CONFIG.telegram_bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. Export it before running this script."
        )

    records_response = call_api("GET", build_call_records_url())
    dtmf_records = extract_dtmf_records(records_response)
    if not dtmf_records:
        print("No call records with dtmf_input were found.")
        return

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    message_lines = [
        f"Date: {ts}",
        f"Found {len(dtmf_records)} call records with dtmf_input:",
    ]
    for record in dtmf_records:
        client_number = (
            record.get("client_number")
            or record.get("contact_details", {}).get("field_0")
            or ""
        )
        dtmf_input = record.get("dtmf_input") or ""
        message_lines.append(f"- {client_number or 'Unknown'}: {dtmf_input}")

    message = "\n".join(message_lines)
    output_path = os.path.join(
        os.path.dirname(__file__), "..", "call_records_output.csv"
    )
    write_records_to_csv(dtmf_records, output_path)
    send_telegram_message(CONFIG.telegram_bot_token, chat_id, message)
    print(f"Sent {len(dtmf_records)} records to Telegram chat {chat_id}")
    print(f"Saved {len(dtmf_records)} records to {output_path}")


if __name__ == "__main__":
    main()
