"""
Index Builder for BakeSmart Recipe Recommendation Module.
Pre-computes and serializes TF-IDF matrices, inverted ingredient indices, and Bayesian rating priors.

Usage:
    uv run --with pyarrow,pandas,scikit-learn,joblib python recipe_recommendation/build_index.py
    # Or for specialized baking core index:
    uv run --with pyarrow,pandas,scikit-learn,joblib python recipe_recommendation/build_index.py --baking-only
"""

import os
import sys
import time
import argparse
import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.feature_extraction.text import TfidfVectorizer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'foodcom')
INPUT_PARQUET = os.path.join(DATA_DIR, 'cleaned_recipes.parquet')

BAKING_CATEGORIES = {
    'dessert', 'breads', 'quick breads', 'pie', 'bar cookie', 'drop cookies',
    'cheesecake', 'yeast breads', 'cakes', 'cookies and brownies', 'sweet breads',
    'baking', 'rolls/biscuits', 'tarts', 'muffins', 'scones', 'pastries',
    'doughnuts', 'crusts', 'frostings/icings'
}


def compute_bayesian_ratings(df: pd.DataFrame, m: int = 5) -> np.ndarray:
    """
    Computes Bayesian weighted rating (shrinkage prior) for recipe ranking:
    WR = (v / (v + m)) * R + (m / (v + m)) * C
    Where:
        v = ReviewCount
        R = AggregatedRating
        m = minimum threshold reviews
        C = mean dataset rating
    """
    v = df['ReviewCount'].to_numpy(dtype=float)
    R = df['AggregatedRating'].to_numpy(dtype=float)
    
    # Calculate global mean of recipes that have ratings
    rated_mask = v > 0
    C = float(np.mean(R[rated_mask])) if np.any(rated_mask) else 4.0
    
    wr = (v / (v + m)) * R + (m / (v + m)) * C
    return wr


def build_inverted_ingredient_index(df: pd.DataFrame) -> dict:
    """
    Builds an inverted index mapping each normalized ingredient to the list of recipe indices.
    Enables sub-millisecond pantry ingredient search without scanning 500k rows.
    """
    print("[*] Building inverted ingredient index...")
    t0 = time.time()
    inverted = {}
    
    ingredients_series = df['ingredients_normalized'].tolist()
    for row_idx, ing_list in enumerate(ingredients_series):
        if ing_list is None or len(ing_list) == 0:
            continue
        for ing in ing_list:
            if ing not in inverted:
                inverted[ing] = []
            inverted[ing].append(row_idx)
            
    print(f"    Indexed {len(inverted):,} unique ingredients across {len(df):,} recipes in {time.time() - t0:.2f}s")
    return inverted


def build_tfidf_index(df: pd.DataFrame, max_features: int = 30000):
    """
    Fits TF-IDF vectorizer over the engineered 'similarity_soup'.
    """
    print(f"[*] Fitting TF-IDF Vectorizer on similarity soup (max_features={max_features:,})...")
    t0 = time.time()
    
    vectorizer = TfidfVectorizer(
        max_features=max_features,
        sublinear_tf=True,
        ngram_range=(1, 2),
        stop_words='english',
        token_pattern=r'(?u)\b\w+\b'
    )
    
    tfidf_matrix = vectorizer.fit_transform(df['similarity_soup'].tolist())
    print(f"    TF-IDF Matrix shape: {tfidf_matrix.shape} (Built in {time.time() - t0:.2f}s)")
    return vectorizer, tfidf_matrix


def main():
    parser = argparse.ArgumentParser(description="Build indexes for recipe recommendation")
    parser.add_argument('--baking-only', action='store_true', help='Build specialized index for baking/dessert recipes only')
    parser.add_argument('--max-features', type=int, default=30000, help='Maximum TF-IDF features')
    parser.add_argument('--output-prefix', type=str, default=None, help='Custom prefix for index files')
    args = parser.parse_args()
    
    print("=" * 75)
    print("         BakeSmart Recipe Recommendation - Index Builder Starting         ")
    print("=" * 75)
    
    if not os.path.exists(INPUT_PARQUET):
        print(f"[ERROR] Cleaned dataset not found at: {INPUT_PARQUET}")
        print("Please run 'python recipe_recommendation/preprocess.py' first.")
        sys.exit(1)
        
    print(f"[*] Loading cleaned dataset from: {INPUT_PARQUET}")
    t_start = time.time()
    table = pq.read_table(INPUT_PARQUET)
    df = table.to_pandas()
    print(f"    Loaded {len(df):,} recipes in {time.time() - t_start:.2f}s")
    
    suffix = "_baking" if args.baking_only else "_full"
    if args.output_prefix:
        suffix = f"_{args.output_prefix}"
        
    if args.baking_only:
        print("[*] Filtering dataset for baking-specific categories...")
        mask = df['RecipeCategory'].str.lower().isin(BAKING_CATEGORIES)
        df = df[mask].reset_index(drop=True)
        print(f"    Retained {len(df):,} baking recipes")
        
    # 1. Compute Bayesian Quality Ratings
    print("[*] Computing Bayesian quality rating scores...")
    df['bayesian_rating'] = compute_bayesian_ratings(df)
    
    # 2. Build Inverted Ingredient Index
    ingredient_index = build_inverted_ingredient_index(df)
    
    # 3. Build TF-IDF Similarity Index
    vectorizer, tfidf_matrix = build_tfidf_index(df, max_features=args.max_features)
    
    # 4. Save Metadata & Artifacts
    print(f"[*] Serializing recommendation indices (suffix: '{suffix}')...")
    
    tfidf_path = os.path.join(DATA_DIR, f'tfidf_matrix{suffix}.joblib')
    vectorizer_path = os.path.join(DATA_DIR, f'tfidf_vectorizer{suffix}.joblib')
    ing_index_path = os.path.join(DATA_DIR, f'ingredient_index{suffix}.joblib')
    meta_parquet_path = os.path.join(DATA_DIR, f'recipe_metadata{suffix}.parquet')
    
    # Keep lightweight metadata for fast recommendation serving
    meta_cols = [
        'RecipeId', 'Name', 'RecipeCategory', 'Description', 'image_url',
        'AggregatedRating', 'ReviewCount', 'Calories', 'RecipeServings',
        'prep_time_mins', 'cook_time_mins', 'total_time_mins',
        'ingredients_normalized', 'keywords_normalized', 'bayesian_rating'
    ]
    df[meta_cols].to_parquet(meta_parquet_path, index=False, engine='pyarrow')
    
    joblib.dump(tfidf_matrix, tfidf_path, compress=3)
    joblib.dump(vectorizer, vectorizer_path, compress=3)
    joblib.dump(ingredient_index, ing_index_path, compress=3)
    
    print(f"    [OK] Metadata:   {meta_parquet_path} ({os.path.getsize(meta_parquet_path)/(1024*1024):.2f} MB)")
    print(f"    [OK] TF-IDF Mat: {tfidf_path} ({os.path.getsize(tfidf_path)/(1024*1024):.2f} MB)")
    print(f"    [OK] Vectorizer: {vectorizer_path} ({os.path.getsize(vectorizer_path)/(1024*1024):.2f} MB)")
    print(f"    [OK] Ing Index:  {ing_index_path} ({os.path.getsize(ing_index_path)/(1024*1024):.2f} MB)")
    
    print("\n" + "=" * 75)
    print(f"  INDEX BUILDING COMPLETED in {time.time() - t_start:.2f}s")
    print("=" * 75 + "\n")


if __name__ == '__main__':
    main()
