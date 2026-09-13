"""
BakeSmart FYP - Core Recipe Recommendation Engine.
Provides high-performance:
1. Ingredient-based Pantry Matching (suggest recipes based on available bakery ingredients).
2. Content-based "More Like This" Recipe Similarity (TF-IDF + Cosine Similarity).
3. Semantic & Keyword Filtered Search with Dietary and Time Constraints.
"""

import os
import sys
import time
from typing import List, Dict, Any, Optional
import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.metrics.pairwise import cosine_similarity

# Local imports
try:
    from recipe_recommendation.utils import normalize_ingredient, normalize_ingredients_list, clean_text
except ImportError:
    from utils import normalize_ingredient, normalize_ingredients_list, clean_text

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'foodcom')


class RecipeRecommender:
    def __init__(self, index_suffix: str = "_baking_1000", auto_load: bool = True):
        """
        Initializes the RecipeRecommender.
        Default index_suffix: '_baking_1000' (1,000 curated baking recipes)
        Also supports '_full' (520k recipes) or custom suffixes.
        """
        self.index_suffix = index_suffix
        self.meta_path = os.path.join(DATA_DIR, f'recipe_metadata{index_suffix}.parquet')
        self.tfidf_path = os.path.join(DATA_DIR, f'tfidf_matrix{index_suffix}.joblib')
        self.vectorizer_path = os.path.join(DATA_DIR, f'tfidf_vectorizer{index_suffix}.joblib')
        self.ing_index_path = os.path.join(DATA_DIR, f'ingredient_index{index_suffix}.joblib')
        
        self.metadata_df: Optional[pd.DataFrame] = None
        self.tfidf_matrix = None
        self.vectorizer = None
        self.ingredient_index: Optional[Dict[str, List[int]]] = None
        self.id_to_index: Dict[int, int] = {}
        
        if auto_load:
            self.load_index()

    def _format_recipe(self, row: pd.Series, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Formats a recipe record for API/UI delivery.
        Strictly excludes AuthorId, AuthorName, or any author profile metadata.
        """
        quants_list = []
        if 'ingredients_with_quantities' in row and row['ingredients_with_quantities'] is not None:
            quants_list = list(row['ingredients_with_quantities'])
            
        instructions = []
        if 'instructions_list' in row and row['instructions_list'] is not None:
            instructions = list(row['instructions_list'])
            
        sample_ings = []
        if 'ingredients_normalized' in row and row['ingredients_normalized'] is not None:
            sample_ings = [i.replace('_', ' ') for i in list(row['ingredients_normalized'])[:8]]
            
        data = {
            "recipe_id": int(row["RecipeId"]),
            "name": clean_text(str(row["Name"])),
            "category": str(row["RecipeCategory"]),
            "description": clean_text(str(row["Description"])) if pd.notna(row.get("Description")) else "",
            "image_url": str(row["image_url"]) if pd.notna(row.get("image_url")) and row["image_url"] else None,
            "rating": round(float(row["AggregatedRating"]), 1) if pd.notna(row.get("AggregatedRating")) else 0.0,
            "reviews_count": int(row["ReviewCount"]) if pd.notna(row.get("ReviewCount")) else 0,
            "servings": int(row["RecipeServings"]) if pd.notna(row.get("RecipeServings")) else 1,
            "prep_time_mins": int(row["prep_time_mins"]) if pd.notna(row.get("prep_time_mins")) else 0,
            "cook_time_mins": int(row["cook_time_mins"]) if pd.notna(row.get("cook_time_mins")) else 0,
            "total_time_mins": int(row["total_time_mins"]) if pd.notna(row.get("total_time_mins")) else 0,
            "calories": round(float(row["Calories"]), 1) if pd.notna(row.get("Calories")) else 0.0,
            "ingredients_with_quantities": quants_list,
            "instructions_list": instructions,
            "sample_ingredients": sample_ings,
        }
        if extra:
            data.update(extra)
        return data

    def get_recipe_details(self, recipe_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves all details for a single recipe by RecipeId.
        Strictly excludes AuthorId, AuthorName.
        """
        if self.metadata_df is None:
            self.load_index()
            
        idx = self.id_to_index.get(recipe_id)
        if idx is None:
            return None
            
        return self._format_recipe(self.metadata_df.iloc[idx])

    def is_indexed(self) -> bool:
        """Checks if all required index artifacts exist on disk."""
        return (
            os.path.exists(self.meta_path) and
            os.path.exists(self.tfidf_path) and
            os.path.exists(self.vectorizer_path) and
            os.path.exists(self.ing_index_path)
        )

    def load_index(self):
        """Loads serialized indices and metadata into memory."""
        if not self.is_indexed():
            print(f"[*] Indices not found for suffix '{self.index_suffix}'. Building now...")
            self._trigger_build_index()

        t0 = time.time()
        print(f"[*] Loading recommendation indices (suffix: '{self.index_suffix}')...")
        
        table = pq.read_table(self.meta_path)
        self.metadata_df = table.to_pandas()
        self.tfidf_matrix = joblib.load(self.tfidf_path)
        self.vectorizer = joblib.load(self.vectorizer_path)
        self.ingredient_index = joblib.load(self.ing_index_path)
        
        # Build O(1) RecipeId -> Row index mapping
        recipe_ids = self.metadata_df['RecipeId'].tolist()
        self.id_to_index = {rid: idx for idx, rid in enumerate(recipe_ids)}
        
        # Pre-cache columnar arrays for sub-millisecond query evaluation
        self.recipe_ingredients = self.metadata_df['ingredients_normalized'].tolist()
        self.recipe_categories = [str(c).lower() for c in self.metadata_df['RecipeCategory'].tolist()]
        self.recipe_total_times = self.metadata_df['total_time_mins'].to_numpy()
        self.recipe_keywords = [set(kws) if kws is not None else set() for kws in self.metadata_df['keywords_normalized'].tolist()]
        self.recipe_bayesian = self.metadata_df['bayesian_rating'].to_numpy()
        self.recipe_lengths = np.array([len(x) for x in self.recipe_ingredients], dtype=np.int32)
        
        print(f"[OK] Recommender initialized with {len(self.metadata_df):,} recipes in {time.time() - t0:.2f}s")

    def _trigger_build_index(self):
        """Builds index automatically if not yet precomputed."""
        try:
            from recipe_recommendation.build_index import main as run_build
        except ImportError:
            from build_index import main as run_build
            
        baking_flag = self.index_suffix == "_baking"
        sys.argv = ['build_index.py']
        if baking_flag:
            sys.argv.append('--baking-only')
        run_build()

    def recommend_by_ingredients(
        self,
        user_ingredients: List[str],
        top_n: int = 10,
        min_match_ratio: float = 0.25,
        dietary_filters: Optional[List[str]] = None,
        max_time_mins: Optional[int] = None,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Suggests recipes based on a list of ingredients available in the kitchen/pantry.
        
        Parameters:
            user_ingredients: List of raw ingredient names (e.g. ['flour', 'butter', 'sugar', 'cocoa'])
            top_n: Number of suggestions to return
            min_match_ratio: Minimum fraction of recipe ingredients matched
            dietary_filters: Optional list of dietary tags (e.g. ['eggless', 'gluten-free'])
            max_time_mins: Maximum total cooking + prep time in minutes
            category: Optional category filter (e.g. 'Dessert', 'Breads')
        """
        from collections import Counter

        if self.metadata_df is None:
            self.load_index()

        t0 = time.time()
        # 1. Normalize user ingredients
        clean_user_ings = set(normalize_ingredients_list(user_ingredients))
        if not clean_user_ings:
            return []

        # 2. Fast candidate retrieval and match counting via inverted index
        hit_counts = Counter()
        for ing in clean_user_ings:
            if ing in self.ingredient_index:
                hit_counts.update(self.ingredient_index[ing])
            else:
                for indexed_ing, indices in self.ingredient_index.items():
                    if ing in indexed_ing:
                        hit_counts.update(indices)
                        break

        if not hit_counts:
            return []

        # 3. Filter candidates and compute overlap scores
        clean_dietary = [d.lower().replace('-', '_').replace(' ', '_') for d in (dietary_filters or [])]
        category_lower = category.lower().strip() if category else None
        user_ing_count = len(clean_user_ings)

        scored_candidates = []
        for idx, match_count in hit_counts.items():
            rec_len = self.recipe_lengths[idx]
            if rec_len == 0:
                continue

            match_ratio = match_count / rec_len
            if match_ratio < min_match_ratio:
                continue

            # Category filter
            if category_lower and self.recipe_categories[idx] != category_lower:
                continue

            # Cooking time filter
            if max_time_mins is not None:
                t_val = self.recipe_total_times[idx]
                if t_val and t_val > max_time_mins:
                    continue

            # Dietary filter
            if clean_dietary:
                recipe_tags = self.recipe_keywords[idx]
                if not all(any(d in tag for tag in recipe_tags) for d in clean_dietary):
                    continue

            pantry_coverage = match_count / user_ing_count
            quality_score = min(self.recipe_bayesian[idx] / 5.0, 1.0)
            composite_score = (0.70 * match_ratio) + (0.15 * pantry_coverage) + (0.15 * quality_score)

            scored_candidates.append((composite_score, idx, match_ratio))

        # 4. Sort and select top N
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        top_candidates = scored_candidates[:top_n]

        # 5. Format detailed breakdown for top N
        results = []
        for comp_score, idx, match_ratio in top_candidates:
            row = self.metadata_df.iloc[idx]
            recipe_ings_set = set(self.recipe_ingredients[idx])
            matched = sorted(list(clean_user_ings.intersection(recipe_ings_set)))
            missing = sorted(list(recipe_ings_set - clean_user_ings))

            extra = {
                "match_percentage": round(match_ratio * 100, 1),
                "matched_ingredients": matched,
                "missing_ingredients": missing,
                "total_ingredients_count": len(recipe_ings_set),
                "composite_score": round(comp_score, 4)
            }
            results.append(self._format_recipe(row, extra=extra))

        return results

    def recommend_similar_recipes(
        self,
        recipe_id: Optional[int] = None,
        recipe_name: Optional[str] = None,
        top_n: int = 10,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Suggests recipes similar to a given target recipe ('More Like This').
        Uses precomputed TF-IDF cosine similarity over the recipe's similarity soup,
        weighted by Bayesian rating shrinkage.
        """
        if self.metadata_df is None:
            self.load_index()

        # Find target row index
        target_idx = None
        if recipe_id is not None:
            target_idx = self.id_to_index.get(recipe_id)
        elif recipe_name is not None:
            name_clean = clean_text(recipe_name).lower()
            matches = self.metadata_df[self.metadata_df['Name'].str.lower() == name_clean]
            if not matches.empty:
                target_idx = matches.index[0]

        if target_idx is None:
            return []

        # 1. Compute cosine similarities against all recipes via sparse matrix multiplication
        query_vec = self.tfidf_matrix[target_idx]
        # Fast dot product on sparse CSR: (N, features) dot (features, 1) -> (N, 1)
        sim_scores = self.tfidf_matrix.dot(query_vec.T).toarray().ravel()

        # 2. Exclude target recipe itself
        sim_scores[target_idx] = -1.0

        # 3. Apply Bayesian quality adjustment: 80% similarity, 20% rating quality
        bayesian_ratings = self.metadata_df['bayesian_rating'].to_numpy()
        quality_factor = np.clip(bayesian_ratings / 5.0, 0.0, 1.0)
        final_scores = (0.80 * sim_scores) + (0.20 * quality_factor)

        # 4. Optional Category Filter
        if category:
            cat_lower = category.lower().strip()
            cat_mask = self.metadata_df['RecipeCategory'].str.lower() == cat_lower
            final_scores = np.where(cat_mask, final_scores, -1.0)

        # 5. Extract top N indices
        top_indices = np.argsort(final_scores)[::-1][:top_n]

        results = []
        for idx in top_indices:
            if final_scores[idx] <= 0:
                continue
            row = self.metadata_df.iloc[idx]
            raw_sim = sim_scores[idx]
            extra = {
                "similarity_percentage": round(float(raw_sim) * 100, 1),
                "rank_score": round(float(final_scores[idx]), 4)
            }
            results.append(self._format_recipe(row, extra=extra))

        return results

    def search_recipes(
        self,
        query: str,
        top_n: int = 10,
        category: Optional[str] = None,
        max_time_mins: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs semantic & keyword retrieval matching user query against recipes.
        """
        if self.metadata_df is None:
            self.load_index()

        cleaned_query = clean_text(query).lower()
        if not cleaned_query:
            return []

        # Vectorize user query
        query_vec = self.vectorizer.transform([cleaned_query])
        sim_scores = self.tfidf_matrix.dot(query_vec.T).toarray().ravel()

        # Combine with quality rating
        bayesian_ratings = self.metadata_df['bayesian_rating'].to_numpy()
        quality_factor = np.clip(bayesian_ratings / 5.0, 0.0, 1.0)
        final_scores = (0.75 * sim_scores) + (0.25 * quality_factor)

        # Filters
        if category:
            cat_mask = self.metadata_df['RecipeCategory'].str.lower() == category.lower().strip()
            final_scores = np.where(cat_mask, final_scores, -1.0)

        if max_time_mins is not None:
            time_mask = (self.metadata_df['total_time_mins'] <= max_time_mins) | (self.metadata_df['total_time_mins'] == 0)
            final_scores = np.where(time_mask, final_scores, -1.0)

        top_indices = np.argsort(final_scores)[::-1][:top_n]

        results = []
        for idx in top_indices:
            if sim_scores[idx] <= 0:
                continue
            row = self.metadata_df.iloc[idx]
            extra = {
                "relevance_score": round(float(sim_scores[idx]) * 100, 1)
            }
            results.append(self._format_recipe(row, extra=extra))

        return results
