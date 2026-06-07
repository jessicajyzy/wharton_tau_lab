"""
Part 1 scraper for archived stated-values pages

This script searches the Wayback Machine for company About/mission/values pages,
extracts usable body text, applies rule-based theme coding, and saves one row
per company-year for 2016-2024.
"""

import argparse
import json
import re
import time
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Project paths and output folders
BASE_DIR = Path(__file__).resolve().parents[1]

COMPANY_FILE = BASE_DIR / "data" / "companies.csv"
RAW_DIR = BASE_DIR / "data" / "raw" / "wayback_html"
OUT_DIR = BASE_DIR / "outputs" / "stated_values"

RAW_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Assignment window: one archived snapshot per company-year
YEARS = range(2016, 2025)
CDX_URL = "https://web.archive.org/cdx"

HEADERS = {
    "User-Agent": "Jessica Yang research assignment contact: jyzy@seas.upenn.edu"
}

MIN_TEXT_LEN = 400
REVIEW_TEXT_LEN = 1000
MAX_CANDIDATES_TO_DOWNLOAD = 8
SLEEP_SECONDS = 0.05

# Value categories used for the rule-based stated-values coding
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
        "talent", "workforce", "workplace", "associates"
    ],
    "diversity_inclusion": [
        "diversity", "inclusion", "inclusive", "equity",
        "belonging", "dei", "equal opportunity"
    ],
    "sustainability_environment": [
        "sustainability", "sustainable", "climate", "environment",
        "environmental", "carbon", "emissions", "renewable"
    ],
    "community_social_impact": [
        "community", "communities", "social impact", "philanthropy",
        "giving", "volunteer", "society"
    ],
    "integrity_ethics_trust": [
        "integrity", "ethics", "ethical", "trust", "responsibility",
        "accountability", "compliance", "transparency"
    ],
    "health_safety_wellbeing": [
        "health", "safety", "wellbeing", "well-being", "patients",
        "care", "quality"
    ],
    "financial_performance_growth": [
        "growth", "shareholder", "value", "performance",
        "returns", "investment", "financial"
    ],
}

