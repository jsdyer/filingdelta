# Filing Delta

A public, browser-based SEC EDGAR explorer at [coolcode.ca/filingdelta/](https://coolcode.ca/filingdelta/). Compare reported financial periods, inspect different values reported for an identical period, and follow the original filings. No API key or financial account is needed.

<!-- coolcode:guide -->
Choose Shopify, Royal Bank of Canada, Canadian Natural Resources, Apple, Microsoft or Amazon, then select a financial concept, currency and period basis. The ledger compares exact reported periods and links each value to its SEC filing; a changed value may reflect a recast or context difference, not necessarily a restatement. Daily captures retain selected standard financial facts from 2018 onward, not a complete company or filing universe.
<!-- /coolcode:guide -->

## What works

- Search the curated company sample by name, ticker or SEC CIK.
- Select a US GAAP or IFRS financial concept and a reporting currency. Revenue aliases remain distinct concepts; the most recently reported revenue concept is the default.
- Compare two annual, roughly quarterly, half-year, nine-month or point-in-time periods. Exact start/end dates remain visible. Different currencies or duration types are not combined.
- Inspect a chart and ledger of latest reported values. Download all underlying filing-level facts for the current filter as CSV.
- Inspect different values reported for **the same company, taxonomy/concept, currency, start and end dates**. Expand each period to see the original filing links.
- Filter recent financial filings by form, including 10-K, 10-Q, 20-F, 40-F, 6-K, 8-K and their amendments.
- Select an earlier retained collection capture, export a company JSON receipt and inspect source-response SHA-256 hashes.

For an interesting comparison, select **Royal Bank of Canada → Revenue → CAD → Annual**. Some exact periods have different values across filings; open the linked original reports to establish the accounting explanation. The first capture also contains historical SEC filing facts. These records do **not** imply the tool has been collecting since 2018.

## Sources and limitations

[SEC EDGAR API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) and [SEC developer resources](https://www.sec.gov/about/developer-resources).

The collector fetches each company's public Submissions and Company Facts JSON. No registration is required. SEC's API does not support browser CORS, so visitors query published local snapshots, not a proxy or the live SEC API.

Company Facts includes selected standardized, whole-entity US GAAP/IFRS facts. This tool retains only the concepts listed in `scripts/collect.py` and periods ending in 2018 or later. Custom tags, segment data, many metrics and older periods are excluded. An absent concept is not a zero. The submissions shelf uses the SEC **recent** window, which varies in length; it does not traverse older referenced submission files. Financial facts can contain filings outside that recent shelf and retain independent accession links.

Country labels identify the company; they do not dictate reporting currency. Figures are not currency-converted. “Annual” and “~3 months” are duration groupings, not promises that fiscal and calendar quarters align. We never subtract year-to-date facts to invent quarterly values. Differences use the latest available report for each exact period; a percentage is the difference divided by the absolute comparison value. No percentage is shown for zero. The comparison is withheld for different duration types, durations more than 14 days apart or ambiguous values within the relevant filing.

A changed value is a comparison signal, not an accounting conclusion. Recasts, corrections and reporting context differences can all matter. The source filing is authoritative. Different tags are never merged into a supposedly continuous series.

## Refresh and retained history

`.github/workflows/pages.yml` runs at **08:45 UTC daily**, on pushes/PRs and manually. Schedules may be delayed by GitHub. The visible capture time is the actual successful collection timestamp. Manual runs offer `refresh_data`; ordinary push and PR builds are offline.

The six-company collector makes requests sequentially, at least one second apart, using:

```
CoolCode FilingDelta Jeffrey Dyer jeffdyer@gmail.com
```

This identifies the app and contact under SEC fair access and remains well below the SEC's 10 requests/second limit. `SEC_USER_AGENT` can override the identity for a fork; it must include a contact email. No secret is required for this deployment.

All twelve responses must parse and validate before a new snapshot is written. HTTP failures, invalid CIKs, malformed values or empty company results abort the refresh. The deployment and committed prior capture remain unchanged. Source response hashes identify the fetched inputs; the published data is a filtered normalized derivative, not the full raw API responses.

`data/history/<UTC-timestamp>.json` holds each successful capture, and `data/index.json` selects the latest. The latest 90 successful captures are published in the date selector; older committed captures remain retrievable through Git history. This bounds the static site size while preserving the filing-level history within each snapshot. The workflow validates data, runs unit checks and browser smoke tests, and only then commits the data update and publishes. Git history additionally preserves changes. A new app initially has one collection capture; source filing history can already be much older.

## Privacy and browser behavior

Searches and filters run locally over the static data. No API key, financial account, pasted query or uploaded file is requested. No preferences are stored. CSV and JSON exports are browser downloads. Source links go to the SEC. The shared CoolCode visit-counter script records aggregate tool opens, not searches or financial selections.

## Develop and verify

Python standard library and browser ES modules; no npm install or build framework needed.

```sh
python3 scripts/collect.py          # explicit network refresh, optional
python3 scripts/validate_data.py    # offline
node --test tests/*.test.mjs
python3 -m unittest discover -s tests -v
python3 scripts/build.py            # offline; outputs dist/
```

CI installs the test-only Playwright dependency from `tests/browser-requirements.txt` and runs `python3 tests/browser_smoke.py` at a project subpath. Tests cover exact period grouping, differing values, ambiguous contexts, currency/duration isolation, zero and negative baselines, source links, safe CSV, collection validation, browser filtering, downloads and mobile width.

`web/` contains the application; `data/` contains dated facts; `scripts/` contains collection/build/validation; `tests/` contains checks. No CNAME is used. The account Pages site supplies the CoolCode domain.
