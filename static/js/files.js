const UPLOAD_ACCEPT = '.docx,.xlsx,.txt,.zip';
const FILE_TYPE_LABEL = { word: 'Word', excel: 'Excel', txt: '文本', zip: 'Zip', other: '其他' };

const fileList = $('#fileList');
const uploadDialog = $('#uploadDialog');
const uploadForm = $('#uploadForm');
const checkinDialog = $('#checkinDialog');
const checkinForm = $('#checkinForm');

function fileTypeLabel(t){
  return FILE_TYPE_LABEL[t] || FILE_TYPE_LABEL.other;
}

function renderFileViewCrumbs(folderId, folderName){
  const el = $('#fileCrumbs');
  if(!el) return;
  el.innerHTML = '';
  const crumbs = [
    { label: STATE.project || '项目' },
    { label: STATE.regionLabel || STATE.region || '地区' },
  ];
  STATE.folderStack.forEach(f => crumbs.push({ label: f.name }));
  if(folderName && (!STATE.folderStack.length || STATE.folderStack[STATE.folderStack.length - 1].id !== folderId)){
    crumbs.push({ label: folderName });
  }
  crumbs.forEach((c, i) => {
    if(i){
      const s = document.createElement('span');
      s.className = 'slash';
      s.textContent = '/';
      el.appendChild(s);
    }
    const span = document.createElement('span');
    span.textContent = c.label;
    el.appendChild(span);
  });
}

function statusTagClass(status){
  if(status === '已借出') return 'tag state out';
  if(status === '已验收') return 'tag state ok';
  if(status === '待验收') return 'tag state pending';
  if(status === '已拒绝') return 'tag state out';
  if(status === '已作废') return 'tag state out';
  return 'tag state';
}

function appendFileRows(container, files, { interactive = true } = {}){
  if(!container) return;
  container.innerHTML = '';
  if(!files.length){
    container.innerHTML = '<div class="row"><span></span><span class="muted">暂无文档，可「新建」或「上传」。</span><span></span><span></span><span></span><span></span><span></span></div>';
    return;
  }
  const head = document.createElement('div');
  head.className = 'row head';
  head.innerHTML = '<span>#</span><span>名称</span><span>类型</span><span>状态</span><span>版本</span><span>借出人</span><span></span>';
  container.appendChild(head);
  files.forEach((f, idx) => {
    const checked = !!f.checked_out_by;
    const row = document.createElement('div');
    row.className = 'row';
    row.dataset.file = f.title || f.name;
    row.dataset.fileId = f.id;
    row.dataset.checkedOut = checked ? 'true' : 'false';
    row.dataset.canCheckout = f.can_checkout ? 'true' : 'false';
    row.dataset.canCheckin = f.can_checkin ? 'true' : 'false';
    row.dataset.canRename = f.can_rename ? 'true' : 'false';
    row.dataset.canMove = f.can_move ? 'true' : 'false';
    row.dataset.canVoid = f.can_void ? 'true' : 'false';
    row.dataset.canDelete = f.can_delete ? 'true' : 'false';
    const owner = f.checked_out_by_name || '—';
    const ver = f.latest_version || '—';
    const tagClass = statusTagClass(f.status);
    const displayName = f.title || f.name;
    row.innerHTML = `
      <span class="idx">${idx + 1}.</span>
      <span>${displayName}</span>
      <span class="tag">${fileTypeLabel(f.file_type)}</span>
      <span class="${tagClass}">${f.status}</span>
      <span>${ver}</span>
      <span class="owner">${owner}</span>
      <span></span>`;
    if(interactive){
      row.ondblclick = () => window.open('/versions/download?file_id=' + f.id);
      row.addEventListener('contextmenu', (e) => openFileMenu(e, row));
      addLongPress(row, (e) => openFileMenu(e, row));
    } else {
      row.ondblclick = () => openFiles(f.folder_id, displayName);
    }
    container.appendChild(row);
  });
}

function getActiveFolderId(){
  return STATE.groupId || STATE.currentFolderId;
}

function openUploadDialog(folderId){
  const fid = folderId || getActiveFolderId();
  if(!fid){ toast('请先进入文件夹'); return; }
  if(!canEdit()){ toast('当前角色不能上传'); return; }
  STATE.groupId = fid;
  uploadForm.reset();
  uploadForm.dataset.folderId = String(fid);
  uploadDialog.classList.add('open');
}

