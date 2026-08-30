from pathlib import Path
import pandas as pd
import csv

SRC = Path(r"d:\work\data\consolidated_mobile_numbers.csv")
DST = Path(r"d:\work\data\contacts.csv")

def is_missing(name: str) -> bool:
    if pd.isna(name):
        return True
    s = str(name).strip()
    return s == "" or s.lower() == "nan"

def name_contains_phone(name: str, phone: str) -> bool:
    if pd.isna(name) or pd.isna(phone):
        return False
    try:
        return str(phone).strip() in str(name)
    except Exception:
        return False

def normalize_phone(p: str) -> str:
    return str(p).strip()

def main():
    if not SRC.exists():
        print(f"Source not found: {SRC}")
        return

    df = pd.read_csv(SRC, dtype=str)

    # ensure columns exist
    if 'name' not in df.columns or ('mobile' not in df.columns and 'phone' not in df.columns):
        print('Expected columns "name" and "mobile"/"phone" not found')
        return

    phone_col = 'mobile' if 'mobile' in df.columns else 'phone'

    # Determine mask for missing names (empty, nan, or 'nana')
    name_series = df['name'] if 'name' in df.columns else pd.Series([pd.NA] * len(df))
    missing_mask = name_series.isna() | name_series.astype(str).str.strip().str.lower().isin(['', 'nan', 'nana'])

    # Prepare first name series
    first_names = name_series.astype(str).str.strip()

    # For rows where name contains the phone, use data<phone>
    # elementwise check: whether phone substring appears in name for each row
    contains_phone_mask = df.apply(lambda r: str(r.get('phone' if phone_col=='phone' else 'mobile') or r.get(phone_col,'')).strip() in str(r.get('name') or ''), axis=1)
    # Apply contains-phone replacement
    first_names[contains_phone_mask] = df.loc[contains_phone_mask, phone_col].astype(str).apply(lambda p: f"data{str(p).strip()}")

    # For missing names, assign sequential data<int> values in order of appearance
    missing_indices = list(df[missing_mask].index)
    for i, idx in enumerate(missing_indices, start=1):
        first_names.at[idx] = f"data{i}"

    # For any still-missing (shouldn't be), fallback to phone
    first_names = first_names.fillna(df[phone_col].astype(str).str.strip())

    out = pd.DataFrame()
    out['First Name'] = first_names
    out['Labels'] = 'data'
    out['Phone 1 - Label'] = 'Mobile'
    out['Phone 1 - Value'] = df[phone_col].astype(str).str.strip()

    # Split output into files of `chunk_size` rows each
    chunk_size = 24950
    total = len(out)
    parts = (total + chunk_size - 1) // chunk_size
    base_stem = DST.stem
    suffix = DST.suffix
    out_dir = DST.parent

    for part in range(1, parts + 1):
        start = (part - 1) * chunk_size
        end = min(start + chunk_size, total)
        chunk = out.iloc[start:end]
        outfile = out_dir / f"{base_stem}_part{part}{suffix}"
        chunk.to_csv(outfile, index=False)

    print(f"Wrote {parts} files {base_stem}_part1{suffix}..{base_stem}_part{parts}{suffix} in {out_dir}")

if __name__ == '__main__':
    main()
