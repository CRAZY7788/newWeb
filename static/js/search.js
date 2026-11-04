const searchInput = $('#searchInput');
const searchPanel = $('#searchPanel');
let searchTimer = null;
let lastSearchQuery = '';

function hideSearchPanel(){
  searchPanel?.classList.remove('open');
  searchPanel.innerHTML = '';
}

function renderSearchResults(json){
  if(!searchPanel) return;
  const parts = [];
  const addSection = (title, html) => {
    if(!html) return;
    parts.push(`<div class="search-section">${title}</div>${html}`);
  };

  let filesHtml = '';
  (json.files || []).forEach(f => {
    const loc = f.location;
    const sub = loc
      ? `${loc.project_name} · ${loc.region_label || loc.region_name} · ${loc.folder_path}`
      : '';
    const code = f.doc_code ? ` · ${f.doc_code}` : '';
    filesHtml += `<button type="button" class="search-hit" data-kind="file" data-file-id="${f.id}" data-name="${escapeAttr(f.name)}">
      <div class="title">${escapeHtml(f.name)}${escapeHtml(code)}</div>
      <div class="sub">${escapeHtml(sub)} · ${escapeHtml(f.status || '')}</div>
    </button>`;
  });

  let foldersHtml = '';
  (json.folders || []).forEach(f => {
    const loc = f.location;
    const sub = loc
      ? `${loc.project_name} · ${loc.region_label || loc.region_name}`
      : '';
    foldersHtml += `<button type="button" class="search-hit" data-kind="folder" data-folder-id="${f.id}">
      <div class="title">📁 ${escapeHtml(f.path || f.name)}</div>
      <div class="sub">${escapeHtml(sub)}</div>
    </button>`;
  });

  addSection('文档', filesHtml);
  addSection('文件夹', foldersHtml);

  if(!parts.length){
    searchPanel.innerHTML = `<div class="search-empty">未找到与「${escapeHtml(json.q || '')}」相关的结果</div>`;
  } else {
    searchPanel.innerHTML = parts.join('');
  }
  searchPanel.classList.add('open');
}

function escapeHtml(s){
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
}

function escapeAttr(s){
  return escapeHtml(s).replace(/'/g, '&#39;');
}

async function runSearch(q){
  const params = new URLSearchParams({ q });
  if(STATE.projectId) params.set('project_id', STATE.projectId);
  const json = await api('/api/search?' + params.toString());
  lastSearchQuery = q;
  renderSearchResults(json);
}

async function navigateToSearchFile(fileId, name, loc){
  if(!loc || !loc.folder_id){
    toast('无法定位文档位置');
    return;
  }
  hideSearchPanel();
  STATE.projectId = loc.project_id;
  STATE.project = loc.project_name;
  STATE.regionId = loc.region_id;
  STATE.region = loc.region_name;
  STATE.regionLabel = loc.region_label || loc.region_name;
  STATE.currentFolderId = loc.folder_id;
  STATE.groupId = loc.folder_id;
  const segs = (loc.folder_path || '').split(' / ');
  STATE.group = segs[segs.length - 1] || loc.folder_path;
  try{
    const meta = await api('/api/folders/' + loc.folder_id);
    STATE.folderStack = meta.path.map(f => ({ id: f.id, name: f.name }));
    await loadBoard(loc.project_id);
    await populateDetail(loc.region_id, loc.region_name, loc.region_label);
    await openTrace(Number(fileId), name, 'detail');
  }catch(err){
    toast(err.message);
  }
}

async function navigateToSearchFolder(loc){
  if(!loc || !loc.folder_id){
    toast('无法打开文件夹');
    return;
  }
  hideSearchPanel();
  STATE.projectId = loc.project_id;
  STATE.project = loc.project_name;
  STATE.regionId = loc.region_id;
  STATE.region = loc.region_name;
  STATE.regionLabel = loc.region_label || loc.region_name;
  STATE.currentFolderId = loc.folder_id;
  STATE.groupId = null;
  STATE.group = null;
  try{
    const meta = await api('/api/folders/' + loc.folder_id);
    STATE.folderStack = meta.path.map(f => ({ id: f.id, name: f.name }));
    await loadBoard(loc.project_id);
    await populateDetail(loc.region_id, loc.region_name, loc.region_label);
    show('detail');
    syncHash();
  }catch(err){
    toast(err.message);
  }
}

searchInput?.addEventListener('input', (e) => {
  const q = e.target.value.trim();
  clearTimeout(searchTimer);
  if(q.length < 1){
    hideSearchPanel();
    $$('#projectNav .nav-item').forEach(n => { n.style.display = ''; });
    return;
  }
  if(q.length === 1){
    $$('#projectNav .nav-item').forEach(n => {
      n.style.display = n.dataset.project.toLowerCase().includes(q.toLowerCase()) ? '' : 'none';
    });
  }
  searchTimer = setTimeout(async () => {
    try{
      await runSearch(q);
    }catch(err){
      hideSearchPanel();
      toast(err.message);
    }
  }, 280);
});

searchInput?.addEventListener('keydown', async (e) => {
  if(e.key === 'Escape'){
    hideSearchPanel();
    return;
  }
  if(e.key !== 'Enter') return;
  const q = searchInput.value.trim();
  if(!q) return;
  e.preventDefault();
  try{
    if(!searchPanel.classList.contains('open') || lastSearchQuery !== q){
      await runSearch(q);
    }
    const first = searchPanel.querySelector('.search-hit');
    first?.click();
  }catch(err){
    toast(err.message);
  }
});

searchPanel?.addEventListener('click', async (e) => {
  const btn = e.target.closest('.search-hit');
  if(!btn) return;
  const kind = btn.dataset.kind;
  try{
    if(kind === 'file'){
      const fileId = Number(btn.dataset.fileId);
      const name = btn.dataset.name || '';
      const json = await api('/api/search?q=' + encodeURIComponent(searchInput.value.trim()) + (STATE.projectId ? '&project_id=' + STATE.projectId : ''));
      const hit = (json.files || []).find(x => x.id === fileId);
      if(hit){
        await navigateToSearchFile(fileId, name, hit.location);
      }else{
        await openTrace(fileId, name, STATE.view || 'board');
      }
    }else if(kind === 'folder'){
      const folderId = Number(btn.dataset.folderId);
      const json = await api('/api/search?q=' + encodeURIComponent(searchInput.value.trim()) + (STATE.projectId ? '&project_id=' + STATE.projectId : ''));
      const hit = (json.folders || []).find(x => x.id === folderId);
      if(hit){
        await navigateToSearchFolder(hit.location);
      }
    }
  }catch(err){
    toast(err.message);
  }
});

document.addEventListener('click', (e) => {
  if(!searchInput || !searchPanel) return;
  if(e.target === searchInput || searchPanel.contains(e.target)) return;
  hideSearchPanel();
});
