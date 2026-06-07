"""
Part 4 exploratory extension.

This script looks beyond the final authenticity score and asks what kind of
alignment gap is driving lower scores: different themes, different emphasis,
tone differences, or insufficient data.
"""

import pandas as pd

# Input from Part 3 and output files for the Part 4 diagnostic analysis
INPUT_FILE = "outputs/authenticity/authenticity_company_year.csv"

OUT_FILE = "outputs/extension/part4_gap_type_company_year.csv"
SUMMARY_FILE = "outputs/extension/part4_gap_type_summary.csv"
SECTOR_FILE = "outputs/extension/part4_gap_type_by_sector.csv"
YEAR_FILE = "outputs/extension/part4_gap_type_by_year.csv"
DRIVER_FILE = "outputs/extension/part4_gap_driver_summary.csv"
EXAMPLES_FILE = "outputs/extension/part4_representative_examples.csv"
SECTOR_YEAR_FILE = "outputs/extension/part4_sector_year_diagnostic.csv"

# Classify each company-year into a diagnostic gap type using Part 3 components
def classify_gap(row):
    if not row["both_texts_available"] or pd.isna(row["authenticity_index"]):
        return "insufficient_data"

    overlap = row["theme_overlap_jaccard"]
    emphasis = row["theme_emphasis_cosine"]
    tone = row["tone_alignment"]

    # Strong overlap and strong emphasis similarity indicate clear alignment
    if overlap >= 0.60 and emphasis >= 0.50:
        return "high_alignment"

    # The same themes appear, but the two documents prioritize them differently
    if overlap >= 0.60 and emphasis < 0.50:
        return "same_themes_different_emphasis"

    # Theme overlap is weak, but the broad tone still points in a similar direction
    if overlap < 0.60 and tone >= 0.70:
        return "different_themes_similar_tone"

    # Low overlap and weak emphasis similarity suggest a broader mismatch
    return "broad_misalignment"

# Identify which component is weakest for each scored company-year
def identify_gap_driver(row):
    if not row["both_texts_available"] or pd.isna(row["authenticity_index"]):
        return "insufficient_data"

    components = {
        "theme_overlap_gap": row["theme_overlap_jaccard"],
        "theme_emphasis_gap": row["theme_emphasis_cosine"],
        "tone_gap": row["tone_alignment"],
    }

    # Lower component score means that component is the bigger weakness
    available = {
        key: value
        for key, value in components.items()
        if not pd.isna(value)
    }

    if not available:
        return "unclear"

    return min(available, key=available.get)


