# wharton_tau_lab

This repository contains code, output files, and written summaries for the Organizational Authenticity & Corporate Value Alignment assignment.

The project studies whether companies’ publicly stated values align with the values emphasized in formal disclosure documents. The analysis is organized into four parts:

1. **Part 1 — Stated Values:** archived corporate About Us / mission / values pages from the Wayback Machine
2. **Part 2 — Lived Values:** proxy statement disclosure analysis
3. **Part 3 — Authenticity Index:** comparison between stated and lived values
4. **Part 4 — Summary and interpretation:** written findings and limitations

## Repository structure

* `data/companies.csv`: sample of 50 companies across five sectors
* `data/raw/wayback_html/`: raw archived HTML files downloaded from the Wayback Machine
* `data/raw/proxy_html/`: raw proxy statement HTML files
* `outputs/stated_values/`: Part 1 stated-values outputs
* `outputs/lived_values/`: Part 2 lived-values outputs
* `outputs/authenticity/`: Part 3 authenticity-index outputs
* `outputs/extension/`: Part 4 exploratory analysis outputs
* `src/`: Python scripts used for scraping, processing, and analysis
* `summaries/`: written summaries for each part
* `requirements.txt`: Python package requirements

## Setup

Install required packages with:

```bash
pip install -r requirements.txt
```

The main packages used include `pandas`, `numpy`, `requests`, `beautifulsoup4`, `lxml`, `tqdm`, and other text-processing libraries listed in `requirements.txt`.

---

# Part 1 — Stated Values

## Goal

Part 1 collects archived stated-values pages for 50 S&P 500 companies from 2016 through 2024. I treated corporate About Us, company overview, mission, values, purpose, responsibility, sustainability, and similar pages as stated-values pages.

The goal is to capture what companies publicly said they valued over time.

## Data source

I used the Internet Archive Wayback Machine CDX API to identify archived HTML snapshots. For each company-year, the scraper attempts to select one representative archived page.

The sample includes 50 companies: the 10 largest companies by market cap in each of five GICS sectors:

* Technology
* Financials
* Healthcare
* Consumer Discretionary
* Energy

The company list is stored in:

```text
data/companies.csv
```

## Page selection criteria

The scraper prioritizes URLs containing terms such as:

```text
about
company
who-we-are
mission
purpose
values
responsibility
citizenship
sustainability
```

The scraper excludes pages that appear to be product pages, shopping pages, support pages, login/account pages, investor-only pages, PDFs/images, search pages, sitemap pages, and other non-values content.

## Handling missing snapshots and redirects

If the exact company URL does not work, the scraper tries backup URLs, historical URL variants, prefix matches, and limited domain fallback.

If no candidate produces usable visible text, the row remains in the dataset but is marked as missing and explained in `analyst_notes`. I retained missing rows rather than dropping them so that coverage gaps remain visible.

## Text extraction

The scraper removes scripts, styles, navigation, headers, footers, and common boilerplate. It uses a minimum text threshold of 400 characters. Rows with short text, weaker fallback selection, lower page scores, or fallback selection methods are marked `needs_review`.

The raw archived HTML files are stored in:

```text
data/raw/wayback_html/
```

## Theme categories

I used nine value categories:

* `innovation`
* `customer_focus`
* `employees_culture`
* `diversity_inclusion`
* `sustainability_environment`
* `community_social_impact`
* `integrity_ethics_trust`
* `health_safety_wellbeing`
* `financial_performance_growth`

These categories were chosen because they capture common corporate values language and can be compared to disclosure language in later parts of the project.

## Prior-year change detection

For each company, the scraper compares each usable year to the previous usable year using text similarity. Rows are marked as changed when similarity falls below the threshold used in the code.

This creates the fields:

```text
changed_from_prior
text_similarity_to_prior
```

## LLM-assisted analysis layer

In addition to the rule-based theme coding, I added an LLM-assisted analysis layer for all usable stated-values snapshots. The LLM layer reviews the cleaned page text and returns structured fields for value categories, prior-year change assessment, a short values summary, and notable linguistic shifts.

