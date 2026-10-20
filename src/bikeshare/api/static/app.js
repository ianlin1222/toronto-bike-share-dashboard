'use strict';
const $ = (id) => document.getElementById(id);
const places = new Map([
  ['Toronto City Hall', {lat:43.6532,lon:-79.3832}],
  ['Union Station', {lat:43.6453,lon:-79.3806}],
  ['University of Toronto', {lat:43.6629,lon:-79.3957}],
  ['St. Lawrence Market', {lat:43.6487,lon:-79.3715}],
  ['Trinity Bellwoods Park', {lat:43.6479,lon:-79.4138}],
  ['Toronto Metropolitan University', {lat:43.6577,lon:-79.3788}]
]);
let latest = null, busy = false, dirty = false, revision = 0;
function el(tag, text, className) {const node=document.createElement(tag);if(text!=null)node.textContent=text;if(className)node.className=className;return node;}
function options(){const list=$('destinations');list.replaceChildren();for(const name of places.keys()){const option=document.createElement('option');option.value=name;list.append(option);}}
options();
async function jsonFetch(path, init={}){
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),12000);
  try{const response=await fetch(path,{...init,signal:controller.signal,cache:'no-store'});const body=await response.json();if(!response.ok){const error=new Error(body.detail?.message || (response.status===422?'Check your destination, arrival time, and search radius.':'Station information is temporarily unavailable.'));error.code=body.detail?.code;error.requestId=response.headers.get('X-Request-ID');throw error;}return body;}
  finally{clearTimeout(timer);}
}
async function checkHealth(){
  try{const response=await fetch('/readyz',{signal:AbortSignal.timeout(7000),cache:'no-store'});const data=await response.json();const sample=data.mode==='fixture_demo';$('status-dot').className='status-dot '+(data.ready&&!sample?'live':!data.ready?'offline':'');$('status-title').textContent=!data.ready?'Station updates paused':sample?'Sample-data demonstration':'Live station updates';$('status-detail').textContent=!data.ready?'The collector is starting or recovering. Wait a minute and refresh.':sample?'These stations show fictional dock availability. Use live mode before planning a real ride.':'Recommendations use fresh reports from Bike Share Toronto. Arrival forecasts are not available yet.';$('feed-age').textContent=data.latest_complete_poll?'Updated '+ageText(data.latest_complete_poll)+' ago':sample?'Sample data':'';
  }catch{$('status-dot').className='status-dot offline';$('status-title').textContent='Cannot reach the service';$('status-detail').textContent='Keep the local application running, then try again.';}
}
async function loadStations(){try{const data=await jsonFetch('/v1/stations');for(const station of data.stations){places.set(`${station.name} · #${station.station_id}`,station);}options();$('station-count').textContent=`${data.stations.length.toLocaleString()} ${data.mode==='fixture_demo'?'sample':'station'} locations`;}catch{$('station-count').textContent='Landmark search available';}}
function ageText(time){const seconds=Math.max(0,Math.floor((Date.now()-new Date(time).getTime())/1000));return seconds<60?`${seconds}s`:`${Math.floor(seconds/60)}m ${seconds%60}s`;}
function selectedDestination(){
  if($('coordinates').open){const lat=Number($('lat').value),lon=Number($('lon').value);if(!$('lat').value||!$('lon').value||!Number.isFinite(lat)||!Number.isFinite(lon)||lat<43.45||lat>43.95||lon< -79.8||lon> -79)throw new Error('Enter valid Toronto latitude (43.45–43.95) and longitude (−79.80–−79.00).');return {lat,lon};}
  const value=$('destination').value.trim();const match=[...places].find(([name])=>name.toLocaleLowerCase()===value.toLocaleLowerCase());if(!match)throw new Error('Choose a suggested landmark or station, or open “Use exact coordinates.”');return {lat:match[1].lat,lon:match[1].lon};
}
function card(title,station){
  const node=el('article',null,'card '+(title==='Alternative'?'alternative':''));const label=el('div',null,'card-label');label.append(el('span',title[0],'card-marker'),document.createTextNode(title));node.append(label);
  if(!station){node.append(el('h3','Only one eligible station'),el('p','Try a larger radius to find an alternative.','hint'));return node;}
  node.append(el('h3',station.name||`Station ${station.station_id}`));const metric=el('p',String(station.available_docks_now??'—'),'dock-metric');metric.append(el('span','docks available now'));node.append(metric,el('p',`${station.distance_m.toLocaleString()} m from your destination`,'card-distance'));const age=el('p',null,'card-age');age.dataset.reported=station.source_last_reported;age.textContent=`Reported ${ageText(station.source_last_reported)} ago · accepting returns`;node.append(age);
  if(station.forecast_probability!=null)node.append(el('small',`${Math.round(station.forecast_probability*100)}% forecast at arrival`));
  return node;
}
function drawDiagram(body,destination){
  $('diagram-wrap').hidden=false;
  const points=[{...destination,label:'Your destination',badge:'D'}];
  for(const [station,badge,title] of [[body.primary,'P','Primary'],[body.alternative,'A','Alternative']]){
    if(station) {
      const label=`${title}: ${station.name} · ${station.available_docks_now??'Unknown'} docks now · ${station.distance_m} m straight-line`;
      const coincident=points.find(p=>p.lat===station.lat&&p.lon===station.lon);
      if(coincident){coincident.badge+=`/${badge}`;coincident.label+=` · ${label}`;}
      else points.push({lat:station.lat,lon:station.lon,badge,label});
    }
  }
  DocksideMaps.render($('diagram'),points);
}
function showResult(body,destination){
  latest=body;dirty=false;$('output').replaceChildren();$('mode-notice').hidden=false;$('mode-notice').className='notice '+(body.mode==='fixture_demo'?'':'live');$('mode-notice').textContent=body.mode==='fixture_demo'?'Sample data · fictional availability for demonstration only.':body.partial_feed?'Some station updates are missing. These options have fresh individual reports.':'Available now · selected by distance. A dock at your arrival time is not guaranteed.';
  if(body.primary){const cards=el('div',null,'cards');cards.append(card('Primary',body.primary),card('Alternative',body.alternative));$('output').append(cards);drawDiagram(body,destination);}else{const empty=el('div',null,'empty');empty.append(el('h3','No suitable docks in this radius'),el('p','Nearby stations may be full, closed, or missing a fresh report. Try expanding your search.'));if(Number($('radius').value)<2000){const button=el('button','Search within 2 km');button.type='button';button.onclick=()=>{$('radius').value='2000';$('search').requestSubmit();};empty.append(button);}$('output').append(empty);}
  $('result-footer').hidden=false;$('result-time').textContent=`Checked ${new Date(body.generated_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}`;
}
function showError(error){latest=null;$('diagram-wrap').hidden=true;$('result-footer').hidden=true;$('mode-notice').hidden=true;const panel=el('div',null,'error-panel');panel.append(el('h3',error.name==='AbortError'?'This is taking longer than expected':'We can’t check docks right now'),el('p',error.name==='AbortError'?'The request timed out. Please retry.':error.message));panel.append(el('p','If you run this app locally, check that Docker Desktop is running. Use “make status” or “make logs” in the project terminal.'));const retry=el('button','Try again');retry.type='button';retry.onclick=()=>{$('search').requestSubmit();checkHealth();};panel.append(retry);if(error.requestId)panel.append(el('p',`Reference: ${error.requestId}`,'request-ref'));$('output').replaceChildren(panel);}
async function search(event){event?.preventDefault();if(busy)return;$('input-error').hidden=true;let destination;try{destination=selectedDestination();}catch(error){$('input-error').textContent=error.message;$('input-error').hidden=false;return;}const searchRevision=revision;const userAction=event?.submitter!=null;busy=true;$('find').disabled=true;$('refresh').disabled=true;$('results-panel').setAttribute('aria-busy','true');$('diagram-wrap').hidden=true;$('result-footer').hidden=true;$('mode-notice').hidden=true;$('output').replaceChildren(el('div','Checking nearby station reports…','loading'));
  try{const body=await jsonFetch('/v1/recommendations',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({destination,horizon_minutes:Number($('horizon').value),radius_m:Number($('radius').value)})});if(searchRevision===revision){showResult(body,destination);if(userAction&&window.innerWidth<=680)$('results-panel').scrollIntoView({block:'start'});}checkHealth();}catch(error){if(searchRevision===revision)showError(error);}finally{busy=false;$('find').disabled=false;$('refresh').disabled=false;$('results-panel').setAttribute('aria-busy','false');}}
