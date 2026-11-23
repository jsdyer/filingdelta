#!/usr/bin/env python3
"""Collect a small, identified SEC sample. Never replace good data on failure."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = os.environ.get("SEC_USER_AGENT", "CoolCode FilingDelta Jeffrey Dyer jeffdyer@gmail.com")
COMPANIES = [
    ("0001594805", "Canada", "Shopify"),
    ("0001000275", "Canada", "Royal Bank of Canada"),
    ("0001017413", "Canada", "Canadian Natural Resources"),
    ("0000320193", "United States", "Apple"),
    ("0000789019", "United States", "Microsoft"),
    ("0001018724", "United States", "Amazon"),
]
CONCEPTS = {
    "us-gaap": {
        "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
        "Assets", "Liabilities", "NetIncomeLoss", "CashAndCashEquivalentsAtCarryingValue",
        "StockholdersEquity", "LongTermDebtCurrent", "LongTermDebtNoncurrent",
    },
    "ifrs-full": {
        "Revenue", "Assets", "Liabilities", "ProfitLoss", "CashAndCashEquivalents",
        "Equity", "Borrowings", "InterestIncome", "InterestExpense",
    },
}
FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A", "40-F", "40-F/A", "6-K", "6-K/A", "8-K", "8-K/A"}
DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")
ACCESSION = re.compile(r"\d{10}-\d{2}-\d{6}$")
MAX_PUBLISHED_CAPTURES = 90


def filing_url(cik, accession, document=None):
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"
    return base + (document if document else accession + "-index.html")


def normalize(cik, country, display_name, submissions, companyfacts, captured_at, sources):
    if int(submissions["cik"]) != int(cik) or int(companyfacts["cik"]) != int(cik):
        raise ValueError("SEC CIK mismatch")
    recent = submissions["filings"]["recent"]
    keys = ["accessionNumber", "filingDate", "reportDate", "form", "primaryDocument"]
    count = len(recent["accessionNumber"])
    if any(len(recent[key]) != count for key in keys):
        raise ValueError("SEC submission columns have different lengths")
    filings = []
    for i in range(count):
        if recent["form"][i] not in FORMS:
            continue
        accn = recent["accessionNumber"][i]
        if not ACCESSION.fullmatch(accn) or not DATE.fullmatch(recent["filingDate"][i]):
            raise ValueError("Invalid accession or filing date")
        document = recent["primaryDocument"][i]
        if document.startswith(("/", ".")) or ":" in document:
            raise ValueError("Unexpected filing document path")
        filings.append({
            "accession": accn, "filed": recent["filingDate"][i], "period": recent["reportDate"][i],
            "form": recent["form"][i], "document": document,
            "url": filing_url(cik, accn, document),
        })
    metrics = []
    for taxonomy, concepts in CONCEPTS.items():
        for concept in sorted(concepts):
            raw = companyfacts.get("facts", {}).get(taxonomy, {}).get(concept)
            if not raw:
                continue
            records = []
            for unit, points in raw.get("units", {}).items():
                # These selected concepts are monetary. Keep currencies separate.
                if not re.fullmatch(r"[A-Z]{3}", unit):
                    continue
                for point in points:
                    end, accn, value = point.get("end", ""), point.get("accn", ""), point.get("val")
                    if end < "2018-01-01" or point.get("form") not in FORMS:
                        continue
                    if not DATE.fullmatch(end) or not ACCESSION.fullmatch(accn) or not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                        raise ValueError("Malformed selected SEC fact")
                    if point.get("start") and (not DATE.fullmatch(point["start"]) or point["start"] > end):
                        raise ValueError("Malformed period start")
                    if not DATE.fullmatch(point.get("filed", "")):
                        raise ValueError("Malformed filing date")
                    records.append({
                        "start": point.get("start"), "end": end, "value": value, "unit": unit,
                        "filed": point.get("filed"), "accession": accn, "form": point["form"],
                        "fiscalYear": point.get("fy"), "fiscalPeriod": point.get("fp"),
                        "frame": point.get("frame"), "url": filing_url(cik, accn),
                    })
            if records:
                metrics.append({"id": f"{taxonomy}:{concept}", "label": raw.get("label") or concept,
                                "description": raw.get("description") or "", "facts": records})
    if not metrics or not filings:
        raise ValueError(f"No usable facts/filings for {display_name}")
    return {"cik": cik, "name": submissions["name"], "displayName": display_name, "country": country,
            "tickers": submissions.get("tickers", []), "exchanges": submissions.get("exchanges", []),
            "fiscalYearEnd": submissions.get("fiscalYearEnd"), "capturedAt": captured_at,
            "sources": sources, "filings": filings, "metrics": metrics}


def fetch(url):
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=90) as response:
        content = response.read(40_000_001)
        if len(content) > 40_000_000:
            raise ValueError("SEC response exceeded the collection size limit")
    return json.loads(content), {"url": url, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}


def validate_companies(companies):
    """Reject configuration mistakes before making source requests."""
    if not isinstance(companies, (list, tuple)) or not companies:
        raise ValueError("COMPANIES must contain at least one company")
    seen = set()
    for entry in companies:
        if not isinstance(entry, (list, tuple)) or len(entry) != 3:
            raise ValueError("Each company needs (CIK, country, display name)")
        cik, country, name = entry
        if not isinstance(cik, str) or not re.fullmatch(r"[0-9]{10}", cik) or int(cik) == 0:
            raise ValueError("Use a ten-digit SEC CIK string, including leading zeroes")
        if cik in seen:
            raise ValueError(f"Duplicate company CIK: {cik}")
        if not all(isinstance(value, str) and value.strip() for value in (country, name)):
            raise ValueError("Company country and display name cannot be empty")
        seen.add(cik)


def collect():
    validate_companies(COMPANIES)
    if "@" not in USER_AGENT or len(USER_AGENT) < 20:
        raise ValueError("SEC_USER_AGENT must identify the application and a contact email")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    captured_at = now.isoformat().replace("+00:00", "Z")
    companies = []
    for cik, country, name in COMPANIES:
        print(f"Collecting {name}", flush=True)
        submissions, s_source = fetch(f"https://data.sec.gov/submissions/CIK{cik}.json")
        time.sleep(1)
        facts, f_source = fetch(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
        time.sleep(1)
        companies.append(normalize(cik, country, name, submissions, facts, captured_at, [s_source, f_source]))
    result = {"schemaVersion": 1, "capturedAt": captured_at, "periodsFrom": "2018-01-01", "companies": companies}
    folder = ROOT / "data"
    folder.mkdir(exist_ok=True)
    history = folder / "history"
    history.mkdir(exist_ok=True)
    filename = now.strftime("%Y-%m-%dT%H%M%SZ") + ".json"
    path = history / filename
    # Only publish after every response is validated; never overwrite an older capture.
    with path.open("x", encoding="utf-8") as output:
        json.dump(result, output, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        output.write("\n")
    all_captures = sorted((p.name for p in history.glob("*.json")), reverse=True)
    captures = all_captures[:MAX_PUBLISHED_CAPTURES]
    index = {"schemaVersion": 1, "latest": "history/" + filename,
             "captures": [{"path": "history/" + p, "label": p.replace(".json", "")} for p in captures]}
    temporary = folder / "index.next.json"
    temporary.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    temporary.replace(folder / "index.json")
    # Older committed captures remain available through git history, keeping Pages small.
    for old in all_captures[MAX_PUBLISHED_CAPTURES:]:
        (history / old).unlink()
    print(f"Retained {path.relative_to(ROOT)} with {len(companies)} companies", flush=True)


if __name__ == "__main__":
    collect()
