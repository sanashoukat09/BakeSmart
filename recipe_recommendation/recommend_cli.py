"""
Interactive Command Line Interface (CLI) for BakeSmart Recipe Suggestions.

Usage:
    # 1. Pantry Ingredient Matching
    uv run --with pyarrow,pandas,scikit-learn,joblib python recipe_recommendation/recommend_cli.py --ingredients "flour, butter, sugar, chocolate"

    # 2. Similar Recipe Suggestions ("More Like This")
    uv run --with pyarrow,pandas,scikit-learn,joblib python recipe_recommendation/recommend_cli.py --similar 38

    # 3. Semantic Search with Time Filter
    uv run --with pyarrow,pandas,scikit-learn,joblib python recipe_recommendation/recommend_cli.py --search "blueberry muffin" --max-time 60

    # 4. Interactive Mode
    uv run --with pyarrow,pandas,scikit-learn,joblib python recipe_recommendation/recommend_cli.py
"""

import sys
import argparse
from recommender import RecipeRecommender


def print_banner():
    print("=" * 75)
    print("           BakeSmart FYP - Recipe Recommendation System           ")
    print("=" * 75)


def display_ingredient_results(results):
    if not results:
        print("\n[!] No matching recipes found for the provided ingredients and filters.")
        return

    print(f"\nFound {len(results)} matching recipes:")
    print("-" * 75)
    for i, r in enumerate(results, 1):
        print(f"\n{i}. {r['name']} (ID: {r['recipe_id']})")
        print(f"   Category:     {r['category']}")
        print(f"   Match Score:  {r['match_percentage']}% matched (Rank: {r['composite_score']})")
        print(f"   Matched Ings: {', '.join(r['matched_ingredients'])}")
        if r['missing_ingredients']:
            missing_preview = ', '.join(r['missing_ingredients'][:6])
            if len(r['missing_ingredients']) > 6:
                missing_preview += f" ... (+{len(r['missing_ingredients']) - 6} more)"
            print(f"   Missing Ings: {missing_preview}")
        else:
            print("   Missing Ings: [None! You have 100% of the ingredients!]")
        print(f"   Rating:       {r['rating']}/5.0 ({r['reviews_count']} reviews) | Total Time: {r['total_time_mins']} mins")
        if r['image_url']:
            print(f"   Thumbnail:    {r['image_url']}")


def display_similar_results(results):
    if not results:
        print("\n[!] No similar recipes found.")
        return

    print(f"\nFound {len(results)} similar recipes:")
    print("-" * 75)
    for i, r in enumerate(results, 1):
        print(f"\n{i}. {r['name']} (ID: {r['recipe_id']})")
        print(f"   Category:     {r['category']}")
        print(f"   Similarity:   {r['similarity_percentage']}% cosine similarity")
        print(f"   Rating:       {r['rating']}/5.0 ({r['reviews_count']} reviews)")
        print(f"   Total Time:   {r['total_time_mins']} mins | Calories: {r['calories']} kcal")
        print(f"   Sample Ings:  {', '.join(r['sample_ingredients'])}")
        if r['image_url']:
            print(f"   Thumbnail:    {r['image_url']}")


def display_search_results(results):
    if not results:
        print("\n[!] No recipes matched the search query.")
        return

    print(f"\nFound {len(results)} matching recipes:")
    print("-" * 75)
    for i, r in enumerate(results, 1):
        print(f"\n{i}. {r['name']} (ID: {r['recipe_id']})")
        print(f"   Category:     {r['category']}")
        print(f"   Relevance:    {r['relevance_score']}% match")
        print(f"   Rating:       {r['rating']}/5.0 ({r['reviews_count']} reviews) | Total Time: {r['total_time_mins']} mins")
        if r['image_url']:
            print(f"   Thumbnail:    {r['image_url']}")