# Backup URLs help when a company's current About page changed or moved over time
BACKUP_URLS = {
    "MSFT": [
        "https://news.microsoft.com/facts-about-microsoft/",
        "https://www.microsoft.com/en-us/about",
    ],
    "AAPL": [
        "https://www.apple.com/diversity/",
        "https://www.apple.com/environment/",
        "https://www.apple.com/privacy/",
        "https://www.apple.com/accessibility/",
        "https://www.apple.com/leadership/",
    ],
    "NVDA": [
        "https://www.nvidia.com/en-us/about-nvidia/",
        "https://www.nvidia.com/en-us/about-nvidia/company-information/",
        "https://www.nvidia.com/en-us/about-nvidia/corporate-social-responsibility/",
        "https://www.nvidia.com/object/corporate.html",
        "https://www.nvidia.com/object/corporate_profile.html",
        "https://www.nvidia.com/page/about_us.html",
    ],
    "GOOGL": [
        "https://abc.xyz/",
        "https://abc.xyz/about/",
        "https://about.google/",
        "https://about.google/intl/en/",
        "https://www.google.com/about/",
        "https://www.google.com/intl/en/about/",
        "https://www.google.com/about/company/",
        "https://www.google.com/intl/en/about/company/",
        "https://www.google.com/corporate/",
        "https://www.google.com/intl/en/corporate/",
    ],
    "META": [
        "https://about.meta.com/company-info/",
        "https://about.fb.com/company-info/",
        "https://about.facebook.com/company-info/",
        "https://newsroom.fb.com/company-info/",
        "https://newsroom.fb.com/company-info/leadership/",
        "https://www.facebook.com/company-info/",
        "https://www.facebook.com/facebook/info/",
    ],
    "AVGO": [
        "https://www.broadcom.com/company/about-us",
        "https://www.broadcom.com/company",
        "https://www.broadcom.com/company/citizenship",
        "https://www.broadcom.com/company/corporate-responsibility",
    ],
    "CRM": [
        "https://www.salesforce.com/company/",
        "https://www.salesforce.com/company/about-us/",
        "https://www.salesforce.com/company/values/",
        "https://www.salesforce.com/company/sustainability/",
    ],
    "ORCL": [
        "https://www.oracle.com/corporate/",
        "https://www.oracle.com/corporate/about/",
        "https://www.oracle.com/corporate/citizenship/",
    ],
    "IBM": [
        "https://www.ibm.com/about",
        "https://www.ibm.com/impact",
        "https://www.ibm.com/corporate-responsibility",
    ],
    "INTC": [
        "https://www.intel.com/content/www/us/en/company-overview/company-overview.html",
        "https://www.intel.com/content/www/us/en/company-overview/overview.html",
        "https://www.intel.com/content/www/us/en/corporate-responsibility/corporate-responsibility.html",
        "https://www.intel.com/content/www/us/en/diversity/diversity-at-intel.html",
        "https://www.intel.com/content/www/us/en/history/historic-timeline.html",
        "https://www.intel.com/content/www/us/en/newsroom/resources/intel-overview.html",
        "https://newsroom.intel.com/company-overview/",
        "https://newsroom.intel.com/corporate/",
    ],
    "BRK.B": [
        "https://www.berkshirehathaway.com/",
    ],
    "JPM": [
        "https://www.jpmorganchase.com/about",
        "https://www.jpmorganchase.com/about/our-business",
        "https://www.jpmorganchase.com/about/our-company",
    ],
    "BAC": [
        "https://about.bankofamerica.com/en",
        "https://about.bankofamerica.com/en/our-company",
        "https://about.bankofamerica.com/en/making-an-impact",
    ],
    "WFC": [
        "https://www.wellsfargo.com/about/",
        "https://www.wellsfargo.com/about/corporate/",
        "https://www.wellsfargo.com/about/corporate-responsibility/",
    ],
    "GS": [
        "https://www.goldmansachs.com/about-us/",
        "https://www.goldmansachs.com/our-firm/",
        "https://www.goldmansachs.com/who-we-are/",
        "https://www.goldmansachs.com/sustainability/",
    ],
    "MS": [
        "https://www.morganstanley.com/about-us",
        "https://www.morganstanley.com/about-us/global-offices",
        "https://www.morganstanley.com/about-us/sustainability-at-morgan-stanley",
    ],
    "BLK": [
        "https://www.blackrock.com/corporate/about-us",
        "https://www.blackrock.com/corporate/about-us/leadership",
        "https://www.blackrock.com/corporate/sustainability",
    ],
    "SCHW": [
        "https://www.schwab.com/about",
        "https://www.aboutschwab.com/",
        "https://www.aboutschwab.com/what-we-do",
        "https://www.aboutschwab.com/citizenship",
    ],
    "AXP": [
        "https://www.americanexpress.com/en-us/company/",
        "https://about.americanexpress.com/",
        "https://about.americanexpress.com/company-and-culture/default.aspx",
        "https://about.americanexpress.com/corporate-sustainability/default.aspx",
    ],
    "C": [
        "https://www.citigroup.com/global/about-us",
        "https://www.citigroup.com/global/about-us/our-company",
        "https://www.citigroup.com/global/our-impact",
    ],

    "LLY": [
        "https://www.lilly.com/who-we-are",
        "https://www.lilly.com/about",
        "https://www.lilly.com/sustainability",
        "https://www.lilly.com/our-medicines",
    ],
    "UNH": [
        "https://www.unitedhealthgroup.com/about.html",
        "https://www.unitedhealthgroup.com/who-we-are.html",
        "https://www.unitedhealthgroup.com/sustainability.html",
    ],
    "JNJ": [
        "https://www.jnj.com/about-jnj",
        "https://www.jnj.com/our-company",
        "https://www.jnj.com/about-jnj/company-statements",
    ],
    "ABBV": [
        "https://www.abbvie.com/who-we-are.html",
        "https://www.abbvie.com/our-company.html",
        "https://www.abbvie.com/societal-impact.html",
    ],
    "MRK": [
        "https://www.merck.com/company-overview/",
        "https://www.merck.com/about/",
        "https://www.merck.com/company-overview/responsibility/",
    ],
    "TMO": [
        "https://www.thermofisher.com/us/en/home/about-us.html",
        "https://corporate.thermofisher.com/en/about.html",
        "https://www.thermofisher.com/us/en/home/about-us/corporate-social-responsibility.html",
    ],
    "ABT": [
        "https://www.abbott.com/about-abbott.html",
        "https://www.abbott.com/responsibility.html",
        "https://www.abbott.com/about-abbott/who-we-are.html",
    ],
    "PFE": [
        "https://www.pfizer.com/about",
        "https://www.pfizer.com/about/responsibility",
        "https://www.pfizer.com/about/purpose",
    ],
    "MDT": [
        "https://www.medtronic.com/us-en/about.html",
        "https://www.medtronic.com/us-en/our-company.html",
        "https://www.medtronic.com/us-en/about/citizenship.html",
    ],
    "BMY": [
        "https://www.bms.com/about-us.html",
        "https://www.bms.com/about-us/our-company.html",
        "https://www.bms.com/about-us/responsibility.html",
    ],

    "AMZN": [
        "https://www.aboutamazon.com/about-us",
        "https://www.aboutamazon.com/who-we-are",
        "https://www.aboutamazon.com/workplace",
        "https://sustainability.aboutamazon.com/",
    ],
    "TSLA": [
        "https://www.tesla.com/about",
        "https://www.tesla.com/impact",
    ],
    "HD": [
        "https://corporate.homedepot.com/page/about-us",
        "https://corporate.homedepot.com/about",
        "https://corporate.homedepot.com/page/responsibility",
    ],
    "MCD": [
        "https://corporate.mcdonalds.com/corpmcd/our-company/who-we-are.html",
        "https://corporate.mcdonalds.com/corpmcd/about-us.html",
        "https://corporate.mcdonalds.com/corpmcd/our-purpose-and-impact.html",
    ],
    "NKE": [
        "https://about.nike.com/en",
        "https://about.nike.com/",
        "https://www.nike.com/about",
        "https://purpose.nike.com/",
        "https://purpose.nike.com/diversity-equity-inclusion",
        "https://purpose.nike.com/sustainability",
    ],
    "SBUX": [
        "https://www.starbucks.com/about-us/",
        "https://www.starbucks.com/responsibility/",
        "https://stories.starbucks.com/stories/people/",
        "https://stories.starbucks.com/stories/sustainability/",
    ],
    "TGT": [
        "https://corporate.target.com/about",
        "https://corporate.target.com/about/purpose-history",
        "https://corporate.target.com/sustainability-governance",
        "https://corporate.target.com/sustainability-governance/target-forward",
    ],
    "LOW": [
        "https://corporate.lowes.com/who-we-are",
        "https://corporate.lowes.com/our-purpose",
        "https://corporate.lowes.com/responsibility",
        "https://corporate.lowes.com/newsroom/stories/inside-lowes/who-we-are",
    ],
    "TJX": [
        "https://www.tjx.com/company",
        "https://www.tjx.com/company/about-us",
        "https://www.tjx.com/responsibility",
    ],
    "F": [
        "https://corporate.ford.com/about.html",
        "https://corporate.ford.com/company.html",
        "https://corporate.ford.com/social-impact.html",
    ],

    "XOM": [
        "https://corporate.exxonmobil.com/who-we-are",
        "https://corporate.exxonmobil.com/about-us",
        "https://corporate.exxonmobil.com/company-overview",
        "https://corporate.exxonmobil.com/sustainability",
    ],
    "CVX": [
        "https://www.chevron.com/who-we-are",
        "https://www.chevron.com/about",
        "https://www.chevron.com/sustainability",
    ],
    "COP": [
        "https://www.conocophillips.com/about-us/",
        "https://www.conocophillips.com/sustainability/",
    ],
    "EOG": [
        "https://www.eogresources.com/about",
        "https://www.eogresources.com/responsibility",
        "https://www.eogresources.com/sustainability",
    ],
    "SLB": [
        "https://www.slb.com/about",
        "https://www.slb.com/sustainability",
        "https://www.slb.com/about/who-we-are",
    ],
    "MPC": [
        "https://www.marathonpetroleum.com/About/",
        "https://www.marathonpetroleum.com/Sustainability/",
        "https://www.marathonpetroleum.com/Responsibility/",
    ],
    "PSX": [
        "https://www.phillips66.com/about/",
        "https://www.phillips66.com/who-we-are/",
        "https://www.phillips66.com/sustainability/",
    ],
    "VLO": [
        "https://www.valero.com/about",
        "https://www.valero.com/about/overview",
        "https://www.valero.com/sustainability",
    ],
    "OXY": [
        "https://www.oxy.com/about/",
        "https://www.oxy.com/who-we-are/",
        "https://www.oxy.com/sustainability/",
    ],
    "HAL": [
        "https://www.halliburton.com/en/about-us",
        "https://www.halliburton.com/en/sustainability",
        "https://www.halliburton.com/en/about-us/corporate-profile",
    ],
}