async function openFiles(folderId, folderName, opts = {}){
  STATE.groupId = folderId;
  STATE.group = folderName;
  STATE.currentFolderId = folderId;
  if(!STATE.folderStack.length || STATE.folderStack[STATE.folderStack.length - 1].id !== folderId){
    try{
      const meta = await api('/api/folders/' + folderId);
      STATE.folderStack = meta.path.map(f => ({ id: f.id, name: f.name }));
    }catch(e){ /* keep stack */ }
  }
  renderFileViewCrumbs(folderId, folderName);
  const uploadBtn = $('#uploadBtn');
  const createBtn = $('#createBtn');
  if(uploadBtn) uploadBtn.style.display = canEdit() ? '' : 'none';
  if(createBtn) createBtn.style.display = canEdit() ? '' : 'none';
  const json = await api('/api/files?folder_id=' + folderId);
  appendFileRows(fileList, json.files, { interactive: true });
  if(!opts.silent) show('files');
  return json.files;
}

async function loadFolderFilePreview(){
  const block = $('#folderFilesBlock');
  const list = $('#folderFileList');
  const uploadBtn = $('#detailUploadBtn');
  const createBtn = $('#detailCreateBtn');
  const manageBtn = $('#openFolderFilesBtn');
  if(!STATE.currentFolderId){
    if(block) block.hidden = true;
    if(uploadBtn) uploadBtn.style.display = 'none';
    if(createBtn) createBtn.style.display = 'none';
    if(manageBtn) manageBtn.style.display = 'none';
    return;
  }
  if(block) block.hidden = false;
  if(uploadBtn) uploadBtn.style.display = canEdit() ? '' : 'none';
  if(createBtn) createBtn.style.display = canEdit() ? '' : 'none';
  if(manageBtn) manageBtn.style.display = '';
  const json = await api('/api/files?folder_id=' + STATE.currentFolderId);
  appendFileRows(list, json.files, { interactive: true });
  if(manageBtn){
    manageBtn.onclick = () => {
      const name = STATE.folderStack.length
        ? STATE.folderStack[STATE.folderStack.length - 1].name
        : '文档';
      openFiles(STATE.currentFolderId, name);
    };
  }
}

function openFileMenu(e, row){
  e.preventDefault();
  const items = [];
  if(row.dataset.canCheckin === 'true'){
    items.push({ text: 'Check in', action: () => openCheckinDialog(Number(row.dataset.fileId)) });
  } else if(row.dataset.canCheckout === 'true'){
    items.push({ text: 'Check out', action: () => doCheckout(row) });
  }
  if(row.dataset.canRename === 'true'){
    items.push({ text: '重命名', action: () => openRenameDialog(row) });
  }
  if(row.dataset.canMove === 'true'){
    items.push({ text: '移动到…', action: () => openMoveDialog(row) });
  }
  if(row.dataset.canVoid === 'true'){
    items.push({ text: '作废', action: () => confirmVoid(row) });
  }
  if(row.dataset.canDelete === 'true'){
    items.push({ text: '永久删除', action: () => confirmDelete(row) });
  }
  items.push({ text: '历史版本', action: () => openVersionsFromRow(row) });
  items.push({ text: '文档追溯', action: () => openTrace(Number(row.dataset.fileId), row.dataset.file) });
  openContextMenu(e, items);
}

async function doCheckout(row){
  const fid = Number(row.dataset.fileId);
  try{
    await api('/api/files/checkout', {
      method: 'POST',
      body: JSON.stringify({ file_id: fid }),
    });
    toast('已 Check out，可编辑后 Check in 提交新版本');
    await refreshFileLists();
  }catch(err){
    toast(err.message);
  }
}

async function refreshFileLists(){
  if(STATE.view === 'files' && STATE.groupId){
    await openFiles(STATE.groupId, STATE.group, { silent: true });
  }
  await loadFolderFilePreview();
}

async function toggleCheckout(row){
  if(row.dataset.canCheckin === 'true'){
    openCheckinDialog(Number(row.dataset.fileId));
    return;
  }
  if(row.dataset.canCheckout === 'true'){
    await doCheckout(row);
  }
}

function openCheckinDialog(fileId){
  checkinForm.reset();
  checkinForm.file_id.value = fileId;
  checkinDialog.classList.add('open');
}

$('#uploadBtn')?.addEventListener('click', () => openUploadDialog(STATE.groupId));
$('#detailUploadBtn')?.addEventListener('click', () => openUploadDialog(STATE.currentFolderId));

