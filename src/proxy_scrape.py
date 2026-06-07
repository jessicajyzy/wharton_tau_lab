"""
Part 2 scraper for lived-values disclosure documents.

This script collects DEF 14A proxy statements from SEC EDGAR, extracts clean
proxy text, applies theme and tone scoring, and saves one row per company-year.
"""

import argparse
import json
import re
import time
import warnings
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from tqdm import tqdm

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Project paths and output folders
BASE_DIR = Path(__file__).resolve().parents[1]

COMPANY_FILE = BASE_DIR / "data" / "companies.csv"
RAW_DIR = BASE_DIR / "data" / "raw" / "proxy_html"
OUT_DIR = BASE_DIR / "outputs" / "lived_values"

RAW_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Assignment window for proxy filings
YEARS = range(2016, 2025)

# SEC requires a descriptive User-Agent for automated requests
HEADERS = {
    "User-Agent": "Jessica Yang research assignment contact: jyzy@seas.upenn.edu",
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov",
}

DATA_HEADERS = {
    "User-Agent": "Jessica Yang research assignment contact: jyzy@seas.upenn.edu",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov",
}

SLEEP_SECONDS = 0.15
MIN_TEXT_LEN = 1000

# Same broad value categories used in Part 1, with a few proxy-relevant terms added
THEMES = {
    "innovation": [
        "innovation", "innovative", "technology", "digital", "research",
        "science", "engineering", "data", "platform", "ai"
    ],
    "customer_focus": [
        "customer", "customers", "client", "clients", "consumer",
        "users", "service", "experience"
    ],
    "employees_culture": [
        "employee", "employees", "people", "team", "culture",
        "talent", "workforce", "workplace", "associates", "human capital"
    ],
    "diversity_inclusion": [
        "diversity", "inclusion", "inclusive", "equity",
        "belonging", "dei", "equal opportunity", "gender", "race", "ethnicity"
    ],
    "sustainability_environment": [
        "sustainability", "sustainable", "climate", "environment",
        "environmental", "carbon", "emissions", "renewable", "esg"
    ],
    "community_social_impact": [
        "community", "communities", "social impact", "philanthropy",
        "giving", "volunteer", "society"
    ],
    "integrity_ethics_trust": [
        "integrity", "ethics", "ethical", "trust", "responsibility",
        "accountability", "compliance", "transparency", "governance"
    ],
    "health_safety_wellbeing": [
        "health", "safety", "wellbeing", "well-being", "patients",
        "care", "quality"
    ],
    "financial_performance_growth": [
        "growth", "shareholder", "value", "performance",
        "returns", "investment", "financial", "compensation"
    ],
}

# Simple word lists for a rough tone measure
POSITIVE_WORDS = [
    "strong", "effective", "successful", "improve", "improved", "progress",
    "opportunity", "responsible", "sustainable", "commitment", "committed",
    "support", "inclusive", "diverse", "ethical", "transparent"
]

NEGATIVE_WORDS = [
    "risk", "risks", "challenge", "challenges", "uncertain", "uncertainty",
    "loss", "decline", "weakness", "concern", "litigation", "violation",
    "failure", "adverse", "material adverse"
]

def clean_text(text):
    if not isinstance(text, str):
        return ""

    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# Strip HTML tags and keep the visible filing text
def extract_text(html):
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript", "svg", "ix:header"]):
        tag.decompose()

    return clean_text(soup.get_text(" "))

# Count exact term matches using word boundaries
def score_terms(text, terms):
    text = text.lower()
    total = 0

    for term in terms:
        pattern = r"\b" + re.escape(term.lower()) + r"\b"
        total += len(re.findall(pattern, text))

    return total

# Count how often each value category appears in the proxy text
def score_themes(text):
    counts = {}

    for theme, words in THEMES.items():
        counts[theme] = score_terms(text, words)

    present = [theme for theme, count in counts.items() if count > 0]
    return present, counts

