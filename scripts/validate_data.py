"""Validate published captures without network access."""
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def validate(root=ROOT):
    data = root / "data"
    index = json.loads((data / "index.json").read_text())
    paths = [capture["path"] for capture in index["captures"]]
    if not paths or index["latest"] not in paths or len(paths) != len(set(paths)):
        raise ValueError("Invalid capture index")
    for path in paths:
        if not re.fullmatch(r"history/[0-9TZ-]+\.json", path):
            raise ValueError("Unexpected capture path")
        capture = json.loads((data / path).read_text())
        if capture["schemaVersion"] != 1 or len(capture["companies"]) != 6:
            raise ValueError("Capture requires six companies")
        for company in capture["companies"]:
            if not company["filings"] or not company["metrics"] or not company["capturedAt"]:
                raise ValueError("Empty company record")
            for source in company["sources"]:
                if not source["url"].startswith("https://data.sec.gov/") or not re.fullmatch(r"[a-f0-9]{64}", source["sha256"]):
                    raise ValueError("Invalid source receipt")
            for metric in company["metrics"]:
                for fact in metric["facts"]:
                    if not isinstance(fact["value"], (int, float)) or isinstance(fact["value"], bool) or not math.isfinite(fact["value"]):
                        raise ValueError("Invalid fact value")
                    if not fact["filed"] or not fact["url"].startswith("https://www.sec.gov/Archives/edgar/data/"):
                        raise ValueError("Missing fact evidence")
    return len(paths)


if __name__ == "__main__":
    print(f"Validated {validate()} retained SEC capture(s)")
