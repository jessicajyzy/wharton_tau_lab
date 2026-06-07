"""
LLM-assisted analysis layer for Part 1 stated-values pages.

This script sends usable stated-values text to Gemini, asks for structured
theme and change annotations, and merges the LLM fields back into the Part 1 dataset.
"""

import argparse
import json
import os
import time
from pathlib import Path

import pandas as pd
import requests

# Project paths and final Part 1 LLM output files
BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = BASE_DIR / "outputs" / "stated_values" / "stated_values_company_year.csv"
OUT_DIR = BASE_DIR / "outputs" / "stated_values"

LLM_OUTPUT_FILE = OUT_DIR / "part1_llm_analysis_final.csv"
MERGED_OUTPUT_FILE = OUT_DIR / "stated_values_company_year_with_llm_final.csv"

MIN_TEXT_LEN = 400
MAX_TEXT_CHARS = 6000
SLEEP_SECONDS = 4

# Allowed categories are kept fixed so LLM output stays comparable across rows
VALUE_CATEGORIES = [
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

# Load the Gemini API key from .env without hard-coding it in the script
def load_env_file():
    env_path = BASE_DIR / ".env"

    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())

# Limit page text length so prompts stay manageable and cheaper to run
def truncate_text(text, max_chars=MAX_TEXT_CHARS):
    if not isinstance(text, str):
        return ""

    text = text.strip()

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n\n[TRUNCATED]"

# Build a structured prompt for one company-year stated-values page
def build_prompt(row):
    text = truncate_text(row.get("page_text_clean", ""))

    return f"""
You are helping with a research assignment on organizational authenticity and corporate value alignment.

Analyze this archived corporate stated-values page. The page is an About Us, mission, values, purpose, responsibility, sustainability, or equivalent corporate values page.

Company: {row.get("company_name")}
Ticker: {row.get("ticker")}
Sector: {row.get("sector")}
Year: {row.get("year")}
Selected URL: {row.get("wayback_original_url")}
Rule-based theme categories already detected: {row.get("theme_categories")}
Rule-based changed_from_prior value: {row.get("changed_from_prior")}
Rule-based text similarity to prior usable year: {row.get("text_similarity_to_prior")}

Allowed value categories:
{", ".join(VALUE_CATEGORIES)}

Cleaned page text:
{text}

Return JSON only, with this exact structure:
{{
  "llm_theme_categories": ["category_1", "category_2"],
  "llm_changed_from_prior": true,
  "llm_change_reason": "brief explanation of whether the page appears materially changed from the prior usable year",
  "llm_main_values_summary": "2-3 sentence plain-English summary of the main values emphasized",
  "llm_linguistic_shift": "brief note on any notable linguistic shift, or 'No clear linguistic shift visible from this snapshot alone'",
  "llm_confidence": "high",
  "llm_notes": "brief caveat if needed"
}}

Rules:
- Use only the allowed value categories.
- If the prior-year information is missing or unclear, set llm_changed_from_prior to null.
- Do not invent information beyond the page text.
- Keep explanations concise.
- Return valid JSON only.
"""

# Parse the model response and recover JSON even if extra text appears around it
def parse_json_response(text):
    if not isinstance(text, str):
        return {}

    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return {}

    return {}

