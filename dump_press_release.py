"""
dump_press_release.py - debugging helper for hw03_earnings.py

Saves the plain text of a company's recent earnings press releases so you can
see why a field came back NOT_FOUND.

Run:  python dump_press_release.py JPM
Output: Data/<TICKER>_<filing_date>.txt (full text) + prints the first 3,000
        characters and every snippet that mentions EPS / per share.
"""
import re
import sys
from pathlib import Path

import hw03_earnings as e

ticker = (sys.argv[1] if len(sys.argv) > 1 else "JPM").upper()
co = next(c for c in e.COMPANIES if c["ticker"] == ticker)
out_dir = Path(__file__).resolve().parent / "Data"
out_dir.mkdir(exist_ok=True)

for f in e.get_earnings_filings(co["cik"]):
    url = e.find_press_release_url(e.filing_index_url(co["cik"], f["accession"]), f["primary_doc"])
    if not url:
        print(f"{f['filing_date']}: no exhibit found")
        continue
    text = e.html_to_text(e.sec_get(url).content)
    path = out_dir / f"{ticker}_{f['filing_date']}.txt"
    path.write_text(text, encoding="utf-8")

    print(f"\n{'=' * 70}\n{ticker} {f['filing_date']}  ->  {path.name}\n{url}")
    print(f"EPS extracted: {e.extract_eps(text)}\n")
    print("--- first 3,000 characters ---")
    print(text[:3000])
    print("\n--- snippets mentioning EPS / per share ---")
    for m in re.finditer(r"EPS|per share", text):
        print("...", text[max(0, m.start() - 150): m.end() + 100], "...")
        if m.start() > 20000:
            break