# Historical URL patterns handle companies whose corporate pages were renamed or restructured
HISTORICAL_URLS = {
    "NVDA": {
        "early": [
            "https://www.nvidia.com/page/about_us.html",
            "https://www.nvidia.com/object/corporate_profile.html",
            "https://www.nvidia.com/object/corporate.html",
            "https://www.nvidia.com/object/about-nvidia.html",
            "https://www.nvidia.com/object/company-information.html",
        ],
        "recent": [
            "https://www.nvidia.com/en-us/about-nvidia/",
            "https://www.nvidia.com/en-us/about-nvidia/company-information/",
            "https://www.nvidia.com/en-us/about-nvidia/corporate-social-responsibility/",
        ],
    },
    "GOOGL": {
        "early": [
            "https://www.google.com/about/company/",
            "https://www.google.com/intl/en/about/company/",
            "https://www.google.com/about/",
            "https://www.google.com/intl/en/about/",
            "https://www.google.com/corporate/",
            "https://www.google.com/intl/en/corporate/",
            "https://abc.xyz/",
        ],
        "recent": [
            "https://abc.xyz/",
            "https://about.google/",
            "https://about.google/intl/en/",
            "https://www.google.com/about/",
            "https://www.google.com/intl/en/about/",
        ],
    },
    "META": {
        "early": [
            "https://newsroom.fb.com/company-info/",
            "https://newsroom.fb.com/company-info/leadership/",
            "https://about.fb.com/company-info/",
            "https://about.facebook.com/company-info/",
            "https://www.facebook.com/company-info/",
            "https://www.facebook.com/facebook/info/",
        ],
        "recent": [
            "https://about.meta.com/company-info/",
            "https://about.fb.com/company-info/",
            "https://about.facebook.com/company-info/",
            "https://newsroom.fb.com/company-info/",
        ],
    },
    "NKE": {
        "early": [
            "https://about.nike.com/",
            "https://news.nike.com/news/nike-company-profile",
            "https://www.nike.com/us/en_us/c/about",
            "https://purpose.nike.com/",
        ],
        "recent": [
            "https://about.nike.com/en",
            "https://purpose.nike.com/",
            "https://purpose.nike.com/sustainability",
            "https://purpose.nike.com/diversity-equity-inclusion",
        ],
    },
    "TSLA": {
        "early": [
            "https://www.tesla.com/about",
            "https://www.tesla.com/blog/about-tesla",
            "https://www.tesla.com/about/legal",
        ],
        "recent": [
            "https://www.tesla.com/about",
            "https://www.tesla.com/impact",
        ],
    },
    "XOM": {
        "early": [
            "https://corporate.exxonmobil.com/en/company/about-us",
            "https://corporate.exxonmobil.com/en/company/who-we-are",
            "https://corporate.exxonmobil.com/company/about-us",
            "https://corporate.exxonmobil.com/company/who-we-are",
        ],
        "recent": [
            "https://corporate.exxonmobil.com/who-we-are",
            "https://corporate.exxonmobil.com/about-us",
            "https://corporate.exxonmobil.com/sustainability",
        ],
    },
    "GS": {
        "early": [
            "https://www.goldmansachs.com/who-we-are/",
            "https://www.goldmansachs.com/our-firm/",
            "https://www.goldmansachs.com/about-us/",
        ],
        "recent": [
            "https://www.goldmansachs.com/about-us/",
            "https://www.goldmansachs.com/our-firm/",
            "https://www.goldmansachs.com/sustainability/",
        ],
    },
    "INTC": {
        "early": [
            "http://www.intel.com/content/www/us/en/company-overview/company-overview.html",
            "https://www.intel.com/content/www/us/en/company-overview/company-overview.html",
            "https://www.intel.com/content/www/us/en/company-overview/overview.html",
            "https://www.intel.com/content/www/us/en/history/historic-timeline.html",
            "https://newsroom.intel.com/company-overview/",
        ],
        "recent": [
            "https://www.intel.com/content/www/us/en/company-overview/company-overview.html",
            "https://www.intel.com/content/www/us/en/corporate-responsibility/corporate-responsibility.html",
            "https://www.intel.com/content/www/us/en/diversity/diversity-at-intel.html",
            "https://www.intel.com/content/www/us/en/newsroom/resources/intel-overview.html",
        ],
    },
    "TGT": {
        "early": [
            "https://corporate.target.com/about",
            "https://corporate.target.com/about/purpose-history",
            "https://corporate.target.com/corporate-responsibility",
        ],
        "recent": [
            "https://corporate.target.com/about",
            "https://corporate.target.com/about/purpose-history",
            "https://corporate.target.com/sustainability-governance",
            "https://corporate.target.com/sustainability-governance/target-forward",
        ],
    },
    "LOW": {
        "early": [
            "https://corporate.lowes.com/who-we-are",
            "https://corporate.lowes.com/about",
            "https://corporate.lowes.com/our-purpose",
        ],
        "recent": [
            "https://corporate.lowes.com/who-we-are",
            "https://corporate.lowes.com/our-purpose",
            "https://corporate.lowes.com/responsibility",
        ],
    },
    "PSX": {
        "early": [
            "https://www.phillips66.com/about/",
            "https://www.phillips66.com/who-we-are/",
            "https://www.phillips66.com/company/about/",
        ],
        "recent": [
            "https://www.phillips66.com/about/",
            "https://www.phillips66.com/who-we-are/",
            "https://www.phillips66.com/sustainability/",
        ],
    },
    "LLY": {
        "early": [
            "https://www.lilly.com/who-we-are",
            "https://www.lilly.com/about",
            "https://www.lilly.com/our-medicines",
        ],
        "recent": [
            "https://www.lilly.com/who-we-are",
            "https://www.lilly.com/about",
            "https://www.lilly.com/sustainability",
        ],
    },
    "TMO": {
        "early": [
            "https://www.thermofisher.com/us/en/home/about-us.html",
            "https://corporate.thermofisher.com/en/about.html",
            "https://www.thermofisher.com/us/en/home/about-us/corporate-social-responsibility.html",
        ],
        "recent": [
            "https://corporate.thermofisher.com/en/about.html",
            "https://www.thermofisher.com/us/en/home/about-us.html",
            "https://www.thermofisher.com/us/en/home/about-us/corporate-social-responsibility.html",
        ],
    },
    "AVGO": {
        "early": [
            "https://www.broadcom.com/company/about-us",
            "https://www.broadcom.com/company",
            "https://www.broadcom.com/company/citizenship",
        ],
        "recent": [
            "https://www.broadcom.com/company/about-us",
            "https://www.broadcom.com/company",
            "https://www.broadcom.com/company/citizenship",
            "https://www.broadcom.com/company/corporate-responsibility",
        ],
    },
}

