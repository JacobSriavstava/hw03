"""
hw03_yfinance_check.py
MIS3060 - HW3, Part 5C: Cross-validate AAPL earnings with yfinance

Pulls Apple's most recent quarterly revenue and net income from Yahoo Finance
and compares them with the most recent AAPL row in earnings_history.csv
(extracted from the 8-K press release).

Run:
    python hw03_yfinance_check.py
"""

import csv
from pathlib import Path

import yfinance as yf

TICKER = "AAPL"
EARNINGS_CSV = Path(__file__).resolve().parent / "earnings_history.csv"
TOLERANCE_PCT = 1.0          # treat values within 1% as a match (8-K revenue is rounded, e.g. $94.0B)


def get_row(stmt, *labels):
    """Return the first matching row from the income statement (label names vary by yfinance version)."""
    for label in labels:
        if label in stmt.index:
            return stmt.loc[label]
    raise KeyError(f"None of {labels} found. Available rows: {list(stmt.index)}")


def latest_from_yfinance():
    stmt = yf.Ticker(TICKER).quarterly_income_stmt        # columns = quarter-end dates, newest first
    if stmt is None or stmt.empty:
        raise RuntimeError("yfinance returned no quarterly income statement data")
    latest_col = stmt.columns[0]
    revenue = get_row(stmt, "Total Revenue", "Operating Revenue")[latest_col]
    net_income = get_row(stmt, "Net Income", "Net Income Common Stockholders")[latest_col]
    return latest_col.date(), revenue / 1e6, net_income / 1e6   # dollars -> millions


def latest_from_8k():
    with open(EARNINGS_CSV, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["ticker"] == TICKER]
    latest = max(rows, key=lambda r: r["filing_date"])
    return latest


def compare(label, ours, theirs):
    if ours == "NOT_FOUND":
        return f"{label:<11} {'NOT_FOUND':>14} {theirs:>14,.1f}   n/a (not extracted)"
    ours = float(ours)
    diff_pct = abs(ours - theirs) / abs(theirs) * 100
    verdict = "MATCH" if diff_pct <= TOLERANCE_PCT else "MISMATCH"
    return f"{label:<11} {ours:>14,.1f} {theirs:>14,.1f}   {verdict} ({diff_pct:.2f}% diff)"


def main():
    quarter_end, yf_revenue, yf_net_income = latest_from_yfinance()
    row = latest_from_8k()

    print(f"{TICKER} - most recent quarter, all figures in $ millions\n")
    print(f"yfinance quarter ended:   {quarter_end}")
    print(f"8-K filing:               {row['filing_date']} ({row['period']})\n")
    print(f"{'Metric':<11} {'8-K extract':>14} {'yfinance':>14}   Result")
    print("-" * 62)
    print(compare("Revenue", row["revenue_reported"], yf_revenue))
    print(compare("Net Income", row["net_income"], yf_net_income))
    print(f"\nNote: 8-K revenue comes from the headline (e.g. '$109.4 billion'), so it is rounded to\n"
          f"$0.1B; a difference under {TOLERANCE_PCT}% is rounding, not an error. If the quarter-end date\n"
          f"above doesn't line up with the 8-K period, the two sources are showing different quarters.")


if __name__ == "__main__":
    main()
