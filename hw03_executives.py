"""
hw03_executives.py
MIS3060 - HW3, Specification B: Executive Events Pipeline (8-K Item 5.02)

For each of five companies, this script:
  1. Queries the SEC EDGAR submissions API (User-Agent header on every request)
  2. Keeps 8-K filings whose items include "5.02" and whose filingDate is
     within the 12 months before September 27, 2026
  3. Downloads each full 8-K, strips the HTML, isolates the Item 5.02 section
     and extracts: event type, person's full name, title, effective date
  4. Writes one row per event (a filing with a departure AND an appointment
     produces two rows)
  5. Prints each event, or "[Ticker]: No executive events in past 12 months"
  6. Saves everything to executive_events.csv (same folder as this script)
  Fields that cannot be extracted are stored as "NOT_FOUND".

Event types:
  departure   - person is leaving a role (resign, retire, step down, ...)
  appointment - person is taking a role (appointed, elected, named, ...)
  both        - the SAME person leaves one role and takes another
                (e.g. "will step down as CFO and become Senior Advisor")

Run:
    python hw03_executives.py
"""

import csv
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

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

REFERENCE_DATE = date(2026, 9, 27)                     # "today" per the specification
CUTOFF_DATE = REFERENCE_DATE - timedelta(days=365)     # past 12 months
REQUEST_DELAY_SECONDS = 0.2                            # SEC limit: 10 requests/second
NOT_FOUND = "NOT_FOUND"

OUTPUT_CSV = Path(__file__).resolve().parent / "executive_events.csv"
CSV_COLUMNS = [
    "company", "ticker", "cik", "filing_date", "event_type",
    "person_name", "title", "effective_date",
]


# ---------------------------------------------------------------------------
# HTTP helper - the ONLY place requests.get() is called, so every request
# carries the User-Agent header.
# ---------------------------------------------------------------------------

def sec_get(url, retries=3):
    for attempt in range(1, retries + 1):
        try:
            time.sleep(REQUEST_DELAY_SECONDS)
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (429, 503):
                time.sleep(2 * attempt)
                continue
            print(f"    WARNING: HTTP {resp.status_code} for {url}")
            return None
        except requests.RequestException as exc:
            print(f"    WARNING: request failed ({exc}) for {url}")
            time.sleep(2 * attempt)
    return None


# ---------------------------------------------------------------------------
# Step 2: find Item 5.02 8-Ks in the past 12 months
# ---------------------------------------------------------------------------

