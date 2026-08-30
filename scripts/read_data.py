from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: pandas. Install with: pip install pandas"
    ) from exc


MOBILE_COL_HINTS = (
    "mobile",
    "mob",
    "phone",
    "contact",
    "number",
    "cell",
)

NAME_COL_HINTS = (
    "name",
    "customer",
    "cust",
    "student",
    "candidate",
    "person",
    "first",
    "last",
)


@dataclass(frozen=True)
class ColumnGuess:
    name_col: Optional[str]
    mobile_col: Optional[str]


def _normalize_col(col: object) -> str:
    text = "" if col is None else str(col)
    text = re.sub(r"\s+", " ", text.strip().lower())
    return text


def _split_possible_numbers(value: object) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return []

    parts = re.split(r"[\n,;/|]+", text)
    out: list[str] = []
    for part in parts:
        part = part.strip()
        if part:
            out.append(part)
    return out


def clean_mobile_number(raw: object, *, country: str = "IN") -> Optional[str]:
    """Return normalized mobile number digits or None if invalid.

    Default rules are tuned for India:
    - keep only digits
    - allow leading 0 (11 digits) or leading 91 (12 digits)
    - final must be 10 digits and start with 6-9
    """

    if raw is None:
        return None
    digits = re.sub(r"\D+", "", str(raw))
    if not digits:
        return None

    if country.upper() == "IN":
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[-10:]
        elif len(digits) == 11 and digits.startswith("0"):
            digits = digits[-10:]

        if len(digits) != 10:
            return None
        if digits[0] not in {"6", "7", "8", "9"}:
            return None
        return digits

    # Generic fallback: accept any 10-digit number
    if len(digits) == 10:
        return digits
    return None


def _guess_columns(df: "pd.DataFrame") -> ColumnGuess:
    normalized = {col: _normalize_col(col) for col in df.columns}

    mobile_candidates = [
        col
        for col, ncol in normalized.items()
        if any(h in ncol for h in MOBILE_COL_HINTS)
    ]
    name_candidates = [
        col
        for col, ncol in normalized.items()
        if any(h in ncol for h in NAME_COL_HINTS)
    ]

    mobile_col = mobile_candidates[0] if mobile_candidates else None
    name_col = name_candidates[0] if name_candidates else None

    # Heuristic fallback: find a column that looks like phone numbers.
    if mobile_col is None and len(df.columns) > 0:
        best_col: Optional[str] = None
        best_score = 0.0
        for col in df.columns:
            series = df[col].astype(str).fillna("")
            sample = series.head(200)
            if sample.empty:
                continue
            cleaned = sample.map(lambda x: re.sub(r"\D+", "", x))
            score = (cleaned.str.len().between(10, 12)).mean()
            if score > best_score:
                best_score = score
                best_col = col
        if best_col is not None and best_score >= 0.25:
            mobile_col = best_col

    return ColumnGuess(name_col=name_col, mobile_col=mobile_col)


def _find_first_last_cols(df: "pd.DataFrame") -> tuple[Optional[str], Optional[str]]:
    normalized = {col: _normalize_col(col) for col in df.columns}
    first_col = None
    last_col = None
    for col, ncol in normalized.items():
        if first_col is None and "first" in ncol:
            first_col = col
        if last_col is None and "last" in ncol:
            last_col = col
    return first_col, last_col


def _make_name_series(df: "pd.DataFrame", guess: ColumnGuess) -> "pd.Series":
    if guess.name_col in df.columns:
        return df[guess.name_col]

    first_col, last_col = _find_first_last_cols(df)
    if first_col in df.columns and last_col in df.columns:
        first = df[first_col].astype(str).fillna("")
        last = df[last_col].astype(str).fillna("")
        combined = (first.str.strip() + " " + last.str.strip()).str.strip()
        combined = combined.where(combined.ne(""), other=None)
        return combined

    if first_col in df.columns:
        first = df[first_col].astype(str).fillna("").str.strip()
        return first.where(first.ne(""), other=None)

    return pd.Series([None] * len(df))


def _read_csv_file(path: Path) -> "pd.DataFrame":
    # Try to auto-detect delimiter; fall back to utf-8-sig and common Windows encodings.
    encodings = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
    last_exc: Optional[Exception] = None
    for enc in encodings:
        try:
            return pd.read_csv(
                path,
                dtype=str,
                sep=None,
                engine="python",
                encoding=enc,
                encoding_errors="replace",
                on_bad_lines="skip",
            )
        except Exception as exc:  # pragma: no cover
            last_exc = exc
            continue

    if last_exc is not None:
        raise last_exc
    return pd.DataFrame()


