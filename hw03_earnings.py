"""
hw03_earnings.py
MIS3060 - HW3, Specification A: Earnings Pipeline (8-K Item 2.02)

For each of five companies, this script:
  1. Queries the SEC EDGAR submissions API
  2. Keeps 8-K filings whose items include "2.02" (Results of Operations)
  3. Selects the four most recent (one per quarter)
  4. Opens each filing index, finds the earnings press release exhibit (.htm),
     downloads it and strips the HTML to plain text
  5. Extracts quarterly revenue (in millions), diluted EPS, net income
     (in millions), and the reporting period
  6. Prints one line per filing
  7. Saves everything to earnings_history.csv (in the same folder as this script)
  8. Writes "NOT_FOUND" for any field that could not be extracted

Run:
    python hw03_earnings.py
"""

import csv
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Spec step 1: SEC requires a descriptive User-Agent on every request.
HEADERS = {
    "User-Agent": "MIS3060 Villanova jsrivast@villanova.edu",
    "Accept-Encoding": "gzip, deflate",
}

COMPANIES = [
    {"company": "Apple Inc.", "ticker": "AAPL", "cik": "0000320193"},
    {"company": "Microsoft Corporation", "ticker": "MSFT", "cik": "0000789019"},
    {"company": "NVIDIA Corporation", "ticker": "NVDA", "cik": "0001045810"},
    {"company": "JPMorgan Chase & Co.", "ticker": "JPM", "cik": "0000019617"},
    {"company": "Walmart Inc.", "ticker": "WMT", "cik": "0000104169"},
]

FILINGS_PER_COMPANY = 4
MIN_DAYS_BETWEEN_FILINGS = 45   # treat 2.02 filings closer than this as the same quarter
REQUEST_DELAY_SECONDS = 0.2     # SEC allows max 10 requests/second
NOT_FOUND = "NOT_FOUND"

OUTPUT_CSV = Path(__file__).resolve().parent / "earnings_history.csv"
CSV_COLUMNS = [
    "company", "ticker", "cik", "filing_date", "period",
    "revenue_reported", "eps_diluted", "net_income",
]


# ---------------------------------------------------------------------------
# HTTP helper - the ONLY place requests.get() is called, so the User-Agent
# header is guaranteed to be sent on every single request.
# ---------------------------------------------------------------------------

def sec_get(url, retries=3):
    """GET a URL from SEC with the required headers. Returns a Response or None."""
    for attempt in range(1, retries + 1):
        try:
            time.sleep(REQUEST_DELAY_SECONDS)
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (429, 503):          # rate limited - back off
                time.sleep(2 * attempt)
                continue
            print(f"    WARNING: HTTP {resp.status_code} for {url}")
            return None
        except requests.RequestException as exc:
            print(f"    WARNING: request failed ({exc}) for {url}")
            time.sleep(2 * attempt)
    return None


# ---------------------------------------------------------------------------
# Step 2 & 3: find the four most recent Item 2.02 8-K filings
# ---------------------------------------------------------------------------

