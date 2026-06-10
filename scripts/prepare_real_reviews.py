#!/usr/bin/env python
"""Prepare external review CSVs for the ecommerce-review-agent pipeline.

Usage:
    python scripts/prepare_real_reviews.py --input external_reviews.csv --output data/real_reviews_sample.csv

Features:
- Standardises field names via alias mapping.
- Validates and cleans review_text (empty rows dropped).
- Validates rating (non-1..5 rows dropped with warning).
- Outputs a clean CSV ready for scripts/run_batch.py.

"""
import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Optional

# ── Field alias map — input name → canonical name ────────────────────────────

FIELD_ALIASES: dict[str, str] = {
    # review_id
    "id": "review_id",
    "review_id": "review_id",
    "reviewid": "review_id",
    "reviewId": "review_id",
    # platform
    "platform": "platform",
    "source": "platform",
    "marketplace": "platform",
    # product_name
    "product_name": "product_name",
    "product": "product_name",
    "title": "product_name",
    "item_name": "product_name",
    # rating
    "rating": "rating",
    "stars": "rating",
    "score": "rating",
    # review_text
    "review_text": "review_text",
    "review": "review_text",
    "text": "review_text",
    "content": "review_text",
    "body": "review_text",
    # country
    "country": "country",
    "region": "country",
    "marketplace_country": "country",
    # created_at
    "created_at": "created_at",
    "date": "created_at",
    "review_date": "created_at",
}

CANONICAL_FIELDS = [
    "review_id",
    "platform",
    "product_name",
    "rating",
    "review_text",
    "country",
    "created_at",
]

DEFAULT_VALUES: dict[str, str] = {
    "platform": "Amazon",
    "product_name": "Unknown Product",
    "country": "Unknown",
    "created_at": "",
}


def build_field_map(header: list[str]) -> dict[str, str]:
    """Map each column in the input header to a canonical field name."""
    mapping: dict[str, str] = {}
    unmapped: list[str] = []
    for col in header:
        col_stripped = col.strip()
        canonical = FIELD_ALIASES.get(col_stripped)
        if canonical:
            mapping[col_stripped] = canonical
        else:
            unmapped.append(col_stripped)
    if unmapped:
        print(f"⚠️  Unrecognised columns (will be ignored): {', '.join(unmapped)}")
    return mapping


def parse_rating(raw: str, row_idx: int) -> Optional[int]:
    """Parse a rating value, returning None if invalid."""
    try:
        val = int(float(str(raw).strip()))
    except (ValueError, TypeError):
        return None
    if 1 <= val <= 5:
        return val
    return None


def clean_review_text(raw: str) -> Optional[str]:
    """Return stripped review_text, or None if effectively empty."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    return text


def prepare(
    input_path: str,
    output_path: str,
    force_overwrite: bool = False,
) -> tuple[int, int]:
    """Read raw CSV, clean it, write canonical CSV.

    Returns:
        (rows_written, rows_skipped)
    """
    if os.path.exists(output_path) and not force_overwrite:
        print(f"❌ Output file already exists: {output_path}")
        print("   Use --force to overwrite, or specify a different --output path.")
        sys.exit(1)

    rows_written = 0
    rows_skipped = 0

    with open(input_path, "r", encoding="utf-8") as infile, \
         open(output_path, "w", encoding="utf-8", newline="") as outfile:

        reader = csv.DictReader(infile)
        if reader.fieldnames is None:
            print("❌ Input CSV has no header row.")
            sys.exit(1)

        # Build the header mapping
        field_map = build_field_map(list(reader.fieldnames))

        # Check that we have at least review_text
        has_text = any(canonical == "review_text" for canonical in field_map.values())
        if not has_text:
            print("❌ No column mapped to review_text. Check input header.")
            print(f"   Available aliases: review_text, review, text, content, body")
            sys.exit(1)

        writer = csv.DictWriter(outfile, fieldnames=CANONICAL_FIELDS)
        writer.writeheader()

        for idx, row in enumerate(reader, start=2):  # 2 because header is row 1
            # Build canonical row
            canonical: dict[str, str] = dict(DEFAULT_VALUES)
            canonical["review_id"] = ""  # will be auto-generated if missing

            for src_col, src_val in row.items():
                canonical_name = field_map.get(src_col.strip())
                if canonical_name and canonical_name in CANONICAL_FIELDS:
                    canonical[canonical_name] = str(src_val).strip()

            # ── Validate review_text ──────────────────────────────────────
            cleaned_text = clean_review_text(canonical.get("review_text", ""))
            if cleaned_text is None:
                print(f"⚠️  Row {idx}: empty review_text — skipped.")
                rows_skipped += 1
                continue

            # ── Validate rating ───────────────────────────────────────────
            parsed_rating = parse_rating(canonical.get("rating", ""), idx)
            if parsed_rating is None:
                raw_rating = canonical.get("rating", "(missing)")
                print(f"⚠️  Row {idx}: invalid rating '{raw_rating}' — skipped.")
                rows_skipped += 1
                continue

            # ── Auto-generate review_id if missing ────────────────────────
            if not canonical["review_id"]:
                canonical["review_id"] = f"r{rows_written + 1:04d}"

            # ── Write ────────────────────────────────────────────────────
            canonical["review_text"] = cleaned_text
            canonical["rating"] = str(parsed_rating)

            writer.writerow(canonical)
            rows_written += 1

    return rows_written, rows_skipped


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare external review CSV for the ecommerce-review-agent pipeline."
    )
    parser.add_argument("--input", required=True, help="Path to raw input CSV file")
    parser.add_argument("--output", required=True, help="Path for cleaned output CSV")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output file if it already exists",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"❌ Input file not found: {args.input}")
        sys.exit(1)

    print(f"📖 Reading:   {args.input}")
    print(f"📝 Writing:   {args.output}")

    written, skipped = prepare(args.input, args.output, force_overwrite=args.force)

    print()
    print(f"✅ Done.  {written} rows written, {skipped} rows skipped.")
    if skipped > 0:
        print("   Skipped rows had empty review_text or invalid rating.")


if __name__ == "__main__":
    main()
