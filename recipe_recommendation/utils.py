"""
Utility functions for Food.com recipe dataset inspection and preprocessing.
BakeSmart FYP - Recipe Recommendation Module
"""

import re
from typing import List, Optional

def parse_r_vector(val: Optional[str]) -> List[str]:
    """
    Parses R-style vector strings from Food.com dataset, such as:
    c("blueberries", "granulated sugar", "vanilla yogurt")
    or returns an empty list for 'character(0)', 'NA', or None.
    """
    if not val or not isinstance(val, str):
        return []
    val = val.strip()
    if val in ('character(0)', 'NA', 'nan', 'NULL', 'null', ''):
        return []
    
    # Extract items inside double quotes
    items = re.findall(r'"((?:[^"\\]|\\.)*)"', val)
    cleaned_items = []
    for item in items:
        unescaped = item.replace(r'\"', '"').replace(r"\'", "'").strip()
        if unescaped:
            cleaned_items.append(unescaped)
    return cleaned_items


def clean_text(text: Optional[str]) -> str:
    """
    Cleans general text strings (removes excess spaces, non-printable characters).
    """
    if not text or not isinstance(text, str):
        return ""
    cleaned = re.sub(r'\s+', ' ', text).strip()
    return cleaned


def normalize_ingredient(ingredient: str) -> str:
    """
    Normalizes an ingredient name:
    - lowercases
    - strips whitespace
    - replaces spaces with underscores for compound terms (e.g. 'all-purpose flour' -> 'all_purpose_flour')
    """
    ing = ingredient.lower().strip()
    ing = ing.replace('-', ' ')
    ing = re.sub(r'[^a-z0-9\s]', '', ing)
    ing = re.sub(r'\s+', ' ', ing).strip()
    return ing.replace(' ', '_')


def normalize_ingredients_list(ingredients: List[str]) -> List[str]:
    """
    Normalizes a list of ingredient strings and removes duplicates while preserving order.
    """
    seen = set()
    normalized = []
    for ing in ingredients:
        norm = normalize_ingredient(ing)
        if norm and norm not in seen:
            seen.add(norm)
            normalized.append(norm)
    return normalized


def normalize_keywords_list(keywords: List[str]) -> List[str]:
    """
    Normalizes tags and keywords (lowercasing, cleaning).
    """
    seen = set()
    normalized = []
    for kw in keywords:
        clean_kw = kw.lower().strip()
        clean_kw = re.sub(r'[^a-z0-9\s-]', '', clean_kw)
        clean_kw = re.sub(r'\s+', ' ', clean_kw).strip()
        clean_tag = clean_kw.replace(' ', '_').replace('-', '_')
        if clean_tag and clean_tag not in seen:
            seen.add(clean_tag)
            normalized.append(clean_tag)
    return normalized


def parse_iso_duration(duration_str: Optional[str]) -> Optional[int]:
    """
    Converts ISO-8601 duration (e.g. 'PT24H', 'PT45M', 'PT24H45M', 'PT1D') into total minutes.
    Returns None if missing or invalid.
    """
    if not duration_str or not isinstance(duration_str, str):
        return None
    duration_str = duration_str.strip().upper()
    if duration_str in ('NA', 'NAN', '', 'NULL'):
        return None

    pattern = r'P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?'
    match = re.match(pattern, duration_str)
    if not match:
        return None

    days = int(match.group(1)) if match.group(1) else 0
    hours = int(match.group(2)) if match.group(2) else 0
    minutes = int(match.group(3)) if match.group(3) else 0
    seconds = int(match.group(4)) if match.group(4) else 0

    total_minutes = (days * 24 * 60) + (hours * 60) + minutes + (1 if seconds >= 30 else 0)
    return total_minutes


def extract_primary_image(images_str: Optional[str]) -> str:
    """
    Extracts the first valid URL from the R-vector images column.
    """
    urls = parse_r_vector(images_str)
    for url in urls:
        if url.startswith('http://') or url.startswith('https://'):
            return url
    return ""