# URL terms that make a candidate more likely to be a relevant corporate values page
STRONG_KEEP = [
    "about", "about-us", "about_us", "company", "company-info",
    "company-profile", "our-company", "who-we-are", "whoweare",
    "our-firm", "mission", "purpose", "values", "corporate",
    "corporate-profile", "corporate_profile", "overview",
    "facts-about", "responsibility", "citizenship"
]

VALUES_KEEP = [
    "diversity", "inclusion", "environment", "sustainability",
    "responsibility", "accessibility", "privacy", "citizenship",
    "impact", "community", "culture", "ethics", "trust"
]

# URL terms that usually indicate non-values pages and should be filtered out
DROP_WORDS = [
    "shop", "store", "buy", "cart", "checkout", "product", "products",
    "iphone", "ipad", "macbook", "microsoft-365", "azure", "cloud-pricing",
    "support", "download", "developer", "developers", "itunes", "login",
    "account", "careers", "jobs", "job", "investor", "investors",
    "press-release", "blog", "calendar", "event",
    "events", "webcast", "podcast", "contact", "search", "security.txt",
    "sitemap", "rss", "pdf", "jpg", "png", "javascript", "research_projects",
    "captioneditor", "cookie", "privacychoices"
]


def norm_url(url):
    if not isinstance(url, str):
        return ""

    url = url.strip()
    url = url.replace("–", "-").replace("—", "-").replace("−", "-")
    return url


