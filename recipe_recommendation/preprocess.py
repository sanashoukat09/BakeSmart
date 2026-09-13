"""
Preprocessing Pipeline for Food.com Recipes Dataset
BakeSmart FYP - Recipe Recommendation Module

Usage:
    uv run --with pyarrow,pandas python recipe_recommendation/preprocess.py
    # Or with options:
    uv run --with pyarrow,pandas python recipe_recommendation/preprocess.py --sample 10000
    uv run --with pyarrow,pandas python recipe_recommendation/preprocess.py --baking-only
"""

import os
import sys
import time
import argparse
import pandas as pd
import pyarrow.csv as pv
import pyarrow.parquet as pq

# Import local preprocessing helpers
from utils import (
    parse_r_vector,
    clean_text,
    pair_ingredients_and_quantities,
    normalize_ingredients_list,
    normalize_keywords_list,
    parse_iso_duration,
    extract_primary_image,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'foodcom')
INPUT_RECIPES_CSV = os.path.join(DATA_DIR, 'recipes.csv')
OUTPUT_CLEANED_PARQUET = os.path.join(DATA_DIR, 'cleaned_recipes.parquet')
OUTPUT_CLEANED_CSV = os.path.join(DATA_DIR, 'cleaned_recipes.csv')
OUTPUT_BAKING_1000_PARQUET = os.path.join(DATA_DIR, 'cleaned_recipes_baking_1000.parquet')
OUTPUT_BAKING_1000_CSV = os.path.join(DATA_DIR, 'cleaned_recipes_baking_1000.csv')

# Baking / Bakery relevant categories for BakeSmart
BAKING_CATEGORIES = {
    'dessert', 'breads', 'quick breads', 'pie', 'bar cookie', 'drop cookies',
    'cheesecake', 'yeast breads', 'cakes', 'cookies and brownies', 'sweet breads',
    'baking', 'rolls/biscuits', 'tarts', 'muffins', 'scones', 'pastries',
    'doughnuts', 'crusts', 'frostings/icings'
}


def load_dataset(input_path: str, sample_size: int = None) -> pd.DataFrame:
    """
    Loads recipes dataset efficiently using PyArrow.
    """
    print(f"\n[1/6] Loading Food.com recipes from: {input_path}")
    t0 = time.time()
    
    parse_opts = pv.ParseOptions(newlines_in_values=True)
    convert_opts = pv.ConvertOptions(null_values=["", "NA", "nan", "NaN", "character(0)", "NULL", "null"])
    
    table = pv.read_csv(input_path, parse_options=parse_opts, convert_options=convert_opts)
    
    # Columns to keep from raw dataset (strictly exclude AuthorId, AuthorName)
    selected_raw_columns = [
        'RecipeId', 'Name', 'CookTime', 'PrepTime', 'TotalTime',
        'Description', 'Images', 'RecipeCategory', 'Keywords',
        'RecipeIngredientParts', 'RecipeIngredientQuantities',
        'AggregatedRating', 'ReviewCount',
        'Calories', 'RecipeServings', 'RecipeInstructions'
    ]
    
    # Ensure all selected columns exist
    cols_to_extract = [c for c in selected_raw_columns if c in table.column_names]
    table = table.select(cols_to_extract)
    
    df = table.to_pandas()
    if sample_size and sample_size > 0:
        df = df.head(sample_size).copy()
        
    print(f"      Loaded {len(df):,} recipes in {time.time() - t0:.2f}s")
    return df


