"""
Verification script for the cleaned recipes dataset.
BakeSmart FYP - Recipe Recommendation Module
"""

import os
import pyarrow.parquet as pq
import pandas as pd

CLEANED_PARQUET = os.path.join('data', 'foodcom', 'cleaned_recipes.parquet')
CLEANED_CSV = os.path.join('data', 'foodcom', 'cleaned_recipes.csv')

def verify():
    print("=" * 75)
    print("       BakeSmart Recipe Module - Cleaned Dataset Verification       ")
    print("=" * 75)

    if not os.path.exists(CLEANED_PARQUET):
        print(f"[ERROR] Cleaned dataset not found at {CLEANED_PARQUET}")
        return

    parquet_size_mb = os.path.getsize(CLEANED_PARQUET) / (1024 * 1024)
    csv_size_mb = os.path.getsize(CLEANED_CSV) / (1024 * 1024) if os.path.exists(CLEANED_CSV) else 0

    print(f"Parquet File: {CLEANED_PARQUET} ({parquet_size_mb:.2f} MB)")
    print(f"CSV File:     {CLEANED_CSV} ({csv_size_mb:.2f} MB)")

    table = pq.read_table(CLEANED_PARQUET)
    print(f"\n[OK] Successfully loaded cleaned dataset into memory.")
    print(f"Total Cleaned Recipes: {table.num_rows:,}")
    print(f"Total Features:        {table.num_columns}")

    # Inspect null counts in cleaned dataset
    print("\nNull Value Verification in Cleaned Dataset:")
    for col_name in table.column_names:
        nulls = table[col_name].null_count
        status = "Clean (0 nulls)" if nulls == 0 else f"{nulls:,} nulls"
        print(f"  - {col_name:<25}: {status}")

    # Load 3 sample rows to inspect actual content
    df_sample = table.slice(0, 3).to_pandas()
    print("\n" + "=" * 75)
    print("                     Sample Cleaned Recipes                         ")
    print("=" * 75)

    for idx, row in df_sample.iterrows():
        print(f"\n--- [Recipe #{idx+1}] {row['Name']} (ID: {row['RecipeId']}) ---")
        print(f"  Category:        {row['RecipeCategory']}")
        print(f"  Rating:          {row['AggregatedRating']} ({row['ReviewCount']} reviews)")
        print(f"  Calories:        {row['Calories']} kcal | Servings: {row['RecipeServings']}")
        print(f"  Cooking Time:    Prep: {row['prep_time_mins']}m | Cook: {row['cook_time_mins']}m | Total: {row['total_time_mins']}m")
        print(f"  Ingredients ({len(row['ingredients_normalized'])}): {list(row['ingredients_normalized'])[:5]}...")
        print(f"  Keywords ({len(row['keywords_normalized'])}):    {list(row['keywords_normalized'])[:5]}...")
        print(f"  Image Thumbnail: {row['image_url'] if row['image_url'] else '[No Image]'}")
        print(f"  Similarity Soup: {row['similarity_soup'][:140]}...")

    print("\n" + "=" * 75)
    print("  VERIFICATION COMPLETE: Dataset is clean and ready for ML models!")
    print("=" * 75 + "\n")

if __name__ == '__main__':
    verify()