# Call Gemini directly through the REST API and request JSON output
def call_gemini(api_key, model, prompt):
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }

    r = requests.post(url, json=payload, timeout=90)

    if r.status_code != 200:
        raise RuntimeError(f"Gemini API error {r.status_code}: {r.text[:800]}")

    data = r.json()

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise RuntimeError(f"Could not parse Gemini response: {json.dumps(data)[:800]}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--tickers", nargs="*", default=None)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()

    load_env_file()

    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing. Add it to your .env file.")

    # Load Part 1 rows and keep only rows with usable scraped text
    df = pd.read_csv(INPUT_FILE)
    df["has_text"] = df["page_text_clean"].fillna("").str.len() >= MIN_TEXT_LEN

    usable = df[df["has_text"]].copy()

    if args.tickers:
        usable = usable[usable["ticker"].isin(args.tickers)]

    if args.limit is not None:
        usable = usable.head(args.limit)

    # Resume safely by skipping rows that already have successful LLM results
    if LLM_OUTPUT_FILE.exists() and not args.overwrite:
        existing = pd.read_csv(LLM_OUTPUT_FILE)

        # Only skip rows that were successfully analyzed
        # Error rows should be retried on the next run
        successful = existing[existing["llm_status"] == "success"].copy()

        done_keys = set(
            zip(
                successful["ticker"].astype(str),
                successful["year"].astype(int),
            )
        )
    else:
        existing = pd.DataFrame()
        done_keys = set()

    rows = []

    # Analyze each remaining usable company-year row
    for _, row in usable.iterrows():
        key = (str(row["ticker"]), int(row["year"]))

        if key in done_keys:
            continue

        print(f"LLM analyzing {row['ticker']} {row['year']}")

        prompt = build_prompt(row)

        try:
            raw_response = call_gemini(api_key, model, prompt)
            parsed = parse_json_response(raw_response)
            status = "success" if parsed else "parse_failed"
            error = ""
        except Exception as e:
            raw_response = ""
            parsed = {}
            status = "error"
            error = str(e)

        rows.append({
            "ticker": row["ticker"],
            "company_name": row["company_name"],
            "sector": row["sector"],
            "year": row["year"],
            "wayback_original_url": row.get("wayback_original_url", ""),
            "rule_theme_categories": row.get("theme_categories", ""),
            "rule_changed_from_prior": row.get("changed_from_prior", ""),
            "rule_text_similarity_to_prior": row.get("text_similarity_to_prior", ""),
            "llm_theme_categories": ";".join(parsed.get("llm_theme_categories", [])) if parsed else "",
            "llm_changed_from_prior": parsed.get("llm_changed_from_prior", "") if parsed else "",
            "llm_change_reason": parsed.get("llm_change_reason", "") if parsed else "",
            "llm_main_values_summary": parsed.get("llm_main_values_summary", "") if parsed else "",
            "llm_linguistic_shift": parsed.get("llm_linguistic_shift", "") if parsed else "",
            "llm_confidence": parsed.get("llm_confidence", "") if parsed else "",
            "llm_notes": parsed.get("llm_notes", "") if parsed else "",
            "llm_status": status,
            "llm_error": error,
            "llm_raw_response": raw_response,
        })

        time.sleep(SLEEP_SECONDS)

    # Combine new LLM results with any earlier successful runs
    new_results = pd.DataFrame(rows)

    if len(existing) and len(new_results):
        out = pd.concat([existing, new_results], ignore_index=True)
    elif len(existing):
        out = existing
    else:
        out = new_results

    if len(out):
        out = out.drop_duplicates(subset=["ticker", "year"], keep="last")
        out = out.sort_values(["ticker", "year"])

    out.to_csv(LLM_OUTPUT_FILE, index=False)

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

    # Merge LLM fields back into the full 450-row Part 1 dataset
    merged = df.merge(
        out[merge_cols] if len(out) else pd.DataFrame(columns=merge_cols),
        on=["ticker", "year"],
        how="left",
    )

    merged.to_csv(MERGED_OUTPUT_FILE, index=False)

    print("Saved:", LLM_OUTPUT_FILE)
    print("Saved:", MERGED_OUTPUT_FILE)
    print("LLM rows:", len(out))
    print("Merged shape:", merged.shape)

    if len(out):
        print("\nLLM status counts:")
        print(out["llm_status"].value_counts(dropna=False))

        print("\nLLM confidence counts:")
        print(out["llm_confidence"].value_counts(dropna=False))


if __name__ == "__main__":
    main()