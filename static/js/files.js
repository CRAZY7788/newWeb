const fileList=$('#fileList'), fileGroup=$('#fileGroup');
const uploadDialog=$('#uploadDialog'), uploadForm=$('#uploadForm');
const checkinDialog=$('#checkinDialog'), checkinForm=$('#checkinForm');

async function openFiles(groupId, groupName, opts={}){
  STATE.groupId = groupId;
  STATE.group = groupName;
  fileGroup.textContent = groupName;
  const uploadBtn = $('#uploadBtn');
  if(uploadBtn) uploadBtn.style.display = canEdit() ? '' : 'none';
  const json = await api('/api/files?folder_id='+groupId);
  fileList.innerHTML = '';
  json.files.forEach((f, idx)=>{
    const checked = !!f.checked_out_by;
    const row=document.createElement('div');
    row.className='row';
    row.dataset.file = f.name;
    row.dataset.fileId = f.id;
    row.dataset.checkedOut = checked ? 'true' : 'false';
    const owner = f.checked_out_by_name || '—';
    const ver = f.latest_version || '';
    const tagClass = f.status === '已借出' ? 'tag state out' : (f.status === '已验收' ? 'tag state ok' : 'tag state');
    row.innerHTML = `<span class="idx">${idx+1}.</span><span>${f.name} ${ver}</span><span class="${tagClass}">${f.status}</span><span class="owner">${owner}</span><span class="owner">${f.checked_out_at ? new Date(f.checked_out_at).toLocaleDateString() : ''}</span>`;
    row.ondblclick = ()=> window.open('/versions/download?file_id='+f.id);
    row.addEventListener('contextmenu', (e)=> openFileMenu(e,row));
    addLongPress(row, (e)=> openFileMenu(e,row));
    fileList.appendChild(row);
  });
  if(!opts.silent) show('files');
}

function openFileMenu(e,row){
  e.preventDefault();
  const items=[];
  if(canEdit()){
    items.push({
      text: row.dataset.checkedOut==='true' ? 'Check in' : 'Check out',
      action:()=> toggleCheckout(row)
    });
  }
  items.push({text:'历史版本', action:()=> openVersionsFromRow(row)});
  items.push({text:'文档追溯', action:()=> openTrace(Number(row.dataset.fileId), row.dataset.file)});
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
      body: JSON.stringify({file_id: fid})
    });
    toast('已 Check out');
    await openFiles(STATE.groupId, STATE.group);
  }catch(err){
    toast(err.message);
  }
}

function openCheckinDialog(fileId){
  checkinForm.reset();
  checkinForm.file_id.value = fileId;
  checkinDialog.classList.add('open');
}

$('#uploadBtn')?.addEventListener('click', ()=>{
  if(!canEdit()){ toast('当前角色不能上传'); return; }
  if(!STATE.groupId){ toast('请先进入分组'); return; }
  uploadForm.reset();
  uploadDialog.classList.add('open');
});
$('#cancelUpload')?.addEventListener('click', ()=> uploadDialog.classList.remove('open'));
uploadDialog?.addEventListener('click', (e)=>{ if(e.target===uploadDialog) uploadDialog.classList.remove('open'); });

uploadForm?.addEventListener('submit', async (e)=>{
  e.preventDefault();
  const fd = new FormData(uploadForm);
  fd.set('group_id', STATE.groupId);
  try{
    await apiForm('/api/files/upload', fd);
    uploadDialog.classList.remove('open');
    await openFiles(STATE.groupId, STATE.group);
    toast('上传成功');
  }catch(err){
    toast(err.message);
  }
});

$('#cancelCheckin')?.addEventListener('click', ()=> checkinDialog.classList.remove('open'));
checkinDialog?.addEventListener('click', (e)=>{ if(e.target===checkinDialog) checkinDialog.classList.remove('open'); });

checkinForm?.addEventListener('submit', async (e)=>{
  e.preventDefault();
  const fd = new FormData(checkinForm);
  try{
    await apiForm('/api/files/checkin', fd);
    checkinDialog.classList.remove('open');
    toast('已 Check in，进入待验收');
    await openFiles(STATE.groupId, STATE.group);
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
  const json = await api('/api/files/trace?file_id='+fileId);
  const f = json.file || {};
  $('#traceSummary').textContent = `${f.name || fileName} · 状态 ${f.status || ''} · 当前版本 ${f.latest_version || ''}`;
  const table = $('#traceVersionTable');
  table.innerHTML = '<tr><th>版本</th><th>时间</th><th>作者</th><th>说明</th><th>文件</th><th>SHA256</th></tr>';
  (json.versions || []).forEach(v=>{
    const tr = document.createElement('tr');
    const hash = v.sha256 ? v.sha256.slice(0,16)+'…' : '—';
    tr.innerHTML = `<td>${v.label}</td><td>${v.date||''}</td><td>${v.author||''}</td><td>${v.comment||''}</td><td>${v.original_filename||''}</td><td class="hash">${hash}</td>`;
    tr.style.cursor = 'pointer';
    tr.onclick = ()=> window.open('/versions/download?version_id='+v.id);
    table.appendChild(tr);
  });
  const audit = $('#traceAuditList');
  audit.innerHTML = '';
  (json.audit || []).forEach((a, idx)=>{
    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML = `<span class="idx">${idx+1}.</span><span>${a.action}</span><span class="tag">${a.user||''}</span><span>${a.created_at||''}</span><span>${a.detail||''}</span>`;
    audit.appendChild(row);
  });
  show('trace');
}
