# BakeSmart Recipe Suggestion Module

This module contains the dataset inspection, data cleaning, and preprocessing pipeline for the Food.com Recipes & Reviews dataset as part of the **BakeSmart Final Year Project (FYP)**.

All work in this module is developed on branch: **`zoha's-work`**.

---

## 📁 Directory Structure

```
BakeSmart/
├── data/
│   └── foodcom/
│       ├── recipes.csv               # Original Food.com recipes dataset (unmodified, 671 MB)
│       ├── reviews.csv               # Original Food.com reviews dataset (unmodified, 473 MB)
│       ├── cleaned_recipes.parquet   # Preprocessed recipes dataset (binary columnar format, fast loading)
│       └── cleaned_recipes.csv       # Preprocessed recipes dataset (standard CSV format)
└── recipe_recommendation/
    ├── __init__.py
    ├── inspect_dataset.py            # Dataset inspection tool
    ├── preprocess.py                 # 6-step dataset cleaning & similarity feature pipeline
    ├── utils.py                      # R-vector parser, text cleaning, ingredient normalizer
    ├── requirements.txt              # Module dependencies (pandas, pyarrow, numpy)
    ├── dataset_summary.json          # Machine-readable inspection metrics
    └── README.md                     # Module documentation
```

---

## 🔍 Dataset Inspection Summary

| Dataset File | File Size | Row Count | Column Count | Key Highlights |
| :--- | :--- | :--- | :--- | :--- |
| **`recipes.csv`** | **671.59 MB** | **522,517** | **28** | Multi-line instructions, R-vector string arrays `c("...")`, 48.46% missing ratings |
| **`reviews.csv`** | **473.12 MB** | **1,401,982** | **8** | Ratings 0-5, 212 empty reviews (0.02%), user interactions |

---

## ⚙️ How to Run

Dependencies are managed automatically using Python 3.11 and `uv` (fast package runner) or standard `pip`.

### 1. Run Dataset Inspection
```bash
uv run --with pyarrow,pandas python recipe_recommendation/inspect_dataset.py
```
This generates:
- Terminal diagnostic table showing data types, null counts, and missing percentages.
- `recipe_recommendation/dataset_summary.json`

### 2. Run Preprocessing Pipeline
To process the full dataset:
```bash
uv run --with pyarrow,pandas python recipe_recommendation/preprocess.py
```

#### Fast Verification / Sampling Options:
```bash
# Process a sample of 5,000 recipes for quick testing
uv run --with pyarrow,pandas python recipe_recommendation/preprocess.py --sample 5000

# Filter exclusively for baking and bakery-related recipes (desserts, cakes, breads, etc.)
uv run --with pyarrow,pandas python recipe_recommendation/preprocess.py --baking-only

# Save only Parquet format (skipping CSV generation)
uv run --with pyarrow,pandas python recipe_recommendation/preprocess.py --no-csv
```

---

## 🧹 Preprocessing Steps

1. **Dataset Loading**: Multi-threaded parsing of raw CSV with newlines-in-values support via PyArrow.
2. **Column Selection & Dimensionality Reduction**: Retains 15 essential features, dropping uninformative metadata (e.g. `AuthorId`, `AuthorName`, `DatePublished`).
3. **Missing Value Handling**:
   - Drops recipes missing names or having empty ingredient lists (`character(0)`).
   - Fills missing ratings (`0.0`), review counts (`0`), calories (`0.0`), and servings (`1`).
4. **Data Normalization & Cleaning**:
   - Parses R-style vectors `c("item1", "item2")` into structured Python lists.
   - Normalizes compound ingredients into joined tokens (e.g. `all-purpose flour` $\to$ `all_purpose_flour`).
   - Normalizes keywords and tags.
   - Parses ISO-8601 durations (`PT45M`, `PT1H30M`) into total integer minutes (`prep_time_mins`, `cook_time_mins`, `total_time_mins`).
   - Extracts primary image URLs from the `Images` array.
5. **Similarity Feature Engineering**:
   - Generates `similarity_soup`: weighted text concatenation combining recipe title, category, keywords, and normalized ingredients.
   - Formatted specifically for downstream TF-IDF, CountVectorizer, Word2Vec, or Transformer embeddings.
6. **Separated Storage**:
   - Saves clean output to `data/foodcom/cleaned_recipes.parquet` and `data/foodcom/cleaned_recipes.csv`.
   - Leaves original raw CSV files completely untouched.
