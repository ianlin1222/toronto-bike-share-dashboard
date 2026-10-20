'use strict';
const $ = id => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const fmt = new Intl.NumberFormat('en-CA', {maximumFractionDigits:1});
const percent = value => value == null ? '—' : `${fmt.format(value*100)}%`;
const number = value => value == null ? '—' : fmt.format(value);
const localTime = value => value ? new Date(value).toLocaleString('en-CA',{timeZone:'America/Toronto',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',timeZoneName:'short'}) : 'Not available';
const days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
let data = null, stationOptions = new Map(), requestSequence = 0, controller = null;
let page = 0, sortKey = 'availability_rate', ascending = true, inspectedRows = [], inspectedName = 'data';
function el(tag,text,className){const node=document.createElement(tag);if(text!=null)node.textContent=text;if(className)node.className=className;return node;}
function svg(tag,attrs={},text){const node=document.createElementNS(NS,tag);for(const [key,value] of Object.entries(attrs))node.setAttribute(key,String(value));if(text!=null)node.textContent=text;return node;}
function empty(container,message='No observations match these filters. Try another date range or clear a filter.',heading='No observed data'){container.replaceChildren();const box=el('div',null,'empty-chart');box.append(el('strong',heading),el('span',message));container.append(box);}
function actionable(node,label,activate,preview){node.setAttribute('tabindex','0');node.setAttribute('role','button');node.setAttribute('aria-label',label);node.append(svg('title',{},label));node.addEventListener('click',activate);node.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();activate();}});if(preview){node.addEventListener('mouseenter',preview);node.addEventListener('focus',preview);}}
function canvas(id,width=650,height=235){const host=$(id);host.replaceChildren();const chart=svg('svg',{viewBox:`0 0 ${width} ${height}`,role:'group','aria-label':host.getAttribute('aria-label')||id});host.append(chart);return chart;}
function axes(chart,width,height,max,label){const l=42,r=15,t=22,b=32,w=width-l-r,h=height-t-b;for(let i=0;i<=4;i++){const y=t+h-i*h/4;chart.append(svg('line',{x1:l,y1:y,x2:width-r,y2:y,class:'axis'}),svg('text',{x:l-9,y:y+3,'text-anchor':'end'},number(max*i/4)));}chart.append(svg('text',{x:l,y:10},label));return {l,t,w,h,y:v=>t+h-v/max*h};}
function colour(rate){if(rate==null)return '#cbd3c6';const low=[221,174,83],high=[34,116,103];return `rgb(${low.map((n,i)=>Math.round(n+(high[i]-n)*rate)).join(',')})`;}
function trend(){
  const values=data.timeline.filter(r=>r.average_docks!=null);
  if(!values.length)return empty($('trend'));
  const chart=canvas('trend',680),max=Math.max(1,...values.map(v=>v.average_docks))*1.18;
  const a=axes(chart,680,235,max,'Avg. docks');
  const min=Date.parse(data.filters.start_utc),last=Date.parse(data.filters.end_utc);
  const x=time=>a.l+a.w*(last===min?.5:(time-min)/(last-min));
  let path='',previous=null;
  for(const v of values){
    const at=Date.parse(v.hour_start),gap=previous==null||at-previous>5400000;
    path+=`${gap?'M':'L'}${x(at)},${a.y(v.average_docks)} `;previous=at;
  }
  chart.append(svg('path',{d:path,fill:'none',stroke:'#267b6c','stroke-width':2}));
  for(const v of values){
    const description=`${localTime(v.hour_start)} · ${number(v.average_docks)} avg. docks · ${percent(v.availability_rate)} with a dock · ${number(v.dock_observations)} known observations`;
    const point=svg('circle',{cx:x(Date.parse(v.hour_start)),cy:a.y(v.average_docks),r:values.length>150?2.8:4,fill:'#267b6c',stroke:'white','stroke-width':1});
    actionable(point,description,()=>inspectRows('One observed hour',[v]),()=>$('trend-foot').textContent=description);chart.append(point);
  }
  // Evenly spaced time ticks keep long collection outages visible and labels apart.
  [min,(min+last)/2,last].forEach((at,i)=>chart.append(svg('text',
    {x:x(at),y:227,'text-anchor':i===0?'start':i===2?'end':'middle'},
    new Date(at).toLocaleString('en-CA',{timeZone:'America/Toronto',month:'short',day:'numeric',hour:'2-digit'}))));
  $('trend-foot').textContent=`${values.length} observed hours · hover or focus a point; click to inspect. Gaps are not interpolated.`;
}
function hourly(){if(!data.hourly.some(r=>r.average_docks!=null))return empty($('hourly'));const chart=canvas('hourly',420);const max=Math.max(1,...data.hourly.map(v=>v.average_docks||0))*1.12;const a=axes(chart,420,235,max,'Avg. docks');const byHour=new Map(data.hourly.map(r=>[r.local_hour,r]));for(let hour=0;hour<24;hour++){const row=byHour.get(hour),x=a.l+hour*a.w/24;if(row?.average_docks!=null){const bar=svg('rect',{x:x+2,y:a.y(row.average_docks),width:a.w/24-4,height:Math.max(2,a.t+a.h-a.y(row.average_docks)),rx:2,fill:hour>=7&&hour<=9||hour>=16&&hour<=18?'#dbb36d':'#4f9284'});actionable(bar,`${hour}:00 · ${number(row.average_docks)} average docks. Filter this hour.`,()=>{$('hour').value=String(hour);load(true);});chart.append(bar);}if(hour%4===0)chart.append(svg('text',{x:x+6,y:226,'text-anchor':'middle'},String(hour).padStart(2,'0')));}chart.append(svg('text',{x:405,y:226,'text-anchor':'end'},'23'));}
function map(){
  const values=data.stations.filter(r=>r.map_eligible),excluded=data.stations.length-values.length;
  $('station-detail').textContent=`${values.length.toLocaleString()} mapped stations${excluded?` · ${excluded} omitted: missing or out-of-Toronto coordinates (still in totals/table)`:''}. Select a marker to see its name, numbers and filter button.`;
  DocksideMaps.render($('station-map'), values.map(v=>({
    lat:v.lat,lon:v.lon,color:colour(v.availability_rate),radius:Math.min(10,3+Math.sqrt(v.average_docks||0)),
    label:`${v.name} · ${percent(v.availability_rate)} with a dock · ${number(v.average_docks)} avg. docks · ${number(v.dock_observations)} observations`,
    action:()=>chooseStation(v.station_id)
  })),label=>{$('station-detail').textContent=label;});
}
function rankingRows(){return DocksideDashboardLogic.rankingRows(data.stations,Number($('ranking-minimum').value));}
function rankings(){
  const host=$('rankings');host.replaceChildren();const values=rankingRows();
  if(!values.length)return empty(host,'No stations meet the ranking sample threshold. Choose a longer period or a smaller minimum. All stations remain in the table.');
  for(const [i,v] of values.entries()){
    const row=el('button',null,'rank-row'),name=el('div'),bar=el('div',null,'rank-bar'),fill=el('div',null,'rank-fill');
    const fullShare=(v.dock_observations-v.available_observations)/v.dock_observations;
    row.type='button';fill.style.width=`${fullShare*100}%`;bar.append(fill);
    name.append(el('div',v.name,'rank-name'),bar,el('small',`${number(v.dock_observations-v.available_observations)} full / ${number(v.dock_observations)} usable reports`,'rank-support'));
    row.append(el('span',String(i+1).padStart(2,'0'),'rank-number'),name,el('strong',percent(fullShare),'rank-value'));
    row.onclick=()=>chooseStation(v.station_id);host.append(row);
  }
}
function updateSnapshotAge(){
  if(data && data.mode!=='fixture_demo' && DocksideDashboardLogic.snapshotAged(data.generated_at)){
    $('live-title').textContent='Current snapshot needs refreshing';$('live-dot').className='status-dot offline';
    $('live-detail').textContent='This page has not checked current reports in over two minutes. Refresh data before using current counts. Historical charts are unchanged.';
  }
}
function heatmap(){const host=$('heatmap');host.replaceChildren();const grid=el('div',null,'heat-grid'),values=new Map(data.heatmap.map(r=>[r.heat_key,r]));grid.append(el('span'));for(let h=0;h<24;h++)grid.append(el('span',String(h).padStart(2,'0'),'hour-label'));for(let day=0;day<7;day++){grid.append(el('span',days[day],'day-label'));for(let hour=0;hour<24;hour++){const value=values.get(day*24+hour),cell=el('button',null,'heat-cell'+(value?.availability_rate==null?' empty':''));cell.type='button';const label=`${days[day]} ${hour}:00 · ${value?percent(value.availability_rate)+' with a dock':'no usable observations'}`;cell.title=label;cell.setAttribute('aria-label',label);if(value?.availability_rate!=null){cell.style.background=colour(value.availability_rate);cell.onclick=()=>inspectRows(label,[{weekday:days[day],local_hour:hour,...value}]);}else cell.disabled=true;grid.append(cell);}}host.append(grid);}
function health(){const values=data.health;if(!values.length)return empty($('health-chart'));const chart=canvas('health-chart',650);const a=axes(chart,650,235,100,'Successful polls (%)');const width=a.w/values.length;values.forEach((v,i)=>{const x=a.l+i*width+3,w=Math.max(2,width-6);chart.append(svg('rect',{x,y:a.t,width:w,height:a.h,rx:2,fill:'#edf1e8'}));const bar=svg('rect',{x,y:a.y((v.coverage||0)*100),width:w,height:Math.max(2,a.h*(v.coverage||0)),rx:2,fill:v.coverage>=.9?'#4f9284':'#d8ad64'});actionable(bar,`${v.date}: ${percent(v.coverage)} · ${v.success} / ${v.expected} expected polls`,()=>inspectRows('Collection on '+v.date,[v]));chart.append(bar);if(values.length<=10||i%Math.ceil(values.length/8)===0)chart.append(svg('text',{x:x+w/2,y:227,'text-anchor':'middle'},v.date.slice(5)));});}
function filteredTable(){const query=$('table-search').value.toLocaleLowerCase();return data.stations.filter(s=>`${s.name} ${s.station_id}`.toLocaleLowerCase().includes(query)).sort((a,b)=>{const av=a[sortKey],bv=b[sortKey];if(av==null)return bv==null?0:1;if(bv==null)return -1;return (typeof av==='string'?av.localeCompare(bv):av-bv)*(ascending?1:-1);});}
function table(){if(!data)return;const rows=filteredTable();page=Math.max(0,Math.min(page,Math.ceil(rows.length/15)-1));$('station-rows').replaceChildren();for(const r of rows.slice(page*15,page*15+15)){const tr=el('tr'),name=el('td',r.name);name.append(el('small',`Station ${r.station_id}`));tr.append(name,el('td',number(r.average_docks)),el('td',percent(r.availability_rate)),el('td',number(r.observations)),el('td',percent(r.freshness_rate)));const cell=el('td'),button=el('button','Focus ↗');button.onclick=()=>chooseStation(r.station_id);cell.append(button);tr.append(cell);$('station-rows').append(tr);}if(!rows.length){const td=el('td','No stations match. Clear the search or change the dashboard filters.');td.colSpan=6;const tr=el('tr');tr.append(td);$('station-rows').append(tr);}$('table-count').textContent=`${rows.length.toLocaleString()} stations · select a column heading to sort`;$('page-label').textContent=`${rows.length?'Page '+(page+1)+' of '+Math.ceil(rows.length/15):'No rows'}`;$('previous').disabled=page===0;$('next').disabled=(page+1)*15>=rows.length;}
function chooseStation(id){const entry=[...stationOptions].find(([,value])=>value===id);$('station').value=entry?.[0]||id;load(true);}
function inspectRows(title,rows,note=''){
  inspectedRows=rows;inspectedName=title;$('inspect-title').textContent=title;
  $('inspect-description').textContent=`${data.source_kind==='synthetic'?'SYNTHETIC DEMONSTRATION — ':'Observed data — '}${data.filters.start_date} through ${data.filters.end_date}. Toronto local dates. Rates are raw fractions (0–1); for example 0.941 = 94.1%. Null = unknown, not zero. ${note}`;
  $('inspect-content').replaceChildren();
  if(rows.length){
    const table=el('table',null,'inspector-table'),head=el('thead'),tr=el('tr'),keys=Object.keys(rows[0]);
    keys.forEach(k=>tr.append(el('th',k.replaceAll('_',' '))));head.append(tr);table.append(head);
    const body=el('tbody');
    for(const row of rows){const tr=el('tr');keys.forEach(key=>tr.append(el('td',row[key]==null?'—':DocksideDashboardLogic.inspectValue(row[key]))));body.append(tr);}
    table.append(body);$('inspect-content').append(table);
  }else $('inspect-content').append(el('p','No observations in this selection.'));
  $('inspect-export').hidden=!rows.length;$('inspector').showModal();
}
function inspectMetric(key){const text={average:data.methodology.average,availability:data.methodology.availability,stations:'Distinct station IDs with at least one canonical observation in the selected period. This does not imply every station was fresh or accepting returns.',coverage:data.methodology.coverage};const sql={average:'SELECT SUM(docks_sum)::float / NULLIF(SUM(dock_observations), 0)\nFROM dashboard_station_hours WHERE source_kind = :source_kind\n  AND hour_start >= :start_utc AND hour_start < :end_utc;\n-- Plus the displayed station/day/hour filters.',availability:'SELECT SUM(available_observations)::float / NULLIF(SUM(dock_observations), 0)\nFROM dashboard_station_hours WHERE source_kind = :source_kind\n  AND hour_start >= :start_utc AND hour_start < :end_utc;\n-- Plus the displayed station/day/hour filters.',stations:'COUNT(DISTINCT station_id) over the filtered hourly observation rows.',coverage:'successful distinct scheduled minute slots / expected scheduled slots\nMissing slots are included in the denominator.\nThe incomplete current minute is excluded; station selection does not apply.'};$('inspect-title').textContent=key==='average'?'Average reported docks':key==='availability'?'Observed dock availability':key==='stations'?'Stations observed':'Collection coverage';$('inspect-description').textContent=text[key];$('inspect-content').replaceChildren(el('pre',sql[key]),el('p',`Read-only calculation, not a query editor. Data source: ${data.source_kind}.`),el('pre',JSON.stringify({filters:data.filters,counts:key==='coverage'?data.coverage:data.summary},null,2)));$('inspect-export').hidden=true;$('inspector').showModal();}
function csv(rows,name){
  if(!rows.length)return;
  const metadata={source_kind:data.source_kind,dashboard_version:data.version,timezone:data.timezone,start_date:data.filters.start_date,end_date:data.filters.end_date,station_filter:data.filters.station_id??'all',day_filter:data.filters.day_type,hour_filter:data.filters.hour??'all',generated_at:data.generated_at};
  const normalized=rows.map(row=>({...metadata,...row})),keys=Object.keys(normalized[0]);
  const quote=v=>{let s=v==null?'':String(v);if(typeof v==='string'&&/^[=+@\-\t\r]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';};
  const output=[keys.map(quote).join(','),...normalized.map(row=>keys.map(k=>quote(row[k])).join(','))].join('\r\n');
  const url=URL.createObjectURL(new Blob(['\ufeff',output],{type:'text/csv;charset=utf-8'}));
  const a=el('a');a.href=url;a.download=`dockside-${name.toLowerCase().replace(/[^a-z0-9]+/g,'-')}-${data.filters.start_date}.csv`;
  document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function render(){const f=data.filters;$('station-focus').hidden=!f.station_id;$('station-focus-label').textContent=f.station_id?`Viewing station ${f.station_id}`:'';$('start').value=f.start_date;$('end').value=f.end_date;$('day').value=f.day_type;$('hour').value=f.hour??'';$('kpi-docks').textContent=number(data.summary.average_docks);$('kpi-available').textContent=percent(data.summary.availability_rate);$('kpi-stations').textContent=number(data.summary.station_count);$('kpi-observations').textContent=`${number(data.summary.observations)} recorded observations`;$('kpi-coverage').textContent=percent(data.coverage.poll_coverage);$('kpi-polls').textContent=`${number(data.coverage.successful_polls)} / ${number(data.coverage.expected_polls)} expected polls`;
  const fixture=data.mode==='fixture_demo',sparse=data.coverage.poll_coverage==null||data.coverage.poll_coverage<.9;$('notice').className='banner '+(fixture?'sample':sparse?'warning':'');$('notice').textContent=fixture?'SAMPLE MODE · Every historical chart below is synthetic demonstration data. Not observed performance.':!data.timeline.length?'No real history matches these filters. Change the dates or allow the collector to gather observations.':sparse?`Partial history · ${percent(data.coverage.poll_coverage)} collection coverage in this selection. Gaps are missing data, not zero activity.`:'Observed history · fresh, return-capable station reports only for availability metrics. Not a forecast.';
  $('filter-context').textContent=`${f.start_date} → ${f.end_date} · ${f.day_type==='all'?'All days':f.day_type} · ${f.hour==null?'All hours':String(f.hour).padStart(2,'0')+':00–'+String((f.hour+1)%24).padStart(2,'0')+':00'} · ${f.station_id?'Station '+f.station_id:'All stations'} · America/Toronto`;$('live-title').textContent=fixture?'Sample current conditions':data.current.stale?'Live feed paused':'Live reports at last refresh';$('live-dot').className='status-dot'+(data.current.stale||fixture?' offline':'');$('live-detail').textContent=data.current.stale?'Historical analysis remains available. Do not use old reports for a return.':`${number(data.current.stations_with_dock)} fresh stations with a dock · ${number(data.current.docks)} reported docks · date/hour filters do not apply`;$('updated').textContent='Loaded '+localTime(data.generated_at)+' · refresh manually';
  $('source-label').textContent=fixture?'Synthetic demonstration':'Self-collected GBFS snapshots';$('history-label').textContent=data.coverage.first_hour?`${localTime(data.coverage.first_hour)} → ${localTime(data.coverage.last_hour)}`:'Not yet collected';$('aggregate-label').textContent=localTime(data.coverage.last_aggregated_at);$('definitions').replaceChildren();for(const [key,value]of Object.entries(data.methodology)){const p=el('p');p.append(el('strong',key[0].toUpperCase()+key.slice(1)+'. '),document.createTextNode(value));$('definitions').append(p);}trend();hourly();map();rankings();heatmap();health();DocksideAnalysis.render(data);page=0;table();$('export').disabled=!data.stations.length;
}
async function load(withFilters=false){const params=new URLSearchParams();$('error').hidden=true;if(withFilters){const value=$('station').value.trim();const id=DocksideDashboardLogic.resolveStation(value,stationOptions,data?.stations||[]);if(value&&!id){$('error').textContent='Choose a suggested station, enter an exact station ID, or clear Station for the whole network.';$('error').hidden=false;return;}if(id)params.set('station_id',id);for(const [name,id]of [['start_date','start'],['end_date','end'],['day_type','day'],['hour','hour']])if($(id).value)params.set(name,$(id).value);}const seq=++requestSequence;controller?.abort();controller=new AbortController();const active=controller;
  $('dashboard-content').setAttribute('aria-busy','true');$('apply').disabled=true;$('refresh').disabled=true;$('export').disabled=true;const timer=setTimeout(()=>active.abort(),20000);try{const response=await fetch('/v1/dashboard?'+params,{signal:active.signal,cache:'no-store'});const body=await response.json();if(!response.ok)throw new Error(body.detail?.message||'The dashboard could not load. Check the local services and retry.');if(seq!==requestSequence)return;data=body;render();}catch(error){if(seq!==requestSequence)return;$('error').textContent=error.name==='AbortError'?'The request timed out. Try a shorter date range, then Refresh data.':error.message;$('error').hidden=false;$('notice').className='banner warning';$('notice').textContent=data?'Refresh failed. Charts below are the previous result, not the requested filters.':'No dashboard data loaded. Run make start, then retry. No sample data has been substituted.';}finally{clearTimeout(timer);if(seq===requestSequence){$('dashboard-content').setAttribute('aria-busy','false');$('apply').disabled=false;$('refresh').disabled=false;}}}
async function catalog(){try{const response=await fetch('/v1/stations',{signal:AbortSignal.timeout(10000)});if(!response.ok)return;const body=await response.json();stationOptions=new Map(body.stations.map(s=>[`${s.name} · #${s.station_id}`,s.station_id]));$('station-options').replaceChildren();for(const label of stationOptions.keys()){const option=el('option');option.value=label;$('station-options').append(option);}}catch{/* The dashboard remains usable for all stations. */}}
for(let h=0;h<24;h++){const option=el('option',`${String(h).padStart(2,'0')}:00–${String((h+1)%24).padStart(2,'0')}:00`);option.value=h;$('hour').append(option);}
$('filters').onsubmit=event=>{event.preventDefault();load(true);};$('refresh').onclick=()=>{catalog();load(Boolean(data));};$('reset').onclick=()=>{$('station').value='';$('table-search').value='';$('day').value='all';$('hour').value='';load();};$('filters').addEventListener('input',()=>{$('filter-context').textContent='Filters changed. Select Apply filters to update the charts.';});$('table-search').oninput=()=>{page=0;table();};$('previous').onclick=()=>{page--;table();};$('next').onclick=()=>{page++;table();};document.querySelectorAll('[data-sort]').forEach(button=>button.onclick=()=>{const key=button.dataset.sort;ascending=sortKey===key?!ascending:key==='name';sortKey=key;page=0;table();});document.querySelectorAll('[data-metric]').forEach(button=>button.onclick=()=>{if(data)inspectMetric(button.dataset.metric);});document.querySelectorAll('[data-table]').forEach(button=>button.onclick=()=>{if(!data)return;const key=button.dataset.table;const rows=key==='rankings'?rankingRows():data[key];inspectRows(button.closest('.panel')?.querySelector('h2')?.textContent||'Collection data',rows);});$('close-inspector').onclick=()=>$('inspector').close();$('inspect-export').onclick=()=>csv(inspectedRows,inspectedName);$('export').onclick=()=>csv(filteredTable(),'station-data');document.querySelectorAll('.sidebar nav a[href^="#"]').forEach(link=>link.onclick=()=>{document.querySelectorAll('.nav-item').forEach(a=>a.classList.remove('selected'));link.classList.add('selected');});
$('ranking-minimum').onchange=()=>{if(data)rankings();};
$('analysis-minimum').onchange=()=>{if(data)DocksideAnalysis.render(data);};
document.querySelectorAll('[data-analysis]').forEach(button=>button.onclick=()=>{
  if(data)DocksideAnalysis.inspect(button.dataset.analysis,button.closest('.panel').querySelector('h2').textContent);
});
$('clear-station').onclick=()=>{$('station').value='';load(true);};
setInterval(updateSnapshotAge,10000);
catalog();load();
