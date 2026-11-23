/** Pure, exact-context comparisons: no fiscal-quarter reconstruction. */
export function durationDays(start, end) {
  if (!start) return null;
  return Math.round((Date.parse(end) - Date.parse(start)) / 86400000) + 1;
}
export function periodType(point) {
  const days = durationDays(point.start, point.end);
  if (days === null) return 'instant';
  if (days >= 330 && days <= 380) return 'annual';
  if (days >= 75 && days <= 105) return 'quarter';
  if (days >= 165 && days <= 200) return 'half';
  if (days >= 255 && days <= 290) return 'nine';
  return 'other';
}
export function periodsFor(metric, unit) {
  const map = new Map();
  for (const fact of metric?.facts ?? []) {
    if (fact.unit !== unit) continue;
    const key = `${fact.start ?? ''}|${fact.end}`;
    if (!map.has(key)) map.set(key, { key, start: fact.start, end: fact.end, unit, type: periodType(fact), records: [] });
    const period = map.get(key);
    if (!period.records.some(r => r.accession === fact.accession && r.value === fact.value && r.filed === fact.filed)) period.records.push(fact);
  }
  return [...map.values()].map(period => {
    period.records.sort((a,b) => a.filed.localeCompare(b.filed) || a.accession.localeCompare(b.accession));
    const first = period.records[0], last = period.records.at(-1);
    const earliest = period.records.filter(r => r.accession === first.accession);
    const latest = period.records.filter(r => r.accession === last.accession);
    const firstValues = new Set(earliest.map(r => r.value)), lastValues = new Set(latest.map(r => r.value));
    return { ...period, first, last, firstValue: firstValues.size === 1 ? first.value : null,
      value: lastValues.size === 1 ? last.value : null,
      ambiguous: firstValues.size > 1 || lastValues.size > 1,
      changed: new Set(period.records.map(r => r.value)).size > 1,
      filingCount: new Set(period.records.map(r => r.accession)).size };
  }).sort((a,b) => b.end.localeCompare(a.end) || (b.start ?? '').localeCompare(a.start ?? ''));
}
export function difference(current, previous) {
  if (!current || !previous || current.unit !== previous.unit || current.type !== previous.type || current.value === null || previous.value === null) return null;
  const nowDays = durationDays(current.start,current.end), thenDays = durationDays(previous.start,previous.end);
  if (nowDays !== null && Math.abs(nowDays - thenDays) > 14) return null;
  const amount = current.value - previous.value;
  return { amount, percent: previous.value === 0 ? null : amount / Math.abs(previous.value) * 100 };
}
export function compactNumber(value, unit='') {
  if (value === null || value === undefined) return 'Ambiguous';
  return `${unit ? unit + ' ' : ''}${new Intl.NumberFormat('en-CA',{notation:'compact',maximumFractionDigits:2}).format(value)}`;
}
export function csv(rows) {
  return rows.map(row => row.map(value => {
    let text = value === null || value === undefined ? '' : String(value);
    if (typeof value === 'string' && /^[=+\-@\t\r]/.test(text)) text = "'" + text;
    return '"' + text.replaceAll('"','""') + '"';
  }).join(',')).join('\r\n');
}
export function safeSourceURL(url) {
  try { const u = new URL(url); return u.protocol === 'https:' && ['www.sec.gov','data.sec.gov'].includes(u.hostname) ? u.href : null; }
  catch { return null; }
}
