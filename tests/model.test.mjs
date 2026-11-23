import test from 'node:test';
import assert from 'node:assert/strict';
import { periodsFor, difference, durationDays, periodType, csv, safeSourceURL } from '../web/model.mjs';
const point=(overrides={})=>({start:'2024-01-01',end:'2024-12-31',unit:'CAD',value:100,filed:'2025-02-01',accession:'0000000001-25-000001',form:'40-F',...overrides});
test('groups only the exact date range and unit, preserving changed reported values',()=>{
 const facts=[point(),point(),point({filed:'2026-02-01',accession:'0000000001-26-000001',value:120}),point({unit:'USD',value:90}),point({start:'2024-04-01',value:75})];
 const ps=periodsFor({facts},'CAD');assert.equal(ps.length,2);const annual=ps.find(p=>p.start==='2024-01-01');assert.equal(annual.records.length,2);assert.equal(annual.firstValue,100);assert.equal(annual.value,120);assert.equal(annual.changed,true);assert.equal(annual.filingCount,2);
});
test('conflicting values inside one filing do not yield an invented comparison value',()=>{
 const p=periodsFor({facts:[point(),point({value:120})]},'CAD')[0];assert.equal(p.ambiguous,true);assert.equal(p.value,null);assert.equal(p.firstValue,null);assert.equal(difference(p,{...p,value:10}),null);
});
test('a mid-history change remains visible when the latest value returns to the first',()=>{
 const p=periodsFor({facts:[point(),point({filed:'2025-03-01',accession:'0000000001-25-000002',value:110}),point({filed:'2025-04-01',accession:'0000000001-25-000003'})]},'CAD')[0];assert.equal(p.changed,true);assert.equal(p.value,p.firstValue);
});
test('classifies actual durations without reconstructing quarterly values',()=>{
 assert.equal(durationDays('2024-01-01','2024-12-31'),366);assert.equal(periodType(point()),'annual');assert.equal(periodType(point({start:'2024-01-01',end:'2024-06-30'})),'half');assert.equal(periodType(point({start:null})),'instant');
 const ps=periodsFor({facts:[point({end:'2024-03-31',value:25}),point({end:'2024-06-30',value:60})]},'CAD');assert.equal(ps.length,2);assert.equal(ps.some(p=>p.start==='2024-04-01'),false);
});
test('differences isolate currency and duration, handle zero and negative baselines',()=>{
 const p={start:'2024-01-01',end:'2024-12-31',type:'annual',unit:'CAD',value:120};const previous={...p,value:100};assert.deepEqual(difference(p,previous),{amount:20,percent:20});assert.equal(difference(p,{...previous,unit:'USD'}),null);assert.equal(difference(p,{...previous,type:'quarter'}),null);assert.equal(difference(p,{...previous,start:'2024-03-01'}),null);assert.deepEqual(difference(p,{...previous,value:0}),{amount:120,percent:null});assert.deepEqual(difference({...p,value:-80},{...previous,value:-100}),{amount:20,percent:20});
});
test('CSV preserves quotes and prevents spreadsheet formula execution without corrupting numeric negatives',()=>{assert.equal(csv([['=HYPERLINK("bad")','a,b',-20]]),'"\'=HYPERLINK(""bad"")","a,b","-20"');});
test('source links reject script and lookalike hosts',()=>{assert.equal(safeSourceURL('javascript:alert(1)'),null);assert.equal(safeSourceURL('https://www.sec.gov.evil.test/'),null);assert.equal(safeSourceURL('http://www.sec.gov/'),null);assert.equal(safeSourceURL('https://www.sec.gov/Archives/example'),'https://www.sec.gov/Archives/example');});