const createDialog = $('#createDialog');
const createForm = $('#createForm');

function updateCreateCommentVisibility(){
  const type = createForm?.querySelector('[name=type]')?.value;
  const field = $('#createCommentField');
  if(field) field.style.display = type === 'txt' ? '' : 'none';
}

function openCreateDialog(folderId){
  const fid = folderId || getActiveFolderId();
  if(!fid){ toast('请先进入文件夹'); return; }
  if(!canEdit()){ toast('当前角色不能新建'); return; }
  STATE.groupId = fid;
  createForm.reset();
  createForm.dataset.folderId = String(fid);
  updateCreateCommentVisibility();
  createDialog.classList.add('open');
}

$('#createBtn')?.addEventListener('click', () => openCreateDialog(STATE.groupId));
$('#detailCreateBtn')?.addEventListener('click', () => openCreateDialog(STATE.currentFolderId));
createForm?.querySelector('[name=type]')?.addEventListener('change', updateCreateCommentVisibility);
$('#cancelCreate')?.addEventListener('click', () => createDialog.classList.remove('open'));
createDialog?.addEventListener('click', (e) => { if(e.target === createDialog) createDialog.classList.remove('open'); });

function folderIdFromDialogForm(form){
  const raw = form?.dataset?.folderId;
  const id = raw ? Number(raw) : NaN;
  return Number.isFinite(id) && id > 0 ? id : null;
}

createForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(createForm);
  const folderId = folderIdFromDialogForm(createForm);
  if(!folderId){ toast('请重新打开「新建文档」并选择文件夹'); return; }
  const body = {
    folder_id: folderId,
    type: fd.get('type'),
    name: (fd.get('name') || '').trim(),
    comment: (fd.get('comment') || '').trim(),
  };
  try{
    await api('/api/files/create', { method: 'POST', body: JSON.stringify(body) });
    createDialog.classList.remove('open');
    toast('已创建');
    if(STATE.view === 'files' && STATE.groupId){
      await openFiles(STATE.groupId, STATE.group);
    }
    await loadFolderFilePreview();
  }catch(err){
    toast(err.message);
  }
});

$('#cancelUpload')?.addEventListener('click', () => uploadDialog.classList.remove('open'));
uploadDialog?.addEventListener('click', (e) => { if(e.target === uploadDialog) uploadDialog.classList.remove('open'); });

uploadForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(uploadForm);
  const folderId = folderIdFromDialogForm(uploadForm);
  if(!folderId){ toast('请重新打开「上传文档」并选择文件夹'); return; }
  fd.set('folder_id', folderId);
  try{
    await apiForm('/api/files/upload', fd);
    uploadDialog.classList.remove('open');
    toast('上传成功');
    if(STATE.view === 'files' && STATE.groupId){
      await openFiles(STATE.groupId, STATE.group);
    }
    await loadFolderFilePreview();
  }catch(err){
    toast(err.message);
  }
});

$('#cancelCheckin')?.addEventListener('click', () => checkinDialog.classList.remove('open'));
checkinDialog?.addEventListener('click', (e) => { if(e.target === checkinDialog) checkinDialog.classList.remove('open'); });

checkinForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(checkinForm);
  try{
    await apiForm('/api/files/checkin', fd);
    checkinDialog.classList.remove('open');
    toast('已 Check in，进入待验收');
    await refreshFileLists();
    loadAcceptance();
  }catch(err){
    toast(err.message);
  }
});

async function openTrace(fileId, fileName){
  STATE.fileId = fileId;
  STATE.file = fileName;
  $('#traceFile').textContent = fileName;
  $('#traceProject').textContent = STATE.project || '';
  const json = await api('/api/files/trace?file_id=' + fileId);
  const f = json.file || {};
  $('#traceSummary').textContent = `${f.title || f.name || fileName} · ${fileTypeLabel(f.file_type)} · 状态 ${f.status || ''} · 当前版本 ${f.latest_version || ''}`;
  const table = $('#traceVersionTable');
  table.innerHTML = '<tr><th>版本</th><th>时间</th><th>作者</th><th>说明</th><th>文件</th><th>SHA256</th></tr>';
  (json.versions || []).forEach(v => {
    const tr = document.createElement('tr');
    const hash = v.sha256 ? v.sha256.slice(0, 16) + '…' : '—';
    tr.innerHTML = `<td>${v.label}</td><td>${v.date || ''}</td><td>${v.author || ''}</td><td>${v.comment || ''}</td><td>${v.original_filename || ''}</td><td class="hash">${hash}</td>`;
    tr.style.cursor = 'pointer';
    tr.onclick = () => window.open('/versions/download?version_id=' + v.id);
    table.appendChild(tr);
  });
  const audit = $('#traceAuditList');
  audit.innerHTML = '';
  (json.audit || []).forEach((a, idx) => {
    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML = `<span class="idx">${idx + 1}.</span><span>${a.action}</span><span class="tag">${a.user || ''}</span><span>${a.created_at || ''}</span><span>${a.detail || ''}</span>`;
    audit.appendChild(row);
  });
  show('trace');
}

