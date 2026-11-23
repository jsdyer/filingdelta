import copy
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import collect as collector
from collect import normalize, filing_url, validate_companies
from validate_data import validate


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.submissions = {'cik':'0000000001','name':'Example','filings':{'recent':{
            'accessionNumber':['0000000001-25-000001'],'filingDate':['2025-02-01'],
            'reportDate':['2024-12-31'],'form':['40-F'],'primaryDocument':['report.htm']}}}
        self.point = {'start':'2024-01-01','end':'2024-12-31','val':100,
                      'accn':'0000000001-25-000001','filed':'2025-02-01','form':'40-F'}
        self.facts = {'cik':1,'facts':{'ifrs-full':{'Revenue':{'label':'Revenue','units':{'CAD':[self.point]}}}}}

    def normalize(self):
        return normalize('0000000001','Canada','Example',self.submissions,self.facts,'2025-03-01T00:00:00Z',[])

    def test_retains_exact_source_period_and_original_filing_links(self):
        company=self.normalize();fact=company['metrics'][0]['facts'][0]
        self.assertEqual((fact['start'],fact['end'],fact['value'],fact['unit']),('2024-01-01','2024-12-31',100,'CAD'))
        self.assertEqual(company['filings'][0]['url'],'https://www.sec.gov/Archives/edgar/data/1/000000000125000001/report.htm')
        self.assertTrue(fact['url'].endswith('0000000001-25-000001-index.html'))

    def test_null_sec_ifrs_labels_fall_back_to_the_concept(self):
        self.facts['facts']['ifrs-full']['Revenue'].update(label=None, description=None)
        metric=self.normalize()['metrics'][0]
        self.assertEqual(metric['label'],'Revenue')
        self.assertEqual(metric['description'],'')

    def test_mismatched_companies_and_ragged_submission_columns_fail(self):
        self.facts['cik']=2
        with self.assertRaisesRegex(ValueError,'CIK'): self.normalize()
        self.facts['cik']=1;self.submissions['filings']['recent']['form']=[]
        with self.assertRaisesRegex(ValueError,'columns'): self.normalize()

    def test_nonfinite_or_boolean_facts_fail_before_publication(self):
        for bad in (float('nan'),float('inf'),True):
            self.point['val']=bad
            with self.assertRaisesRegex(ValueError,'Malformed'): self.normalize()

    def test_older_periods_are_excluded_and_missing_selected_facts_do_not_publish(self):
        self.point['end']='2017-12-31'
        with self.assertRaisesRegex(ValueError,'No usable'): self.normalize()

    def test_real_published_collection_validates_offline(self):
        self.assertGreaterEqual(validate(),1)

    def test_adding_a_seventh_company_populates_a_new_capture_and_preserves_old_coverage(self):
        companies = [(f'{i:010d}', 'Canada', f'Example {i}') for i in range(1, 8)]
        def source(url):
            cik = re.search(r'CIK([0-9]{10})', url).group(1)
            payload = copy.deepcopy(self.facts if '/companyfacts/' in url else self.submissions)
            payload['cik'] = int(cik)
            payload['tickers'] = [f'TEST{int(cik)}']
            return payload, {'url': url, 'sha256': 'a' * 64, 'bytes': 100}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(collector, 'ROOT', root), patch.object(collector, 'fetch', side_effect=source), patch.object(collector.time, 'sleep'):
                # Save an older six-company capture, then change only the configuration.
                with patch.object(collector, 'COMPANIES', companies[:6]):
                    collector.collect()
                index_path = root / 'data/index.json'
                old_index = json.loads(index_path.read_text())
                old_path = root / 'data' / old_index['latest']
                archived_path = root / 'data/history/2020-01-01T000000Z.json'
                old_path.rename(archived_path)
                old_index['latest'] = 'history/' + archived_path.name
                old_index['captures'][0]['path'] = old_index['latest']
                index_path.write_text(json.dumps(old_index))
                original = archived_path.read_bytes()
                with patch.object(collector, 'COMPANIES', companies):
                    collector.collect()
                current = json.loads((root / 'data' / json.loads(index_path.read_text())['latest']).read_text())
                self.assertEqual(len(current['companies']), 7)
                self.assertEqual(current['companies'][-1]['displayName'], 'Example 7')
                self.assertEqual(current['companies'][-1]['tickers'], ['TEST7'])
                self.assertEqual(archived_path.read_bytes(), original)
                self.assertEqual(validate(root), 2)
                before_failure = index_path.read_bytes()
                with patch.object(collector, 'COMPANIES', companies + [('0000000008', 'Canada', 'Unavailable')]), patch.object(collector, 'fetch', side_effect=OSError('Source unavailable')):
                    with self.assertRaises(OSError):
                        collector.collect()
                self.assertEqual(index_path.read_bytes(), before_failure)

    def test_configuration_rejects_bad_and_duplicate_ciks_before_fetching(self):
        valid = ('0000000001', 'Canada', 'Example')
        for bad in ([], [valid, valid], [('1', 'Canada', 'Example')], [('0000000000', 'Canada', 'Example')], [('0000000001', '', 'Example')], [('0000000001', 'Canada')]):
            with self.subTest(companies=bad), patch.object(collector, 'COMPANIES', bad), patch.object(collector, 'fetch') as fetch:
                with self.assertRaises(ValueError):
                    collector.collect()
                fetch.assert_not_called()
        validate_companies([valid])

    def test_capture_rejects_empty_or_duplicate_company_identities(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'data/history').mkdir(parents=True)
            path = 'history/2025-01-01T000000Z.json'
            (root / 'data/index.json').write_text(json.dumps({'latest': path, 'captures': [{'path': path}]}))
            company = self.normalize()
            for companies in ([], [company, company]):
                (root / 'data' / path).write_text(json.dumps({'schemaVersion': 1, 'companies': companies}))
                with self.assertRaises(ValueError):
                    validate(root)


if __name__ == '__main__': unittest.main()