The final merged dataset keeps all 450 company-year rows. LLM fields are available for the 385 rows with usable scraped text, while the remaining 65 rows remain documented as missing or unusable snapshots.

The final LLM output files are:

```text
outputs/stated_values/part1_llm_analysis_final.csv
outputs/stated_values/stated_values_company_year_with_llm_final.csv
```

The LLM layer is used as an interpretive enrichment layer alongside the reproducible rule-based fields.

## Running Part 1

Run the Wayback scraper with:

```bash
python3 src/wayback_scrape.py
```

After the scrape finishes, generate the Part 1 coverage and missing-row reports:

```bash
python3 src/generate_part1_reports.py
```

Run the LLM-assisted analysis layer:

```bash
python3 src/llm_part1_analysis.py
```

Merge the LLM fields into the final Part 1 dataset:

```bash
python3 src/merge_part1_llm_outputs.py
```

## Part 1 output files

The main Part 1 output files are:

```text
outputs/stated_values/stated_values_company_year.csv
outputs/stated_values/stated_values_company_year_with_llm_final.csv
outputs/stated_values/part1_llm_analysis_final.csv
outputs/stated_values/part1_collection_log.csv
outputs/stated_values/part1_company_coverage_report.csv
outputs/stated_values/part1_missing_rows_report.csv
```

The required structured dataset is:

```text
outputs/stated_values/stated_values_company_year.csv
```

The final LLM-enriched dataset is:

```text
outputs/stated_values/stated_values_company_year_with_llm_final.csv
```

The base Part 1 dataset includes one row per company-year and contains, at minimum:

```text
ticker
company_name
sector
year
page_text_clean
changed_from_prior
theme_categories
analyst_notes
```

It also includes additional fields such as selected Wayback URL, timestamp, page type, selection method, page score, review flag, and theme-count JSON.

The LLM-enriched dataset preserves the same 450 company-year structure and adds LLM-generated fields for usable rows.

## Part 1 coverage

The final Part 1 dataset contains 450 company-year rows.

```text
Overall usable-text coverage: 85.6%
Usable rows: 385 / 450
```

Coverage by year:

```text
2016    0.80
2017    0.84
2018    0.84
2019    0.90
2020    0.86
2021    0.86
2022    0.82
2023    0.88
2024    0.90
```

Coverage by sector:

```text
Consumer Discretionary    0.800
Energy                    0.933
Financials                0.922
Healthcare                0.833
Technology                0.789
```

Remaining gaps were mostly due to missing Wayback captures, empty archived pages, JavaScript-heavy captures, blocked pages, server-error pages, or pages that did not produce enough visible body text.

## Part 1 limitations

Wayback coverage is uneven across companies and years. Some companies changed domains or page structures over time. Some archived pages existed but did not preserve readable body text. I retained and documented these gaps instead of forcing unrelated pages into the dataset.

The theme-coding approach is also limited because it relies on predefined dictionaries. This improves reproducibility, but it may miss more subtle value language. The LLM-assisted layer helps add qualitative interpretation, but it is still limited by the quality of the extracted text and by the fact that long pages may need to be truncated before being analyzed.

---

# Part 2 — Lived Values

## Goal

Part 2 analyzes formal disclosure documents as evidence of lived values. I selected DEF 14A proxy statements as the document type because they are available through SEC EDGAR, follow a relatively consistent filing structure, and usually include language about governance, executive compensation, human capital, board oversight, risk, shareholder value, and corporate responsibility.

The goal is to compare companies’ public stated-values language with language in formal corporate disclosures.

## Data source

Part 2 uses SEC EDGAR proxy statement filings. The scraper searches for DEF 14A filings for each company-year from 2016 through 2024, downloads available HTML documents, extracts clean text, and applies the same broad theme categories used in Part 1.

I used proxy statements instead of ESG, sustainability, or DEI reports because proxy filings are more consistently available across companies and years. This made the lived-values dataset more comparable across the 50-company sample.

