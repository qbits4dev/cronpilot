#!/usr/bin/env python3
"""Deduplicate and validate mobile numbers (India by default).

Outputs:
- numbers_normalized.csv  (e164, source_raw)
- numbers_invalid.csv     (raw, reason)
- summary.json            (counts)

Usage:
  python dedupe_validate.py --input consolidated_mobile_numbers.csv
  python dedupe_validate.py --scan-dir "mobile numbers"
"""
import argparse
import csv
import json
import os
from pathlib import Path
from typing import Iterable

import pandas as pd
import phonenumbers
from phonenumbers import NumberParseException


def read_numbers_from_file(path: Path) -> Iterable[str]:
    # Try to read CSV/TSV first, fallback to lines
    try:
        df = pd.read_csv(path, dtype=str, engine="python")
        # detect a likely phone column by header name
        cols = [c for c in df.columns]
        phone_col = None
        for c in cols:
            lc = str(c).lower()
            if "mob" in lc or "phone" in lc or "number" in lc:
                phone_col = c
                break
        if phone_col is None:
            # fallback: pick first column that looks numeric in sample
            for c in cols:
                sample = df[c].dropna().astype(str).str.strip().head(20)
                # count how many sample rows contain digits
                digit_counts = sample.str.replace(r'\D', '', regex=True).str.len()
                if len(digit_counts) > 0 and digit_counts.mean() >= 7:
                    phone_col = c
                    break
        if phone_col is None:
            phone_col = cols[0]
        for v in df[phone_col].astype(str).fillna(""):
            yield v
        return
    except Exception:
        pass
    # fallback plain lines
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                yield line.strip()
    except Exception:
        return


def gather_inputs(inputs, scan_dir: Path):
    seen = set()
    for p in inputs:
        p = Path(p)
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in p.rglob("*.csv"):
                yield f
    if scan_dir and scan_dir.exists():
        for f in scan_dir.rglob("*.csv"):
            yield f


def to_e164(raw: str, region: str = "IN"):
    raw = str(raw).strip()
    if not raw:
        return None, "empty"
    try:
        num = phonenumbers.parse(raw, region)
    except NumberParseException as e:
        # try a digit-only fallback (common in dirty CSVs)
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) == 10 and digits[0] in "6789":
            return "+91" + digits, "assumed_in_10d"
        return None, f"parse_error: {e}"
    if not phonenumbers.is_possible_number(num):
        return None, "not_possible"
    if not phonenumbers.is_valid_number(num):
        # still return E164 if parseable but not valid
        # try digit-only fallback too
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) == 10 and digits[0] in "6789":
            return "+91" + digits, "assumed_in_10d"
        return None, "not_valid"
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164), "valid"


def main():
    parser = argparse.ArgumentParser(description="Deduplicate and validate mobile numbers (India default)")
    parser.add_argument("--input", "-i", nargs="*", help="Input file(s) or directories", default=["consolidated_mobile_numbers.csv"]) 
    parser.add_argument("--scan-dir", "-s", help="Also scan this directory for CSVs", default="mobile numbers")
    parser.add_argument("--region", "-r", help="Default region for parsing", default="IN")
    parser.add_argument("--out-normal", help="Output normalized CSV", default="numbers_normalized.csv")
    parser.add_argument("--out-invalid", help="Output invalid CSV", default="numbers_invalid.csv")
    parser.add_argument("--summary", help="Output summary JSON", default="summary.json")
    args = parser.parse_args()

    files = list(gather_inputs(args.input, Path(args.scan_dir)))
    if not files:
        print("No input files found.")
        return

    raw_rows = []
    for f in files:
        for v in read_numbers_from_file(f):
            if v is None:
                continue
            s = str(v).strip()
            if s:
                raw_rows.append((str(f), s))

    df = pd.DataFrame(raw_rows, columns=["source", "raw"])
    df["raw"] = df["raw"].astype(str).str.strip()
    before = len(df)
    df = df.drop_duplicates(subset=["raw"]).reset_index(drop=True)
    after_dedupe = len(df)

    results = []
    invalids = []
    for _, row in df.iterrows():
        raw = row["raw"]
        e164, reason = to_e164(raw, args.region)
        if e164:
            results.append({"e164": e164, "raw": raw, "source": row["source"]})
        else:
            invalids.append({"raw": raw, "reason": reason, "source": row["source"]})

    df_valid = pd.DataFrame(results)
    df_invalid = pd.DataFrame(invalids)

    df_valid.to_csv(args.out_normal, index=False)
    df_invalid.to_csv(args.out_invalid, index=False)

    summary = {
        "input_files": [str(p) for p in files],
        "rows_before": before,
        "rows_after_dedupe": after_dedupe,
        "valid_count": len(df_valid),
        "invalid_count": len(df_invalid),
    }
    with open(args.summary, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
