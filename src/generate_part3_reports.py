"""
Generate reporting files for Part 3.

This script summarizes the authenticity index distribution, variation over time,
a simple top/bottom validity check, and key threats to validity.
"""

import pandas as pd

# Inputs from the main authenticity index script and outputs for Part 3 reporting
INPUT_FILE = "outputs/authenticity/authenticity_company_year.csv"
COMPANY_FILE = "outputs/authenticity/authenticity_summary_by_company.csv"
SECTOR_FILE = "outputs/authenticity/authenticity_summary_by_sector.csv"

DISTRIBUTION_FILE = "outputs/authenticity/part3_distribution_summary.csv"
YEAR_SUMMARY_FILE = "outputs/authenticity/part3_year_summary.csv"
VALIDITY_FILE = "outputs/authenticity/part3_validity_check.csv"
LIMITATIONS_FILE = "outputs/authenticity/part3_limitations_notes.csv"


def main():
    # Load company-year scores plus company and sector summaries
    df = pd.read_csv(INPUT_FILE)
    company = pd.read_csv(COMPANY_FILE)
    sector = pd.read_csv(SECTOR_FILE)

    # Distributional properties of the index and components
    metrics = [
        "authenticity_index",
        "theme_overlap_jaccard",
        "theme_emphasis_cosine",
        "tone_alignment",
    ]

    distribution = (
        df[metrics]
        .describe()
        .T
        .reset_index()
        .rename(columns={"index": "metric"})
    )

    distribution.to_csv(DISTRIBUTION_FILE, index=False)

    # Variation over time
    year_summary = (
        df.groupby("year")
        .agg(
            rows=("ticker", "count"),
            usable_rows=("both_texts_available", "sum"),
            coverage_for_index=("both_texts_available", "mean"),
            avg_authenticity_index=("authenticity_index", "mean"),
            median_authenticity_index=("authenticity_index", "median"),
            avg_theme_overlap=("theme_overlap_jaccard", "mean"),
            avg_theme_emphasis_similarity=("theme_emphasis_cosine", "mean"),
            avg_tone_alignment=("tone_alignment", "mean"),
        )
        .reset_index()
    )

    year_summary.to_csv(YEAR_SUMMARY_FILE, index=False)

    # Simple validity check:
    # compare top and bottom firms and inspect whether the component scores
    # move in the same direction as the overall index
    valid_company = company.dropna(subset=["avg_authenticity_index"]).copy()

    top = valid_company.sort_values(
        ["avg_authenticity_index", "coverage_for_index"],
        ascending=[False, False],
    ).head(10)

    bottom = valid_company.sort_values(
        ["avg_authenticity_index", "coverage_for_index"],
        ascending=[True, False],
    ).head(10)

    top = top.copy()
    bottom = bottom.copy()

    top["validity_group"] = "top_10_alignment"
    bottom["validity_group"] = "bottom_10_alignment"

    validity = pd.concat([top, bottom], ignore_index=True)

    validity["validity_interpretation"] = validity.apply(
        lambda row: (
            "High-scoring company: stated and lived documents have relatively stronger theme overlap, "
            "theme-emphasis similarity, or tone alignment."
            if row["validity_group"] == "top_10_alignment"
            else
            "Low-scoring company: stated and lived documents have weaker measured alignment or limited usable coverage."
        ),
        axis=1,
    )

    validity.to_csv(VALIDITY_FILE, index=False)

    # Notes on limitations + threats to validity
    limitations = pd.DataFrame([
        {
            "limitation": "Document mismatch",
            "explanation": (
                "Part 1 uses public stated-values web pages, while Part 2 uses proxy statements. "
                "These documents have different audiences and purposes, so perfect alignment is not expected."
            ),
        },
        {
            "limitation": "Text availability",
            "explanation": (
                "The index is only calculated when both stated-values text and proxy text are available. "
                "Rows with missing or unusable text are retained but labeled as insufficient data."
            ),
        },
        {
            "limitation": "Dictionary-based themes",
            "explanation": (
                "Theme categories rely on predefined keyword dictionaries. This improves transparency, "
                "but it may miss subtle or indirect language about corporate values."
            ),
        },
        {
            "limitation": "Tone is a rough proxy",
            "explanation": (
                "Tone alignment is based on positive and negative word counts. It should be read as a simple "
                "supporting signal rather than a complete sentiment analysis."
            ),
        },
        {
            "limitation": "Not causal",
            "explanation": (
                "The authenticity index measures language alignment. It does not prove that a company actually "
                "behaves authentically or that specific events caused changes in the score."
            ),
        },
    ])

    limitations.to_csv(LIMITATIONS_FILE, index=False)

    # Print a compact audit trail so the run can be checked from the terminal
    print("Saved:", DISTRIBUTION_FILE)
    print("Saved:", YEAR_SUMMARY_FILE)
    print("Saved:", VALIDITY_FILE)
    print("Saved:", LIMITATIONS_FILE)

    print("\nDistribution summary:")
    print(distribution.to_string(index=False))

    print("\nYear summary:")
    print(year_summary.to_string(index=False))

    print("\nTop validity-check firms:")
    print(top[[
        "ticker",
        "company_name",
        "sector",
        "coverage_for_index",
        "avg_authenticity_index",
        "avg_theme_overlap",
        "avg_theme_emphasis_similarity",
        "avg_tone_alignment",
    ]].to_string(index=False))

    print("\nBottom validity-check firms:")
    print(bottom[[
        "ticker",
        "company_name",
        "sector",
        "coverage_for_index",
        "avg_authenticity_index",
        "avg_theme_overlap",
        "avg_theme_emphasis_similarity",
        "avg_tone_alignment",
    ]].to_string(index=False))


if __name__ == "__main__":
    main()