def load_all_mobile_occurrences(
    base_dir: str | Path,
    *,
    country: str = "IN",
) -> "pd.DataFrame":
    base_path = Path(base_dir)
    if not base_path.exists():
        raise FileNotFoundError(f"Base directory not found: {base_path}")

    csv_files = sorted(base_path.rglob("*.csv"))
    rows: list[dict[str, object]] = []

    for file_path in csv_files:
        try:
            df = _read_csv_file(file_path)
            if df is None or df.empty:
                continue

            guess = _guess_columns(df)
            if guess.mobile_col is None or guess.mobile_col not in df.columns:
                continue

            name_series = _make_name_series(df, guess)
            mobile_series = df[guess.mobile_col]

            temp = pd.DataFrame(
                {
                    "name": name_series,
                    "raw_mobile": mobile_series,
                }
            )
            # Row number: 2-based so it matches how people count rows in files (header is row 1).
            temp["source_row"] = temp.index + 2
            temp["source_file"] = str(file_path.relative_to(base_path))

            temp["raw_mobile"] = temp["raw_mobile"].astype(str)
            temp["_parts"] = temp["raw_mobile"].map(_split_possible_numbers)
            temp = temp.explode("_parts", ignore_index=False)
            temp["mobile"] = temp["_parts"].map(lambda x: clean_mobile_number(x, country=country))
            temp = temp.dropna(subset=["mobile"])

            if not temp.empty:
                temp["name"] = temp["name"].map(lambda x: None if x is None else str(x).strip() or None)
                rows.extend(
                    temp[["name", "mobile", "source_file", "source_row"]].to_dict("records")
                )
        except Exception:
            # Skip unreadable files/sheets but keep processing others.
            continue

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    out["name"] = out["name"].astype("string")
    out["mobile"] = out["mobile"].astype("string")
    out = out.dropna(subset=["mobile"])
    out = out.sort_values(["mobile", "source_file", "source_row"], kind="stable").reset_index(drop=True)
    return out


def build_duplicates_report(occurrences: "pd.DataFrame") -> "pd.DataFrame":
    if occurrences is None or occurrences.empty:
        return pd.DataFrame(columns=["mobile", "source_file", "source_row"])

    dupes = occurrences[occurrences["mobile"].duplicated(keep=False)].copy()
    if dupes.empty:
        return pd.DataFrame(columns=["mobile", "source_file", "source_row"])

    cols = [c for c in ["mobile", "source_file", "source_row"] if c in dupes.columns]
    dupes = dupes[cols].sort_values(["mobile", "source_file", "source_row"], kind="stable")
    dupes = dupes.reset_index(drop=True)
    return dupes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read all .csv under a folder and consolidate valid mobile numbers + names."
    )
    parser.add_argument(
        "--input",
        default="mobile numbers",
        help="Folder containing .csv files (recursively). Default: %(default)s",
    )
    parser.add_argument(
        "--output",
        default="consolidated_mobile_numbers.csv",
        help="Output CSV path. Default: %(default)s",
    )
    parser.add_argument(
        "--duplicates-output",
        default="duplicates.csv",
        help="Duplicates report CSV path. Default: %(default)s",
    )
    parser.add_argument(
        "--country",
        default="IN",
        help="Validation rules country code. Default: %(default)s",
    )
    args = parser.parse_args()

    occ = load_all_mobile_occurrences(args.input, country=args.country)
    dupes = build_duplicates_report(occ)
    unique = occ.drop_duplicates(subset=["mobile"], keep="first") if not occ.empty else occ
    unique = unique.sort_values(["mobile"], kind="stable").reset_index(drop=True)
    unique_out = unique[["name", "mobile"]] if not unique.empty else unique

    out_path = Path(args.output)
    dup_path = Path(args.duplicates_output)
    unique_out.to_csv(out_path, index=False, encoding="utf-8")
    dupes.to_csv(dup_path, index=False, encoding="utf-8")

    print(f"Total valid occurrences: {len(occ)}")
    print(f"Unique mobiles written: {len(unique)}")
    print(f"Duplicate rows written: {len(dupes)}")
    print(f"Output (unique): {out_path.resolve()}")
    print(f"Output (duplicates): {dup_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
