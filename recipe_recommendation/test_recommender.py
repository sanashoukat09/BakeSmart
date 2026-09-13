"""
Automated unit tests and benchmarks for BakeSmart Recipe Recommendation Module.
Usage:
    uv run --with pyarrow,pandas,scikit-learn,joblib python recipe_recommendation/test_recommender.py
"""

import time
import sys
import os

try:
    from recipe_recommendation.recommender import RecipeRecommender
except ImportError:
    from recommender import RecipeRecommender


def run_tests():
    print("=" * 75)
    print("      Running BakeSmart Recipe Recommendation Test Suite      ")
    print("=" * 75)

    recommender = RecipeRecommender(index_suffix="_baking_1000")
    assert recommender.metadata_df is not None, "Metadata DataFrame should be loaded"
    assert len(recommender.metadata_df) == 1000, f"Expected exactly 1,000 baking recipes, got {len(recommender.metadata_df)}"
    assert recommender.tfidf_matrix is not None, "TF-IDF matrix should be loaded"
    assert recommender.ingredient_index is not None, "Ingredient index should be loaded"
    print("\n[PASS] Test 1: Index loaded successfully with exactly", f"{len(recommender.metadata_df):,} curated baking recipes.")

    # Test 2: Pantry Ingredient Matching
    test_pantry = ["all-purpose flour", "granulated sugar", "unsalted butter", "cocoa powder"]
    t0 = time.time()
    results = recommender.recommend_by_ingredients(test_pantry, top_n=5)
    latency_ms = (time.time() - t0) * 1000

    assert len(results) > 0, "Should return at least 1 recipe for common baking ingredients"
    first = results[0]
    assert "recipe_id" in first, "Result must contain recipe_id"
    assert "match_percentage" in first, "Result must contain match_percentage"
    assert "matched_ingredients" in first, "Result must contain matched_ingredients"
    assert "ingredients_with_quantities" in first, "Result must contain ingredients_with_quantities"
    assert "instructions_list" in first, "Result must contain instructions_list"
    assert "author" not in str(first).lower(), "Author information must NOT be present in recipe output"
    assert len(first["matched_ingredients"]) > 0, "Matched ingredients cannot be empty"
    print(f"[PASS] Test 2: Ingredient matching returned '{first['name']}' ({first['match_percentage']}% match) in {latency_ms:.1f}ms.")

    # Test 3: Similar Recipes ("More Like This")
    target_id = int(first["recipe_id"])
    t0 = time.time()
    similar = recommender.recommend_similar_recipes(recipe_id=target_id, top_n=5)
    latency_sim_ms = (time.time() - t0) * 1000

    assert len(similar) > 0, "Should return similar recipes"
    for s in similar:
        assert s["recipe_id"] != target_id, "Target recipe should be excluded from recommendations"
        assert s["similarity_percentage"] > 0, "Similarity score must be positive"
        assert "author" not in str(s).lower(), "Author information must NOT be present in similar recipes"
    print(f"[PASS] Test 3: Similar recipes returned {len(similar)} items (top: '{similar[0]['name']}' with {similar[0]['similarity_percentage']}% sim) in {latency_sim_ms:.1f}ms.")

    # Test 4: Search Recipes
    t0 = time.time()
    search_res = recommender.search_recipes("chocolate chip cookie", top_n=5)
    latency_search_ms = (time.time() - t0) * 1000
    assert len(search_res) > 0, "Search should return chocolate chip cookie recipes"
    assert "ingredients_with_quantities" in search_res[0], "Search result must contain ingredients with quantities"
    assert "instructions_list" in search_res[0], "Search result must contain instructions_list"
    assert "author" not in str(search_res[0]).lower(), "Author information must NOT be present in search results"
    print(f"[PASS] Test 4: Semantic search returned '{search_res[0]['name']}' in {latency_search_ms:.1f}ms.")

    # Test 5: Single Recipe Details & Latency Benchmark
    details = recommender.get_recipe_details(target_id)
    assert details is not None, "get_recipe_details should return recipe object"
    assert len(details["ingredients_with_quantities"]) > 0, "Ingredients with quantities cannot be empty"
    assert len(details["instructions_list"]) > 0, "Instructions list cannot be empty"
    assert "author" not in str(details).lower(), "Author info must NOT exist in get_recipe_details"

    assert latency_ms < 100.0, f"Ingredient matching latency must be < 100ms (got {latency_ms:.1f}ms)"
    assert latency_sim_ms < 100.0, f"Similar recipes latency must be < 100ms (got {latency_sim_ms:.1f}ms)"
    print(f"[PASS] Test 5: Recipe details and latency verified (Lookup: {latency_ms:.1f}ms, Similarity: {latency_sim_ms:.1f}ms).")

    print("\n" + "=" * 75)
    print("            ALL 5 RECOMMENDER TESTS PASSED SUCCESSFULLY!            ")
    print("=" * 75 + "\n")


if __name__ == '__main__':
    run_tests()
