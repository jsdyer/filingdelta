"""Exercise the built starter at a project subpath in Chromium."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import tempfile
import threading
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    screenshots = ROOT / "browser-checks"
    screenshots.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        shutil.copytree(ROOT / "dist", Path(temporary) / "example-tool")
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=temporary))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 1000})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}/example-tool/")
                page.locator('#companyName').filter(has_text='Shopify').wait_for()
                assert page.locator('#currentValue').inner_text().startswith('USD ')
                assert page.locator('#periodRows tr').count() > 0
                page.locator('#companySearch').fill('Royal')
                assert page.locator('.company-button').count() == 1
                page.locator('.company-button').click()
                assert page.locator('#companyName').inner_text() == 'Royal Bank of Canada'
                assert page.locator('#unit').input_value() == 'CAD'
                assert page.locator('#metric').input_value() == 'ifrs-full:Revenue'
                assert page.locator('#currentValue').inner_text().startswith('CAD ')
                assert '/1000275/' in page.locator('#currentSource').get_attribute('href')
                assert '/1000275/' in page.locator('#previousSource').get_attribute('href')
                assert '/1000275/' in page.locator('#filings a').first.get_attribute('href')
                assert page.locator('#currentSource').get_attribute('href').startswith('https://www.sec.gov/Archives/')
                page.locator('#periodType').select_option('annual')
                assert page.locator('#changes .change-card').count() > 0
                page.locator('#changes details').first.click()
                assert page.locator('#changes details').first.get_attribute('open') is not None
                with page.expect_download() as download:
                    page.locator('#exportCSV').click()
                assert download.value.suggested_filename.endswith('.csv')
                page.locator('#companySearch').fill('<img onerror=alert(1)>')
                assert page.locator('.company-button').count() == 0
                assert page.locator('img').count() == 0
                page.locator('#companySearch').fill('')
                page.locator('[data-cik="0001017413"]').click()
                assert page.locator('#unit').input_value() == 'CAD'
                assert '/1017413/' in page.locator('#currentSource').get_attribute('href')
                page.locator('[data-cik="0000320193"]').click()
                assert page.locator('#unit').input_value() == 'USD'
                assert '/320193/' in page.locator('#currentSource').get_attribute('href')
                page.locator('#metric').select_option('us-gaap:Assets')
                assert page.locator('#periodType').input_value() == 'instant'
                assert page.locator('#previousPeriod option').count() > 0
                page.locator('#filingForm').select_option('10-K')
                assert page.locator('.filing-form').first.inner_text() == '10-K'
                page.screenshot(path=str(screenshots / "desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.screenshot(path=str(screenshots / "mobile.png"), full_page=True)
                assert not errors, errors
                browser.close()
            print("Browser checks passed: project subpath, SEC data, company/concept/period/form filters, evidence, CSV and mobile layout")
        finally:
            server.shutdown()


if __name__ == "__main__":
    main()