def get_executive_filings(cik):
    resp = sec_get(f"https://data.sec.gov/submissions/CIK{cik}.json")
    if resp is None:
        return None                                     # None = API failure (not "zero filings")

    recent = resp.json().get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    items = recent.get("items", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    matches = []
    for i in range(len(forms)):
        if forms[i] != "8-K" or "5.02" not in (items[i] or ""):
            continue
        filed = datetime.strptime(dates[i], "%Y-%m-%d").date()
        if CUTOFF_DATE <= filed <= REFERENCE_DATE:
            matches.append({
                "filing_date": dates[i],
                "accession": accessions[i],
                "primary_doc": primary_docs[i],
            })
    return matches


def filing_doc_url(cik, accession, primary_doc):
    return (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{accession.replace('-', '')}/{primary_doc}")


# ---------------------------------------------------------------------------
# Step 3: HTML -> text, isolate Item 5.02
# ---------------------------------------------------------------------------

def html_to_text(html_bytes):
    soup = BeautifulSoup(html_bytes, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    # Inline XBRL filings hide metadata in <ix:header>; drop it
    for tag in soup.find_all(re.compile(r"^ix:header$", re.I)):
        tag.decompose()
    text = soup.get_text(" ")
    text = (text.replace("\xa0", " ").replace("’", "'")
                .replace("“", '"').replace("”", '"'))
    return re.sub(r"\s+", " ", text).strip()


def isolate_item_502(text):
    """Return the text between 'Item 5.02' and the next Item / signature block."""
    sections = []
    for m in re.finditer(r"Item\s*5\.02", text, re.IGNORECASE):
        rest = text[m.end():]
        end = re.search(r"Item\s*\d\.\d{2}|SIGNATURES?\b", rest, re.IGNORECASE)
        sections.append(rest[: end.start()] if end else rest)
    # Longest candidate = the real section (skips short table-of-contents hits)
    section = max(sections, key=len) if sections else text
    # Drop the standard heading "Departure of Directors or Certain Officers; Election of
    # Directors; ... Compensatory Arrangements of Certain Officers" - its keywords
    # ("Election", "Appointment") otherwise create fake events.
    heading = (r"(?:Departure of Directors or Certain Officers|Election of Directors|"
               r"Appointment of Certain Officers|Compensatory Arrangements of Certain Officers)")
    section = re.sub(r"^(?:[\s.:;()\-\u2013\u2014a-e]{0,6}" + heading + r")+[\s.:;]*",
                     "", section, count=1, flags=re.IGNORECASE)
    return section


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

DEPARTURE_WORDS = (r"retire(?:d|s|ment)?|resign(?:ed|s|ation)?|step(?:s|ping)? down|stepped down|"
                   r"depart(?:ure|s|ed|ing)?|will leave|leaving|terminat(?:e|ed|ion)|"
                   r"not (?:to )?stand for re-?election|not seek re-?election|ceased? to serve|"
                   r"will no longer serve|transition(?:s|ing)? (?:out )?(?:of|from)|will transition")
APPOINTMENT_WORDS = (r"appoint(?:ed|s|ment)?|elect(?:ed|s|ion)?|named|promot(?:ed|ion)|"
                     r"will succeed|succeed(?:s|ing)?|will join|hired|"
                     r"become|becomes|will serve as|will assume|assumes?")

MONTHS = (r"(?:January|February|March|April|May|June|July|August|September|"
          r"October|November|December)")
DATE_RE = MONTHS + r"\s+\d{1,2},\s+\d{4}"

# Words that can look like a Name but are not people
NON_NAME_WORDS = {
    "Apple", "Microsoft", "Nvidia", "NVIDIA", "Jpmorgan", "JPMorgan", "Chase", "Walmart",
    "Inc", "Corporation", "Company", "Board", "Directors", "Director", "Chief", "Officer",
    "Executive", "Financial", "Operating", "Accounting", "Legal", "Technology", "Vice",
    "President", "Senior", "Chairman", "Chair", "Committee", "Compensation", "Audit",
    "Item", "Items", "Section", "Exhibit", "Form", "Securities", "Exchange", "Commission",
    "Act", "Annual", "Meeting", "Shareholders", "Stockholders", "Plan", "Agreement",
    "Named", "United", "States", "America", "Global", "General", "Counsel", "Secretary",
    "Treasurer", "Controller", "The", "This", "On", "In", "As", "Effective", "Mr", "Ms",
    "Mrs", "Dr", "Following", "Upon", "Prior", "Cupertino", "California", "Redmond",
    "Washington", "Santa", "Clara", "New", "York", "Bentonville", "Arkansas", "Delaware",
    "Retirement", "Departure", "Appointment", "Election", "Directors", "Certain",
    "Officers", "Operations", "Services", "Retail", "Marketing", "Worldwide", "Human",
    "Resources", "Group", "International", "Sam", "Club", "Stock", "Restricted", "Units",
    "Letter", "Press", "Release", "Holdings", "Bank", "Asset", "Wealth", "Management",
    "Consumer", "Community", "Banking", "Commercial", "Investment", "Corporate",
    "Cloud", "Intelligence", "Business", "Chairwoman", "Lead", "Independent",
    "Transition", "Date", "Hardware", "Software", "Engineering", "Target", "Award",
    "Awards", "Opportunity", "Achievement", "Fiscal", "Year", "Base", "Salary", "Bonus",
    "Compensatory", "Arrangements", "Arrangement", "Competition", "Covenant", "Not",
    "Compete", "Agreements", "Separation", "Release", "Incentive", "Equity", "Cash",
    "Performance", "Share", "Shares", "Options", "Grant", "Program", "Policy", "Term",
    "Effective", "Period", "Quarter", "Retail", "Chief", "People", "Officer", "Emeritus",
    "Nominating", "Governance", "Public", "Responsibility", "Risk", "Finance", "Advisor",
    "Advisory", "Senior", "Walmart", "Supercenter", "Services", "Products", "Division",
    "Segment", "Chase", "Morgan", "Firm", "Operating", "Sales", "Supply", "Chain",
    "Commerce", "Global", "Markets", "Payments", "Paris", "London", "Texas", "Wash",
} | {m for m in re.findall(r"[A-Z][a-z]+", MONTHS)}

NAME_TOKEN = r"(?:Mc|Mac|O'|D')?[A-Z][a-z]+(?:-[A-Z][a-z]+)?"   # McMillon, O'Brien, Jen-Hsun
NAME_RE = re.compile(
    r"\b(" + NAME_TOKEN + r"(?:\s+[A-Z]\.)?(?:\s+" + NAME_TOKEN + r"){1,2}"
    r"(?:,?\s+(?:Jr\.|Sr\.|III|II))?)(?![A-Za-z])"
)
HONORIFIC_RE = re.compile(r"\b(?:Mr|Ms|Mrs|Dr)\.\s+([A-Z][a-z'\-]+)")

TITLE_RE = re.compile(
    r"((?:(?:Executive|Senior|Corporate|Group|Deputy|Co-)\s*)*"
    r"(?:(?:CEO|CFO|COO|CAO|VP)(?:\s+and\s+(?:CEO|CFO|COO|CAO))?(?![A-Za-z])|"
    r"Vice\s+President|General\s+Counsel|Chief\s+[A-Z][a-z]+(?:\s+(?:and\s+)?[A-Z][a-z]+)?\s+Officer|"
    r"Chief\s+Executive\s+Officer|President|Chairman(?:\s+of\s+the\s+Board)?|Chair|"
    r"Lead\s+Independent\s+Director|General\s+Counsel|Controller|Treasurer|"
    r"Corporate\s+Secretary|Senior\s+Advisor|Principal\s+[A-Z][a-z]+\s+Officer)"
    r"(?:,?\s+(?:and|&)\s+(?:Chief\s+[A-Z][a-z]+\s+Officer|President|Secretary|"
    r"General\s+Counsel|Chairman))?"
    r"(?:\s+(?:of|,)\s+(?:the\s+)?[A-Z][A-Za-z&' ]{2,40}?(?=[,.;]|\s+(?:and|effective|of|to|on|who)\b))?)",
    re.IGNORECASE,
)
BOARD_RE = re.compile(r"(?:member of|to|from|join) (?:the|its|our) (?:Company's )?Board\b",
                      re.IGNORECASE)


# Explicit role changes: "step down as CFO and become Senior Advisor",
# "transition from his role as CEO to Executive Chair", "transition to the role of ..."
BOTH_RE = re.compile(
    r"(?:step(?:s|ping)?\s+down|transition\w*|resign\w*)\b[^.;]{0,150}?"
    r"(?:\band\s+(?:will\s+)?(?:become|serve\s+as|assume)\b|"
    r"\bto\s+(?:the\s+role\s+of\s+)?(?:Executive|Non-Executive)?\s*Chair|"
    r"\bto\s+the\s+role\s+of\b)",
    re.IGNORECASE,
)


def valid_name(candidate):
    tokens = re.findall(r"[A-Za-z][A-Za-z'\-]*", candidate)
    real = [t for t in tokens if t not in ("Jr", "Sr", "II", "III")]
    if len(real) < 2:
        return False
    return not any(t in NON_NAME_WORDS for t in real)


def find_names(sentence, known_people):
    """Return [(full_name, position)] for people mentioned in the sentence."""
    found = []
    for m in NAME_RE.finditer(sentence):
        cand = m.group(1).strip().rstrip(",")
        # Trim leading non-name words ("Board Kevan Parekh" -> "Kevan Parekh")
        parts = cand.split()
        while parts and parts[0].rstrip(".") in NON_NAME_WORDS:
            parts.pop(0)
        cand = " ".join(parts)
        before = sentence[max(0, m.start() - 30): m.start()]
        if re.search(r"(?:succeed|succeeds|replace|replaces|report(?:ing|s)? to|"
                     r"CEO|CFO|Chair(?:man)?)\s*(?:Mr\.|Ms\.)?\s*$", before, re.IGNORECASE):
            continue                                     # mentioned, but not the subject
        if valid_name(cand):
            found.append((cand, m.start(), False))
    if found:
        return found                                     # full name is the subject here
    # "Mr. Parekh" -> map back to a full name already seen in this filing
    for m in HONORIFIC_RE.finditer(sentence):
        last = m.group(1)
        for full in known_people:
            if full.split()[-1].rstrip(",") == last or last in full.split():
                found.append((full, m.start(), True))    # True = "Mr. X" reference
                break
    return found


def nearest_keyword_type(sentence, pos):
    """Classify a mention by the closest departure/appointment keyword."""
    best = None
    for kind, pattern in (("departure", DEPARTURE_WORDS), ("appointment", APPOINTMENT_WORDS)):
        for m in re.finditer(r"(?<![\w-])(?:" + pattern + r")\b", sentence, re.IGNORECASE):
            dist = abs(m.start() - pos)
            if best is None or dist < best[0]:
                best = (dist, kind)
    return best[1] if best else None


def keyword_types_in_clause(clause):
    kinds = set()
    if re.search(r"(?<![\w-])(?:" + DEPARTURE_WORDS + r")\b", clause, re.IGNORECASE):
        kinds.add("departure")
    if re.search(r"(?<![\w-])(?:" + APPOINTMENT_WORDS + r")\b", clause, re.IGNORECASE):
        kinds.add("appointment")
    return kinds


def extract_title(sentence, pos):
    """Title closest AFTER the name (fallback: closest anywhere in the sentence)."""
    # Best signal: the role named right after "as" / "role of" (the role being taken or left)
    for m in re.finditer(r"\b(?:as|role of|position of|become|becomes|appointed|elected)\s+(?:the\s+)?(?:Company's\s+|its\s+)?",
                         sentence[pos:]):
        t = TITLE_RE.match(sentence, pos + m.end())
        if t:
            return t.group(1).strip(" ,")
    titles = [(m.start(), m.group(1).strip(" ,")) for m in TITLE_RE.finditer(sentence)]
    after = [t for t in titles if t[0] >= pos]
    pick = min(after, key=lambda t: t[0] - pos) if after else (
        min(titles, key=lambda t: abs(t[0] - pos)) if titles else None)
    if pick:
        return pick[1]
    if BOARD_RE.search(sentence):
        return "Director"
    return NOT_FOUND


def extract_effective_date(sentence, section, filing_date):
    m = re.search(r"effective\s+(?:as\s+of\s+|on\s+)?(" + DATE_RE + r")", sentence, re.I)
    if m:
        return m.group(1)
    if re.search(r"effective\s+immediately", sentence, re.I):
        return filing_date                               # immediate = date of the filing
    m = re.search(r"(?:on|as of|at the close of business on|through|until)\s+(" + DATE_RE + r")",
                  sentence, re.I)
    if m:
        return m.group(1)
    m = re.search(r"effective\s+(?:as\s+of\s+|on\s+)?(" + DATE_RE + r")", section, re.I)
    if m:
        return m.group(1)
    return NOT_FOUND


def normalize_date(value):
    """'March 1, 2026' -> '2026-03-01'; leaves other values untouched."""
    try:
        return datetime.strptime(value, "%B %d, %Y").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return value


def extract_events(section, filing_date):
    """Return a list of event dicts (one per person) from the Item 5.02 text."""
    # Split into sentences, but not after initials/abbreviations ("Jane Q. Smith", "Mr.")
    sentences = re.split(r"(?<=[.;])(?<!\s[A-Z]\.)(?<!Mr\.)(?<!Ms\.)(?<!Dr\.)(?<!Mrs\.)"
                         r"(?<!Inc\.)(?<!Jr\.)(?<!Sr\.)(?<!Co\.)\s+(?=[A-Z(])", section)
    people = {}              # name -> {"types": set, "title": str, "effective_date": str}
    order = []

    for sent in sentences:
        if not keyword_types_in_clause(sent):
            continue                                     # biography / compensation sentences
        for name, pos, is_ref in find_names(sent, list(people.keys())):
            # Clause around this name (split on ", and" / ";" / " while ")
            clause_start = max(sent.rfind(", and ", 0, pos), sent.rfind(";", 0, pos), 0)
            nxt = [i for i in (sent.find(", and ", pos), sent.find(";", pos)) if i != -1]
            clause = sent[clause_start: min(nxt) if nxt else len(sent)]

            kind = nearest_keyword_type(sent, pos)
            if kind is None:
                continue

            if name not in people:
                people[name] = {"types": set(), "title": NOT_FOUND, "effective_date": NOT_FOUND}
                order.append(name)
            p = people[name]
            if not is_ref:                               # "Mr. X" mentions don't change the type
                p["types"].add(kind)
                # Same person leaves one role and takes another -> "both"
                if BOTH_RE.search(sent[pos:]):
                    p["types"].update({"departure", "appointment"})
            if p["title"] == NOT_FOUND:
                p["title"] = extract_title(sent, pos)
            if p["effective_date"] == NOT_FOUND:
                p["effective_date"] = extract_effective_date(sent, section, filing_date)

    # Drop names that are just a piece of a longer name found in the same filing
    order = [n for n in order
             if not any(n != other and re.search(r"\b" + re.escape(n) + r"$", other)
                        for other in order)]

    events = []
    for name in order:
        p = people[name]
        event_type = "both" if p["types"] == {"departure", "appointment"} else next(iter(p["types"]))
        events.append({
            "event_type": event_type,
            "person_name": name,
            "title": p["title"] or NOT_FOUND,
            "effective_date": normalize_date(p["effective_date"]) or NOT_FOUND,
        })
    return events


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    rows = []
    print(f"Looking for Item 5.02 8-Ks filed {CUTOFF_DATE} to {REFERENCE_DATE}\n")

    for co in COMPANIES:
        ticker, cik = co["ticker"], co["cik"]

        filings = get_executive_filings(cik)
        if filings is None:
            print(f"{ticker}: WARNING - could not reach EDGAR submissions API, skipped")
            continue
        if not filings:                                  # Edge case 1: zero filings
            print(f"{ticker}: No executive events in past 12 months")
            continue

        for f in filings:
            try:
                url = filing_doc_url(cik, f["accession"], f["primary_doc"])
                resp = sec_get(url)
                if resp is None:
                    print(f"{ticker}|{f['filing_date']}|WARNING: could not download {url}")
                    continue

                section = isolate_item_502(html_to_text(resp.content))
                events = extract_events(section, f["filing_date"])

                if not events:
                    # e.g. Item 5.02(e) compensation-only filings: no one joins or leaves
                    print(f"{ticker}|{f['filing_date']}|no departure/appointment found "
                          f"(likely compensation-only 5.02 filing) - {url}")
                    continue

                # Edge case 2: several events in one filing -> one row each
                for ev in events:
                    row = {
                        "company": co["company"],
                        "ticker": ticker,
                        "cik": cik,
                        "filing_date": f["filing_date"],
                        **ev,
                    }
                    for k, v in row.items():
                        if v is None or v == "":
                            row[k] = NOT_FOUND
                    rows.append(row)
                    print(f"{ticker}|{row['filing_date']}|{row['event_type']}|"
                          f"{row['person_name']}|{row['title']}")

            except Exception as exc:                     # never let one filing crash the run
                print(f"{ticker}|{f['filing_date']}|WARNING: unexpected error ({exc}), skipped")

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} events to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
