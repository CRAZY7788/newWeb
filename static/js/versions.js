function openVersionsFromRow(row){
  const name = row.dataset.file;
  const fileId = Number(row.dataset.fileId);
  $('#verFile').textContent = name;
  STATE.file = name;
  STATE.fileId = fileId;
  populateVersions(fileId, name);
  show('versions');
}

async function populateVersions(fileId, fileName){
  const scroller=$('#versionScroller');
  scroller.innerHTML='加载中...';
  try{
    const json = await api('/api/files/versions?file_id='+fileId);
    scroller.innerHTML='';
    if(!json.versions.length){
      scroller.innerHTML = '<p style="color:var(--muted)">暂无版本</p>';
      return;
    }
    json.versions.forEach(v=>{
      const card=document.createElement('article');
      card.className='version-card';
      card.style.cursor='pointer';
      card.innerHTML = `<h3>${v.label}</h3><p style="color:var(--muted)">${fileName}${v.comment ? ' · '+v.comment : ''}</p><p class="meta"><span>${v.date}</span><span>${v.author||''}</span></p>`;
      card.onclick = ()=> window.open('/versions/download?version_id='+v.id);
      scroller.appendChild(card);
    });
  }catch(err){
    scroller.innerHTML = '';
    toast(err.message);
  }
}