## Text mining approach

For each proxy statement, I extracted cleaned body text and measured topic emphasis using the same nine value categories from Part 1:

* `innovation`
* `customer_focus`
* `employees_culture`
* `diversity_inclusion`
* `sustainability_environment`
* `community_social_impact`
* `integrity_ethics_trust`
* `health_safety_wellbeing`
* `financial_performance_growth`

I calculated both raw theme counts and normalized theme counts per 10,000 words. The normalized counts make it easier to compare proxy statements of different lengths.

I also calculated a simple dictionary-based tone score using positive and negative term counts. This is not meant to be a full sentiment model, but it provides a consistent way to compare broad tone differences across firms, sectors, and years.

## Trend and variation analysis

To analyze changes over time within companies, I created company-year trend fields such as tone change from the prior usable year, total theme-mention change from the prior usable year, text similarity to the prior usable year, a changed-from-prior indicator, and a theme-shift measure.

To analyze cross-company and cross-sector variation, I generated company coverage reports and year-sector summaries. These outputs compare coverage, average text length, average tone, and theme emphasis across sectors and over time.

I also grouped years into broad external-event windows: pre-2020, 2020–2021, and post-2021. These windows are used as interpretation periods rather than causal claims. They help identify whether language around employees, health and safety, diversity, sustainability, or risk shifted around major external events such as COVID-19 and the broader increase in attention to human capital and ESG disclosure.

## Running Part 2

Run the proxy scraper with:

```bash
python3 src/proxy_scrape.py
```

After the scrape finishes, generate the Part 2 coverage, trend, sector, and event-period reports:

```bash
python3 src/generate_part2_reports.py
```

## Part 2 output files

The main Part 2 output files are:

```text
outputs/lived_values/lived_values_company_year.csv
outputs/lived_values/part2_collection_log.csv
outputs/lived_values/part2_company_coverage_report.csv
outputs/lived_values/part2_missing_rows_report.csv
outputs/lived_values/part2_company_trends.csv
outputs/lived_values/part2_year_sector_summary.csv
outputs/lived_values/part2_external_event_summary.csv
```

The raw proxy HTML files are stored in:

```text
data/raw/proxy_html/
```

The final Part 2 dataset includes one row per company-year and contains fields for company identity, document type, SEC source information, filing metadata, cleaned proxy text, theme categories, normalized theme counts per 10,000 words, tone scores, text availability, and analyst notes.

## Part 2 coverage

The final Part 2 dataset contains 450 company-year rows.

```text
Overall usable-text coverage: 97.1%
Usable rows: 437 / 450
Missing or unusable rows: 13 / 450
```

Coverage by year:

```text
2016    0.94
2017    0.96
2018    0.96
2019    0.98
2020    1.00
2021    0.98
2022    0.96
2023    0.98
2024    0.98
```

Coverage by sector:

```text
Consumer Discretionary    0.978
Energy                    0.989
Financials                0.956
Healthcare                0.989
Technology                0.944
```

Remaining gaps were mostly due to missing DEF 14A filings for a given filing year or filings that did not produce enough usable text.

## Part 2 limitations

Proxy statements are formal legal and governance documents. They are useful for observing what companies disclose and emphasize, but they do not capture every aspect of internal culture or actual behavior. They should be interpreted as a formal disclosure proxy for lived values, not as complete evidence of corporate behavior.

The tone measure is dictionary-based, so it should be treated as a rough indicator rather than a complete sentiment model. The external-event windows are also descriptive. They help organize the analysis around major time periods, but they do not prove that any event caused a specific language shift.

---

# Part 3 — Authenticity Index

## Goal

Part 3 combines the Part 1 stated-values data and the Part 2 lived-values data into a company-year authenticity index. I define organizational authenticity as the degree of alignment between what a company publicly says it values and what its formal disclosures suggest it actually emphasizes.

The index is not meant to prove whether a company is truly authentic in practice. It is a structured language-alignment measure that compares stated-values pages with proxy statement disclosures.

