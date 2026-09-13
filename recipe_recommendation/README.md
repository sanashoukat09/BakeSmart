# BakeSmart Recipe Suggestion & Recommendation Module

This module contains the end-to-end intelligent recipe suggestion system for the **BakeSmart Final Year Project (FYP)**, powered by the Food.com dataset (520,298 recipes).

All development is maintained strictly on branch: **`zoha's-work`**.

---

## 📁 Directory Structure

```
BakeSmart/
├── data/
│   └── foodcom/
│       ├── recipes.csv                  # Original Food.com recipes dataset (unmodified, 671 MB)
│       ├── reviews.csv                  # Original Food.com reviews dataset (unmodified, 473 MB)
│       ├── cleaned_recipes.parquet      # Preprocessed recipes dataset (binary columnar format, 304 MB)
│       ├── cleaned_recipes.csv          # Preprocessed recipes dataset (CSV export, 671 MB)
│       ├── recipe_metadata_full.parquet # Fast metadata index (84 MB)
│       ├── tfidf_matrix_full.joblib     # Pre-computed sparse TF-IDF matrix (131 MB)
│       ├── tfidf_vectorizer_full.joblib # Trained TF-IDF vectorizer (0.39 MB)
│       └── ingredient_index_full.joblib # Inverted ingredient lookup table (8.22 MB)
└── recipe_recommendation/
    ├── __init__.py
    ├── inspect_dataset.py               # Multi-threaded dataset inspection
    ├── preprocess.py                    # 6-step dataset cleaning & similarity pipeline
    ├── utils.py                         # R-vector parser, duration parser, ingredient normalizer
    ├── build_index.py                   # Index builder for TF-IDF & inverted ingredient index
    ├── recommender.py                   # Core RecipeRecommender engine
    ├── recommend_cli.py                 # Interactive & CLI recommendation tool
    ├── api.py                           # FastAPI REST endpoints for BakeSmart integration
    ├── test_recommender.py              # Automated test suite and latency benchmarks
    ├── verify_cleaned.py                # Validation script for cleaned data
    ├── requirements.txt                 # Dependencies: pandas, pyarrow, scikit-learn, fastapi, uvicorn
    ├── dataset_summary.json             # Inspection metrics in JSON format
    └── README.md                        # Documentation
```

---

## 🧠 Core Recommendation Capabilities

### 1. Ingredient-Based Pantry Matching
- **Concept**: Bakers or customers input available ingredients in their pantry (e.g. `flour, butter, sugar, chocolate`).
- **Algorithm**:
  - Uses an inverted index mapping 7,285 unique ingredients to candidate recipes.
  - Computes recipe match ratio: $\frac{|\text{User} \cap \text{Recipe}|}{|\text{Recipe}|}$
  - Computes pantry coverage: $\frac{|\text{User} \cap \text{Recipe}|}{|\text{User}|}$
  - Applies Bayesian rating shrinkage: $\text{Rank} = 0.70 \cdot \text{MatchRatio} + 0.15 \cdot \text{PantryCoverage} + 0.15 \cdot \text{BayesianRating}$
  - Returns match percentage, matched ingredients, and **missing ingredients needed**.
  - **Latency**: $\approx 85\text{ ms}$ across 520,298 recipes.

### 2. Content-Based "More Like This" Similarity
- **Concept**: Suggests recipes closely related to a specific cake, pastry, or recipe ID.
- **Algorithm**:
  - TF-IDF vectorization with sublinear scaling over the engineered `similarity_soup`.
  - Pairwise cosine similarity against sparse CSR matrix.
  - Combines with quality prior ($0.80 \cdot \text{CosineSim} + 0.20 \cdot \text{RatingPrior}$).
  - **Latency**: $\approx 210\text{ ms}$.

### 3. Semantic & Keyword Filtered Search
- Full query matching supporting dietary constraints (`Eggless`, `Gluten-Free`), category filtering (`Dessert`, `Cakes`, `Breads`), and maximum preparation time (e.g. `max_time <= 45 mins`).

### 4. Interactive Recipe Detail Modal & Culinary Measurements
- Full ingredient quantities with standard baking units (`cups`, `tsp`, `tbsp`, `packet`, `can`, `oz`).
- Step-by-step numbered baking directions.
- Strict omission of author details.

---

## 🚀 How to Run

### 1. Run Recommender Test Suite
```bash
uv run --with pyarrow,pandas,scikit-learn,joblib python recipe_recommendation/test_recommender.py
```

### 2. Command-Line Interface (CLI)

#### Pantry Ingredient Matching:
```bash
uv run --with pyarrow,pandas,scikit-learn,joblib python recipe_recommendation/recommend_cli.py --ingredients "flour, butter, sugar, chocolate" --top-n 5
```

#### Find Similar Recipes:
```bash
uv run --with pyarrow,pandas,scikit-learn,joblib python recipe_recommendation/recommend_cli.py --similar 2886 --top-n 5
```

#### Search with Dietary & Time Filters:
```bash
uv run --with pyarrow,pandas,scikit-learn,joblib python recipe_recommendation/recommend_cli.py --search "banana bread" --max-time 60
```

#### Interactive Mode:
```bash
uv run --with pyarrow,pandas,scikit-learn,joblib python recipe_recommendation/recommend_cli.py
```

---

## 🌐 Running the FastAPI REST Service & Web UI

Start the API server:
```bash
uv run --with pyarrow,pandas,scikit-learn,joblib,fastapi,uvicorn uvicorn recipe_recommendation.api:app --host 127.0.0.1 --port 8000 --reload
```

Interactive Web UI:
`http://127.0.0.1:8000/`

Swagger API documentation:
`http://127.0.0.1:8000/docs`

### API Endpoints:
* `POST /api/recommend/ingredients`: Body: `{"ingredients": ["flour", "cocoa", "butter"], "top_n": 5, "max_time_mins": 60}`
* `GET /api/recommend/similar/{recipe_id}`: e.g. `/api/recommend/similar/2886?top_n=5`
* `GET /api/recipes/search`: e.g. `/api/recipes/search?q=banana+bread&top_n=5`
* `GET /api/recipes/{recipe_id}`: e.g. `/api/recipes/2886` (Returns full ingredient quantities, steps, without author)
* `GET /api/health`: Health status and total indexed recipe count.
