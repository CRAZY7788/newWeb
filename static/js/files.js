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

function appendFileRows(container, files, { interactive = true } = {}){
  if(!container) return;
  container.innerHTML = '';
  if(!files.length){
    container.innerHTML = '<div class="row"><span></span><span class="muted">暂无文档，可点击「上传文档」。</span><span></span><span></span><span></span><span></span><span></span></div>';
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
    const owner = f.checked_out_by_name || '—';
    const ver = f.latest_version || '—';
    const tagClass = f.status === '已借出' ? 'tag state out' : (f.status === '已验收' ? 'tag state ok' : 'tag state');
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
  if(uploadBtn) uploadBtn.style.display = canEdit() ? '' : 'none';
  const json = await api('/api/files?folder_id=' + folderId);
  appendFileRows(fileList, json.files, { interactive: true });
  if(!opts.silent) show('files');
  return json.files;
}

async function loadFolderFilePreview(){
  const block = $('#folderFilesBlock');
  const list = $('#folderFileList');
  const uploadBtn = $('#detailUploadBtn');
  const manageBtn = $('#openFolderFilesBtn');
  if(!STATE.currentFolderId){
    if(block) block.hidden = true;
    if(uploadBtn) uploadBtn.style.display = 'none';
    if(manageBtn) manageBtn.style.display = 'none';
    return;
  }
  if(block) block.hidden = false;
  if(uploadBtn) uploadBtn.style.display = canEdit() ? '' : 'none';
  if(manageBtn) manageBtn.style.display = '';
  const json = await api('/api/files?folder_id=' + STATE.currentFolderId);
  appendFileRows(list, json.files, { interactive: false });
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
  if(canEdit()){
    items.push({
      text: row.dataset.checkedOut === 'true' ? 'Check in' : 'Check out',
      action: () => toggleCheckout(row),
    });
  }
  items.push({ text: '历史版本', action: () => openVersionsFromRow(row) });
  items.push({ text: '文档追溯', action: () => openTrace(Number(row.dataset.fileId), row.dataset.file) });
  openContextMenu(e, items);
}

async function toggleCheckout(row){
  const fid = Number(row.dataset.fileId);
  const checked = row.dataset.checkedOut === 'true';
  if(checked){
    openCheckinDialog(fid);
    return;
  }
  try{
    await api('/api/files/checkout', {
      method: 'POST',
      body: JSON.stringify({ file_id: fid }),
    });
    toast('已 Check out');
    await openFiles(STATE.groupId, STATE.group);
    await loadFolderFilePreview();
  }catch(err){
    toast(err.message);
  }
}

function openCheckinDialog(fileId){
  checkinForm.reset();
  checkinForm.file_id.value = fileId;
  checkinDialog.classList.add('open');
}

$('#uploadBtn')?.addEventListener('click', () => openUploadDialog(STATE.groupId));
$('#detailUploadBtn')?.addEventListener('click', () => openUploadDialog(STATE.currentFolderId));

$('#cancelUpload')?.addEventListener('click', () => uploadDialog.classList.remove('open'));
uploadDialog?.addEventListener('click', (e) => { if(e.target === uploadDialog) uploadDialog.classList.remove('open'); });

uploadForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(uploadForm);
  const folderId = getActiveFolderId();
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
    await openFiles(STATE.groupId, STATE.group);
    await loadFolderFilePreview();
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