def domain_from_url(url):
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if not host and "/" not in url:
        host = url.lower()

    return host.replace("www.", "")


def clean_text(text):
    if not isinstance(text, str):
        return ""

    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# Extract visible body text while removing scripts, navigation, footers, and common boilerplate
def extract_text(html):
    if not html:
        return ""

    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        tag.decompose()

    bad_words = [
        "cookie", "breadcrumb", "newsletter", "subscribe",
        "social", "modal", "popup", "menu"
    ]

    tags = list(soup.find_all(True))

    for tag in tags:
        if tag is None or tag.name is None:
            continue

        try:
            attrs = " ".join([
                " ".join(tag.get("class", [])) if isinstance(tag.get("class"), list) else str(tag.get("class", "")),
                str(tag.get("id", "")),
                str(tag.get("role", "")),
            ]).lower()
        except Exception:
            continue

        if any(word in attrs for word in bad_words):
            try:
                tag.decompose()
            except Exception:
                pass

    text = clean_text(soup.get_text(" "))

    if len(text) >= MIN_TEXT_LEN:
        return text

    fallback_bits = []

    for key in ["description", "og:description", "twitter:description"]:
        tag = soup.find("meta", attrs={"name": key}) or soup.find("meta", attrs={"property": key})
        if tag and tag.get("content"):
            fallback_bits.append(tag.get("content"))

    for tag in soup.find_all(["title", "h1", "h2", "h3", "p", "li"]):
        bit = clean_text(tag.get_text(" "))
        if len(bit) > 20:
            fallback_bits.append(bit)

    for tag in soup.find_all(attrs={"data-testid": True}):
        bit = clean_text(tag.get_text(" "))
        if len(bit) > 20:
            fallback_bits.append(bit)

    fallback_text = clean_text(" ".join(fallback_bits))

    if len(fallback_text) > len(text):
        return fallback_text

    return text