def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and imputes missing values.
    """
    print(f"[2/6] Handling missing values (Initial rows: {len(df):,})")
    
    # 1. Drop rows missing essential recipe identifiers
    initial_len = len(df)
    df = df[df['Name'].notna() & (df['Name'].str.strip() != '')].copy()
    
    # 2. Drop recipes with no ingredient parts (cannot compute similarity without ingredients)
    df = df[df['RecipeIngredientParts'].notna() & 
            (df['RecipeIngredientParts'] != 'character(0)') & 
            (df['RecipeIngredientParts'].str.strip() != '')].copy()
    
    dropped = initial_len - len(df)
    print(f"      Dropped {dropped:,} invalid/missing-ingredient rows. Remaining: {len(df):,}")
    
    # 3. Fill non-critical missing values
    df['RecipeCategory'] = df['RecipeCategory'].fillna('Other')
    df['Description'] = df['Description'].fillna('')
    df['Keywords'] = df['Keywords'].fillna('character(0)')
    df['Images'] = df['Images'].fillna('character(0)')
    df['RecipeInstructions'] = df['RecipeInstructions'].fillna('character(0)')
    
    # Numerical fillings
    df['AggregatedRating'] = df['AggregatedRating'].fillna(0.0)
    df['ReviewCount'] = df['ReviewCount'].fillna(0).astype(int)
    df['Calories'] = df['Calories'].fillna(0.0)
    df['RecipeServings'] = df['RecipeServings'].fillna(1).astype(int)
    
    return df


def clean_and_normalize(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans recipe text fields and parses R-vectors into Python lists.
    """
    print(f"[3/6] Cleaning names, categories, and parsing lists...")
    t0 = time.time()
    
    # Fast vectorized/list-comprehension processing
    df['Name'] = [clean_text(x) for x in df['Name'].tolist()]
    df['RecipeCategory'] = [clean_text(x) for x in df['RecipeCategory'].tolist()]
    df['Description'] = [clean_text(x) for x in df['Description'].tolist()]
    
    # Parse durations to minutes (default to 0 for no-cook/instant recipes)
    df['cook_time_mins'] = [parse_iso_duration(x) or 0 for x in df['CookTime'].tolist()]
    df['prep_time_mins'] = [parse_iso_duration(x) or 0 for x in df['PrepTime'].tolist()]
    df['total_time_mins'] = [parse_iso_duration(x) or 0 for x in df['TotalTime'].tolist()]
    
    # Parse R-vector lists
    print("      Parsing R-vector columns (Ingredients, Quantities, Keywords, Instructions, Images)...")
    df['ingredients_raw'] = [parse_r_vector(x) for x in df['RecipeIngredientParts'].tolist()]
    df['quantities_raw'] = [parse_r_vector(x) if 'RecipeIngredientQuantities' in df.columns else [] for x in df['RecipeIngredientQuantities'].tolist()]
    df['keywords_raw'] = [parse_r_vector(x) for x in df['Keywords'].tolist()]
    df['instructions_list'] = [[clean_text(s) for s in parse_r_vector(x) if clean_text(s)] for x in df['RecipeInstructions'].tolist()]
    df['image_url'] = [extract_primary_image(x) for x in df['Images'].tolist()]
    
    # Pair ingredients with their quantities using smart culinary units
    df['ingredients_with_quantities'] = [
        pair_ingredients_and_quantities(parts, quants, ' '.join(instrs))
        for parts, quants, instrs in zip(df['ingredients_raw'].tolist(), df['quantities_raw'].tolist(), df['instructions_list'].tolist())
    ]
    
    # Drop recipes that ended up with 0 parsed ingredients
    df = df[[len(x) > 0 for x in df['ingredients_raw']]].copy()
    
    print(f"      Cleaned and parsed in {time.time() - t0:.2f}s")
    return df


