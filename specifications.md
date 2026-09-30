# Part 1: Writing Specifications #

## Specification A - Earnings Pipeline (Item 2.02)

Create a python code with the title hw03_earnings.py in the ho03 folder. The python code should do the following:

Note these are the 5 companies being refered to:
The following companies are in the format of: Company Name (Ticker) (SEC CIK)
Apple Inc (AAPL) (0000320193)
Microsoft Corporation (MSFT) (0000789019)
NVIDIA Corporation (NVDA) (0001045810)
JPMorgan Chase & Co. (JPM) (0000019617)
Walmart Inc. (WMT) (0000104169)
1. Create the SEC EDGAR User-Agent header to "MIS3060 Villanova jsrivast@villanova.edu" on all HTTP requests. 
2. Querie the Edgar submissions API at https://data.sec.gov/submissions/CIK{cik}.json for each of the five companies and filter for the 8-K fillings where the items field contains "2.02" (Results of Operations). The 5 companies refer to the list at the top of 5 companies, their ticker, and their SEC CIK. 
3. Only select the four (4) most recent filings per company (one per quarter)
4. For each of the filings, constuct the filing index URL, identifies the earnings press release exhibit (.htm file), download it, and scripts HTML to plain text
5. Extract from the plan text the following: Quarterly revenue (As numbers in millions), diluted EPS, net income, and the reporting period (e.g., "Fourth quarter fiscal 2024)
6. Print the extracted row for each filing as it is processed, in the format: [Ticker] | [Period] | Revenue: $x | EPS: $x|Net Income: $x 
7. Create and save all rows to a file titled earnings_history.csv with columns: company, ticker, cik, filing_date, period, revenue_reported, eps_diluted, net_income
8. When there is a field that cannot be extracted (regex returns no match), store the string "NOT_FOUND" rather than leaving the cell blank

## Specification B - Execuative Events Pipeline (Item 5.02)
Create a python code for the following description. Save it as hw03_earnings.py within the hw03 folder. The python code must complete all of the following tasks. 

Note these are the 5 companies being refered to:
The following companies are in the format of: Company Name (Ticker) (SEC CIK)
Apple Inc (AAPL) (0000320193)
Microsoft Corporation (MSFT) (0000789019)
NVIDIA Corporation (NVDA) (0001045810)
JPMorgan Chase & Co. (JPM) (0000019617)
Walmart Inc. (WMT) (0000104169)

1. Set the same EDGAR User-Agent header on all requests. MIS3060 Villanova jsrivast@villanova.edu" on all HTTP requests. 
2. For each of the 5 companies (the one noted above), querie the EDGAR submissions API at https://data.sec.gov/submissions/CIK{cik}.json and filter for 8-K filings where the items field contains "5.02" (Departure of Directors or Officers) and the filingDate is within the past 12 months from today (September 27, 2026). 
3. For all matching filing, dowload the full 8-K text, Scriots HTML, and extract the following: event type ("departure" or "appointment" or "both"), the person's full name, their title, and the effective date of change
4. If a filing reports multiple events (e.g., one departure and one appointment), create a separate row for each event
Print each extracted event as it is processed: [Ticker]|[Date]|[Event Type]|[Name]|[Title]
6. If no Item 5.02 filings are found for a company in the past 12 months, print [Ticker]: No executive events in past 12 months
7. Create and save all events to executive_events.csv with columns: company, ticker, cik, filing_date, event_type, person_name, title, effective_date