def interactive_mode(recommender):
    while True:
        print("\n" + "=" * 75)
        print("BakeSmart Recommendation Menu:")
        print("  1. Find recipes from ingredients (Pantry Suggester)")
        print("  2. Find similar recipes ('More Like This')")
        print("  3. Search recipes by keyword / flavor")
        print("  4. Exit")
        print("=" * 75)
        
        choice = input("Select an option (1-4): ").strip()
        if choice == '1':
            raw = input("\nEnter available ingredients (comma-separated, e.g. flour, butter, chocolate): ")
            ings = [x.strip() for x in raw.split(',') if x.strip()]
            dietary_raw = input("Dietary filters (optional, e.g. eggless, gluten-free, or press enter): ").strip()
            dietary = [x.strip() for x in dietary_raw.split(',') if x.strip()] if dietary_raw else None
            max_time = input("Max total time in minutes (optional, or press enter): ").strip()
            time_mins = int(max_time) if max_time.isdigit() else None
            
            results = recommender.recommend_by_ingredients(ings, top_n=5, dietary_filters=dietary, max_time_mins=time_mins)
            display_ingredient_results(results)
            
        elif choice == '2':
            recipe_id_raw = input("\nEnter Recipe ID (e.g. 38): ").strip()
            if recipe_id_raw.isdigit():
                results = recommender.recommend_similar_recipes(recipe_id=int(recipe_id_raw), top_n=5)
                display_similar_results(results)
            else:
                results = recommender.recommend_similar_recipes(recipe_name=recipe_id_raw, top_n=5)
                display_similar_results(results)
                
        elif choice == '3':
            query = input("\nEnter search query (e.g. strawberry tart, chocolate chip cookies): ").strip()
            results = recommender.search_recipes(query, top_n=5)
            display_search_results(results)
            
        elif choice in ('4', 'q', 'exit'):
            print("\nExiting BakeSmart Recommendation CLI.")
            break


def main():
    parser = argparse.ArgumentParser(description="BakeSmart Recipe Suggestion CLI")
    parser.add_argument('--ingredients', type=str, help='Comma-separated list of ingredients')
    parser.add_argument('--similar', type=int, help='Recipe ID to find similar recipes for')
    parser.add_argument('--similar-name', type=str, help='Recipe Name to find similar recipes for')
    parser.add_argument('--search', type=str, help='Search query text')
    parser.add_argument('--category', type=str, help='Filter by recipe category')
    parser.add_argument('--dietary', type=str, help='Comma-separated dietary tags (e.g. eggless, gluten-free)')
    parser.add_argument('--max-time', type=int, help='Maximum total time in minutes')
    parser.add_argument('--top-n', type=int, default=5, help='Number of recommendations to return')
    parser.add_argument('--all-recipes', action='store_true', help='Use full 520k recipes index')
    args = parser.parse_args()

    print_banner()
    suffix = "_full" if args.all_recipes else "_baking_1000"
    recommender = RecipeRecommender(index_suffix=suffix)

    dietary = [x.strip() for x in args.dietary.split(',')] if args.dietary else None

    if args.ingredients:
        ings = [x.strip() for x in args.ingredients.split(',') if x.strip()]
        print(f"\n[*] Matching recipes for ingredients: {ings}")
        results = recommender.recommend_by_ingredients(
            ings,
            top_n=args.top_n,
            dietary_filters=dietary,
            max_time_mins=args.max_time,
            category=args.category
        )
        display_ingredient_results(results)

    elif args.similar is not None or args.similar_name:
        print(f"\n[*] Finding similar recipes for: {args.similar or args.similar_name}")
        results = recommender.recommend_similar_recipes(
            recipe_id=args.similar,
            recipe_name=args.similar_name,
            top_n=args.top_n,
            category=args.category
        )
        display_similar_results(results)

    elif args.search:
        print(f"\n[*] Searching recipes for: '{args.search}'")
        results = recommender.search_recipes(
            args.search,
            top_n=args.top_n,
            category=args.category,
            max_time_mins=args.max_time
        )
        display_search_results(results)

    else:
        interactive_mode(recommender)


if __name__ == '__main__':
    main()
