const regionScroller=$('#regionScroller'), detailRegion=$('#detailRegion'), detailList=$('#detailList');

regionScroller?.addEventListener('click', async (e)=>{
  const card=e.target.closest('.status-card');
  if(!card) return;
  try{
    await populateDetail(Number(card.dataset.regionId), card.dataset.region, card.dataset.label);
    show('detail');
  }catch(err){
    toast(err.message);
  }
});

async function loadBoard(projectId){
  if(!projectId) return;
  const json = await api('/api/regions?project_id='+projectId);
  STATE.regions = json.regions;
  regionScroller.innerHTML = '';
  json.regions.forEach((r, idx)=>{
    const art = document.createElement('article');
    art.className = 'status-card';
    art.dataset.region = r.name;
    art.dataset.regionId = r.id;
    art.dataset.label = r.label;
    art.innerHTML = `<h3>${r.label}</h3>
      <p class="meta"><span>Status: ${r.status}</span> <span>${r.file_count} files</span></p>
      <div class="bar"><span style="width:${r.progress}%"></span></div>`;
    regionScroller.appendChild(art);
  });
  if(!STATE.regionId && json.regions.length){
    const match = json.regions.find(r=>r.name===STATE.region) || json.regions[0];
    STATE.regionId = match.id;
    STATE.region = match.name;
    STATE.regionLabel = match.label;
  }
}

async function populateDetail(regionId, regionName, regionLabel){
  if(!regionId && STATE.regions.length){
    const match = STATE.regions.find(r=>r.name===regionName) || STATE.regions[0];
    regionId = match.id;
    regionName = match.name;
    regionLabel = match.label;
  }
  STATE.regionId = regionId;
  STATE.region = regionName;
  STATE.regionLabel = regionLabel || regionName;
  detailRegion.textContent = STATE.regionLabel;
  $('#fileRegion').textContent = STATE.regionLabel;
  $('#verRegion').textContent = STATE.regionLabel;

  const json = await api('/api/groups?region_id='+regionId);
  STATE.groups = json.groups;
  detailList.innerHTML = '';
  json.groups.forEach((g, idx)=>{
    const row=document.createElement('div');
    row.className='row';
    row.dataset.group = g.name;
    row.dataset.groupId = g.id;
    row.innerHTML = `<span class="idx">${idx+1}.</span><span><b>${STATE.region} · </b>${g.name}</span><span class="tag">${g.accepted}/${g.file_count}</span><span>${g.file_count} 个文件</span><span></span>`;
    row.ondblclick = ()=> openFiles(g.id, g.name);
    detailList.appendChild(row);
  });
}
