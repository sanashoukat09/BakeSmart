"""
FastAPI REST Service for BakeSmart Recipe Suggestions.
Provides HTTP endpoints for the BakeSmart Flutter app and Firebase Cloud Functions.

Run with:
    uv run --with pyarrow,pandas,scikit-learn,joblib,fastapi,uvicorn uvicorn recipe_recommendation.api:app --host 0.0.0.0 --port 8000 --reload
"""

import os
from typing import List, Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

try:
    from recipe_recommendation.recommender import RecipeRecommender
except ImportError:
    from recommender import RecipeRecommender

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')

app = FastAPI(
    title="BakeSmart Recipe Suggestion API",
    description="Intelligent ingredient-based pantry matching and content-based recipe recommendation for BakeSmart FYP.",
    version="1.0.0"
)

@app.get("/", response_class=HTMLResponse)
def serve_ui():
    """Serves the interactive BakeSmart Recipe Recommendation web application."""
    index_file = os.path.join(TEMPLATES_DIR, 'index.html')
    if os.path.exists(index_file):
        with open(index_file, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h2>BakeSmart UI template not found</h2>", status_code=404)

# Global singleton recommender instance (lazy loaded)
recommender: Optional[RecipeRecommender] = None


@app.on_event("startup")
def startup_event():
    global recommender
    # Default to full dataset index
    recommender = RecipeRecommender(index_suffix="_full")


class IngredientRecommendRequest(BaseModel):
    ingredients: List[str] = Field(..., example=["all-purpose flour", "unsalted butter", "granulated sugar", "cocoa powder"])
    top_n: int = Field(10, ge=1, le=50)
    min_match_ratio: float = Field(0.25, ge=0.0, le=1.0)
    dietary_filters: Optional[List[str]] = Field(None, example=["eggless", "gluten-free"])
    max_time_mins: Optional[int] = Field(None, example=60)
    category: Optional[str] = Field(None, example="Dessert")


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "BakeSmart Recipe Suggestion API",
        "total_recipes_indexed": len(recommender.metadata_df) if recommender and recommender.metadata_df is not None else 0
    }


@app.post("/api/recommend/ingredients")
def recommend_by_ingredients(payload: IngredientRecommendRequest):
    """
    Suggests recipes that best match the ingredients provided by the baker/user.
    """
    if not recommender:
        raise HTTPException(status_code=503, detail="Recommender engine is not initialized.")

    if not payload.ingredients:
        raise HTTPException(status_code=400, detail="Ingredients list cannot be empty.")

    results = recommender.recommend_by_ingredients(
        user_ingredients=payload.ingredients,
        top_n=payload.top_n,
        min_match_ratio=payload.min_match_ratio,
        dietary_filters=payload.dietary_filters,
        max_time_mins=payload.max_time_mins,
        category=payload.category
    )
    return {
        "query_ingredients": payload.ingredients,
        "total_matches": len(results),
        "recommendations": results
    }


@app.get("/api/recommend/similar/{recipe_id}")
def recommend_similar(
    recipe_id: int,
    top_n: int = Query(10, ge=1, le=50),
    category: Optional[str] = Query(None)
):
    """
    Finds recipes similar to a specific recipe ('More Like This').
    """
    if not recommender:
        raise HTTPException(status_code=503, detail="Recommender engine is not initialized.")

    results = recommender.recommend_similar_recipes(
        recipe_id=recipe_id,
        top_n=top_n,
        category=category
    )
    if not results:
        raise HTTPException(status_code=404, detail=f"Recipe with ID {recipe_id} not found or has no similar items.")

    return {
        "target_recipe_id": recipe_id,
        "total_similar": len(results),
        "recommendations": results
    }


@app.get("/api/recipes/search")
def search_recipes(
    q: str = Query(..., min_length=1, description="Search query or flavor keywords"),
    top_n: int = Query(10, ge=1, le=50),
    category: Optional[str] = Query(None),
    max_time_mins: Optional[int] = Query(None)
):
    """
    Search recipes by keyword / natural language query with optional filtering.
    """
    if not recommender:
        raise HTTPException(status_code=503, detail="Recommender engine is not initialized.")

    results = recommender.search_recipes(
        query=q,
        top_n=top_n,
        category=category,
        max_time_mins=max_time_mins
    )
    return {
        "query": q,
        "total_results": len(results),
        "recipes": results
    }