# Calculate a simple net tone score from positive and negative term counts
def score_tone(text):
    positive = score_terms(text, POSITIVE_WORDS)
    negative = score_terms(text, NEGATIVE_WORDS)
    total = positive + negative

    if total == 0:
        net = 0
    else:
        net = (positive - negative) / total

    return positive, negative, round(net, 4)

# Load SEC submission metadata for a company using its CIK
def get_submission_json(cik):
    cik_str = str(int(cik)).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_str}.json"

    r = requests.get(url, headers=DATA_HEADERS, timeout=20)
    r.raise_for_status()

    return r.json()

def recent_filings_to_df(data):
    recent = data.get("filings", {}).get("recent", {})

    if not recent:
        return pd.DataFrame()

    return pd.DataFrame(recent)

def extra_filings_to_df(data):
    rows = []
    files = data.get("filings", {}).get("files", [])

    for item in files:
        name = item.get("name")
        if not name:
            continue

        url = f"https://data.sec.gov/submissions/{name}"

        try:
            r = requests.get(url, headers=DATA_HEADERS, timeout=20)
            r.raise_for_status()
            sub = r.json()
        except Exception:
            continue

        df = recent_filings_to_df({"filings": {"recent": sub}})
        if len(df):
            rows.append(df)

        time.sleep(SLEEP_SECONDS)

    if rows:
        return pd.concat(rows, ignore_index=True)

    return pd.DataFrame()

# Combine recent and older SEC filing metadata into one table
def all_filings_df(data):
    recent = recent_filings_to_df(data)
    older = extra_filings_to_df(data)

    parts = [df for df in [recent, older] if len(df)]

    if not parts:
        return pd.DataFrame()

    df = pd.concat(parts, ignore_index=True)
    df = df.drop_duplicates(subset=["accessionNumber", "primaryDocument"], keep="first")

    return df

# Select the first DEF 14A filing for the target year
def pick_proxy_by_year(filings, year):
    if filings.empty:
        return None

    df = filings.copy()
    df = df[df["form"].astype(str).str.upper() == "DEF 14A"]
    df["filingDate"] = pd.to_datetime(df["filingDate"], errors="coerce")
    df = df[df["filingDate"].dt.year == year]

    if df.empty:
        return None

    df = df.sort_values("filingDate")
    return df.iloc[0].to_dict()

def filing_document_url(cik, accession, primary_doc):
    cik_clean = str(int(cik))
    acc_clean = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{acc_clean}/{primary_doc}"

