function resetFolderNav(){
  STATE.currentFolderId = null;
  STATE.folderStack = [];
}

async function resolveFolderFromHash(){
  if(!STATE.currentFolderId){
    STATE.folderStack = [];
    return;
  }
  const json = await api('/api/folders/' + STATE.currentFolderId);
  STATE.folderStack = json.path.map(f => ({ id: f.id, name: f.name }));
}

function renderFolderBreadcrumbs(){
  const el = $('#folderBreadcrumbs');
  if(!el) return;
  const parts = [];
  const addCrumb = (label, action) => {
    const span = document.createElement('span');
    span.textContent = label;
    if(action){
      span.style.cursor = 'pointer';
      span.style.color = 'var(--brand)';
      span.onclick = action;
    }
    parts.push(span);
  };
  addCrumb(STATE.project || '项目', () => navigateFolderRoot());
  addCrumb(STATE.regionLabel || STATE.region || '地区', () => navigateFolderRoot());
  STATE.folderStack.forEach((f, idx) => {
    const slash = document.createElement('span');
    slash.className = 'slash';
    slash.textContent = '/';
    parts.push(slash);
    const isLast = idx === STATE.folderStack.length - 1;
    addCrumb(f.name, isLast ? null : () => navigateFolderTo(idx));
  });
  el.innerHTML = '';
  parts.forEach((node, i) => {
    if(i > 0 && !node.classList?.contains('slash')){
      const slash = document.createElement('span');
      slash.className = 'slash';
      slash.textContent = '/';
      el.appendChild(slash);
    }
    el.appendChild(node);
  });
  const upBtn = $('#folderUpBtn');
  if(upBtn) upBtn.disabled = STATE.folderStack.length === 0;
}

async function navigateFolderRoot(){
  STATE.currentFolderId = null;
  STATE.folderStack = [];
  await refreshFolderListing();
}

async function navigateFolderTo(stackIndex){
  STATE.folderStack = STATE.folderStack.slice(0, stackIndex + 1);
  const last = STATE.folderStack[STATE.folderStack.length - 1];
  STATE.currentFolderId = last ? last.id : null;
  STATE.view = 'detail';
  await refreshFolderListing();
  syncHash();
}

async function enterFolder(folder){
  STATE.folderStack.push({ id: folder.id, name: folder.name });
  STATE.currentFolderId = folder.id;
  STATE.view = 'detail';
  await refreshFolderListing();
  syncHash();
}

async function refreshFolderListing(){
  if(!STATE.regionId) return;
  if(STATE.currentFolderId){
    await resolveFolderFromHash();
  } else {
    STATE.folderStack = [];
  }
  renderFolderBreadcrumbs();
  const parentParam = STATE.currentFolderId == null ? 'null' : STATE.currentFolderId;
  const json = await api(`/api/folders?region_id=${STATE.regionId}&parent_id=${parentParam}`);
  STATE.folders = json.folders;
  const list = $('#detailList');
  list.innerHTML = '';
  if(!json.folders.length){
    list.innerHTML = '<div class="row"><span></span><span class="muted">此目录下还没有文件夹，可点击「新建文件夹」。</span><span></span><span></span><span></span></div>';
  }
  json.folders.forEach((f, idx) => {
    const row = document.createElement('div');
    row.className = 'row';
    row.dataset.folderId = f.id;
    row.innerHTML = `
      <span class="idx">${idx + 1}.</span>
      <span>📁 <b>${f.name}</b></span>
      <span class="tag">${f.child_count} 子文件夹</span>
      <span>${f.file_count} 个文件</span>
      <span><button type="button" class="btn" data-open-files="${f.id}">文档</button></span>`;
    row.addEventListener('dblclick', () => enterFolder(f));
    row.querySelector('[data-open-files]').addEventListener('click', (e) => {
      e.stopPropagation();
      openFilesFromFolder(f);
    });
    list.appendChild(row);
  });
  await loadFolderFilePreview();
  const btn = $('#newFolderBtn');
  if(btn) btn.style.display = canEdit() ? '' : 'none';
}

function openFilesFromFolder(folder){
  if(!STATE.folderStack.length || STATE.folderStack[STATE.folderStack.length - 1].id !== folder.id){
    const idx = STATE.folderStack.findIndex(x => x.id === folder.id);
    if(idx >= 0){
      STATE.folderStack = STATE.folderStack.slice(0, idx + 1);
    } else {
      STATE.folderStack.push({ id: folder.id, name: folder.name });
    }
    STATE.currentFolderId = folder.id;
  }
  openFiles(folder.id, folder.name);
}

const folderDialog = $('#folderDialog');
const folderForm = $('#folderForm');

$('#newFolderBtn')?.addEventListener('click', () => {
  if(!canEdit()){ toast('当前角色不能创建文件夹'); return; }
  folderForm.reset();
  folderDialog.classList.add('open');
});

$('#cancelFolder')?.addEventListener('click', () => folderDialog.classList.remove('open'));
folderDialog?.addEventListener('click', (e) => { if(e.target === folderDialog) folderDialog.classList.remove('open'); });

folderForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(folderForm);
  const name = (fd.get('name') || '').trim();
  if(!name) return;
  try{
    await api('/api/folders', {
      method: 'POST',
      body: JSON.stringify({
        name,
        region_id: STATE.regionId,
        parent_id: STATE.currentFolderId
      })
    });
    folderDialog.classList.remove('open');
    toast('文件夹已创建');
    await refreshFolderListing();
  }catch(err){
    toast(err.message);
  }
});

$('#folderUpBtn')?.addEventListener('click', async () => {
  if(STATE.folderStack.length === 0) return;
  STATE.folderStack.pop();
  const last = STATE.folderStack[STATE.folderStack.length - 1];
  STATE.currentFolderId = last ? last.id : null;
  await refreshFolderListing();
});
