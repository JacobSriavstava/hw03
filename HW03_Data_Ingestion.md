# HW3: Building a Corporate Intelligence Database from SEC 8-K Filings
## MIS3060 Business Intelligence with AI | Villanova University

**Due:** End of Week 6 (Wednesday 11:59 PM)
**Weight:** 5% of final grade
**Submission:** GitHub repository link submitted via Brightspace
**Tools:** Claude Cowork, Python (VS Code terminal), GitHub

---

## Overview

Public companies are required to disclose material events — earnings results, leadership changes, acquisitions — within four business days of occurrence, via the SEC's Form 8-K. Every one of those filings is public, free, and machine-readable through the EDGAR system.

In this assignment you will build two data extraction pipelines from scratch using Vibe Coding: one that pulls earnings figures from earnings press releases (Item 2.02), and one that pulls executive departure and appointment events (Item 5.02). Both draw from the same five companies over the past year. In the final part you join the two tables into a corporate events timeline and use it to ask a business question that neither table could answer alone.

This is the workflow BI analysts use to build proprietary datasets out of public filings — and you will write zero Python from scratch.

> *Public data is not the same as structured data. The pipeline that turns a press release into a spreadsheet row is the analyst's edge.*

---

## Learning Objectives

- Build two multi-company, multi-period extraction pipelines using Vibe Coding
- Navigate SEC EDGAR's API to locate and retrieve specific filing types
- Extract structured fields from unstructured prose using pattern matching
- Join two datasets derived from separate sources into a unified analytical table
- Validate extracted data against known public figures

---

## Companies and EDGAR Identifiers

You will extract data for these five companies. Their CIK numbers are required to query EDGAR — do not look them up, use the values below exactly.

| Company | Ticker | SEC CIK |
|---|---|---|
| Apple Inc. | AAPL | 0000320193 |
| Microsoft Corporation | MSFT | 0000789019 |
| NVIDIA Corporation | NVDA | 0001045810 |
| JPMorgan Chase & Co. | JPM | 0000019617 |
| Walmart Inc. | WMT | 0000104169 |

**Required packages:** `requests`, `beautifulsoup4`. Install before starting (with your venv activated):

```bash
pip install requests beautifulsoup4
```

---

## Part 1 — Write Your Specifications (15 points)

Before opening Claude Cowork, write specifications for **both** pipelines in `hw03/specifications.md`. Treat each specification as a complete, plain-English instruction to Claude Cowork — as if handing the task to a colleague who will implement exactly what you describe.

### Specification A — Earnings Pipeline (Item 2.02)

Your specification for `hw03/hw03_earnings.py` must describe a script that:

1. Sets the SEC EDGAR `User-Agent` header to `"MIS3060 Villanova youremail@villanova.edu"` on all HTTP requests
2. For each of the five companies, queries the EDGAR submissions API at `https://data.sec.gov/submissions/CIK{cik}.json` and filters for 8-K filings where the `items` field contains `"2.02"` (Results of Operations)
3. Selects the most recent **four** such filings per company (one per quarter)
4. For each filing, constructs the filing index URL, identifies the earnings press release exhibit (`.htm` file), downloads it, and strips HTML to plain text
5. Extracts from the plain text: quarterly revenue (as a number in millions or billions), diluted EPS, net income, and the reporting period (e.g., "fourth quarter fiscal 2024")
6. Prints the extracted row for each filing as it is processed, in the format: `[Ticker] | [Period] | Revenue: $X | EPS: $X | Net Income: $X`
7. Saves all rows to `hw03/earnings_history.csv` with columns: `company`, `ticker`, `cik`, `filing_date`, `period`, `revenue_reported`, `eps_diluted`, `net_income`
8. Where a field cannot be extracted (regex returns no match), stores the string `"NOT_FOUND"` rather than leaving the cell blank — blank cells and missing data are two different things

### Specification B — Executive Events Pipeline (Item 5.02)

Your specification for `hw03/hw03_executives.py` must describe a script that:

1. Sets the same EDGAR `User-Agent` header on all requests
2. For each of the five companies, queries the EDGAR submissions API and filters for 8-K filings where the `items` field contains `"5.02"` (Departure of Directors or Officers) and the `filingDate` is within the past 12 months
3. For each matching filing, downloads the full 8-K text, strips HTML, and extracts: event type (`"departure"` or `"appointment"` or `"both"`), the person's full name, their title, and the effective date of the change
4. If a filing reports multiple events (e.g., one departure and one appointment), creates a separate row for each event
5. Prints each extracted event as it is processed: `[Ticker] | [Date] | [Event Type] | [Name] | [Title]`
6. If no Item 5.02 filings are found for a company in the past 12 months, prints `[Ticker]: No executive events in past 12 months` — this is valid data, not an error
7. Saves all events to `hw03/executive_events.csv` with columns: `company`, `ticker`, `cik`, `filing_date`, `event_type`, `person_name`, `title`, `effective_date`