# Download the proxy statement HTML, retrying if the request fails
def download_proxy(cik, accession, primary_doc):
    url = filing_document_url(cik, accession, primary_doc)

    last_error = ""

    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.text, url, f"downloaded on attempt {attempt + 1}"
        except Exception as e:
            last_error = str(e)
            time.sleep(1.5 * (attempt + 1))

    return "", url, f"download failed after 3 attempts: {last_error}"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=None)
    parser.add_argument("--n", type=int, default=None)
    parser.add_argument("--tickers", nargs="*", default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    companies = pd.read_csv(COMPANY_FILE)

    if args.tickers:
        companies = companies[companies["ticker"].isin(args.tickers)]

    if args.start is not None and args.n is not None:
        companies = companies.iloc[args.start:args.start + args.n]
    elif args.n is not None:
        companies = companies.head(args.n)

    rows = []
    logs = []

    # Main collection loop: one proxy row is created for every company-year
    for _, company in tqdm(companies.iterrows(), total=len(companies)):
        ticker = company["ticker"]
        cik = company["cik"]

        print(f"Getting SEC index for {ticker}")

        try:
            data = get_submission_json(cik)
            filings = all_filings_df(data)
            index_note = "SEC submissions loaded."
        except Exception as e:
            filings = pd.DataFrame()
            index_note = f"SEC submissions failed: {e}"

        for year in YEARS:
            time.sleep(SLEEP_SECONDS)

            base = {
                "ticker": ticker,
                "company_name": company["company_name"],
                "sector": company["sector"],
                "cik": cik,
                "year": year,
                "document_type": "DEF 14A proxy statement",
                "source": "SEC EDGAR",
            }

            if filings.empty:
                note = index_note
                rows.append({
                    **base,
                    "filing_date": "",
                    "accession_number": "",
                    "filing_url": "",
                    "document_url": "",
                    "proxy_text_clean": "",
                    "text_len": 0,
                    "theme_categories": "",
                    "theme_counts_json": "{}",
                    "theme_counts_per_10k_json": "{}",
                    "tone_positive": 0,
                    "tone_negative": 0,
                    "tone_net": 0,
                    "has_text": False,
                    "analyst_notes": note,
                })
                logs.append({**base, "status": "missing", "notes": note})
                continue

            filing = pick_proxy_by_year(filings, year)

            if filing is None:
                note = "No DEF 14A filing found for this filing year."
                rows.append({
                    **base,
                    "filing_date": "",
                    "accession_number": "",
                    "filing_url": "",
                    "document_url": "",
                    "proxy_text_clean": "",
                    "text_len": 0,
                    "theme_categories": "",
                    "theme_counts_json": "{}",
                    "theme_counts_per_10k_json": "{}",
                    "tone_positive": 0,
                    "tone_negative": 0,
                    "tone_net": 0,
                    "has_text": False,
                    "analyst_notes": note,
                })
                logs.append({**base, "status": "missing", "notes": note})
                continue

            accession = filing["accessionNumber"]
            primary_doc = filing["primaryDocument"]
            filing_date = filing["filingDate"].strftime("%Y-%m-%d")
            filing_url = filing.get("primaryDocDescription", "")

            html, document_url, download_note = download_proxy(cik, accession, primary_doc)
            text = extract_text(html) if html else ""
            text_len = len(text)
            has_text = text_len >= MIN_TEXT_LEN

            # Save the raw proxy HTML so the selected filing can be checked later
            if html:
                raw_path = RAW_DIR / f"{ticker}_{year}_{accession.replace('-', '')}.html"
                raw_path.write_text(html, encoding="utf-8", errors="ignore")

            # Apply text-mining features used later in the authenticity index
            themes, theme_counts = score_themes(text)
            pos, neg, net = score_tone(text)

            if has_text:
                note = f"{download_note}. Clean text length: {text_len}. Themes: {', '.join(themes) if themes else 'none'}."
                status = "success"
            else:
                note = f"{download_note}. Text too short or unavailable. Clean text length: {text_len}."
                status = "missing"

            rows.append({
                **base,
                "filing_date": filing_date,
                "accession_number": accession,
                "filing_url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}",
                "document_url": document_url,
                "proxy_text_clean": text,
                "text_len": text_len,
                "theme_categories": ";".join(themes),
                "theme_counts_json": json.dumps(theme_counts),
                "theme_counts_per_10k_json": json.dumps({
                    k: round(v / max(text_len, 1) * 10000, 4)
                    for k, v in theme_counts.items()
                }),
                "tone_positive": pos,
                "tone_negative": neg,
                "tone_net": net,
                "has_text": has_text,
                "analyst_notes": note,
            })

            logs.append({**base, "status": status, "notes": note})
            
    # Save both the structured lived-values dataset and a collection log
    df = pd.DataFrame(rows)
    log = pd.DataFrame(logs)

    df.to_csv(OUT_DIR / "lived_values_company_year.csv", index=False)
    log.to_csv(OUT_DIR / "part2_collection_log.csv", index=False)

    print("Saved:", OUT_DIR / "lived_values_company_year.csv")
    print("Saved:", OUT_DIR / "part2_collection_log.csv")
    print("Shape:", df.shape)

    if len(df):
        print("\nOverall coverage:")
        print(round(df["has_text"].mean(), 3))

        print("\nCoverage by year:")
        print(df.groupby("year")["has_text"].mean().round(3))

        print("\nCoverage by sector:")
        print(df.groupby("sector")["has_text"].mean().round(3))


if __name__ == "__main__":
    main()