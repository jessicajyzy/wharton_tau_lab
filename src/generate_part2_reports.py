"""
Generate Part 2 lived-values reports.

This script enriches the proxy-statement dataset with normalized theme measures,
within-company trend fields, sector-year summaries, and external-event summaries.
"""

import json
from difflib import SequenceMatcher

import pandas as pd

# Minimum cleaned-text length used to treat a proxy statement as usable
MIN_TEXT_LEN = 1000

# Input and output files for Part 2 reporting
INPUT_FILE = "outputs/lived_values/lived_values_company_year.csv"

COMPANY_COVERAGE_FILE = "outputs/lived_values/part2_company_coverage_report.csv"
MISSING_REPORT_FILE = "outputs/lived_values/part2_missing_rows_report.csv"
COMPANY_TRENDS_FILE = "outputs/lived_values/part2_company_trends.csv"
YEAR_SECTOR_SUMMARY_FILE = "outputs/lived_values/part2_year_sector_summary.csv"
EXTERNAL_EVENT_SUMMARY_FILE = "outputs/lived_values/part2_external_event_summary.csv"

# Theme order used when expanding normalized theme counts into columns
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

# Safely parse JSON fields that store theme counts
def safe_json_loads(value):
    if not isinstance(value, str) or not value.strip():
        return {}

    try:
        return json.loads(value)
    except Exception:
        return {}

# Compare proxy text with the prior usable year for the same company
def text_similarity(current_text, prior_text):
    if not isinstance(current_text, str) or not isinstance(prior_text, str):
        return None

    if len(current_text) < 500 or len(prior_text) < 500:
        return None

    # Proxy statements are very long, so compare truncated text for speed
    # This keeps the comparison reproducible while avoiding extremely slow full-document matching.
    current_sample = current_text[:20000]
    prior_sample = prior_text[:20000]

    return SequenceMatcher(None, prior_sample, current_sample).ratio()


