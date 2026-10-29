const regionScroller=$('#regionScroller');

regionScroller?.addEventListener('click', async (e)=>{
  const card=e.target.closest('.status-card');
  if(!card) return;
  try{
    resetFolderNav();
    STATE.regionId = Number(card.dataset.regionId);
    STATE.region = card.dataset.region;
    STATE.regionLabel = card.dataset.label;
    await populateDetail(STATE.regionId, STATE.region, STATE.regionLabel);
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
  json.regions.forEach((r)=>{
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
  const verRegion = $('#verRegion');
  if(verRegion) verRegion.textContent = STATE.regionLabel;
  if(STATE.currentFolderId){
    await resolveFolderFromHash();
  }
  await refreshFolderListing();
}
