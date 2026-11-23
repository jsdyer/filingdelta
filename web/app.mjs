import { periodsFor, difference, compactNumber, durationDays, csv, safeSourceURL, metricLabel, orderedMetrics } from './model.mjs';
const $ = id => document.getElementById(id);
const typeLabels = { annual:'Annual (~12 months)',quarter:'About 3 months',half:'About 6 months',nine:'About 9 months',instant:'Point in time',other:'Other duration' };
let data, manifest, company, metric, periods=[], shownPeriods=12, shownFilings=9, shownChanges=6;
let requestSequence = 0, activeCapturePath = '';

const el = (tag, text, cls) => { const n=document.createElement(tag); if(text!==undefined)n.textContent=text; if(cls)n.className=cls; return n; };
const date = value => value ? new Intl.DateTimeFormat('en-CA',{year:'numeric',month:'short',day:'numeric',timeZone:'UTC'}).format(new Date(value.length===10 ? value+'T00:00:00Z' : value)) : 'Not supplied';
const exact = (value,unit) => value===null ? 'Ambiguous source values' : `${unit} ${new Intl.NumberFormat('en-CA',{maximumFractionDigits:4}).format(value)}`;
const periodLabel = p => p.start ? `${p.start} → ${p.end}` : `At ${p.end}`;
const periodDescription = p => p.start ? `${durationDays(p.start,p.end)} days · ${p.start} to ${p.end}` : `Balance at ${p.end}`;
function link(text,url,cls='') { const a=el('a',text,cls); const safe=safeSourceURL(url); if(safe){a.href=safe;a.target='_blank';a.rel='noopener noreferrer';} return a; }
function setSource(id,point){ const a=$(id),url=point&&safeSourceURL(point.url); a.hidden=!url; if(url){a.href=url;a.target='_blank';a.rel='noopener noreferrer';} }
function options(id,values,selected){const s=$(id);s.replaceChildren();for(const [value,label] of values){const o=el('option',label);o.value=value;s.append(o);}if(values.some(v=>v[0]===selected))s.value=selected;}
function download(name,content,type){const a=el('a');const url=URL.createObjectURL(new Blob([content],{type}));a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);}
function notify(message,error=false){$('status').textContent=message;$('status').classList.toggle('error',error);}
async function loadCapture(path){
  if(!/^history\/[0-9T\-Z]+\.json$/.test(path))throw new Error('Unexpected capture path');
  const sequence=++requestSequence;notify('Loading retained SEC data…');
  const response=await fetch('./data/'+path);if(!response.ok)throw new Error(`Capture unavailable (${response.status})`);
  const next=await response.json();if(next.schemaVersion!==1||!Array.isArray(next.companies)||!next.companies.length)throw new Error('Unsupported capture format');
  if(sequence!==requestSequence)return;
  activeCapturePath=path;const previousCIK=company?.cik;data=next;company=data.companies.find(c=>c.cik===previousCIK)||data.companies[0];
  $('captureDate').textContent=date(data.capturedAt)+' · '+data.capturedAt.slice(11,16)+' UTC';
  $('companyCount').textContent=data.companies.length;$('filingCount').textContent=data.companies.reduce((a,c)=>a+c.filings.length,0).toLocaleString();
  $('captureCount').textContent=manifest.captures.length;
  $('snapshotNote').textContent=manifest.captures.length===1?'One collection capture is retained so far. Earlier SEC filing records are included in this first capture; collection-to-collection history will grow after future successful runs.':`${manifest.captures.length} collection captures are retained. Use Dated capture to inspect an earlier saved collection.`;
  $('companySearch').value='';renderCompanies();selectCompany(company.cik);
  notify(`Loaded ${data.companies.length} companies · SEC capture ${date(data.capturedAt)} · Scheduled daily; this page does not submit scans or live SEC requests.`);
}
function renderCompanies(){
  if(!data)return;
  const q=$('companySearch').value.trim().toLowerCase();const container=$('companies');container.replaceChildren();
  for(const c of data.companies.filter(c=>[c.name,c.displayName,c.cik,...c.tickers].join(' ').toLowerCase().includes(q))){
    const button=el('button',undefined,'company-button');button.type='button';button.dataset.cik=c.cik;button.setAttribute('aria-pressed',String(c.cik===company.cik));button.append(el('strong',c.displayName),el('span',`${c.tickers.slice(0,2).join(' / ')||'SEC FILER'} · ${c.country==='Canada'?'CA':'US'}`));button.addEventListener('click',()=>selectCompany(c.cik));container.append(button);
  }
  if(!container.children.length)container.append(el('p','No companies in this sample match.','small-note'));
}
function selectCompany(cik){
  company=data.companies.find(c=>c.cik===cik);renderCompanies();shownFilings=9;
  $('companyName').textContent=company.displayName;$('companyMeta').textContent=company.country+' / SEC REPORTING COMPANY';
  $('companyIdentity').textContent=`${company.name} · CIK ${company.cik}`;
  $('companySource').href=`https://www.sec.gov/edgar/browse/?CIK=${company.cik}&owner=exclude`;
  const ordered=orderedMetrics(company.metrics);
  options('metric',ordered.map(m=>[m.id,metricLabel(m)]));
  options('filingForm',[['all','All selected forms'],...[...new Set(company.filings.map(f=>f.form))].sort().map(f=>[f,f])]);
  selectMetric();renderFilings();renderProvenance();
}
function selectMetric(){metric=company.metrics.find(m=>m.id===$('metric').value);options('unit',[...new Set(metric.facts.map(f=>f.unit))].sort().map(v=>[v,v]));$('conceptDescription').textContent=metric.id;$('conceptDescription').title=metric.description||'';selectUnit();}
function selectUnit(){const all=periodsFor(metric,$('unit').value);const available=new Set(all.map(p=>p.type));options('periodType',Object.keys(typeLabels).filter(k=>available.has(k)).map(k=>[k,typeLabels[k]]));selectType();}
function selectType(){shownPeriods=12;shownChanges=6;periods=periodsFor(metric,$('unit').value).filter(p=>p.type===$('periodType').value);options('currentPeriod',periods.map(p=>[p.key,periodLabel(p)]));selectCurrent();renderHistory();renderChanges();}
function selectCurrent(){const old=$('previousPeriod').value;const choices=periods.filter(p=>p.key!==$('currentPeriod').value);options('previousPeriod',choices.map(p=>[p.key,periodLabel(p)]),old);if(!choices.length)options('previousPeriod',[['','No other comparable period']]);renderComparison();}
function renderComparison(){
  const current=periods.find(p=>p.key===$('currentPeriod').value),previous=periods.find(p=>p.key===$('previousPeriod').value);
  for(const [prefix,point] of [['current',current],['previous',previous]]){
    $(prefix+'Value').textContent=point?compactNumber(point.value,point.unit):'Unavailable';
    $(prefix+'Value').title=point?exact(point.value,point.unit):'';
    $(prefix+'Details').textContent=point?`${periodDescription(point)}. Latest report: ${point.last.form}, filed ${date(point.last.filed)}.`:'No second period on this basis.';
    setSource(prefix+'Source',point?.last);
  }
  const delta=difference(current,previous);
  $('deltaValue').textContent=delta?`${delta.amount>0?'+':''}${compactNumber(delta.amount,current.unit)}`:'Not comparable';
  $('deltaDetails').textContent=delta?(delta.percent===null?'No percentage: the comparison value is zero.':`${delta.percent>0?'+':''}${delta.percent.toFixed(2)}% of the absolute comparison value.`):'Choose two unambiguous periods of similar duration in the same currency.';
  $('comparisonNote').textContent=current?.ambiguous||previous?.ambiguous?'At least one filing reports multiple values for this exact period. Inspect the source; a numeric difference is intentionally withheld.':'Values come from the latest filing in this capture for each period, which may differ from what was first reported. Compare the exact dates and accounting context before interpreting a change.';
}
function renderHistory(){
  const chart=$('chart');chart.replaceChildren();const points=periods.filter(p=>p.value!==null).slice(0,10).reverse();
  if(!points.length){chart.append(el('p','No unambiguous figures for this selection.'));}else{
    const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 700 190');svg.setAttribute('role','img');svg.setAttribute('aria-label',`${metricLabel(metric)}, ${$('unit').value}, latest reported values for ${points.length} periods`);
    const max=Math.max(...points.map(p=>Math.abs(p.value)),1),hasNegative=points.some(p=>p.value<0),zero=hasNegative?92:145,scale=(hasNegative?65:110)/max,width=650/points.length;
    const line=document.createElementNS(ns,'line');for(const[k,v]of Object.entries({x1:25,y1:zero,x2:685,y2:zero,class:'zero'}))line.setAttribute(k,v);svg.append(line);
    points.forEach((p,i)=>{const x=29+i*width,height=Math.abs(p.value)*scale;const rect=document.createElementNS(ns,'rect');for(const[k,v]of Object.entries({x:x+width*.17,y:p.value>=0?zero-height:zero,width:width*.58,height:Math.max(height,1),rx:2,class:'bar'}))rect.setAttribute(k,v);const title=document.createElementNS(ns,'title');title.textContent=`${periodLabel(p)}: ${exact(p.value,p.unit)}`;rect.append(title);svg.append(rect);
      const value=document.createElementNS(ns,'text');value.textContent=compactNumber(p.value);value.setAttribute('x',x+width*.46);value.setAttribute('y',p.value>=0?zero-height-7:zero+height+13);value.setAttribute('text-anchor','middle');svg.append(value);
      const label=document.createElementNS(ns,'text');label.textContent=p.end.slice(0,7);label.setAttribute('x',x+width*.46);label.setAttribute('y',181);label.setAttribute('text-anchor','middle');label.setAttribute('class','axis-label');svg.append(label);
    });chart.append(svg);
  }
  const body=$('periodRows');body.replaceChildren();
  for(const p of periods.slice(0,shownPeriods)){
    const row=el('tr'),pCell=el('td',p.end);pCell.append(el('small',p.start?`${p.start} · ${durationDays(p.start,p.end)} days`:'Point in time'));
    const value=el('td',exact(p.value,p.unit));const filed=el('td',p.last.filed);filed.append(el('small',p.last.form));
    const evidence=el('td');evidence.append(link('Source ↗',p.last.url));if(p.changed)evidence.append(el('small',p.ambiguous?'Ambiguous values':'Changed across filings','change-badge'));else evidence.append(el('small',`${p.filingCount} filing${p.filingCount===1?'':'s'}`));row.append(pCell,value,filed,evidence);body.append(row);
  }
  $('morePeriods').hidden=periods.length<=shownPeriods;$('morePeriods').textContent=`Show all ${periods.length} periods ↓`;
}
function renderChanges(){
  const changed=periods.filter(p=>p.changed),container=$('changes');container.replaceChildren();$('changesCount').textContent=`${changed.length} changed period${changed.length===1?'':'s'}`;
  if(!changed.length){container.append(el('div','No differing values found for this concept, currency and period basis in the retained SEC records. This does not establish that no restatements occurred.','empty'));return;}
  for(const p of changed.slice(0,shownChanges)){
    const card=el('article',undefined,'change-card');card.append(el('span',p.ambiguous?'CONTEXT NEEDS REVIEW':'EXACT PERIOD / DIFFERENT VALUES','eyebrow'),el('h3',periodLabel(p)));
    const values=el('div',undefined,'change-values');values.append(el('span',compactNumber(p.firstValue)),el('span','→'),el('span',compactNumber(p.value)));card.append(values,el('p',`${p.unit} · ${p.filingCount} filings · First: ${p.first.filed} · Latest: ${p.last.filed}`));
    const details=el('details');details.append(el('summary','Inspect reported values & filings'));const list=el('ul');for(const r of p.records){const item=el('li',`${r.filed} · ${exact(r.value,r.unit)} · `);item.append(link(r.form+' ↗',r.url));list.append(item);}details.append(list);card.append(details);container.append(card);
  }
  if(changed.length>shownChanges){const more=el('button',`Show all ${changed.length} changed periods ↓`,'text-button');more.type='button';more.addEventListener('click',()=>{shownChanges=Infinity;renderChanges();});container.append(more);}
}
function renderFilings(){const all=company.filings.filter(f=>$('filingForm').value==='all'||f.form===$('filingForm').value),container=$('filings');container.replaceChildren();for(const f of all.slice(0,shownFilings)){const card=el('article',undefined,'filing-card'),top=el('div',undefined,'filing-card-top');top.append(el('span',f.form,'filing-form'),el('time',date(f.filed)));card.append(top,el('p',f.period?`Report period: ${f.period}`:'Report period not supplied'),el('small',f.accession),link('Read original filing ↗',f.url));container.append(card);}if(!all.length)container.append(el('p','No filings of this form in the recent submission window.','empty'));$('moreFilings').hidden=all.length<=shownFilings;$('moreFilings').textContent=`Show more (${Math.max(0,all.length-shownFilings)} remaining) ↓`;}
function renderProvenance(){const box=$('provenance');box.replaceChildren(el('p',`Selected company source receipts · Retrieved ${company.capturedAt}`));for(const source of company.sources){const p=el('p');p.append(link(source.url.includes('companyfacts')?'Company Facts JSON ↗':'Submissions JSON ↗',source.url),el('br'),el('code',`SHA-256 ${source.sha256}`));box.append(p);}}
$('companySearch').addEventListener('input',renderCompanies);
$('metric').addEventListener('change',selectMetric);$('unit').addEventListener('change',selectUnit);$('periodType').addEventListener('change',selectType);$('currentPeriod').addEventListener('change',selectCurrent);$('previousPeriod').addEventListener('change',renderComparison);
$('filingForm').addEventListener('change',()=>{shownFilings=9;renderFilings();});$('moreFilings').addEventListener('click',()=>{shownFilings+=18;renderFilings();});$('morePeriods').addEventListener('click',()=>{shownPeriods=Infinity;renderHistory();});
$('capture').addEventListener('change',()=>loadCapture($('capture').value).catch(e=>{$('capture').value=activeCapturePath;notify('Could not load that capture. '+e.message,true);}));
$('exportCSV').addEventListener('click',()=>{if(!company)return;const rows=[['Company','CIK','Concept','Unit','Start','End','Value','Filed','Form','Accession','Source','Captured at']];for(const p of periods)for(const f of p.records)rows.push([company.name,company.cik,metric.id,f.unit,f.start,f.end,f.value,f.filed,f.form,f.accession,f.url,data.capturedAt]);download(`filingdelta-${company.cik}-${$('unit').value}.csv`,csv(rows),'text/csv;charset=utf-8');notify(`Downloaded ${rows.length-1} source fact records for the selected concept, currency and period basis.`);});
$('exportJSON').addEventListener('click',()=>{if(company)download(`filingdelta-${company.cik}-${data.capturedAt.slice(0,10)}.json`,JSON.stringify({schemaVersion:1,capturedAt:data.capturedAt,company},null,2),'application/json');});
try{const response=await fetch('./data/index.json');if(!response.ok)throw new Error(`Collection index unavailable (${response.status})`);manifest=await response.json();options('capture',manifest.captures.map(c=>[c.path,c.label.replace('T',' · ').replace(/(\d{2})(\d{2})(\d{2})Z$/,'$1:$2 UTC')] ),manifest.latest);await loadCapture(manifest.latest);}catch(e){notify('The retained collection could not be loaded. Reload this page, or inspect the data files on GitHub. '+e.message,true);$('companyName').textContent='Collection unavailable';}
