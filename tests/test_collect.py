import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from collect import normalize, filing_url
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


if __name__ == '__main__': unittest.main()
