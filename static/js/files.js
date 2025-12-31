const fileList=$('#fileList'), fileGroup=$('#fileGroup');

function openFiles(groupName){
  fileGroup.textContent=groupName; fileList.innerHTML=''; STATE.group=groupName;
  ['文件 A','文件 B','文件 C','文件 D'].forEach((name,idx)=>{
    const row=document.createElement('div'); row.className='row'; row.dataset.file=name; row.dataset.checkedOut='false';
    row.innerHTML = `<span class="idx">${idx+1}.</span><span>${name}</span><span class="tag state">草稿</span><span class="owner">owner ${idx+1}</span><span class="owner">${new Date().toLocaleDateString()}</span>`;
    row.ondblclick = ()=> toast('打开：'+name);
    row.addEventListener('contextmenu', (e)=> openFileMenu(e,row));
    addLongPress(row, (e)=> openFileMenu(e,row));
    fileList.appendChild(row);
  });
  show('files');
}

function openFileMenu(e,row){
  e.preventDefault();
  const items=[
    {text: row.dataset.checkedOut==='true'?'Check in':'Check out', action:()=> toggleCheckout(row)},
    {text:'历史版本', action:()=> openVersionsFromRow(row)}
  ];
  openContextMenu(e, items);
}

function toggleCheckout(row){
  const flag=row.dataset.checkedOut==='true';
  row.dataset.checkedOut=(!flag).toString();
  row.querySelector('.state').textContent = flag ? '草稿' : '已借出';
  toast(flag?'已 Check in':'已 Check out');
}