## Measure construction

I operationalized alignment using three components:

* `theme_overlap_jaccard`: whether the same broad value categories appear in both the stated-values page and the proxy statement
* `theme_emphasis_cosine`: whether the two documents emphasize those categories in similar proportions
* `tone_alignment`: whether the overall tone direction is similar across the two documents

The final authenticity index uses the following weighting:

```text
authenticity_index =
0.40 * theme_overlap_jaccard
+ 0.45 * theme_emphasis_cosine
+ 0.15 * tone_alignment
```

I weighted theme-emphasis similarity slightly more than simple theme overlap because two companies can mention the same values while emphasizing them very differently. Theme overlap still receives substantial weight because shared categories are the clearest sign of alignment. Tone alignment receives a smaller weight because it is useful supporting evidence, but it is a rougher dictionary-based measure.

Rows are scored only when both stated-values text and lived-values proxy text are available. Rows without enough text from either source are retained and labeled as `insufficient_data`.

## Running Part 3

Run the authenticity index script with:

```bash
python3 src/authenticity_index.py
```

Then generate the Part 3 distribution, year, validity-check, and limitations reports:

```bash
python3 src/generate_part3_reports.py
```

## Part 3 output files

The main Part 3 output files are:

```text
outputs/authenticity/authenticity_company_year.csv
outputs/authenticity/authenticity_summary_by_company.csv
outputs/authenticity/authenticity_summary_by_sector.csv
outputs/authenticity/part3_distribution_summary.csv
outputs/authenticity/part3_year_summary.csv
outputs/authenticity/part3_validity_check.csv
outputs/authenticity/part3_limitations_notes.csv
```

The company-year file keeps all 450 rows and includes the component scores used to construct the index: theme overlap, theme-emphasis similarity, tone alignment, and the final authenticity index.

## Part 3 coverage and distribution

The final authenticity dataset contains 450 company-year rows.

```text
Coverage for authenticity index: 82.9%
Scored rows: 373 / 450
Insufficient-data rows: 77 / 450
Average authenticity index: 0.579
Median authenticity index: 0.595
```

Authenticity label counts:

```text
moderate_alignment      230
low_alignment           102
insufficient_data        77
high_alignment           41
```

The index ranges from 0.111 to 0.9055 among scored rows. This gives enough variation to compare companies, sectors, and changes over time.

## Validity check

As a basic validity check, I compared the top and bottom companies by average authenticity index. Higher-scoring companies generally had stronger theme overlap and theme-emphasis similarity between stated-values pages and proxy statements. Lower-scoring companies generally had weaker measured overlap or weaker theme-emphasis similarity.

This check does not prove the measure is perfect, but it suggests that the index behaves in a reasonable direction: companies with more similar stated and disclosed value language tend to score higher, while companies with weaker alignment tend to score lower.

## Part 3 limitations

There are several threats to validity. First, the two document types have different purposes: stated-values pages are public-facing, while proxy statements are formal governance disclosures. Some mismatch is expected even for companies that may be authentic in practice.

Second, the index relies on broad dictionary-based value categories. This makes the measure transparent and reproducible, but it can miss subtle or indirect language. Third, tone alignment is only a rough supporting signal based on positive and negative word counts. Finally, the index measures language alignment, not actual behavior. It should be read as a structured proxy for authenticity, not a complete measure of corporate conduct.

---

# Part 4 — Exploratory Extension

## Goal

Part 4 adds one exploratory analysis to better understand what the authenticity index is capturing. Instead of only ranking companies by their final score, I wanted to ask a more diagnostic question: when stated-values language and proxy-statement language do not align, what kind of gap is driving the mismatch?

The main question is whether low alignment usually comes from companies discussing completely different value categories, or from companies mentioning similar categories but emphasizing them differently.

## Method

I used the Part 3 component scores to classify each company-year into a gap type:

* `high_alignment`: strong theme overlap and strong theme-emphasis similarity
* `same_themes_different_emphasis`: similar value categories appear in both documents, but the relative emphasis differs
* `different_themes_similar_tone`: the documents discuss different value categories, but the overall tone is still similar
* `broad_misalignment`: weak theme overlap and weak theme-emphasis similarity
* `insufficient_data`: one or both documents did not have usable text

I also added a component-level diagnostic called `component_gap_driver`, which identifies the weakest component for each company-year. This helps show whether lower alignment is mainly driven by weak theme overlap, weak theme-emphasis similarity, or tone differences.

## Running Part 4

Run:

```bash
python3 src/extension_analysis.py
```

## Part 4 output files

The main Part 4 output files are:

```text
outputs/extension/part4_gap_type_company_year.csv
outputs/extension/part4_gap_type_summary.csv
outputs/extension/part4_gap_type_by_sector.csv
outputs/extension/part4_gap_type_by_year.csv
outputs/extension/part4_gap_driver_summary.csv
outputs/extension/part4_sector_year_diagnostic.csv
outputs/extension/part4_representative_examples.csv
```

## Part 4 findings

The most common scored gap type was `same_themes_different_emphasis`, with 162 company-year rows, or 43.4% of scored rows. This suggests that many companies are not necessarily using completely different values language across public-facing values pages and proxy statements. Instead, they often mention overlapping value categories but place different weight on those categories depending on the document type.

The component-level diagnostic points in the same direction. The most common component gap driver was `theme_emphasis_gap`, which appeared in 259 rows, or 69.4% of scored rows. This means the largest source of measured misalignment is usually not tone or the complete absence of shared themes, but different relative emphasis across documents.

The extension also produces sector-year summaries and representative company-year examples for each gap type. These outputs make the authenticity index more interpretable by showing not only whether alignment is high or low, but how that alignment breaks down.

## Part 4 limitations

This analysis is exploratory. The gap-type categories depend on thresholds chosen from the Part 3 component scores, so they should not be treated as fixed ground truth. The analysis also inherits the limitations of the authenticity index: broad dictionary-based themes, different document purposes, and missing or incomplete text for some company-years. Still, the extension is useful because it turns the index from a simple ranking into a more diagnostic tool.

---

# Known limitations

This project relies on archival and public disclosure data, both of which have limitations. Wayback snapshots are not always complete, company websites change over time, and archived pages may not preserve visible text accurately. Proxy statements are also formal legal documents and may not capture all aspects of a company’s internal culture or operational behavior.

The theme categories are intentionally broad. This makes cross-company comparison easier, but it also means the analysis may miss more nuanced differences in how companies describe values. The authenticity index should therefore be interpreted as a structured measure of language alignment between public stated values and formal disclosure emphasis, not as a complete measure of whether a company truly “lives” its values.

# Reproducibility notes

The main scripts are:

```text
src/wayback_scrape.py
src/generate_part1_reports.py
src/llm_part1_analysis.py
src/merge_part1_llm_outputs.py
src/proxy_scrape.py
src/generate_part2_reports.py
src/authenticity_index.py
src/generate_part3_reports.py
src/extension_analysis.py
```

The recommended order is:

```bash
python3 src/wayback_scrape.py
python3 src/generate_part1_reports.py
python3 src/llm_part1_analysis.py
python3 src/merge_part1_llm_outputs.py
python3 src/proxy_scrape.py
python3 src/generate_part2_reports.py
python3 src/authenticity_index.py
python3 src/generate_part3_reports.py
python3 src/extension_analysis.py
```

Because Wayback scraping can be slow and occasionally unstable, I saved raw HTML files and collection logs so that gaps and selected pages can be audited later.

# What I would do differently with more time

With more time, I would validate a larger sample of selected Wayback pages, test additional text extraction methods for JavaScript-heavy archived pages, and compare proxy statements with other lived-values documents such as ESG, sustainability, or DEI reports. I would also experiment with more granular value categories and compare multiple LLM prompts to test the stability of the qualitative coding.