# Score candidate URLs so About/values pages outrank generic or irrelevant pages
def score_url(original, seed_domain):
    u = original.lower()
    parsed = urlparse(original)
    path = parsed.path.lower()
    host = parsed.netloc.lower().replace("www.", "")

    if seed_domain and seed_domain not in host:
        return -100

    if any(word in u for word in DROP_WORDS):
        return -100

    # Allow company-info pages on newsroom-style domains, but reject random news pages
    if "newsroom" in u and "company-info" not in u:
        return -100

    if "article" in u and not any(x in u for x in ["company-info", "about", "values", "purpose"]):
        return -100

    score = 0

    for word in STRONG_KEEP:
        if word in path:
            score += 25

    for word in VALUES_KEEP:
        if word in path:
            score += 12

    # Homepages can sometimes be acceptable for holding-company sites like abc.xyz,
    # but they should not beat explicit About/Values pages
    if path in ["", "/"]:
        score += 10

    # Prefer shorter corporate pages over deep nested pages
    path_parts = [p for p in path.strip("/").split("/") if p]

    if len(path_parts) <= 2:
        score += 8
    elif len(path_parts) >= 5:
        score -= 10

    # Query parameters are usually tracking/referral noise
    if parsed.query:
        score -= 8

    # Small boost for English/localized company pages
    if "/en-us/" in path or "/en/" in path or "/intl/en/" in path:
        score += 3

    # Extra boosts for historically useful company-page patterns
    if "company-info" in path:
        score += 20

    if "corporate_profile" in path or "corporate-profile" in path:
        score += 20

    if "about_us" in path or "about-us" in path:
        score += 15

    # Avoid very generic pages unless they are from a manually curated backup
    if score == 0:
        return -100

    return score

def page_type_from_url(url):
    u = url.lower()

    if any(word in u for word in ["mission", "purpose", "values"]):
        return "mission_values_page"

    if any(word in u for word in ["diversity", "inclusion", "environment", "sustainability", "accessibility", "privacy"]):
        return "values_subpage"

    if any(word in u for word in ["about", "company", "who-we-are", "corporate", "overview", "facts-about"]):
        return "about_company_page"

    return "domain_discovered_page"

# Query the Wayback CDX API for archived HTML captures in a specific year
def get_cdx_rows(search_url, year, match_type, limit=3000):
    params = {
        "url": search_url,
        "matchType": match_type,
        "from": f"{year}0101",
        "to": f"{year}1231",
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype,digest",
        "filter": "statuscode:200",
        "collapse": "digest",
        "limit": str(limit),
    }

    r = requests.get(CDX_URL, params=params, headers=HEADERS, timeout=8)

    if r.status_code == 404:
        return []

    r.raise_for_status()
    data = r.json()

    if len(data) <= 1:
        return []

    return data[1:]

