const regionScroller=$('#regionScroller'), detailRegion=$('#detailRegion'), detailList=$('#detailList');

regionScroller?.addEventListener('click', (e)=>{
  const card=e.target.closest('.status-card');
  if(!card) return;
  const region=card.dataset.region;
  detailRegion.textContent = (region==='China') ? 'China · NMPA' : region;
  $('#fileRegion').textContent = detailRegion.textContent;
  $('#verRegion').textContent=detailRegion.textContent;
  populateDetail(region);
  STATE.region=region;
  show('detail');
});

function populateDetail(region){
  detailList.innerHTML='';
  for(let i=1;i<=12;i++){
    const row=document.createElement('div'); row.className='row'; row.dataset.group=`占位条目 ${i}`;
    row.innerHTML = `<span class="idx">${i}.</span><span><b>${region} 组 · </b>${row.dataset.group}</span><span class="tag">Class ${(i%3==1)?'A':(i%3==2)?'B':'C'}</span><span>${new Date(2025,i%12,i).toLocaleDateString()}</span><span>Owner ${(i%4)+1}</span>`;
    row.ondblclick = ()=> openFiles(row.dataset.group);
    detailList.appendChild(row);
  }
}