const renameDialog = $('#renameDialog');
const renameForm = $('#renameForm');
const moveDialog = $('#moveDialog');
const moveForm = $('#moveForm');
const moveFolderSelect = $('#moveFolderSelect');

function openRenameDialog(row){
  renameForm.reset();
  renameForm.file_id.value = row.dataset.fileId;
  renameForm.name.value = row.dataset.file || '';
  renameDialog.classList.add('open');
}

async function openMoveDialog(row){
  if(!STATE.regionId){
    toast('请先进入项目地区');
    return;
  }
  moveForm.reset();
  moveForm.file_id.value = row.dataset.fileId;
  moveFolderSelect.innerHTML = '<option value="">加载中…</option>';
  moveDialog.classList.add('open');
  try{
    const json = await api('/api/folders/choices?region_id=' + STATE.regionId);
    const currentFolder = STATE.groupId || STATE.currentFolderId;
    moveFolderSelect.innerHTML = '';
    json.folders.forEach(f => {
      const opt = document.createElement('option');
      opt.value = f.id;
      opt.textContent = f.path + (f.id === currentFolder ? '（当前）' : '');
      moveFolderSelect.appendChild(opt);
    });
    if(!json.folders.length){
      moveFolderSelect.innerHTML = '<option value="">无可用文件夹</option>';
    }
  }catch(err){
    toast(err.message);
    moveDialog.classList.remove('open');
  }
}

async function confirmVoid(row){
  const name = row.dataset.file;
  if(!confirm(`确定作废「${name}」？作废后将从列表隐藏，追溯记录保留。`)) return;
  try{
    await api('/api/files/' + row.dataset.fileId + '/void', { method: 'POST', body: '{}' });
    toast('已作废');
    await refreshFileLists();
    loadAcceptance();
    if(typeof loadBoard === 'function' && STATE.projectId){
      try{ await loadBoard(STATE.projectId); }catch(_e){}
    }
  }catch(err){
    toast(err.message);
  }
}

async function confirmDelete(row){
  const name = row.dataset.file;
  if(!confirm(`永久删除「${name}」？此操作不可恢复。`)) return;
  try{
    await api('/api/files/' + row.dataset.fileId, { method: 'DELETE' });
    toast('已删除');
    await refreshFileLists();
    if(typeof loadBoard === 'function' && STATE.projectId){
      try{ await loadBoard(STATE.projectId); }catch(_e){}
    }
  }catch(err){
    toast(err.message);
  }
}

$('#cancelRename')?.addEventListener('click', () => renameDialog.classList.remove('open'));
renameDialog?.addEventListener('click', (e) => { if(e.target === renameDialog) renameDialog.classList.remove('open'); });
renameForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(renameForm);
  const fileId = fd.get('file_id');
  const name = (fd.get('name') || '').trim();
  try{
    await api('/api/files/' + fileId, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    });
    renameDialog.classList.remove('open');
    toast('已重命名');
    await refreshFileLists();
  }catch(err){
    toast(err.message);
  }
});

$('#cancelMove')?.addEventListener('click', () => moveDialog.classList.remove('open'));
moveDialog?.addEventListener('click', (e) => { if(e.target === moveDialog) moveDialog.classList.remove('open'); });
moveForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(moveForm);
  const fileId = fd.get('file_id');
  const folderId = Number(fd.get('folder_id'));
  if(!folderId){ toast('请选择目标文件夹'); return; }
  try{
    await api('/api/files/' + fileId, {
      method: 'PATCH',
      body: JSON.stringify({ folder_id: folderId }),
    });
    moveDialog.classList.remove('open');
    toast('已移动');
    await refreshFileLists();
  }catch(err){
    toast(err.message);
  }
});
