// Rebuild from the frozen, non-personal aggregate data. No database credentials.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const data = JSON.parse(await fs.readFile(path.join(here, 'data/analysis.json'), 'utf8'));
const cfg = JSON.parse(await fs.readFile(path.join(here, 'config.json'), 'utf8'));
const out = path.join(root, 'outputs/portfolio-2026-10-17');
const preview = path.join(root, 'var/portfolio-build');
await fs.mkdir(out, { recursive: true });
await fs.mkdir(preview, { recursive: true });
const wb = Workbook.create();
const names = ['Overview', 'Stations', 'Daily coverage', 'Time patterns', 'Nearby alternatives', 'Source QA', 'Read Me'];
const sh = Object.fromEntries(names.map(n => [n, wb.worksheets.add(n)]));
const ink = '#173B32', green = '#287D65', amber = '#FFF0D5';
for (const s of Object.values(sh)) {
  s.showGridLines = false;
  s.getRange('A1:P45').format.font = { name: 'Arial', size: 11, color: '#243A35' };
  s.getRange('A1:P45').format.rowHeight = 21;
  s.getRange('A1:A45').format.columnWidth = 3;
}
sh.Overview.tabColor = ink;
sh['Read Me'].tabColor = '#A6AAA6';
function cell(s, a, v) { s.getRange(a).values = [[v]]; }
function formula(s, a, f) { s.getRange(a).formulas = [[f]]; }
function title(s, text, note) {
  cell(s, 'B2', text); s.getRange('B2').format.font = { name:'Arial',size:17,bold:true,color:ink };
  s.getRange('B3:M3').format.borders = {bottom:{style:'thin',color:green}};
  cell(s, 'B4', note); s.getRange('B4').format.font = {name:'Arial',size:11,italic:true,color:'#64756C'};
}
function table(s, headers, rows, name, widths, start=6) {
  const end = start+rows.length;
  const range = s.getRangeByIndexes(start-1,1,rows.length+1,headers.length);
  range.values = [headers,...rows];
  range.format.font = {name:'Arial',size:11,color:'#243A35'};
  range.format.rowHeight = 23;
  range.format.verticalAlignment = 'center';
  range.format.numberFormat = '#,##0';
  const t = s.tables.add(`B${start}:${String.fromCharCode(65+headers.length)}${end}`, true,name);
  t.showFilterButton=true;
  const head=s.getRangeByIndexes(start-1,1,1,headers.length);
  head.format={fill:ink,font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',rowHeight:40};
  widths.forEach((w,i)=>s.getRangeByIndexes(start-1,i+1,rows.length+1,1).format.columnWidth=w);
  s.freezePanes.freezeRows(start);
  return end;
}
function percent(s, range) { s.getRange(range).setNumberFormat('0.0%'); }
function chart(s,type,categories,values,titleText,position,pct=true) {
  const c=s.charts.add(type,[s.getRange(categories),s.getRange(values)]);
  c.title=titleText; c.hasLegend=false;
  c.titleTextStyle.fontSize=14; c.titleTextStyle.typeface='Arial';
  c.xAxis={axisType:'textAxis',textStyle:{typeface:'Arial',fontSize:11}};
  c.yAxis={min:0,max:pct?1:undefined,numberFormatCode:pct?'0%':'#,##0',numberFormatSourceLinked:false,textStyle:{typeface:'Arial',fontSize:11}};
  c.series.items[0].fill=green;
  if(type==='line') c.series.items[0].line={fill:green,style:'solid',width:2};
  c.setPosition(...position);
  return c;
}

const q=data.quality[0];
title(sh['Source QA'],'Source quality and exclusions','Frozen SQL counts. These are report observations, not rider trips.');
const keys=Object.keys(q);
table(sh['Source QA'],['SQL metric','Count'],keys.map(k=>[k,q[k]]),'QualityCounts',[43,19]);
const qref=k=>`'Source QA'!C${7+keys.indexOf(k)}`;
const sr=keys.length+10;
cell(sh['Source QA'],`B${sr-2}`,'Freshness sensitivity');
table(sh['Source QA'],['Freshness limit (s)','Eligible reports','Available reports','Availability'],data.sensitivity.map(r=>[r.fresh_seconds,r.reports,r.available_reports,null]),'FreshnessSensitivity',[43,19,20,18],sr);
data.sensitivity.forEach((r,i)=>formula(sh['Source QA'],`E${sr+1+i}`,`=D${sr+1+i}/C${sr+1+i}`));
percent(sh['Source QA'],`E${sr+1}:E${sr+3}`);

title(sh.Stations,'Station analysis','Filter the table. Ranking support: 100 unique reports on at least 5 observed dates.');
const stationRows=data.stations.map(r=>[r.station_id,r.name??'Unknown metadata',r.reports,r.available_reports,r.full_reports,r.observed_days,r.observed_hours,r.docks_sum,null,null,null,r.ranking_eligible?'Included':'Low support']);
const se=table(sh.Stations,['Station ID','Station name','Reports','Available','Full','Dates','Hours','Docks sum','Availability','Full rate','Mean docks','Ranking support'],stationRows,'StationAnalysis',[14,47,15,15,14,12,12,17,17,16,16,20]);
sh.Stations.getRange(`B7:B${se}`).setNumberFormat('@');
for(let r=7;r<=se;r++) {
  formula(sh.Stations,`J${r}`,`=E${r}/D${r}`);
  formula(sh.Stations,`K${r}`,`=F${r}/D${r}`);
  formula(sh.Stations,`L${r}`,`=I${r}/D${r}`);
}
percent(sh.Stations,`J7:K${se}`); sh.Stations.getRange(`L7:L${se}`).setNumberFormat('0.0');
sh.Stations.getRange(`K7:K${se}`).conditionalFormats.add('colorScale',{colors:['#FFFFFF','#F2C57C'],thresholds:['min','max']});
sh.Stations.freezePanes.freezeColumns(3);

title(sh['Daily coverage'],'Collection coverage by date','Toronto dates. First and last dates are partial days; absent polls are counted.');
const de=table(sh['Daily coverage'],['Date','Expected polls','Attempted','Successful','Partial','Failed','Reports','Available','Docks sum','Stations','Poll coverage','Availability'],data.daily.map(r=>[new Date(r.local_date+'T00:00:00Z'),r.expected_minutes,r.attempted_minutes,r.successful_minutes,r.partial_minutes,r.failed_minutes,r.reports,r.available_reports,r.docks_sum,r.stations,null,null]),'DailyCoverage',[16,17,15,15,13,13,16,16,17,14,18,18]);
sh['Daily coverage'].getRange(`B7:B${de}`).setNumberFormat('yyyy-mm-dd');
for(let r=7;r<=de;r++) {
  formula(sh['Daily coverage'],`L${r}`,`=E${r}/C${r}`);
  formula(sh['Daily coverage'],`M${r}`,`=IF(H${r}=0,"n.a.",I${r}/H${r})`);
}
percent(sh['Daily coverage'],`L7:M${de}`);
sh['Daily coverage'].getRange(`M7:M${de}`).format.horizontalAlignment='right';

title(sh['Time patterns'],'Availability by local hour','Report-weighted comparisons. Uneven date and station mixes prevent causal conclusions.');
const te=table(sh['Time patterns'],['Hour','Day type','Reports','Available','Docks sum','Observed dates','Stations','Availability','Mean docks'],data.time_patterns.map(r=>[r.local_hour,r.day_type,r.reports,r.available_reports,r.docks_sum,r.observed_days,r.stations,null,null]),'TimePatterns',[12,16,17,17,18,18,15,18,17]);
for(let r=7;r<=te;r++) {
  formula(sh['Time patterns'],`I${r}`,`=E${r}/D${r}`);
  formula(sh['Time patterns'],`J${r}`,`=F${r}/D${r}`);
}
percent(sh['Time patterns'],`I7:I${te}`); sh['Time patterns'].getRange(`J7:J${te}`).setNumberFormat('0.0');
cell(sh['Time patterns'],'L6','Day type');cell(sh['Time patterns'],'M6','Weekday');
sh['Time patterns'].getRange('M6').dataValidation={rule:{type:'list',values:['Weekday','Weekend']}};
sh['Time patterns'].getRange('M6').format.fill=amber;
sh['Time patterns'].getRange('L8:M8').values=[['Local hour','Availability']];
for(let i=0;i<24;i++) {
  const r=i+9; cell(sh['Time patterns'],`L${r}`,`${String(i).padStart(2,'0')}:00`);
  formula(sh['Time patterns'],`M${r}`,`=IF(OR(SUMIFS(D$7:D$${te},B$7:B$${te},${i},C$7:C$${te},$M$6)<100,SUMIFS(G$7:G$${te},B$7:B$${te},${i},C$7:C$${te},$M$6)<3),"n.a.",SUMIFS(E$7:E$${te},B$7:B$${te},${i},C$7:C$${te},$M$6)/SUMIFS(D$7:D$${te},B$7:B$${te},${i},C$7:C$${te},$M$6))`);
}
percent(sh['Time patterns'],'M9:M32');
sh['Time patterns'].getRange('M9:M32').format.horizontalAlignment='right';
sh['Time patterns'].getRange('L6:M32').format.columnWidth=18;
chart(sh['Time patterns'],'bar','L8:L32','M8:M32','Availability in observed reports',['O6','X23']);
cell(sh['Time patterns'],'L35','Chart omits cells with fewer than 100 reports or 3 observed dates.');

title(sh['Nearby alternatives'],'Nearby stations during full reports','Same-feed comparison within 750 m. This is not arrival-time or sequential-backup success.');
const ne=table(sh['Nearby alternatives'],['Station ID','Full reports','Matched nearby','Nearby with dock','Matched share','Nearby availability','Mean distance (m)'],data.nearby.map(r=>[r.station_id,r.full_reports,r.matched_reports,r.nearby_available_reports,null,null,r.mean_distance_m]),'NearbyComparison',[15,17,19,20,18,23,22]);
sh['Nearby alternatives'].getRange(`B7:B${ne}`).setNumberFormat('@');
for(let r=7;r<=ne;r++) {
 formula(sh['Nearby alternatives'],`F${r}`,`=D${r}/C${r}`);
 formula(sh['Nearby alternatives'],`G${r}`,`=IF(D${r}=0,"n.a.",E${r}/D${r})`);
}
percent(sh['Nearby alternatives'],`F7:G${ne}`);
sh['Nearby alternatives'].getRange(`H7:H${ne}`).setNumberFormat('0');
cell(sh['Nearby alternatives'],'B21','Selection: 10 highest full-rate stations meeting the declared support threshold.');
cell(sh['Nearby alternatives'],'B23','Nearest fresh operational neighbor is selected by distance, not by dock count.');
cell(sh['Nearby alternatives'],'B25','Unmatched reports remain visible in the denominator. No independence assumption is used.');

title(sh.Overview,'Dockside analytical case study','September 16 - October 17, 2026. Exploratory analysis of incomplete collected history.');
sh.Overview.getRange('B6:B31').format.columnWidth=37;
sh.Overview.getRange('C6:C31').format.columnWidth=22;
sh.Overview.getRange('D6:M39').format.columnWidth=13;
const metrics=[['Fresh unique operational reports',`=SUM('Stations'!D7:D${se})`],['Observed dock availability',`=SUM('Stations'!E7:E${se})/C6`],['Successful poll coverage',`=SUM('Daily coverage'!E7:E${de})/SUM('Daily coverage'!C7:C${de})`],['Observed dates',`=${qref('observed_days')}`],['Stations represented',`=${qref('eligible_stations')}`]];
metrics.forEach((m,i)=>{cell(sh.Overview,`B${i+6}`,m[0]);formula(sh.Overview,`C${i+6}`,m[1]);});
sh.Overview.getRange('C6:C10').setNumberFormat('#,##0');percent(sh.Overview,'C7:C8');
cell(sh.Overview,'B12','Availability is conditional on observed fresh operational reports, not elapsed time or rider success.');
cell(sh.Overview,'B14','Explore a station');cell(sh.Overview,'B15','Station ID (editable)');cell(sh.Overview,'C15',data.stations.find(r=>r.ranking_eligible)?.station_id??data.stations[0].station_id);
sh.Overview.getRange('C15').setNumberFormat('@');sh.Overview.getRange('C15').format.fill=amber;
wb.names.add('StationIDs',sh.Stations.getRange(`B7:B${se}`));
sh.Overview.getRange('C15').dataValidation={rule:{type:'list',formula1:'StationIDs'}};
for(const [offset,label,col] of [[16,'Name','C'],[17,'Reports','D'],[18,'Availability','J'],[19,'Full rate','K'],[20,'Observed dates','G'],[21,'Mean docks','L']]) {
  cell(sh.Overview,`B${offset}`,label);
  formula(sh.Overview,`C${offset}`,`=IF(COUNTIFS('Stations'!$B$7:$B$${se},$C$15)=0,"Unknown ID",INDEX('Stations'!$${col}$7:$${col}$${se},MATCH($C$15,'Stations'!$B$7:$B$${se},0)))`);
}
percent(sh.Overview,'C18:C19');sh.Overview.getRange('C21').setNumberFormat('0.0');
cell(sh.Overview,'B24','Interpretation');
cell(sh.Overview,'B26','Missing collection dominates the limitations. Do not rank stations as year-round reliable.');
cell(sh.Overview,'B28','Use current fresh station reports for an actual trip. This workbook is a frozen analysis.');
cell(sh.Overview,'B30','Controls: change the amber station ID; filter station tables; choose weekday/weekend on Time patterns.');
// Formula-backed compact daily coverage chart; helper labels avoid Excel serial dates.
const he=36+data.daily.length;
sh.Overview.getRange('B35:C35').values=[['Toronto date','Successful polls / expected']];
data.daily.forEach((r,i)=>{const row=36+i; cell(sh.Overview,`B${row}`,r.local_date.slice(5));formula(sh.Overview,`C${row}`,`='Daily coverage'!L${7+i}`);});
percent(sh.Overview,`C36:C${he-1}`);
chart(sh.Overview,'bar',`B35:B${he-1}`,`C35:C${he-1}`,'Collection coverage by date',['F6','O22']);

title(sh['Read Me'],'Methods, provenance and refresh','Ian Lin | Dockside portfolio analysis | Version 1.0.0');
sh['Read Me'].getRange('B6:B28').format.columnWidth=28;
sh['Read Me'].getRange('C6:C28').format.columnWidth=115;
const notes=[
 ['Source','Self-collected Bike Share Toronto GBFS v3 station status; live provenance only.'],
 ['Source URL','https://toronto.publicbikesystem.net/customer/gbfs/v3.0/gbfs.json'],
 ['Period (UTC)',`${cfg.start_utc} to ${cfg.end_utc_exclusive} (exclusive)`],
 ['Local calendar','America/Toronto; UTC remains the ordering key. First/last local dates are partial.'],
 ['Observation unit','First canonical retrieval per station and source report timestamp within the study window.'],
 ['Freshness','Report age at retrieval between -30 and 300 seconds. Sensitivity: 60, 120, 300 seconds.'],
 ['Eligibility','Installed, accepting returns, known dock count. Reported usable docks are authoritative.'],
 ['Main rate','Reports with at least one dock / eligible reports. No filling or time-weighting across gaps.'],
 ['Poll coverage','Minutes with a successful batch / all expected 60-second slots, including unattempted slots.'],
 ['Metadata','Joined through the metadata version stored with the snapshot, not today’s station metadata.'],
 ['Station name','Last eligible observed name within the window; station IDs remain strings.'],
 ['Ranking support','At least 100 eligible unique reports on at least 5 dates. This is not a validation gate.'],
 ['Nearby comparison','Nearest fresh operational station in the same feed within 750 m, while the primary is full.'],
 ['Limitations','Sparse nonrandom collection; report updates are correlated and may favor changing inventory.'],
 ['No causal claims','Inventory does not identify trips, demand or rebalancing. No validated forecast or rider trial.'],
 ['Workbook refresh','Frozen snapshot. Rerun export.py and this builder to refresh; no embedded database connection.'],
 ['Excel tools','Native tables, filters, formulas, dropdowns and charts. No PivotTable or slicer is claimed.'],
 ['Reproduction','GitHub: ianlin1222/toronto-bike-share-dashboard, analysis/portfolio/README.md'],
 ['Data license','Contains information licensed under the Open Government Licence – Toronto.'],
 ['License URL','https://www.toronto.ca/city-government/data-research-maps/open-data/open-data-licence/']
];
sh['Read Me'].getRange(`B6:C${5+notes.length}`).values=notes;
sh['Read Me'].getRange(`B6:C${5+notes.length}`).format.wrapText=true;
sh['Read Me'].getRange(`B6:C${5+notes.length}`).format.rowHeight=35;

// Independent tie-outs are terminal; the analytical results never depend on them.
const checks=sh['Source QA'];const cr=sr+7;
cell(checks,`B${cr}`,'Reconciliation residuals (must equal zero)');
for(const [i,label,f] of [[1,'Station reports vs SQL quality',`=SUM('Stations'!D7:D${se})-${qref('eligible_reports')}`],
 [2,'Daily available vs SQL quality',`=SUM('Daily coverage'!I7:I${de})-${qref('available_reports')}`],
 [3,'Hourly reports vs SQL quality',`=SUM('Time patterns'!D7:D${te})-${qref('eligible_reports')}`]]) {
 cell(checks,`B${cr+i}`,label);formula(checks,`C${cr+i}`,f);
}
checks.getRange(`C${cr+1}:C${cr+3}`).conditionalFormats.add('cellIs',{operator:'notEqual',formula:0,format:{fill:'#FDE2DC',font:{color:'#9B2920',bold:true}}});
const cs=cr+7;
cell(checks,`B${cs-2}`,'Conflicting timestamp sensitivity');
table(checks,['Rule','Reports','Available','Availability'],data.conflict_sensitivity.map(r=>[r.rule,r.reports,r.available_reports,null]),'ConflictSensitivity',[43,19,20,18],cs);
formula(checks,`E${cs+1}`,`=D${cs+1}/C${cs+1}`);percent(checks,`E${cs+1}`);
cell(checks,`B${cs+4}`,'Quarantine reasons (record/code counts; do not add overlapping codes)');
table(checks,['Reason','Records'],data.quarantine_reasons.map(r=>[r.code,r.record_code_occurrences]),'QuarantineReasons',[43,19],cs+6);
wb.recalculate();
// Test a real control change, plus the unmatched-key boundary, then restore it.
const original=sh.Overview.getRange('C15').values[0][0];
const other=data.stations.find(r=>r.station_id!==original);
cell(sh.Overview,'C15',other.station_id);wb.recalculate();
if(sh.Overview.getRange('C17').values[0][0]!==other.reports) throw Error('Station control failed');
cell(sh.Overview,'C15','not-a-station');wb.recalculate();
if(sh.Overview.getRange('C17').values[0][0]!=='Unknown ID') throw Error('Missing key failed');
cell(sh.Overview,'C15',original);
for(const dayType of ['Weekend','Weekday']) {
 cell(sh['Time patterns'],'M6',dayType);wb.recalculate();
 for(let hour=0;hour<24;hour++) {
  const expected=data.time_patterns.find(r=>r.day_type===dayType&&r.local_hour===hour);
  const actual=sh['Time patterns'].getRange(`M${9+hour}`).values[0][0];
  if(expected&&expected.reports>=100&&expected.observed_days>=3) {
   if(typeof actual!=='number'||Math.abs(actual-expected.available_reports/expected.reports)>1e-10) throw Error(`Day filter failed: ${dayType} ${hour}`);
  } else if(actual!=='n.a.') throw Error(`Unsupported hour was not omitted: ${dayType} ${hour}`);
 }
}
for(let r=cr+1;r<=cr+3;r++) if(checks.getRange(`C${r}`).values[0][0]!==0) throw Error('Reconciliation failed');
if(Math.abs(sh.Overview.getRange('C7').values[0][0]-q.available_reports/q.eligible_reports)>1e-10) throw Error('Headline mismatch');
const errorScan=await wb.inspect({select:"$.sheets[*].cells[?(@.formula && @.valueType == 'error')]",include:['sheet','address','formula','error']});
if(errorScan.records.length) throw Error('Formula errors detected: '+errorScan.ndjson);
console.log(errorScan.ndjson);
await fs.writeFile(path.join(preview,'workbook-checks.json'),JSON.stringify({headline:sh.Overview.getRange('C6:C10').values,controls:'station ID, unknown ID, weekday/weekend tested',errors:errorScan.ndjson},null,2));
for(const name of names) {
 const range=name==='Overview'?'A1:P32':name==='Read Me'?'A1:D27':name==='Time patterns'?'A1:X36':name==='Stations'?'A1:N18':name==='Source QA'?`A1:F${cs+8}`:name==='Daily coverage'?'A1:N20':'A1:I27';
 const png=await wb.render({sheetName:name,range,scale:1.5,format:'png'});
 await fs.writeFile(path.join(preview,name.replaceAll(' ','-')+'.png'),new Uint8Array(await png.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(out,'Dockside_Analysis.xlsx'));
console.log('Workbook saved and recalculation checks passed.');
