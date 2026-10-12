const fileList=$('#fileList'), fileGroup=$('#fileGroup');

async function openFiles(groupId, groupName){
  STATE.groupId = groupId;
  STATE.group = groupName;
  fileGroup.textContent = groupName;
  const json = await api('/api/files?group_id='+groupId);
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
    row.innerHTML = `<span class="idx">${idx+1}.</span><span>${f.name} ${ver}</span><span class="tag state">${f.status}</span><span class="owner">${owner}</span><span class="owner">${f.checked_out_at ? new Date(f.checked_out_at).toLocaleDateString() : ''}</span>`;
    row.ondblclick = ()=> window.open('/versions/download?file_id='+f.id);
    row.addEventListener('contextmenu', (e)=> openFileMenu(e,row));
    addLongPress(row, (e)=> openFileMenu(e,row));
    fileList.appendChild(row);
  });
  show('files');
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
  openContextMenu(e, items);
}

async function toggleCheckout(row){
  const fid = Number(row.dataset.fileId);
  const checked = row.dataset.checkedOut === 'true';
  try{
    await api(checked ? '/api/files/checkin' : '/api/files/checkout', {
      method: 'POST',
      body: JSON.stringify({file_id: fid})
    });
    toast(checked ? '已 Check in，进入待验收' : '已 Check out');
    await openFiles(STATE.groupId, STATE.group);
    loadAcceptance();
  }catch(err){
    toast(err.message);
  }
}