# Build exact, prefix, and domain fallback searches for each company-year
def build_searches(ticker, seed_url, year):
    seed_url = norm_url(seed_url)

    urls = [seed_url] + BACKUP_URLS.get(ticker, [])

    if ticker in HISTORICAL_URLS:
        if year <= 2020:
            urls = HISTORICAL_URLS[ticker].get("early", []) + urls
        else:
            urls = HISTORICAL_URLS[ticker].get("recent", []) + urls

    urls = [norm_url(u) for u in urls if norm_url(u)]
    urls = list(dict.fromkeys(urls))

    searches = []

    for u in urls:
        d = domain_from_url(u)

        searches.append({
            "search_url": u,
            "match_type": "exact",
            "source": "exact_seed_or_backup",
            "seed_domain": d,
        })

        searches.append({
            "search_url": u.rstrip("/") + "/",
            "match_type": "exact",
            "source": "exact_seed_or_backup_slash",
            "seed_domain": d,
        })

        searches.append({
            "search_url": u,
            "match_type": "prefix",
            "source": "prefix_seed_or_backup",
            "seed_domain": d,
        })

    seen_domains = list(dict.fromkeys([domain_from_url(u) for u in urls if domain_from_url(u)]))

    for d in seen_domains:
        searches.append({
            "search_url": d,
            "match_type": "domain",
            "source": "domain_fallback",
            "seed_domain": d,
        })

    return searches

# Collect and rank candidate archived pages before downloading the best options
def collect_candidates(ticker, seed_url, year):
    candidates = []
    notes = []

    for search in build_searches(ticker, seed_url, year):
        try:
            rows = get_cdx_rows(
                search["search_url"],
                year,
                search["match_type"],
                limit=1000 if search["match_type"] == "domain" else 350,
            )
        except Exception as e:
            notes.append(f"{search['source']} failed: {e}")
            continue

        if not rows:
            notes.append(f"{search['source']} no captures")
            continue

        for row in rows:
            if len(row) != 5:
                continue

            timestamp, original, statuscode, mimetype, digest = row
            mimetype = str(mimetype).lower()

            if "html" not in mimetype:
                continue

            page_score = score_url(original, search["seed_domain"])

            if page_score < 15:
                continue

            candidates.append({
                "timestamp": timestamp,
                "original": original,
                "mimetype": mimetype,
                "digest": digest,
                "selection_method": search["source"],
                "page_score": page_score,
                "page_type": page_type_from_url(original),
            })

        # Keep searching unless we have several strong candidates
        strong_candidates = [c for c in candidates if c["page_score"] >= 35]

        if len(strong_candidates) >= 8 and search["source"] != "domain_fallback":
            break

        if len(candidates) >= 15:
            break

    deduped = {}
    for c in candidates:
        key = (c["timestamp"], c["original"], c["digest"])
        deduped[key] = c

    candidates = list(deduped.values())
    target = int(f"{year}0701000000")

    candidates.sort(
        key=lambda c: (
            -c["page_score"],
            abs(int(c["timestamp"]) - target)
        )
    )

    return candidates, notes


def download_html(timestamp, original):
    archive_url = f"https://web.archive.org/web/{timestamp}id_/{original}"

    try:
        r = requests.get(archive_url, headers=HEADERS, timeout=5, allow_redirects=True)
        r.raise_for_status()
        return r.text, archive_url, "downloaded"
    except Exception as e:
        return "", archive_url, f"download failed: {e}"

# Try top-ranked candidates and select the first one with usable stated-values text
def choose_snapshot(ticker, seed_url, year):
    candidates, notes = collect_candidates(ticker, seed_url, year)

    if not candidates:
        return None, "No candidate URL passed filters. " + " | ".join(notes[:6])

    tried = []

    bad_text_markers = [
        "wayback machine",
        "page cannot be displayed",
        "access denied",
        "403 forbidden",
        "404 not found",
        "server error",
        "something has gone wrong on our end",
        "technical went wrong on our site",
        "enable javascript",
        "please enable javascript",
        "browser is not supported",
        "temporarily unavailable",
    ]

    for c in candidates[:MAX_CANDIDATES_TO_DOWNLOAD]:
        html, capture_url, download_note = download_html(c["timestamp"], c["original"])
        text = extract_text(html) if html else ""

        text_lower = text.lower()
        bad_text = any(marker in text_lower[:1000] for marker in bad_text_markers)

        tried.append(
            f"{c['original']} len={len(text)} score={c['page_score']} bad_text={bad_text}"
        )

        if len(text) >= MIN_TEXT_LEN and not bad_text:
            c["html"] = html
            c["text"] = text
            c["capture_url"] = capture_url
            c["download_note"] = download_note
            c["needs_review"] = (
                c["selection_method"] == "domain_fallback"
                or c["page_score"] < 30
                or len(text) < REVIEW_TEXT_LEN
            )
            return c, f"Selected usable candidate. Tried {len(tried)} candidate(s)."

    return None, "Candidates found but none produced usable text. " + " | ".join(tried[:8])