def main():
    # Load the Part 3 company-year authenticity output
    df = pd.read_csv(INPUT_FILE)

    # Add the two main Part 4 diagnostic fields
    df["gap_type"] = df.apply(classify_gap, axis=1)
    df["component_gap_driver"] = df.apply(identify_gap_driver, axis=1)

    # Distance from high alignment: useful for ranking how severe the gap is
    df["alignment_gap_size"] = 1 - df["authenticity_index"]
    df.loc[df["authenticity_index"].isna(), "alignment_gap_size"] = pd.NA

    # Separate scored rows from rows without enough data for the index
    scored = df[df["gap_type"] != "insufficient_data"].copy()

    # Overall gap-type summary
    summary = (
        df["gap_type"]
        .value_counts(dropna=False)
        .rename_axis("gap_type")
        .reset_index(name="rows")
    )

    summary["share_of_all_rows"] = summary["rows"] / len(df)

    scored_counts = (
        scored["gap_type"]
        .value_counts()
        .rename_axis("gap_type")
        .reset_index(name="scored_rows")
    )
    scored_counts["share_of_scored_rows"] = scored_counts["scored_rows"] / len(scored)

    summary = summary.merge(scored_counts, on="gap_type", how="left")

    # Component driver summary
    driver = (
        df["component_gap_driver"]
        .value_counts(dropna=False)
        .rename_axis("component_gap_driver")
        .reset_index(name="rows")
    )

    driver["share_of_all_rows"] = driver["rows"] / len(df)

    scored_driver = (
        scored["component_gap_driver"]
        .value_counts()
        .rename_axis("component_gap_driver")
        .reset_index(name="scored_rows")
    )
    scored_driver["share_of_scored_rows"] = scored_driver["scored_rows"] / len(scored)

    driver = driver.merge(scored_driver, on="component_gap_driver", how="left")

    # Gap type by sector
    sector = (
        df.groupby(["sector", "gap_type"])
        .size()
        .reset_index(name="rows")
    )

    sector["sector_total"] = sector.groupby("sector")["rows"].transform("sum")
    sector["share_within_sector"] = sector["rows"] / sector["sector_total"]

    # Gap type by year
    year = (
        df.groupby(["year", "gap_type"])
        .size()
        .reset_index(name="rows")
    )

    year["year_total"] = year.groupby("year")["rows"].transform("sum")
    year["share_within_year"] = year["rows"] / year["year_total"]

    # Sector-year diagnostic summary
    sector_year = (
        df.groupby(["sector", "year"])
        .agg(
            rows=("ticker", "count"),
            scored_rows=("authenticity_index", "count"),
            avg_authenticity_index=("authenticity_index", "mean"),
            avg_theme_overlap=("theme_overlap_jaccard", "mean"),
            avg_theme_emphasis_similarity=("theme_emphasis_cosine", "mean"),
            avg_tone_alignment=("tone_alignment", "mean"),
            same_themes_different_emphasis_share=(
                "gap_type",
                lambda x: (x == "same_themes_different_emphasis").mean(),
            ),
            broad_misalignment_share=(
                "gap_type",
                lambda x: (x == "broad_misalignment").mean(),
            ),
            high_alignment_share=(
                "gap_type",
                lambda x: (x == "high_alignment").mean(),
            ),
        )
        .reset_index()
    )

    # Representative examples: pick the most central or clear examples from each gap type
    examples = []

    for gap_type, group in scored.groupby("gap_type"):
        group = group.copy()

        if gap_type == "high_alignment":
            selected = group.sort_values(
                ["authenticity_index", "theme_overlap_jaccard", "theme_emphasis_cosine"],
                ascending=[False, False, False],
            ).head(5)

        elif gap_type == "same_themes_different_emphasis":
            # High overlap but low emphasis similarity makes the pattern clear
            selected = group.sort_values(
                ["theme_overlap_jaccard", "theme_emphasis_cosine"],
                ascending=[False, True],
            ).head(5)

        elif gap_type == "different_themes_similar_tone":
            # Low overlap but high tone alignment makes the pattern clear
            selected = group.sort_values(
                ["theme_overlap_jaccard", "tone_alignment"],
                ascending=[True, False],
            ).head(5)

        else:
            # Broad misalignment: lowest overall index
            selected = group.sort_values("authenticity_index").head(5)

        examples.append(selected)

    examples = pd.concat(examples, ignore_index=True)

    # Keep the example file focused on fields needed for interpretation
    example_cols = [
        "ticker",
        "company_name",
        "sector",
        "year",
        "gap_type",
        "component_gap_driver",
        "authenticity_index",
        "theme_overlap_jaccard",
        "theme_emphasis_cosine",
        "tone_alignment",
        "stated_theme_categories",
        "lived_theme_categories",
    ]

    examples = examples[example_cols]

    # Save the full diagnostic dataset and all Part 4 summary tables
    df.to_csv(OUT_FILE, index=False)
    summary.to_csv(SUMMARY_FILE, index=False)
    sector.to_csv(SECTOR_FILE, index=False)
    year.to_csv(YEAR_FILE, index=False)
    driver.to_csv(DRIVER_FILE, index=False)
    sector_year.to_csv(SECTOR_YEAR_FILE, index=False)
    examples.to_csv(EXAMPLES_FILE, index=False)

    # Print the main findings so the run can be checked from the terminal
    print("Saved:", OUT_FILE)
    print("Saved:", SUMMARY_FILE)
    print("Saved:", SECTOR_FILE)
    print("Saved:", YEAR_FILE)
    print("Saved:", DRIVER_FILE)
    print("Saved:", SECTOR_YEAR_FILE)
    print("Saved:", EXAMPLES_FILE)

    print("\nGap type summary:")
    print(summary.to_string(index=False))

    print("\nComponent gap driver summary:")
    print(driver.to_string(index=False))

    print("\nMost common scored gap type:")
    print(scored["gap_type"].value_counts().head(1))

    print("\nMost common scored component gap driver:")
    print(scored["component_gap_driver"].value_counts().head(1))

    print("\nRepresentative examples:")
    print(examples[[
        "ticker",
        "company_name",
        "sector",
        "year",
        "gap_type",
        "component_gap_driver",
        "authenticity_index",
        "theme_overlap_jaccard",
        "theme_emphasis_cosine",
        "tone_alignment",
    ]].to_string(index=False))


if __name__ == "__main__":
    main()