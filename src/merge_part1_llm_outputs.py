"""
Merge final Part 1 LLM annotations into the base stated-values dataset.

This script keeps the original 450 company-year rows and adds LLM-generated
theme, change, summary, and confidence fields where available.
"""

from pathlib import Path

import pandas as pd

# Input and output paths for the final Part 1 LLM merge
BASE_DIR = Path(__file__).resolve().parents[1]

MAIN_FILE = BASE_DIR / "outputs" / "stated_values" / "stated_values_company_year.csv"
FINAL_LLM_FILE = BASE_DIR / "outputs" / "stated_values" / "part1_llm_analysis_final.csv"
FINAL_MERGED_FILE = BASE_DIR / "outputs" / "stated_values" / "stated_values_company_year_with_llm_final.csv"


def main():
    # Load the base stated-values dataset and the final LLM annotation file
    main_df = pd.read_csv(MAIN_FILE)
    llm_df = pd.read_csv(FINAL_LLM_FILE)

    # Only merge the LLM fields needed for the final enriched dataset
    merge_cols = [
        "ticker",
        "year",
        "llm_theme_categories",
        "llm_changed_from_prior",
        "llm_change_reason",
        "llm_main_values_summary",
        "llm_linguistic_shift",
        "llm_confidence",
        "llm_notes",
        "llm_status",
    ]

    # Left join preserves all company-year rows, including rows without usable text
    merged = main_df.merge(
        llm_df[merge_cols],
        on=["ticker", "year"],
        how="left",
    )

    # Save the final LLM-enriched Part 1 dataset
    merged.to_csv(FINAL_MERGED_FILE, index=False)

    print("Saved:", FINAL_MERGED_FILE)
    print("Main shape:", main_df.shape)
    print("LLM shape:", llm_df.shape)
    print("Merged shape:", merged.shape)

    print("\nLLM status counts:")
    print(llm_df["llm_status"].value_counts(dropna=False))

    print("\nMerged LLM status counts:")
    print(merged["llm_status"].value_counts(dropna=False))


if __name__ == "__main__":
    main()