---

## Part 2 — Build and Run the Earnings Pipeline (20 points)

Open Claude Cowork and send Specification A as your prompt. Save the generated script as `hw03/hw03_earnings.py`.

Before running, confirm the script:
- Sets the User-Agent header on **every** `requests.get()` call (not just the first)
- Handles the case where a filing's press release exhibit cannot be found (does not crash — prints a warning and continues to the next filing)
- Stores `"NOT_FOUND"` rather than `None` or empty for missing extractions

Run the script:

```bash
python hw03/hw03_earnings.py
```

**Expected output:** Up to 20 printed rows (5 companies × 4 quarters), followed by a confirmation that `earnings_history.csv` was saved.

If any company's extraction repeatedly returns `"NOT_FOUND"` for all fields, open a new Claude Cowork session, paste the 3,000-character raw text for that company's most recent press release, and ask: *"What regex pattern would reliably extract the quarterly revenue figure from this text?"* Apply the suggested pattern and rerun.

---

## Part 3 — Build and Run the Executive Events Pipeline (20 points)

Send Specification B to Claude Cowork as a new conversation. Save the generated script as `hw03/hw03_executives.py`.

Before running, confirm the script handles two edge cases:
- A company with **zero** Item 5.02 filings in the past 12 months (prints the no-events message, does not crash)
- A single filing that reports **both** a departure and an appointment (produces two rows in the output CSV)

Run the script:

```bash
python hw03/hw03_executives.py
```

**Expected output:** One printed line per extracted event, a no-events message for any company with no Item 5.02 filings, and a confirmation that `executive_events.csv` was saved.

---

## Part 4 — Build the Corporate Events Timeline (20 points)

Use Claude Cowork to generate a third script, `hw03/hw03_timeline.py`, that joins the two tables and answers a business question. Send this prompt to Claude Cowork in a new session:

> *"Write a Python script that reads `hw03/earnings_history.csv` and `hw03/executive_events.csv`. Do the following:*
>
> *1. For each executive event in the events table, calculate the number of days between the executive event's `filing_date` and the nearest earnings filing date for the same company in the earnings table. Call this `days_to_nearest_earnings`.*
> *2. Add a column `event_timing` that categorizes each executive event as: `'before earnings'` if the event came before the nearest earnings filing, `'after earnings'` if it came after, or `'same week'` if within 7 days of an earnings filing.*
> *3. Save the combined table to `hw03/corporate_events_timeline.csv` with all columns from both source tables plus `days_to_nearest_earnings` and `event_timing`.*
> *4. Print a summary: for each company, list any executive events and whether they occurred before or after the nearest earnings announcement.*
> *5. Print a final count: how many events occurred before vs. after an earnings announcement across all five companies."*

Run the script and review the output. In `hw03/analysis.md`, write a short paragraph (3–5 sentences) answering: based on your data, do the executive changes you found appear to precede or follow earnings announcements? Is there any pattern across the five companies, or does it vary?

If `executive_events.csv` has no rows (all five companies had zero Item 5.02 filings in the past 12 months), note this in `hw03/analysis.md` and explain what it might mean — this is a valid analytical finding.

---

## Part 5 — Validate the Extracted Data (15 points)

Document all validation in `hw03/validation.md`.

### 5A — Known-Answer Check: Earnings

Look up the officially reported quarterly revenue for **one** company for **one** specific quarter using the company's investor relations website or a financial news source.

| Check | Official Source | Your CSV | Match? |
|---|---|---|---|
| [Company] [Quarter] Revenue | | | |
| [Company] [Quarter] EPS Diluted | | | |

If a value does not match or shows `"NOT_FOUND"`: paste the raw press release text excerpt into a new Claude Cowork session and ask for an improved regex pattern. Document the before/after pattern and whether the fix resolved the discrepancy.

### 5B — Known-Answer Check: Executive Events