def engineer_similarity_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transforms ingredients and keywords into normalized tokens and a combined
    'soup' (content feature string) suitable for similarity algorithms (TF-IDF, Embeddings).
    """
    print(f"[4/6] Converting ingredients & tags into similarity features...")
    t0 = time.time()
    
    # Normalize ingredients: e.g. ["all-purpose flour", "brown sugar"] -> ["all_purpose_flour", "brown_sugar"]
    df['ingredients_normalized'] = [normalize_ingredients_list(x) for x in df['ingredients_raw'].tolist()]
    df['ingredients_text'] = [' '.join(x) for x in df['ingredients_normalized'].tolist()]
    
    # Normalize tags/keywords
    df['keywords_normalized'] = [normalize_keywords_list(x) for x in df['keywords_raw'].tolist()]
    df['keywords_text'] = [' '.join(x) for x in df['keywords_normalized'].tolist()]
    
    # Create the Content Feature 'soup' for similarity computation
    # Formula: Name (doubled for weight) + Category + Keywords + Normalized Ingredients
    names = [clean_text(x).lower() for x in df['Name'].tolist()]
    categories = [clean_text(x).lower().replace(' ', '_') for x in df['RecipeCategory'].tolist()]
    kws = df['keywords_text'].tolist()
    ings = df['ingredients_text'].tolist()
    
    df['similarity_soup'] = [f"{n} {n} {c} {k} {i}" for n, c, k, i in zip(names, categories, kws, ings)]
    
    print(f"      Feature engineering completed in {time.time() - t0:.2f}s")
    return df


def filter_top_baking_recipes(df: pd.DataFrame, limit: int = 1000) -> pd.DataFrame:
    """
    Curates the top N highest-quality recipes strictly focused on baking
    (Cakes, Cookies, Breads, Pies, Pastries, Muffins, Scones, etc.)
    with complete ingredients and multi-step instructions.
    """
    print(f"[*] Selecting top {limit:,} premier baking recipes...")
    t0 = time.time()
    
    baking_title_keywords = {
        'cake', 'cookie', 'bread', 'muffin', 'pie', 'brownie', 'tart', 'pastry',
        'scone', 'biscuit', 'doughnut', 'cupcake', 'cheesecake', 'crust',
        'cinnamon roll', 'cobbler', 'crisp', 'strudel', 'danish', 'croissant', 'fudge'
    }
    
    cat_mask = df['RecipeCategory'].str.lower().isin(BAKING_CATEGORIES)
    title_mask = df['Name'].str.lower().apply(lambda name: any(kw in name for kw in baking_title_keywords))
    baking_mask = cat_mask | title_mask
    df_baking = df[baking_mask].copy()
    
    # Exclude savory meat dishes that accidentally matched categories
    non_baking_terms = ['meatloaf', 'meat loaf', 'chicken', 'pork', 'beef', 'salmon', 'tuna', 'turkey', 'pasta', 'casserole', 'stew', 'soup', 'chili', 'burger']
    df_baking = df_baking[~df_baking['Name'].str.lower().apply(lambda name: any(term in name for term in non_baking_terms))].copy()
    
    # Quality filters: Must have at least 2 instruction steps and at least 3 ingredients
    df_baking = df_baking[df_baking['instructions_list'].apply(lambda x: len(x) >= 2 if x is not None else False)].copy()
    df_baking = df_baking[df_baking['ingredients_normalized'].apply(lambda x: len(x) >= 3 if x is not None else False)].copy()
    
    # Bayesian weighted rating shrinkage
    v = df_baking['ReviewCount'].to_numpy(dtype=float)
    R = df_baking['AggregatedRating'].to_numpy(dtype=float)
    bayesian_score = (v / (v + 5.0)) * R + (5.0 / (v + 5.0)) * 4.0
    df_baking['bayesian_temp'] = bayesian_score
    
    # Sort by quality and review popularity
    df_sorted = df_baking.sort_values(by=['bayesian_temp', 'ReviewCount', 'AggregatedRating'], ascending=[False, False, False])
    
    top_df = df_sorted.head(limit).drop(columns=['bayesian_temp']).copy()
    print(f"      Selected {len(top_df):,} baking recipes in {time.time() - t0:.2f}s")
    return top_df


def select_and_reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Selects final clean columns and drops unnecessary raw strings.
    AuthorId and AuthorName are strictly excluded.
    """
    print(f"[5/6] Finalizing column schema...")
    final_cols = [
        'RecipeId',
        'Name',
        'RecipeCategory',
        'Description',
        'image_url',
        'AggregatedRating',
        'ReviewCount',
        'Calories',
        'RecipeServings',
        'prep_time_mins',
        'cook_time_mins',
        'total_time_mins',
        'ingredients_normalized',
        'ingredients_text',
        'ingredients_with_quantities',
        'keywords_normalized',
        'keywords_text',
        'instructions_list',
        'similarity_soup'
    ]
    
    df_clean = df[final_cols].copy()
    return df_clean


