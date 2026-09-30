"""
dump_502.py - debugging helper for hw03_executives.py
Saves the Item 5.02 section of every matching 8-K to Data/502_<TICKER>_<date>.txt
Run:  python dump_502.py
"""
from pathlib import Path
import hw03_executives as x

out = Path(__file__).resolve().parent / "Data"
out.mkdir(exist_ok=True)
for co in x.COMPANIES:
    for f in x.get_executive_filings(co["cik"]) or []:
        resp = x.sec_get(x.filing_doc_url(co["cik"], f["accession"], f["primary_doc"]))
        if resp is None:
            continue
        section = x.isolate_item_502(x.html_to_text(resp.content))
        name = f"502_{co['ticker']}_{f['filing_date']}_{f['accession'][-6:]}.txt"
        (out / name).write_text(section, encoding="utf-8")
        print("saved", name)
