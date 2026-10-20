'use strict';
// Render-only layer. All calculations live in the dependency-free, tested logic module.
const DocksideAnalysis = (() => {
  let inspected = {}, notes = {};
  const palette = ['#237769','#aa7536','#537f88','#6d776a'];
  const stationWord = count => count===1?'station':'stations';
  function plot(id, yLabel, yMax=100) {
    const chart=canvas(id,540,300),left=48,top=28,width=475,height=210;
    for(let i=0;i<=4;i++) {
      const y=top+height-i*height/4;
      chart.append(svg('line',{x1:left,y1:y,x2:left+width,y2:y,class:'axis'}),
        svg('text',{x:left-9,y:y+4,'text-anchor':'end'},number(yMax*i/4)));
    }
    chart.append(svg('text',{x:left,y:13},yLabel));
    return {chart,left,top,width,height,y:v=>top+height-v/yMax*height};
  }
  function distribution(stats) {
    const rows=stats.bins.map(({members,...row})=>({...row,
      included_station_count:stats.included.length,excluded_below_minimum:stats.excluded_sparse,
      excluded_without_usable_counts:stats.excluded_unknown,analysis_version:'descriptive_v1'}));
    inspected.distribution=rows;
    notes.distribution='Unit: stations, each counted once. Bin lower bounds are inclusive; upper bounds are exclusive except 100%. The minimum applies to usable observations per station.';
    const foot=$('distribution-finding');
    if(!stats.included.length){foot.textContent='No supported stations. Reduce the minimum or widen the main filters.';return empty($('distribution-chart'),'No stations meet the selected minimum with usable counts.','Insufficient station support');}
    const peak=Math.max(...rows.map(r=>r.station_count));
    const scale=10**Math.floor(Math.log10(Math.max(1,peak)));
    const max=Math.max(4,Math.ceil(peak*1.15/scale)*scale); // Headroom for count labels.
    const p=plot('distribution-chart','Number of stations',max),step=p.width/rows.length;
    rows.forEach((row,i)=>{
      const x=p.left+i*step+12,w=step-24,y=p.y(row.station_count);
      const label=`${row.band} full share: ${row.station_count} stations (${percent(row.share_of_included_stations)} of included stations). Inspect stations.`;
      const group=svg('g');
      // A transparent hit area keeps genuinely zero-height bars inspectable.
      group.append(svg('rect',{x,y:p.top,width:w,height:p.height,fill:'transparent'}),
        svg('rect',{x,y,width:w,height:p.top+p.height-y,rx:3,fill:i<2?'#337f73':'#bd8b45'}),
        svg('text',{x:x+w/2,y:Math.max(p.top+12,y-7),'text-anchor':'middle'},number(row.station_count)),
        svg('text',{x:x+w/2,y:258,'text-anchor':'middle'},row.band));
      actionable(group,label,()=>inspectRows(`${row.band} full share · station details`,stats.bins[i].members,notes.distribution));
      p.chart.append(group);
    });
    p.chart.append(svg('text',{x:p.left+p.width/2,y:284,'text-anchor':'middle'},'Share of usable observations with zero docks'));
    const high=stats.included.filter(r=>r.full_share>=.25).length;
    foot.textContent=`${number(high)} of ${number(stats.included.length)} included ${stationWord(stats.included.length)} showed zero docks in at least 25% of usable observations. This is a descriptive threshold, not a service standard.`;
  }
  function scatter(stats) {
    const rows=stats.included.filter(s=>s.average_docks!=null);
    inspected.scatter=rows.map(row=>({...row,analysis_version:'descriptive_v1'}));
    notes.scatter='One point per station. Both axes use the same usable observations. Equal-size points; no capacity adjustment, fitted causal relationship or forecast.';
    if(!rows.length)return empty($('scatter-chart'),'No stations meet the minimum with both a known average and full share.','Insufficient station support');
    const p=plot('scatter-chart','Zero-dock observations (%)');
    const max=Math.max(5,Math.ceil(Math.max(...rows.map(s=>s.average_docks))/5)*5);
    for(let i=0;i<=4;i++)p.chart.append(svg('text',{
      x:p.left+i*p.width/4,y:258,'text-anchor':'middle'},number(max*i/4)));
    for(const row of rows) {
      const dot=svg('circle',{cx:p.left+row.average_docks/max*p.width,
        cy:p.y(row.full_share*100),r:4.5,fill:'#287a6c','fill-opacity':.55,stroke:'#fff','stroke-width':.6});
      const label=`${row.name} (#${row.station_id}): ${number(row.average_docks)} average docks; ${percent(row.full_share)} full (${number(row.full_observations)}/${number(row.usable_observations)}). Select to focus the dashboard.`;
      actionable(dot,label,()=>chooseStation(row.station_id),()=>$('scatter-detail').textContent=label);
      p.chart.append(dot);
    }
    p.chart.append(svg('text',{x:p.left+p.width/2,y:284,'text-anchor':'middle'},'Average reported docks per usable observation'));
    $('scatter-detail').textContent=`${number(rows.length)} ${stationWord(rows.length)} plotted; ${stats.included.length-rows.length} missing an average. Hover or focus a dot for counts; select it to focus the dashboard.`;
  }
  function dayTypes(response) {
    const rows=DocksideDashboardLogic.dayTypeProfile(response.heatmap,100);
    inspected.daytypes=rows.map(row=>({...row,analysis_version:'descriptive_v1'}));
    notes.daytypes='Rates are SUM(available observations) / SUM(usable observations), not an average of percentages. Blank points have fewer than 100 usable observations. This is an unadjusted comparison, not a causal effect or rider success rate.';
    const supported=rows.filter(r=>r.availability_rate!=null);
    const selected=response.filters.day_type;
    $('daytype-finding').textContent=selected==='all'
      ? 'Compare the same hour, then inspect its counts. Different station/date mixes and collection gaps can explain differences. No statistical significance is claimed.'
      : `Only ${selected==='weekday'?'weekdays':'weekends'} are selected. Choose Every day in the main filters to compare both groups.`;
    if(!supported.length)return empty($('daytype-chart'),'Each day-type/hour point needs 100 usable observations. Widen the main filters; missing data is not 0%.','Insufficient hourly support');
    const p=plot('daytype-chart','Observations with a dock (%)');
    const x=h=>p.left+h/23*p.width;
    [0,4,8,12,16,20,23].forEach(h=>p.chart.append(svg('text',{x:x(h),y:258,'text-anchor':'middle'},String(h).padStart(2,'0'))));
    ['Weekday','Weekend'].forEach((type,index)=>{
      let path='',previous=null;
      const series=rows.filter(r=>r.day_type===type);
      for(const row of series) {
        if(row.availability_rate==null){previous=null;continue;}
        path+=`${previous===null?'M':'L'}${x(row.local_hour)},${p.y(row.availability_rate*100)} `;
        previous=row.local_hour;
      }
      p.chart.append(svg('path',{d:path,fill:'none',stroke:palette[index],'stroke-width':2,
        'stroke-dasharray':index?'6 4':'none'}));
      for(const row of series.filter(r=>r.availability_rate!=null)) {
        const cx=x(row.local_hour),cy=p.y(row.availability_rate*100);
        const marker=index?svg('rect',{x:cx-4,y:cy-4,width:8,height:8,fill:palette[index],stroke:'white'}):
          svg('circle',{cx,cy,r:4.5,fill:palette[index],stroke:'white'});
        const label=`${type} ${String(row.local_hour).padStart(2,'0')}:00: ${percent(row.availability_rate)} with a dock (${number(row.available_observations)}/${number(row.usable_observations)}). Inspect counts.`;
        actionable(marker,label,()=>inspectRows('Day-type / hour comparison',rows.filter(r=>r.local_hour===row.local_hour),notes.daytypes));
        p.chart.append(marker);
      }
    });
    p.chart.append(svg('text',{x:p.left+p.width/2,y:284,'text-anchor':'middle'},'Toronto local hour · minimum 100 observations per point'));
  }
  function quality(response) {
    const rows=DocksideDashboardLogic.qualityBreakdown(response.summary),host=$('quality-chart');
    inspected.quality=(rows||[]).map(row=>({...row,analysis_version:'descriptive_v1'}));
    notes.quality='Four mutually exclusive categories partition recorded canonical observations. Only the first two form the availability denominator. Missing polls, quarantined records and noncanonical snapshots are outside this population—not hidden successes.';
    host.replaceChildren();
    if(!rows||!response.summary.observations)return empty(host,rows?'No recorded observations match this selection.':'Aggregate counts are inconsistent; this breakdown cannot be calculated.');
    rows.forEach((row,i)=>{
      const button=el('button',null,'quality-row');button.type='button';
      const head=el('span',null,'quality-label');
      head.append(el('span',row.category),el('strong',percent(row.share_of_recorded_observations)));
      const track=el('span',null,'quality-track'),bar=el('span',null,'quality-fill');
      bar.style.width=`${row.share_of_recorded_observations*100}%`;bar.style.background=palette[i];track.append(bar);
      button.append(head,track,el('small',`${number(row.observation_count)} / ${number(row.recorded_observations)} recorded observations`));
      button.onclick=()=>inspectRows(row.category,[row],notes.quality);host.append(button);
    });
  }
  function render(response) {
    const minimum=Number($('analysis-minimum').value);
    const stats=DocksideDashboardLogic.stationAnalysis(response.stations,minimum);
    $('analysis-context').textContent=`${response.source_kind==='synthetic'?'SYNTHETIC DEMO · ':''}${$('filter-context').textContent} · ${percent(response.coverage.poll_coverage)} system collection coverage`;
    $('analysis-support').textContent=`Distribution & scatter: ${number(stats.included.length)} ${stationWord(stats.included.length)} included · ${number(stats.excluded_sparse)} below minimum · ${number(stats.excluded_unknown)} without usable counts. The minimum does not affect other charts.`;
    $('scatter-detail').textContent='No supported stations to compare.';
    distribution(stats);scatter(stats);dayTypes(response);quality(response);
  }
  function inspect(key,title) {inspectRows(title,inspected[key]||[],notes[key]||'');}
  return {render,inspect};
})();