def main():
    # Load the Part 2 proxy-statement company-year dataset
    df = pd.read_csv(INPUT_FILE)

    # Refresh text length and usable-text flags before building reports
    df["proxy_text_clean"] = df["proxy_text_clean"].fillna("")
    df["has_text"] = df["proxy_text_clean"].str.len() >= MIN_TEXT_LEN
    df["text_len"] = df["proxy_text_clean"].str.len()

    # Parse normalized theme-count JSON into separate columns
    for theme in THEMES:
        df[f"{theme}_per_10k"] = df["theme_counts_per_10k_json"].apply(
            lambda x: safe_json_loads(x).get(theme, 0)
        )

    theme_cols = [f"{theme}_per_10k" for theme in THEMES]

    # Create summary theme features for comparison across documents of different lengths
    df["total_theme_mentions_per_10k"] = df[theme_cols].sum(axis=1)

    df["dominant_theme"] = df[theme_cols].idxmax(axis=1).str.replace("_per_10k", "")
    df.loc[df["total_theme_mentions_per_10k"] == 0, "dominant_theme"] = ""

    # Company-level coverage report
    company_coverage = (
        df.groupby(["ticker", "company_name", "sector"])
        .agg(
            usable=("has_text", "sum"),
            total=("year", "count"),
            avg_text_len=("text_len", "mean"),
            avg_tone_net=("tone_net", "mean"),
            avg_total_theme_mentions_per_10k=("total_theme_mentions_per_10k", "mean"),
        )
        .reset_index()
    )

    company_coverage["coverage"] = company_coverage["usable"] / company_coverage["total"]

    company_coverage.to_csv(COMPANY_COVERAGE_FILE, index=False)

    # Missing rows report
    missing_rows = df[~df["has_text"]][[
        "ticker",
        "company_name",
        "sector",
        "cik",
        "year",
        "document_type",
        "source",
        "filing_date",
        "accession_number",
        "analyst_notes",
    ]]

    missing_rows.to_csv(MISSING_REPORT_FILE, index=False)

    # Within-company trend analysis
    trend_rows = []

    for ticker, group in df.sort_values(["ticker", "year"]).groupby("ticker"):
        prior_text = None
        prior_tone = None
        prior_theme_total = None
        prior_theme_vector = None

        for _, row in group.iterrows():
            has_text = bool(row["has_text"])

            # Compare the current proxy statement to the prior usable proxy statement
            if has_text and prior_text is not None:
                similarity = text_similarity(row["proxy_text_clean"], prior_text)
                changed_from_prior = similarity is not None and similarity < 0.90
            else:
                similarity = None
                changed_from_prior = None

            if has_text and prior_tone is not None:
                tone_change = row["tone_net"] - prior_tone
            else:
                tone_change = None

            if has_text and prior_theme_total is not None:
                theme_total_change = row["total_theme_mentions_per_10k"] - prior_theme_total
            else:
                theme_total_change = None

            current_theme_vector = row[theme_cols].astype(float).to_dict()

            if has_text and prior_theme_vector is not None:
                theme_shift = sum(
                    abs(current_theme_vector[col] - prior_theme_vector[col])
                    for col in theme_cols
                )
            else:
                theme_shift = None

            trend_rows.append({
                "ticker": row["ticker"],
                "company_name": row["company_name"],
                "sector": row["sector"],
                "year": row["year"],
                "has_text": row["has_text"],
                "text_len": row["text_len"],
                "tone_net": row["tone_net"],
                "tone_change_from_prior": tone_change,
                "total_theme_mentions_per_10k": row["total_theme_mentions_per_10k"],
                "theme_mentions_change_from_prior": theme_total_change,
                "dominant_theme": row["dominant_theme"],
                "text_similarity_to_prior": similarity,
                "changed_from_prior": changed_from_prior,
                "theme_shift_from_prior": theme_shift,
            })

            # Update prior-year reference values only when the current row has usable text
            if has_text:
                prior_text = row["proxy_text_clean"]
                prior_tone = row["tone_net"]
                prior_theme_total = row["total_theme_mentions_per_10k"]
                prior_theme_vector = current_theme_vector

    trends = pd.DataFrame(trend_rows)
    trends.to_csv(COMPANY_TRENDS_FILE, index=False)

    # Cross-year and cross-sector summary
    year_sector_summary = (
        df.groupby(["year", "sector"])
        .agg(
            rows=("ticker", "count"),
            usable=("has_text", "sum"),
            coverage=("has_text", "mean"),
            avg_text_len=("text_len", "mean"),
            avg_tone_net=("tone_net", "mean"),
            avg_total_theme_mentions_per_10k=("total_theme_mentions_per_10k", "mean"),
            avg_diversity_inclusion_per_10k=("diversity_inclusion_per_10k", "mean"),
            avg_sustainability_environment_per_10k=("sustainability_environment_per_10k", "mean"),
            avg_employees_culture_per_10k=("employees_culture_per_10k", "mean"),
            avg_integrity_ethics_trust_per_10k=("integrity_ethics_trust_per_10k", "mean"),
        )
        .reset_index()
    )

    year_sector_summary.to_csv(YEAR_SECTOR_SUMMARY_FILE, index=False)

    # External-event windows
    # These are broad interpretation windows rather than causal claims
    df["event_period"] = "pre_2020"
    df.loc[df["year"].between(2020, 2021), "event_period"] = "covid_2020_2021"
    df.loc[df["year"].between(2022, 2024), "event_period"] = "post_2021"

    external_event_summary = (
        df.groupby(["event_period", "sector"])
        .agg(
            rows=("ticker", "count"),
            usable=("has_text", "sum"),
            coverage=("has_text", "mean"),
            avg_tone_net=("tone_net", "mean"),
            avg_total_theme_mentions_per_10k=("total_theme_mentions_per_10k", "mean"),
            avg_diversity_inclusion_per_10k=("diversity_inclusion_per_10k", "mean"),
            avg_sustainability_environment_per_10k=("sustainability_environment_per_10k", "mean"),
            avg_employees_culture_per_10k=("employees_culture_per_10k", "mean"),
            avg_health_safety_wellbeing_per_10k=("health_safety_wellbeing_per_10k", "mean"),
        )
        .reset_index()
    )

    external_event_summary.to_csv(EXTERNAL_EVENT_SUMMARY_FILE, index=False)

    # Save enriched main file back to disk
    df.to_csv(INPUT_FILE, index=False)

    # Print a short summary to check coverage and main reporting outputs
    print("Saved:", INPUT_FILE)
    print("Saved:", COMPANY_COVERAGE_FILE)
    print("Saved:", MISSING_REPORT_FILE)
    print("Saved:", COMPANY_TRENDS_FILE)
    print("Saved:", YEAR_SECTOR_SUMMARY_FILE)
    print("Saved:", EXTERNAL_EVENT_SUMMARY_FILE)

    print("\nShape:", df.shape)
    print("\nOverall coverage:", round(df["has_text"].mean(), 3))

    print("\nCoverage by year:")
    print(df.groupby("year")["has_text"].mean().round(3))

    print("\nCoverage by sector:")
    print(df.groupby("sector")["has_text"].mean().round(3))

    print("\nAverage tone by sector:")
    print(df.groupby("sector")["tone_net"].mean().round(3))

    print("\nAverage total theme mentions per 10k words by sector:")
    print(df.groupby("sector")["total_theme_mentions_per_10k"].mean().round(3))


if __name__ == "__main__":
    main()