#!/usr/bin/env python3
import csv
import re
from collections import defaultdict


def normalize_header(h):
    if h is None:
        return ""
    s = str(h).strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    s = re.sub(r"_+", "_", s)
    return s


def find_key(norm_keys, patterns):
    for p in patterns:
        if p in norm_keys:
            return p
    for p in patterns:
        for k in norm_keys:
            if p in k:
                return k
    return None


def to_seconds(v):
    if v is None or v == "":
        return None
    s = str(v).strip()
    if ":" in s:
        parts = s.split(":")
        try:
            parts = [float(p) for p in parts if p != ""]
            seconds = 0
            for p in parts:
                seconds = seconds * 60 + p
            return int(seconds)
        except Exception:
            return None
    cleaned = re.sub(r"[^\d\.\-]", "", s)
    try:
        return int(float(cleaned))
    except Exception:
        return None


def analyze(infile, outfile, min_suspect_calls=3, top_n=200, suspect_threshold=5):
    """Simplified analysis: only `call_duration` is used to flag suspect calls.

    Any call with duration < `suspect_threshold` seconds is counted as suspect.
    """
    stats = defaultdict(lambda: {"total": 0, "suspect": 0, "examples": []})

    with open(infile, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            print("Empty CSV")
            return

        normed = [normalize_header(h) for h in header]
        norm_keys = set(normed)
        mapping = {normed[i]: i for i in range(len(normed))}

        client_candidates = [
            "client_number",
            "clientnumber",
            "client",
            "destination_number",
            "destination",
            "to",
            "to_number",
            "phone",
            "number",
            "msisdn",
        ]
        call_duration_candidates = [
            "call_duration",
            "duration",
            "callduration",
            "call_time",
            "calltime",
            "calllength",
        ]

        client_key = find_key(norm_keys, client_candidates)
        call_duration_key = find_key(norm_keys, call_duration_candidates)

        if client_key is None:
            print("Could not locate client/called number column in CSV headers.")
            print("Available headers:", ",".join(normed))
            return

        if call_duration_key is None:
            print("Could not locate call duration column in CSV headers.")
            print("Available headers:", ",".join(normed))
            return

        def get_by_key(row, key):
            if key is None:
                return ""
            idx = mapping.get(key)
            if idx is None or idx >= len(row):
                return ""
            return row[idx].strip()

        for row in reader:
            client = get_by_key(row, client_key)
            if not client:
                continue
            client = client.replace(" ", "")
            stats[client]["total"] += 1

            cd = to_seconds(get_by_key(row, call_duration_key))

            if cd is not None and cd < suspect_threshold:
                stats[client]["suspect"] += 1
                if len(stats[client]["examples"]) < 5:
                    stats[client]["examples"].append(cd)

    rows = []
    for client, v in stats.items():
        total = v["total"]
        suspect = v["suspect"]
        pct = suspect / total if total else 0
        rows.append((client, total, suspect, pct, v["examples"]))

    rows.sort(key=lambda x: (x[2], x[3], x[1]), reverse=True)

    if min_suspect_calls:
        rows = [r for r in rows if r[2] >= min_suspect_calls]

    with open(outfile, "w", newline="", encoding="utf-8") as fo:
        w = csv.writer(fo)
        w.writerow(
            [
                "client_number",
                "total_calls",
                "suspect_calls",
                "suspect_percent",
                "example_count",
                "example_call_durations",
            ]
        )
        for client, total, suspect, pct, examples in rows:
            durations_str = "|".join(str(d) for d in examples)
            w.writerow(
                [client, total, suspect, f"{pct:.3f}", len(examples), durations_str]
            )

    print(f"Wrote {len(rows)} client rows to {outfile}")
    print(
        "Top suspected numbers (client_number, total_calls, suspect_calls, suspect_percent):"
    )
    for client, total, suspect, pct, examples in rows[:top_n]:
        print(f"{client},{total},{suspect},{pct:.3f}")

    try:
        txt_out = outfile.replace(".csv", "_list.txt")
        with open(txt_out, "w", encoding="utf-8") as ft:
            for client, total, suspect, pct, examples in rows:
                durations_str = "|".join(str(d) for d in examples)
                ft.write(f"{client},{total},{suspect},{pct:.3f},{durations_str}\n")
        print(f"Wrote text list to {txt_out}")
    except Exception:
        pass


if __name__ == "__main__":
    INPUT = "call_records.csv"
    OUTPUT = "suspected_truecaller_blocked_numbers.csv"
    # show clients with at least one short call by default
    MIN_SUSPECT_CALLS = 1
    TOP_N = 200
    analyze(INPUT, OUTPUT, MIN_SUSPECT_CALLS, TOP_N)
