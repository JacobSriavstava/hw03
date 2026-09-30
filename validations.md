# Part 5 - Validations 

### 5A — Known-Answer Check: Earnings

Look up the officially reported quarterly revenue for **one** company for **one** specific quarter using the company's investor relations website or a financial news source.

| Check | Official Source | Your CSV | Match? |
|---|---|---|---|
| [Apple] [Fourth quarter fiscal 2025] Revenue | 102.45 Billion | 102500.0 (Millions)| Yes|
| [Apple] [Fourth quarter fiscal 2025] EPS Diluted | 1.85 | 1.85 | Yes |

If a value does not match or shows `"NOT_FOUND"`: paste the raw press release text excerpt into a new Claude Cowork session and ask for an improved regex pattern. Document the before/after pattern and whether the fix resolved the discrepancy.

### 5B — Known-Answer Check: Executive Events

Pick **one** executive event from your `executive_events.csv`. Verify it against a public news source (Google News, LinkedIn, or the company's own press releases).

| Check | News Source Confirms? | Notes |
|---|---|---|
| Nicholas Parker Execuative Vice Priseident | Yes | Confirms name and position title|
| Appointment | Yes| Confirms he was appointed|
| 2026-07-02 | Yes| Confirms the data |

### 5C — Cross-Validation: Earnings via Yahoo Finance

For the same company and quarter you checked in 5A, use `yfinance` (from ICE 5.1) to retrieve quarterly revenue and net income as a second independent source:

> *"Write Python using yfinance to get the most recent quarterly revenue and net income for [ticker]."*

| Metric | From 8-K text extraction | From yfinance | Match? |
|---|---|---|---|
| Revenue | 109,400.00| 109,417.00| Off slightly |
| Net Income | 29,789.00| 29,789.00 | 100% match|

If the two sources disagree, explain the most likely reason (period mismatch, metric definition difference, or extraction error).

The 109.4 billion comes from a article headline so it is rounded. The Yahoo finance one is a more exact number and more accurate. 

### 5D — Pipeline Integrity Checks

Complete this table:

| Check | Expected | Actual | Pass/Fail |
|---|---|---|---|
| `earnings_history.csv` row count | Up to 20 (5 companies × 4 quarters) | 20 (5 companies x 4 quarters) | Pass|
| `executive_events.csv` row count | At least 0 (document actual) | 28 rows created | Pass|
| `corporate_events_timeline.csv` created | Yes | Yes | Pass |
| Rows with all three fields `"NOT_FOUND"` | 0 (investigate if > 0) | 0 |Pass|