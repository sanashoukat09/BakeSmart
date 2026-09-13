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


import html

def clean_text(text: Optional[str]) -> str:
    """
    Cleans general text strings (unescapes HTML entities, fixes degree symbols, removes excess spaces).
    """
    if not text or not isinstance(text, str):
        return ""
    unescaped = html.unescape(text)
    # Fix common encoding artifact for degree symbol in baking temperatures (e.g. 350 -> 350°)
    unescaped = unescaped.replace('\ufffd', '°')
    cleaned = re.sub(r'\s+', ' ', unescaped).strip()
    return cleaned


def format_measured_ingredient(part: str, quant: str, instructions_text: str = "") -> str:
    """
    Intelligently formats an ingredient name and quantity with appropriate culinary units
    (e.g., '1 1/2 cups milk', '1 cup warm water', '2 cups all-purpose flour', '1 tsp baking soda', '2 eggs').
    """
    clean_p = clean_text(part)
    q = clean_text(quant) if quant and str(quant).strip() not in ('NA', 'character(0)', '0', 'None') else ""
    if not q:
        return clean_p
    if not clean_p:
        return q

    part_lower = clean_p.lower()

    # 1. If quantity already contains a unit of measurement (e.g. "1 cup", "2 tsp", "8 oz")
    unit_regex = r'\b(cup|cups|c|tsp|teaspoon|teaspoons|tbsp|tablespoon|tablespoons|oz|ounce|ounces|lb|pound|pounds|stick|sticks|can|pkg|package|packet|pinch|dash|ml|g|gram|grams)\b'
    if re.search(unit_regex, q, re.IGNORECASE):
        return f"{q} {clean_p}"

    # 2. Check if instructions text mentions this quantity + unit + ingredient
    if instructions_text:
        clean_search = re.escape(part_lower.split(',')[0].strip())
        instr_pattern = rf'\b({re.escape(q)}\s*(?:cups?|c\.|teaspoons?|tsp\.?|tablespoons?|tbsp\.?|ounces?|oz\.?|sticks?|pkgs?|can|packet)\b(?:\s+of)?\s+{clean_search})'
        match = re.search(instr_pattern, instructions_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # 3. Determine culinary unit based on ingredient type
    # Check if quantity represents a single/fractional amount (uses singular e.g. "1 cup", "1/2 cup")
    is_singular = q in ('1', '1.0', '1/2', '1/3', '1/4', '2/3', '3/4', '1/8')

    # A. Countable ingredients (no measurement unit needed)
    if any(part_lower == c or part_lower.startswith(c + ' ') for c in ['egg', 'eggs']):
        if 'white' in part_lower:
            return f"{q} egg white" if q in ('1', '1.0') else f"{q} egg whites"
        if 'yolk' in part_lower:
            return f"{q} egg yolk" if q in ('1', '1.0') else f"{q} egg yolks"
        return f"{q} egg" if q in ('1', '1.0') else f"{q} eggs"

    if any(part_lower == c or part_lower.startswith(c + ' ') for c in ['banana', 'bananas']):
        return f"{q} banana" if q in ('1', '1.0') else f"{q} bananas"

    if any(part_lower == c or part_lower.startswith(c + ' ') for c in ['apple', 'apples']):
        return f"{q} apple" if q in ('1', '1.0') else f"{q} apples"

    if any(part_lower == c or part_lower.startswith(c + ' ') for c in ['lemon', 'lemons']):
        return f"{q} lemon" if q in ('1', '1.0') else f"{q} lemons"

    if any(part_lower == c or part_lower.startswith(c + ' ') for c in ['clove', 'cloves']):
        return f"{q} clove" if q in ('1', '1.0') else f"{q} cloves"

    # B. Butter / Margarine / Shortening (always cups in baking)
    if any(b in part_lower for b in ['butter', 'margarine', 'shortening', 'lard']):
        unit = 'cup' if is_singular else 'cups'
        return f"{q} {unit} {clean_p}"

    # C. Teaspoon items (spices, leaveners, extracts, salt)
    tsp_regex = r'\b(baking soda|baking powder|salt|kosher salt|sea salt|table salt|cinnamon|ground cinnamon|vanilla|vanilla extract|almond extract|nutmeg|ground nutmeg|cream of tartar|allspice|cloves?|ground cloves|ginger|ground ginger|cardamom)\b'
    if re.search(tsp_regex, part_lower) and 'unsalted' not in part_lower:
        return f"{q} tsp {clean_p}"

    # D. Yeast
    if 'yeast' in part_lower:
        if q in ('1', '1.0'):
            return f"1 packet (or 2 1/4 tsp) {clean_p}"
        return f"{q} tsp {clean_p}"

    # E. Tablespoon items (juices, vinegars)
    tbsp_items = ['lemon juice', 'lime juice', 'vinegar', 'apple cider vinegar']
    if any(item in part_lower for item in tbsp_items):
        unit = 'tbsp' if is_singular else 'tbsps'
        return f"{q} {unit} {clean_p}"

    # F. Cream cheese
    if 'cream cheese' in part_lower:
        if q in ('8', '8.0'):
            return f"8 oz {clean_p}"
        if q in ('1', '1.0'):
            return f"1 pkg (8 oz) {clean_p}"
        return f"{q} cup {clean_p}"

    # G. Canned items (condensed milk, evaporated milk, pumpkin)
    if any(item in part_lower for item in ['condensed milk', 'evaporated milk', 'pumpkin puree', 'canned pumpkin']):
        return f"{q} can (14 oz) {clean_p}"

    # H. Standard bulk baking ingredients (Flour, Sugar, Milk, Water, Cocoa, Oils, Chips, Nuts, Oats, etc.)
    unit = 'cup' if is_singular else 'cups'
    return f"{q} {unit} {clean_p}"


def pair_ingredients_and_quantities(parts: List[str], quants: List[str], instructions_text: str = "") -> List[str]:
    """
    Pairs raw ingredient names with their corresponding measurements/quantities and intelligent culinary units.
    E.g. parts=["milk", "warm water", "baking soda", "eggs"], quants=["1 1/2", "1", "1", "2"]
      -> ["1 1/2 cups milk", "1 cup warm water", "1 tsp baking soda", "2 eggs"]
    """
    paired = []
    for i, part in enumerate(parts):
        q = quants[i] if i < len(quants) else ""
        paired.append(format_measured_ingredient(part, q, instructions_text))
    return paired


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