def save_cleaned_dataset(
    df: pd.DataFrame,
    output_parquet: str = OUTPUT_CLEANED_PARQUET,
    output_csv: str = OUTPUT_CLEANED_CSV,
    save_csv: bool = True
):
    """
    Saves the cleaned dataset to parquet and optionally CSV,
    keeping original datasets untouched.
    """
    print(f"[6/6] Saving cleaned dataset...")
    t0 = time.time()
    
    # 1. Save Parquet (Preserves list structures, highly compressed and fast)
    df.to_parquet(output_parquet, index=False, engine='pyarrow')
    parquet_size_mb = os.path.getsize(output_parquet) / (1024 * 1024)
    print(f"      [OK] Saved Parquet: {output_parquet} ({parquet_size_mb:.2f} MB)")
    
    # 2. Save CSV (Converts lists to comma/pipe separated strings for CSV compatibility)
    if save_csv:
        df_csv = df.copy()
        df_csv['ingredients_normalized'] = df_csv['ingredients_normalized'].apply(lambda x: '|'.join(x) if isinstance(x, list) else '')
        df_csv['ingredients_with_quantities'] = df_csv['ingredients_with_quantities'].apply(lambda x: ' | '.join(x) if isinstance(x, list) else '')
        df_csv['keywords_normalized'] = df_csv['keywords_normalized'].apply(lambda x: '|'.join(x) if isinstance(x, list) else '')
        df_csv['instructions_list'] = df_csv['instructions_list'].apply(lambda x: ' \\n '.join(x) if isinstance(x, list) else '')
        df_csv.to_csv(output_csv, index=False)
        csv_size_mb = os.path.getsize(output_csv) / (1024 * 1024)
        print(f"      [OK] Saved CSV:     {output_csv} ({csv_size_mb:.2f} MB)")
        
    print(f"      Saved cleaned data in {time.time() - t0:.2f}s")


def main():
    parser = argparse.ArgumentParser(description="Food.com Recipe Preprocessing Pipeline for BakeSmart")
    parser.add_argument('--input', type=str, default=INPUT_RECIPES_CSV, help='Path to raw recipes.csv')
    parser.add_argument('--sample', type=int, default=None, help='Sample N rows for fast verification')
    parser.add_argument('--baking-1000', action='store_true', default=True, help='Curate top 1,000 premier baking recipes')
    parser.add_argument('--all-recipes', action='store_true', help='Process all 520k recipes without 1000 baking limit')
    parser.add_argument('--no-csv', action='store_true', help='Skip CSV output (save only parquet)')
    args = parser.parse_args()
    
    print("=" * 75)
    print("      BakeSmart FYP - Recipe Preprocessing Pipeline Starting      ")
    print("=" * 75)
    total_start = time.time()
    
    # Execute Pipeline
    df = load_dataset(args.input, sample_size=args.sample)
    df = handle_missing_values(df)
    df = clean_and_normalize(df)
    df = engineer_similarity_features(df)
    
    if args.baking_1000 and not args.all_recipes:
        df = filter_top_baking_recipes(df, limit=1000)
        df_final = select_and_reorder_columns(df)
        save_cleaned_dataset(
            df_final,
            output_parquet=OUTPUT_BAKING_1000_PARQUET,
            output_csv=OUTPUT_BAKING_1000_CSV,
            save_csv=not args.no_csv
        )
    else:
        df_final = select_and_reorder_columns(df)
        save_cleaned_dataset(
            df_final,
            output_parquet=OUTPUT_CLEANED_PARQUET,
            output_csv=OUTPUT_CLEANED_CSV,
            save_csv=not args.no_csv
        )
    
    print("\n" + "=" * 75)
    print(f"  PREPROCESSING COMPLETED SUCCESSFULLY in {time.time() - total_start:.2f}s")
    print(f"  Cleaned Recipes Count: {len(df_final):,}")
    print(f"  Columns ({len(df_final.columns)}): {list(df_final.columns)}")
    print("=" * 75 + "\n")


if __name__ == '__main__':
    main()