# Count value-theme keywords in the cleaned page text
def score_themes(text):
    text = text.lower()
    counts = {}

    for theme, words in THEMES.items():
        total = 0

        for word in words:
            pattern = r"\b" + re.escape(word.lower()) + r"\b"
            total += len(re.findall(pattern, text))

        counts[theme] = total

    present = [theme for theme, count in counts.items() if count > 0]
    return present, counts

# Compare each usable page with the prior usable year for the same company
def compare_to_prior(text, prior_text):
    if prior_text is None or len(prior_text) < 200 or len(text) < 200:
        return None, None, "No reliable prior-year comparison."

    similarity = SequenceMatcher(None, prior_text, text).ratio()
    changed = similarity < 0.90

    if changed:
        note = f"Changed from prior usable year; similarity={similarity:.3f}."
    else:
        note = f"Similar to prior usable year; similarity={similarity:.3f}."

    return changed, similarity, note


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

    # Main scraping loop: one company-year row is produced for every company and year
    for _, company in tqdm(companies.iterrows(), total=len(companies)):
        ticker = company["ticker"]
        prior_text = None

        for year in YEARS:
            time.sleep(SLEEP_SECONDS)
            print(f"Working on {ticker} {year}")

            base = {
                "ticker": ticker,
                "company_name": company["company_name"],
                "sector": company["sector"],
                "year": year,
                "source_url_seed": company["about_url"],
            }

            chosen, selection_note = choose_snapshot(ticker, company["about_url"], year)

            if chosen is None:
                row = {
                    **base,
                    "wayback_timestamp": "",
                    "wayback_original_url": "",
                    "wayback_capture_url": "",
                    "page_text_clean": "",
                    "changed_from_prior": "",
                    "text_similarity_to_prior": "",
                    "theme_categories": "",
                    "theme_counts_json": "{}",
                    "selection_method": "",
                    "selected_page_type": "",
                    "selected_page_score": "",
                    "needs_review": True,
                    "analyst_notes": selection_note,
                }

                rows.append(row)
                logs.append({**base, "status": "missing", "notes": selection_note})
                continue
            # Save the raw archived HTML so selected captures can be audited later
            html_path = RAW_DIR / f"{ticker}_{year}_{chosen['timestamp']}.html"
            html_path.write_text(chosen["html"], encoding="utf-8", errors="ignore")

            text = chosen["text"]
            themes, theme_counts = score_themes(text)
            changed, similarity, change_note = compare_to_prior(text, prior_text)

            notes = " ".join([
                selection_note,
                chosen["download_note"],
                change_note,
                f"Clean text length: {len(text)}.",
                f"URL score: {chosen['page_score']}.",
                f"Page type: {chosen['page_type']}.",
                f"Themes: {', '.join(themes) if themes else 'none'}."
            ])

            row = {
                **base,
                "wayback_timestamp": chosen["timestamp"],
                "wayback_original_url": chosen["original"],
                "wayback_capture_url": chosen["capture_url"],
                "page_text_clean": text,
                "changed_from_prior": changed,
                "text_similarity_to_prior": similarity,
                "theme_categories": ";".join(themes),
                "theme_counts_json": json.dumps(theme_counts),
                "selection_method": chosen["selection_method"],
                "selected_page_type": chosen["page_type"],
                "selected_page_score": chosen["page_score"],
                "needs_review": chosen["needs_review"],
                "analyst_notes": notes,
            }

            rows.append(row)

            status = "review" if chosen["needs_review"] else "success"
            logs.append({**base, "status": status, "notes": notes})

            if len(text) >= 200:
                prior_text = text

    # Convert collected rows into the final dataset and collection log
    df = pd.DataFrame(rows)
    log = pd.DataFrame(logs)

    df["has_text"] = df["page_text_clean"].fillna("").str.len() >= MIN_TEXT_LEN

    df.to_csv(OUT_DIR / "stated_values_company_year.csv", index=False)
    log.to_csv(OUT_DIR / "part1_collection_log.csv", index=False)

    print("Saved:", OUT_DIR / "stated_values_company_year.csv")
    print("Saved:", OUT_DIR / "part1_collection_log.csv")
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