def get_earnings_filings(cik):
    """Return up to 4 recent 8-K filings with Item 2.02, one per quarter."""
    resp = sec_get(f"https://data.sec.gov/submissions/CIK{cik}.json")
    if resp is None:
        return []

    recent = resp.json().get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    items = recent.get("items", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    selected = []
    for i in range(len(forms)):                          # EDGAR lists newest first
        if forms[i] != "8-K" or "2.02" not in (items[i] or ""):
            continue

        filing_date = datetime.strptime(dates[i], "%Y-%m-%d")
        # "One per quarter": skip a filing that is too close to one already chosen
        if any(abs((filing_date - f["date_obj"]).days) < MIN_DAYS_BETWEEN_FILINGS
               for f in selected):
            continue

        selected.append({
            "filing_date": dates[i],
            "date_obj": filing_date,
            "accession": accessions[i],
            "primary_doc": primary_docs[i],
        })
        if len(selected) == FILINGS_PER_COMPANY:
            break
    return selected


# ---------------------------------------------------------------------------
# Step 4: locate the press release exhibit and convert it to plain text
# ---------------------------------------------------------------------------

def filing_index_url(cik, accession):
    cik_int = str(int(cik))                              # EDGAR paths drop leading zeros
    acc_nodash = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{accession}-index.htm"


def find_press_release_url(index_url, primary_doc):
    """Parse the filing index page and return the URL of the EX-99 press release (.htm)."""
    resp = sec_get(index_url)
    if resp is None:
        return None

    soup = BeautifulSoup(resp.content, "html.parser")
    candidates = []   # (priority, url) - lower priority number = better match

    for row in soup.select("table.tableFile tr"):
        cells = row.find_all("td")
        link = row.find("a", href=True)
        if len(cells) < 4 or link is None:
            continue

        description = cells[1].get_text(" ", strip=True).lower()
        doc_type = cells[3].get_text(" ", strip=True).upper()
        href = link["href"].replace("/ix?doc=", "")       # strip inline-XBRL viewer prefix
        if not href.lower().endswith((".htm", ".html")):
            continue
        url = "https://www.sec.gov" + href if href.startswith("/") else href

        if doc_type.startswith("EX-99.1"):
            candidates.append((0, url))
        elif doc_type.startswith("EX-99") and "press" in description:
            candidates.append((1, url))
        elif doc_type.startswith("EX-99"):
            candidates.append((2, url))
        elif re.search(r"ex-?99", href, re.I) and primary_doc not in href:
            candidates.append((3, url))

    if not candidates:
        return None
    return sorted(candidates)[0][1]


def html_to_text(html_bytes):
    """Strip HTML tags and normalize whitespace."""
    soup = BeautifulSoup(html_bytes, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(" ")
    text = text.replace("\xa0", " ").replace("’", "'")
    text = re.sub(r"\$\s+", "$", text)                   # "$ 94,036" -> "$94,036"
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Step 5: extraction with regular expressions
# ---------------------------------------------------------------------------

NUM = r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)"
SCALE = r"\s*(billion|million)"


def to_millions(number_str, scale):
    value = float(number_str.replace(",", ""))
    if scale and scale.lower() == "billion":
        value *= 1000
    return round(value, 1)


def first_match(patterns, text):
    """Return the regex match that appears EARLIEST in the text (headline beats tables)."""
    best = None
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m and (best is None or m.start() < best.start()):
            best = m
    return best


def extract_revenue(text):
    # Prose: "quarterly revenue of $94.0 billion", "Revenue was $76.4 billion",
    #        "revenue for the second quarter ended ..., of $46.7 billion",
    #        "Consolidated revenue of $177.4 billion", "Reported revenue of $44.9 billion"
    m = first_match([
        r"\brevenues?\b[^$.;]{0,120}?\$" + NUM + SCALE,
        r"\bnet sales\b[^$.;]{0,60}?\$" + NUM + SCALE,
    ], text)
    if m:
        return to_millions(m.group(1), m.group(2))

    # Table fallback (values already in millions): "Total net sales $94,036"
    m = first_match([
        r"Total net (?:sales|revenues?) \$?" + NUM,
        r"Total revenues? \$?" + NUM,
        r"\bRevenue \$" + NUM,
    ], text)
    if m:
        return to_millions(m.group(1), None)
    return NOT_FOUND


def extract_eps(text):
    # Highest priority: an explicit "diluted EPS" line in the results table.
    # JPM's headline mixes reported and "excluding significant items" EPS, e.g.
    # "NET INCOME OF $21.2 BILLION ( $7.70 PER SHARE), ... EXCLUDING SIGNIFICANT
    # ITEMS ... ($6.14 PER SHARE)", so the table row is the reliable source:
    # "Earnings per share - diluted $7.70 $5.94 $5.24" -> first number = current quarter.
    m = re.search(r"Earnings per share\s*[-\u2013\u2014:]\s*diluted\s+\$?(\d+\.\d{2})",
                  text, re.IGNORECASE)
    if m:
        return float(m.group(1))

    m = first_match([
        r"diluted earnings per share (?:was|were|of)\s+\$(\d+\.\d{2})",
        r"earnings per diluted share[^$]{0,60}?\$(\d+\.\d{2})",
        r"diluted EPS[^$]{0,40}?\$(\d+\.\d{2})",
        r"GAAP EPS of \$(\d+\.\d{2})",
        r"earnings per share \(EPS\) of \$(\d+\.\d{2})",
        r"\(\s*\$(\d+\.\d{2}) per share\)",      # allow "( $5.07 PER SHARE)"
    ], text)
    if m:
        return float(m.group(1))

    # Table fallback: "Diluted $1.57"
    m = re.search(r"\bDiluted \$(\d+\.\d{2})", text)
    if m:
        return float(m.group(1))
    return NOT_FOUND


def extract_net_income(text):
    # Prose: "Net income was $27.2 billion", "reported net income of $15.0 billion"
    m = first_match([
        r"\bnet income (?:was|of|totaled)\s+\$" + NUM + SCALE,
        r"\bnet income\b[^$.;]{0,60}?\$" + NUM + SCALE,
    ], text)
    if m:
        return to_millions(m.group(1), m.group(2))

    # Table fallback (in millions): "Net income $23,434",
    # "Consolidated net income attributable to Walmart $7,026"
    m = first_match([
        r"Consolidated net income attributable to \w+ \$" + NUM,
        r"\bNet income(?: attributable to [\w .&]+?)? \$" + NUM,
    ], text)
    if m:
        return to_millions(m.group(1), None)
    return NOT_FOUND


ORDINALS = r"(first|second|third|fourth)"


def extract_period(text):
    patterns = [
        # "fourth quarter of fiscal year 2025", "second quarter fiscal 2026"
        (ORDINALS + r"[- ]quarter(?: of)? fiscal(?: year)? (\d{4})",
         lambda m: f"{m.group(1).capitalize()} quarter fiscal {m.group(2)}"),
        # Apple: "fiscal 2025 third quarter"
        (r"fiscal(?: year)? (\d{4}) " + ORDINALS + r" quarter",
         lambda m: f"{m.group(2).capitalize()} quarter fiscal {m.group(1)}"),
        # "fiscal fourth quarter 2025"
        (r"fiscal " + ORDINALS + r" quarter(?: of)? (\d{4})",
         lambda m: f"{m.group(1).capitalize()} quarter fiscal {m.group(2)}"),
        # JPM: "second-quarter 2025"
        (ORDINALS + r"[- ]quarter(?: of)? (\d{4})",
         lambda m: f"{m.group(1).capitalize()} quarter {m.group(2)}"),
        # "Q2 FY26" / "Q2 fiscal 2026"
        (r"\bQ([1-4]) (?:FY|fiscal )(\d{2,4})\b",
         lambda m: f"Q{m.group(1)} FY{m.group(2)}"),
        # Last resort: "quarter ended June 30, 2025"
        (r"quarter ended (\w+ \d{1,2}, \d{4})",
         lambda m: f"Quarter ended {m.group(1)}"),
    ]
    best = None
    for pat, fmt in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m and (best is None or m.start() < best[0].start()):
            best = (m, fmt)
    return best[1](best[0]) if best else NOT_FOUND


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def fmt_money_millions(value):
    if value == NOT_FOUND:
        return NOT_FOUND
    if value >= 1000:
        return f"${value / 1000:,.2f}B"
    return f"${value:,.1f}M"


def fmt_eps(value):
    return NOT_FOUND if value == NOT_FOUND else f"${value:.2f}"


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    rows = []

    for co in COMPANIES:
        ticker, cik = co["ticker"], co["cik"]
        print(f"\n=== {co['company']} ({ticker}) ===")

        filings = get_earnings_filings(cik)
        if not filings:
            print(f"  WARNING: no Item 2.02 8-K filings found for {ticker}")
            continue

        for f in filings:
            try:
                index_url = filing_index_url(cik, f["accession"])
                exhibit_url = find_press_release_url(index_url, f["primary_doc"])
                if exhibit_url is None:
                    print(f"  WARNING: {ticker} {f['filing_date']} - press release "
                          f"exhibit not found ({index_url}). Skipping.")
                    continue

                resp = sec_get(exhibit_url)
                if resp is None:
                    print(f"  WARNING: {ticker} {f['filing_date']} - could not download "
                          f"{exhibit_url}. Skipping.")
                    continue

                text = html_to_text(resp.content)

                row = {
                    "company": co["company"],
                    "ticker": ticker,
                    "cik": cik,
                    "filing_date": f["filing_date"],
                    "period": extract_period(text),
                    "revenue_reported": extract_revenue(text),
                    "eps_diluted": extract_eps(text),
                    "net_income": extract_net_income(text),
                }
                # Safety net: never leave a blank/None cell
                for key, val in row.items():
                    if val is None or val == "":
                        row[key] = NOT_FOUND

                rows.append(row)
                print(f"{ticker} | {row['period']} | "
                      f"Revenue: {fmt_money_millions(row['revenue_reported'])} | "
                      f"EPS: {fmt_eps(row['eps_diluted'])} | "
                      f"Net Income: {fmt_money_millions(row['net_income'])}")

            except Exception as exc:   # one bad filing should never stop the pipeline
                print(f"  WARNING: {ticker} {f['filing_date']} - unexpected error "
                      f"({exc}). Skipping.")

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {OUTPUT_CSV}")
    print("Note: revenue_reported and net_income are in millions of USD.")


if __name__ == "__main__":
    main()
