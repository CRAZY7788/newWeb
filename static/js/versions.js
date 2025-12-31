function openVersionsFromRow(row){
  const name=row.dataset.file;
  $('#verFile').textContent=name;
  populateVersions(name);
  STATE.file=name;
  show('versions');
}

function populateVersions(fileName){
  const scroller=$('#versionScroller'); scroller.innerHTML='';
  ['V1','V2','V2.1','V2.2','V3'].forEach((v,i)=>{
    const card=document.createElement('article'); card.className='version-card';
    card.innerHTML = `<h3>${v}</h3><p style="color:var(--muted)">${fileName} 的历史版本</p><p class="meta"><span>${new Date(2024+i,i%12,10+i).toLocaleDateString()}</span><span>by User${i+1}</span></p>`;
    scroller.appendChild(card);
  });
}
