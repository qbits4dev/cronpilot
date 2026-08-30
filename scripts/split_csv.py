#!/usr/bin/env python3
"""Split a CSV file into smaller files with a fixed number of rows per file."""

import csv
import sys
from pathlib import Path
from typing import Optional


def split_csv(
    input_path: str, output_dir: Optional[str] = None, chunk_size: int = 499999
) -> None:
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    output_folder = (
        Path(output_dir)
        if output_dir
        else input_file.parent / f"{input_file.stem}_split"
    )
    output_folder.mkdir(parents=True, exist_ok=True)

    with input_file.open("r", newline="", encoding="utf-8-sig") as infile:
        reader = csv.DictReader(infile)
        if not reader.fieldnames:
            raise ValueError("Input CSV has no header row")

        chunk_number = 1
        row_count = 0
        writer = None
        dict_writer = None
        output_path = None

        for row in reader:
            if row_count % chunk_size == 0:
                if writer is not None:
                    writer.close()

                output_path = (
                    output_folder / f"{input_file.stem}_{chunk_number:03d}.csv"
                )
                writer = output_path.open("w", newline="", encoding="utf-8")
                dict_writer = csv.DictWriter(writer, fieldnames=reader.fieldnames)
                dict_writer.writeheader()
                chunk_number += 1

            dict_writer.writerow(row)
            row_count += 1

        if writer is not None:
            writer.close()

    print(f"Created {chunk_number - 1} file(s) in {output_folder}")


if __name__ == "__main__":
    input_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "/home/atulitha/projects/data/consolidated_mobile_numbers.csv"
    )
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    split_csv(input_path=input_path, output_dir=output_dir, chunk_size=499999)
