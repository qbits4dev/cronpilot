#!/usr/bin/env python3
"""Upload leads from a CSV file into a Smartflo lead list named broadcast1.

This script uses only Python's built-in libraries.
It reads the input CSV, finds the lead list by name, and posts the leads to the
Smartflo bulk lead API using a hardcoded API token.
"""

import csv
import json
from pathlib import Path
from urllib import error, request

API_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4MDY4NzIiLCJjciI6ZmFsc2UsImlzcyI6Imh0dHA6Ly9jbG91ZHBob25lLnRhdGF0ZWxlc2VydmljZXMuY29tL2Nvbm5lY3QvYXBpL3YxL2FwaS10b2tlbiIsImlhdCI6MTc4NzEzOTIzMCwibmJmIjoxNzg3MTM5MjMwLCJleHAiOjE3OTQ5MTUyMzAsImp0aSI6ImVVcExKR0JhVGpRbmFqbE0ifQ.pQ1uDJVkVVToOAmQVIsR1fsf1WMewkqPFnPSkw7pL5g"
BASE_URL = "https://api-smartflo.tatateleservices.com"
INPUT_PATH = "/home/atulitha/projects/data/mobile numbers/inter"
LEAD_LIST_NAME = "intermediate"
BATCH_SIZE = 10000


def normalize_phone(value):
    if value is None:
        return ""
    return "".join(ch for ch in str(value).strip() if ch.isdigit())


def iter_csv_files(input_path):
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input path not found: {path}")

    if path.is_file():
        if path.suffix.lower() != ".csv":
            raise ValueError(f"Input file is not a CSV: {path}")
        return [path]

    csv_files = sorted(path.rglob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in: {path}")
    return csv_files


def load_leads(input_path):
    csv_files = iter_csv_files(input_path)
    leads = []
    seen_phones = set()

    for csv_file in csv_files:
        with csv_file.open("r", newline="", encoding="utf-8-sig") as infile:
            reader = csv.DictReader(infile)
            if not reader.fieldnames:
                print(f"Skipping {csv_file}: no header row")
                continue

            for row in reader:
                name = (row.get("name") or "").strip()
                phone = normalize_phone(
                    row.get("mobile") or row.get("phone") or row.get("number") or ""
                )
                if not phone:
                    print(f"Skipping row without phone number in {csv_file}: {row}")
                    continue

                if phone in seen_phones:
                    print(f"Skipping duplicate phone number: {phone}")
                    continue

                seen_phones.add(phone)
                leads.append({"field_0": phone, "field_1": name})

    return leads


def call_api(method, url, payload=None):
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method=method)

    try:
        with request.urlopen(req, timeout=60) as response:
            text = response.read().decode("utf-8", errors="ignore")
            return response.status, text
    except error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {text}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Request failed: {exc}") from exc


def find_or_create_lead_list_id():
    status, body = call_api("GET", f"{BASE_URL}/v1/broadcast/lists")
    print(f"List lookup status: {status}")

    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON from lead list API: {body}") from exc

    items = payload
    if isinstance(payload, dict):
        for key in ("data", "lists", "result", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                items = value
                break
        else:
            items = []

    if not isinstance(items, list):
        raise RuntimeError(f"Unexpected lead list response format: {payload}")

    for item in items:
        if isinstance(item, dict) and (
            item.get("name") == LEAD_LIST_NAME
            or item.get("list_name") == LEAD_LIST_NAME
        ):
            return item.get("id") or item.get("list_id") or item.get("lead_list_id")

    create_payload = {
        "name": LEAD_LIST_NAME,
        "description": f"Auto-created lead list for {LEAD_LIST_NAME}",
        "field": ["Name", "Phone"],
        "enable_outbound_based_skill": "0",
    }
    status, body = call_api("POST", f"{BASE_URL}/v1/broadcast/list", create_payload)
    print(f"Create list status: {status}")
    print(f"Create list response: {body}")

    try:
        create_result = json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON from create list API: {body}") from exc

    if isinstance(create_result, dict):
        for key in ("id", "list_id", "lead_list_id"):
            value = create_result.get(key)
            if value:
                return value

    raise RuntimeError(
        f"Lead list '{LEAD_LIST_NAME}' could not be created; response: {body}"
    )


def upload_leads(leads):
    lead_list_id = find_or_create_lead_list_id()
    print(f"Found lead list id: {lead_list_id}")

    total = len(leads)
    for start in range(0, total, BATCH_SIZE):
        batch = leads[start : start + BATCH_SIZE]
        payload = {"data": batch, "duplicate_option": "skip"}
        status, body = call_api(
            "POST", f"{BASE_URL}/v1/broadcast/leads/{lead_list_id}", payload
        )
        print(f"Batch {start // BATCH_SIZE + 1}: status={status}, response={body}")

    print(f"Uploaded {total} leads to lead list '{LEAD_LIST_NAME}'")


def main():
    if (
        API_TOKEN
        == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4MDY4NzIiLCJjciI6ZmFsc2UsImlzcyI6Imh0dHA6Ly9jbG91ZHBob25lLnRhdGF0ZWxlc2VydmljZXMuY29tL2Nvbm5lY3QvYXBpL3YxL2FwaS10b2tlbiIsImlhdCI6MTc4NzEzOTIzMCwibmJmIjoxNzg3MTM5MjMwLCJleHAiOjE3OTQ5MTUyMzAsImp0aSI6ImVVcExKR0JhVGpRbmFqbE0ifQ.pQ1uDJVkVVToOAmQVIsR1fsf1WMewkqPFnPSkw7pL5g"
    ):
        raise SystemExit(
            "Please replace API_TOKEN in the script with your real Smartflo token."
        )

    leads = load_leads(INPUT_PATH)
    if not leads:
        raise SystemExit(f"No leads were found in the input path: {INPUT_PATH}")

    upload_leads(leads)


if __name__ == "__main__":
    main()