Pick **one** executive event from your `executive_events.csv`. Verify it against a public news source (Google News, LinkedIn, or the company's own press releases).

| Check | News Source Confirms? | Notes |
|---|---|---|
| Person name and title | | |
| Event type (departure/appointment) | | |
| Effective date | | |

### 5C — Cross-Validation: Earnings via Yahoo Finance

For the same company and quarter you checked in 5A, use `yfinance` (from ICE 5.1) to retrieve quarterly revenue and net income as a second independent source:

> *"Write Python using yfinance to get the most recent quarterly revenue and net income for [ticker]."*

| Metric | From 8-K text extraction | From yfinance | Match? |
|---|---|---|---|
| Revenue | | | |
| Net Income | | | |

If the two sources disagree, explain the most likely reason (period mismatch, metric definition difference, or extraction error).

### 5D — Pipeline Integrity Checks

Complete this table:

| Check | Expected | Actual | Pass/Fail |
|---|---|---|---|
| `earnings_history.csv` row count | Up to 20 (5 companies × 4 quarters) | | |
| `executive_events.csv` row count | At least 0 (document actual) | | |
| `corporate_events_timeline.csv` created | Yes | | |
| Rows with all three fields `"NOT_FOUND"` | 0 (investigate if > 0) | | |

---

## Part 6 — Commit and AI Usage Log (10 points)

**Before committing, confirm your `.gitignore` includes the CSV exception for homework folders.** The course `.gitignore` blanket-excludes all `.csv` files to keep large raw datasets out of the repo — but this assignment's own deliverables (`earnings_history.csv`, `executive_events.csv`, `corporate_events_timeline.csv`) are themselves CSVs that need to be tracked. The updated `.gitignore` distributed with this assignment adds an exception (`!hw*/*.csv`) so CSVs inside any `hw0N/` folder are still committed. If your `.gitignore` predates this exception, replace it with the updated version before committing — otherwise `git add` will silently skip your output files and your submission will be missing its CSVs.

Everything you're graded on lives inside `hw03/`, so a single `git add hw03/` picks up the whole submission:

```bash
git add hw03/ .gitignore
git commit -m "HW3: 8-K pipeline — [X] earnings rows, [Y] executive events, timeline built for 5 companies"
git push origin main
```

Edit the commit message to include your actual row counts. The commit message must state what the pipeline produced, not just what files were added.

Complete `hw03/ai_usage_log.md` with:
- The three prompts you sent to Claude Cowork (Specification A, Specification B, and the timeline prompt)
- Which companies' extractions required iteration (follow-up regex fixes)
- One thing the generated script did that you would not have thought to specify, and whether it was correct or needed adjustment

---

## Submission Checklist

- [ ] `hw03/specifications.md` — both specifications written before generating any code
- [ ] `hw03/hw03_earnings.py` — runs without crashing; produces `hw03/earnings_history.csv`
- [ ] `hw03/hw03_executives.py` — runs without crashing; produces `hw03/executive_events.csv`
- [ ] `hw03/hw03_timeline.py` — runs without crashing; produces `hw03/corporate_events_timeline.csv`
- [ ] `hw03/validation.md` — 5A, 5B, 5C, 5D all completed
- [ ] `hw03/analysis.md` — 3–5 sentence business interpretation of the timeline
- [ ] Updated `.gitignore` (with the `hw*/*.csv` exception) present at repo root — CSV deliverables actually committed
- [ ] Commit message includes actual row counts
- [ ] `hw03/ai_usage_log.md` — three prompts documented, iterations noted

**Submit:** Paste your `hw03` folder URL into Brightspace: `https://github.com/[username]/mis3060-bi-ai/tree/main/hw03`

---

## Grading Rubric

| Component | Points | What earns full credit |
|---|---|---|
| Specifications (1) | 15 | Both specs written before code; all required elements present for each |
| Earnings pipeline (2) | 20 | Script runs; CSV produced; `"NOT_FOUND"` used correctly; no crashes |
| Executive events pipeline (3) | 20 | Script runs; edge cases handled; zero-event companies reported, not skipped |
| Timeline join and analysis (4) | 20 | Script runs; `days_to_nearest_earnings` computed; `analysis.md` answers the business question |
| Validation (5) | 15 | All four sections completed; cross-validation attempted; discrepancies explained |
| Commit and AI log (6) | 10 | Commit message has actual counts; all three prompts documented in AI log |

---

## A Note on Extraction Reliability

Text parsing against prose documents does not have a 100% success rate. A well-written pipeline handles failure gracefully — it stores `"NOT_FOUND"`, logs a warning, and continues to the next record. A poorly written pipeline crashes on the first unparseable filing and produces nothing.

Your grade on Parts 2 and 3 is based on whether the pipeline runs reliably and handles edge cases correctly — not on whether every field extracted successfully. An `earnings_history.csv` where 15 of 20 rows extracted cleanly and 5 show `"NOT_FOUND"` with documented investigation earns more credit than a pipeline that crashes on the first difficult filing.
