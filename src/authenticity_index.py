"""
Part 3 authenticity index construction.

This script combines the Part 1 stated-values dataset with the Part 2 lived-values
proxy dataset, calculates alignment components, and saves the final company-year
authenticity index.
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

# Project paths and input files
BASE_DIR = Path(__file__).resolve().parents[1]

STATED_FILE = BASE_DIR / "outputs" / "stated_values" / "stated_values_company_year.csv"
LIVED_FILE = BASE_DIR / "outputs" / "lived_values" / "lived_values_company_year.csv"

OUT_DIR = BASE_DIR / "outputs" / "authenticity"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_FILE = OUT_DIR / "authenticity_company_year.csv"
SUMMARY_FILE = OUT_DIR / "authenticity_summary_by_company.csv"
SECTOR_FILE = OUT_DIR / "authenticity_summary_by_sector.csv"

# Shared value categories used to compare stated-values pages and proxy statements
THEMES = [
    "innovation",
    "customer_focus",
    "employees_culture",
    "diversity_inclusion",
    "sustainability_environment",
    "community_social_impact",
    "integrity_ethics_trust",
    "health_safety_wellbeing",
    "financial_performance_growth",
]

# Safely parse stored JSON theme-count fields
def safe_json_loads(x):
    if not isinstance(x, str) or not x.strip():
        return {}
    try:
        return json.loads(x)
    except Exception:
        return {}

# Convert semicolon-separated theme strings into sets for overlap comparison
def parse_theme_set(x):
    if not isinstance(x, str) or not x.strip():
        return set()
    return set([t.strip() for t in x.split(";") if t.strip()])

# Measure whether the two documents mention the same value categories
def jaccard_similarity(a, b):
    a = set(a)
    b = set(b)

    if not a and not b:
        return np.nan

    union = a | b
    intersection = a & b

    if not union:
        return np.nan

    return len(intersection) / len(union)

# Convert theme counts into a fixed-order vector, optionally normalized by text length
def counts_to_vector(counts, text_len=None):
    vec = []

    for theme in THEMES:
        val = counts.get(theme, 0)
        try:
            val = float(val)
        except Exception:
            val = 0.0

        vec.append(val)

    vec = np.array(vec, dtype=float)

    if text_len and text_len > 0:
        vec = vec / text_len * 10000

    return vec

# Measure whether the two documents emphasize themes in similar proportions
def cosine_similarity(a, b):
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)

    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return np.nan

    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def tone_alignment(stated_tone, lived_tone):
    """
    Returns a 0-1 score.
    1 = very similar tone direction.
    0 = very different tone direction.
    """

    if pd.isna(stated_tone) or pd.isna(lived_tone):
        return np.nan

    diff = abs(float(stated_tone) - float(lived_tone))

    # Tone scores are roughly in [-1, 1]. Convert difference to 0-1 similarity.
    return max(0.0, 1.0 - diff / 2.0)


def simple_tone_from_text(text):
    """
    Part 1 does not currently have explicit tone columns, so this creates
    a simple tone score using the same idea as Part 2.
    """

    if not isinstance(text, str):
        text = ""

    text = text.lower()

    positive_words = [
        "strong", "effective", "successful", "improve", "improved", "progress",
        "opportunity", "responsible", "sustainable", "commitment", "committed",
        "support", "inclusive", "diverse", "ethical", "transparent"
    ]

    negative_words = [
        "risk", "risks", "challenge", "challenges", "uncertain", "uncertainty",
        "loss", "decline", "weakness", "concern", "litigation", "violation",
        "failure", "adverse", "material adverse"
    ]

    def count_terms(words):
        total = 0
        for word in words:
            total += text.count(word)
        return total

    pos = count_terms(positive_words)
    neg = count_terms(negative_words)
    total = pos + neg

    if total == 0:
        return 0.0, pos, neg

    return round((pos - neg) / total, 4), pos, neg

# Convert the numeric index into a simple interpretation label
def authenticity_label(score):
    if pd.isna(score):
        return "insufficient_data"
    if score >= 0.75:
        return "high_alignment"
    if score >= 0.50:
        return "moderate_alignment"
    return "low_alignment"


def main():
    # Load stated-values and lived-values datasets before merging them by company-year
    stated = pd.read_csv(STATED_FILE)
    lived = pd.read_csv(LIVED_FILE)

    # Recalculate text-availability flags so the index only uses rows with enough text
    stated["stated_text_len"] = stated["page_text_clean"].fillna("").str.len()
    stated["stated_has_text"] = stated["stated_text_len"] >= 400

    lived["lived_text_len"] = lived["proxy_text_clean"].fillna("").str.len()
    lived["lived_has_text"] = lived["lived_text_len"] >= 1000

    # Part 1 does not have a stored tone field, so create one from the stated-values text
    tone_rows = stated["page_text_clean"].fillna("").apply(simple_tone_from_text)
    stated["stated_tone_net"] = tone_rows.apply(lambda x: x[0])
    stated["stated_tone_positive"] = tone_rows.apply(lambda x: x[1])
    stated["stated_tone_negative"] = tone_rows.apply(lambda x: x[2])

    # Keep only the Part 1 columns needed for the authenticity index
    keep_stated = stated[[
        "ticker",
        "company_name",
        "sector",
        "year",
        "source_url_seed",
        "wayback_timestamp",
        "wayback_original_url",
        "stated_text_len",
        "stated_has_text",
        "theme_categories",
        "theme_counts_json",
        "changed_from_prior",
        "text_similarity_to_prior",
        "selection_method",
        "selected_page_type",
        "selected_page_score",
        "needs_review",
        "stated_tone_positive",
        "stated_tone_negative",
        "stated_tone_net",
        "analyst_notes",
    ]].rename(columns={
        "theme_categories": "stated_theme_categories",
        "theme_counts_json": "stated_theme_counts_json",
        "needs_review": "stated_needs_review",
        "analyst_notes": "stated_analyst_notes",
    })

    # Keep only the Part 2 columns needed for the authenticity index
    keep_lived = lived[[
        "ticker",
        "company_name",
        "sector",
        "year",
        "document_type",
        "source",
        "filing_date",
        "accession_number",
        "document_url",
        "lived_text_len",
        "lived_has_text",
        "theme_categories",
        "theme_counts_json",
        "theme_counts_per_10k_json",
        "tone_positive",
        "tone_negative",
        "tone_net",
        "analyst_notes",
    ]].rename(columns={
        "theme_categories": "lived_theme_categories",
        "theme_counts_json": "lived_theme_counts_json",
        "theme_counts_per_10k_json": "lived_theme_counts_per_10k_json",
        "tone_positive": "lived_tone_positive",
        "tone_negative": "lived_tone_negative",
        "tone_net": "lived_tone_net",
        "analyst_notes": "lived_analyst_notes",
    })

    # Merge Part 1 and Part 2 into one company-year table
    merged = keep_stated.merge(
        keep_lived,
        on=["ticker", "company_name", "sector", "year"],
        how="outer"
    )

    rows = []

    # Calculate alignment components and the final index for each company-year
    for _, row in merged.iterrows():
        stated_themes = parse_theme_set(row.get("stated_theme_categories", ""))
        lived_themes = parse_theme_set(row.get("lived_theme_categories", ""))

        stated_counts = safe_json_loads(row.get("stated_theme_counts_json", "{}"))
        lived_counts = safe_json_loads(row.get("lived_theme_counts_json", "{}"))

        stated_len = row.get("stated_text_len", 0)
        lived_len = row.get("lived_text_len", 0)

        stated_vec = counts_to_vector(stated_counts, stated_len)
        lived_vec = counts_to_vector(lived_counts, lived_len)

        # Component 1: shared value categories between stated and lived documents
        theme_overlap = jaccard_similarity(stated_themes, lived_themes)
        # Component 2: similarity in how strongly each document emphasizes the themes
        theme_emphasis_similarity = cosine_similarity(stated_vec, lived_vec)
        # Component 3: similarity in broad tone direction
        tone_sim = tone_alignment(row.get("stated_tone_net"), row.get("lived_tone_net"))

        stated_ok = bool(row.get("stated_has_text", False))
        lived_ok = bool(row.get("lived_has_text", False))

        both_available = stated_ok and lived_ok

        # Only calculate the index when both documents have usable text
        if both_available:
            # Reweight available components if one component is missing
            weighted_components = []

            if not pd.isna(theme_overlap):
                weighted_components.append((theme_overlap, 0.40))

            if not pd.isna(theme_emphasis_similarity):
                weighted_components.append((theme_emphasis_similarity, 0.45))

            if not pd.isna(tone_sim):
                weighted_components.append((tone_sim, 0.15))

            if weighted_components:
                total_weight = sum(weight for _, weight in weighted_components)
                authenticity_index = sum(
                    value * weight for value, weight in weighted_components
                ) / total_weight
            else:
                authenticity_index = np.nan
        else:
            authenticity_index = np.nan

        row_dict = row.to_dict()
        row_dict.update({
            "both_texts_available": both_available,
            "theme_overlap_jaccard": round(theme_overlap, 4) if not pd.isna(theme_overlap) else np.nan,
            "theme_emphasis_cosine": round(theme_emphasis_similarity, 4) if not pd.isna(theme_emphasis_similarity) else np.nan,
            "tone_alignment": round(tone_sim, 4) if not pd.isna(tone_sim) else np.nan,
            "authenticity_index": round(authenticity_index, 4) if not pd.isna(authenticity_index) else np.nan,
            "authenticity_label": authenticity_label(authenticity_index),
        })

        rows.append(row_dict)

    # Save the company-year index and then create company and sector summaries
    out = pd.DataFrame(rows)

    out.to_csv(OUT_FILE, index=False)

    # Company-level averages show how the measure varies across firms
    summary = (
        out.groupby(["ticker", "company_name", "sector"])
        .agg(
            years=("year", "count"),
            usable_years=("both_texts_available", "sum"),
            avg_authenticity_index=("authenticity_index", "mean"),
            avg_theme_overlap=("theme_overlap_jaccard", "mean"),
            avg_theme_emphasis_similarity=("theme_emphasis_cosine", "mean"),
            avg_tone_alignment=("tone_alignment", "mean"),
        )
        .reset_index()
    )

    summary["coverage_for_index"] = summary["usable_years"] / summary["years"]
    summary = summary.sort_values(["avg_authenticity_index", "coverage_for_index"], ascending=[False, False])
    summary.to_csv(SUMMARY_FILE, index=False)

    # Sector-level averages give a broader comparison across industries
    sector_summary = (
        out.groupby("sector")
        .agg(
            rows=("year", "count"),
            usable_rows=("both_texts_available", "sum"),
            avg_authenticity_index=("authenticity_index", "mean"),
            avg_theme_overlap=("theme_overlap_jaccard", "mean"),
            avg_theme_emphasis_similarity=("theme_emphasis_cosine", "mean"),
            avg_tone_alignment=("tone_alignment", "mean"),
        )
        .reset_index()
    )

    sector_summary["coverage_for_index"] = sector_summary["usable_rows"] / sector_summary["rows"]
    sector_summary = sector_summary.sort_values("avg_authenticity_index", ascending=False)
    sector_summary.to_csv(SECTOR_FILE, index=False)

    # Quick sanity check after running 
    print("Saved:", OUT_FILE)
    print("Saved:", SUMMARY_FILE)
    print("Saved:", SECTOR_FILE)

    print("\nShape:", out.shape)

    print("\nCoverage for authenticity index:")
    print(round(out["both_texts_available"].mean(), 3))

    print("\nAverage authenticity index:")
    print(round(out["authenticity_index"].mean(), 3))

    print("\nAuthenticity label counts:")
    print(out["authenticity_label"].value_counts(dropna=False))

    print("\nAverage authenticity by sector:")
    print(sector_summary[[
        "sector",
        "coverage_for_index",
        "avg_authenticity_index",
        "avg_theme_overlap",
        "avg_theme_emphasis_similarity",
        "avg_tone_alignment"
    ]].to_string(index=False))

    print("\nTop 10 companies by average authenticity index:")
    print(summary.head(10)[[
        "ticker",
        "company_name",
        "sector",
        "coverage_for_index",
        "avg_authenticity_index",
        "avg_theme_overlap",
        "avg_theme_emphasis_similarity",
        "avg_tone_alignment"
    ]].to_string(index=False))

    print("\nBottom 10 companies by average authenticity index:")
    print(summary.tail(10)[[
        "ticker",
        "company_name",
        "sector",
        "coverage_for_index",
        "avg_authenticity_index",
        "avg_theme_overlap",
        "avg_theme_emphasis_similarity",
        "avg_tone_alignment"
    ]].to_string(index=False))


if __name__ == "__main__":
    main()