"""
Generate Part 1 coverage reports.

This script refreshes the usable-text flag for stated-values pages and creates
company-level coverage and missing-row reports.
"""

import pandas as pd

# Minimum cleaned-text length used to treat a stated-values page as usable
MIN_TEXT_LEN = 400

# Input and output files for Part 1 reporting
INPUT_FILE = "outputs/stated_values/stated_values_company_year.csv"
COMPANY_REPORT_FILE = "outputs/stated_values/part1_company_coverage_report.csv"
MISSING_REPORT_FILE = "outputs/stated_values/part1_missing_rows_report.csv"


def main():
    # Load the Part 1 company-year stated-values dataset
    df = pd.read_csv(INPUT_FILE)

    # Add/refresh a simple usable-text flag
    df["has_text"] = df["page_text_clean"].fillna("").str.len() >= MIN_TEXT_LEN
    df.to_csv(INPUT_FILE, index=False)

    print("Overall coverage:", round(df["has_text"].mean(), 3))

    print("\nCoverage by year:")
    print(df.groupby("year")["has_text"].mean().round(3))

    print("\nCoverage by sector:")
    print(df.groupby("sector")["has_text"].mean().round(3))

    # Summarize coverage and review counts at the company level
    company_coverage = (
        df.groupby(["ticker", "company_name", "sector"])
        .agg(
            usable=("has_text", "sum"),
            total=("year", "count"),
            review_rows=("needs_review", "sum"),
            avg_text_len=("page_text_clean", lambda x: x.fillna("").str.len().mean()),
        )
        .reset_index()
    )

    company_coverage["coverage"] = company_coverage["usable"] / company_coverage["total"]

    # Keep a separate file explaining company-years without usable stated-values text
    missing_rows = df[~df["has_text"]][
        ["ticker", "company_name", "sector", "year", "source_url_seed", "analyst_notes"]
    ]

    # Save the Part 1 reporting outputs
    company_coverage.to_csv(COMPANY_REPORT_FILE, index=False)
    missing_rows.to_csv(MISSING_REPORT_FILE, index=False)

    print("\nSaved:")
    print(COMPANY_REPORT_FILE)
    print(MISSING_REPORT_FILE)


if __name__ == "__main__":
    main()