$('search').addEventListener('submit',search);$('refresh').onclick=()=>$('search').requestSubmit();
document.querySelectorAll('[data-place]').forEach(button=>button.onclick=()=>{$('destination').value=button.dataset.place;$('coordinates').open=false;updateCoordinates();markDirty();$('destination').focus();});
function updateCoordinates(){const place=places.get($('destination').value);if(place){$('lat').value=place.lat;$('lon').value=place.lon;}}
function markDirty(){revision++;dirty=true;latest=null;$('diagram-wrap').hidden=true;$('result-footer').hidden=true;$('mode-notice').hidden=true;$('output').replaceChildren(el('div','Destination or options changed. Select “Find return stations” to update your results.','empty'));}
$('coordinates').addEventListener('toggle',()=>{$('destination').required=!$('coordinates').open;markDirty();});
$('destination').addEventListener('input',()=>{updateCoordinates();markDirty();});for(const id of ['lat','lon','horizon','radius'])$(id).addEventListener('input',markDirty);
setInterval(()=>{document.querySelectorAll('[data-reported]').forEach(node=>{node.textContent=`Reported ${ageText(node.dataset.reported)} ago · accepting returns`;});if(latest&&latest.mode!=='fixture_demo'&&Date.now()-new Date(latest.generated_at).getTime()>120000){$('mode-notice').hidden=false;$('mode-notice').className='notice';$('mode-notice').textContent='These results are over two minutes old. Refresh before relying on the available dock counts.';}},10000);
setInterval(()=>{if(!document.hidden)checkHealth();},30000);
setInterval(()=>{if(!document.hidden&&!busy&&!dirty&&latest&&$('auto-refresh').checked)$('search').requestSubmit();},60000);
checkHealth();loadStations();
