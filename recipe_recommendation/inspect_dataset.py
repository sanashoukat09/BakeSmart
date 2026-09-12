"""
Dataset inspection script for Food.com Recipes & Reviews.
BakeSmart FYP - Recipe Recommendation Module

Usage:
    uv run --with pyarrow,pandas python recipe_recommendation/inspect_dataset.py
"""

import os
import json
import time
import pyarrow.csv as pv
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'foodcom')
RECIPES_PATH = os.path.join(DATA_DIR, 'recipes.csv')
REVIEWS_PATH = os.path.join(DATA_DIR, 'reviews.csv')
SUMMARY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dataset_summary.json')


def inspect_file(filepath: str, name: str) -> dict:
    print(f"\n{'='*75}")
    print(f"  INSPECTING: {name}")
    print(f"  Path: {filepath}")
    print(f"{'='*75}")

    if not os.path.exists(filepath):
        print(f"  [ERROR] File not found: {filepath}")
        return {"error": "File not found"}

    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"  File Size: {file_size_mb:.2f} MB")

    t0 = time.time()
    # Read using PyArrow with multi-line support
    parse_opts = pv.ParseOptions(newlines_in_values=True)
    convert_opts = pv.ConvertOptions(null_values=["", "NA", "nan", "NaN", "character(0)", "NULL", "null"])
    table = pv.read_csv(filepath, parse_options=parse_opts, convert_options=convert_opts)
    load_time = time.time() - t0

    num_rows = table.num_rows
    num_cols = table.num_columns
    print(f"  Rows: {num_rows:,} | Columns: {num_cols} (Loaded in {load_time:.2f}s)")
    print(f"\n  {'Column Name':<30} | {'Data Type':<20} | {'Missing Count':<14} | {'Missing %'}")
    print(f"  {'-'*30}-+-{'-'*20}-+-{'-'*14}-+---------")

    columns_info = {}
    for col_name in table.column_names:
        col = table[col_name]
        null_count = col.null_count
        null_pct = (null_count / num_rows * 100) if num_rows > 0 else 0
        dtype_str = str(col.type)

        columns_info[col_name] = {
            "type": dtype_str,
            "missing_count": null_count,
            "missing_percentage": round(null_pct, 2)
        }
        print(f"  {col_name:<30} | {dtype_str:<20} | {null_count:>14,} | {null_pct:>7.2f}%")

    return {
        "file_name": os.path.basename(filepath),
        "file_size_mb": round(file_size_mb, 2),
        "total_rows": num_rows,
        "total_columns": num_cols,
        "columns": columns_info
    }


def main():
    print("\n===========================================================================")
    print("        BakeSmart Recipe Recommendation - Dataset Inspection Report        ")
    print("===========================================================================")
    print(f"Data Directory: {DATA_DIR}")

    recipes_summary = inspect_file(RECIPES_PATH, "Food.com Recipes Dataset (recipes.csv)")
    reviews_summary = inspect_file(REVIEWS_PATH, "Food.com Reviews Dataset (reviews.csv)")

    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "recipes_dataset": recipes_summary,
        "reviews_dataset": reviews_summary
    }

    with open(SUMMARY_PATH, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    print(f"\n[OK] Inspection summary written to: {SUMMARY_PATH}\n")


if __name__ == '__main__':
    main()
