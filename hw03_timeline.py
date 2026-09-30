"""
hw03_timeline.py
MIS3060 - HW3, Part 4: Corporate Events Timeline

Joins executive_events.csv (Item 5.02) to earnings_history.csv (Item 2.02):
  1. For each executive event, finds the nearest earnings filing for the same
     company and computes days_to_nearest_earnings (absolute number of days
     between the two filing dates).
  2. Adds event_timing:
       'same week'        - within 7 days of that earnings filing (checked first)
       'before earnings'  - event filed before the nearest earnings filing
       'after earnings'   - event filed after the nearest earnings filing
  3. Saves corporate_events_timeline.csv with all columns from both tables
     plus days_to_nearest_earnings and event_timing.
  4. Prints a per-company summary.
  5. Prints the overall before vs. after count.

Run:
    python hw03_timeline.py
"""

from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
EARNINGS_CSV = HERE / "earnings_history.csv"
EVENTS_CSV = HERE / "executive_events.csv"
OUTPUT_CSV = HERE / "corporate_events_timeline.csv"

SAME_WEEK_DAYS = 7
TICKER_ORDER = ["AAPL", "MSFT", "NVDA", "JPM", "WMT"]


def nearest_earnings(event_date, company_earnings):
    """Return the earnings row whose filing_date is closest to event_date.
    Ties (equally close before and after) go to the earlier earnings filing."""
    diffs = (company_earnings["earnings_filing_date"] - event_date).abs()
    best = diffs.min()
    candidates = company_earnings[diffs == best]
    return candidates.sort_values("earnings_filing_date").iloc[0]


def classify(event_date, earnings_date):
    days = abs((event_date - earnings_date).days)
    if days <= SAME_WEEK_DAYS:
        return days, "same week"
    return days, "before earnings" if event_date < earnings_date else "after earnings"


def main():
    # Read everything as text so CIKs keep their leading zeros and NOT_FOUND stays as-is
    earnings = pd.read_csv(EARNINGS_CSV, dtype=str)
    events = pd.read_csv(EVENTS_CSV, dtype=str)

    # Both tables have company/ticker/cik/filing_date; keep one set of IDs and
    # rename the earnings filing date so the two dates stay distinct.
    earnings = earnings.rename(columns={"filing_date": "earnings_filing_date"})
    earnings["earnings_filing_date"] = pd.to_datetime(earnings["earnings_filing_date"])
    earnings_cols = [c for c in earnings.columns if c not in ("company", "ticker", "cik")]

    rows = []
    for _, ev in events.iterrows():
        row = ev.to_dict()
        event_date = pd.to_datetime(ev["filing_date"])
        company_earnings = earnings[earnings["ticker"] == ev["ticker"]]

        if company_earnings.empty:
            row.update({c: "NOT_FOUND" for c in earnings_cols})
            row["days_to_nearest_earnings"] = "NOT_FOUND"
            row["event_timing"] = "no earnings data"
        else:
            match = nearest_earnings(event_date, company_earnings)
            row.update({c: match[c] for c in earnings_cols})
            row["earnings_filing_date"] = match["earnings_filing_date"].strftime("%Y-%m-%d")
            days, timing = classify(event_date, match["earnings_filing_date"])
            row["days_to_nearest_earnings"] = days
            row["event_timing"] = timing
        rows.append(row)

    out_cols = list(events.columns) + earnings_cols + ["days_to_nearest_earnings", "event_timing"]
    timeline = pd.DataFrame(rows, columns=out_cols)
    timeline.to_csv(OUTPUT_CSV, index=False)

    # ---- Step 4: per-company summary -------------------------------------
    print("=" * 78)
    print("CORPORATE EVENTS TIMELINE - executive events vs. nearest earnings filing")
    print("=" * 78)
    tickers = [t for t in TICKER_ORDER if t in set(earnings["ticker"]) | set(events["ticker"])]
    for ticker in tickers:
        name = (earnings.loc[earnings["ticker"] == ticker, "company"].tolist()
                or events.loc[events["ticker"] == ticker, "company"].tolist())[0]
        print(f"\n{name} ({ticker})")
        company_events = timeline[timeline["ticker"] == ticker].sort_values("filing_date")
        if company_events.empty:
            print("  No executive events in past 12 months")
            continue
        for _, r in company_events.iterrows():
            print(f"  {r['filing_date']}  {r['event_type']:<11} {r['person_name']:<22} "
                  f"-> {r['event_timing']:<15} "
                  f"({r['days_to_nearest_earnings']} days from earnings filed "
                  f"{r['earnings_filing_date']}, {r['period']})")

    # ---- Step 5: overall counts ------------------------------------------
    counts = timeline["event_timing"].value_counts()
    print("\n" + "=" * 78)
    print("TOTAL ACROSS ALL FIVE COMPANIES")
    print(f"  Before earnings: {counts.get('before earnings', 0)}")
    print(f"  After earnings:  {counts.get('after earnings', 0)}")
    print(f"  Same week:       {counts.get('same week', 0)}  (within {SAME_WEEK_DAYS} days)")
    if counts.get("no earnings data", 0):
        print(f"  No earnings data: {counts['no earnings data']}")
    print(f"  Total events:    {len(timeline)}")
    print(f"\nSaved {len(timeline)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
